#!/usr/bin/env python3
"""把 modules/personal.module 的分组与规则并入 Nextin Hub 生成的 mihomo 模板，输出 configs/nextin.yaml。

模板原有内容一行不改，只在两处插入：
- 个人分组追加在 proxy-groups 末尾；
- 个人规则插在私有 IP 之后、广告拦截之前，与 Shadowrocket 里模块规则先于配置规则的顺序一致。
模板兜底的 MATCH 若指向代理，还会在它之前加一条 GEOSITE,cn,DIRECT，让国内域名直连；MATCH 已是 DIRECT 时不加。

同时把结果中的代理组与规则导出为 configs/clashmi.js，供 Clash Mi 作 JS 覆写使用（需要 PyYAML）。

另外生成只有东京静态住宅 IP 时用的 configs/tokyo.yaml 与 configs/tokyo.js：规则与上面相同，
所有代理分组合并成一个，按账号所在地走美国的几段改为直连。

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
TOKYO = ROOT / "configs" / "tokyo.yaml"
TOKYO_JS = ROOT / "configs" / "tokyo.js"

# 广告拦截之前插入个人规则
RULES_ANCHOR = "  # 广告拦截 · Nextin bundled MRS\n"
GROUPS_ANCHOR = "\nrules:\n"
# 模板的国内 IP 规则都带 no-resolve，按域名发起的请求匹配不上，B 站接口这类国内域名会落到 MATCH 走代理；
# 在 MATCH 之前补一条国内域名直连，排在被墙名单之后，境外域名不受影响；MATCH 本身已是 DIRECT 时这条多余，不加
CN_DIRECT = '  # 国内域名直连（个人追加）\n  - "GEOSITE,cn,DIRECT"\n'
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

# 东京版只有两个节点：主入口与备入口，出口是同一个静态住宅 IP。所有代理规则都指向「🚀 节点选择」，
# 它默认用「🛡️ 故障转移」，按订阅里的节点顺序先用主入口，主入口不通才换备入口；也可以手动选定某个入口
TOKYO_PROXY = "🚀 节点选择"
INFO_NODES = "(?i)(剩余|流量|套餐|到期|重置|官网|Traffic|Expire)"
TOKYO_GROUPS = f"""proxy-groups:
  - name: "{TOKYO_PROXY}"
    type: select
    include-all-proxies: true
    exclude-filter: "{INFO_NODES}"
    proxies:
      - "🛡️ 故障转移"
      - DIRECT
  - name: "🛡️ 故障转移"
    type: fallback
    include-all-proxies: true
    exclude-filter: "{INFO_NODES}"
    url: "https://www.gstatic.com/generate_204"
    interval: 300
