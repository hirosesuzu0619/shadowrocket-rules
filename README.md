# shadowrocket-rules

存放个人使用的 Shadowrocket 配置、模块与规则。仓库是公开的，文件里不含订阅链接、节点名等任何私密内容。

## configs/base.conf

基础配置文件，只负责国内直连、国外代理这一层兜底分流。Shadowrocket 会把模块的规则排在配置文件的规则之前，所以 `personal.module` 等模块先匹配，模块没命中的流量才轮到这里。

规则按顺序是：局域网直连；国内域名直连（blackmatrix7 维护的 `China.list` 与 `China_Domain.list`，前者含关键字和 IP 段，按 `RULE-SET` 引用，后者是纯域名集合，按 `DOMAIN-SET` 引用）；常用境外服务按域名走 `OVERSEAS`；被墙域名（Loyalsoldier 生成的 `gfw.txt`，按 `DOMAIN-SET` 引用）同样按域名走 `OVERSEAS`；以上都没命中时按解析出的 IP 判断，`GEOIP,CN` 直连；其余 `FINAL,OVERSEAS`。

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

规则的开头是 `AND,((PROTOCOL,UDP),(DST-PORT,443)),REJECT-NO-DROP`，拒绝 UDP 443 也就是 QUIC 流量。国内运营商对出境 UDP 限速和丢包都很重，QUIC 经节点的 UDP 转发时，X 这类 App 从后台切回来重新建连容易卡住，要等超时才退回 TCP；直接拒绝后 App 立即改用 TCP。这条必须排在所有域名规则之前，否则 x.com 等流量会先被后面的规则带走。国内直连的 App 也会随之改用 TCP，影响很小。唯一的例外是 Claude：在 Claude 上传图片仍比 Nextin Hub 生成的模板慢，而 Nextin 不拦 QUIC，上传可能走了 HTTP/3，所以在拒绝规则之前加了两条 `AND` 规则，让名字带 claude 的域名和 anthropic.com 的 UDP 443 走 `US`，作为对比试验。节点不支持 UDP 时，`udp-policy-not-supported-behaviour = REJECT` 会直接拒绝，Claude 照样立即退回 TCP。若试下来没有变快，删掉这两条即可。

### URL 重写

模块把 `google.cn`、`g.cn`（含 `www.` 前缀）用 302 跳转到 `https://www.google.com`，跳转由 Shadowrocket 在本地直接返回，不经过任何节点。正则在主机名之后要求紧跟 `/`、`:`、`?` 或网址结尾，否则 `g.cn.miaozhen.com` 这类以 `g.cn` 开头的其他域名也会被误跳转。对 https 地址，不解密就看不到完整 URL，所以模块同时用 `%APPEND%` 把这四个主机名追加进 `[MITM]` 的解密列表；证书仍用设备上那份配置里生成的，仓库里不出现证书和口令。没有安装并信任证书时，只有 http 地址的跳转会生效。
