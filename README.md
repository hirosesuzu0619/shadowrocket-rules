# shadowrocket-rules

存放个人使用的 Shadowrocket 配置、模块与规则。仓库是公开的，文件里不含订阅链接、节点名等任何私密内容。

## configs/base.conf

基础配置文件，只负责国内直连、国外代理这一层兜底分流。Shadowrocket 会把模块的规则排在配置文件的规则之前，所以 `personal.module` 等模块先匹配，模块没命中的流量才轮到这里。

规则按顺序是：局域网直连；AI 服务（`rules/ai.list`）走 `AI_US`；国内域名直连（blackmatrix7 维护的 `China.list` 与 `China_Domain.list`，前者含关键字和 IP 段，按 `RULE-SET` 引用，后者是纯域名集合，按 `DOMAIN-SET` 引用）；常用境外服务按域名走 `OVERSEAS`；被墙域名（Loyalsoldier 生成的 `gfw.txt`，按 `DOMAIN-SET` 引用）同样按域名走 `OVERSEAS`；以上都没命中时按解析出的 IP 判断，`GEOIP,CN` 直连；其余 `FINAL,OVERSEAS`。

10 月 10 日曾把分流逻辑改成与 Nextin 模板一致：去掉 `GEOIP,CN`，兜底改为 `DIRECT`，同时放开 QUIC。设想是 `GEOIP,CN` 要求名单外的域名先在本机经国内 DoH 解析出 IP，每个新域名多等一轮，而 Nextin 模板没有任何需要本机解析的规则。试下来没有变快，两边选中的节点也差不多，剩下的差别应在客户端内核本身，所以当天就恢复了原来的末尾两条，避免名单外的境外站点直连。

AI 名单是那次试验留下的。Nextin 模板用 v2fly 的 `category-ai-!cn` 分类把 AI 服务统一送去美国节点，这里照做：`tools/build_ai_list.py` 从 MetaCubeX 的同一份名单生成 Shadowrocket 的 DOMAIN-SET `rules/ai.list`，按 raw 链接引用，送到 `AI_US` 组。这个组在美国节点里按延迟择优，排除倍率与信息节点。不写这条时，Perplexity、Cursor、OpenRouter 这类模块没有钉住的 AI 服务会落到 `OVERSEAS`，出口多在日本、韩国。名单里也有 Claude、OpenAI、Gemini，但模块规则先匹配，它们照旧走模块的 `US`。名单需要更新时运行 `python3 tools/build_ai_list.py` 再提交。

文件里的通用出口是策略组 `OVERSEAS`，类型是 `url-test`，在排除香港、新加坡、台湾之后的全部节点里按延迟自动择优，实际多落在日本、韩国，它们都不通时还能退到美国等其他地区；`tolerance = 50` 让延迟相差不到 50 毫秒时不切换，测速间隔 300 秒，坏掉的节点能更快被换下。它和模块里的分组一样不写 `policy-path`，正则直接筛选全部节点，用一个否定前瞻同时排除上述三个地区、名字里带「倍」的倍率节点，以及「剩余流量」「套餐到期」「官网」这类信息节点。

这个组此前叫 `EAST_ASIA`，候选是香港、日本、韩国。实际用下来明显比 Nextin Hub 生成的模板慢，对照之后差别主要在出口：香港节点延迟最低，`url-test` 几乎总选中它，但香港线路高峰期带宽常常跟不上（Telegram 一节里香港5、香港10 的表现也指向这一点），延迟低并不等于下载快；Nextin 模板里选定的是排除香港、新加坡、台湾，现在照此调整，组名也随之改成不再指代具体地区的 `OVERSEAS`。另一处差别是被墙域名：Nextin 模板按 v2fly 的 gfw 分类直接按域名走代理，这里以前要先经国内 DoH 解析、再由 `GEOIP,CN` 判断，解析慢或超时时连接就跟着等，现在补上同源的 `gfw.txt`。该名单不含 apple.com、icloud.com、microsoft.com 这类国内也在用的域名，所以不会出现下文提到的大名单误伤问题。下文模块一节提到的 `url-test` 反复切换问题主要影响交易所这类看出口 IP 的服务，普通浏览不受影响。组名刻意不叫 `PROXY`、`AUTO` 这类常见名字，避免与模块或其他配置来源重名。

Telegram 单独走 `TELEGRAM` 组，同样是 `url-test`，候选节点在香港、日本、韩国之外加上新加坡，测速地址换成 `telegram.org`。9 月 30 日的日志显示，当时的通用组 `EAST_ASIA` 按到 gstatic 的延迟择优，几乎每轮测速都换一个节点，107 分钟里换了 14 次；轮到香港5、香港10 时，Telegram 反复在 443、80、5222 三个端口上重连阿姆斯特丹和新加坡机房，香港10 上持续了一分多钟，还转去 `dns.google.com` 拉备用地址，而同一节点上的 Google 请求一次就通。也就是说，gstatic 的延迟反映不出节点到 Telegram 机房的线路好坏，Telegram 时快时慢取决于那一轮碰巧选中了哪个节点。改用 Telegram 自己的服务器测速后，选出的就是到它机房最快的节点；IP 段也按官方的 `cidr.txt` 补齐了此前缺的几段。若仍偶尔卡住，进 `TELEGRAM` 组看一下各节点的测速结果，把长期超时的节点从正则里排除即可。

