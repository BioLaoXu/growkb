# NGS 智能体 / 技能 / 知识库全景（20 项，2026-10-31）

> 范围：NGS 各组学（RNA-seq/ATAC/ChIP/WGS-WES/单细胞/宏基因组）相关的 Agent、技能包、基准、工具层与知识库。
> 检索源：SkillHub 技能市场、GitHub、Claw4Science 目录、arXiv/bioRxiv。星数为约数。

## A. 智能体系统（10）

| # | 项目 | 地址 | 能力点 | 边界 | 底层逻辑 |
|---|---|---|---|---|---|
| 1 | **OmicsClaw**（清华 AI4Life） | github.com/TianGzlab/OmicsClaw | 多组学统一 Agent：基因组学（变异/CNV/WGS-WES）、转录组（RNA/scRNA/DE/富集）、蛋白、代谢 + 跨组学整合（MOFA）；**88-93 个技能、7 领域**；CLI+桌面端+聊天平台；memory-enabled 会话 | 研究工具非医疗器械，结论需专家审核；可选依赖缺失时技能降级 | OpenClaw 底座 + **技能即文档**（skills/ 目录 SKILL.md 写方法学规范，Agent 读技能指令后在本地执行 Python/R/CLI）；分域依赖安装（core/domain/full） |
| 2 | **BioMaster** | github.com/ai4nucleome/BioMaster | 长工作流自动分解执行；动态知识检索；多组学 | bioRxiv 预印；工具覆盖有限 | 多智能体（规划/检索/执行/评审）+ RAG 知识注入 |
| 3 | **AutoBA**（Adv Sci 2024） | 论文 doi:10.1002/advs.202407094 | 极少人工输入的全自动多组学分析（40 类任务） | 新工具跟不上 LLM 训练时效；无经验沉淀 | 多 LLM 流水线：数据搜索→代码生成→执行→汇报 |
| 4 | **GenoAgent**（UIUC） | 项目页 haohanwang.ischool.illinois.edu/research/agentic-ai-genomics.html；基准 arXiv:2406.15341 | 基因表达数据全自动探索（数据集选择→预处理→统计→基因-性状关联） | 面向研究型问题，非交付报告 | **五角色多智能体**：项目经理/数据工程师/统计学家/代码审查员/领域专家——程序员 Agent 写码、审查 Agent 验码、专家 Agent 咨询 |
| 5 | **CellAgent** | github.com/lsq2wal/CellAgent | scRNA-seq/空间转录组端到端（QC→聚类→注释→可视化） | 仅单细胞/空间组；本地小模型打折 | Planner→Executor→Evaluator 三角色闭环 |
| 6 | **scAgent**（deepmind11） | github.com/deepmind11/scAgent | 10x scRNA-seq；强制最佳实践；全程 provenance | 10x 专用；绑定 Feynman 运行时 | 智能体 + 预定义最佳实践约束 + 执行溯源 |
| 7 | **Biomni**（斯坦福，~4k★） | github.com/snap-stanford/Biomni | 通用生医：CRISPR 设计/组学/数据库查询 + 假设生成；Know-How 经验库；MCP | 数据湖 11GB；偏研究场景 | LLM 推理 + 检索增强规划 + 代码执行；经验库随用随长 |
| 8 | **GeneGPT**（NCBI） | github.com/ncbi/GeneGPT | NCBI 数据库问答（基因/疾病/变异） | 仅 NCBI 系；参数偶幻觉 | LangChain ReAct + E-utilities API few-shot |
| 9 | **ELAGT**（论文项目） | bioRxiv 2024（检索 "ELAGT enhanced LLM agent genomic tasks"） | 增强 LLM 智能体做基因组任务（RNA-seq 差异分析为主），R 代码执行 | 仓库未公开/以论文为准；任务面窄 | LLM+R 执行环境+文献工具增强 |
| 10 | **geno_agent**（Zenodo 2026） | zenodo.org/records/22182322 | 罕见孟德尔病文献因果基因优先级（GA4GH 队列 n=1047 评测） | 垂直场景（文献 RAG，非数据分析） | **LangGraph 四智能体 + RAG**：检索-评估-综合-排序 |

## B. 技能包 / 技能市场（5）

