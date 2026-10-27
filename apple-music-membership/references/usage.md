# 命令与安全边界

在 skill 根目录执行命令；从其他目录使用时，先将相对路径解析到本 skill 目录。以下占位值仅是说明，执行前替换为最新 UI 观察或当前官方链接。

| 命令 | 行为与前提 |
| --- | --- |
| `python3 scripts/music_membership.py doctor` | 检查 macOS 与辅助功能权限；不领取、不取消。 |
| `python3 scripts/music_membership.py open-music` | 打开本机音乐 App；本人亲自登录。 |
| `python3 scripts/music_membership.py snapshot` | 读取 Music 最新辅助功能界面；不读取输入框内容。不要保存含账号标识的原始日志。 |
| `python3 scripts/music_membership.py inspect-offer` | GET 检查固定活动；不请求兑换码、不证明资格。 |
| `python3 scripts/music_membership.py decode-qr` | 只读解码内置 `assets/活动二维码.jpg`，返回 `{"urls":[...]}`。 |
| `python3 scripts/music_membership.py decode-qr "新二维码图片路径"` | 只读解码用户提供的图片；未知域名不继续请求。 |
| `python3 scripts/music_membership.py redeem-link --authorize` | 仅用户授权领取时请求官方兑换链接；会访问活动服务，不是只读核验命令。 |
| `python3 scripts/music_membership.py open-redemption --url "官方 HTTPS 兑换链接"` | 验证 Apple Music 官方链接并通过已注册 `musics` 协议打开 Music；打开不等于兑换成功。 |
| `python3 scripts/music_membership.py open-subscriptions` | 打开原生 App Store 订阅管理。 |
| `python3 scripts/music_membership.py snapshot --app 'App Store'` | 观察当前 App Store 订阅详情，识别 Apple Music。 |
| `python3 scripts/music_membership.py status --app 'App Store'` | 只读判定续费状态；仅 `renewal_disabled` 代表脚本观察到最终取消证据。 |

`inspect-offer`、`redeem-link` 支持 `--url "已核对的活动 URL"`。固定活动入口为 `https://plus.migu.cn/c/0fxt2u`，可重复使用；不要假定当次兑换链接里的兑换码一次性或可重复使用。不要在日志、README 或分发包保存当次兑换链接。

## 点击模板（不是即用按钮名）

```sh
python3 scripts/music_membership.py click --label "fresh snapshot 中实际导航文字" --role AXButton --intent navigate
python3 scripts/music_membership.py click --label "fresh snapshot 中实际免费领取文字" --role AXButton --intent claim --authorize --free-offer-confirmed
python3 scripts/music_membership.py click --app 'App Store' --label "fresh snapshot 中实际取消文字" --role AXButton --intent cancel --authorize
```

每次点击前取得 fresh snapshot，label 和 role 必须唯一匹配当前可用控件；AXButton 只是示例。脚本会重新观察语义目标，但这不能替代领取资格、目标账号和免费内容核对。点击后再 snapshot 确认业务结果。UI 变化或不唯一时不沿用旧按钮、不盲目重复。

- `claim`：必须有本次领取授权、可见的免费优惠、`--authorize` 和 `--free-offer-confirmed`。检查账号与地区资格；仅看到“免费”不代表已领取。
- `cancel`：只针对明确观察到、用户已授权取消的 Apple Music。其他订阅不处理。确认页再读取一次；立即失去权益时重新询问，脚本拒绝此类自动点击，用户确认后由本人手动操作。
- 已取消：只核验，不重领、不续订。看到“订阅”“重新订阅”并不表示要点击它们。
- 登录：停下来让本人输入账号、密码和验证码；不读取或代填这些内容。

## 状态解释

| 状态 | 报告与下一步 |
| --- | --- |
| `renewal_disabled` | 有明确到期文字和到期日期、订阅／重新订阅按钮且无取消控件；报告关闭续费及观察到的日期。 |
| `cancellable` | 仍有取消控件，或当前取消确认页；不等于取消成功，待授权及最终核验。 |
| `login_required` | 本人完成登录后再读取 UI。 |
| `loading` | 等待界面稳定后重新读取，不在加载时点击。 |
| `needs_inspection` | 非 Apple Music、UI 截断或证据不全；报告未完成，停止变更。 |

日期解析只处理明确到期语境；不支持的语言／格式返回未知，不猜测。无年份日期按当前日期推定下一次出现的日期；需结合 UI 原文复核。缺少取消控件、只打开页面或 `verified: false` 回执都不能单独证明成功。

## 结果模板

- 领取：已领取／未完成／仅核验已有权益，附可见证据（不含账号）。
- 到期：实际界面日期，或“尚未确认”。
- 自动续费：已关闭／尚未确认，附最终 App Store 证据。
- 受阻原因和下一步：权限、本人登录、资格、活动变化或 UI 证据不足。

## 优惠口径

可使用“免费 AppleMusic 1–6 个月，因账号而异”的宣传口径，不写成所有账号都能领取或都有 1–6 个月。实际时长以该账号兑换页面为准，不固定两个月；以下两个月仅为验证记录。

## 历史证据与待验

2026-10-27 观察到一个账号免费领取 2 个月，最终 App Store 显示 Apple Music 个人、12 月 27 日到期、“你的订阅即将到期”，可按 12 元／月重新订阅。按当时日期对应 2026-12-27；这不是其他账号的承诺。

此前取消点击遇 UI 变化，脚本没有发出取消动作；后来仅核验已取消状态。不声称自动取消端到端通过。已查本机 `musics` 注册，完整新账号兑换跳转和自动取消仍待验。无副作用单测与只读 UI 观察可以验证，不使用这些测试去变更权益。Skill 不创建定时任务。
