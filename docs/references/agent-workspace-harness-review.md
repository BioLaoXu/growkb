# Agent 工作空间 Harness 工程评审文档（v2.3，2026-10-31）

> 定位：给评审专家的**系统现状与设计细节专文**，与 HARNESS.md（白皮书）互补——
> 白皮书讲哲学与范式，本文讲"当前到底长什么样、每件东西怎么工作、证据在哪"。
> 所有服务器路径/软件包已抽象化；全部断言可由文中标注的文件位置验证。

## 一、系统快照：六大能力现状矩阵

| 能力 | 现状 | 证据（工作空间内可验证） |
|---|---|---|
| 1 方案科学性 | **初步落地**：方案库 SKILL 范式+首个种子方案；受理环境预核验；报告证据键协议 | .kb/docs/methods/SKILL_FORMAT.md、data-report-inhouse/SKILL.md、.ws/templates/report.md.tmpl |
| 2 结果可靠性 | **工具已建**：胶囊基准（pack+三梯度评分）；逐步对照评分协议（失败=0）；重跑比对待做 | .ws/bin/ws_bench.py、.kb/docs/methods/report-scoring.md |
| 3 规范化管理 | **基线成熟**：五态状态机/三级索引/回执/备份 10 份/权限分层/迁移四模式/回收站 | .ws/bin/ 脚本族、HANDOFF.md |
| 4 记忆与 RSI | **冲突层已实装**：MEMEX schema+种子 3 条+冲突四操作+双层去重+升华规则；提炼时机待自动化 | .kb/memory/_schema.md、.kb/memory/*.yaml、.ws/bin/ws_memory.py |
| 5 长任务规划 | **规范已立**：plan.md 勾选清单防谎报状态机+断点续跑条款；执行器待做 | .ws/templates/plan.md.tmpl、规则 5C 条款 |
| 6 Harness 工程 | **持续加固**：工具目录表+断言设计、事件/错误契约、看板写接口白名单、Hook 三件套 | .ws/tools-catalog.yaml、.kb/docs/methods/harness-event-contract.md、.codebuddy/settings.json |

## 二、Harness 七件详解

### 2.1 提示词体系（四层注入）

| 层 | 载体 | 注入时机 | 内容 |
|---|---|---|---|
| 常驻规则 | .codebuddy/rules/workspace-convention.md | 每会话 | 落盘归属/命名/状态机/受理协议（含环境预注入、勾选清单、黄金实践引用、MEMEX 纪律）/禁止事项 |
| 会话开场 | SessionStart Hook | 每新会话 | 扫描收件箱注入待受理卡摘要（含命名建议） |
| 首条消息 | UserPromptSubmit Hook | 首条任务消息 | 会话命名建议（批次_合同号_日期，会话内去重） |
| 任务内 | plan.md + 黄金实践段 + .env_check.yaml | 开工时 | 勾选清单防谎报 + NGS 纪律条目 + 已核验环境清单 |

设计手法（吸收来源标注）：结构化变量槽+输出契约（CellAgent）；渐进披露/正文按需加载（OmicsClaw）；
"人类专家经验"硬编码段（CellAgent）；环境预注入禁硬编码（GenoTEX）。

### 2.2 流程工程

五态状态机（planned/wip/blocked/done/delivered）+ 两阶段受理 + 收件箱对账归档（批次+slug 双匹配）
+ 回执三态 + 幂等保护（同名拒绝/产物不覆盖/重做加 -v2）。详见白皮书第三章。

### 2.3 工具层

- 管理脚本族 13 个（建/感知/报告/记账/运维/看板六类），目录表 `.ws/tools-catalog.yaml`
  （每工具：动词+有界输入+明确禁止项——BioMCP 范式，MCP 化时直接映射）
- 看板单进程双职能：静态托管 + /api/state + 9 个写接口（只调既有脚本）
- 保护机制：路径越界检查、仅 planned 可删、回收站语义、同 slug 冲突即拒、生产目录先核验后落盘

### 2.4 记忆（MEMEX v1 实装）

- 条目：.kb/memory/*.yaml，schema 十字段（id/type/scope/task/trigger/content/evidence/superseded/hits/expiration）
- 操作：ws_memory.py add/update/delete/search/list
- 冲突四操作：ADD（新知）/UPDATE（同 id 修订）/DELETE（矛盾，须写原因，历史入 .superseded/）/NOOP（MD5 命中）
- 去重双层：MD5 精确 → 语义相似度 0.85 阈值（difflib），冲突时给出三选一建议
- 检索：关键词加权评分（trigger 命中×3），--use 自动计 hits（使用信号），TTL 惰性过期
- 升华：同类 ≥3 条 → 提示合并为正式方法文档

### 2.5 评测基准（胶囊）

ws_bench.py pack：done 任务 → 胶囊（data/=tables+figures，**剔除结论性 report.md**，
单文件>2MB 跳过）+ capsule.yaml（request/标准产物清单）+ README（任务书）。
grade：覆盖率（标准产物被引用比例 0.7）+ 证据键格式合规（0.3）→ 总分；LLM verifier P2 接入。

### 2.6 事件/错误契约

写操作统一 JSON：{ok, action, is_error, error{message, retriable, next_steps[]}, data}；
错误三要素缺一不可（BioMCP/ToolUniverse 范式）；写响应禁缓存；破坏性操作 fail-closed。

### 2.7 护栏清单（v2.3）

删除三重锁 · 路径越界检查 · 产物不覆盖 · 写接口白名单 · 先问不猜 · 备份前置 ·
**记忆双层去重+矛盾审计** · **危险操作 fail-closed** · **写响应禁缓存**（后三为 v2.3 新增）

## 三、验证记录（关键实测，均为本会话真实执行）

| 机制 | 实测内容 | 结果 |
|---|---|---|
| MEMEX 冲突层 | 六场景：新增/MD5 重复拒绝/语义变体拒绝并给 UPDATE 建议/检索计 hits/无 reason 删除拒绝/带 reason 归档 | 全通过（测试中修掉 glob 漏配 bug） |
| 胶囊基准 | 对真实 ATAC 数据报告任务 pack（61 数据文件/61 标准产物，report.md 结论未带入）+ 跨批次 grade（覆盖率 0.44 合理） | 通过 |
| 错误协议 | 看板 POST 错误返回 {message, retriable, next_steps[]}，POST 响应带 Cache-Control: no-store | 通过（修复 elif 互斥 bug 后） |
| 受理环境预核验 | 看板受理 ATAC 卡自动写 .env_check.yaml | 通过 |
| 一键发起 | dispatch → 卡生成 → Hook 注入 → 受理 → 回执 全链路 | 通过 |

## 四、与外部范式的映射（吸收清单摘要）

| 我们的组件 | 吸收来源 | 吸收了什么 |
|---|---|---|
| 方案库 SKILL.md | OmicsClaw、SkillHub bio-* 族 | frontmatter 五键、load/skip 双半、固定章节、三件套组织 |
| ws_memory.py | mem0、OmicsClaw、Hindsight | 加法提取、四操作、MD5+语义去重、TTL 惰性、升华通道 |
| ws_bench.py | BixBench、GenoTEX | 胶囊结构、答案剔除、三梯度判分、失败=0 |
| plan.md 防谎报 | OmicsClaw planning/rules | 单次完成一项、禁复活、违规拒绝自愈 |
| 环境预注入 | GenoTEX path_config | 预执行核验替代硬编码 |
| 事件/错误契约 | OpenHands、BioMCP、ToolUniverse | 成对同构、retriable、next_steps、溯源 |
| 工具目录表 | BioMCP catalog | 静态表+启动断言、描述三要素 |
| 报告证据键 | PaperQA2 | 引用键正反例清单、CANNOT_ANSWER 哨兵 |

全部 25 份源码笔记见同目录 absorb/*.md，综合报告 absorb/SYNTHESIS.md。

## 五、求教清单（更新版，重点前四项）

1. **方案映射库的结构**：SKILL.md 范式已定，但"需求类型→方案"的路由层怎么建（关键词？意图分类？让 LLM 读全部 description 自选）？
2. **胶囊基准的评分进化**：当前覆盖率+键格式是表面指标，"结论正确性"如何评（LLM verifier 的 prompt 设计/防评审自恋）？
3. **MEMEX 提炼时机**：任务 done 自动提炼 vs 收尾会话人工确认——如何平衡噪音与遗漏？
4. **记忆的图谱化**：任务-方法-结果-文献实体关联（Cognee 方向）值不值得现在投入？
5. 多会话并行写 META 的一致性；6. 常驻规则膨胀的消减策略；7. 整理型任务结论的数值一致性校验。

## 六、已知边界（诚实声明）

- ws_memory 语义去重用 difflib 字符相似度，非 embedding——中文短文本够用，长文本有漏检风险
- ws_bench 评分 v1 只看"引用覆盖+键格式"，不看结论语义正确性
- 看板写接口白名单只调既有脚本，但脚本本身的参数校验深浅不一
- 单 Agent 状态机路线（非多智能体），长任务并发执行未支持
