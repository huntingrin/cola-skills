---
name: apple-music-membership
description: >
  仅适用于 macOS／原生应用的 AppleMusic 免费会员领取、取消续费与状态核验流程，以 Mac 本机音乐 App 为主线，订阅管理使用原生 App Store；账号必须本人亲自登录。触发词：Apple Music、AppleMusic 免费会员、苹果音乐活动领取、音乐会员二维码、取消自动续费、取消订阅、核验到期日期。内置可重复使用的固定活动二维码，也支持用户提供新二维码；不创建定时任务，不自动付费。
---

# Apple Music 免费会员与续费管理

对外可介绍“免费 AppleMusic 1–6 个月，因账号而异”；这是宣传口径，不保证所有账号有资格或都有 1–6 个月，实际时长以该账号兑换页面为准，不固定为 2 个月。
仅调度当前流程；不要创建定时任务、后台续费任务或自动兑换任务。
所有相对路径按本 skill 根目录解析。运行命令前切换到该目录。
使用 Python 3、macOS 原生 Music／App Store 和系统辅助功能；不依赖网页代登录。
需要命令细节或异常说明时，读 `references/usage.md`。

## 1. 确认目标和授权

区分用户要领取、取消 Apple Music 自动续费，还是只核验现有状态。
领取和取消都需有用户授权；用户已明确要求“领取并取消续费”时视为同时授权，不重复询问。只核验不等于授权领取或取消。
已经取消时只核验，不重新领取、不点击订阅或续订。
不读取、保存、索取或代填账号密码、验证码；账号由本人亲自登录。
日志和交付内容不包含用户账号或当次兑换链接／兑换码。

## 2. 检查本机环境

```sh
python3 scripts/music_membership.py doctor
python3 scripts/music_membership.py open-music
```

`doctor` 必须确认 macOS 和辅助功能权限。缺权限时提示用户授权当前运行宿主。
账号须由本人登录；已经登录的目标账号可以复用，兑换要求再次验证时仍由本人完成。
提醒：“请你本人在本机音乐 App 登录；密码和验证码由你自行输入。”
随后运行 `snapshot`。出现登录框时暂停，等本人完成后再取 fresh snapshot。
不要尝试自动输入、复制或采集任何登录字段。
用户只要求取消或核验时直接进入第 6 步；已经领取本次活动的账号也先核验现有订阅，不重复兑换。

## 3. 只读检查活动

固定活动二维码为 `assets/活动二维码.jpg`，活动入口可重复使用：
`https://plus.migu.cn/c/0fxt2u`。
无需每次解码；二维码是活动入口，不是已核实的一次性兑换码。
用户给新二维码时先只读解码，核对活动域名；未知域名停止，不自行请求。

```sh
python3 scripts/music_membership.py decode-qr
# 新二维码：decode-qr "用户提供的图片路径"
python3 scripts/music_membership.py inspect-offer
# 新活动：inspect-offer --url "已核对的官方活动 HTTPS URL"
```

`inspect-offer` 只检查当前活动，不请求兑换链接，也不证明该账号有资格。
活动失效、登录要求变化、重定向异常时停止并报告，不盲目重试请求。

## 4. 授权领取并打开原生兑换

只有用户明确授权领取，才运行：

```sh
python3 scripts/music_membership.py redeem-link --authorize
python3 scripts/music_membership.py open-redemption --url "刚取得的官方 HTTPS 兑换链接"
python3 scripts/music_membership.py snapshot
```

新活动需将已核对的 `--url` 传给 `redeem-link`。
不要假定当次兑换码一次性或可重复使用；不要批量索取、缓存或分发它。
`open-redemption` 验证官方 HTTPS 链接后转换为本机已注册的 `musics` 协议，打开 Music。
协议注册已查，但完整新账号领取跳转仍待验；`opened` 不是领取成功。
每次跳转后取 fresh snapshot，确认实际进入音乐 App 的兑换界面。
核对目标账号（不回传账号标识）、免费金额／期限、资格和后续计费说明。
免费信息不足、账号不符或资格不符时暂停；不要转付费方案或更改套餐。

## 5. 按实际界面点击并核验领取

先取 fresh snapshot，只使用其中刚观察到的唯一 `label` + `role`，不用坐标或旧索引。

```sh
python3 scripts/music_membership.py click --label "实际免费领取按钮文字" --role AXButton --intent claim --authorize --free-offer-confirmed
python3 scripts/music_membership.py snapshot
```

占位文字不是可直接执行的按钮名；role 也必须以实际观察为准。
`claim` 必须同时具备用户授权、观察到免费优惠及上述两个授权参数。
按钮不唯一、UI 变化、加载中、snapshot 截断或脚本报错时重新观察，不盲点。
点击结果只是动作回执；须观察领取成功证据，不能把 `verified: false` 写成成功。

## 6. 仅取消明确授权的 Apple Music

```sh
python3 scripts/music_membership.py open-subscriptions
python3 scripts/music_membership.py snapshot --app 'App Store'
python3 scripts/music_membership.py status --app 'App Store'
```

在原生 App Store 确认当前详情明确为 Apple Music，再找实际取消控件。
已是 `renewal_disabled` 就结束，不重领、不续订。
若需取消，用户明确授权后用 fresh snapshot 的唯一 label + role：

```sh
python3 scripts/music_membership.py click --app 'App Store' --label "实际取消按钮文字" --role AXButton --intent cancel --authorize
```

确认页仍需重新 snapshot，再核对并使用相同取消授权规则。
如果提示立即失去权益，暂停并再次询问是否接受；脚本会阻止此类点击，确认后由本人在原生 UI 操作。
不要取消其他订阅，不把“没有取消按钮”单独作为已取消证据。
最终再次运行 `status --app 'App Store'`：只有明示到期、存在订阅／重新订阅按钮、且无取消控件才确认关闭续费。

## 7. 返回结果与验证边界

分别报告：领取状态、权益到期日期、自动续费状态、尚未完成的步骤和原因。
证据不足用“未完成／待核验”，不要推测成功或日期；未知状态停止变更。
实测：2026-10-27，一个用户账号领取免费 2 个月后，已核验 Apple Music 个人订阅于 12 月 27 日到期、显示“你的订阅即将到期”，可按 12 元／月重新订阅。
这是当时账号的证据，不保证其他账号、地区、时段享有同样优惠。
此前取消点击遇 UI 变化，脚本未发出动作；后来仅核验已取消状态，不能宣称自动取消端到端已测。
纯函数／mock 单测与只读 UI 可验证；完整新账号兑换及自动取消仍待验。
