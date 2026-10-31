# v49.2 私密测试与防误触补丁

包含 v49.1 内容修正，无须先重复安装 v49.1。基于 v49 或 v49.1 覆盖同名文件即可；不要删除其他文件，不替换数据库或密钥。

1. 解压本包，内容复制到现有仓库根目录，替换同名文件。
2. GitHub Desktop Commit，再 Push；等 Render Live。
3. Render → your-answer-book → Environment → Add Environment Variable：
   名称 PRIVATE_TEST_UNLIMITED
   值 1
4. 保持 STRIPE_MODE=test，保留已有 SITE_ACCESS_PASSWORD。使用 tester 和你自己的访问密码登录。
5. 保存并部署后，页面会出现“私密测试：免费次数和操作间隔限制已关闭；费用安全上限仍生效。”
6. /healthz 的 version 应以 v49.2-private-test-progressive-rate- 开头，private_test_unlimited 为 true。

私密测试开关仅对通过网站 Basic Auth 的请求生效，且必须 Stripe 为 test。不带访问密码、密码错误、开关为0或切 live 时均不能绕过。只设置 Stripe=test 不会绕过配额。Turnstile真人验证、CSRF、字数、费用安全上限、模型并发及同卦生成锁仍保留。Stripe 沙盒付款仍是必需步骤，开关不解锁付费内容。

测试的 AI 调用仍真实消耗余额，保留 AI_DAILY_BUDGET_AUD=2、AI_DAILY_REQUEST_LIMIT=40、AI_MAX_CONCURRENT=2 等现有设置；它们是全站费用和并发保护，不是每日免费次数。若费用安全额度耗尽，仍会暂停调用。

正式开放前，把 PRIVATE_TEST_UNLIMITED 改为0或删除并部署；准备好正式付款配置后再切 live。正常访客仍为浏览器每天1次、同IP每天最多2次免费，两者同时满足。

普通访问的频率规则：新问题及发起付款间隔30秒；第一次误触只等本轮剩余时间；10分钟内连续违规累计5次才升级15分钟，长拦截期间不会继续延长。代付请求和外网网络切换仍需实际验证，不保证所有异常流量都能识别。

付费生成不再套通用操作冷却；同卦生成锁防止并行重复调用，遇到正在生成时显示处理提示和刷新链接。已经保存的全文仍直接返回。免费翻译保持短频率保护。GET查看、历史页、PDF不走生成频率规则。所有POST按钮提交后禁用，浏览器后退恢复时重置按钮。

数据库仅新增一个短期违规计数表，不改旧记录和订单；旧频率记录保留。私密测试绕过旧冷却，关闭测试开关后尚未到期的旧拦截仍可能短暂生效。

本包自动测试390项通过，JavaScript语法检查通过。未调用真实DeepSeek、未操作你的Render账户、未重复执行Stripe测试付款；浏览器按钮行为及真实公网流量需部署后验证。
