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

10 月 10 日把设备上一批历史遗留的手动规则并进了模块。它们原本都指向 `PROXY`，也就是首页当前所选的节点，出口随首页切换。其中与模块重复的 Siri、隐私中继、datadog、Bybit 条目，以及 Telegram 这类不写规则也会走代理的条目直接作废；其余按服务所需地区落位：Bybit 的资源与备用域名（byabcde、bybdc6、byd3c3、byapps）随主域走 `BYBIT_TW`；OKX 钉到 `SG`，因为 10 月 10 日的日志里它走了美国节点，而 OKX 不对美国用户开放；Schwab、Monarch、Kubera、Red Pocket、Origin、T-Mobile 这些美国金融与运营商服务走 `US`；Wise、N26、Gekkard、Kast、Moment、Ekubo、Vesu、Ready（原 Argent）、Dune、Coca 所需地区尚未确定，暂走 `SG`；luluwu.org、weijingle.com 两个国内站点显式 `DIRECT`，因为 Nextin 模板没有国内域名名单，不写就会走代理。并入后设备上的那批手动规则可以全部删除。

规则的开头是 `AND,((PROTOCOL,UDP),(DST-PORT,443)),REJECT-NO-DROP`，拒绝 UDP 443 也就是 QUIC 流量。国内运营商对出境 UDP 限速和丢包都很重，QUIC 经节点的 UDP 转发时，X 这类 App 从后台切回来重新建连容易卡住，要等超时才退回 TCP；直接拒绝后 App 立即改用 TCP。这条必须排在所有域名规则之前，否则 x.com 等流量会先被后面的规则带走。国内直连的 App 也会随之改用 TCP，影响很小。唯一的例外是 Claude：在 Claude 上传图片仍比 Nextin Hub 生成的模板慢，而 Nextin 不拦 QUIC，上传可能走了 HTTP/3，所以在拒绝规则之前加了两条 `AND` 规则，让名字带 claude 的域名和 anthropic.com 的 UDP 443 走 `US`，作为对比试验。节点不支持 UDP 时，`udp-policy-not-supported-behaviour = REJECT` 会直接拒绝，Claude 照样立即退回 TCP。若试下来没有变快，删掉这两条即可。10 月 10 日随分流逻辑改成与 Nextin 一致时曾把拒绝规则和这两条例外一并删除、放开 QUIC，试下来仍不如 Nextin 快，已原样改回。

### URL 重写

模块把 `google.cn`、`g.cn`（含 `www.` 前缀）用 302 跳转到 `https://www.google.com`，跳转由 Shadowrocket 在本地直接返回，不经过任何节点。正则在主机名之后要求紧跟 `/`、`:`、`?` 或网址结尾，否则 `g.cn.miaozhen.com` 这类以 `g.cn` 开头的其他域名也会被误跳转。对 https 地址，不解密就看不到完整 URL，所以模块同时用 `%APPEND%` 把这四个主机名追加进 `[MITM]` 的解密列表；证书仍用设备上那份配置里生成的，仓库里不出现证书和口令。没有安装并信任证书时，只有 http 地址的跳转会生效。

## configs/nextin.yaml

在 Nextin Hub 生成的 mihomo（Clash Meta）模板之上，并入 `personal.module` 的分组与规则。实际使用中，同一批节点下这份模板比 `base.conf` 加模块明显更快，尤其是在 Claude 上传图片时，所以直接以它为底，把个人规则搬进去。模板原有的分组、规则与顺序一行未改，只在两处插入内容：`US`、`MEXC_JP`、`BYBIT_TW`、`SG` 四个个人分组追加在 `proxy-groups` 末尾；个人规则插在私有地址之后、广告拦截之前，与 Shadowrocket 里模块规则先于配置规则的顺序一致，所以 MEXC 的推送与归因这类域名不会先被模板的广告与追踪名单拦掉。

模块里 Claude 主站的两条规则（`claude` 关键字与 `anthropic.com`）以及 OpenAI、Gemini 两段不搬，交给模板自带的 Anthropic、OpenAI、Gemini 分组处理。最初这些规则也一并并入、排在模板规则之前，Claude 就改走了个人的 `US` 组；两者虽然都是在美国节点里按延迟择优，但实际用下来还是想保持与纯 Nextin 模板完全相同的处理方式。Claude 段里其余的周边域名（Cloudflare 人机验证、statsig 特性开关、sentry、datadog、sift 遥测风控）照常并入，但策略改指模板的 Anthropic 分组：人机验证与风控都看来源 IP，`US` 与模板的 Anthropic 分组各自测速、可能选中不同的美国节点，指向同一个分组才能保证与主站同一出口，同时也不会被模板的追踪名单拦截。分组名由脚本从模板的 `GEOSITE,anthropic` 规则读取，Nextin 改名也不受影响；sentry、datadog 为多个 App 共用，其他 App 的上报也会一并走这个分组。

