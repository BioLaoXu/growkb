# 吸收笔记：LangGraph（状态机编排与断点续跑，D5）

## 1. 提示词
- 无内置系统提示词；唯一形态在 libs/prebuilt/chat_agent_executor.py:278 create_react_agent(model, prompt=...)——prompt 是一等参数；提示词管理交上层应用，框架只管状态流转

## 2. 流程（核心吸收点）
- StateGraph（libs/langgraph/graph/state.py，74KB）+ Pregel 引擎（pregel/_loop.py、pregel/main.py）按 superstep 推进，channel 版本号驱动增量计算
- 断点续跑：checkpointer 每 superstep 存快照（libs/checkpoint/README.md:19"save graph state at every superstep, enabling human-in-the-loop, memory between interactions, durable execution"）；thread_id+checkpoint_id 定位恢复点（README.md:33-48）；pending writes 机制：节点失败时保存同 superstep 已成功节点的写入，恢复时不重跑（README.md:57-59）
- 人工介入：interrupt() 抛可恢复异常暂停图，Command(resume=...) 恢复（types.py:833,896-909）
- 状态声明：TypedDict + reducer 注解（LastValue/BinaryOperator/Topic，channels/*.py）——并行写入合并策略显式化

## 3. 工具
- ToolNode（libs/prebuilt/tool_node.py:630）统一执行工具调用、支持状态注入与错误处理；节点即普通函数/Runnable；Send（types.py:738）动态 fan-out 到任意节点并携带自定义状态——map-reduce 编排原语

## 4. 记忆
- 短期记忆=thread 的 checkpoint 链（跨轮次共享状态）；长期记忆=BaseStore（跨 thread 的 key-value 语义存储，langgraph/store/）；序列化 JsonPlusSerializer（checkpoint README.md:50-55）

## 5. 护栏
- pregel/_validate.py、渠道 schema 校验；超时 _timeout.py、重试 _retry.py；错误分类 errors.py
- 安全：checkpoint 反序列化白名单 LANGGRAPH_STRICT_MSGPACK=true（README.md:54-55，防恶意 pickle）；interrupt 是最强护栏——关键写操作前强制人工确认

## 6. 可移植清单
1. thread_id+checkpoint_id 断点续跑模型 → 收件箱任务恢复键（恢复=载入最后快照+pending writes）
2. superstep+pending writes"半步失败不重算成功节点" → 看板多步骤任务细粒度断点
3. interrupt()/Command(resume) → Hook 人工审批点（挂起任务、批准后 resume）
4. reducer 注解式状态合并 → 任务状态机字段级并发写策略声明
5. checkpoint 版本号 versions_seen 增量调度 → 看板依赖触发（仅输入变更才重跑下游）

## 7. 知识库/技能清单
- 文档即知识库：libs/checkpoint/README.md（checkpoint/thread/serde 概念）、libs/prebuilt/README.md、AGENTS.md（面向 AI 协作者的项目说明，本身可借鉴）、.github/THREAT_MODEL.md（57KB 威胁模型文档）；examples/ 含 delta-channel 等示例；无数据集依赖
