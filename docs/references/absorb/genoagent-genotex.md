# 吸收笔记：GenoTEX / GenoAgent（UIUC，五角色+专家标注基准）

## 0. 前置结论
本仓库是 GenoTEX 基准发布版（benchmark-only），五角色 GenoAgent 的完整 prompt 原文不在仓库（datasheet.md:158 明言 GenoAgent 仅是用基准评测的基线方法）。仓库保留：agent 运行骨架（CLI/路径配置/LLM 客户端）、工具函数库、专家标注答案、逐步评分脚本。prompt 部分按残存片段+可验证设计手法吸收。

## 1. 提示词（角色化残片与设计手法）
- 角色开关参数化（utils/config.py:9-24）：--max-rounds（修订轮数默认2）、--de（领域专家可消融）、--cs（代码片段/工具示例）、--plan（上下文感知规划）、--max-retract（允许回退次数）——每个角色/机制做成可开关项支持消融
- 环境预注入式 prompt（utils/path_config.py:58-101）：get_setup_prompt() 生成两段——"1. Path Configuration：以下变量已预配置在你的执行环境中…Use this instead of hardcoding the trait name"；"2. Pre-executed Setup Code：以下代码已自动执行，tools.preprocess 全部函数可直接使用"。手法：角色 prompt = 身份/任务说明 + 预执行命名空间快照，杜绝硬编码路径

## 2. 流程（分解、传递、逐步对照评分）
- GTA 问题=(trait, condition) 共 1,384 题；三段流水线：数据集筛选→预处理（gene/clinical/linked CSV）→统计回归出显著基因
- 步间传递靠结构化中间产物 cohort_info.json（is_usable/is_biased/has_age/sample_size，preprocess.py:491-576）
- 专家标注：4 名研究者定指南→9 名生信专家 20 周产出 237,907 行分析代码（每 cohort 一个带输出 notebook，agent 输出格式与专家格式逐字同构），IAA F1 94.73%
- 逐步对照评分（eval.py）：selection=混淆矩阵 P/R/F1；preprocessing=属性 Jaccard×样本 Jaccard×特征 Pearson 复合相似度；analysis=基因集 P/R/F1/Jaccard，**预测文件缺失即记 success=0 其余 NaN**，按无条件/条件一步/两步分类聚合

## 3. 工具链
- 预处理：GEO 解析、基因符号正则、探针→基因映射（一探针多基因均分再求和）、同义词归一、缺失值 20%/5% 阈值
- 统计：协方差特征值间隙检测 batch effect→自动切 LMM/Lasso；残差化回归；两步回归工具变量须"与 condition 相关、与 trait 无关"（IV 排他约束）；5 折 CV 以基因选择 precision 为目标；FDR 校正
- 基础设施：多 provider LLM 客户端含重试/成本核算；code/regress.py 固定逻辑参照实现

## 4. 记忆
无长期经验库。任务级状态沉淀：completed_tasks.json 断点续跑、跨步骤 cohort_info.json、logger 记录 token/成本

## 5. 护栏
审查员验码不在仓库。现存：任务级 420s 超时+资源峰值监控；成本超限关账；数据可用性硬校验（行数/列数异常覆盖指标）；输出目录/JSON 格式符合性检查

## 6. 可移植清单
1. 专家格式即接口：agent 输出与专家 notebook 同构（同路径配置/同产物名），评分脚本直接 diff → 评分基准
2. 逐步独立评分指标（选择/预处理/分析三段各自 P/R/F1），"跑失败=0 分"计入总分 → 评分基准
3. prompt 预注入执行环境（变量+setup 代码预执行，禁硬编码）→ 角色受理协议
4. 角色开关参数化（--de/--cs/--max-rounds/--max-retract）支持消融与回退 → 会话提示词
5. 元数据 JSON 作跨步契约 + completed_tasks 断点续跑 → 收尾状态落盘协议
6. 领域知识外置（related_genes、同义词表）既作先验又作评测参照 → 评分基准
