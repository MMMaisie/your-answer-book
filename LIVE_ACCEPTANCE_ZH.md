# DeepSeek 真实模型验收 v49.8.2

默认预览不调用API。实际执行需要密钥环境变量及 --execute --budget-cny；人民币直接计价，无汇率换算。不自动读取.env。Windows推荐始终加 -X utf8，代码读取知识文件也已明确UTF-8编码。

## Windows：继续上次已保存的初判

在原项目目录覆盖更新文件，保留 .venv、acceptance-reports 和自己已有的本地配置。不要删除报告或 daily-budget-cny.sqlite3。仍在配置过密钥的同一个PowerShell窗口执行：

```powershell
$env:AI_DAILY_BUDGET_CNY = "10"
.\.venv\Scripts\python.exe -X utf8 tools\live_acceptance.py --execute --budget-cny 10 --limit 1 --resume ".\acceptance-reports\20261122T102231Z-9bdb1d63" --save-responses
```

--resume只读取原报告，新结果存入新目录，不覆盖旧报告。它核对原问题、固定卦盘及已存初判；初判复用，付费复核、文案缺哪一步才执行哪一步。若引擎版本或模型设置变化，则重做复核和文案，保留初判以免重复花费。旧初判文案不会因此自动改写；付费复核可以纠正原判断。单独测试新初判请开启新测试，不使用resume。

## 新测一个问题

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\live_acceptance.py --limit 3
.\.venv\Scripts\python.exe -X utf8 tools\live_acceptance.py --execute --budget-cny 10 --limit 1 --topic marriage --scenario static --save-responses
```

话题可选marriage/offer/house/debt/exam/lost/rent/business/legal/travel/pet/cooperation，盘面static/moving/multiple。12×3共36个组合只是验收样本，不是全书覆盖证明。--limit默认1；--english增加英文翻译。固定日期2026-11-22 11:40北京时间，便于重现，不是当前日期预测。

## 预算的实际含义

- AI_DAILY_BUDGET_CNY 默认10：每天UTC零点重置（阿德莱德夏令时10:30）。同一项目的本地测试跨多次运行共用 acceptance-reports/daily-budget-cny.sqlite3；更换 --out 不改变这个账本。
- --budget-cny 10：本次运行最多预留10元，仍受当天剩余额度约束，不会每次重跑重新获得10元。
- 不同设备、项目副本和线上网站不是同一个账本，不能自动合并为整个DeepSeek账户每天10元的硬限额。这个工具不访问线上Neon或Stripe。若需要总额不超过10元，不要让本地测试和线上同时使用各自额度。
- 按UTF-8输入字节加额外开销和输出上限预留。Pro输入/输出默认10/30元每百万token，Flash默认2.5/10，均高于2026-11-22官方高峰缓存未命中价格9/27及2/8。配置项AI_PRO_INPUT_CNY_PER_M、AI_PRO_OUTPUT_CNY_PER_M、AI_FLASH_INPUT_CNY_PER_M、AI_FLASH_OUTPUT_CNY_PER_M。缓存、闲时优惠不提前折扣，失败也保留预留，防止超时已计费。
- Reserved CNY不是实际扣款，实际费用以DeepSeek后台为准。供应商调价后应更新单价上限。这是程序预留控制，不是对供应商账户设置强制扣费上限。
- 续测旧AUD报告：有token用量的旧调用按当前人民币上限重算并登记一次；没有用量时以旧AUD预留×5保守计入。×5是迁移安全系数，不是汇率报价。不重复登记同一报告，不把旧日支出计入今日。不要手动删除账本以绕过额度。

## 报告与判断

每次输出Report路径、真实请求次数、本次及今日CNY预留、逐项状态。budget_stopped会在summary.json中记录scope（run/day）、next_stage、next_reservation_cny及remaining_cny。先读报告，再决定是否继续，不要无意识从头重跑。

calls.json保存阶段、结束原因、token用量、预留金额；*-output.json保存所有已完成阶段；*-chart.json保存本盘；--save-responses保存最终content，不保存隐藏思考、密钥、请求头或原始SDK错误。summary.csv为Excel友好UTF-8。报告不要提交Git。

protocol_passed只说明初判→复核→文案通过程序校验，quality_review仍为pending，须人工看依据、结论、语气、是否编造现实情况及中英文一致性。退出码0为全部选定组合通过；2为失败、预算停止或配置错误。

测试脚本不测试支付、排队、PDF、外部搜索或线上数据库。这些仍需分别验收，不能由模拟模型测试代替。
