v49.4.1 初判响应未完成修复（基于已部署v49.4）

将包内文件复制到现有 your-answer-book 文件夹，选择替换同名文件。
保留 .git、环境变量和其他文件，不要清空整个项目。
GitHub Desktop Commit 后 Push，等待 Render 部署。
/healthz version 应以 v49.4.1-completion-retry- 开头。无需改数据库或环境变量。

修复：
1. 日志 incomplete 新增经过白名单过滤的 finish_reason，不输出模型内容。
2. 仅首次 finish_reason=length 时重试一次，输出上限从4096升至8192（writer/translation从2048至4096）。
3. 丢弃不完整片段，重新请求完整紧凑JSON，不拼接或展示半截解读。
4. 每个阶段总共最多2次调用，包含JSON/事实/文案修正；预算和并发保护仍生效。
5. 缩短初判内部分析要求，只核对实际用到的关键事实；所有事实检查和免费50字/付费300字限制保持。

限制：
现有日志无法确认具体结束原因，本补丁针对长度截断并改进诊断。
自动重试可能新增一次API费用及预算预留，未提高日预算。
已完成455项本地模拟/回归测试及Gunicorn启动、12个中英文页面HTTP检查。
未调用真实DeepSeek API，真实模型验收需部署后再试。
若仍失败，提供 Reading operation failed 所在一行，含stage/reason/finish_reason。
