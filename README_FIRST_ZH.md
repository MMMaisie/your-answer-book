# v49：防刷、Neon临时存储、书籍依据与案例检索

本包替换 v48.2 的运行程序，沿用原页面、排盘与书籍数据。尚未代你连接 Neon、部署 Render 或使用真实 DeepSeek／Stripe 账号验收。请保持 Stripe 测试模式与私密访问，完成下面步骤后再公开收费。

## 这次改变

- 免注册、免余额、单卦一次性 Stripe Checkout。默认 A$1.99，可通过 READING_PRICE_CENTS 修改。没有次数包或订阅。
- 免费：每浏览器每天1次、同IP每天最多2次，两项均需满足，以UTC日期计。失败释放免费预留，服务方已发生的费用仍计入预算。
- 免费额度耗尽：仍可保存卦盘并直接付款，付款前不会生成50字短评或全文。付费后才生成内部判断和正文。
- 真人验证在服务器核对成功、域名、动作和时间，并记录一次性凭证。每类新增／生成／付款动作按浏览器及IP限制60秒1次，过快进入固定15分钟冷却，继续刷新不延长冷却。正常查看缓存、下载和返回不调用模型。
- 全站预算、全站调用上限和并发控制保存到同一数据库。预算按保守上界预留，不等于实际费用；供应商调价后应更新费率上界。不能保证完全阻挡分布式真人／代理攻击。
- Neon PostgreSQL存储卦盘、初判、付款授权、全文与翻译、防刷和预算；生产环境缺 DATABASE_URL 不启动，绝不静默退回易丢失的本地数据库。
- 解读保存10天，首次确认付款给予新的10天保存期；到期立即不可访问，之后由请求触发每小时清理。无人访问时不主动唤醒服务，亦不会主动调用AI。管理员可执行 python manage.py cleanup 手动清理。
- 对账订单单独保留，只有支付标识和金额，不含问题／正文。数据库备份不属于正文清理；自动异地备份与财务保存策略尚未额外配置。
- PDF内嵌中文字库，包含问题、排盘和已经生成的当前语言文字。下载不会调用模型。未实现邮件发送，避免新增邮件服务费用。
- 保留141条规则、133例档案、112例可检索；基础规则常驻，按问题与盘面条件最多选择40条相关规则、3例匹配案例。程序不按关键词决定能不能解，也不把空破墓直接当成失败。
- 内部区分事实、取用爻位、依据编号、推测与不确定性。案例是参考，不照搬历史结果。格式／可选引用可整理，未知引用、基础关系错误、字数超限或截断仍拒绝或有限修正。最多一次修正，不无限重试。
- 免费正文中文≤50字、英文≤60词；付费中文≤300字、英文≤350词。标题不计；英文只翻译已保存中文，不另断一卦。只给大概节奏，不报具体日期。
- 保存当时的卦盘、参考材料与结果；后续更新页面不会使已交付全文失效。免费不搜索；付费必要时才尝试搜索，最多3次／全站日；搜索不可用时基于书籍条件性解释，不伪称联网。

## 部署步骤

