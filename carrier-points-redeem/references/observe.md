# 可选：一次读取非敏感页面摘要

普通业务页的一次快照已经包含所需字段时，不加载本文件。仅在页面冗长、字段不足，或登录/验证后需要避免读取输入值时使用。

读取一次 [scripts/observe.js](../scripts/observe.js)，将整个文件作为函数源码复用：

- Cola：`browser` 参数为 `action="act", kind="evaluate", profile, targetId, fn`，fn 的值是文件全文，不能传本地路径。
- Ego：按其技能使用 `page.evaluate(函数源码)`；不要直接执行整个技能目录或重写一份提取器。
- 脚本只读取可见正文和按钮标签，不读任何输入值、Cookie、存储或网络；返回的号码已脱敏，网址不含 query/hash。不点击、不等待、不下单。
- 摘要没有 refs。下一步需要交互时仍按浏览器工具要求读取当前快照；不要为已有完整快照额外跑摘要。验证阶段不能安全取得 refs 时，让本人完成验证及确认后接回。

## 字段如何使用

| 返回项 | 用途及限制 |
|---|---|
| page | 识别站点和路径，不含登录/收银台参数 |
| signals | 登录、验证、结算、结果文字的独立线索；可同时为 true，不是最终阶段或成功判定 |
| accounts | 可见脱敏号码，核对可见位；没有则表示未读到 |
| pointLines / amountLines | 原文积分/金额上下文；空数组不是 0，不计算余额或兑换比例 |
| orderLines / ruleLines | 本页可见订单/规则线索，不代替完整商品细则或最终订单核对 |
| buttons | 可见按钮标签，仅助识别，不作为自动点击选择器 |

输出有长度上限，缺少完整组合、续订、现金或接收账户等关键字段时定向补读，不能把省略当作不存在。加载完成的合法 0 与未加载要结合本次页面业务状态判断，脚本不输出 loaded=true。

## 可选批量：只等信号再读取

仅在当前页面和要等的信号已知、evaluate 可用时，将 wait + evaluate 放到同一 `act/batch`；fn 字段使用脚本全文，避免重复生成代码：

```json
{
  "action": "act",
  "profile": "cola",
  "request": {
    "kind": "batch",
    "targetId": "本次返回的targetId",
    "stopOnError": true,
    "actions": [
      {"kind": "wait", "text": "可用积分", "timeoutMs": 8000},
      {"kind": "evaluate", "fn": "scripts/observe.js 的函数全文，替换此说明"}
    ]
  }
}
```

等待失败时该批次不执行摘要；再做一次安全读取判断是否未加载，不直接重放批次。条件等待最多补一次；字段仍不明就报告缺项。evaluate 不支持时按 [能力失败](browser.md#能力失败) 降级，不改配置或循环重试。
