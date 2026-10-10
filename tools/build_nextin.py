#!/usr/bin/env python3
"""把 modules/personal.module 的分组与规则并入 Nextin Hub 生成的 mihomo 模板，输出 configs/nextin.yaml。

模板原有内容一行不改，只在两处插入：
- 个人分组追加在 proxy-groups 末尾；
- 个人规则插在私有 IP 之后、广告拦截之前，与 Shadowrocket 里模块规则先于配置规则的顺序一致。
模板兜底的 MATCH 若指向代理，还会在它之前加一条 GEOSITE,cn,DIRECT，让国内域名直连；MATCH 已是 DIRECT 时不加。

同时把结果中的代理组与规则导出为 configs/clashmi.js，供 Clash Mi 作 JS 覆写使用（需要 PyYAML）。

另外生成只有东京静态住宅 IP 时用的 configs/tokyo.yaml 与 configs/tokyo.js：规则与上面相同，
所有代理分组合并成一个；兜底改为代理，之前先按国内域名、再按解析出的国内 IP 直连。

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
TOKYO_RULES = ROOT / "rules" / "tokyo"
RAW = "https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/"

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
BUILTIN = {"DIRECT", "REJECT", "REJECT-DROP", "PASS"}
# 东京版的兜底走代理，未命中的境外站点也从东京出去。只靠 GEOSITE,cn 识别国内域名时，apple.com、icloud.com、微软更新、
# Akamai 这类国内有 CDN 节点的境外服务都不在名单里，会全部挤上住宅线路，与 X 等服务抢带宽；所以再引用一次国内 IP 规则集、
# 不带 no-resolve：名单外的域名先在本机解析，落在国内 IP 段的直连。最终直连的域名本来就要在本机解析，结果会被缓存复用，
# 只有走代理的境外域名多一次本地查询。前面的规则集仍带 no-resolve，只拦直接连 IP 的请求，被墙名单也排在前面
TOKYO_TAIL = f"""  # 兜底 · 东京版追加：国内域名直连，其余域名在本机解析，落在国内 IP 段的也直连，剩下的走代理
  - "GEOSITE,cn,DIRECT"
  - "RULE-SET,tokyo-cn-ip,DIRECT"
  - "MATCH,{TOKYO_PROXY}"
"""
# Clash Verge 的扩展脚本存在本地，不能按链接订阅。所以东京版把常改的个人规则与庞大的国内 IP 段放进 rules/tokyo/ 下的规则集，
# 由 mihomo 按 raw 链接定时下载，脚本本身只剩分组与规则骨架，改了 personal.module 也不必重新粘贴
# 个人规则按策略拆成三个规则集，依次匹配拒绝、直连、代理；模块里直连与拒绝的条目本来就写在同类代理条目之前，顺序不受影响
TOKYO_SETS = {"REJECT": "reject", "DIRECT": "direct", TOKYO_PROXY: "proxy"}
# 下载规则集也走代理：raw.githubusercontent.com 在国内直连经常不通
TOKYO_PROVIDER = """  {name}:
    type: http
    behavior: {behavior}
    format: text
    url: "{url}"
    path: ./rules/{name}.list
    interval: {interval}
    proxy: "{proxy}"