1. 先下载／备份现有GitHub仓库。本包不会迁移旧SQLite的账号、余额、旧卦和旧订单。新数据使用独立的 ab49_ 数据表，不删除其他数据库表。如还有真实未用余额或未交付订单，请先处理，不能直接关闭旧服务。
2. 解压本包，将里面的文件放在现有仓库最外层，app.py、requirements.txt、templates、static、knowledge、fonts应在同一层。不要上传整个上级文件夹。旧 membership.py 等即使暂时残留，也不会再被 app.py 导入；旧账号路由已移除。
3. Render → your-answer-book → Environment，设置 environment.example.txt 中的变量。切勿把真实连接串、密钥写入代码、GitHub、日志或聊天。
4. DATABASE_URL：使用Neon Connect给出的完整Postgres连接串，建议池化地址，保留 sslmode=require／channel_binding=require 参数。不需要建新的Render数据库或购买磁盘。程序首次启动自动建表。
5. 配置Cloudflare Turnstile Managed组件，添加实际网站域名 your-answer-book.onrender.com（如有自定义域名一并添加）。将Site Key和Secret Key分别填 TURNSTILE_SITE_KEY、TURNSTILE_SECRET_KEY。PUBLIC_BASE_URL必须与用户访问的主域名一致。
6. 仅在Render提供一层可信反向代理且应用不能绕过该代理直连时用 TRUST_PROXY=1。本程序信任最靠近应用的一层 X-Forwarded-For；不能在任意直连服务器上盲目启用。请在上线前用不同网络核对IP额度行为。
7. 复用现有Stripe测试密钥：STRIPE_MODE=test、STRIPE_TEST_SECRET_KEY、STRIPE_TEST_WEBHOOK_SECRET。旧 PRICE_ID 不再使用；价格由服务器创建单次结账项目。推荐使用具有所需权限的受限密钥。
8. Stripe webhook目的地址保持 https://your-answer-book.onrender.com/stripe/webhook 。订阅 checkout.session.completed、checkout.session.async_payment_succeeded、charge.refunded、charge.dispute.created。成功页面不是唯一授权来源；带签名的Webhook也会独立确认付款。不要把测试签名密钥用于正式模式。
9. Render Build Command：pip install -r requirements.txt；Start Command：gunicorn app:app；Health Check Path：/healthz。项目根目录无须修改。保存环境变量并部署，等 Live。
10. 打开 /healthz，应看到 version以v49开头、database=postgresql、storage_durable=true、accounts_enabled=false、turnstile_configured=true、payment_mode=test。checkout_enabled=false 时检查支持邮箱、Stripe变量、真人验证、AI预算与密钥。

## 部署后的验收顺序

1. 保留 SITE_ACCESS_PASSWORD，Basic Auth用户名 tester。即使私密测试也不绕过真人验证。
2. 中文提一个普通问题，看免费初判是否回应倾向且不超过50字。保存私密链接，再从“我的卦”返回。
3. 同浏览器至少等60秒后提交另一卦，应显示额度用完而无初判，仍有付款入口；同IP另一个浏览器最多再获得一次免费。UTC午夜重新计次。快速刷新不同新请求应看到“操作过于频繁，请稍后再试。”
4. 进入Stripe测试结账，用Stripe测试卡 4242 4242 4242 4242、任意未来有效期与测试CVC。应返回原问题，不要求注册，不得再付款。
5. 点击生成完整解读（有真人验证）；确认中文≤300字、依据正确且与初判一致。切换英文，按按钮翻译，≤350词，不能新增结论。实际字数、依据和用语仍需人工验收。
6. 刷新／返回／PDF下载均不新增模型调用。测试生成失败后已付款权限保留。预算到顶可能暂缓生成，不会要求再次付款。
7. Render再次部署，确认原链接、付款状态与解读仍在，直到10天保存期结束。
8. 验收后才考虑移除 SITE_ACCESS_PASSWORD，并切换Stripe live及对应正式Webhook密钥。切正式前确认有效支持邮箱、供应商余额、预算费率上界与退款处理。测试付款不授予正式付款权限。

## 新旧真实模型对照测试

本包包含 compare_readings.py 和 baseline_v48.py（仅用于对照，不被网站导入）。

- python compare_readings.py ：只显示计划，不联网、不花费。
- 在本机环境变量配置密钥后，python compare_readings.py --execute --max-cases 2 --tier both --budget-aud 2 ：明确执行付费对照，最多AUD 2保守预算，亦受较低的全站预算限制；可能因预留不足提前停止并保存部分结果。
- 报告含新旧输出、倾向、引用集合、耗时、token和保守费用预留。实际账单需在供应商后台核对。默认不联网，保证同卦、同问题、同模型比较。
- 人工盲评：是否回答原问题、取用是否有依据、主要作用是否用对、是否矛盾、免费付费是否一致、有没有套话。结构测试通过不等于预测准确。
- 密钥不要写进命令参数或代码。该脚本不执行Stripe付款，也不部署。

## 本地测试

Python 3.12，pip install -r requirements.txt，另装 pytest 后运行 python -m pytest tests -q。自动测试使用模拟模型、模拟验证与Stripe签名样本，不花费模型费用。没有DATABASE_URL时本机使用新SQLite测试文件；Render上必须提供Neon。

旧的每日3次、每IP12次、每日5次付费生成等限制已不在运行代码中。保留的是本页明示的免费日额度、短时防刷和全站成本保护，不按账号或购买次数限制。
