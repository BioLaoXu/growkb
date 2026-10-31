# 吸收笔记：SWE-agent（ACI 接口设计范式）

## 1. 提示词
- ACI 接口提示集中在 YAML 配置而非代码：config/default.yaml（system/instance/next_step 模板+工具 bundle 声明 L33-66）；config/bash_only.yaml L5-19 定义 REPL 约束："You must issue exactly ONE command at a time... exactly ONE bash code block"，含正/反示例（L90-112）与"Failure to follow these rules will cause your response to be rejected"
- 编辑格式约束（tools/edit_anthropic/config.yaml L15-18）："The old_str parameter should match EXACTLY one or more consecutive lines... If not unique, the replacement will not be performed"；tools/windowed_edit_linting/config.yaml L10-17：多行编辑必须以 end_of_edit 终止、"THIS COMMAND REQUIRES PROPER INDENTATION"

## 2. 流程
- DefaultAgent step 循环（sweagent/agent/agents.py）：格式错误/blocklist/shell 语法错误统一走 handle_error_with_retry（L1088-1150），用 format_error_template 重新请求模型；特殊控制令牌 RETRY_WITH_OUTPUT_TOKEN 等（L219-221）
- 外层 RetryAgent（L257-430）：ScoreRetryLoop/ChooserRetryLoop 多次尝试+评审，成本预算跨 attempt 分摊（L307-310）

## 3. 工具
- sweagent/tools/commands.py：Command/Argument Pydantic 模型，支持多行命令（end_name 终止标记）、参数枚举、签名校验（L167-205）、OpenAI function-calling 导出（L133-165）
- sweagent/tools/bundle.py：工具以 Bundle 打包（目录+config.yaml），可 hidden_tools、可带 state_command
- 实际工具库 tools/：registry、edit_anthropic（str_replace_editor，state_command _state_anthropic）、windowed 系列、search、submit、web_browser 等 14 个 bundle

## 4. 记忆
无长期记忆；历史管理靠 sweagent/agent/history_processors.py：LastNObservations 截断旧观测（L85-90，"used in the original paper to elide but the last 5 observations"）、cache_control 提示缓存（L53-67）

## 5. 护栏
- 动作黑名单过滤器+filter.blocklist_error_template（agents.py L1125-1129）；提交自审门：tools/review_on_submit_m/ 提交时强制复跑复现脚本、回滚测试文件改动（config/default.yaml L47-63）；成本/步数限额（agents.py L336-339）；评审循环打分（agent/reviewer.py）

## 6. 可移植清单
① Command/Argument 强校验 schema（签名↔参数一致性检查）→ 脚本族命令封装（commands.py L167-205）
② str_replace 唯一匹配编辑协议 → 看板 agent 的编辑工具规范（edit_anthropic/config.yaml）
③ Hook 抽象基类（on_run_start/on_step_done/on_model_query 等 13 个钩子）→ 工作空间 Hook 层（agent/hooks/abstract.py L10-53）
④ 格式错误→带模板重问→多次熔断 → 脚本族状态机（agents.py L1088-1150）
⑤ YAML 声明式系统/实例模板+Bundle 工具包 → MEMEX 旁的配置化提示词库（config/*.yaml）

## 7. 知识库/技能清单
无自带领域知识库。知识以"配置模板"组织：config/（default、bash_only、多模态、benchmark 变体）、tools/ bundle 即"技能包"、docs/（mkdocs，含 usage/config/dev）。依赖外部：SWE-bench 类数据集、trajectories/ 轨迹库、tests/ 作评测