常用境外名单直接写在文件里，内容是 Google、YouTube、Telegram、GitHub、Reddit、Netflix 等常见站点的关键字和后缀。以前这些域名要先经国内 DoH 解析，再由 `GEOIP,CN` 判断不在国内，才落到兜底规则；现在按域名直接命中，每个新域名省去一轮 DNS 查询，被污染的解析结果也不再影响分流。没有引用 blackmatrix7 的 `Global` 或 `Proxy` 名单，因为它们包含 `apple.com`、`icloud.com`、`microsoft.com`、`akamai.net` 等域名，会把 iCloud、系统更新和国内也在使用的 CDN 一并改走代理。X 与各家 AI 服务已由模块钉到 `US`，不在这份名单里重复。需要固定出口的服务照旧写进模块。
DNS 使用腾讯与阿里的 DoH，失败时退回系统 DNS。IPv6 关闭，避免请求绕开节点、从本机 IPv6 地址直接出去。
`udp-policy-not-supported-behaviour = REJECT` 让节点不支持 UDP 时拒绝 UDP 连接，QUIC 会随之退回 TCP 走代理，而不是改成直连。

使用方法是在 App 的「配置」页添加远程配置，填入 `https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/configs/base.conf` 并设为当前配置，之后再在模块列表里启用 `personal.module`。
切换过来之前，先看一下其他远程模块有没有引用旧配置里的策略组（例如「谷歌服务」「苹果服务」「美国节点」）：新配置里没有这些组，引用它们的规则需要一并调整或停用对应模块。
文件里刻意不写 `[MITM]`。在 App 里生成证书时，口令和证书会写进设备上的那份配置，只留在本机，不要提交回仓库；在本地另存的副本请命名为 `*.local.conf`，已被 `.gitignore` 忽略。

## modules/personal.module

个人最高优先级规则层，也就是设备上本地加载的「个人」模块，包含地区策略组与规则两部分。
因为是本地模块，任何远程模块的自动更新都不会覆盖它，请在模块列表里把它排在其他模块之上，让它的规则先被命中。

### 策略组

模块定义了 `US`、`MEXC_JP`、`BYBIT_TW`、`SG`、`JP` 五个地区分组。
关键点是各组都不写 `policy-path`：此时 `policy-regex-filter` 直接作用于 Shadowrocket 当前的全部节点，订阅拉取来的节点同样在内，所以分组能自动吃到订阅节点，而订阅链接完全不必出现在文件里。
若正则中含有逗号，需要给它加上引号，否则会被当成参数分隔符；本文件的正则不含逗号，故未加引号。

模块里的五个组全部是 `url-test` 类型：在组内按延迟自动择优，`tolerance = 50` 让延迟相差不到 50 毫秒时不切换，测速间隔 300 秒。`US` 候选是全部美国节点，`MEXC_JP` 与 `JP` 是日本节点，`BYBIT_TW` 是台湾节点，`SG` 是新加坡节点；`MEXC_JP`、`BYBIT_TW` 额外排除倍率节点和「剩余流量」「套餐到期」这类信息节点。

各组都曾用过别的类型。`US`、`SG`、`JP` 一度改成 `fallback`，按节点列表顺序固定用第一个可用节点，出口稳定，但只认顺序、不看快慢，排在最前的节点一慢，走这个组的服务就全都跟着慢。交易所的组曾是 `select` 且正则只匹配单个节点（台湾1），出口完全钉死，代价同样是速度受制于那一个节点。10 月 10 日起全部改为按延迟择优，换来速度，代价是出口会在延迟接近的节点之间偶尔切换。日志里曾出现同一秒内两个台湾节点同时在用的情况，交易所看到的就是一个账号来自多个地址，可能触发风控或要求重新验证；若遇到这种情况，可以把交易所的组改回 `select`，固定在一个节点上。

10 月 10 日之前，MEXC 和 Bybit 共用一个钉在台湾1 的 `MEXC_TW` 组，MEXC 一直明显偏慢：所有请求都挤在这一个节点上，而 MEXC 的 App 资源包放在 AWS 东京（ap-northeast-1），日本节点离它更近。于是 MEXC 拆出来改走 `MEXC_JP`。日本不在 MEXC 公布的禁止服务地区之内，只是日区 App Store 下架了它的 App，已安装的不受影响；第一次换到日本出口时，MEXC 可能要求重新验证一次。Bybit 已限制日本用户，所以留在台湾，组名随之改成 `BYBIT_TW`。

这个组此前叫 `TW`，而且那一行末尾带着一段 `#` 注释。9 月 24 日的日志显示，命中 MEXC、Bybit 规则的连接出口依次是美国4、美国1、台湾2，从未出现台湾1，并且与 `PROXY`、`谷歌服务`、`苹果服务` 等组在同一时刻一起切换，也就是在跟随首页所选的节点；走到美国1 时 MEXC 随即提示不支持所在地区。同一模块里没有行尾注释的 `US`、`SG` 都按各自的正则正常工作，所以最可能的原因是行尾注释被并进了正则，组内一个节点也匹配不到，引用它的规则只好退回首页节点。现在注释移到了单独一行，并把组名改成更独有的 `MEXC_TW`（后来又拆分为 `MEXC_JP` 与 `BYBIT_TW`），避免与其他配置来源里可能存在的 `TW` 重名。今后策略组和规则行都不要写行尾注释。

筛选依据是节点名称，所以正则里同时写了简体、繁体和英文；`US`、`SG` 这类两字母缩写加了 `\b` 单词边界，避免把 `AUS` 之类的名字误判进来。
节点命名风格因机场而异，加载模块后进分组看一眼实际匹配到的节点，按需补关键字。
新增地区照抄同一行格式即可，只需更换组名和正则。