"""
# 这几段原本按账号所在地钉在 US。东京版没有美国出口，改为直连，交给设备自己的美国漫游流量
TOKYO_US_HOME = {"希尔顿", "Kraken", "Kalshi", "Equifax", "美国金融与运营商"}
BUILTIN = {"DIRECT", "REJECT", "REJECT-DROP", "PASS"}


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


def write_js(text, path, intro):
    """导出 JS 覆写：订阅的节点、DNS 等设置原样保留，只换掉代理组与规则。

    nextin.yaml 里的 proxies 是空的，直接当 YAML 覆写可能把订阅节点一并清空，所以改用脚本只替换这两项。
    include-all-proxies 换成 include-all，订阅若用 proxy-providers 下发节点也能纳入各组。
    Clash Mi 与 Clash Verge 的扩展脚本都调用 main(config)，同一份脚本两边通用。
    """
    conf = yaml.safe_load(text)
    groups = conf["proxy-groups"]
    for g in groups:
        if g.pop("include-all-proxies", False):
            g["include-all"] = True
    js = (
        "".join(f"// {line}\n" for line in intro)
        + "var PROXY_GROUPS = " + json.dumps(groups, ensure_ascii=False, indent=2) + ";\n\n"
        "var RULES = [\n" + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in conf["rules"]) + "\n];\n\n"
        "function main(config) {\n"
        "  config[\"proxy-groups\"] = PROXY_GROUPS;\n"
        "  config[\"rules\"] = RULES;\n"
        "  return config;\n"
        "}\n"
    )
    path.write_text(js, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}: {len(groups)} groups, {len(conf['rules'])} rules")


def tokyo(body):
    """把合并后的配置改成东京版：代理组换成 TOKYO_GROUPS，规则逐条改指向。

    内置策略（DIRECT、REJECT 等）不动；TOKYO_US_HOME 几段改为 DIRECT；其余凡是指向代理分组的一律改指 TOKYO_PROXY。
    """
    start, end = body.index("\nproxy-groups:\n") + 1, body.index(GROUPS_ANCHOR)
    groups = set(re.findall(r'^  - name: "(.+)"$', body[start:end], re.M))
    out, section, seen = [], None, set()
    for line in body[end:].splitlines(keepends=True):
        m = re.match(r"  # (.+)", line)
        if m:
            name = m.group(1)
            section = name.split(" · ", 1)[1] if name.startswith("个人规则 · ") else None
            seen.add(section)
        m = re.fullmatch(r'  - "(.+)"\n?', line)
        if m:
            parts = m.group(1).split(",")
            # MATCH 只有两段，策略在第二段；其余规则在第三段
            i = 1 if parts[0] == "MATCH" else 2
            if parts[i] not in BUILTIN:
                if parts[i] not in groups:
                    raise SystemExit(f"规则引用了未定义的分组：{parts[i]}")
                parts[i] = "DIRECT" if section in TOKYO_US_HOME else TOKYO_PROXY
                line = f"  - {q(','.join(parts))}\n"
        out.append(line)
    if TOKYO_US_HOME - seen:
        raise SystemExit(f"模块里找不到这些分段：{TOKYO_US_HOME - seen}")
    return body[:start] + TOKYO_GROUPS + "".join(out)


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
    assert len(MATCH_RE.findall(template)) == 1
    match_direct = MATCH_RE.search(template).group(1) == "DIRECT"
    header = (
        "# 本文件由 tools/build_nextin.py 生成：在 Nextin Hub 模板之上并入 modules/personal.module 的分组与规则，模板原有内容未改动。\n"
        "# 个人规则排在私有地址之后、广告拦截之前；模块的 URL 重写与 MITM 在 mihomo 里没有对应功能，未搬入。\n"
        "# Claude 主站（claude 关键字与 anthropic.com）以及 OpenAI、Gemini 两段未搬入，由模板自带的 Anthropic、OpenAI、Gemini 分组处理；Claude 的人机验证、statsig 与遥测风控域名改指模板的 Anthropic 分组，与主站同一出口。\n"
    ) + (
        "# 模板兜底的 MATCH 为 DIRECT：未命中任何规则的连接一律直连。\n"
        if match_direct else
        "# 兜底的 MATCH 之前追加了 GEOSITE,cn,DIRECT：模板的国内 IP 规则带 no-resolve，不加这条时国内域名会走代理。\n"
    )
    body = template.replace(GROUPS_ANCHOR, "\n" + "\n".join(group_lines).rstrip("\n") + "\n" + GROUPS_ANCHOR, 1)
    body = body.replace(RULES_ANCHOR, "\n".join(rule_lines) + "\n" + RULES_ANCHOR, 1)
    if not match_direct:
        body = MATCH_RE.sub(lambda m: CN_DIRECT + m.group(0), body, count=1)
    out = header + body
    OUTPUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(names)} groups, {sum(1 for l in rule_lines if l.startswith('  - '))} rules")
    write_js(out, CLASHMI, [
        "本文件由 tools/build_nextin.py 从 configs/nextin.yaml 生成，不要手工编辑。",
        "Clash Mi 的 JS 覆写：订阅里的节点、DNS 等设置原样保留，只把代理组与规则换成 nextin.yaml 的。",
    ])

    tokyo_header = (
        "# 本文件由 tools/build_nextin.py 生成，是 configs/nextin.yaml 的东京静态住宅 IP 版，供只有东京主、备两个入口节点时使用。\n"
        "# 规则的条目与顺序和 nextin.yaml 相同，只是代理分组合并成一个：原先指向 US、MEXC_JP、BYBIT_TW、SG 与模板各 AI 分组的规则一律走「🚀 节点选择」。\n"
        "# 希尔顿、Kraken、Kalshi、Equifax 与美国金融运营商几段原本按账号所在地走 US，这里改为直连，交给设备自己的美国漫游流量。\n"
    ) + header.splitlines(keepends=True)[-1]
    out = tokyo_header + tokyo(body)
    TOKYO.write_text(out, encoding="utf-8")
    print(f"wrote {TOKYO.relative_to(ROOT)}")
    write_js(out, TOKYO_JS, [
        "本文件由 tools/build_nextin.py 从 configs/tokyo.yaml 生成，不要手工编辑。",
        "Clash Verge 的扩展脚本：订阅里的节点、DNS 等设置原样保留，只把代理组与规则换成 tokyo.yaml 的。",
    ])


if __name__ == "__main__":
    main()
