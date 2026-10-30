# shadowrocket-rules

个人使用的代理分流规则，目前有两套：手机上的 Shadowrocket（`configs/base.conf` 加 `modules/personal.module`），以及 Clash Mi 连甲骨文日本、美国两个节点时用的覆写 `configs/oracle.js`。个人规则只写在 `personal.module` 一处，`oracle.js` 与它引用的 `rules/tokyo/` 规则集都由脚本从模块生成。仓库是公开的，文件里不含订阅链接、节点凭据或证书。

设备都按默认分支的 raw 链接（`https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/...`）加载，改动合并到默认分支才会生效。本文只写现状，每次调整的原因与试验经过见 git 提交记录。

## Shadowrocket

### configs/base.conf

基础配置只负责「国内直连、国外代理」这一层兜底。Shadowrocket 把模块规则排在配置规则之前，所以 `personal.module` 先匹配，没命中的才轮到这里。规则依次是：局域网直连；AI 服务（`rules/ai.list`）走 `AI_US`；国内名单（blackmatrix7 的 `China.list` 与 `China_Domain.list`）直连；Google、YouTube、GitHub、Netflix 等常用境外服务按域名走 `OVERSEAS`，其中 Telegram 的域名与 IP 段走 `TELEGRAM`；被墙名单（Loyalsoldier 的 `gfw.txt`）走 `OVERSEAS`；都没命中时按解析出的 IP 判断，`GEOIP,CN` 直连，其余 `FINAL,OVERSEAS`。常用境外名单没有引用 blackmatrix7 的 `Global` 或 `Proxy`，因为它们包含 apple.com、icloud.com、microsoft.com 这类国内也在用的域名，会把 iCloud 和系统更新一并改走代理。

三个策略组都是 `url-test`，按延迟自动择优，`tolerance = 50` 让延迟相差不到 50 毫秒时不切换，每 300 秒测速一次，都排除倍率节点和「剩余流量」「套餐到期」这类信息节点。`OVERSEAS` 是通用出口，候选是排除香港、新加坡、台湾之后的全部节点，实际多落在日本、韩国：香港延迟最低却在高峰期带宽跟不上，所以排除。`AI_US` 只用美国节点。`TELEGRAM` 用香港、日本、韩国、新加坡节点，测速地址是 `telegram.org`，因为到 gstatic 的延迟反映不出节点到 Telegram 机房的线路。

`rules/ai.list` 由 `tools/build_ai_list.py` 从 MetaCubeX 的 `category-ai-!cn` 名单生成，让 Perplexity、Cursor、OpenRouter 这类模块没钉住的 AI 服务也走美国；名单里的 Claude、OpenAI、Gemini 已被模块先匹配，不受它影响。需要更新时运行 `python3 tools/build_ai_list.py` 再提交。

DNS 用腾讯与阿里的 DoH，失败时退回系统 DNS；IPv6 关闭，免得请求绕开节点从本机 IPv6 直接出去；`udp-policy-not-supported-behaviour = REJECT` 让节点不支持 UDP 时拒绝而不是直连，QUIC 会随之退回 TCP。

使用时在 App 的「配置」页添加远程配置 `https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/configs/base.conf` 并设为当前配置，再在模块列表里启用 `personal.module`。文件里刻意不写 `[MITM]`：App 生成证书时口令和证书写进设备上的那份配置，只留在本机；本地另存的副本请命名为 `*.local.conf`，已被 `.gitignore` 忽略。

### modules/personal.module

设备上本地加载的「个人」模块，是最高优先级的规则层，要在模块列表里排在其他模块之上。本地模块不会被远程模块的自动更新覆盖。

模块定义了 `US`、`JP`、`MEXC_JP`、`BYBIT_TW`、`SG` 五个地区分组，都是 `url-test`，参数与上面相同；`MEXC_JP`、`BYBIT_TW` 另外排除倍率与信息节点。各组都不写 `policy-path`，`policy-regex-filter` 直接作用于全部节点，订阅拉来的节点也会被吸收，订阅链接不必出现在文件里。筛选依据是节点名，所以正则里同时写了简体、繁体和英文，两字母缩写加了 `\b` 边界；换机场后进分组看一眼实际匹配到的节点，按需补关键字。有两点要注意：分组行和规则行都不能写行尾注释，Shadowrocket 会把它并进正则，组里一个节点都匹配不到，引用它的规则会退回首页所选节点；启用模块前要删掉 App 里手工建的同名分组，主配置里也不能有同名组，否则改了模块不生效、出口来回跳。

