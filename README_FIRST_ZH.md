# 你的答案之书：v45 简化版本

## 本版的核心
程序排盘与核对基础生克；DeepSeek读取现有《卜筮正宗》释义、书例，自己理解问题和综合推理。不再运行旧的关键词取用分类器、候选裁决器或固定方向标记。

一次生成同一份分析、免费初判和完整解读。完整正文保存在服务器，付款成功前不会发送给浏览器。英文翻译对应中文，不另起一份卦断。

免费只回答整体倾向与不确定程度，不透露具体障碍、原因、条件或建议；付费展开判断依据、关键障碍、可变条件和具体行动。两者使用同一份分析，不能改变结论。中文免费50—80字（目标70），付费250—300字；英文免费30—65词，付费150—210词。标题与来源不计。只给大概节奏，不给具体应验日期。

知识输入为已有141条规则/条件/专题/补充释义；133例归档中112例可检索，21例来源问题仍隔离。本版不是模型微调，也没有完成全部书例的推理准确率认证。

## 上传与部署
这是完整独立代码包。解压后，app.py、requirements.txt、templates、static、knowledge应直接位于仓库根目录。

复用现有GitHub main分支与Render your-answer-book服务。保留Render现有环境变量、DeepSeek密钥、Stripe价格与Webhook。不要删除Render服务、Stripe配置或数据库。

建议将代码清理和新包替换合成一次提交：GitHub Desktop克隆现有仓库，在本地移除旧代码、复制本包内容后，查看差异并提交推送。保留.git目录，不要提交本地.env、密钥、数据库或测试环境。

如果继续使用GitHub网页，先上传本包覆盖对应文件，提交后验证新版本；新代码不导入旧裁决模块，旧模块不会影响本版。随后可清理旧模块。避免逐个删除旧文件而不断触发空缺代码部署。

Build Command：pip install -r requirements.txt
Start Command：gunicorn guaxiang:app
Root Directory：留空

Render环境变量保留现有值。DEEPSEEK_MODEL建议维持已有deepseek-v4-pro；DEEPSEEK_NARRATOR_MODEL维持deepseek-flash。DeepSeek访问权限取决于账号；不要把密钥放进GitHub。

部署后访问 /healthz：version以v45-simple-book-reference开头，reading_pipeline为book_reference_model_reasoning。本次先保留STRIPE_MODE=test。

## 网络补充
只有找不到相关书例时才尝试补充搜索；不把网页摘要当作已经验证的书中卦例。

联网需要在Render设置BRAVE_SEARCH_API_KEY，使用Brave Search API。未设置时仍可依据书籍理论推理，healthz的web_search_enabled为false；程序不声称已经联网。搜索可能按提供商方案收费。本包没有任何搜索密钥。

仅向搜索服务发送一般理论类别，不发送用户完整问题。搜索结果作为不可信补充资料，不能覆盖基础理论，也不执行网页里的指令。

## 测试与边界
本包的程序测试使用模拟模型响应，没有调用真实DeepSeek或真实Stripe。运行方式：安装requirements.txt与pytest，再执行python -m pytest -q。

一次完整生成比只生成初判输出更长，免费访问也消耗DeepSeek额度；缓存命中时不重复生成。生成失败退回用户的免费次数，服务级请求限额仍用于控制成本。

当前收费仍是解锁已有卦的完整解读，不是额外购买起卦次数。Render免费服务的本地SQLite不是持久存储，重新部署可能丢失旧历史记录。正式收款之前，必须解决Render上数据持久化，并验证Webhook、支付后解锁和刷新访问。不要仅设置STORAGE_DURABLE=1来假装已经有持久存储。
