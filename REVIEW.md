# REVIEW.md — 致命边界审查契约（Anthropic 六层防御规范）

> 本文件定义自动化 Reviewer 的硬阻断（🔴 Important）与免打扰边界。普通编码风格与排版规范见 `.codebuddy/rules/workspace-convention.md`（违规仅记为 🟡 Nit）。

## 1. 致命阻断项（🔴 Important — 触发即硬阻断合并与置 `done`）
- **Docs/Report Lie（报告与数据不符）**：`report.md` 中的显著行数、上下调方向、Top 基因或富集通路与 `tables/*.tsv` 实盘数据不一致。
- **Plan Lock Violation（计划结构篡改）**：命中锁死技能（`LOCKED_EXPLOITATION`）时，擅自增删或重排 `plan.md` 标准步骤，或弃用绑定的 `.kb/code/` 函数。
- **Scientific Threshold Degradation（静默降标）**：将未校正 `pvalue < 0.05` 冒充 `FDR/padj < 0.05`，或未经人工确认擅自剔除样本。
- **Config / Skill Misroute（方案错配）**：未通过 `ws_disco_distill.py` 或 `ws_env_skill_router.py` 绑定合规方案。

## 2. 审查收敛与降噪硬约束（防 50 轮死循环断路器）
- **轮次硬上限**：单任务 Author ↔ Reviewer 自动交互 **≤ 3 轮**；第 3 轮仍未收敛必须立即熔断置为 `blocked` 交由人类裁决。
- **局部差量审查（Round 2+ Differential-Only）**：第 2、3 轮审查**只允许检查本轮新增修改的 Diff 行**，严禁翻旧账质疑第 1 轮未改动的代码或段落。
- **报“类”不报“行”（Report Class, Not Line）**：同类格式或引用瑕疵必须合并为 1 条“类别级（Class-level）”意见要求单次全局修复，禁止逐行拆成多条意见。
- **三级打标与噪声上限**：
  - 🔴 `Important`：致命错误（仅置信度 ≥ 80 方可提出，必须带精确 `file:line`）；
  - 🟡 `Nit`：非阻断优化建议，**单次审查最多不超过 2 条（Noise Cap ≤ 2）**；
  - 🟣 `Pre-existing`：上游生产目录或历史遗留瑕疵，**严禁归咎于当前任务或阻断交付**。
- **忽略路径**：忽略 `tables/raw_*`、`figures/*.png`、`.kb/memory/.superseded/**`。

## 3. 风险分级人工审批矩阵（Commit/Report SHA 强绑定）
| 风险等级 | 典型变更场景 | 所需人工审批数 | 失效规则 |
|---|---|---|---|
| **Low** | 已命中 `LOCKED_EXPLOITATION` 技能的常规报告生成、文档排版微调 | **0 人**（全绿自动放行） | — |
| **Medium** | 新增或修订 `.kb/docs/methods/*/SKILL.md`、自定义分析脚本参数调整 | **1 人** | 报告或代码 SHA256 一旦变更，旧批准立即失效 |
| **High** | 修改 `.ws/bin/` 核心框架脚本、放宽统计学阈值、跨批次合并重算 | **2 人** | 强制双人审计，Agent 的 Approve 永远不算数 |