| # | 项目 | 地址 | 能力点 | 边界 | 底层逻辑 |
|---|---|---|---|---|---|
| 11 | **bioskills**（SkillHub） | lightmake.site slug=bioskills | **412 种生信技能、54 类**：序列/RNA-seq/单细胞/变异检测/宏基因组/结构生物学校 | 单技能深度浅；质量参差需自筛 | 技能=markdown 指令+脚本，按类目装载 |
| 12 | **bio-\* 整合技能族**（SkillHub） | 同上（bio-atac-seq-integrated / bioinfo-differential-expression / bio-variant-calling-integrated / bio-small-rna-seq-integrated 等） | 单项分析全流程中文整合技能：ATAC 峰统计、DESeq2 差异、变异检出（VAF/TsTv）、小 RNA 长度谱 | 一技能一流程，扩展靠自己写 | 分析方法规范文档 + 内嵌脚本，中文版对国内团队友好 |
| 13 | **OmicsClaw 技能库**（可独立分发） | skillsmp.com/creators/tiangzlab/omicsclaw（93 技能） | 单技能可装进 Claude Code/Codex（如 genomics-variant-annotation：VEP/SnpEff/ANNOVAR 变异注释解读） | 单技能需自备依赖环境 | SKILL.md + 工具脚本，npx/skills 协议一键安装 |
| 14 | **scientific-agent-skills**（K-Dense-AI，~25.8k★） | github.com/K-Dense-AI/scientific-agent-skills | 科研技能套件：生信（序列/蛋白结构/代谢组）+ 化学信息 + 临床文献 | 依赖宿主 Agent（Claude Code 系） | 技能包=文档化工作流集合，装完即会"做科研" |
| 15 | **Claw4Science**（目录站） | claw4science.org（131+ 项目） | 科研 Agent 发现与比较：每日刷新星数/更新时间，诚实状态标签（含"早期/不活跃"） | 目录非工具；生态新、稳定性自验 | 独立策展 + 实时 GitHub 数据聚合 |

## C. 基准（2）

| # | 项目 | 地址 | 能力点 | 边界 | 底层逻辑 |
|---|---|---|---|---|---|
| 16 | **BixBench**（Future House） | github.com/Future-House/BixBench | 61 个真实分析胶囊 × ~300 开放问题，测"探索数据→多步分析→解读"全链 | 只评不执行；胶囊需专家制作 | 胶囊=数据+假设+标准分析；LLM 评分开放性答案 |
| 17 | **GenoTEX**（UIUC） | arXiv:2406.15341 | 基因表达分析全流程基准（数据集选择→预处理→统计），含生信专家标注的标准答案 | 限基因表达场景 | 任务分解为可评测子步骤，每步对照专家标注评对错 |

## D. 工具层 / 知识库（3）

| # | 项目 | 地址 | 能力点 | 边界 | 底层逻辑 |
|---|---|---|---|---|---|
| 18 | **BioMCP** | github.com/fei0810/biomcp | 单二进制 + MCP：直达 70 个可信生医源（PubMed/ClinVar/ClinicalTrials/OncoKB/Reactome…） | 只读检索层，无执行器 | 统一命令语法 → 各源 API 适配器；MCP server 同源复用 |
| 19 | **ToolUniverse**（mims-harvard） | github.com/mims-harvard/ToolUniverse | 数百生医工具的 MCP 化集合（TxAgent 工具层） | 需配智能体使用 | 工具 schema 注册表 + MCP 协议暴露 |
| 20 | **nf-core**（含 atacseq/rnaseq/sarek/chi） | github.com/nf-core | 社区评审的标准化 NGS pipeline 集（ATAC-seq 也有专属管线）；版本锁定、CI、参数模板 | 非智能体；流程固定需自己改 | Nextflow DSL + 容器化 + 自动化测试——**流程工程最佳实践的知识库** |

## 三、对本项目的启示（对照六大能力）

1. **技能化路线已被验证**（OmicsClaw/bioskills/nf-core）：我们的 `.kb/docs/methods/` 方案库应向"SKILL.md 规范式"靠拢——每个方案=方法学文档+可执行脚本+输入输出约定
2. **角色分工有两条路线**：固定角色（GenoAgent 五角色）vs 状态机+单一 Agent（我们现状）；GenoTEX 证明"每步对照专家标注"可显著提升准确率——对应我们求教 #1/#3
3. **对账/评分是准确率杠杆**：BixBench 的胶囊、GenoTEX 的专家标注，本质都是"先有标准答案再跑 Agent"——我们应把已完成任务转化为内部胶囊
4. **工具层协议化**（BioMCP/ToolUniverse）：我们的 ws_* 脚本可 MCP 化，被任意 Agent 复用