启用本模块前，请先删除此前在 App 界面里手工建立的同名分组，也请检查主配置文件（含 `[General]`/`[MITM]` 那份，而非本仓库的模块）里是否也定义了同名策略组。同一个组名只要在两处各存在一份就会产生冲突，表现为改了模块不生效、节点在多个出口间跳动，或分组列表出现重复项。

### 规则

格式是 `类型,值,策略`。精确匹配用 `DOMAIN`，后缀匹配用 `DOMAIN-SUFFIX`，关键字匹配用 `DOMAIN-KEYWORD`；策略可以填 `US`、`MEXC_JP`、`BYBIT_TW`、`SG`、`JP` 这类策略组名，也可以填 `DIRECT` 直连或 `REJECT` 屏蔽。
当前规则把 Siri 与 Apple 隐私中继相关的域名统一指向 `US`，Apple TV App（Apple TV+）的主站、片单目录、播放鉴权、订阅校验、播放进度与视频流域名也指向 `US`，让同一次播放的所有请求从同一出口出去，只列具体的 `itunes.apple.com` 子域，不影响 App Store 下载。Apple Music 则整体直连，走国内 CDN，其中播放授权 `play.itunes.apple.com` 与服务端点配置 `bag.itunes.apple.com` 两个域名与 Apple TV+ 共用，以前随 Apple TV 规则走 `US`，每首歌开播前都要绕美国节点取授权，导致开播慢、播放卡住，现在让给 Apple Music 直连，Apple TV+ 若再加载不出来，先检查这两个域名。X（含图片视频资源与 t.co 短链）以及 Meta AI、Claude、OpenAI、Gemini、Grok 这几家 AI 服务也指向 `US`；Meta AI 除了 meta.ai、meta.com、metaaivm.com 三个后缀，还单独把账号登录与上报接口 `graph.facebook.com` 钉到 `US`，否则它会被基础配置的 facebook 关键字带去 `OVERSEAS`，Facebook、Instagram 发往这个域名的请求也随之走 `US`；其中 Claude 用 `DOMAIN-KEYWORD,claude,US` 统一命中，因为它的主站、artifact 内容、公开分享页分别挂在 claude.ai、claudeusercontent.com、claude.site 等不同根域下，逐个列后缀容易漏，代价是名字里带 claude 的其他网站也会走 `US`；Claude 相关的 Cloudflare 人机验证、statsig 特性开关以及 sentry、datadog、sift 遥测风控域名同样指向 `US`，让它们与主站同一出口，其中 sentry、datadog 为多个 App 共用；Gemini 只挑出 Google 旗下的相关子域做精确匹配，不影响其他 Google 服务；MEXC 及其推送、监控、归因、资源下载、阿里云日志上报与设备风控等一整套域名指向 `MEXC_JP`，Bybit 的主域、备用 API 域与资源域指向 `BYBIT_TW`。其中 `DOMAIN-KEYWORD,siri,US` 是关键字匹配，凡域名含 siri 都会命中，范围比其他几条宽，若出现误伤可改成更精确的写法。

10 月 10 日把设备上一批历史遗留的手动规则并进了模块。它们原本都指向 `PROXY`，也就是首页当前所选的节点，出口随首页切换。其中与模块重复的 Siri、隐私中继、datadog、Bybit 条目，以及 Telegram 这类不写规则也会走代理的条目直接作废；其余按服务所需地区落位：Bybit 的资源与备用域名（byabcde、bybdc6、byd3c3、byapps）随主域走 `BYBIT_TW`；OKX 钉到 `SG`，因为 10 月 10 日的日志里它走了美国节点，而 OKX 不对美国用户开放；Schwab、Monarch、Kubera、Red Pocket、Origin、T-Mobile 这些美国金融与运营商服务走 `US`；Wise、N26、Gekkard、Kast、Moment、Ekubo、Vesu、Ready（原 Argent）、Dune、Coca 所需地区尚未确定，暂走 `SG`；luluwu.org、weijingle.com 两个国内站点显式 `DIRECT`，因为 Nextin 模板没有国内域名名单，不写就会走代理。10 月 15 日又加了中国建设银行的 `ccb.com` 与 `ccb.com.cn` 两个后缀显式 `DIRECT`：日志里建行 App 的接口、网银、推送与广告资源都在这两个后缀下，当时已靠各版本的国内名单直连，但银行 App 看来源 IP 做风控，写进模块后不再依赖名单是否收录，所有版本都由同一条规则保证直连。并入后设备上的那批手动规则可以全部删除。

10 月 25 日把 TopCashback 与 Trip.com 也钉到 `US`。TopCashback 此前没有规则，落在兜底出口；返现按账号所在地区结算，用 `topcashback` 关键字统一命中各国站点，再加上它的资源域名 `tcb-cdn.com`。Trip.com 的 `trip.com`、`tripcdn.com` 在国内名单里，东京版会直连，而 `m.trip.com` 等域名解析到 Akamai 海外节点，直连全部超时；同一会话里 App 还调用了携程的 `ubtlog.ctrip.com`、`m.ctrip.com`、`m.ctripins.com`，这三个子域一并走 `US`，携程 App 发往这三处的请求也会随之走美国。

10 月 26 日又加了一段「联盟平台跳转（返利）」：从 TopCashback 点去商家时，请求先经联盟平台的跳转域名写入追踪 Cookie 再到商家，部分美国商家与联盟项目只认美国流量，所以 Rakuten（`linksynergy.com`）、CJ 的一组跳转与回传域名、Impact 的通用跳转域名、Awin、ShareASale、Partnerize、Pepperjam、AvantLink 都走 `US`。这些规则排在广告拦截之前，即使在广告名单里也不会被拦，其他返利工具经过这些平台的跳转同样走 `US`。商家自己的域名每次不同，没有列入，商家网站仍按其他规则走；需要整段走美国时，购物期间在客户端切到全局模式并把 GLOBAL 选为美国组，下单后再切回规则模式。

