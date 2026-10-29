# 生物信息智能体与相关项目全景（调研于 2026-10-29）

> 服务于 ROADMAP 六大能力规划。星数为约数（调研时点），以仓库实况为准。

## 一、生物信息智能体 / 基准（12 个）

| 项目 | 地址 | 能力点 | 对本项目的借鉴 |
|---|---|---|---|
| **Biomni**（斯坦福 SNAP，~4.0k★） | github.com/snap-stanford/Biomni | 通用生医智能体 A1：LLM 推理 + 检索增强规划 + 代码执行；内置 Know-How 经验库；MCP 集成；自带 Biomni-R0 推理模型 | ★ 最对标。其 Know-How 库 ≈ 我们的 `.kb/docs/methods/`；「检索经验再规划」正是能力 1 的实现范式 |
| **AutoBA**（Advanced Science 2024） | 论文: doi.org/10.1002/advs.202407094 | 极少人工输入的全自动多组学分析：自动搜索数据、生成代码、逐步执行并汇报 | 能力 1/5 的先例；也暴露了局限：工具更新快于模型训练 → 需要经验库持续喂养（即我们的 .kb 闭环） |
| **BioMANIA**（batmen-lab） | github.com/batmen-lab/BioMANIA | 从教程/API 文档自动生成对话式分析助手，覆盖组学数据分析 | 低成本构建领域助手的路径：用已有文档自动生成 —— 可为我们每类产品线生成专属助手 |
| **GeneGPT**（NCBI） | github.com/ncbi/GeneGPT | LLM 调用 NCBI API（Gene/Docsums）回答基因组学问题 | 工具调用+权威数据源的模式，适合我们的数据库查询类需求 |
| **CellAgent**（lsq2wal） | github.com/lsq2wal/CellAgent | scRNA-seq 端到端自动分析：Planner / Executor / Evaluator 三角色 | ★ 三角色架构直接对应能力 5（规划分解）+ 能力 2（Evaluator 自检） |
| **scAgent**（deepmind11） | github.com/deepmind11/scAgent | 10x scRNA-seq 智能体：强制最佳实践、全流程 provenance 追踪、可复现输出 | ★「强制最佳实践 + provenance」正是能力 2/3；其 provenance 思路可加进我们的 report.md |
| **PaperQA2**（Future House） | github.com/Future-House/paper-qa | 文献检索-阅读-引用问答智能体（高精度引用） | 能力 1「方案要有文献依据」的实现样板：方案生成时自动挂引用 |
| **BRAD**（jpickard1） | github.com/jpickard1/brad | 检索增强的生物标志物发现智能体（Bioinformatics 2025） | 检索增强 + 自动化发现流程的组合范式 |
| **BioMCP**（fei0810/biomcp） | github.com/fei0810/biomcp | 一个二进制、统一语法，直达 70 个可信生医数据源（PubMed/ClinVar/OncoKB/Reactome…），同时是 MCP server | ★ 我们未来接「权威数据源」的最短路径：CodeBuddy 原生支持 MCP（`buddycn --add-mcp`） |
| **ToolUniverse**（mims-harvard，Zitnik 组） | github.com/mims-harvard/ToolUniverse | 数百个生医工具的 MCP 化集合（TxAgent 的工具层） | 工具层与智能体解耦的范式；我们的 ws_* 脚本未来可 MCP 化 |
| **BixBench**（Future House） | github.com/Future-House/BixBench | 生信智能体基准：61 个真实分析场景 / ~300 开放问题（分析胶囊=数据+假设+标准分析） | ★ 能力 2/6 的基准样板：我们的内部基准直接借鉴「胶囊」结构 |
| **Galaxy / nf-core**（领域基建，非 agent） | usegalaxy.org · github.com/nf-core | 可复现分析平台 / 标准化 pipeline 集合（社区评审、CI、版本化） | 能力 3 的领域标杆：nf-core 的 pipeline 规范（参数模板、CI、版本锁定）值得抄 |

## 二、通用高星项目（与规划相关，非生信，10 个）

| 项目 | 地址 | 星数(约) | 能力点 | 对本项目的借鉴 |
|---|---|---|---|---|
| **AutoGen** | github.com/microsoft/autogen | 40k+ | 多智能体对话/编排框架 | 能力 5：多角色协作拆解长任务 |
| **MetaGPT** | github.com/FoundationAgents/MetaGPT | 50k+ | SOP 驱动的多智能体（软件公司隐喻） | 能力 1/3：把「标准作业程序」编码进智能体 —— 与我们的方案映射库同思路 |
| **OpenHands**（原 OpenDevin） | github.com/All-Hands-AI/OpenHands | 45k+ | 通用开发智能体平台（沙箱执行、事件流） | 能力 6：Agent-Computer Interface 的工程参考 |
| **SWE-agent**（普林斯顿） | github.com/SWE-agent/SWE-agent | 15k+ | ACI（智能体-计算机接口）设计，SWE-bench 领先 | 能力 6：接口设计决定 Agent 上限的实证 |
| **LangGraph** | github.com/langchain-ai/langgraph | 10k+ | 状态机式智能体编排（断点、持久化、人审） | 能力 5：长任务断点续跑的编排模型 |
| **crewAI** | github.com/crewAIInc/crewAI | 30k+ | 角色化多智能体（轻量） | 快速原型多角色流程 |
| **smolagents**（HF） | github.com/huggingface/smolagents | 15k+ | 极简 code-agent（用代码表达行动） | 轻量执行器参考 |
| **AI-Scientist**（Sakana） | github.com/SakanaAI/AI-Scientist | 10k+ | 端到端自动科研： idea→实验→论文→评审 | 能力 4 RSI 的完整闭环先例（含自动评审） |
| **aider** | github.com/Aider-AI/aider | 35k+ | 结对编程智能体（git 原生：每步自动 commit） | 「每步有回滚点」已是我们铁律；aider 是极致版 |
| **lm-evaluation-harness**（EleutherAI） | github.com/EleutherAI/lm-evaluation-harness | 8k+ | 标准化评测框架（任务定义/评分/回归） | 能力 2/6：评测 harness 的工程范式 |

## 三、对我们路线的关键启示（综述 PMC12476841 + 上述调研）

1. **单智能体 specialize，多智能体 orchestrate**：单智能体适合明确任务（成本低、稳），多智能体适合复杂长任务（规划/执行/评审分离）—— CellAgent 的三角色是两者之间的甜点
2. **经验库是被反复验证的核心**：Biomni Know-How、AutoBA 的教训（工具迭代快于模型）都指向同一个结论 —— **持续喂养的领域经验库决定 Agent 上限**（我们的 `.kb` 方向正确）
3. **基准先行**：BixBench 证明 2025 年的模型在真实生信任务上准确率仅 ~17% —— 不要迷信裸模型，要用我们自己的基准测我们自己的流程
4. **工具层解耦**：BioMCP/ToolUniverse 把「能力」做成协议层（MCP），智能体只是调用方 —— 我们的 ws_* 脚本未来可以低成本 MCP 化，被任何 Agent 使用
