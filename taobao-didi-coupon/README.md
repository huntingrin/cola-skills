# 淘宝闪购 / 滴滴红包码

把淘宝闪购（饿了么）和滴滴的推广链接，变成两张可扫码领取的二维码，并各配一句文案。默认直接给两张，不用选平台；不登录账号、不代领、不承诺到账。

## 它能做什么

- 默认一次给淘宝闪购 + 滴滴两张码；用户明确只要一个时才只做一个。
- 自己扫 / 发群都出码，默认自己扫文案，发群可替换。
- 复用项目里保存的链接和二维码；说「再来一张」直接复用，不重复制码。
- 生成真实可扫的 PNG 二维码，不依赖第三方制码服务或图像模型。
- 检查链接能否打开、是否带归因参数、是否是登录入口。
- 把链接保存到项目 `红包配置.json`，下次不用再发。
- 在 Cola 里用 `MEDIA:` 把图片送进对话；其他支持文件/图片发送的 Agent 也能用。

## 它不做什么

- 不登录用户账号、不代领、不碰验证码。
- 不保证券还能领、金额多少、佣金到账；以活动页面为准。
- 不替用户发群；只交付二维码和一句发群文案。
- 不把推广链接写进仓库、全局记忆或技能目录。

## 在 Cola 中使用

1. 安装到 `~/.cola/skills/taobao-didi-coupon/`，或通过 Skill Hub 安装。
2. 输入 `/skill:taobao-didi-coupon`，或直接说「领淘宝闪购红包」「滴滴红包」「做个推广二维码」。
3. 直接出淘宝闪购 + 滴滴两张码；不用选平台，也不用先选自己扫还是发群。
4. 收到两张码和两句文案，长按保存即可；要发群就把文案换成「扫码领取…」。

第一次用、不知道链接在哪：

> 打开推广后台 → 推广/活动 → 选淘宝闪购或滴滴 → 点「我要推广」→ 复制整条链接。
> 链接里的参数别删；有推广位就确认不是默认的 `123456`。

如果只是自己领，也用这两张码：

> 扫开后按页面提示登录领取；验证码只有本人能填。

## 其他 Agent

需要：本地文件读写、运行 Node.js 18+、能把图片/文件发给用户。

没有 Node 时，可以用宿主自带的二维码能力；不要把二维码交给图像生成模型，也不要上传到陌生第三方。Cola 之外的宿主如果没有 `MEDIA:`，用宿主自己的文件/图片发送方式交付 `交付物/*.png`。

## 目录

```text
SKILL.md                     Agent 入口：首次引导、流程、边界、话术
references/onboarding.md     首次使用的完整对话分支和小白话术
references/cola-delivery.md  MEDIA 交付、项目目录、发群/操作者文案分开
references/project-setup.md  红包配置.json 的字段、复用和原子写入
references/operator-guide.md 配单/选活动/询价时才读的历史运营资料
scripts/make_qr.mjs          无依赖 QR PNG 生成器（vendor MIT qrcode-generator）
scripts/check_link.mjs       无登录链接连通性检查
tests/smoke.mjs              本地冒烟测试，不联网
```

## 脚本

```bash
# 生成 PNG（8px/模块，4 模块留白，ECC M）
node <skill-dir>/scripts/make_qr.mjs "<完整链接>" "<项目目录>/交付物/淘宝闪购-红包二维码.png"

# 检查链接（不登录、不带 cookie、不验券）
node <skill-dir>/scripts/check_link.mjs "<完整链接>"
```

`make_qr.mjs` 会打印 `QR:` 和 `VERIFY: png-ok`。`VERIFY` 只证明 PNG 容器和像素写对了，不等于扫码验证；没有本地解码器就如实说明「文件已生成，未做扫码验证」。

## 验证

- `node tests/smoke.mjs` 通过（不联网）。
- 在 Cola 里实测：首次引导、链接检查、PNG 生成、`MEDIA:` 交付、「再来一张」复用。
- 二维码用 macOS Vision 解码，内容与原始链接一致。
- 未在 CI 中做真机扫码、登录或领券验证；活动是否有效、券能否领到，以活动页面为准。

## 隐私

- 仓库不含任何推广链接、二维码、账号、手机号或验证码。
- 用户链接只写项目 `红包配置.json`；二维码只写项目 `交付物/`。
- 不登录、不读取账号数据。

## License

MIT。二维码矩阵使用 [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator)（MIT），许可证见 `scripts/vendor/LICENSE-qrcode-generator.txt`。