规则的开头是 `AND,((PROTOCOL,UDP),(DST-PORT,443)),REJECT-NO-DROP`，拒绝 UDP 443 也就是 QUIC 流量。国内运营商对出境 UDP 限速和丢包都很重，QUIC 经节点的 UDP 转发时，X 这类 App 从后台切回来重新建连容易卡住，要等超时才退回 TCP；直接拒绝后 App 立即改用 TCP。这条必须排在所有域名规则之前，否则 x.com 等流量会先被后面的规则带走。国内直连的 App 也会随之改用 TCP，影响很小。唯一的例外是 Claude：在 Claude 上传图片仍比 Nextin Hub 生成的模板慢，而 Nextin 不拦 QUIC，上传可能走了 HTTP/3，所以在拒绝规则之前加了两条 `AND` 规则，让名字带 claude 的域名和 anthropic.com 的 UDP 443 走 `US`，作为对比试验。节点不支持 UDP 时，`udp-policy-not-supported-behaviour = REJECT` 会直接拒绝，Claude 照样立即退回 TCP。若试下来没有变快，删掉这两条即可。10 月 10 日随分流逻辑改成与 Nextin 一致时曾把拒绝规则和这两条例外一并删除、放开 QUIC，试下来仍不如 Nextin 快，已原样改回。

### URL 重写

模块把 `google.cn`、`g.cn`（含 `www.` 前缀）用 302 跳转到 `https://www.google.com`，跳转由 Shadowrocket 在本地直接返回，不经过任何节点。正则在主机名之后要求紧跟 `/`、`:`、`?` 或网址结尾，否则 `g.cn.miaozhen.com` 这类以 `g.cn` 开头的其他域名也会被误跳转。对 https 地址，不解密就看不到完整 URL，所以模块同时用 `%APPEND%` 把这四个主机名追加进 `[MITM]` 的解密列表；证书仍用设备上那份配置里生成的，仓库里不出现证书和口令。没有安装并信任证书时，只有 http 地址的跳转会生效。

## configs/nextin.yaml

在 Nextin Hub 生成的 mihomo（Clash Meta）模板之上，并入 `personal.module` 的分组与规则。实际使用中，同一批节点下这份模板比 `base.conf` 加模块明显更快，尤其是在 Claude 上传图片时，所以直接以它为底，把个人规则搬进去。模板原有的分组、规则与顺序一行未改，只在两处插入内容：`US`、`MEXC_JP`、`BYBIT_TW`、`SG` 四个个人分组追加在 `proxy-groups` 末尾；个人规则插在私有地址之后、广告拦截之前，与 Shadowrocket 里模块规则先于配置规则的顺序一致，所以 MEXC 的推送与归因这类域名不会先被模板的广告与追踪名单拦掉。

模块里 Claude 主站的两条规则（`claude` 关键字与 `anthropic.com`）以及 OpenAI、Gemini 两段不搬，交给模板自带的 Anthropic、OpenAI、Gemini 分组处理。最初这些规则也一并并入、排在模板规则之前，Claude 就改走了个人的 `US` 组；两者虽然都是在美国节点里按延迟择优，但实际用下来还是想保持与纯 Nextin 模板完全相同的处理方式。Claude 段里其余的周边域名（Cloudflare 人机验证、statsig 特性开关、sentry、datadog、sift 遥测风控）照常并入，但策略改指模板的 Anthropic 分组：人机验证与风控都看来源 IP，`US` 与模板的 Anthropic 分组各自测速、可能选中不同的美国节点，指向同一个分组才能保证与主站同一出口，同时也不会被模板的追踪名单拦截。分组名由脚本从模板的 `GEOSITE,anthropic` 规则读取，Nextin 改名也不受影响；sentry、datadog 为多个 App 共用，其他 App 的上报也会一并走这个分组。

搬运时有几处按 mihomo 的规矩做了调整。mihomo 用 Go 的正则，不支持否定前瞻，`MEXC_JP`、`BYBIT_TW` 里「排除倍率与信息节点」的写法拆成了 `filter` 与 `exclude-filter` 两项；测速超时从秒换算成毫秒。模块开头拒绝 QUIC 的规则以及 Claude 的放行例外没有搬，Nextin 模板本身不拦 QUIC，这正是它与 `base.conf` 的差别之一。没有任何规则引用的 `JP` 组不搬。URL 重写与 `[MITM]` 在 mihomo 配置里没有对应功能，`google.cn` 跳转在这份配置下不生效。

兜底的 `MATCH` 改成了 `DIRECT`，即未命中任何规则的连接一律直连，做法是把 `tools/nextin.url` 里的 `matchTarget` 由 `proxy` 改为 `direct`，由 Nextin Hub 生成，模板其余内容与原先完全相同。此前 `MATCH` 指向代理，而模板的国内 IP 规则都带 `no-resolve`，只能命中直接连 IP 的请求，按域名发起的国内请求一律落到 `MATCH` 走代理，B 站接口与图片就是这样绕了境外节点；当时的补救是在 `MATCH` 之前追加 `GEOSITE,cn,DIRECT`。改为直连兜底后这条已经多余，脚本只在模板的 `MATCH` 仍指向代理时才追加它。代价是境外站点要靠规则命中才走代理：不在被墙名单、AI 名单或个人规则里的境外站点会直连，名单漏掉的被墙站点会打不开，未被墙的境外站点也可能变慢。遇到这种情况把域名补进 `personal.module` 并重新生成；想退回原来的做法，把 `matchTarget` 改回 `proxy` 再运行脚本即可。10 月 10 日试过改回代理兜底并追加 `GEOSITE,cn,DIRECT`（约十一万条，常见国内站点都能命中），用下来网速明显变慢，当天又改回直连兜底。

