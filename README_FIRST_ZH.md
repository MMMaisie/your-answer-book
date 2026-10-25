# 你的答案之书 v48 — 完整代码与 Windows 安装包

这是一份应用代码包，不是模型权重或“训练完毕”的模型。Codex 编写、修改并执行了程序测试；网站以 DeepSeek Pro 进行解卦、Flash 翻译。模型参数按照当前官方接口实现。API密钥、Stripe、邮箱、人机验证必须由运营者配置，包内不含任何真实凭据。

## 本次交付的边界

- 中文免费正文 ≤50字符；中文付费正文 ≤300字符。
- 英文免费正文 ≤60个英文词；英文付费正文 ≤350个英文词。
- 中文按去空白后的字符数计，标点、数字、英文字符均计入；英文按单词识别计，带内部连字符/撇号的单词算一个。固定页面标题和按钮不是解读正文；不会额外附加无限长的模型来源说明。
- 没有之前250字等苛刻最低长度；提示词要求付费具体解释依据、障碍、条件、行动，目标230–270中文字符。输出超限会有且只有一次修正机会，不直接截断，不无限重试，不用模板冒充成功。
- 免费只生成简短初判及内部依据简记，返回值里剔除任何意外生成的paid字段，不生成或保存付费全文。扣取/预留购买次数后才另行调用模型生成全文。
- 中文判断为唯一来源，英文翻译中文，不能另起一份卦断。付款后中文成功即计为已交付；若英文翻译失败，中文仍可读，翻译可重试且不另扣解读次数，仍受AI总预算保护。
- 本次没有使用真实DeepSeek、SMTP、Turnstile或Stripe账户凭据，未执行真实模型/邮件/支付验收。TEST_STATUS.json列明实际检查，不能以单元测试通过宣称预测准确或“任何问题都不会发生”。

## 商业规则

全部价格为澳币AUD，一次性付款，无自动续费：

| 方案 | 价格 |
|---|---:|
| 1次完整解读 | A$1.99 |
| 5次包 | A$5.99 |
| 10次包 | A$9.99 |

- 游客按IP加浏览器领取一次免费初判；验证邮箱的账号领取一次。游客已领后在同一浏览器注册不会再赠送。
- 永久领取标记依赖数据库和稳定的FLASK_SECRET_KEY。不能把IP当作一个人：共享网络会误伤，更换网络/浏览器、批量邮箱仍可能绕过；验证码、账号、速率和全站预算一起兜底。
- 一次余额对应一个问题的完整解读，中英共用；次数不自动到期。一次免费体验只给初判，不送全文。
- 免费额度用完后，新问题需要余额，提交时会预留一次，生成成功后扣次。已有免费卦也可用一次余额展开全文。刷新已生成页面不扣次、不调用模型。
- 同一问题、同一卦、同一时间和时区重复提交复用缓存；切换界面语言不会另扣一次。
- 多窗口/并发使用服务器锁和余额预留；失败释放预留次数。意外中断的预留在超时并确认无活动任务后恢复，已生成正文则补记已用次数，避免免费交付或重复扣次。

## 已移除的旧限制

代码已删除每账号/浏览器每日3次新增问题、每IP每日12次操作、每账号每日5次未缓存完整生成/付费翻译的旧限额。FREE_DAILY_LIMIT、IP_DAILY_LIMIT、GLOBAL_DAILY_LIMIT、PAID_DAILY_LIMIT旧环境变量不再被代码读取。

保留永久免费领取资格、同IP每小时6次新问题/6次全文提交、验证码、并发防重、余额预留，以及全站API请求和预算保护。这些是明确的新防刷措施，不是额外的付费日配额；达到速率后稍后再试，余额不清空。

## 1. 旧密钥和旧仓库

先在DeepSeek撤销旧Key；只删GitHub文件不能删除Git历史中的秘密。新Key只粘贴到Render环境变量，不发聊天，不放源代码、截图、Build/Start命令或ZIP。

