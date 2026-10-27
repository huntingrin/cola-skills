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
python3 scripts/music_membership.py open-music
python3 scripts/music_membership.py snapshot
```

doctor 检查 macOS 和辅助功能权限。缺权限时提示本人授权当前运行宿主；出现登录框时等待本人完成，再读取最新界面。已有目标账号登录态可以复用，需要再次验证时仍由本人操作。

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

这些是执行约定；当前脚本的完整点击保护、兑换链接输出脱敏和端到端稳定性仍需单独验证。

## 执行流程

开场说明三步：“先由你登录，我核验优惠，再领取并确认结果。”沿用用户已经明确的目标，不重新选品。只取消或核验时，直接进入第 3 步。

### 1. 核验活动

```sh
python3 scripts/music_membership.py inspect-offer
```

新活动传入已核对的 --url。inspect-offer 只检查活动配置，不请求兑换链接，也不证明账号有资格。活动失效、登录要求变化或重定向异常时停止，不盲目重试。

### 2. 领取并核验

只有用户已明确授权领取，才运行：

```sh
python3 scripts/music_membership.py redeem-link --authorize
python3 scripts/music_membership.py open-redemption --url "刚取得的官方 HTTPS 兑换链接"
python3 scripts/music_membership.py snapshot
```

新活动需将已核对的 --url 传给 redeem-link。不要批量索取、分发或假定兑换码可重复使用。open-redemption 将官方 HTTPS 链接转为 musics 协议打开 Music，opened 不代表领取成功。

核对本人目标账号、免费期限、金额和后续计费说明，再使用刚观察到的按钮：

```sh
python3 scripts/music_membership.py click --label "实际免费领取按钮文字" --role AXButton --intent claim --authorize --free-offer-confirmed
python3 scripts/music_membership.py snapshot
```

占位值和 role 均须以实际界面为准。free-offer-confirmed 表示已经观察并核对免费优惠，不能替代页面核验。

点击后读取领取成功证据；verified:false 不写成成功。缺少到账证据时，主动请本人确认会员是否生效，避免重复领取。

### 3. 按授权核验续费

```sh
python3 scripts/music_membership.py open-subscriptions
python3 scripts/music_membership.py snapshot --app 'App Store'
python3 scripts/music_membership.py status --app 'App Store'
```

确认当前详情为 Apple Music。已经是 renewal_disabled 时结束；仍需取消且已获授权时：

```sh
python3 scripts/music_membership.py click --app 'App Store' --label "实际取消按钮文字" --role AXButton --intent cancel --authorize
```

确认页重新读取并核对。立即失去权益时按核心条件交给本人操作；不要处理其他订阅或把缺少取消按钮单独作为已取消证据。

最后再次运行 status --app 'App Store'。只有明确到期日期、订阅／重新订阅按钮且无取消控件，才报告关闭续费。

## 领取结果输出

分别返回：

- **领取状态**：已领取／未完成／仅核验已有权益，说明可见依据。
- **权益期限**：实际免费时长和到期日期；无证据填“尚未确认”。
- **自动续费**：已关闭／尚未确认，说明最终界面依据。
- **后续操作**：受阻原因及本人需要完成的步骤；未取得到账证据时请本人确认。

活动可介绍为“Apple Music 免费试用，资格与时长以账号实际页面为准”，不承诺固定免费月数。

验证边界：原包记录过一个账号领取 2 个月、最终核验续费关闭，同时注明自动取消点击曾因界面变化未执行。完整新账号兑换和自动取消仍待验；历史单账号记录不代表其他账号、地区或时段同样适用。
