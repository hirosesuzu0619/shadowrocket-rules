// 本文件由 tools/build_nextin.py 从 configs/tokyo.yaml 生成，不要手工编辑。
// 甲骨文节点配置用的覆写：规则与分流与东京版相同，美国规则先走名字带「美国」的节点、不通再换日本，其余先走日本、不通再换美国。
// 订阅里的节点原样保留，分组里的节点按节点名现填；订阅没有开启 DNS 时补上下面的 DNS，其余设置不动。规则集由内核按链接定时下载。
var PROXY_GROUPS = [
  {
    "name": "🚀 节点选择",
    "type": "select",
    "proxies": []
  },
  {
    "name": "🇺🇸 美国",
    "type": "fallback",
    "url": "https://www.gstatic.com/generate_204",
    "interval": 300,
    "proxies": []
  },
  {
    "name": "🛡️ 故障转移",
    "type": "fallback",
    "url": "https://www.gstatic.com/generate_204",
    "interval": 300,
    "proxies": []
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

var DNS = {
  "enable": true,
  "enhanced-mode": "fake-ip",
  "fake-ip-range": "198.18.0.1/16",
  "fake-ip-filter": [
    "*.lan",
    "*.local",
    "+.msftconnecttest.com",
    "+.msftncsi.com",
    "time.*.com",
    "+.ntp.org",
    "+.stun.*.*"
  ],
  "default-nameserver": [
    "223.5.5.5",
    "119.29.29.29"
  ],
  "nameserver": [
    "https://dns.alidns.com/dns-query",
    "https://doh.pub/dns-query"
  ]
};

var STATS_NODES = {
  "stats.jp.node": "甲骨文日本",
  "stats.us.node": "甲骨文美国"
};

var JP_NAME = /(日本|东京|東京)/;
var US_NAME = /(美国|美國)/;
var INFO_NODES = /(剩余|流量|套餐|到期|重置|官网|Traffic|Expire)/i;
var TOKYO_PROXY = "🚀 节点选择";
var TOKYO_US = "🇺🇸 美国";
var FALLBACK = "🛡️ 故障转移";

function main(config) {
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
  if (!config["dns"] || !config["dns"]["enable"]) config["dns"] = DNS;
  // 按节点名分出日本与美国；故障转移的顺序是日本、美国、其余节点
  var names = (config["proxies"] || []).map(function (p) { return p.name; }).filter(function (n) { return !INFO_NODES.test(n); });
  var jp = names.filter(function (n) { return JP_NAME.test(n); });
  var us = names.filter(function (n) { return US_NAME.test(n) && jp.indexOf(n) < 0; });
  var rest = names.filter(function (n) { return jp.indexOf(n) < 0 && us.indexOf(n) < 0; });
  var all = jp.concat(us, rest);
  var groups = JSON.parse(JSON.stringify(PROXY_GROUPS));
  var rules = RULES;
  groups.forEach(function (g) {
    if (g.name === TOKYO_PROXY) g.proxies = [FALLBACK].concat(all, ["DIRECT"]);
    if (g.name === FALLBACK) g.proxies = all.length ? all : ["DIRECT"];
    if (g.name === TOKYO_US) g.proxies = us.concat(jp, rest);
  });
  if (!us.length) {
    groups = groups.filter(function (g) { return g.name !== TOKYO_US; });
    rules = rules.map(function (r) { return r.replace("," + TOKYO_US, "," + TOKYO_PROXY); });
  }
  var stats = [];
  for (var host in STATS_NODES) {
    if (names.indexOf(STATS_NODES[host]) >= 0) stats.push("DOMAIN," + host + "," + STATS_NODES[host]);
  }
  config["proxy-groups"] = groups;
  config["rule-providers"] = providers;
  config["rules"] = stats.concat(rules);
  return config;
}
