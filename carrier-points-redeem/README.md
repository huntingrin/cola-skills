# 三网积分兑换 · Cola 预装版

将三个运营商流程收进一个 `carrier-points-redeem` 入口，针对 Cola 已预装、已有浏览器能力的环境执行。运行时不查安装位置、不安装工具，只加载本次业务所需文件。

| 运营商 | 范围 |
|---|---|
| 移动 | 现有适用 AI 豆兑本机话费，现金 0 |
| 联通 | 积分兑流量包、语音包、影音组合；话费只给 10010 短信文字方法 |
| 电信 | 积分兑本机话费直充，现金 0；需要真实移动 UA 和移动视口 |

所有新查询/兑换一律按未登录处理，先打开对应 GUIDE 的完整登录地址，再验收可见表单。移动若落首页，在原页点“登录”或“请登录”，等手机号、验证码输入框和登录按钮出现才交接；不把首页当登录页，不另开第二页。本任务已有页直接接续；登录、图形码和短信验证由本人在官网完成，确认后核对账户再继续。未知余额、价格、资格与到账状态不能用历史样本补齐。

## 预装到 Cola 项目

从本仓库执行，目标是 Cola 的资源源目录，而非用户技能目录：

```sh
./install.sh --target /Users/kris/Projects/marswave/cola/apps/agent-runtime/resources/skills
```

将生成 `apps/agent-runtime/resources/skills/carrier-points-redeem/SKILL.md` 及其完整依赖，不会修改 Cola 的 TypeScript 源码。此命令会整体替换目标中同名技能，请在目标源码工作区审查变更后提交。

已核对的 Cola 副本使用现有 electron-builder 资源打包及 `bootstrapBundledResources` 部署机制，无需另加启动安装逻辑。运行位置由 Cola 给出，不把开发者项目路径写入技能。数据目录可能为 `~/.cola`、`~/.cola-cn` 或宿主配置的其他位置，运行流程不猜路径。

用户目录的同名技能可能覆盖内置版本；升级后若仍读到旧内容，先核对实际加载路径，再由维护者处理覆盖副本，不在每次兑换前扫描或自动删除用户技能。

本机适配基线：`marswaveai/cola` 副本 `cdeef1ff7`（2026-10-23）。目标项目路径不在当前机器，尚未在该目标版本中执行预装或真实兑换验收。

## 浏览器能力边界

