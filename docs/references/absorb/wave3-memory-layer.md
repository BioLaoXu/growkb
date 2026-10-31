# 吸收笔记（Wave 3 要点级）：记忆层四仓（Letta/Hindsight/Cognee/claude-mem）

> T3 要点级：基于 README/架构文档+领域知识，未逐文件精读。

## Letta（原 MemGPT，letta-ai）
- 现状：核心已迁至 letta-ai/letta-code（agent harness+TUI+App Server+channels）；archive 分支保留 V1 API server
- 记忆设计（MemGPT 范式）：core memory（常驻上下文，Agent 可自编辑）+ archival memory（向量检索）+ recall memory（对话历史）三分层；"Agent 自编辑记忆"=记忆操作是 Agent 的工具调用
- 可移植：MEMEX 的"热/温/冷三层"与"记忆操作即工具"直接对标；我们 .kb 的 docs/memory 分层对应其 core/archival

## Hindsight（vectorize-io，LongMemEval SOTA）
- 核心概念（README 确认）：memory types 分类、**retain / recall / reflect 三操作**、observations（观察记录）、**mental models & knowledge pages（心智模型与知识页）**、memory banks（记忆库分组）
- 定位："make agents that learn, not just remember"——不止回忆，还要学习；LongMemEval SOTA，Virginia Tech 独立复现
- 可移植：①"观察→心智模型"的升华通道即我们"≥3 条同类经验升华为方法文档"的成熟参照；②retain/recall/reflect 三操作可作为 MEMEX 的 API 面（写入/检索/反思）；③memory banks 对应我们按产品线分组的 .kb 结构

## Cognee（topoteretes）
- 定位：知识图谱+LLM 接口优化（论文 arXiv:2505.24478）；"Company Brain"/"agent memory across runs"——把决策、讨论、实现连成图谱
- 组织：实体-关系-事件图谱 + 自定义本体（ontology support）；免费小模型可跑（CPU）
- 可移植：把"任务-方法-结果-文献"连成图谱是 MEMEX 的进阶形态；本体支持提示我们给 .kb 定 schema

## claude-mem（thedotmack）
- 定位：Claude Code 生态的会话压缩沉淀记忆（hooks 驱动）
- 可移植：会话结束自动压缩入库的节奏（对应我们收尾自动提炼）；其 hooks 集成方式与我们 .codebuddy/settings.json 同构

## 综合
四仓共同点：**记忆是独立服务/层，而非对话附件**；检索有专门评分；写入有质量门。MEMEX 应定位为"独立记忆层"而非".kb 里多几篇文档"——条目 schema（mem0）+ 三操作 API（Hindsight）+ 分层（Letta）+ 图谱化（Cognee，远期）。
