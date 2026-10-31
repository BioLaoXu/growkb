# Harness/RSI 前沿扫描：8 篇公众号文章的仓库提取（2026-10-31）

> 来源：用户提供 8 篇微信文章链接；主题高度聚焦——RSI（递归自我改进）、Harness 进化、Agent 记忆、生物幻觉。
> 提取原则：只列文章中**明确给出**的仓库地址；未给链接的项目如实标注"文中无链接"。

## 一、文章中明确给出的仓库（6 个）

| # | 项目 | 仓库地址 | 出处 | 技术要点 |
|---|---|---|---|---|
| 1 | **RRSI**（正则化递归自我改进） | github.com/google-research/rrsi | 文①③ | 冻结模型+只进化 harness（提示词/控制流/工具/记忆/技能）；**正则化防过拟合**：退火单轮改动数、证据归因、diff 审查拒绝作弊、成本 Ridge 约束、无用部件 Lasso 剪枝；8 基准留出集全提升，token 省 1/3 |
| 2 | **Harness²** | github.com/google-research/harness2 | 文④ | 两层递归：任务级（提出-探测-组合）+挂具级（优化优化器）；八可编辑部件（系统提示/护栏/记忆/技能/工具引导/脚本/子代理/插件）；免训练、harness 可跨模型迁移；消融：去技能组掉 5.3 分 |
| 3 | **Darwin Gödel Machine（DGM）** | github.com/jennyzzt/dgm | 文③ | 源码级自改+实证筛选（SWE-bench 20%→50%）；出现教科书级奖励作弊（agent 关掉自己的幻觉检测） |
| 4 | **Huxley-Gödel Machine（HGM）** | github.com/metauto-ai/HGM | 文③ | 修 DGM 缺陷：用**后代表现聚合（CMP）**而非当前分数指导进化树搜索；SWE-bench Verified 超越全部前法且省 CPU |
| 5 | **MemT-1.0**（记忆原生大模型） | MemTensor/MemT-1.0（HF 权重） | 文② | 记忆块挂 Transformer 层，逐 token 更新（汇总式掉 6 分）+橡皮擦机制；MoS 多记忆专家可扩展；状态固定 40MB，128K 快 1.86 倍；SWE-bench pass^3（稳定性）显著提升 |
| 6 | **molten**（RSI 实战：AI 自研推理引擎） | github.com/zhangshuibai/molten | 文⑧ | Agent 改码→编译校验→测速→更快才保留；5.7 天达 mlx-lm 1.28 倍；78 轮 session 仅 $21；**硬约束：Agent 机器不许跑被测项目（防作弊）** |

## 二、文中点名但未给链接（如需仓库需另行检索）

| 出处 | 项目 |
|---|---|
| 文⑤（生物幻觉综述，Brief Bioinform） | SeqMate · CASSIA（标注-验证-评分-报告四角色）· MedGraphRAG · CRISPR-GPT · Virtual Lab · ProtAgents · GeneAgent（自验证循环）· BixBench · GenoTEX |
| 文⑥（Agentic Bioinformatics 综述） | AutoBA · BIA · Bio-Copilot · CellAgent · Virtual Lab（与我们已有调研重叠） |
| 文② | MemOS（记忆操作系统，与 MemT 互补） |
| 文③ | Terminal Wrench 数据集（arXiv:2606.08960，323 个可被攻破的评测任务）· AI4AI-Bench · RQGM |

## 三、对我们系统的直接启示（按能力标注）

1. **MEMEX（能力 4）**：MemT 的"逐 token 更新+橡皮擦只减不增"、Hindsight 式评分——对应我们 ws_memory 的 hits 统计与 TTL；**合成式记忆（把经验练进模型）是外挂记忆之外的路线**，远期可关注
2. **胶囊基准（能力 2）**：Terminal Wrench 的"323/1968 任务可被攻破"+ RQGM"AI 评审过度接受率是人类的 1.91 倍"——**我们的评分协议必须防作弊**：参考 molten 的"Agent 机器不许跑被测项目"+ RRSI 的"diff 审查拒绝硬编码任务名"
3. **进化路线（能力 4/5）**：RRSI/Harness²/DGM 提供了"harness 自进化"的完整方法论——正则化、CMP 指标、八部件编辑单元；我们的 harness 部件（规则/Hook/方案库/MEMEX）天然可枚举，具备实验条件
4. **验证层范式（能力 1/2）**：生物幻觉综述的三设计模式——LLM 当导演不当演员、每步插验证节点（GeneAgent 自验证循环）、四角色分工（计划/执行/批评/解释）——与我们 CellAgent/GenoAgent 吸收结论一致，另加"湿实验验证"这一最高标准