如果担心旧Git历史含密钥，推荐新建 PRIVATE 空仓库并上传本包全部内容，再把现有Render服务关联到该仓库。不要删除原Render服务、数据库或Stripe配置。新仓库不会清除已经传播的秘密，旧Key仍必须撤销。

若保留原仓库：先下载ZIP备份至自己电脑；使用GitHub Desktop克隆，保留.git，删除其余旧代码，把本包内容复制进去，把删除与新增一次提交推送。不要在GitHub网页逐个删除、逐次部署。不需要把所有旧版本补丁混进新包。

文件必须位于仓库根：app.py、guaxiang.py、requirements.txt、templates/、static/、knowledge/。不要再套一个外层目录。不要上传.env、数据库、.local-secret、.venv、acceptance.json或真实凭据。本包已排除这些文件。

## 2. Render 先私密测试，不新建服务

保留现有 your-answer-book 服务与Stripe测试配置。Environment是该服务的配置页，不需要重新创建项目环境，也不要把旧环境变量全部删掉。

构建命令：pip install -r requirements.txt
启动命令：gunicorn guaxiang:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180
Root Directory：留空。

先配置：

| Key | 设置 |
|---|---|
| DEEPSEEK_API_KEY | 你自己粘贴的新Key |
| DEEPSEEK_MODEL | deepseek-v4-pro |
| DEEPSEEK_NARRATOR_MODEL | deepseek-flash |
| FLASK_SECRET_KEY | 保留现有稳定随机值；不要每次部署更换 |
| SITE_ACCESS_PASSWORD | 自己设置至少20位随机密码，和API Key不同 |
| ALLOW_PRIVATE_TEST_ACCOUNTS | 1，仅私密测试时 |
| STRIPE_MODE | test |
| AI_ENABLED | 1；设0可暂停新AI调用 |
| AI_DAILY_REQUEST_LIMIT | 20 |
| AI_DAILY_BUDGET_AUD | 2 |
| BUDGET_AUD_PER_USD | 2.0，保守预算折算系数，不是实时汇率 |
| SUPPORT_EMAIL | 你真实可用的客服邮箱 |
| PUBLIC_BASE_URL | 现有网站的https网址 |

Stripe测试模式继续使用已有 STRIPE_TEST_SECRET_KEY、STRIPE_TEST_WEBHOOK_SECRET。新次数包由服务器固定AUD金额创建Checkout，不需要手填三个Price ID；旧Price ID可以保留兼容历史订单。推荐使用符合所需权限的受限Stripe密钥。不要把DeepSeek密钥放入Stripe变量，或反过来。

Render修改变量后：Save only仅保存、不立即生效；Save, rebuild, and deploy才用新配置重建。等Live再测试。

浏览器会弹出网站登录框：用户名 tester，密码为SITE_ACCESS_PASSWORD，不是DeepSeek Key。私密测试+STRIPE_MODE=test+ALLOW_PRIVATE_TEST_ACCOUNTS=1时，注册账号可直接标记验证完成，以便测试，不发送邮件。公开环境不会走这条捷径。

## 3. 正式开放必须完成的配置

### 持久存储

账号、次数、付款、永久免费标记和限额都依赖数据库。Render临时磁盘会丢数据，不能直接用于正式收款。

给现有服务配置持久磁盘，挂载路径 /var/data，设置：

DB_PATH=/var/data/readings.db
PERSISTENT_DATA_DIR=/var/data
STORAGE_DURABLE=1

代码检查数据库在实际挂载的目录内，只有标志但没有挂载不能启用真实收款。磁盘路径可以自定义，但需同时修改上面变量。只支持单实例SQLite，不支持横向多实例共用本地数据库。

更改DB_PATH不会自动迁移原数据库。先用服务器端SQLite backup制作一致性备份，再复制到挂载目录，确认账号/历史/次数无误后切换；不能以新空库冒充保留原数据。不熟悉时先停在测试模式，避免误删付款记录。manage.py backup可在可信服务端Shell创建备份；不要把备份提交GitHub。

### 邮件和验证码