规则按服务所需的出口地区分段，格式是 `类型,值,策略`。走 `US` 的有 Siri 与 Apple 隐私中继、Apple TV+、X（含图片视频与 t.co）、Meta AI（含 `graph.facebook.com`）、Claude、Gemini、Grok，以及按账号所在地钉在美国的希尔顿、Kraken、Kalshi、Equifax、美国金融与运营商、TopCashback、返利联盟的跳转域名、Trip.com，以及 OKX 和它活动期间用到的第三方验证 SDK。走 `JP` 的有 OpenAI（ChatGPT）和甲骨文（`DOMAIN-KEYWORD,oracle`）。MEXC 及其推送、监控、风控等一整套域名走 `MEXC_JP`，Bybit 走 `BYBIT_TW`（Bybit 已限制日本用户）。一个钱包接口和「待定地区」那一段银行、加密卡与 DeFi 服务暂走 `SG`。Apple Music 整体直连走国内 CDN，其中播放授权 `play.itunes.apple.com` 与 `bag.itunes.apple.com` 和 Apple TV+ 共用，让给 Apple Music 直连，Apple TV+ 加载不出来时先查这两个域名。中国建设银行与两个国内站点显式直连。

几处写法有意放宽或共用，改动时留意。Claude 用 `DOMAIN-KEYWORD,claude` 统一命中散落在多个根域下的主站、artifact 与分享页，Siri 也用关键字，名字里带这些词的其他网站会一并走美国。Claude 段里的 Cloudflare 人机验证 `challenges.cloudflare.com`、statsig、sentry、datadog、sift 是为了让验证与风控和主站同一出口，但它们被多个 App 共用：ChatGPT 的人机验证与上报也会走美国，ChatGPT 登录时若反复弹验证，先看这一条。OpenAI 段照 geosite 的 openai 分类补齐了 `chat.com`、`oaistatsig.com` 与高级语音用的三个 livekit 子域，否则它们会落到 `AI_US`。

规则开头是 `AND,((PROTOCOL,UDP),(DST-PORT,443)),REJECT-NO-DROP`，拒绝 QUIC。国内运营商对出境 UDP 限速丢包严重，QUIC 经节点时 App 从后台切回来常卡到超时才退回 TCP，直接拒绝后立即改用 TCP。这条必须排在所有域名规则之前。它前面有两条例外，让 Claude（claude 关键字与 anthropic.com）的 QUIC 走 `US`，是对比上传速度的试验，没有效果时删掉即可。

模块还把 `google.cn`、`g.cn`（含 `www.`）302 跳转到 `https://www.google.com`，由 Shadowrocket 在本地直接返回；正则要求主机名后紧跟 `/`、`:`、`?` 或结尾，免得误伤 `g.cn.miaozhen.com` 这类域名。https 地址需要解密才能看到完整 URL，所以模块用 `%APPEND%` 把这几个主机名追加进 `[MITM]`，证书用设备上生成的那份；没有安装并信任证书时只有 http 地址会跳转。

## Clash Mi：configs/oracle.js

甲骨文节点的配置是 Clash Mi 里一份本地 mihomo 文件，有「甲骨文日本」「甲骨文美国」两个 VLESS Reality 节点，凭据只在本机。`oracle.js` 是套在它上面的 JS 覆写：节点原样保留，整体换掉分组、规则集与规则；配置自己没开 DNS 时补一份 fake-ip、国内 DoH 的 DNS 设置，否则不动。配置的 DNS 若用 `rule-set:名称` 引用了自带的规则集，这几个规则集会留下，不然内核会因找不到规则集拒绝加载。

覆写建三个分组，节点按名字现填：名字带「日本」「东京」「東京」的算日本，带「美国」「美國」的算美国。`🚀 节点选择` 是手动选择组，默认用 `🛡️ 故障转移`，也可以手动选定某个节点或直连；`🛡️ 故障转移` 按日本、美国的顺序，日本不通才换美国；`🇺🇸 美国` 反过来，先美国后日本。配置里没有美国节点时去掉美国组，相关规则改走 `🚀 节点选择`。两个节点各有一个流量页面，`stats.jp.node`、`stats.us.node` 两条规则排在最前，钉到对应节点；配置里没有同名节点时不加，节点改名后要同步改脚本里的 `ORACLE_STATS`。

