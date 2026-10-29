# 智能体深度调研：生信 Agent 16 个 + 通用高星 10 个（2026-10-29）

> 配合 ROADMAP 使用。汇总表在前，逐项目技术框架与边界在后。
> 标 ★ = 对本项目某项能力有直接可抄的实现。

## 一、汇总表（生信智能体）

| 项目 | 地址 | 底层框架 | 擅长 | 主要边界 |
|---|---|---|---|---|
| **BioMedAgent** ★RSI | github.com/Schaudge/BioMedAgent | 自研多智能体流水线（14+ Agent），三阶段：Planning→Coding→Execution；`SAVE_MEMORY`/`USE_MEMORY` 经验积累机制；`tool_info.json` 静态工具清单；Nature BME 2026 | 生医数据分析全流程（FASTQ→突变、差异表达、生存建模）；**自进化**：成功经验沉淀、跨任务复用；已复现 67 个生物工具 | 经验库质量决定上限；工具清单静态（需人工扩充）；复现依赖环境一致性 |
| **BioMaster** ★长任务 | github.com/ai4nucleome/BioMaster | 多智能体（Planner/Searcher/Executor/Critic 等）+ 动态知识检索（RAG）；有 readthedocs 文档 | 长工作流分解执行、多组学任务、可复现性 | bioRxiv 预印（未同行评审）；工具覆盖有限；代码活跃度一般 |
| **PromptBio / ToolsGenie 2.0** | 论文: bioRxiv 2025.07.05.663295 | 多智能体平台；ToolsGenie 2.0 核心 = **动态 Docker 镜像选择**（异构环境免装软件）+ 多 Agent 编排 | 生信数据分析平台化；环境兼容性方案（Docker 动态选择）值得抄 | 平台化偏产品；源码开放程度待确认 |
| **Biomni**（斯坦福，~4.0k★） | github.com/snap-stanford/Biomni | A1 智能体（LLM 推理+检索增强规划+代码执行）+ E1 统一生医环境；Know-How 经验库；MCP 集成；Biomni-R0 推理模型 | 通用生医任务（CRISPR 设计、组学、数据库查询）；7000+ 实验室在用 | 数据湖首次下载 ~11GB；偏研究场景；依赖强模型（sonnet 级） |
| **GeneGPT**（NCBI） | github.com/ncbi/GeneGPT | LangChain ReAct + NCBI API（EUtils）few-shot 示例选择 | NCBI 数据库问答（基因/疾病/变异） | 只覆盖 NCBI 系工具；API 参数偶有幻觉 |
| **CellAgent** | github.com/lsq2wal/CellAgent | 三角色多智能体：Planner→Executor→Evaluator；默认 Ollama 本地模型 | scRNA-seq / 空间转录组端到端（QC→聚类→注释→可视化） | 仅限单细胞/空间组；本地小模型效果打折 |
| **scAgent**（deepmind11） | github.com/deepmind11/scAgent | Feynman runtime 上的智能体；强制最佳实践 + 全程 provenance 追踪 | 10x Chromium scRNA-seq；产出可复现 notebook | 10x 数据专用；绑定 Feynman 运行时 |
| **AutoBA**（Adv Sci 2024） | 论文: doi.org/10.1002/advs.202407094 | 多 LLM 协作流水线：数据搜索→代码生成→执行→汇报（40 类组学任务） | 极少人工输入的全自动多组学 | 训练时效问题：新工具/新方法跟不上（作者自己承认） |
| **BioMANIA** | github.com/batmen-lab/BioMANIA | 从教程/API 文档自动生成对话助手（chatbot generation pipeline） | 低成本把已有文档变成分析助手 | 依赖教程质量；工具边界=文档边界 |
| **PaperQA2**（Future House） | github.com/Future-House/paper-qa | 文献检索→解析→引用对齐→问答（RAG+引用校验） | 高精度文献问答与引用 | 只做文献层，不做计算分析 |
| **BRAD** | github.com/jpickard1/brad | 检索增强多智能体（文献+代码+生标发现） | 生物标志物发现全流程（Bioinformatics 2025） | 偏发现型研究，非交付型分析 |
| **BioMCP** | github.com/fei0810/biomcp | 单二进制 CLI + MCP server，统一语法直达 70 个生医数据源（PubMed/ClinVar/OncoKB/Reactome） | 权威数据源检索层；任何 MCP Agent 可挂载 | 只读检索层，无分析执行器 |
| **ToolUniverse**（mims-harvard） | github.com/mims-harvard/ToolUniverse | 数百生医工具的 MCP 化集合（TxAgent 的工具层） | 工具与智能体解耦的协议层 | 无执行器；需配 TxAgent 类智能体使用 |
| **BixBench**（Future House） | github.com/Future-House/BixBench | 基准框架：61 个「分析胶囊」（数据+假设+标准分析）×~300 开放问题，LLM 评分 | 评测生信智能体的真实任务能力（2025 年模型仅 ~17%） | 只评不执行；胶囊需专家制作 |
| **Claw4Science**（生态目录） | claw4science.org | OpenClaw 生态（~179k★）的科研 Agent 目录：131+ 策展项目（OmicsClaw/BloClaw/DrugClaw…） | 发现与比较科研 Agent；skill 化工作流趋势风向标 | 目录站非工具；生态新、稳定性需自验 |
| **Scientific Agent Skills**（K-Dense-AI，~25.8k★） | github.com/K-Dense-AI/scientific-agent-skills | Claude Code 的科研技能套件（生信/化学/临床文档型 skills） | 让通用编码 Agent 变科研专用 | 依赖宿主 Agent（Claude Code） |

