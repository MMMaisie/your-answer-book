v49.4.2 付费复核表达检查边界修复
适用已部署v49.4或v49.4.1，包含v49.4.1长度重试修复。
复制包内文件到原项目，替换同名文件；保留.git和其余项目文件。Commit、Push后等待部署。
无需修改环境变量或数据库。健康版本前缀：v49.4.2-review-boundary-

本次日志 stage=review reason=editorial 说明内部复核被表达检查拒绝。
旧日志没有具体规则，不能证明实际触发项。
本补丁将内部复核摘要的术语数量和跨字段重复句检查交给最终正文编辑阶段；
保留内部事实、关系、时间、引用、无依据人物推断检查。
公开revised_free仍受免费文案规则约束；最终付费正文仍保留术语数量、重复句和字数检查。
不强行放行错误事实，不使用假解读兜底。

新增日志detail白名单代码：
preview_jargon / review_preview_jargon：公开初判包含术语。
paid_jargon：最终正文术语过多。
repetition / review_preview_repetition：重复句。
personal_inference / review_preview_personal_inference：无依据个人状况推断。
unspecified：其他未分类表达错误。
表达校验失败时finish_reason现在正确记为stop；之前unknown不是模型结束状态。

本地461项回归测试通过，Gunicorn启动和12个中英文页面HTTP检查通过。
未执行真实DeepSeek调用，无法保证本次实际响应将通过所有校验。
付款授权仍有效；从同一卦的私密链接重试生成，不要重新付款或重新起卦。
若仍失败，提供新日志完整一行，含stage/reason/finish_reason/detail。