公开注册需要可发验证与密码重置邮件的SMTP服务，配置：
SMTP_HOST、SMTP_PORT（587 STARTTLS或465 TLS）、SMTP_USERNAME、SMTP_PASSWORD、MAIL_FROM。

密码只存加密哈希。验证链接一次使用、24小时过期，重置链接1小时过期；密码重置使旧登录失效。账号使用邮箱验证，不提供邮箱供应商；需要你使用已有或自行配置的发信服务。

公开访问使用Cloudflare Turnstile：配置TURNSTILE_SITE_KEY与TURNSTILE_SECRET_KEY，并在Turnstile允许你的域名。前端site key是公开标识，secret key只能保存在Render。后台验证token和hostname；未配置则公开注册/生成拒绝服务，不悄悄跳过验证。验证码不保证挡住所有自动化或人工滥用。

在确认SMTP、验证码和真实付款验收通过后，移除 SITE_ACCESS_PASSWORD，设置 ALLOW_PRIVATE_TEST_ACCOUNTS=0，才开放网站。不要把私密测试密码分发给真实客户。

### 真实收款

先完成Stripe测试Checkout、回调、余额到账、生成与刷新。确认Stripe账户业务信息与收款资格，测试通过不代表已获真实收款资格。真实模式使用 STRIPE_SECRET_KEY、STRIPE_WEBHOOK_SECRET；设置STRIPE_MODE=live。保持测试和正式Webhook密钥分开。

Webhook URL：网站网址/stripe/webhook
必须启用：checkout.session.completed、checkout.session.async_payment_succeeded、charge.refunded、charge.dispute.created。

服务端验证签名、模式、订单所属账号、金额、AUD币种、支付状态；重放回调不重复加次数。回调先于订单落库时返回503让Stripe重试，不能仅凭浏览器success页面发货。退款/拒付会撤回对应次数，事件乱序也不会重新发放。已用后退款可能出现负余额，阻止继续消耗；争议撤销/胜诉后恢复余额需运营者核对后人工调整。

真实Checkout发起前检查DeepSeek账户余额可用；服务暂停时不发起新增订单。但外部服务仍可能在付款之后故障，不能保证“付款成功=AI永远可用”。未使用包7天内可申请退款；部分使用和服务故障人工核对，不限制适用消费者权利。税务、商户资料、客服及退款由你运营；不要未经确认启用自动税收功能。

## 4. 成本与密钥保护的实际边界

- 每个真实API请求先原子计数：免费、付费、翻译、修正、失败都计入。默认20次/UTC日；默认保守预算预留A$2/UTC日。并发不能绕过预留。
- 预算按当前官方峰值模型费率、输入UTF8字节保守估算、不假定缓存折扣，并使用人工配置的USD→AUD安全系数；失败也不退回预留预算。它不是DeepSeek账户级的澳币硬预算，价格、汇率、分词规则变化需要复核；不能限制持有泄露Key的人绕过网站直接调用API。
- 限制输入大小、输出tokens、模型白名单、同时生成和请求速率。普通生成阶段最多2次模型请求（含一次修正）；如已有书例但模型请求联网补充，可再进行一个最多2次请求的免费修订阶段，之后停止，不循环搜索。翻译每次最多2次请求。
- 案例不足时可用DeepSeek官方Search API检索补充，不需要Brave Key。默认开启WEB_SEARCH_ENABLED=1，WEB_SEARCH_DAILY_LIMIT=5；最多每个免费判断流程发起一次搜索，结果缓存24小时（失败短暂缓存）。搜索也计入全站20次调用和保守预算，按官方每次US$0.00075预留，再按安全折算系数转换。调整价格前需核对官方。
- 搜索词只由通用理论主题组成，不上传原问题、人名、日期、联系方式或用户IP。不执行网页中的指令，网络资料标为未核实；不能覆盖程序排盘、时间转换、五行生克。模型会比较书例是否适用，主题相同不等于条件相同。网页不可用时可以继续基于书中基础推理，不伪造检索成功或永久学习。
- 账号/密钥轮换、换库、清空数据会影响会话或额度。数据库丢失会破坏所有持久限制；正式环境必须备份持久数据。
- Key只在服务器读取，不传HTML/JS/健康检查，不保存到安装包。但Render/GitHub管理员、恶意服务端代码或入侵的服务器仍可能读环境变量。你必须检查团队成员、协作者、已连接应用与异常登录，并启用账户双重验证。不能保证“Render里绝不可能泄露”。
- 当前代码包扫描不等于审计全部Git历史或你电脑上的其他程序。
- 同一公网IP可能对应多人；VPN或移动网络变化也能绕过永久IP限制，因此IP只是辅助，不能当身份保证。Render默认可能看到代理IP，TRUST_PROXY=1只应在确认可信代理链后配置；本包没有凭空确认你的代理跳数。
- AI仍可能推理错误。141条整理规则、133例档案中112例可检索，并非已训练完整书籍；21例源字段存在问题未加入检索。程序检查已支持的基础生克与卦盘事实，但不能证明所有复杂判断或预测准确。

