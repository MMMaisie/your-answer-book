# your-answer-book v49.8.3：单个Web服务测试版

本版本默认同步生成，不需要创建或购买Render Background Worker。Stripe继续测试模式。代码的模拟验收不等于真实DeepSeek或实际支付已通过，正式收款前须由站点所有者完成线上验收。

## 部署现有Web服务

将本包内容更新到现有GitHub仓库根目录。保留已有真实环境变量、固定FLASK_SECRET_KEY和Neon数据库，不要把密钥提交Git，不要新建数据库。Web构建命令保持pip install -r requirements.txt，启动命令保持原有gunicorn guaxiang:app或gunicorn app:app。本包gunicorn.conf.py提供线程和超时设置。

Render Environment确认：

```text
GENERATION_QUEUE_ENABLED=0
AI_DAILY_BUDGET_CNY=10
SAFETY_LIMITS_ENFORCED=1
PRIVATE_TEST_UNLIMITED=0
STRIPE_MODE=test
```

不需要Worker。保留PUBLIC_BASE_URL、SUPPORT_EMAIL、DATABASE_URL、FLASK_SECRET_KEY、DEEPSEEK_API_KEY、TURNSTILE_SITE_KEY、TURNSTILE_SECRET_KEY，以及Stripe测试密钥STRIPE_TEST_SECRET_KEY和STRIPE_TEST_WEBHOOK_SECRET。两项Stripe密钥不是同一项；不可用API密钥代替webhook签名密钥。

## 本次修复

1. 关闭队列后，在查看卦盘或申请免费额度时，将尚未领取的queued任务及租约已到期的running任务转为可重试，释放它们关联的held免费记录；不删除used额度，不取消租约仍有效的任务，不更改付款权益。
2. 原来排队的免费卦出现“重试初判”，在同一卦上直接生成并保存，失败释放本次预留。成功后重复刷新或提交不会再调用模型。也可以回首页重新测试一个问题，释放旧占用后按正常每日额度申请。
3. 默认GENERATION_QUEUE_ENABLED=0，不再默认依赖一个未创建的收费后台服务。初判和付费在现有Web内直接生成；并发上限仍为5、固定冷却5秒。同步模式没有独立的持久后台执行进程；长请求、服务重启和流量承载仍需线上验证，不能保证免费主机正式运营的可用性。
4. 旧AUD记录不再一律以原最大预留×5判断今日预算：成功且有完整正token用量的Pro/Flash调用，按配置的人民币保守单价核算；失败或用量不明的调用仍保留原预留（旧AUD×5，新CNY原金额），不假设超时免费、不清空消费记录。新调用的原始预留保留供审计，已知token按高峰上限估算，不套用缓存或闲时优惠。实际账单以DeepSeek后台为准。
5. /healthz新增checkout_blockers，显示付款入口的具体阻断条件；不返回密钥、数据库地址或问题内容。不会为了显示付款按钮而跳过签名、预算或必要配置。

## 部署后只做这一步检查

打开网站 /healthz：

- version以v49.8.3-sync-recovery-开头。
- generation_queue_enabled为false。
- ai_budget_currency为CNY。
- checkout_blockers为空数组时，基础收款配置及全站用量检查通过。真正创建checkout时仍检查本卦完整生成所需余额和CSRF、人机验证。

若checkout_blockers不为空：

| 标记 | 处理 |
| --- | --- |
| missing_stripe_key | 检查当前test模式的STRIPE_TEST_SECRET_KEY |
| missing_stripe_webhook | 检查STRIPE_TEST_WEBHOOK_SECRET及Stripe测试webhook配置 |
| missing_support_email | 填写SUPPORT_EMAIL |
| missing_public_url | 检查PUBLIC_BASE_URL |
| missing_ai_key | 检查DEEPSEEK_API_KEY |
| missing_turnstile_site_key / missing_turnstile_secret_key | 检查Turnstile对应配置 |
| missing_database | 检查现有Neon DATABASE_URL，禁止切换到临时本地库收款 |
| ai_disabled | AI_ENABLED需为1 |
| ai_daily_budget_unavailable | 当日保守费用已达到预算，不要通过删除使用量绕过；保留10元上限，等待UTC次日或先核对实际账单与记录 |
| ai_daily_request_limit_reached | 当日请求计数达到上限，默认300 |
| ai_budget_configuration_invalid | 检查人民币单价、预算和请求上限是否为有效正数 |
| queue_worker_unavailable_or_queue_full | 当前仍在队列模式，确认GENERATION_QUEUE_ENABLED=0并部署 |

这些标记可以发给支持人员，环境变量值和密钥不要截图或公开。缺失的真实密钥不能由代码自动生成。

## 最后线上测试

重新测试一个问题，确认免费初判返回；使用Stripe测试卡完成测试checkout，确认付款回跳、付费三段生成、刷新不重复收费/生成、PDF仅导出已生成内容。模型文案仍需人工看依据和是否编造现实情况。成功后再另行切换Stripe live密钥、live webhook及STRIPE_MODE，移除私密测试密码；这些切换不会由本包自动执行。

全站人民币预算默认10元/UTC日；收费币种仍为AUD、单次199分。两者互不改变。本地验收账本与线上账本独立，不要并行消耗各自额度。真实模型续测步骤见LIVE_ACCEPTANCE_ZH.md。
