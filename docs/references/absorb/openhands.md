# 吸收笔记：OpenHands（新版 Agent Canvas 前端：事件流契约）

> 前置结论：本仓库是新版 OpenHands 前端（React/TS），Agent 循环/沙箱在 software-agent-sdk 仓（AGENTS.md:32-37 分工表）。但本仓库完整保留 Agent Server 的**事件流契约**——恰是 Harness 设计的最佳横切面。

## 1. 提示词
- 系统提示建模为事件：SystemPromptEvent{system_prompt, tools, dynamic_context}（src/types/agent-server/core/events/system-event.ts:5-26）；dynamic_context 运行时注入（日期/skills/secrets）与静态提示分离
- 分层 AGENTS.md + .agents/skills/*/SKILL.md（8 个），SKILL 用 frontmatter description 做触发路由；Agent 经 InvokeSkillAction{name} 按名加载；settings 有 disabled_skills/enabled_skills 双表（settings.ts:156-163）

## 2. 流程
- 事件即状态：OpenHandsEvent 联合 = Action/Message/Observation/UserReject/AgentError/SystemPrompt/Condensation*/ConversationStateUpdate/Pause/HookExecution/StreamingDelta（core/openhands-event.ts:25-46）；来源四分 source: agent|user|environment|hook（common.ts:56）
- 状态机：ExecutionStatus = idle|running|paused|waiting_for_confirmation|finished|error|stuck（common.ts:67-75），经 ConversationStateUpdateEvent 流式更新
- ActionEvent 携带 thought/tool_call_id/llm_response_id（并行分组）/security_risk/critic_result（action-event.ts:11-72）；失败路径 AgentErrorEvent + stuck + bash 软超时（exit_code=-1 仍在跑，可发 C-c/reset，action.ts:29-46）

## 3. 工具（ACI）
- 动作/反馈成对同构：Action 27 种 vs Observation 17 种一一对应；Observation 统一 content + is_error + 结构化元数据（exit_code/timeout/truncated≤100 文件/file editor 的 old/new_content）
- 终端持久会话（is_input/reset/timeout）；编辑器 str_replace 范式含 undo_edit；内置 TaskTrackerAction（todo/in_progress/done 看板）——与我们看板同构；子代理 TaskAction{prompt,subagent_type,resume}
- 沙箱：每会话独立工作目录 workspace/project/<hex>；子会话 isolation 参数

## 4. 记忆
压缩是事件化一等公民：CondensationRequest → Condensation(forgotten_event_ids, summary, summary_offset) → CondensationSummaryEvent（condensation-event.ts:5-52）；settings 有 enable_default_condenser/condenser_max_size

## 5. 护栏
- 确认模式：confirmation_mode + security_analyzer → waiting_for_confirmation → 用户拒绝产生 UserRejectObservation{rejection_reason, action_id} 回喂 LLM
- LLM 自评 security_risk: UNKNOWN/LOW/MEDIUM/HIGH 存于每个 ActionEvent（common.ts:59-64）
- Hook 护栏：HookEventType = PreToolUse|PostToolUse|UserPromptSubmit|SessionStart|SessionEnd|Stop，事件含 blocked/reason/exit_code/stdout——hook 可拦截动作并给理由（hook-execution-event.ts:6-12,44-59）
- 密钥隔离：RequestSecretAction{name,reason} 只传名字，"the value never passes through the agent"；预算护栏 max_budget_per_task

## 6. 可移植清单
1. 事件即契约：动作/反馈定义成同构类型对（ActionKind+payload ↔ ObservationKind+is_error+metadata）→ 脚本族输入/输出 schema 与看板事件流
2. 状态机七态 + stuck 兜底与软超时（exit_code=-1 可恢复）→ 收件箱任务状态机
3. 压缩三件套（forgotten_ids+summary+offset）→ 会话记忆压缩
4. Hook 六类型 + blocked/reason 事件 → Pre/PostToolUse Hook 与执行留痕
5. TaskTracker 看板工具（view/plan + TaskItem{title,notes,status}）→ 让 Agent 自主维护看板数据
6. 确认+密钥隔离：拒绝回喂 rejection_reason 作为观察事件；密钥只报名不传值 → Hook 密钥注入与人工确认
