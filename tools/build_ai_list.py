#!/usr/bin/env python3
"""把 MetaCubeX 的 category-ai-!cn 名单转成 Shadowrocket 的 DOMAIN-SET，输出 rules/ai.list。

与 Nextin Hub 模板「AI 平台合集」用的是同一份来源，base.conf 按 DOMAIN-SET 引用，送到 AI_US 组。
mihomo 的写法里 "+.example.com" 表示域名本身及其子域名，Shadowrocket 的 DOMAIN-SET 写作 ".example.com"；
不带前缀的条目两边都只匹配该域名本身，原样保留。

用法：python3 tools/build_ai_list.py
"""
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "rules" / "ai.list"
SOURCE = "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/category-ai-!cn.list"
DOMAIN_RE = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)+")


def main():
    with urllib.request.urlopen(SOURCE) as resp:
        text = resp.read().decode("utf-8")
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        suffix = s.startswith("+.")
        domain = s[2:] if suffix else s
        # 名单里若出现关键字或正则条目，DOMAIN-SET 表达不了，直接报错而不是悄悄丢掉
        if not DOMAIN_RE.fullmatch(domain):
            raise SystemExit(f"无法转换的条目：{s}")
        out.append("." + domain if suffix else domain)
    header = (
        "# 本文件由 tools/build_ai_list.py 生成，不要手工编辑。\n"
        f"# 来源：{SOURCE}（MetaCubeX/meta-rules-dat，GPL-3.0），与 Nextin Hub 模板的「AI 平台合集」同源。\n"
    )
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(header + "\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(out)} domains")


if __name__ == "__main__":
    main()
