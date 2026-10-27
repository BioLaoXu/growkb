# CHANGELOG —— 工作空间版本历史

> 语义化版本：架构变更 → 主版本（v3）；加功能/脚本 → 次版本（v2.x）；修 bug → 补丁（v2.0.x）。
> 每次变更：先改这里，再 `git commit` + `git tag`。

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
