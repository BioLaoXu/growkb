# CHANGELOG —— 工作空间版本历史

> 语义化版本：架构变更 → 主版本（v3）；加功能/脚本 → 次版本（v2.x）；修 bug → 补丁（v2.0.x）。
> 每次变更：先改这里，再 `git commit` + `git tag`。

## v2.4.0 — 2026-11-01（专家架构合并）

- **并发安全**：ws_meta.py 新增 flock 排他锁 + rev 乐观锁 CAS + os.replace 原子替换（`patch --expected-rev`）
- **收尾封印工作流**：`ws_meta.py seal <任务> --grade` = 评分门禁（≥0.8 才允许）+ 产物 chmod 只读 + .kb 知识快照烙印 + 回显收尾阶段 SOP
- **阶段门控 SOP**：.ws/prompts/stage_accept|wip|report.md，状态切换时由 ws_meta 回显对应细则（规则微内核化第一步）
- **MEMEX 两级暂存**：经验 add 默认入 .staging/（promote 转正）；knowhow 类反具体化门禁（拦截合同号/批次/日期/路径写进经验）
- **单行哨兵**：SessionStart 只注入 "Inbox pending: N | Active WIP: M"，修复续跑会话被收件箱劫持
- **深度环境探针**：.env_check.yaml 增加 broken symlink/0-byte/sample.txt sha256 指纹（记录不阻断）
- **五个新工具**：ws_env_skill_router（两阶段漏斗路由）、ws_table_peek（防位置偏见大表摘要）、ws_bio_verifier（证据键源表反查）、ws_run（进程组沙箱）、ws_contract（统一 emit 契约）
- 修复：ws_memory glob 漏配去重失效、看板错误包装 elif 互斥、ws_meta 双 main 冲突

## v2.3.0 — 2026-10-31（P1 六项）

- ws_memory.py：MEMEX 冲突层工具（add/update/delete/search/list，事件契约输出，六场景实测）
- ws_bench.py：胶囊基准（pack 答案剔除/list/grade 覆盖率+证据键三梯度）
- 看板错误协议化：{message, retriable, next_steps[]} + POST Cache-Control: no-store
- HARNESS.md 升版 + 评审专文 agent-workspace-harness-review.md

## v2.2.0 — 2026-10-31（P0 十二项）

- 方案库 SKILL 范式（SKILL_FORMAT.md + method-skill 模板 + 首个种子方案 data-report-inhouse）
- 受理环境预核验（.env_check.yaml）+ 报告证据键协议 + 评分协议（report-scoring.md）
- MEMEX schema 定稿 + 3 条种子经验（真实事故沉淀）
- plan.md 勾选清单模板 + 断点续跑条款 + 工具目录表 tools-catalog.yaml
- ControlTower 动态看板全量（筛选/分页/回收站/帮助浮层/事件错误契约）

## v2.1.0 — 2026-10-29（发起通道与调研）

- ws_dispatch.sh 一键发起（建项目/任务 + 信息卡；-C 卡-only 模式）+ SessionStart Hook 查收
- ws_migrate.sh 迁移工具（一键换路径/pack/deploy/handover 四模式）
- check_inbox Hook 兼容工作台缩进式信息卡
- ROADMAP 六大能力规划 + 智能体全景/深度调研（26+ 项目）

## v2.0.0 — 2026-10-27

**基线版本：无 DB 架构 + 年份/批次号三级目录 + 隐藏元数据 + 双知识库 + pwb 对接协议**

- 移除 ws.db 台账数据库：.meta.yaml 是唯一事实来源，.index.md 即台账
- 项目目录定稿三级：projects/<年>/<批次号>/<YYYYMMDD>_<slug>/
- 配置/元数据文件隐藏化：.meta.yaml / .project.yaml / .source / .notes.md / .index.md（input.* 保持可见）
- 交付包瘦身：只含 scripts/ 与 results/（含 report.html），排除元数据与软链
- 新增报告能力：report.md（收尾源稿）→ ws_report.sh → results/report.html
- 新增知识库 .kb/：code（R Roxygen / Python Google docstring）+ cli（optparse / argparse）+ docs（需求/方法/参考/结果）
- 新增 ws_kb.sh：index / check / new / sync（GitHub 私库 growkb）
- 新增 pwb 对接协议：项目信息卡提单（HANDOFF.md）+ .outbox/ 回执对账
- 新增 ws_backup.sh 扩容版：元数据 + 任务脚本 + report.md + .ws 工具区（results 不进包）
- 权限三档方案文档化（README 9.2，由用户执行 chmod）
