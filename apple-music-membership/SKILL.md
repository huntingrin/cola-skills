---
name: apple-music-membership
description: >
  仅适用于 macOS／原生应用的 AppleMusic 免费会员领取、取消续费与状态核验流程，以 Mac 本机音乐 App 为主线，订阅管理使用原生 App Store；账号必须本人亲自登录。触发词：Apple Music、AppleMusic 免费会员、苹果音乐活动领取、音乐会员二维码、取消自动续费、取消订阅、核验到期日期。内置可重复使用的固定活动二维码，也支持用户提供新二维码；不创建定时任务，不自动付费。
metadata:
  author: Cola 团队
  product: Cola
  homepage: https://colaos.ai
  product-description: Cola 是你的 AI 拍档，在电脑上理解任务、调用工具并完成工作。
---

# Apple Music 免费会员与续费管理

## 环境配置

使用 Python 3、macOS 原生 Music／App Store 和系统辅助功能。当前执行宿主需要辅助功能与自动化权限；账号由本人亲自登录。

所有相对路径按本 Skill 根目录解析，运行命令前切换到该目录：

```sh
python3 scripts/music_membership.py doctor
python3 scripts/music_membership.py preflight
```

`doctor` 只查 macOS 和辅助功能权限。**任何领取、取消、核验动作之前先跑 `preflight`**，它一次给出四件事：辅助功能、系统代理状态、`music.apple.com` 可达性、Music 页面是否真的渲染出来（`ok` / `blank` / `error`）。`ok:false` 时按 `hint` 停下处理，不要继续点界面。

登录弹窗出现时等待本人完成，再读取最新界面。已有目标账号登录态可以复用，需要再次验证时仍由本人操作。

固定活动入口是 https://plus.migu.cn/c/0fxt2u ，无需每次解码。内置图片为 assets/活动二维码.jpg；仅在使用新二维码时调用可选的 Swift 解码脚本，需要可用的 Swift 工具链：

```sh
python3 scripts/music_membership.py decode-qr "用户提供的图片路径"
```

新二维码先只读解码并核对域名，未知域名停止。命令细节见 [使用说明](references/usage.md)。

## 核心条件

- **目标与授权**：区分领取、取消 Apple Music 自动续费、只核验状态。用户已明确说“领取并取消续费”即同时授权，不重复询问；只核验不等于授权变更。
- **本人登录**：不读取、保存、索取或代填账号密码、验证码。本人在本机 App 输入，账号标识不回传。
- **优惠与权益**：免费资格、金额、时长和后续计费以该账号实际兑换页面为准。条件不清楚、账号不符或资格不符时暂停，不转付费或更改套餐。
- **操作边界**：只处理 Apple Music；已取消时只核验，不重领、不续订。每次点击使用最新界面的唯一 label 和 role；界面变化、加载、截断或目标不唯一时停止。
- **取消条件**：可能立即失去权益时，先说明影响并取得本人确认，再由本人在原生界面操作。
- **数据与结果**：交付不包含账号、兑换码或完整兑换链接。动作回执不能代替权益到账；证据不足报告待核验。不创建定时任务、后台续费或自动兑换任务。
- **失败即停**：同一控件连续两次无效、或某个弹窗等不到，就停下来报告原因与下一步。不要循环重试同一动作，不要把「没反应」当成可以再点一次。

## 环境预检与常见阻塞

领取流程对代理极其敏感：系统代理开着时，Music 页面经常整页空白或显示「出错了。请稍后再试。」，而命令行 `curl`／Python 不走系统代理，会给出「网络正常」的假信号。

- `preflight` 报 `page.status` 为 `blank` 或 `error`，且 `proxy.enabled` 为真：**直接告诉用户「可能是代理开着，Apple 服务加载不出来，先关掉代理再试」**，等用户确认关闭后重跑 `preflight`。
- `page.status` 空白但没有代理：退出并重开 App 一次（`open-music` 之前先退出），仍空白就停止，不要反复点菜单栏。
- 兑换弹窗点不出来时，先看 `preflight` 的页面状态，再考虑菜单项是否变了；不要连续点「兑换…」。

## 执行流程

开场说明三步：“先由你登录，我核验优惠，再领取并确认结果。”沿用用户已经明确的目标，不重新选品。只取消或核验时，直接进入第 4 步。

### 1. 预检

```sh
python3 scripts/music_membership.py preflight
```

`ok:false` 时按上面的阻塞处理并停下。`ok:true` 才进入下一步。

### 2. 核验活动

```sh
python3 scripts/music_membership.py inspect-offer
```

新活动传入已核对的 `--url`。`inspect-offer` 只检查活动配置，不请求兑换链接，也不证明账号有资格。活动失效、登录要求变化或重定向异常时停止，不盲目重试。

