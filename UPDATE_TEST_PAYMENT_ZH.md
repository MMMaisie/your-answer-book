# Stripe 测试付款更新

这次只改付款测试与请求超时，未修改解卦内容和数据表结构，不包含任何密钥。

上传到 GitHub MMMaisie/your-answer-book：
- app.py 覆盖仓库根目录同名文件。
- templates/reading.html 覆盖 templates 文件夹内同名文件。
- gunicorn.conf.py 新增到仓库根目录。
无需删除其他文件。不要把整个 stripe-test-update 文件夹作为子目录上传。

Render 新增 STRIPE_MODE=test。保留原来的正式 Stripe 变量和 STORAGE_DURABLE=0。
已有 STRIPE_TEST_SECRET_KEY 和 STRIPE_TEST_PRICE_ID 应来自同一个 Stripe 测试环境。

Stripe 测试模式下创建付款通知（Webhook）目标：
https://your-answer-book.onrender.com/stripe/webhook
选择 checkout.session.completed 和 checkout.session.async_payment_succeeded。
将通知签名密钥存入 Render 的 STRIPE_TEST_WEBHOOK_SECRET，完整密钥不要发到聊天或提交到 GitHub。
签名密钥未设置时，付款按钮继续关闭。

代码上传到 main 后等待 Render 部署成功。原启动命令 gunicorn guaxiang:app 会读取根目录的 gunicorn.conf.py，将超时延长到 120 秒。
重新起卦后，在解读页确认测试付款提示，付款页确认 Test mode，使用 Stripe 测试卡完成模拟付款。
实际 AI 生成仍会消耗 DeepSeek 用量；测试付款不会扣取真实款项。

本地 46 项测试通过，包含模拟 Checkout、返回后解锁、完整解读生成、重复通知、测试/正式记录隔离。尚未执行线上 Stripe 端到端测试。
测试存储可在部署/重启后丢失。正式收费仍需持久存储；不要为了开放真实付款把 STORAGE_DURABLE 虚设为 1。
