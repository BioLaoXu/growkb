---
name: harness_review_doc
overview: 撰写一份面向外部专家的系统评审文档（Markdown 单文件，落盘 .kb/docs/），全面盘点 CodeBuddy Agent + 工作空间的架构、规范、流程、harness（提示词/钩子/记忆/工具链/KB/记忆）现状，并附痛点诊断与可落地的优化建议清单，目标是提升后续 NGS 任务处理的准确率与速度。
todos:
  - id: gather-material
    content: Use [subagent:code-explorer] 通读 README 全文、4 份全局规则、.ws/bin 脚本与 .kb/README，提取真实行为清单
    status: completed
  - id: write-review-doc
    content: 撰写 .kb/docs/references/agent-workspace-harness-review.md：全景六层结构 + 痛点诊断 + 优化建议清单
    status: completed
    dependencies:
      - gather-material
  - id: verify-doc
    content: 逐条核对文中路径/脚本名/参数真实存在，核查无凭证与客户数据泄露
    status: completed
    dependencies:
      - write-review-doc
  - id: kb-changelog
    content: 在 .kb/CHANGELOG.md 追加变更记录并确认 .kb 索引一致
    status: completed
    dependencies:
      - verify-doc
---

## Product Overview

撰写一份面向外部专家的「Agent + 工作空间系统」评审文档（Markdown 单文件，含目录与表格），落盘 `.kb/docs/references/`（常驻维护）。目的：让专家在无需接触生产数据的前提下，完整理解当前系统的架构、规范、流程与 harness 现状，并据此优化系统，使后续 NGS 任务处理准确率更高、速度更快。

## Core Features

- **全景盘点（客观现状）**：
- 工作空间架构：projects/ 批次号项目树、scratch/、.ws/ 工具层、.inbox/.outbox 回执链路、与生产目录的只读软链映射
- 规范层：4 份全局规则（安全红线、Agent 行为、可视化偏好、项目制管理）+ README 三条核心原则与第七节 pwb 提单受理流程
- 工具链：.ws/bin/ 18 个 ws_* 管理脚本（受理/回执/报告/索引/检索/体检/打包/交付/KB）逐一说明用途与用法
- Harness 层：SessionStart 钩子（check_inbox.py 查收信息卡 + 会话命名约定注入）、CodeBuddy 记忆条目（archify 偏好、图表英文约定、OXM 环境与适配史）、可用 Skills 清单、Plan 模式/TodoList 工作方式
- KB 体系：目录结构、ws_kb.sh 工作流（new/check/index/sync→GitHub growkb）、现有条目清单
- 技术资产：OXM 包（私有库激活方式、关键函数、已知坑清单）、实战样例任务（SP20260929002 两轮 peak-overlap 全流程复盘）
- 规划与遗留项：断点续跑（暂缓+方案）、OXM 上 GitHub、KB 泛化入库惯例、contract 对账问题
- **痛点诊断**：从两轮实战任务中提炼的实际踩坑（bed2gr strand 缺列/geneStrand 误识别、报告模板缺失、会话命名依赖约定而非接口、无断点续跑、contract 字段对账、检索依赖 grep 级工具等）
- **可落地优化建议清单**：按「准确率 / 速度 / 可维护性」分类，每条含现状→建议→预期收益→实施成本，供专家直接评估下手

## Tech Stack

- 纯文档任务：Markdown 单文件（GFM，含 YAML 头部标注版本/日期/维护说明），无代码实现
- 素材采集：只读命令（ls/cat/grep）+ 已有对话上下文与记忆，不修改任何现有配置或脚本
- 落盘：`/data/Agent/xufa/workspace/.kb/docs/references/agent-workspace-harness-review.md`（命名贴合 KB references 分类惯例）

## Implementation Approach

1. **补齐素材**：通读 README.md 全文与 4 份全局规则原文、抽查 .ws/bin 关键脚本（ws_new_task/ws_receipt/ws_pack/ws_kb）的实际行为、核对 .kb/README.md 规范，确保文档描述与真实行为一致（不凭记忆写）
2. **按「六层结构」组织文档**：①系统目标与原则 → ②架构与目录 → ③流程（受理→分析→收尾→交付全生命周期）→ ④Harness 清单（钩子/记忆/规则/技能/工具）→ ⑤已知坑与痛点诊断 → ⑥优化建议清单；痛点与建议均标注证据来源（哪次任务踩的坑）
3. **自校验**：成文后逐条核对文中提到的路径/脚本名/参数是否真实存在，避免给专家错误信息；敏感信息核查（无凭证、无客户数据，仅内部路径与流程）
4. **入 KB 维护**：落盘后视情况在 .kb/CHANGELOG.md 记一笔，保持 KB 索引一致性

## Directory Structure

```
/data/Agent/xufa/workspace/
└── .kb/
    ├── docs/
    │   └── references/
    │       └── agent-workspace-harness-review.md   # [NEW] 系统评审文档（唯一交付物）
    └── CHANGELOG.md                                 # [MODIFY] 追加一条文档变更记录
```

## Agent Extensions

### SubAgent

- **code-explorer**
- Purpose: 快速通读 .ws/bin/ 各管理脚本与 .kb/README.md，提取每个脚本的真实用途、参数与行为（而非仅凭文件名推断）
- Expected outcome: 工具链与 KB 章节的描述全部有源码依据，避免文档与实现脱节