文件由 `tools/build_nextin.py` 生成，不要手工编辑。改了 `personal.module` 之后运行 `python3 tools/build_nextin.py`，脚本会按 `tools/nextin.url` 里的地址重新下载模板并重新合并；想换 Nextin 的规则组合，就在 Nextin Hub 重新生成链接，替换 `tools/nextin.url` 后再运行。生成后可用 mihomo 自带的检查确认无误：`mihomo -d <目录> -t -f configs/nextin.yaml`。

使用时在 mihomo 内核的客户端里，按原来使用 Nextin 模板的方式填入 `https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/configs/nextin.yaml`。模板里 `proxies` 为空、各组用 `include-all-proxies` 吸收全部节点，订阅节点由客户端合并进来，文件里不出现任何节点或订阅链接。

## configs/clashmi.js

`configs/nextin.yaml` 的 Clash Mi 版本，内容相同，形式是 Clash Mi 的 JS 覆写脚本。Clash Mi 不像 Nextin 那样把订阅节点注入模板，而是先加载机场订阅，再用覆写去改它；`nextin.yaml` 的 `proxies` 是空的，直接当覆写用可能把订阅节点一并清空。这个脚本只把订阅里的 `proxy-groups` 与 `rules` 整体换成 `nextin.yaml` 的，节点、DNS、TUN 等其余设置保持订阅原样。各组的 `include-all-proxies` 换成了 `include-all`，机场若用 `proxy-providers` 下发节点也能被各组吸收。

文件同样由 `tools/build_nextin.py` 生成，运行一次脚本会同时更新两份文件（需要 PyYAML）。生成后可以把脚本套在一份订阅配置上，再交给 mihomo 检查：10 月 10 日用 mihomo 1.19.15 和一份模拟订阅试过，配置检查通过，各组按地区筛选正确，订阅原有的分组被替换，流量信息节点被排除。

在 Clash Mi 里的用法：进入「核心设置 → 覆写」，点右上角加号，选「添加配置链接」，类型选 JS，链接填 `https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/configs/clashmi.js`；然后在「我的配置」里编辑机场订阅，在自定义覆写配置中选中它，更新订阅并重新连接。不同版本的菜单名称可能略有差异。「分流模板」里的规则提供者、规则模板、代理组模板是 Clash Mi 自带的另一套分流方式，用这个脚本就不需要再填。

## configs/tokyo.yaml 与 configs/tokyo.js

只用东京静态住宅 IP 时的版本。这个住宅 IP 只提供主入口、备入口两个节点，入口线路不同、出口是同一个东京 IP，所以 `nextin.yaml` 里按地区筛选节点的分组在这里都没有意义：美国、台湾、新加坡的组一个节点也匹配不到，mihomo 遇到空组会塞进一个相当于直连的占位节点，Claude、OpenAI 这类服务就会直接连接、打不开。东京版把全部代理分组合并成两个：`🚀 节点选择` 是手动选择组，默认用 `🛡️ 故障转移`，也可以手动钉在某个入口或改为直连；`🛡️ 故障转移` 按订阅里的节点顺序先用主入口，主入口不通才换备入口。两个入口出口相同，切换不会改变对外 IP，交易所和 Claude 看到的始终是同一个地址。如果订阅里备入口排在前面，故障转移会先选它，此时进 `🚀 节点选择` 手动选定主入口即可。`🚀 节点选择` 带有正则 `(日本|东京)` 的筛选，手动可选的只有名字里含「日本」或「东京」的节点，`🛡️ 故障转移` 与 `DIRECT` 两项不受筛选影响；`🛡️ 故障转移` 自身不筛选，仍收全部节点。筛选只认这两个简体字样，名字只写 Tokyo、JP 或繁体「東京」的节点不会出现在手动选项里。10 月 14 日用 mihomo 1.19.15 和一份模拟订阅检查过，配置检查通过，组里只剩故障转移、直连和名字带日本、东京的节点。10 月 25 日看过的订阅里共有四个节点：东京住宅的 ① ② 两个入口（出口同为一个住宅 IP），以及两个东京机房节点（出口各不相同）。故障转移按顺序先用两个住宅入口，都不通时才轮到机房节点，那时对外 IP 会变。

10 月 25 日起东京版可以再加一份美国（洛杉矶）订阅，多出第三个组 `🇺🇸 美国`。美国订阅不单独导入，而是由脚本作为 `proxy-providers` 里的 `us` 加进东京订阅的配置，内核按链接每天更新一次节点，下载同样经由 `🚀 节点选择`。`🇺🇸 美国` 是故障转移组，只用 `us` 里的节点，按订阅顺序先用第一个，不通才换下一个，也可以在组里手动点选固定一个；东京的两个组改为只收东京订阅自己的节点，美国节点不会混进去，两边都不靠节点名区分。订阅链接相当于密码，而这个仓库是公开的，所以链接不写进仓库：把 `tokyo.js` 粘贴进 Clash Verge 后，在顶部 `US_SUBSCRIPTION` 的引号里填上美国订阅链接再保存。留空时脚本不建美国组，原本走美国的规则一并走 `🚀 节点选择`，效果和只有东京订阅时一样。以后重新粘贴新版脚本，记得把链接再填一次。

