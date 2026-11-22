v49.4.4 私密测试取消用量限制
包含v49.4.1至v49.4.3修复，适用于已部署v49.4及后续补丁。
将本包文件复制到原your-answer-book，替换同名文件。保留.git和其余文件。
Commit、Push，等待Render部署。
健康版本前缀：v49.4.4-unlimited-private-test-

现有配置 PRIVATE_TEST_UNLIMITED=1、STRIPE_MODE=test、SITE_ACCESS_PASSWORD已设置；
使用tester用户名和正确密码登录后，即取消：
免费次数、操作间隔、AI日预算、每日调用次数、全站AI并发上限、联网日调用次数。
无需提高AI_DAILY_BUDGET_AUD或清除旧数据库记录。
测试调用仍记录使用量；测试调用reserve=0表示不参与费用保护预留，绝非API免费。
真实API请求仍会计费，此测试模式不设应用内日费用上限。

保留身份认证、CSRF、Turnstile、付款授权、模型输出和事实校验。
AI_ENABLED=0总开关仍可停用服务。模型输出长度和有限修正重试仍保留。
同一卦生成锁保留，防止连点重复启动；这不是全站并发限制。

取消PRIVATE_TEST_UNLIMITED或改成STRIPE_MODE=live后自动恢复普通用量限制。
未认证、密码错误、正式支付模式均不能跳过限制。
普通请求的费用上限与操作频繁提示已分开。
本次未实施普通模式按实际账单结算，普通模式仍保守预留。

验证：478项本地模拟回归通过；Gunicorn启动和12个中英文页面HTTP检查通过。
未调用真实DeepSeek、未花费API费用、未操作Render账户。
部署后从同一付费卦重试，无需再次付款。
本补丁取消用量阻挡，不保证尚未验收的真实模型文案必然通过。
