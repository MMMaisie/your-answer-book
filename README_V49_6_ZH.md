> 当前版本 v49.8.2：每日模型预算为人民币10元；旧AUD变量停止使用。请先看文末更新及 LIVE_ACCEPTANCE_ZH.md 的续测步骤。

# v49.8.1 完整队列版：部署前请读

本版本新增数据库任务队列，初判和付费解读都由独立后台Worker执行。不是仅覆盖网页代码就能工作。未切换Stripe正式模式、未删除测试密码、未修改你的线上账户。

## 本次行为

- 起卦、结账、付款检查等同类操作：固定5秒冷却；重复点击不延长，不再升级15分钟封锁。首次升级清除旧频率封锁记录，不清空免费次数、费用或付款记录。
- 默认全站模型请求300次/UTC日，最多同时5次模型请求；搜索20次/UTC日。Render已配置的环境变量优先，需要按下方更新。
- 初判/付费任务保存到现有数据库，同卦同语言同层级重复提交复用任务，不重复付款。队列按创建顺序领取（重试、同卦锁和依赖可能改变完成顺序）。
- 队列最多100个等待或运行任务；等待15分钟未领取则失败，可手动重试。免费初判在执行失败或等待过期后退回尚未使用的免费名额；已成功中文、英文失败时不退成功中文的免费名额。
- 模型并发满额自动回到等待队列；预算/日调用额度用完不无限重试，页面允许稍后手动重试，保留付款权益。
- 页面每5秒自动刷新等待结果。后台中断的租约20分钟后可重新领取，最多自动恢复2次；已保存初判、复核和正文会复用。网络成功但尚未保存时进程被杀，不能承诺API绝不重复消耗。
- Worker无心跳或队列满时暂停新付款入口，避免收款后无人处理；已付款任务权益仍保留。
- 免费浏览器每天1次、同IP每天2次，CSRF、Turnstile、支付校验、内容校验、AI关闭开关仍保留。

## 部署步骤（先测试，不切正式支付）

1. 覆盖项目文件并提交至原仓库，保留.git、真实环境配置、稳定的FLASK_SECRET_KEY和Neon数据库。不要新建空数据库。
2. 原Web Service继续使用：
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn guaxiang:app
3. 在Render新增一个Background Worker，连接同一个仓库、分支、根目录、Python版本。Worker需独立运行，平台费用以创建页显示为准。本包不需要新增Redis。
   Build Command: pip install -r requirements.txt
   Start Command: python queue_worker.py
4. Web和Worker共享相同Neon DATABASE_URL、FLASK_SECRET_KEY、PUBLIC_BASE_URL、SUPPORT_EMAIL、DEEPSEEK_API_KEY及模型设置、预算参数、Stripe模式及该模式密钥、Turnstile配置。复制现有环境值，不要生成另一套secret，不要把密钥提交Git。
5. 两个服务都设置：

   GENERATION_QUEUE_ENABLED=1
   SAFETY_LIMITS_ENFORCED=1
   PRIVATE_TEST_UNLIMITED=0
   AI_ENABLED=1
   AI_DAILY_REQUEST_LIMIT=300
   AI_MAX_CONCURRENT=5
   WEB_SEARCH_DAILY_LIMIT=20
   AI_DAILY_BUDGET_CNY=10
   STRIPE_MODE=test

   预算仍保留A$2，采用保守预留，可能比次数上限更早触发；300次是次数上限，不表示A$2一定够300次。Web和Worker预算设置必须一致。
6. 等两个服务部署完成后，访问Web的/healthz：
   version以v49.8.1-live-acceptance-开头
   generation_queue_enabled=true
   queue_worker_recent=true
   safety_limits_enforced=true
   private_test_unlimited=false

   queue_worker_recent=false时先检查Worker是否启动、是否连到同一数据库。不要继续收费测试。健康状态仅说明心跳，不代表真实模型已验收。
7. 新起一卦，页面应先显示初判排队，再自动出现结果；用Stripe测试支付后点生成，全文应从队列自动出现。再检查英文和PDF。重复点击不能新增同一任务，刷新不会重新扣费。

保留旧部署版本和环境配置。若Worker未配置完成，可在Web临时设GENERATION_QUEUE_ENABLED=0恢复原同步生成，不会删除已排队任务；恢复队列后仍需处理它们。不要同时把所有已付费卦重新创建。

## 正式上线

本包不会自动切换正式支付。最后测试通过后，再在两个服务一致切换STRIPE_MODE=live，配置真实Stripe密钥及正式Webhook签名secret，并在正式Stripe配置本站/stripe/webhook事件。测试付款不能自动视为正式付款。公开站点前再移除SITE_ACCESS_PASSWORD；保留安全限制。正式订单、回调、生成、英文和PDF仍需验收。

## 本地验收与尚未验收

本地953项测试通过，包括5个模型请求并发入场、第6个等待、跨进程读取任务、真实Worker入口启动/优雅退出、队列重复提交、超限、过期、有限恢复、初判/付费/英文/PDF、失败后保留付款与复核、旧版回归。另检查Gunicorn启动及12个中英文页面。

模型与支付使用模拟数据；队列自动测试使用SQLite，另补跑本地PGlite的PostgreSQL协议检查，验证初始化、领取、去重及初判/付费保存；未验证线上Neon的TLS实际连接或真实DeepSeek输出。没有访问你的Render或Stripe账户，没有实际部署或扣费，不能把本地通过称为线上验收通过。书中参考覆盖及文案语义也不由这些流程测试证明。

Render文档：https://render.com/docs/background-workers

## 新增真实API验收工具

见LIVE_ACCEPTANCE_ZH.md。仅新增工具、说明及版本标记，不改变v49.8队列与支付逻辑。默认dry-run，明确--execute和--budget-cny才会产生费用。本次没有实际执行付费测试。


## v49.8.2 人民币预算与续测

当前交付v49.8.2。Web和Background Worker同时更新；两个服务都设置AI_DAILY_BUDGET_CNY=10。旧AI_DAILY_BUDGET_AUD、BUDGET_AUD_PER_USD、*_USD_PER_M和WEB_SEARCH_RESERVE_AUD不再读取，删除旧变量以免混淆。新的人民币单价变量见environment.example.txt。不要让旧版本Worker继续运行。

默认每日10元，UTC零点重置。新调用写入CNY标记；已有数据库自动增加currency字段，原记录保留为AUD，统计时按旧预留×5保守累计，金额不清零。×5只是旧预留的迁移安全系数，不是市场汇率。并发仍为5，排队、安全验证及支付权益不变。不同部署若共用同一个数据库，则共用网站的额度。

本地真实验收见LIVE_ACCEPTANCE_ZH.md，支持--resume，不再重做已完成初判。本地账本和线上数据库相互独立；并行运行时不能声称整个API账户合计每天最多10元。

本包修复Windows知识JSON默认GBK读取问题；婚恋提示词补充“不把旺衰直接写成人物现实条件优劣”。已有报告或已生成内容不会自动重写。付费真实模型完整验收仍未通过，需继续实测。