规则的条目与 `nextin.yaml` 相同，只改指向。走 `🇺🇸 美国` 的是 AI 服务与美国账户类服务：模板的 OpenAI、Anthropic、Gemini、AI 平台合集四条，个人规则的 Meta AI（含 `graph.facebook.com`）、Claude（含人机验证、statsig 与遥测风控）、Grok，以及按账号所在地钉在美国的希尔顿、Kraken、Kalshi、Equifax、美国金融与运营商、TopCashback、Trip.com。其余原先指向 `US`、`MEXC_JP`、`BYBIT_TW`、`SG` 和模板 GFW 列表的规则走 `🚀 节点选择`，也就是从东京出去，包括 Siri 与隐私中继、Apple TV+、X、MEXC、Bybit、OKX 以及「待定地区」那一段。哪些分段走美国由 `tools/build_nextin.py` 里的 `TOKYO_US_SECTIONS` 与 `TOKYO_US_GEOSITES` 决定，分段改名时生成脚本会直接报错，不会悄悄落到东京。只有东京订阅时，这些美国账户类服务也统一走东京：曾考虑改为直连或整段不搬，但直连在国内网络下拿到的是国内 IP，不搬则交给兜底，出口时有时无。

东京版的兜底与 `nextin.yaml` 不同，走 `🚀 节点选择`，名单之外的境外站点也从东京出去。之前先有两层直连：`GEOSITE,cn` 让常见国内域名直接命中；再引用一次国内 IP 规则集 `tokyo-cn-ip`，这次不带 `no-resolve`，其余域名先在本机解析，落在国内 IP 段的也直连。第二层是为了住宅线路的带宽：10 月 10 日试过只加 `GEOSITE,cn` 的代理兜底，`apple.com`、`icloud.com`、微软更新、Akamai 这类国内有 CDN 节点的境外服务不在国内名单里，全部挤上住宅线路，X 视频随之变慢。这些服务用国内 DNS 解析时通常拿到国内节点的地址，经第二层就回到直连。最终直连的域名本来就要在本机解析，结果会被缓存复用；只有走代理的境外域名多一次本地查询。这一层依赖订阅里的 DNS 设置：脚本不改 DNS，若订阅的 `nameserver` 是境外 DNS 或经代理查询，苹果、微软会解析到境外地址，照样走东京。想退回直连兜底，把 `tools/build_nextin.py` 里的 `TOKYO_TAIL` 换成 `MATCH,DIRECT` 再生成即可。

改从日本出去的服务有几处会受影响。Bybit 已限制日本用户，从东京出口很可能被拒绝或触发风控，目前没有可替代的出口。OKX 原本钉在新加坡，是否对日本 IP 开放需要自行确认。Apple TV+、Siri 与隐私中继、X 原本走美国，现在从日本出去。原先「待定地区（暂走新加坡）」那一段同样改走东京。没填美国订阅时，Meta AI、Claude、OpenAI、Gemini、Grok 和美国账户类服务也从日本出去，主流 AI 服务在日本都正常可用，个别服务的可用地区可能不含日本。

10 月 28 日起甲骨文相关的域名一律走日本，东京版里也就是 `🚀 节点选择`。geosite 的国内名单收录了 `+.oracle.com`，东京版此前会在 `GEOSITE,cn` 命中直连，所以先给 `oracle.com` 加了一条走 `JP` 的规则；随后改成 `DOMAIN-KEYWORD,oracle,JP`，把甲骨文云控制台与接口所在的 `oraclecloud.com`、自治数据库与 APEX 应用所在的 `oraclecloudapps.com`，以及官网引用的 `oracleinfinity.io`、`oracleimg.com` 一并命中。这条在规则集 `proxy.list` 里，排在国内名单与国内 IP 段之前，不会再被直连带走；脚本本身没有变，Clash Verge 不用重新粘贴，Clash Mi 的 Gist 也不用重新运行，规则集一小时内自动更新。代价是名字里带 oracle 的其他网站也会走日本，目前没有发现常用的此类域名。

10 月 26 日起东京版拒绝 MEXC 的 QUIC。加美国组之后 MEXC 明显变慢，但对照前后两版配置，MEXC 的域名始终命中 `tokyo-proxy`，经 `🚀 节点选择` 从东京-主出去，美国组不在它的路径上。当天的日志里，MEXC 对 www、futures、otc、p2p、prediction、static 等几乎每个接口域名都先发 UDP 443，一两秒后再对同一域名发 TCP，反复多次后放弃 greentreeone，轮换 coldbookfly、hotbookzone、flytogarden 等镜像域名，还会对同一域名同时重开五条 TCP，与上文 `base.conf` 拦 QUIC 之前的卡顿是同一种情况，而东京版沿用 Nextin 模板，从未拦过 QUIC。所以在个人规则之前加了一条 `AND,((NETWORK,UDP),(DST-PORT,443),(RULE-SET,tokyo-no-quic)),REJECT`，规则集 `rules/tokyo/no-quic.list` 由生成脚本按 `TOKYO_NO_QUIC_SECTIONS` 从模块的 MEXC 分段复制而来，条目照旧也在 `proxy.list` 里走东京，只是 QUIC 被拒绝后 App 立即改用 TCP。其他服务的 QUIC 不受影响。这是一次试验：若 MEXC 没有变快，把 `TOKYO_NO_QUIC_SECTIONS` 清空再生成即可；若有效，也可以考虑像 `base.conf` 那样全局拦截。这条规则写在脚本骨架里，Clash Verge 需要重新粘贴一次 `tokyo.js`，Clash Mi 的 Gist 会随默认分支自动更新。

