#!/usr/bin/env python3
"""把 modules/personal.module 的分组与规则并入 Nextin Hub 生成的 mihomo 模板，输出 configs/nextin.yaml。

模板原有内容一行不改，只在两处插入：
- 个人分组追加在 proxy-groups 末尾；
- 个人规则插在私有 IP 之后、广告拦截之前，与 Shadowrocket 里模块规则先于配置规则的顺序一致。
模板兜底的 MATCH 若指向代理，还会在它之前加一条 GEOSITE,cn,DIRECT，让国内域名直连；MATCH 已是 DIRECT 时不加。
另外关闭 IPv6：顶层加 ipv6: false，个人规则最前面再加一条拒绝全部 IPv6 地址的规则，与 base.conf 的 ipv6 = false 对应。

同时把结果中的代理组与规则导出为 configs/clashmi.js，供 Clash Mi 作 JS 覆写使用（需要 PyYAML）。

用法：python3 tools/build_nextin.py [模板文件或 URL]，不带参数时按 tools/nextin.url 里的地址重新下载模板。
"""
import json
import pathlib
import re
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE = ROOT / "modules" / "personal.module"
OUTPUT = ROOT / "configs" / "nextin.yaml"
CLASHMI = ROOT / "configs" / "clashmi.js"
URL_FILE = ROOT / "tools" / "nextin.url"

# 广告拦截之前插入个人规则
RULES_ANCHOR = "  # 广告拦截 · Nextin bundled MRS\n"
GROUPS_ANCHOR = "\nrules:\n"
# 模板的国内 IP 规则都带 no-resolve，按域名发起的请求匹配不上，B 站接口这类国内域名会落到 MATCH 走代理；
# 在 MATCH 之前补一条国内域名直连，排在被墙名单之后，境外域名不受影响；MATCH 本身已是 DIRECT 时这条多余，不加
CN_DIRECT = '  # 国内域名直连（个人追加）\n  - "GEOSITE,cn,DIRECT"\n'
# 关闭 IPv6，与 base.conf 的 ipv6 = false 对应：微信在有 IPv6 的网络下优先走 IPv6，客户端处理不好时会连不上。
# 客户端可能用自己的设置覆盖顶层的 ipv6，所以规则里再拒绝全部 IPv6 地址，让 App 立即改用 IPv4；
# 这条排在私有地址之后，局域网与链路本地的 IPv6 仍然直连
IPV6_ANCHOR = "\nproxies:"
IPV6_OFF = "\nipv6: false\n"
IPV6_REJECT = ['  # 关闭 IPv6（个人追加）', '  - "IP-CIDR6,::/0,REJECT,no-resolve"']
MATCH_RE = re.compile(r'^  - "MATCH,([^"]*)"\n', re.M)
# 这几段交给模板自带的 OpenAI、Anthropic、Gemini 分组处理，速度与纯 Nextin 模板一致
# 值为 None 表示整段不搬；Claude 段只去掉主站两条，其余见下方 FOLLOW_GEOSITE
SKIP_RULES = {
    "Claude": {"DOMAIN-KEYWORD,claude,US", "DOMAIN-SUFFIX,anthropic.com,US"},
    "OpenAI": None,
    "Gemini": None,
}
# 这些分段里剩下的规则改指模板里某条 GEOSITE 规则的目标分组：Claude 的人机验证、statsig 与遥测风控要与主站同一出口，
# 所以跟随模板的 Anthropic 分组；分组名从模板读取，Nextin 改名也不受影响
FOLLOW_GEOSITE = {"Claude": "anthropic"}


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


