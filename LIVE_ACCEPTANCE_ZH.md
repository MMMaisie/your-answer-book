# 真实 DeepSeek 验收（v49.8.1）

## 测的是什么

脚本tools/live_acceptance.py直接复用网站的simple_reading初判、检索、事实校验、复核、文案及翻译代码。默认12个话题×3种盘面，共36个组合，可选少量先试；顺序先覆盖不同话题再换盘。固定起卦时间2026-11-22 11:40北京时间，便于重现，不是当前时刻预测。不同盘面不意味着已覆盖全部六爻条件，更不能证明解释准确。

脚本不导入Web应用，不访问Neon，不修改已有卦、免费额度或付款，不发起Stripe支付，不启动队列，也不执行额外联网搜索。它验证真实模型与解读程序的配合；浏览器、Worker、Stripe、PDF和线上Neon须另外验收。

## 在哪里执行

在已配置DEEPSEEK_API_KEY和项目依赖的服务器Shell、或你的本地项目目录运行。密钥只读环境变量，不写进脚本、Git或聊天。模型名与费用预留参数沿用环境变量（DEEPSEEK_MODEL、DEEPSEEK_WRITER_MODEL、DEEPSEEK_NARRATOR_MODEL、AI_PRO_*、AI_FLASH_*、BUDGET_AUD_PER_USD）。不自动读取.env文件。若在本机，需先安装requirements.txt并在本机安全配置环境变量；Render环境变量不会自动出现在本机。

## 1. 先预览（绝不调用API）

python tools/live_acceptance.py --limit 3

预览列出准备测试的问题、盘面、模型及费率预留参数，不需要密钥，不创建报告。

## 2. 先测一个问题（会产生API费用）

python tools/live_acceptance.py --execute --budget-aud 2 --limit 1 --topic marriage --scenario static --save-responses

--execute才调用真实模型；必须同时指定--budget-aud，表示这一次脚本执行的保守费用预留上限。默认最多1个组合，每组合通常3次模型请求（初判、复核、文案），失败修复可能增加请求。每个阶段最多2次，沿用网站设置。--english追加英文翻译。

预算不是准确账单：按UTF-8输入字节+额外开销、请求输出上限、配置费率及汇率保守预留；调用报错也不退预留，避免超时实际已计费却误认为免费。费率必须不低于账户实际计费水平，脚本无法向DeepSeek账户强制设置消费硬上限。保留费用预留不是实际花掉同样金额。A$2可能不足一个完整流程，遇到budget_stopped不是生成格式失败；不要无意识重复运行或自动提高预算。

此测试预算独立于网站AI_DAILY_BUDGET_AUD，不读写网站使用量。若两个同时运行，实际账户总消耗是两者合计。

## 3. 换话题/盘面（先自行确定预算，再执行）

预览3种问法：
python tools/live_acceptance.py --limit 3 --topic marriage --topic offer --topic house

指定一个话题的三种盘面：
python tools/live_acceptance.py --topic marriage --limit 3

加--execute及明确的--budget-aud才实际运行；加--english同时验收翻译。--limit最大可选36；超过组合总量只运行实际组合。再次运行会从头调用，报告不是断点续跑，不自动重复通过的结果以外的任务。

## 输出文件

控制台只显示报告路径、调用次数和预留费用。每次新建acceptance-reports/时间-随机编号/私有目录，不覆盖旧报告：

- plan.json：程序版本、模型、问题、盘面、费率和预算参数。
- summary.csv / summary.json：逐项通过、失败、预算停止、失败阶段、detail、耗时及调用次数；未运行数量单独记录。
- calls.json：每次真实请求的阶段、输出上限、结束原因、实际返回token用量和预留额；API无usage时值为null，不伪造用量。
- *-chart.json / *-output.json：完整测试卦盘和已完成阶段结果，失败不会丢掉前面已保存的结果。
- response-*.json：仅加--save-responses时保存模型最终content，便于定位不符合格式的真实返回。不保存隐藏思考文本、请求头或原始SDK报错。

输出属于测试资料，不要公开或提交Git；默认目录已加入.gitignore。--out可改父目录。Render临时文件可能因重启丢失，运行后及时下载保存报告。本脚本不会自动上传报告。

退出码0表示所有选定组合通过程序校验；退出码2表示失败、预算停止或配置错误。protocol_passed只代表程序链路通过，quality_review始终pending，必须人工评审。

## 人工验收标准

逐项看：是否直接回答原问题；依据是否对应本盘并综合主要因素；未受克制是否被误写成支持；有无编造现实经历；免费是否判断加关键点；付费是否三段有不同信息、专业词少而有解释；英文是否忠实。记录合格、需改写、不合格及理由。不能只看退出码或让模型自评就认定准确。

## 本次交付状态

仅交付并测试脚本，未执行真实DeepSeek调用，未产生API费用。自动测试使用模拟提供方验证dry-run、预算停止、错误脱敏、各阶段保存、token记录和报告隔离。排队版部署步骤仍按README，Stripe仍由你最后测试后手动切换。
