# scripts

默认发码流程不需要跑脚本；这里只用于换码维护。路径相对技能根目录解析：

```bash
SKILL_DIR="$(dirname "<SKILL.md 的绝对路径>")"
```

## make_qr.mjs

```bash
node "$SKILL_DIR/scripts/make_qr.mjs" "<完整链接>" "$SKILL_DIR/assets/<平台>-红包二维码.png"
```

- 生成 PNG，8px/模块，4 模块留白，ECC M。
- 不联网、不装依赖、不用图像模型。
- 输出 `QR: <绝对路径>`、`MODULES`、`SIZE`、`BYTES`。
- 覆盖前先备份旧图；同一个活动不要混用不同文件。
- QR 矩阵来自 `vendor/qrcode.js`（qrcode-generator，MIT，见 `vendor/LICENSE-qrcode-generator.txt`）；PNG 容器由本脚本用 `zlib` 写入。

## check_link.mjs

```bash
node "$SKILL_DIR/scripts/check_link.mjs" "<完整链接>"
```

- 跟随重定向和 HTML meta refresh 短链做一次 GET，不登录、不带 cookie、不验券。
- 输出 JSON：`ok`、`status`、`finalHost`、`finalPath`、`loginWrapper`、`metaRedirect`、`params`、`warnings`。
- `ok` 只代表链接能打开，不代表券还能领或佣金能到账。
- `metaRedirect: true` 表示短链先跳了一次，正常；看最终 host 和参数。
- `warnings` 可能是 `sid_placeholder`、`no_attribution_params`、`login_page`、`http_error`、`network_error`。
