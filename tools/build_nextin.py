#!/usr/bin/env python3
"""把 modules/personal.module 的分组与规则并入 Nextin Hub 生成的 mihomo 模板，输出 configs/nextin.yaml。

模板原有内容一行不改，只在两处插入：
- 个人分组追加在 proxy-groups 末尾；
- 个人规则插在私有 IP 之后、广告拦截之前，与 Shadowrocket 里模块规则先于配置规则的顺序一致。

用法：python3 tools/build_nextin.py [模板文件或 URL]，不带参数时按 tools/nextin.url 里的地址重新下载模板。
"""
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE = ROOT / "modules" / "personal.module"
OUTPUT = ROOT / "configs" / "nextin.yaml"
URL_FILE = ROOT / "tools" / "nextin.url"

# 广告拦截之前插入个人规则
RULES_ANCHOR = "  # 广告拦截 · Nextin bundled MRS\n"
GROUPS_ANCHOR = "\nrules:\n"
# 这几段不搬：模板自带 OpenAI、Anthropic、Gemini 分组，交给模板处理，速度与纯 Nextin 模板一致
SKIP_SECTIONS = {"Claude", "OpenAI", "Gemini"}


def load_template(src):
    if src.startswith("http"):
        # Nextin Hub 会拒绝 Python 默认的 User-Agent（403），这里换成 curl 的
        req = urllib.request.Request(src, headers={"User-Agent": "curl/8.5.0"})
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8")
    return pathlib.Path(src).read_text(encoding="utf-8")


def sections(text):
    """按 [Section] 切分模块，返回 {名称: 行列表}。"""
    out, name = {}, None
    for line in text.splitlines():
        m = re.fullmatch(r"\[(.+)\]", line.strip())
        if m:
            name = m.group(1)
            out[name] = []
        elif name:
            out[name].append(line)
    return out


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def convert_group(line):
    name, rest = [x.strip() for x in line.split("=", 1)]
    params = [p.strip() for p in rest.split(",")]
    gtype = params[0]
    opts = dict(p.split(" = ", 1) for p in params[1:])
    regex = opts["policy-regex-filter"]
    # mihomo 用 Go 的正则，不支持否定前瞻：把 ^(?!.*(排除)).*(匹配) 拆成 filter 与 exclude-filter
    m = re.fullmatch(r"\(\?i\)\^\(\?!\.\*\((.+?)\)\)\.\*\((.+)\)", regex)
    if m:
        include, exclude = f"(?i)({m.group(2)})", f"(?i)({m.group(1)})"
    else:
        include, exclude = regex, None
    if "(?!" in include:
        raise SystemExit(f"无法转换的正则：{regex}")
    out = [f"  - name: {q(name)}", f"    type: {gtype}", "    include-all-proxies: true", f"    filter: {q(include)}"]
    if exclude:
        out.append(f"    exclude-filter: {q(exclude)}")
    if gtype in ("url-test", "fallback"):
        out.append(f"    url: {q(opts['url'])}")
        out.append(f"    interval: {opts['interval']}")
        if "tolerance" in opts:
            out.append(f"    tolerance: {opts['tolerance']}")
        out.append(f"    timeout: {int(opts.get('timeout', '5')) * 1000}")
    return name, out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else URL_FILE.read_text().strip()
    template = load_template(src)
    mod = sections(MODULE.read_text(encoding="utf-8"))

    rule_lines, used, title, skipping = [], set(), None, False
    for line in mod["Rule"]:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            # 只保留分段标题，作为 YAML 注释；没有规则的分段不输出标题
            if s.startswith("# ——"):
                name = s.strip("# —").strip()
                skipping = name in SKIP_SECTIONS
                title = f"  # 个人规则 · {name}"
            continue
        if skipping:
            continue
        # QUIC 相关的 AND 规则不搬：Nextin 模板本身不拦 QUIC，Claude 的放行例外也就无需存在
        if s.startswith("AND,") and "DST-PORT,443" in s:
            continue
        # 各类规则的策略都在第三个字段（IP-CIDR 之后还跟着 no-resolve）
        used.add(s.split(",")[2])
        if title:
            rule_lines.append(title)
            title = None
        rule_lines.append(f"  - {q(s)}")

    group_lines = []
    for line in mod["Proxy Group"]:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        name, out = convert_group(s)
        # 没有任何规则引用的分组不搬，避免多出空置分组
        if name in used:
            group_lines += out + [""]

    builtin = {"DIRECT", "REJECT"}
    names = {re.match(r'  - name: "(.+)"', l).group(1) for l in group_lines if l.startswith("  - name:")}
    missing = used - builtin - names
    if missing:
        raise SystemExit(f"规则引用了未定义的分组：{missing}")

    assert template.count(RULES_ANCHOR) == 1 and template.count(GROUPS_ANCHOR) == 1
    header = (
        "# 本文件由 tools/build_nextin.py 生成：在 Nextin Hub 模板之上并入 modules/personal.module 的分组与规则，模板原有内容未改动。\n"
        "# 个人规则排在私有地址之后、广告拦截之前；模块的 URL 重写与 MITM 在 mihomo 里没有对应功能，未搬入。\n"
        "# 模块里的 Claude、OpenAI、Gemini 三段未搬入，由模板自带的 Anthropic、OpenAI、Gemini 分组处理。\n"
    )
    out = header + template
    out = out.replace(GROUPS_ANCHOR, "\n" + "\n".join(group_lines).rstrip("\n") + "\n" + GROUPS_ANCHOR, 1)
    out = out.replace(RULES_ANCHOR, "\n".join(rule_lines) + "\n" + RULES_ANCHOR, 1)
    OUTPUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(names)} groups, {sum(1 for l in rule_lines if l.startswith('  - '))} rules")


if __name__ == "__main__":
    main()