搬运时有几处按 mihomo 的规矩做了调整。mihomo 用 Go 的正则，不支持否定前瞻，`MEXC_JP`、`BYBIT_TW` 里「排除倍率与信息节点」的写法拆成了 `filter` 与 `exclude-filter` 两项；测速超时从秒换算成毫秒。模块开头拒绝 QUIC 的规则以及 Claude 的放行例外没有搬，Nextin 模板本身不拦 QUIC，这正是它与 `base.conf` 的差别之一。没有任何规则引用的 `JP` 组不搬。URL 重写与 `[MITM]` 在 mihomo 配置里没有对应功能，`google.cn` 跳转在这份配置下不生效。

兜底的 `MATCH` 指向代理（`🚀 节点选择`），`tools/nextin.url` 里的 `matchTarget` 为 `proxy`，并在 `MATCH` 之前追加一条 `GEOSITE,cn,DIRECT`，排在被墙名单之后。模板的国内 IP 规则都带 `no-resolve`，只能命中直接连 IP 的请求，按域名发起的国内请求靠的是这条 `GEOSITE,cn`：它来自 MetaCubeX/meta-rules-dat，约十一万条，百度、淘宝、京东、腾讯、B 站、抖音、小红书、美团等常见国内站点及其 CDN 都在内，`.cn` 整个后缀也包括在内。10 月 10 日曾把 `matchTarget` 改成 `direct`、让未命中的连接一律直连，代价是不在被墙名单、AI 名单或个人规则里的境外站点会直连，名单漏掉的被墙站点打不开，所以当天又改回代理兜底。现在的代价反过来：不在 `GEOSITE,cn` 里的小众国内域名会走代理，通常照样能用，只是绕了一圈；遇到需要直连的，把域名以 `DIRECT` 补进 `personal.module` 并重新生成。脚本会按模板的 `MATCH` 自动处理：指向代理时追加 `GEOSITE,cn,DIRECT`，是 `DIRECT` 时不加。东京版与本配置共用模板，兜底同样走代理。

文件由 `tools/build_nextin.py` 生成，不要手工编辑。改了 `personal.module` 之后运行 `python3 tools/build_nextin.py`，脚本会按 `tools/nextin.url` 里的地址重新下载模板并重新合并；想换 Nextin 的规则组合，就在 Nextin Hub 重新生成链接，替换 `tools/nextin.url` 后再运行。生成后可用 mihomo 自带的检查确认无误：`mihomo -d <目录> -t -f configs/nextin.yaml`。

使用时在 mihomo 内核的客户端里，按原来使用 Nextin 模板的方式填入 `https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/configs/nextin.yaml`。模板里 `proxies` 为空、各组用 `include-all-proxies` 吸收全部节点，订阅节点由客户端合并进来，文件里不出现任何节点或订阅链接。

## configs/clashmi.js

`configs/nextin.yaml` 的 Clash Mi 版本，内容相同，形式是 Clash Mi 的 JS 覆写脚本。Clash Mi 不像 Nextin 那样把订阅节点注入模板，而是先加载机场订阅，再用覆写去改它；`nextin.yaml` 的 `proxies` 是空的，直接当覆写用可能把订阅节点一并清空。这个脚本只把订阅里的 `proxy-groups` 与 `rules` 整体换成 `nextin.yaml` 的，节点、DNS、TUN 等其余设置保持订阅原样。各组的 `include-all-proxies` 换成了 `include-all`，机场若用 `proxy-providers` 下发节点也能被各组吸收。

文件同样由 `tools/build_nextin.py` 生成，运行一次脚本会同时更新两份文件（需要 PyYAML）。生成后可以把脚本套在一份订阅配置上，再交给 mihomo 检查：10 月 10 日用 mihomo 1.19.15 和一份模拟订阅试过，配置检查通过，各组按地区筛选正确，订阅原有的分组被替换，流量信息节点被排除。

在 Clash Mi 里的用法：进入「核心设置 → 覆写」，点右上角加号，选「添加配置链接」，类型选 JS，链接填 `https://raw.githubusercontent.com/hirosesuzu0619/shadowrocket-rules/HEAD/configs/clashmi.js`；然后在「我的配置」里编辑机场订阅，在自定义覆写配置中选中它，更新订阅并重新连接。不同版本的菜单名称可能略有差异。「分流模板」里的规则提供者、规则模板、代理组模板是 Clash Mi 自带的另一套分流方式，用这个脚本就不需要再填。

