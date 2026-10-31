# 吸收笔记：autogen（v0.4 AgentChat 多智能体运行时）

## 1. 提示词
AgentChat 角色：packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py（system_message 参数）与 _base_chat_agent.py 抽象（on_messages 契约）；Magentic-One 编排提示词在 teams/_group_chat/_magentic-one/_prompts.py（Orchestrator 进度计划/反思提示）

## 2. 流程
消息传递：teams/_group_chat/_base_group_chat.py——agent runtime 循环分发消息，run(:247)/run_stream(:351) 异步消息流；团队四族：RoundRobin、Selector（_selector_group_chat.py，LLM/函数选下个发言者）、Swarm（handoff）、DiGraph（_graph/_digraph_group_chat.py，DAG 拓扑调度）。终止：conditions/_terminations.py 12 种可组合条件（MaxMessage/TokenUsage/Handoff/Timeout/External/SourceMatch 等，各配 Config+Component 支持 YAML 序列化）。断点：save_state(:748)/load_state(:798) 全队状态序列化，支持 pause/resume

## 3. 工具
tools/_task_runner_tool.py 把 Team/Agent 包装为工具（嵌套多智能体）；工具调用经 autogen-core BaseTool

## 4. 记忆
团队级 save_state/load_state + state/_states.py（消息历史存为 Mapping）；无持久化仓库地图，依赖外部模型记忆

## 5. 护栏
每条件/组件双模型（Pydantic Config 校验）；tests 巨量（test_group_chat.py 82KB、test_termination_condition.py）；_base_group_chat_manager.py 集中校验发言合法性

## 6. 可移植清单
① 12 种终止条件组合器（_terminations.py）→ 我们状态机的出边/超时/人工确认（ExternalTermination→收件箱手动放行）；② save/load_state 序列化→任务断点续跑；③ Selector/Swarm/DiGraph 三种路由→看板任务分派模式；④ Team-as-Tool 嵌套→子智能体封装；⑤ 组件 Config 双模型→配置校验规范

## 7. 知识库/技能清单
无内置知识库；packages/autogen-ext 提供 Mem0/ChromaDB 等记忆扩展与代码执行器；magentic-one 内置网页/文件技能集；agbench、autogen-studio 为运行时 UI 与评测
