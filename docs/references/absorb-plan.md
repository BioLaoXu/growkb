# 源码吸收工程路线图（2026-10-31 立项）

> 目标：把 33 个外部源（NGS 专项 20 + 通用框架 10 + 记忆层 5，去重后）的
> 提示词/流程/工具/记忆/Harness 设计吸收进本系统，服务六大能力。
> 方法：每源产出结构化吸收笔记（固定六字段：提示词/流程/工具/记忆/护栏/可移植清单）→
> 汇总《吸收综合报告》→ 按六大能力分组出改进提案 → 评审后排期落地。
> 笔记落点：.kb/docs/references/absorb/<源名>.md；源码克隆区：~/study/（工作空间外）。

## 七大能力域 × 源矩阵

### D1 方案科学性（能力 1）
| 源 | 深度 | 吸收重点 |
|---|---|---|
| OmicsClaw | T1 精读 | SKILL.md 格式、技能装载/降级机制、分域依赖 |
| bio-* 整合技能族 + bioskills | T2 | 单项全流程技能的文档结构与脚本组织 |
| GenoAgent/GenoTEX | T1 | 五角色 prompt 原文、每步专家标注对照法 |
| MetaGPT | T2 | SOP 编码进多智能体的写法 |
| nf-core（atacseq/rnaseq） | T2 | 流程参数模板/文档规范/最佳实践条目化 |
| BioMaster | T1 | 动态知识检索注入受理/执行的实现 |

### D2 结果可靠性（能力 2）
| 源 | 深度 | 吸收重点 |
|---|---|---|
| BixBench | T1 | 胶囊结构（数据+假设+标准答案）、评分脚本 |
| GenoTEX | T2 | 每步专家标注的对照评测法 |
| lm-evaluation-harness | T2 | 任务注册/评分器/回归组织的工程范式 |
| nf-core（CI 部分） | T2 | 流水线自动测试 |

### D3 规范化管理（能力 3）
| 源 | 深度 | 吸收重点 |
|---|---|---|
| nf-core | T2 | 版本锁定/容器化/参数校验 |
| Galaxy | T3 | 可复现平台的历史与审计设计 |
| aider | T2 | git 原生"每步回滚"实现 |

### D4 记忆与 RSI（能力 4）
| 源 | 深度 | 吸收重点 |
|---|---|---|
| Biomni | T2 | Know-How 条目 schema 与检索增强规划 |
| Mem0 | T1 | 记忆三层作用域、冲突编辑、多信号检索 |
| Letta / Hindsight / Cognee / claude-mem | T3 | 分层记忆/心智模型升华/图谱记忆/会话压缩沉淀 |
| AI-Scientist | T2 | 自动科研闭环+LLM-as-judge 自评 |
| PaperQA2 | T2 | 引用校验（方案"有据"的实现） |

### D5 长任务规划（能力 5）
| 源 | 深度 | 吸收重点 |
|---|---|---|
| LangGraph | T2 | 状态机编排/checkpoint 断点续跑/人审中断 |
| crewAI + AutoGen | T2 | 角色化与事件驱动多智能体运行时 |
| BioMaster | T1 | 长工作流分解+动态知识检索 |
| geno_agent | T3 | LangGraph 四智能体 RAG 实例 |
| smolagents | T3 | code-as-action 表达 |

### D6 Harness 框架与工具层（能力 6）
| 源 | 深度 | 吸收重点 |
|---|---|---|
| OpenHands | T1 | 事件流架构/沙箱执行/ACI 设计 |
| SWE-agent | T1 | ACI 接口设计范式 |
| MetaGPT / AutoGen / crewAI / smolagents | T2 | 框架对比（多智能体组织四种流派） |
| CellAgent | T1 | Planner/Executor/Evaluator 三角色 prompts |
| BioMCP | T2 | 统一命令语法+MCP server（ws_* MCP 化模板） |
| ToolUniverse | T2 | 工具 schema 注册表 |
| GeneGPT | T2 | API few-shot 工具调用 |
| AI-Scientist | T2 | LLM-as-judge 自评 |

## 执行波次

- **Wave 1（核心 8 仓精读）✅ 已完成（2026-10-31，8 份笔记见 absorb/，综合见 wave1-synthesis.md）**：OmicsClaw · GenoAgent · CellAgent · OpenHands · MetaGPT · BixBench · Mem0 · BioMCP
- **Wave 2（结构研究 10 源）**：lm-eval-harness · LangGraph · AI-Scientist · aider · AutoGen · nf-core · Biomni · SWE-agent · ToolUniverse · PaperQA2
- **Wave 3（要点级 15 源）**：其余全部（Letta/Hindsight/Cognee/claude-mem/Galaxy/GeneGPT/scAgent/ELAGT/AutoBA/BioMANIA/BRAD/geno_agent/bioskills/bio-* 族/scientific-agent-skills/crewAI/smolagents）

## 产出物

1. 吸收笔记 33 份（.kb/docs/references/absorb/<源名>.md，六字段模板）
2. 《吸收综合报告》1 份：按六大能力分组，每项改进提案标注【可立即落地/需设计/仅参考】
3. ROADMAP 修订提案（吸收结果回写里程碑）

## 执行方式

- 源码浅克隆至 ~/study/（工作空间外，不污染任务区）
- 每仓用并行代码探索子代理按六字段模板产出笔记（主会话汇总）
- 每完成一个 Wave：笔记入知识库（ws_kb sync）+ 综合推进一次