## 5. Windows 安装和本地检查

需要Python 3.11或更高，安装时选择可使用py启动器。

1. 解压到普通本地目录。
2. 双击 INSTALL_WINDOWS.bat 安装依赖；有错会停留，不会闪退。
3. 双击 START_LOCAL.bat，隐藏输入新Key及私密测试网站密码；Key只在当前进程环境中，不生成.env。
4. 浏览器打开 http://127.0.0.1:5000 ，用户名tester，密码为你设置的网站密码。

本地入口只监听127.0.0.1，不公开到互联网。GUI可查看但没有真实Key无法生成AI；没有Stripe测试配置不能模拟实际付款到账。

TEST_REAL_MODEL.bat是可选的真实模型验收：先明确输入TEST，再隐藏输入Key；最多8次API调用，输出acceptance.json，只包含固定公开测试问题的结果和统计，不保存Key。此工具会消耗你的DeepSeek余额，不会发起Stripe付款；本次交付未替你执行它。已有网站和本地测试建议分开Key。

程序测试：python -m pip install -r requirements.txt pytest；python -m pytest -q。

## 6. 部署后的验收顺序

1. /healthz 的 version 以 v48-web-reference-no-legacy-caps- 开头；generation_mode=paid_deferred，output_limits是50/300/60/350。
2. 未输入网站密码不能访问首页。用tester进入；建立私密测试账号并登录。
3. 免费生成一次，只看到短初判，页面刷新不重复调用；第二次游客同IP不能免费领取。
4. 同一卦英文翻译，不增加新的卦或扣次数。
5. Stripe测试购买1次或次数包，核对AUD金额与到账次数。
6. 使用一次余额生成全文，检查方向与初判一致；刷新/重复点击不重复扣次。
7. 检查邮件验证、密码重置、验证码、持久存储；在手机与电脑分别测试布局。
8. 再切换真实收款和公开访问，先用低全站预算观察。不要直接把测试模式标志当作已完成真实收款验收。

CLI维护：在可信服务端Shell中运行python manage.py audit/backup/recover。人工补次：python manage.py grant --email 用户邮箱 --credits 数量 --reason 核对原因；它只改余额、不发起付款。不要分享Shell权限或数据库备份。

## 管理员读取环境变量是什么意思

普通访客不能通过页面、JS或健康检查拿到API Key。有Render后台管理/环境变量查看权限的人，或者能进入服务器Shell的人，可以查看或使用服务端环境变量；被授权运行的服务器程序也能读取。环境变量能避免密钥进入前端和代码仓库，但不能防拥有管理权限的人，也不能防服务器被入侵。

只给你本人保留管理权限，审查协作者与连接应用，启用账户双重验证。新Key只放Render，不发聊天或截图。代码没有加入密钥展示页面，但这不等于已审计你Render账号的所有权限。

备份方面：本包仍提供手动一致性数据库备份，没有代你创建每日自动备份和异地存储。免费临时磁盘上的数据库和同盘备份都可能随重启一起丢失，因此不能把“有备份命令”当作“商业数据已得到持久保护”。
