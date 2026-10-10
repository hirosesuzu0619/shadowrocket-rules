// 本文件由 tools/build_nextin.py 从 configs/tokyo.yaml 生成，不要手工编辑。
// Clash Verge 的扩展脚本：订阅里的节点、DNS 等设置原样保留，只把代理组、规则集与规则换成 tokyo.yaml 的。
// 个人规则与国内 IP 段放在仓库的 rules/tokyo/ 下，由内核按链接定时下载；改了规则不必重新粘贴本脚本。
var PROXY_GROUPS = [
  {
    "name": "🚀 节点选择",
    "type": "select",
    "exclude-filter": "(?i)(剩余|流量|套餐|到期|重置|官网|Traffic|Expire)",
    "proxies": [
      "🛡️ 故障转移",
      "DIRECT"
    ],
    "include-all": true
  },
  {
    "name": "🛡️ 故障转移",
    "type": "fallback",
    "exclude-filter": "(?i)(剩余|流量|套餐|到期|重置|官网|Traffic|Expire)",
    "url": "https://www.gstatic.com/generate_204",
    "interval": 300,
    "include-all": true
  }
];

var RULE_PROVIDERS = {
  "tokyo-reject": {
    "type": "http",
    "behavior": "classical",
    "format": "text",
    "url": "https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/rules/tokyo/reject.list",
    "path": "./rules/tokyo-reject.list",
    "interval": 3600,
    "proxy": "🚀 节点选择"
  },
  "tokyo-direct": {
    "type": "http",
    "behavior": "classical",
    "format": "text",
    "url": "https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/rules/tokyo/direct.list",
    "path": "./rules/tokyo-direct.list",
    "interval": 3600,
    "proxy": "🚀 节点选择"
  },
  "tokyo-proxy": {
    "type": "http",
    "behavior": "classical",
    "format": "text",
    "url": "https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/rules/tokyo/proxy.list",
    "path": "./rules/tokyo-proxy.list",
    "interval": 3600,
    "proxy": "🚀 节点选择"
  },
  "tokyo-cn-ip": {
    "type": "http",
    "behavior": "ipcidr",
    "format": "text",
    "url": "https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/rules/tokyo/cn-ip.list",
    "path": "./rules/tokyo-cn-ip.list",
    "interval": 86400,
    "proxy": "🚀 节点选择"
  }
};

var RULES = [
  "GEOSITE,private,DIRECT",
  "IP-CIDR,0.0.0.0/8,DIRECT,no-resolve",
  "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
  "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
  "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
  "IP-CIDR,169.254.0.0/16,DIRECT,no-resolve",
  "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
  "IP-CIDR,192.0.0.0/24,DIRECT,no-resolve",
  "IP-CIDR,192.0.2.0/24,DIRECT,no-resolve",
  "IP-CIDR,192.88.99.0/24,DIRECT,no-resolve",
  "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
  "IP-CIDR,198.18.0.0/15,DIRECT,no-resolve",
  "IP-CIDR,198.51.100.0/24,DIRECT,no-resolve",
  "IP-CIDR,203.0.113.0/24,DIRECT,no-resolve",
  "IP-CIDR,224.0.0.0/3,DIRECT,no-resolve",
  "IP-CIDR6,::/127,DIRECT,no-resolve",
  "IP-CIDR6,fc00::/7,DIRECT,no-resolve",
  "IP-CIDR6,fe80::/10,DIRECT,no-resolve",
  "IP-CIDR6,ff00::/8,DIRECT,no-resolve",
  "RULE-SET,tokyo-reject,REJECT",
  "RULE-SET,tokyo-direct,DIRECT",
  "RULE-SET,tokyo-proxy,🚀 节点选择",
  "GEOSITE,category-ads-all,REJECT",
  "GEOSITE,tracker,REJECT",
  "GEOSITE,openai,🚀 节点选择",
  "GEOSITE,anthropic,🚀 节点选择",
  "GEOSITE,google-gemini,🚀 节点选择",
  "GEOSITE,category-ai-!cn,🚀 节点选择",
  "RULE-SET,tokyo-cn-ip,DIRECT,no-resolve",
  "GEOSITE,gfw,🚀 节点选择",
  "GEOSITE,cn,DIRECT",
  "MATCH,🚀 节点选择"
];

function main(config) {
  config["proxy-groups"] = PROXY_GROUPS;
  config["rule-providers"] = RULE_PROVIDERS;
  config["rules"] = RULES;
  return config;
}