## configs/tokyo.yaml 与 configs/tokyo.js

只用东京静态住宅 IP 时的版本。这个住宅 IP 只提供主入口、备入口两个节点，入口线路不同、出口是同一个东京 IP，所以 `nextin.yaml` 里按地区筛选节点的分组在这里都没有意义：美国、台湾、新加坡的组一个节点也匹配不到，mihomo 遇到空组会塞进一个相当于直连的占位节点，Claude、OpenAI 这类服务就会直接连接、打不开。东京版把全部代理分组合并成两个：`🚀 节点选择` 是手动选择组，默认用 `🛡️ 故障转移`，也可以手动钉在某个入口或改为直连；`🛡️ 故障转移` 按订阅里的节点顺序先用主入口，主入口不通才换备入口。两个入口出口相同，切换不会改变对外 IP，交易所和 Claude 看到的始终是同一个地址。如果订阅里备入口排在前面，故障转移会先选它，此时进 `🚀 节点选择` 手动选定主入口即可。

规则的条目与 `nextin.yaml` 相同，只改指向：原先指向 `US`、`MEXC_JP`、`BYBIT_TW`、`SG` 以及模板 OpenAI、Anthropic、Gemini、AI 平台合集、GFW 列表这些分组的规则，一律走 `🚀 节点选择`，希尔顿、Kraken、Kalshi、Equifax 和美国金融与运营商这些原本按账号所在地钉在 `US` 的也不例外，统一从东京出去。曾考虑把这几段改为直连或整段不搬：直连在国内网络下拿到的是国内 IP；不搬则会交给模板的兜底规则，而当时模板兜底是直连，只有 Schwab、Kraken 这类恰好在被墙名单里的才会走代理，出口时有时无，所以统一走代理。

只剩日本出口后有几处服务会受影响。Bybit 已限制日本用户，从东京出口很可能被拒绝或触发风控，目前没有可替代的出口。OKX 原本钉在新加坡，是否对日本 IP 开放需要自行确认。Apple TV+、Siri 与隐私中继、X、Meta AI 以及 Claude、OpenAI、Gemini、Grok 这些原本走美国的服务改从日本出去，主流 AI 服务在日本都正常可用，个别服务的可用地区可能不含日本。原先「待定地区（暂走新加坡）」那一段同样改走东京。

Clash Verge 的扩展脚本保存在本地，不能像订阅那样填链接自动更新，所以东京版把常改的部分移出了脚本：个人规则按策略拆成 `rules/tokyo/` 下的 `reject.list`、`direct.list`、`proxy.list` 三个规则集，依次匹配拒绝、直连、代理，模板里九千多条国内 IP 段也放进 `cn-ip.list`。脚本里只剩代理组、规则集的链接和三十来条骨架规则，内核按 raw 链接下载规则集，个人规则每小时检查一次更新，国内 IP 段每天一次，下载经由 `🚀 节点选择`，因为 raw.githubusercontent.com 在国内直连经常不通。改了 `personal.module` 之后照常运行 `python3 tools/build_nextin.py` 并合并，设备上一小时内会自动换上新规则，等不及可以在「规则」页的规则集合里手动更新；只有代理组或模板结构变了，脚本才需要重新粘贴。个人规则拆成三个规则集后，同一域名若同时命中代理与直连或拒绝条目，会先按直连或拒绝处理；模块里直连与拒绝的条目本来就写在相应代理条目之前，比如希尔顿埋点的拒绝写在希尔顿主域之前，目前没有因此改变结果的条目。

这些文件由 `tools/build_nextin.py` 与 `nextin.yaml`、`clashmi.js` 一起生成，不要手工编辑。10 月 10 日用 mihomo 1.19.15 和一份按住宅 IP 订阅结构模拟的配置试过：配置检查通过，两个组都只含主、备两个入口，故障转移选中主入口；四个规则集从本地模拟的链接下载成功，条数与生成时一致，希尔顿埋点命中拒绝、Apple Music 授权命中直连、x.com 命中代理。

在 Clash Verge 里的用法：住宅 IP 的订阅照常导入，然后在「订阅」页对它右键选「扩展脚本」，编辑框里原有的示例代码全部删掉，换成 `configs/tokyo.js` 的全部内容，保存后对这份订阅点「使用」重新激活。也可以粘贴到下方的「全局扩展脚本」，那样会作用于所有订阅。脚本只替换订阅里的代理组、规则集与规则，节点、DNS 等设置保持订阅原样，Clash Mi 的 JS 覆写也能直接用它。第一次启用时内核要先下载规则集，稍等几秒再看「规则」页是否已列出四个规则集。不同版本的菜单名称可能略有差异。
