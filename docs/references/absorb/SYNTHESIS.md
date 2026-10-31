# 吸收综合报告：33 源 × 六大能力改进提案（2026-10-31）

> 基于 25 份吸收笔记（Wave1 八仓精读 + Wave2 十源结构研究 + Wave3 要点级四组 + 既有调研三份）。
> 提案三档：【落地】可直接实施（本周期）；【设计】需先出设计稿；【参考】仅作背景。
> 交叉引用：明细见同目录 absorb/*.md；能力定义见 HARNESS.md 第六章；里程碑见 ROADMAP.md。

## 能力 1｜方案科学性（需求拆解 + 方案有据）

| 提案 | 档 | 来源 | 落点 |
|---|---|---|---|
| 1.1 方案库 SKILL.md 范式：每方案=方法学文档（固定章节：When to use/API/Methods/Gotchas/Inputs-outputs/Dependencies）+ 可执行脚本 + load/skip 双半描述 + frontmatter（name/version/license/tags） | 落地 | OmicsClaw、SkillHub bio-* 族、OpenHands | .kb/docs/methods/ 改版 |
| 1.2 环境预注入式受理提示：受理时把 source_dir/cohort/可用数据文件写进开工 prompt 并预执行核验，禁止硬编码路径 | 落地 | GenoTEX path_config | 受理协议（规则+看板） |
| 1.3 增量式方案文档自动生成器：仿 BioMANIA 从已有教程/报告自动生成方案草稿 | 设计 | BioMANIA | .kb 工具 |
| 1.4 引用键协议：报告结论每句挂"证据键"（文档/数据文件），格式用正反例清单约束，迭代时剔除失效键 | 落地 | PaperQA2 | report.md 规范+评分协议 |

## 能力 2｜结果可靠性（稳定性与可复现）

| 提案 | 档 | 来源 | 落点 |
|---|---|---|---|
| 2.1 内部胶囊基准：已完成任务转化为"数据+假设+标准分析"胶囊；打包剔除答案性文件；评分三梯度（精确→部分→LLM verifier）+ 三态（对/错/拒答）+ replica 多数投票 | 设计 | BixBench、GenoTEX | 新 ws_bench 工具 |
| 2.2 逐步对照评分：报告产出拆子步骤，每步对照"标准产物"独立评分；跑失败=0 分计入总分 | 落地 | GenoTEX eval.py | 评分协议 |
| 2.3 重跑比对：同任务重跑 diff 结果+MD5；环境版本记录进 META | 落地 | GenoTEX 断点续跑 | ws_replay（ROADMAP M2） |
| 2.4 schema 驱动参数校验（参数契约 JSON+校验插件） | 落地 | nf-core nextflow_schema | 收件箱表单/信息卡校验 |

## 能力 3｜规范化管理

| 提案 | 档 | 来源 | 落点 |
|---|---|---|---|
| 3.1 module 三件套标准化：每个分析脚本目录=主文件+测试+元数据说明 | 落地 | nf-core modules | 脚本族规范 |
| 3.2 产物路径约定文档（output.md 式）随任务生成 | 落地 | nf-core docs/output | report.md 章节 |
| 3.3 每步自动 commit+白名单 undo | 落地 | aider | 状态机收尾 |

## 能力 4｜记忆与 RSI（MEMEX 定稿输入）

| 提案 | 档 | 来源 | 落点 |
|---|---|---|---|
| 4.1 条目 schema 定稿：{id,text,hash,created_at,updated_at,expiration_date,attributed_to,linked_ids[],hits,score_details}；TTL 惰性过期（读取时过滤不物理删，留 show_expired 逃生口） | 落地 | mem0、OmicsClaw | MEMEX schema |
| 4.2 提取策略：LLM 只做"加法提取"（sole operation ADD）；变更类记忆强制记录"转变前后"；实体相同不等于事实重复；"When in doubt, extract"（去重交下游） | 落地 | mem0 | 收尾提炼规则 |
| 4.3 冲突四操作（ADD/UPDATE/DELETE/NONE）+ MD5 精确去重 + 语义去重双层 | 落地 | mem0 | MEMEX 冲突层 |
| 4.4 检索评分：semantic+BM25(sigmoid 归一)+实体 boost 加性融合，threshold 只门控语义分，score_details 可解释字段 | 设计 | mem0 | MEMEX 检索层 |
| 4.5 升华通道：同类经验 ≥3 条 → 提示升华为方法文档（对应 Hindsight 观察→心智模型） | 落地 | Hindsight、OmicsClaw Know-How | .kb 升华规则 |
| 4.6 记忆操作即工具（Agent 可自编辑 core 层，archival 走检索） | 设计 | Letta | MEMEX API |
| 4.7 防记忆污染：入库查重（n-gram janitor 思路）+ 角色泄漏惩罚写进提取 prompt | 落地 | lm-eval、mem0 | Hook |

## 能力 5｜长任务规划

| 提案 | 档 | 来源 | 落点 |
|---|---|---|---|
| 5.1 子任务清单=plan_write 状态机（3-7 项、唯一 in_progress、单次只许完成一项、禁复活 cancelled，违规拒绝并让 Agent 自愈） | 落地 | OmicsClaw planning/rules | 任务 plan.md 规范+Hook 校验 |
| 5.2 断点续跑：文件系统即状态（阶段产物落盘+skip 已完成）；任务失败回滚"已投递未消费"态 | 落地 | AI-Scientist、MetaGPT | 看板状态机 |
| 5.3 checkpoint/pending-writes 细粒度断点（半步失败不重算成功节点） | 设计 | LangGraph | 长任务执行器 |

## 能力 6｜Harness 工程

| 提案 | 档 | 来源 | 落点 |
|---|---|---|---|
| 6.1 事件契约：动作/观察成对同构（is_error+元数据）；失败回喂 rejection_reason 作观察事件 | 落地 | OpenHands | 脚本族 schema+看板 |
| 6.2 Hook 七类型对齐（Pre/PostToolUse、SessionStart/End、UserPromptSubmit、Stop）——已部分实现，补 Stop 与留痕事件 | 落地 | OpenHands | settings.json |
| 6.3 工具目录表+启动断言（description 与路由一一对应）；工具描述="动词+有界输入+明确禁止项" | 落地 | BioMCP | ws_* MCP 化 |
| 6.4 错误协议化：错误带 retriable 标志+next_steps 恢复建议+SectionSource 溯源 | 落地 | ToolUniverse、BioMCP | 脚本族错误层 |
| 6.5 勾选清单状态机提示词（[ ]/[✓]/[✗] 每步回显） | 落地 | Biomni | 开工/收尾提示词 |
| 6.6 人类专家经验硬编码段（NGS 黄金实践条目写进 prompt） | 落地 | CellAgent | 开工提示词 |
| 6.7 压缩三件套（forgotten_ids+summary+offset）+ 压缩前抽取器 | 设计 | OpenHands、OmicsClaw | 会话记忆 |
| 6.8 危险操作 fail-closed 批准卡（凭证打码）+ 认证请求禁缓存 | 落地 | OmicsClaw、BioMCP | Hook/看板 |
| 6.9 领域工具检索用"API 演示>文档"原则 | 参考 | GeneGPT | 工具描述设计 |

## 优先级建议

- P0（本周期）：1.1、1.2、1.4、2.2、4.1、4.2、4.5、5.1、5.2、6.3、6.5、6.6 —— 全部零/低依赖，直接补强准确率
- P1（下周期）：2.1（胶囊基准 MVP 3-5 个）、4.3、4.7、6.1、6.4、6.8
- P2（需设计）：1.3、2.3 重跑执行器、4.4 检索评分、4.6、5.3、6.2 补全、6.7