## 二、通用高星 10 个（框架层 / Harness）

| 项目 | 地址 | 星(约) | 底层框架与机制 | 擅长 | 边界 |
|---|---|---|---|---|---|
| **AutoGen**（微软） | github.com/microsoft/autogen | 40k+ | 事件驱动多智能体运行时；Actor 模型；可嵌套团队 | 多智能体协作、人在环 | 通用框架，无领域知识；版本迭代 API 变动大 |
| **MetaGPT** | github.com/FoundationAgents/MetaGPT | 50k+ | SOP 编码进智能体（产品经理→架构师→工程师流水线），消息池共享 | 把标准作业程序变成角色分工 | 软件开发导向；重预设流程 |
| **OpenHands**（原 OpenDevin） | github.com/All-Hands-AI/OpenHands | 45k+ | 事件流架构 + 沙箱执行（Docker）+ 浏览器/终端/文件三态 ACI | 通用开发智能体平台 | 面向软件工程；资源开销大 |
| **SWE-agent**（普林斯顿） | github.com/SWE-agent/SWE-agent | 15k+ | ACI 设计研究（紧凑文件查看器、守卫 lint）；SWE-bench 驱动 | 接口设计决定 Agent 上限的实证 | 基准导向，非日常工具 |
| **LangGraph** | github.com/langchain-ai/langgraph | 10k+ | 图状态机编排：节点/边/持久化 checkpoint/中断人审 | 长任务断点续跑、复杂控制流 | 学习曲线陡；需自建大量基础设施 |
| **crewAI** | github.com/crewAIInc/crewAI | 30k+ | 角色化 Crew（role/goal/backstory）+ Flow 事件流 | 快速搭多角色流程 | 深度控制弱于 LangGraph |
| **smolagents**（HF） | github.com/huggingface/smolagents | 15k+ | CodeAgent：**用代码表达行动**而非 JSON 工具调用 | 极简、快、可读 | 生态薄；安全沙箱需自配 |
| **AI-Scientist**（Sakana） | github.com/SakanaAI/AI-Scientist | 10k+ | 端到端自动科研闭环：idea→实验→论文→自动评审（LLM-as-judge） | RSI 完整先例 | 评审可靠性有争议；成本高 |
| **aider** | github.com/Aider-AI/aider | 35k+ | git 原生结对编程：每步自动 commit、repo-map、双模型 diff/apply | 「每步可回滚」的极致实现 | 单文件编辑为主，非任务管理器 |
| **lm-evaluation-harness**（EleutherAI） | github.com/EleutherAI/lm-evaluation-harness | 8k+ | 标准化评测：任务注册、评分器、回归对比 | 评测 harness 的工程范式 | 面向模型评测，非任务级评测 |

## 三、关键结论（映射到 ROADMAP）

1. **能力 4（RSI）已有生医领域现成参考**：BioMedAgent 的 `SAVE_MEMORY/USE_MEMORY` 双开关经验机制 + Nature BME 同行评审 —— 我们的「收尾自动提炼 → `.kb/` → 受理时应用」应直接对标它的记忆体设计（经验条目的结构化存储与检索是核心，不是简单日志）。
2. **能力 2（稳定性）的两层实现**：环境层抄 ToolsGenie 2.0 的动态 Docker 选择；结果层用 BixBench 胶囊思路建内部基准。
3. **能力 1（科学方案）的分工**：PaperQA2 管引用、BioMaster 的动态知识检索管方案匹配、BioMCP/ToolUniverse 管权威数据源 —— 三者拼起来即「每个方案都有据可查」。
4. **生态趋势**：OpenClaw 的 markdown-skill 生态（179k★）证明「技能=文档」的低成本扩展模式可以规模化 —— 我们的 `.kb/docs/methods/` 方案库天然兼容这种形态。
