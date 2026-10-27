# 淘宝闪购 / 滴滴红包码

装好就出两张码：淘宝闪购 + 滴滴。不用发链接、不用建项目、不用配置。

## 用法

输入 `/skill:taobao-didi-coupon`，或直接说「领淘宝闪购红包」「滴滴红包」「再来一张」。

默认直接收到：

- 淘宝闪购二维码 PNG + 一句自己扫文案
- 滴滴二维码 PNG + 一句自己扫文案

默认按「自己扫」写；明确说「发群」时只换文案，不换码。

## 码从哪来

- 两张码在 `assets/`，是提前生成好的固定 PNG；扫码进入对应活动页。
- 发码不需要 Node、不需要联网、不需要读项目配置。
- 码随技能包分发：谁安装都能扫，扫码归因到码里原有的推广链接。
- 链接换了才需要重新生成码，见下面「换码」。

## 它不做什么

- 不登录用户账号、不代领、不碰验证码。
- 不保证券还能领、金额多少、佣金到账；以活动页面为准。
- 不替用户发群；只交付二维码和一句发群文案。
- 不把推广链接、二维码、账号信息写进全局记忆或书签。

## 换码（维护）

只有用户明确说「换链接 / 换码」时才做：

```bash
# 1. 检查新链接（不登录、不带 cookie、不验券）
node scripts/check_link.mjs "<完整链接>"

# 2. 生成新 PNG，覆盖 assets/ 下同名文件；先备份旧图
node scripts/make_qr.mjs "<完整链接>" "assets/淘宝闪购-红包二维码.png"
node scripts/make_qr.mjs "<完整链接>" "assets/滴滴-红包二维码.png"
```

生成后最好用本地解码器解回链接核对；没有解码器就如实说「文件已生成，未做扫码验证」。

## 目录

```text
SKILL.md                     Agent 入口：默认发两张码、文案、边界、换码
assets/淘宝闪购-红包二维码.png  固定码，随技能包分发
assets/滴滴-红包二维码.png      固定码，随技能包分发
scripts/make_qr.mjs          无依赖 QR PNG 生成器（vendor MIT qrcode-generator）
scripts/check_link.mjs       无登录链接连通性检查（换码时用）
tests/smoke.mjs              本地冒烟测试，不联网
```

## 验证

- `node tests/smoke.mjs` 通过（不联网）。
- 两张码用 macOS Vision 解码，内容与原始推广链接一致。
- 未在 CI 中做真机扫码、登录或领券验证；活动是否有效、券能否领到，以活动页面为准。

## 隐私

- 技能包内含两张推广二维码；仓库公开时，码对所有安装者可见、可扫。
- 不含账号、手机号或验证码。
- 不想让码跟着技能包分发时，不要安装或发布这个包。

## License

MIT。二维码矩阵使用 [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator)（MIT），许可证见 `scripts/vendor/LICENSE-qrcode-generator.txt`。