"""


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
    providers = conf.get("rule-providers")
    for g in groups:
        if g.pop("include-all-proxies", False):
            g["include-all"] = True
    js = (
        "".join(f"// {line}\n" for line in intro)
        + "var PROXY_GROUPS = " + json.dumps(groups, ensure_ascii=False, indent=2) + ";\n\n"
        + ("var RULE_PROVIDERS = " + json.dumps(providers, ensure_ascii=False, indent=2) + ";\n\n" if providers else "")
        + "var RULES = [\n" + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in conf["rules"]) + "\n];\n\n"
        "function main(config) {\n"
        "  config[\"proxy-groups\"] = PROXY_GROUPS;\n"
        + ("  config[\"rule-providers\"] = RULE_PROVIDERS;\n" if providers else "")
        + "  config[\"rules\"] = RULES;\n"
        "  return config;\n"
        "}\n"
    )
    path.write_text(js, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}: {len(groups)} groups, {len(conf['rules'])} rules")


def tokyo(body):
    """把合并后的配置改成东京版，返回 (配置正文, {规则集文件名: 内容})。

    代理组换成 TOKYO_GROUPS；内置策略（DIRECT、REJECT 等）不动，凡是指向代理分组的一律改指 TOKYO_PROXY。个人规则与国内 IP 段移进规则集，原位置换成 RULE-SET。
    模板的 MATCH 换成 TOKYO_TAIL；模板兜底指向代理时 body 里已有的那条 GEOSITE,cn 一并去掉，免得重复。
    """
    start, end = body.index("\nproxy-groups:\n") + 1, body.index(GROUPS_ANCHOR)
    groups = set(re.findall(r'^  - name: "(.+)"$', body[start:end], re.M))
    personal = {k: [] for k in TOKYO_SETS}
    cn_ip, out, section = [], [], None
    for line in body[end:].splitlines(keepends=True):
        if line in CN_DIRECT.splitlines(keepends=True):
            continue
        if MATCH_RE.fullmatch(line):
            out.append(TOKYO_TAIL)
            continue
        m = re.match(r"  # (.+)", line)
        if m:
            name = m.group(1)
            section = name.split(" · ", 1)[1] if name.startswith("个人规则 · ") else None
            if section and not any(personal.values()):
                out.append("  # 个人规则 · 依次匹配拒绝、直连、代理三个规则集，内容见 rules/tokyo/\n")
                out += [f"  - {q(f'RULE-SET,tokyo-{v},{k}')}\n" for k, v in TOKYO_SETS.items()]
            if name.startswith("中国 IP"):
                out.append("  # 中国 IP · 规则集 rules/tokyo/cn-ip.list\n")
                out.append(f"  - {q('RULE-SET,tokyo-cn-ip,DIRECT,no-resolve')}\n")
            if section or name.startswith("中国 IP"):
                continue
        m = re.fullmatch(r'  - "(.+)"\n?', line)
        if m:
            parts = m.group(1).split(",")
            # MATCH 只有两段，策略在第二段；其余规则在第三段
            i = 1 if parts[0] == "MATCH" else 2
            if parts[i] not in BUILTIN:
                if parts[i] not in groups:
                    raise SystemExit(f"规则引用了未定义的分组：{parts[i]}")
                parts[i] = TOKYO_PROXY
            if section:
                personal[parts.pop(i)].append(",".join(parts))
                continue
            if out[-1].startswith("  - \"RULE-SET,tokyo-cn-ip,"):
                if parts[2] != "DIRECT" or parts[0] not in ("IP-CIDR", "IP-CIDR6"):
                    raise SystemExit(f"国内 IP 段里出现了意外的规则：{m.group(1)}")
                cn_ip.append(parts[1])
                continue
            line = f"  - {q(','.join(parts))}\n"
        out.append(line)
    if not cn_ip:
        raise SystemExit("模板里找不到中国 IP 段")
    if TOKYO_TAIL not in out:
        raise SystemExit("模板里找不到 MATCH 规则")

    lists = {f"{v}.list": personal[k] for k, v in TOKYO_SETS.items()}
    lists["cn-ip.list"] = cn_ip
    providers = "rule-providers:\n" + "".join(
        TOKYO_PROVIDER.format(
            name=f"tokyo-{f[:-5]}",
            behavior="ipcidr" if f == "cn-ip.list" else "classical",
            url=f"{RAW}rules/tokyo/{f}",
            # 个人规则改得勤，每小时检查一次；国内 IP 段一天一次
            interval=86400 if f == "cn-ip.list" else 3600,
            proxy=TOKYO_PROXY,
        )
        for f in lists
    )
    return body[:start] + TOKYO_GROUPS + "\n" + providers + "".join(out), lists


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
        "# 规则的条目与 nextin.yaml 相同，只是代理分组合并成一个：原先指向 US、MEXC_JP、BYBIT_TW、SG 与模板各 AI 分组的规则一律走「🚀 节点选择」。\n"
        "# 个人规则与国内 IP 段放在 rules/tokyo/ 下的规则集里，按链接定时下载；个人规则依次匹配拒绝、直连、代理三个规则集。\n"
        "# 兜底的 MATCH 走代理，之前先让国内域名（GEOSITE,cn）直连，再把其余域名在本机解析、落在国内 IP 段的也直连，减少挤上住宅线路的流量。\n"
    )
    tokyo_body, lists = tokyo(body)
    out = tokyo_header + tokyo_body
    TOKYO.write_text(out, encoding="utf-8")
    print(f"wrote {TOKYO.relative_to(ROOT)}")
    TOKYO_RULES.mkdir(exist_ok=True)
    for name, lines in lists.items():
        (TOKYO_RULES / name).write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        print(f"wrote {(TOKYO_RULES / name).relative_to(ROOT)}: {len(lines)} rules")
    write_js(out, TOKYO_JS, [
        "本文件由 tools/build_nextin.py 从 configs/tokyo.yaml 生成，不要手工编辑。",
        "Clash Verge 的扩展脚本：订阅里的节点、DNS 等设置原样保留，只把代理组、规则集与规则换成 tokyo.yaml 的。",
        "个人规则与国内 IP 段放在仓库的 rules/tokyo/ 下，由内核按链接定时下载；改了规则不必重新粘贴本脚本。",
    ])


if __name__ == "__main__":
    main()