10 月 28 日起东京版与甲骨文版都改为拒绝所有走代理的 QUIC，直连的 QUIC 照常放行，`no-quic.list` 随之删除。两个订阅的节点协议（anytls、VLESS Reality）都跑在 TCP 上，QUIC 经节点只能装进 TCP 隧道，抗丢包、免队头阻塞的长处全部丢掉，还要与外层 TCP 的重传和拥塞控制叠加，MEXC 那次卡顿就是这样来的；甲骨文版此前全局拒绝 QUIC，用起来比东京版顺，这也是可能的原因之一。而直连的 QUIC 不经隧道，在手机弱网和网络切换时确有好处，全局拒绝会把抖音、B 站这类国内 App 一起拦掉。做法是生成脚本在每条指向代理分组的规则前插一条条件相同、只多 UDP 443 的 `AND` 拒绝规则，`MATCH` 前插一条只看 UDP 443 的；直连与拒绝规则前不插，所以先被直连规则命中的 QUIC 照常直连。脚本骨架变了，Clash Verge 需要重新粘贴一次 `tokyo.js`，Clash Mi 的 Gist 与按链接加载的 `oracle.js` 随默认分支自动更新。

Clash Verge 的扩展脚本保存在本地，不能像订阅那样填链接自动更新，所以东京版把常改的部分移出了脚本：个人规则按策略拆成 `rules/tokyo/` 下的 `reject.list`、`direct.list`、`us.list`、`proxy.list` 四个规则集，依次匹配拒绝、直连、美国、东京，模板里九千多条国内 IP 段也放进 `cn-ip.list`。脚本里只剩代理组、规则集的链接和三十来条骨架规则，内核按 raw 链接下载规则集，个人规则每小时检查一次更新，国内 IP 段每天一次，下载经由 `🚀 节点选择`，因为 raw.githubusercontent.com 在国内直连经常不通。改了 `personal.module` 之后照常运行 `python3 tools/build_nextin.py` 并合并，设备上一小时内会自动换上新规则，等不及可以在「规则」页的规则集合里手动更新；只有代理组或模板结构变了，脚本才需要重新粘贴。个人规则拆成规则集后，同一域名若同时命中代理与直连或拒绝条目，会先按直连或拒绝处理；模块里直连与拒绝的条目本来就写在相应代理条目之前，比如希尔顿埋点的拒绝写在希尔顿主域之前，目前没有因此改变结果的条目。美国排在东京之前，两边的关键字规则若同时命中某个域名，宁可让账号类请求走美国；生成时核对过，目前两个列表之间没有互相覆盖的条目。

这些文件由 `tools/build_nextin.py` 与 `nextin.yaml`、`clashmi.js` 一起生成，不要手工编辑。10 月 10 日用 mihomo 1.19.15 和一份按住宅 IP 订阅结构模拟的配置试过：配置检查通过，两个组都只含主、备两个入口，故障转移选中主入口；四个规则集从本地模拟的链接下载成功，条数与生成时一致，希尔顿埋点命中拒绝、Apple Music 授权命中直连、x.com 命中代理。改为代理兜底后同样检查通过：baidu.com 命中 `GEOSITE,cn` 直连，解析到国内 IP 的测试域名命中 `tokyo-cn-ip` 直连，example.org 落到兜底走代理，x.com 与 video.twimg.com 仍命中个人规则走代理。

在 Clash Verge 里的用法：住宅 IP 的订阅照常导入，然后在「订阅」页对它右键选「扩展脚本」，编辑框里原有的示例代码全部删掉，换成 `configs/tokyo.js` 的全部内容，保存后对这份订阅点「使用」重新激活。也可以粘贴到下方的「全局扩展脚本」，那样会作用于所有订阅。脚本只替换订阅里的代理组、规则集与规则，节点、DNS 等设置保持订阅原样，Clash Mi 的 JS 覆写也能直接用它。订阅的 DNS 设置若用 `rule-set:名称` 引用订阅自带的规则集，脚本会把这几个规则集留下：东京订阅的 `nameserver-policy` 与 `fake-ip-filter` 都引用了 `cn-domain`，10 月 25 日之前的脚本把规则集整个换掉，内核会因找不到 `cn-domain` 拒绝加载配置。还要注意这份订阅的 DNS 是 fake-ip 模式，默认经 `🚀 节点选择` 查询 Google 与 Cloudflare 的 DoH，只有 `cn-domain` 里的域名用阿里与腾讯的 DNS，所以兜底前「本机解析落在国内 IP 段的也直连」那一层，对名单外的苹果、微软这类服务基本起不到作用，它们会解析到境外地址并走东京。第一次启用时内核要先下载规则集，稍等几秒再看「规则」页是否已列出四个规则集。不同版本的菜单名称可能略有差异。

在 Clash Mi 里，覆写按链接加载才会自动更新，但仓库里的 `tokyo.js` 没有美国订阅链接，链接又不能进公开仓库。所以由 `.github/workflows/tokyo-gist.yml` 代劳：默认分支上的 `configs/tokyo.js` 一有变化（或在 Actions 页手动运行），就把仓库 Secret `US_SUBSCRIPTION` 里的链接填进去，写到私密 Gist 的 `tokyo-us.js`，Clash Mi 用「添加配置链接」引用这个 Gist 的 raw 地址 `https://gist.githubusercontent.com/<用户名>/<Gist 编号>/raw/tokyo-us.js`（不带版本号，始终指向最新内容）。需要三个 Secret：`US_SUBSCRIPTION`、`GIST_ID`（Gist 网址最后那串编号）、`GIST_TOKEN`（只勾 gist 权限的令牌）。私密 Gist 只是不公开列出，拿到地址的人都能读，所以 raw 地址与订阅链接一样要保密；仓库的 Actions 日志是公开的，工作流不打印任何 Secret。美国订阅链接变了只需改 `US_SUBSCRIPTION` 再手动运行一次；令牌失效时运行会失败并提示 HTTP 401。

