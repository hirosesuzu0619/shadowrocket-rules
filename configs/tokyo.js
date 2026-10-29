// 本文件由 tools/build_nextin.py 从 configs/tokyo.yaml 生成，除了下面的 US_SUBSCRIPTION 不要手工编辑。
// Clash Verge 的扩展脚本：订阅里的节点、DNS 等设置原样保留，只把代理组、规则集与规则换成 tokyo.yaml 的，
// 订阅 DNS 设置引用到的规则集一并保留；填了美国订阅链接时再加入美国节点。
// 个人规则与国内 IP 段放在仓库的 rules/tokyo/ 下，由内核按链接定时下载；改了规则不必重新粘贴本脚本。
var PROXY_GROUPS = [
  {
    "name": "🚀 节点选择",
    "type": "select",
    "include-all-proxies": true,
    "filter": "(日本|东京)",
    "exclude-filter": "(?i)(剩余|流量|套餐|到期|重置|官网|Traffic|Expire)",
    "proxies": [
      "🛡️ 故障转移",
      "DIRECT"
    ]
  },
  {
    "name": "🇺🇸 美国",
    "type": "fallback",
    "use": [
      "us"
    ],
    "exclude-filter": "(?i)(剩余|流量|套餐|到期|重置|官网|Traffic|Expire)",
    "url": "https://www.gstatic.com/generate_204",
    "interval": 300
  },
  {
    "name": "🛡️ 故障转移",
    "type": "fallback",
    "include-all-proxies": true,
    "exclude-filter": "(?i)(剩余|流量|套餐|到期|重置|官网|Traffic|Expire)",
    "url": "https://www.gstatic.com/generate_204",
    "interval": 300
  }
];

var PROXY_PROVIDERS = {
  "us": {
    "type": "http",
    "url": "https://example.invalid/fill-in-US_SUBSCRIPTION",
    "path": "./proxies/us.yaml",
    "interval": 86400,
    "proxy": "🚀 节点选择"
  }
};

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
  "tokyo-us": {
    "type": "http",
    "behavior": "classical",
    "format": "text",
    "url": "https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/rules/tokyo/us.list",
    "path": "./rules/tokyo-us.list",
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
  "IP-CIDR,192.31.196.0/24,DIRECT,no-resolve",
  "IP-CIDR,192.52.193.0/24,DIRECT,no-resolve",
  "IP-CIDR,192.88.99.0/24,DIRECT,no-resolve",
  "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
  "IP-CIDR,198.18.0.0/15,DIRECT,no-resolve",
  "IP-CIDR,198.51.100.0/24,DIRECT,no-resolve",
  "IP-CIDR,203.0.113.0/24,DIRECT,no-resolve",
  "IP-CIDR,224.0.0.0/3,DIRECT,no-resolve",
  "IP-CIDR6,::/127,DIRECT,no-resolve",
  "IP-CIDR6,64:ff9b::/96,DIRECT,no-resolve",
  "IP-CIDR6,64:ff9b:1::/48,DIRECT,no-resolve",
  "IP-CIDR6,100::/64,DIRECT,no-resolve",
  "IP-CIDR6,2001::/23,DIRECT,no-resolve",
  "IP-CIDR6,2001:db8::/32,DIRECT,no-resolve",
  "IP-CIDR6,2620:4f:8000::/48,DIRECT,no-resolve",
  "IP-CIDR6,3fff::/20,DIRECT,no-resolve",
  "IP-CIDR6,5f00::/16,DIRECT,no-resolve",
  "IP-CIDR6,fc00::/7,DIRECT,no-resolve",
  "IP-CIDR6,fe80::/10,DIRECT,no-resolve",
  "IP-CIDR6,ff00::/8,DIRECT,no-resolve",
  "RULE-SET,tokyo-reject,REJECT",
  "RULE-SET,tokyo-direct,DIRECT",
  "AND,((NETWORK,UDP),(DST-PORT,443),(RULE-SET,tokyo-us)),REJECT",
  "RULE-SET,tokyo-us,🇺🇸 美国",
  "AND,((NETWORK,UDP),(DST-PORT,443),(RULE-SET,tokyo-proxy)),REJECT",
  "RULE-SET,tokyo-proxy,🚀 节点选择",
  "GEOSITE,category-ads-all,REJECT",
  "GEOSITE,tracker,REJECT",
  "AND,((NETWORK,UDP),(DST-PORT,443),(GEOSITE,openai)),REJECT",
  "GEOSITE,openai,🚀 节点选择",
  "AND,((NETWORK,UDP),(DST-PORT,443),(GEOSITE,anthropic)),REJECT",
  "GEOSITE,anthropic,🇺🇸 美国",
  "AND,((NETWORK,UDP),(DST-PORT,443),(GEOSITE,google-gemini)),REJECT",
  "GEOSITE,google-gemini,🇺🇸 美国",
  "AND,((NETWORK,UDP),(DST-PORT,443),(GEOSITE,category-ai-!cn)),REJECT",
  "GEOSITE,category-ai-!cn,🇺🇸 美国",
  "RULE-SET,tokyo-cn-ip,DIRECT,no-resolve",
  "AND,((NETWORK,UDP),(DST-PORT,443),(GEOSITE,gfw)),REJECT",
  "GEOSITE,gfw,🚀 节点选择",
  "GEOSITE,cn,DIRECT",
  "RULE-SET,tokyo-cn-ip,DIRECT",
  "AND,((NETWORK,UDP),(DST-PORT,443)),REJECT",
  "MATCH,🚀 节点选择"
];

// 美国订阅链接填在下面的引号里，保存后重新激活订阅即可。仓库是公开的，填好的脚本只留在本机，不要提交回来。
// 留空时不建美国组，AI 与美国金融等规则一并走「🚀 节点选择」，与只有东京订阅时一样。
var US_SUBSCRIPTION = "";

var TOKYO_PROXY = "🚀 节点选择";
var TOKYO_US = "🇺🇸 美国";

function main(config) {
  var groups = PROXY_GROUPS;
  var rules = RULES;
  // 订阅自带的 DNS 设置可能用 rule-set:名称 引用订阅里的规则集（如 nameserver-policy、fake-ip-filter 里的 cn-domain），
  // 整体换掉规则集时内核会报 not found rule-set 而拒绝加载，所以把 DNS 引用到的那几个保留下来
  var old = config["rule-providers"] || {};
  var providers = {};
  var refs = JSON.stringify(config["dns"] || {}).match(/rule-set:[^"]+/g) || [];
  refs.forEach(function (ref) {
    ref.slice(9).split(",").forEach(function (name) {
      if (old[name]) providers[name] = old[name];
    });
  });
  for (var name in RULE_PROVIDERS) providers[name] = RULE_PROVIDERS[name];
  if (US_SUBSCRIPTION) {
    var us = JSON.parse(JSON.stringify(PROXY_PROVIDERS["us"]));
    us.url = US_SUBSCRIPTION;
    config["proxy-providers"] = config["proxy-providers"] || {};
    config["proxy-providers"]["us"] = us;
  } else {
    groups = groups.filter(function (g) { return g.name !== TOKYO_US; });
    rules = rules.map(function (r) { return r.replace("," + TOKYO_US, "," + TOKYO_PROXY); });
  }
  config["proxy-groups"] = groups;
  config["rule-providers"] = providers;
  config["rules"] = rules;
  return config;
}