走 `🇺🇸 美国` 的是 AI 与美国账户类服务：模块里的 Meta AI、Claude（含人机验证、statsig 与上报）、Grok、希尔顿、Kraken、Kalshi、Equifax、美国金融与运营商、TopCashback、返利联盟跳转、Trip.com、OKX 与第三方验证 SDK，加上 Nextin 模板的 Anthropic、Gemini、AI 平台合集三条 geosite。其余原先指向代理的规则都走 `🚀 节点选择`，也就是从日本出去，包括 ChatGPT（模板的 `GEOSITE,openai`）、甲骨文、Siri、Apple TV+、X、MEXC、Bybit 和待定地区。Bybit 限制日本用户。

规则顺序是：流量页面两条；私有地址直连；个人规则的四个规则集，依次是拒绝、直连、美国、日本；模板的广告与追踪器拦截；模板的 OpenAI、Anthropic、Gemini、AI 合集；国内 IP 段（`no-resolve`）直连；模板的被墙名单；`GEOSITE,cn` 直连；再引用一次国内 IP 段，这次不带 `no-resolve`，名单外的域名先在本机解析，落在国内 IP 段的也直连；最后 `MATCH,🚀 节点选择`。第二次引用国内 IP 段是为了让苹果、微软更新、Akamai 这类在国内有 CDN 的境外服务直连，不挤占节点。模板私有 IP 段里的 `172.16.0.0/12` 被去掉了：Clash Mi 在 iOS 上有些连接进内核时目标地址落在这个网段，会被它抢先直连再解析到被污染的地址；局域网主机名仍由 `GEOSITE,private` 直连。

走代理的 QUIC（UDP 443）一律拒绝，直连的照常放行：每条指向代理分组的规则前插一条条件相同、只多 UDP 443 的拒绝规则，`MATCH` 前插一条只看 UDP 443 的。节点协议跑在 TCP 上，QUIC 经节点只能装进 TCP 隧道，既丢了自身优势，又与外层 TCP 的重传叠加，MEXC 就曾因此卡顿；直连的 QUIC 不受这个问题影响，所以不拦。

个人规则与国内 IP 段放在 `rules/tokyo/` 的五个规则集里，内核按 raw 链接下载，下载经由 `🚀 节点选择`，因为 raw.githubusercontent.com 在国内直连经常不通；个人规则每小时检查一次更新，国内 IP 段每天一次，等不及可以在「规则」页手动更新。规则集名与目录的 `tokyo` 前缀是早先东京住宅 IP 版留下的，设备上的覆写按这些链接下载，改名会让旧覆写一时找不到规则集，所以没有改。

在 Clash Mi 里的用法：「核心设置 → 覆写」里点加号选「添加配置链接」，类型选 JS，链接填 `https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/configs/oracle.js`，再在甲骨文那份配置的自定义覆写里选中它，重新连接。覆写本身不含秘密，直接按 raw 链接加载即可，合并到默认分支后随之更新。

## 生成与维护

改了 `personal.module` 之后运行 `python3 tools/build_nextin.py`（需要 PyYAML），再提交并合并。脚本按 `tools/nextin.url` 下载 Nextin Hub 生成的 mihomo 模板，把模块的规则插在私有地址之后、广告拦截之前；模块里 Claude 主站两条、OpenAI 与 Gemini 两段不搬，交给模板的 geosite 规则；mihomo 不支持否定前瞻，正则里的排除部分拆成 `exclude-filter`；QUIC 拒绝、URL 重写与 MITM 不搬。然后改写成上面的甲骨文版，写出 `configs/oracle.js` 与 `rules/tokyo/*.list`。合并结果只在内存里，不再单独保存。

常调的开关都在脚本开头：`TOKYO_US_SECTIONS` 与 `TOKYO_US_GEOSITES` 决定哪些分段与模板规则走美国组，分段改名时脚本直接报错，不会悄悄改走日本；`TOKYO_TAIL` 是兜底的几条；`ORACLE_JP`、`ORACLE_US` 是认节点的正则；`ORACLE_STATS` 是流量页面。只改了个人规则时，设备一小时内自动换上新规则集；改了分组或规则骨架，`oracle.js` 本身会变，在 Clash Mi 里更新一下覆写即可。生成后可以用 Node 把 `oracle.js` 的 `main` 套在一份模拟配置上，核对分组与规则引用的分组、规则集都存在。