def write_clashmi(text):
    """导出 Clash Mi 的 JS 覆写：订阅的节点、DNS 等设置原样保留，只换掉代理组与规则。

    nextin.yaml 里的 proxies 是空的，直接当 YAML 覆写可能把订阅节点一并清空，所以改用脚本只替换这两项。
    include-all-proxies 换成 include-all，订阅若用 proxy-providers 下发节点也能纳入各组。
    """
    conf = yaml.safe_load(text)
    groups = conf["proxy-groups"]
    for g in groups:
        if g.pop("include-all-proxies", False):
            g["include-all"] = True
    js = (
        "// 本文件由 tools/build_nextin.py 从 configs/nextin.yaml 生成，不要手工编辑。\n"
        "// Clash Mi 的 JS 覆写：订阅里的节点、DNS 等设置原样保留，只把代理组与规则换成 nextin.yaml 的。\n"
        "var PROXY_GROUPS = " + json.dumps(groups, ensure_ascii=False, indent=2) + ";\n\n"
        "var RULES = [\n" + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in conf["rules"]) + "\n];\n\n"
        "function main(config) {\n"
        "  config[\"proxy-groups\"] = PROXY_GROUPS;\n"
        "  config[\"rules\"] = RULES;\n"
        "  return config;\n"
        "}\n"
    )
    CLASHMI.write_text(js, encoding="utf-8")
    print(f"wrote {CLASHMI.relative_to(ROOT)}: {len(groups)} groups, {len(conf['rules'])} rules")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else URL_FILE.read_text().strip()
    template = load_template(src)
    mod = sections(MODULE.read_text(encoding="utf-8"))

    template_groups = set(re.findall(r'^  - name: "(.+)"$', template, re.M))
    rule_lines, used, title, skip, follow = [], set(), None, set(), None
    for line in mod["Rule"]:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            # 只保留分段标题，作为 YAML 注释；没有规则的分段不输出标题
            if s.startswith("# ——"):
                name = s.strip("# —").strip()
                skip = SKIP_RULES.get(name, set())
                follow = None
                if name in FOLLOW_GEOSITE:
                    m = re.search(rf'^  - "GEOSITE,{re.escape(FOLLOW_GEOSITE[name])},(.+)"$', template, re.M)
                    if not m:
                        raise SystemExit(f"模板里找不到 GEOSITE,{FOLLOW_GEOSITE[name]} 规则")
                    follow = m.group(1)
                title = f"  # 个人规则 · {name}"
            continue
        if skip is None or s in skip:
            continue
        # QUIC 相关的 AND 规则不搬：Nextin 模板本身不拦 QUIC，Claude 的放行例外也就无需存在
        if s.startswith("AND,") and "DST-PORT,443" in s:
            continue
        # 各类规则的策略都在第三个字段（IP-CIDR 之后还跟着 no-resolve）
        if follow:
            parts = s.split(",")
            parts[2] = follow
            s = ",".join(parts)
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
    missing = used - builtin - names - template_groups
    if missing:
        raise SystemExit(f"规则引用了未定义的分组：{missing}")

    assert template.count(RULES_ANCHOR) == 1 and template.count(GROUPS_ANCHOR) == 1
    assert template.count(IPV6_ANCHOR) == 1 and not re.search(r"^ipv6:", template, re.M)
    assert len(MATCH_RE.findall(template)) == 1
    match_direct = MATCH_RE.search(template).group(1) == "DIRECT"
    header = (
        "# 本文件由 tools/build_nextin.py 生成：在 Nextin Hub 模板之上并入 modules/personal.module 的分组与规则，模板原有内容未改动。\n"
        "# 个人规则排在私有地址之后、广告拦截之前；模块的 URL 重写与 MITM 在 mihomo 里没有对应功能，未搬入。\n"
        "# 关闭 IPv6：顶层 ipv6: false，个人规则最前面拒绝全部 IPv6 地址，App 会立即改用 IPv4。\n"
        "# Claude 主站（claude 关键字与 anthropic.com）以及 OpenAI、Gemini 两段未搬入，由模板自带的 Anthropic、OpenAI、Gemini 分组处理；Claude 的人机验证、statsig 与遥测风控域名改指模板的 Anthropic 分组，与主站同一出口。\n"
    ) + (
        "# 模板兜底的 MATCH 为 DIRECT：未命中任何规则的连接一律直连。\n"
        if match_direct else
        "# 兜底的 MATCH 之前追加了 GEOSITE,cn,DIRECT：模板的国内 IP 规则带 no-resolve，不加这条时国内域名会走代理。\n"
    )
    out = header + template
    out = out.replace(GROUPS_ANCHOR, "\n" + "\n".join(group_lines).rstrip("\n") + "\n" + GROUPS_ANCHOR, 1)
    out = out.replace(RULES_ANCHOR, "\n".join(IPV6_REJECT + rule_lines) + "\n" + RULES_ANCHOR, 1)
    out = out.replace(IPV6_ANCHOR, IPV6_OFF + IPV6_ANCHOR, 1)
    if not match_direct:
        out = MATCH_RE.sub(lambda m: CN_DIRECT + m.group(0), out, count=1)
    OUTPUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(names)} groups, {sum(1 for l in rule_lines if l.startswith('  - '))} rules")
    write_clashmi(out)


if __name__ == "__main__":
    main()