## configs/oracle.js

甲骨文节点配置用的覆写。这份配置是一个本地的 mihomo 文件，起初只有甲骨文美国一个 VLESS Reality 节点，10 月 28 日加了甲骨文日本。它的节点凭据不能进公开仓库，所以节点仍留在本机那份配置里，仓库只放覆写：规则与东京版完全相同，规则集也引用同一组 `rules/tokyo/` 链接，改 `personal.module` 并合并后两边同时更新。由 `tools/build_nextin.py` 从 `configs/tokyo.yaml` 派生，和其他文件一起生成，不要手工编辑。

和 `tokyo.js` 的区别有三处。第一，分组里的节点不靠订阅或筛选，而是由脚本按配置里的节点名现填（见下一段）。第二，订阅没有开启 DNS 时补一份 fake-ip、国内 DoH 的 DNS 设置：东京订阅自带 DNS，甲骨文这份没有，10 月 28 日把只换分组与规则的 `tokyo-us.js` 套在它上面，Clash Mi 连不上网，而用内置覆写可以上网，推断是缺 DNS 所致。订阅自己开了 DNS 时脚本不动它。第三，去掉了一条私有 IP 段规则，见再下一段。

最初的版本只有美国一个节点，没有美国组，原先走 `🇺🇸 美国` 的规则一律走 `🚀 节点选择`。10 月 29 日起改为与东京版相同的分流：规则一字不差地沿用东京版（只少上述私有 IP 段那一条），`tokyo-us` 规则集里的 AI 与美国账户类服务，以及 OpenAI、Anthropic、Gemini 与 AI 合集这几条 GEOSITE 走 `🇺🇸 美国`，先用名字带「美国」的节点，美国不通才换日本；其余走 `🚀 节点选择`，默认用 `🛡️ 故障转移`，按日本、美国的顺序，日本不通才换美国，也可以手动选定某个节点。MEXC、Bybit、OKX 这些规则因此从日本出去，不再从美国出去。两个组互为备份：起初 `🇺🇸 美国` 只收美国节点，美国不通时宁可失败也不从日本出去，10 月 29 日按用户要求改为美国不通换日本，这些服务的风控没那么严，真正严格的另走手机漫游流量，不经代理。配置里没有美国节点时去掉美国组，美国规则改走 `🚀 节点选择`，与东京版不填美国订阅时一样；没有日本节点时 `🚀 节点选择` 只有美国。节点按名字识别：带「日本」「东京」的算日本，带「美国」的算美国，正则在 `tools/build_nextin.py` 的 `ORACLE_JP`、`ORACLE_US`。

同一天换上 `oracle.js` 后仍然连不上。Clash Mi 的日志里，x.com、twitter、claude.ai、iCloud 等域名的连接进入内核时目标地址落在 `172.16.0.0/12`，全部命中模板私有 IP 段里的 `IP-CIDR,172.16.0.0/12,DIRECT,no-resolve` 而直连，直连时再解析到被污染的地址，超时或被拒绝；按域名分流的规则都排在私有 IP 段之后，轮不到它们。不带这类地址的连接一切正常，例如 `icloud-content.com` 落到兜底走甲骨文，`cdn-apple.com` 命中国内 IP 段直连。所以甲骨文版去掉了这一条，局域网主机名仍由 `GEOSITE,private` 直连，真正落在这个网段的局域网设备会改走代理，家用路由器很少用这个网段。这些地址为什么落在这个网段还没有查清，推测是 Clash Mi 在 iOS 上自己分配的假地址。

在 Clash Mi 里的用法与 `clashmi.js` 相同：「核心设置 → 覆写」里添加配置链接，类型选 JS，链接填 `https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/configs/oracle.js`，再在甲骨文那份配置的自定义覆写里选中它。脚本不含秘密，直接按 raw 链接加载即可，不需要 Gist。10 月 29 日用 mihomo 1.19.32（与手机上的内核同版本）实际加载检查：把新旧两版脚本分别套在两个节点都有、只有美国、只有日本三种配置上（节点凭据换成占位值），`mihomo -t` 全部通过。改为美国组可换日本后再查一次，三种情况的分组依次为：「🚀 节点选择」故障转移/日本/美国/直连、「🇺🇸 美国」美国/日本、「🛡️ 故障转移」日本/美国；故障转移/美国/直连、美国、美国；故障转移/日本/直连、无美国组、日本。

10 月 29 日起，甲骨文版在所有规则之前加两条：`DOMAIN,stats.jp.node,甲骨文日本` 与 `DOMAIN,stats.us.node,甲骨文美国`。两个节点上各有一个流量页面，节点的 Xray 把这两个假域名转给本机的页面服务，所以必须经对应的节点访问；此前它们落到兜底的 `🚀 节点选择`，选中日本时美国的页面就打不开。覆写会整体替换配置里的规则，在配置文件里自己加的这两条不起作用，只能写在覆写里。脚本按配置里的节点名决定加不加：没有名为「甲骨文日本」或「甲骨文美国」的节点时对应那条不加，免得内核因找不到节点拒绝加载。节点改名后要同步改 `tools/build_nextin.py` 里的 `ORACLE_STATS`。两个节点都有、只有美国、两个都没有时，加出的规则分别为两条、一条、零条。
