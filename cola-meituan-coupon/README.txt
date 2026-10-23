Cola 美团领券（基于美团开放平台官方技能 meituan-coupon v1.0.10 的接口）

Cola 预装本技能；每天自动领由 Cola 的智能闹钟负责，技能本身不建定时任务。

结构
  SKILL.md            给 Agent 的说明：用户说什么 → 跑哪条命令，输出原样发给用户
  scripts/run.sh      Mac / Linux 入口：找 Python 3.8+，没有就免密码装到 ~/.cola/runtime/python
  scripts/run.ps1     Windows 入口（同上，装到 %USERPROFILE%\.cola\runtime\python）
  scripts/mt.py       全部逻辑，只用 Python 标准库（不再需要 httpx / pip）
  scripts/config.json subChannelCode / lch

命令（mt.py）：claim / sms PHONE / login PHONE CODE / history [DATES] / logout

推广链接
- 每类券的文案（用途）和链接都在 scripts/mt.py 的 CONF 表里，按这次真领到的券自动拼：领到哪类才说哪类、才放哪类的链接。
- 现在外卖、买菜、闪购的「去使用」和结尾「还想多领」都指向 http://dpurl.cn/CFuhm7Dz（美团红包天天领，Cola 推广位）；酒店、机票、火车票用券自带链接，结尾不推。

已知情况（2026-10-19 实测）
- 一次 10 张、合计 ¥139：外卖 4 张（满 25 减 7、满 30 减 10、满 38 减 14、满 48 减 18）、买菜超市 2 张、闪购 1 张、境外酒店 1 张、机票火车票各 1 张（当天领、次日过期）。
- 每个美团账号每天只能领一次，当天再领返回的是早上那批（会自动说「今天已经领过了」）。
- 券是美团官方发的、直接进用户账户；领券记录算在美团自己的渠道下，没有 Cola 的分成。
- 登录信息和领券记录存在本机 ~/.xiaomei-workspace/skills_local_cache/，与官方 meituan-coupon 技能格式一致、共用一个登录；
  不在技能文件夹里，所以拷技能给别人不会带上账号。测新用户前先说「退出登录」。