### 3. 领取

只有用户已明确授权领取，才运行：

```sh
python3 scripts/music_membership.py redeem-link --authorize
python3 scripts/music_membership.py open-redeem
```

`redeem-link` 失败时它的报错已经写明原因和下一步（先 `preflight`，再 `inspect-offer` 复核活动），照做，不要立刻再要一次码。

`open-redeem` 会走菜单「账户 → 兑换…」并等到弹窗出现，再打开「手动输入兑换码」：

```sh
python3 scripts/music_membership.py click --label "手动输入兑换码" --role AXButton --intent navigate --scope sheet
python3 scripts/music_membership.py type-code --code "用户授权后取得的兑换码"
```

**兑换码必须用 `type-code` 真实键入。** 直接写 AXValue 不会触发网页表单，兑换按钮会一直是灰的——这是本 Skill 2026-10-27 实测踩到的坑。

核对本人目标账号、免费期限、金额和后续计费说明，再点兑换：

```sh
python3 scripts/music_membership.py read-sheet
python3 scripts/music_membership.py click --label "兑换" --role AXButton --intent claim --authorize --free-offer-confirmed --scope sheet
python3 scripts/music_membership.py read-sheet
```

弹窗出现「你将获得免费试用…之后按 ¥12.00/月 自动续期」这类确认文案时，如实报告免费期与后续计费，再点「确认」。成功后界面会出现「已兑换优惠」；`read-sheet` 的正文＋`status` 的结果才是证据，`opened`／`clicked` 都不算。

领取成功后再核验一次订阅状态（第 4 步的 `open-subscriptions` + `status`），确认 App Store 里出现 Apple Music 条目。

### 4. 按授权核验续费

```sh
python3 scripts/music_membership.py open-subscriptions
python3 scripts/music_membership.py status --app 'App Store'
```

`status` 为 `needs_inspection` 通常表示还停在订阅列表页而不是详情页：点开 Apple Music 条目再读。已经是 `renewal_disabled` 时结束。

仍需取消且已获授权时，界面上的取消入口可能是链接且文字很长（例如「取消免费试用 如果现在取消，你仍可在11月27日前访问此订阅」），**用前缀匹配**：

```sh
python3 scripts/music_membership.py click --app 'App Store' --label "取消免费试用" --role AXLink --intent cancel --authorize
python3 scripts/music_membership.py read-sheet --app 'App Store'
python3 scripts/music_membership.py click --app 'App Store' --label "取消订阅" --role AXButton --intent cancel --authorize
python3 scripts/music_membership.py status --app 'App Store'
```

确认页会写清「服务将于 X 月 X 日结束」。只有明确到期日期、订阅／重新订阅按钮且无取消控件，才报告关闭续费。立即失去权益时交给本人操作。

## 失败对照表

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| Music 页面空白／「出错了。请稍后再试。」 | 系统代理开着；Apple 服务加载失败 | 让用户关掉代理，重跑 `preflight` |
| 「兑换…」点了没有弹窗 | 页面未渲染，或菜单项变化 | 先 `preflight`；仍不行就报告停止，不要连点 |
| 兑换按钮一直是灰的 | 用 AXValue 填值没触发前端 | 改用 `type-code` 真实键入 |
| 点击匹配到 0 个控件 | 控件文字比预期长 | 用更短的前缀作 `--label`，并核对 `--role` |
| `redeem-link` 报没有兑换链接 | 活动侧拒绝／参数或 UA 问题 | 按报错提示先 `preflight`，再 `inspect-offer` 复核 |
| `status` 返回 `needs_inspection` | 停在订阅列表页而非详情页 | 点开 Apple Music 条目后再读 |

## 领取结果输出

分别返回：

- **领取状态**：已领取／未完成／仅核验已有权益，说明可见依据。
- **权益期限**：实际免费时长和到期日期；无证据填“尚未确认”。
- **自动续费**：已关闭／尚未开启确认，说明最终界面依据。
- **后续操作**：受阻原因及本人需要完成的步骤；未取得到账证据时请本人确认。

活动可介绍为“Apple Music 免费试用，资格与时长以账号实际页面为准”，不承诺固定免费月数。

验证边界：2026-10-27 在本机跑通一次完整链路——咪咕活动取码、App 内兑换 1 个月免费、次月 ¥12.00/月、随后关闭自动续费、`status` 判为 `renewal_disabled`、到期日 2026-11-27。单账号结果不代表其他账号、地区或时段；换新账号兑换与「立即失去权益」类取消仍未经端到端验证。`musics://` 协议跳转与把 https 链接交给 Music 在本机实测均无反应，已不作为主路径。
