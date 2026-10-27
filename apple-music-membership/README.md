# Apple Music 免费会员与取消续费 Skill

仅适用于 macOS 原生音乐 App 与 App Store。内置固定活动二维码 `assets/活动二维码.jpg`，可直接使用活动入口 <https://plus.migu.cn/c/0fxt2u>，也支持用户提供新二维码。活动入口可重复使用；这不表示当次兑换码一次性或可重复使用，也不保证每个账号都有领取资格。

可介绍为“免费 AppleMusic 1–6 个月，因账号而异”。这不是所有账号都能领取或都有 1–6 个月的承诺；**实际免费时长以该账号兑换页面为准，不固定为两个月。** 下方两个月仅为本机验证记录。

## 安装与使用

把完整 `apple-music-membership` 文件夹放入支持 SKILL.md 的 skills 目录，例如 `~/.cola/skills/`，在下一轮会话中使用。保留 `scripts/`、`assets/` 和 `references/`。

依赖：macOS、Python 3、系统 `osascript`；二维码解码还需要可用的 Swift 工具链和系统 Vision 框架。不需要第三方 Python 包。

先运行 `python3 scripts/music_membership.py doctor`，按提示授予运行宿主辅助功能权限；首次自动化访问 System Events 时也可能需要本人批准。**Apple 账号由本人亲自在本机 App 登录；密码和验证码不代填、不采集。**

可这样请求：
- “领取这个 Apple Music 免费活动，我授权领取，账号我自己登录。”
- “取消我的 Apple Music 自动续费，先核对是否立即失去权益。”
- “只检查 Apple Music 是否已取消续费，不要领取或续订。”

执行细节见 `SKILL.md` 与 `references/usage.md`。领取和取消都需要明确授权；一句“领取并取消续费”即可同时授权。免费资格不符时不转付费；立即失去权益时另行确认。不会创建定时任务。

## 验证范围

2026-10-27 已观察到一个用户账号领取免费 2 个月，随后原生 App Store 显示 Apple Music 个人订阅“12 月 27 日到期”“你的订阅即将到期”，可按 12 元／月重新订阅，最终核验自动续费关闭。此证据不代表通用活动承诺。

此前脚本取消点击因 UI 变化未发出动作；后续只是核验取消成功状态。**不宣称自动取消已端到端测试。** `musics` 协议已查到本机注册，但完整新账号兑换跳转和自动取消仍待测试；每次必须读取最新界面确认结果。

离线无副作用测试：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

测试仅使用纯函数和 mock，不登录、不访问活动接口、不打开本机 App、不领取或取消权益。交付不包含用户账号、密码、验证码或当次兑换码。