- 用户或宿主已指定 Ego 时，按其现有 TaskSpace/后台约定执行，不自动切换浏览器。
- Cola 已启用内置 `browser` 时，在本任务页面直接打开登录 URL，不先访问商城、检查旧登录态或 status/start/tabs 连续探测。
- 下单、扣分、短信请求逐步核对，只读等待与摘要才按条件合并。
- 电信登录页可在桌面 UA 打开，移动环境检查不能拦截登录。本人登录后需要兑换时，才核对页面级移动 UA 能力；缺失时停在下单前，交由本人手机办理后续兑换。设置方法见 [浏览器适配](references/browser.md#电信移动环境)。
- 不抢前台、不导出 Cookie、不复制浏览器配置；登录与验证原页交接，等待本人确认。

## 最小阅读路径

以下均为入口 `SKILL.md` 之外的阅读量：

| 本次业务 | 读取 |
|---|---|
| 联通纯话费方法 | 直接读 `skills/cucc-points-redeem/references/phonefee-text.md`，不读 GUIDE、不开浏览器、不收手机号 |
| 移动查询/兑换 | 移动 GUIDE，自足 |
| 联通商城查询 | 联通 GUIDE；选品才加类别规则 |
| 电信查询/兑换 | 电信 GUIDE 中直接给出完整登录 URL；登录后准备下单才读移动环境，规则不清才补话费规则 |
| 异常或复杂恢复 | 对应 browser-flow / transaction-state，正常流程不预读 |

普通业务页用一次快照；复杂页或验证页需要无输入值摘要时，按需读 [observe.md](references/observe.md)，复用 [observe.js](scripts/observe.js)。该脚本只是浏览器中的只读函数，不依赖 Node 或第三方包，不替代业务判断。

查询不写文件。首次可能建单/扣分前保存一条私有断点，交接时保留页面标识，后续更新同一条。正常流程不启动状态脚本；跨进程保护可用子流程原有 Python 脚本（仅 macOS/Linux 的 fcntl 环境），同一笔共用原记录，不能靠新文件绕过提交状态。

## 使用

```text
联通话费怎么换
移动 13800138000，查查积分能兑多少，先不兑换
电信 13900139000，兑 10 元本机话费
继续刚才那笔，验证填好了
```

先使用当前任务已有信息；查询/兑换仅补缺失的运营商或预期手机号，只问方法无需手机号。用途不明先查，不能自行扣分。广电或虚拟运营商不硬路由，也不按号段猜实际运营商。

只办本机、现金 0、无自动续订。已指定面额或商品不重复选；实际成本或条件变化时说明。状态不明先查原订单，不重复下单。报告区分提交、平台完成、用户确认到账及独立权益记录。

## 目录

```text
SKILL.md                   唯一运行入口
references/browser.md      Cola 接口、能力失败及电信移动环境（按需）
references/observe.md      安全摘要调用及字段解释（按需）
scripts/observe.js         可复用的只读函数
skills/*/GUIDE.md          三家流程，按分支读取
skills/*/references/      类别规则、异常恢复和可选状态脚本说明
agents/openai.yaml         支持该格式的宿主展示信息
install.sh / uninstall.sh  维护者安装工具
tests/                    离线校验与摘要测试
```

子流程使用 GUIDE.md，避免被发现为三个额外技能。README、来源记录、测试和安装脚本只供维护，运行时不读。

## 其他安装方式

保留原有兼容入口；这些是维护者操作，不是预装 skill 的运行步骤：

```sh
./install.sh --target cola       # 用户技能 ~/.cola/skills
./install.sh --target codex
./install.sh --target claude
./install.sh --target ~/my-skills
```

不传目标时沿用原安装器的 Codex / Cola / Claude 检测与静默安装；无匹配时回落到 Codex。其他数据目录请传实际 skills 目录，不把 `--target cola` 当作所有地区/配置的路径解析器。

独立安装的三家技能默认保留；需要归档时显式加 `--archive-standalone`，旧目录移到同级归档目录，恢复时先卸载入口再移回。卸载用 `./uninstall.sh --target 实际skills目录`。

手动安装（含 Windows）：将本技能目录完整复制到宿主实际 skills 目录下的 `carrier-points-redeem/`，保留 references、scripts、skills、agents 和根 SKILL.md，不复制 .git。Windows 使用 Git Bash 时也可运行安装脚本；本机预装目录由目标项目决定。

## 验证

```sh
bash tests/test_install.sh
python3 -m unittest discover -s tests -p 'test_skill_contract.py' -v
node --test tests/test_observe.cjs
```

离线检查覆盖安装/重复安装/卸载、Cola 资源目录打包、唯一技能发现、引用有效性、阅读字符预算、文档号码脱敏，以及摘要对零余额、敏感输入、网址参数、长度限制的处理。Python 检查也运行两份未改动的状态脚本测试。测试需要 Python 3、Node 和 Bash；这些不成为普通兑换流程的安装要求。

静态检查包含三家登录直达路由与回跳参数，防止入口退回商城首页或把电信 appCode 写成渠道编号。网页验收关注：新任务直接显示登录表单、一次登录交接、联通文字分支、账户不符停止、超时恢复不重提，以及电信缺少移动环境仍先完成登录、仅在下单前停止。真实兑换另需本人授权；文档阅读量不代表实测网页耗时。

## 来源

上游提交、许可及本地修改见 [THIRD_PARTY.md](THIRD_PARTY.md)。整合层和新增摘要函数采用本仓库 MIT License，子流程沿用各自许可状态。
