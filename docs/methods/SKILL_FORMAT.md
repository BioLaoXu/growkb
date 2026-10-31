# 方案库 SKILL.md 格式规范（v1，源自 OmicsClaw/OpenHands/bio-* 族吸收）

每个"标准分析方案"一个目录：`.kb/docs/methods/<方案名>/SKILL.md`（可附 references/）。
Agent 受理时按 frontmatter 的 description 路由（**load/skip 双半**：必须同时写明何时加载、
何时跳过并指名替代方案）；正文按需读取，不整篇注入。

## frontmatter（仅五键）

```yaml
---
name: <kebab-case 唯一名>
displayName: <中文名>
version: 1.0.0
description: >
  双半描述：何时使用本方案（触发词/数据类型/交付物）；何时不适用并指名替代方案。
tags: [atac, data-report, inhouse]
---
```

## 正文固定章节（顺序不变）

| 章节 | 内容 |
|---|---|
| When to use | 触发条件、适用数据类型、前置要求 |
| Inputs | 输入清单（生产目录相对路径约定）、格式与缺失处理 |
| Workflow | 分步骤操作规范（每步：动作/工具/产物/校验点） |
| Gotchas | 已知坑（每条锚定来源任务或脚本行） |
| Evidence | 方案依据：文献/文档/先例任务路径（方案"有据"的强制章节） |
| Outputs | 交付物清单与验收标准 |
| Dependencies | 依赖的软件/数据资源（升级 MEMEX 后作为依赖白名单） |

## 治理规则

- 同类 Gotchas/经验 ≥3 条 → 升华为新方案或并入既有方案（升华通道）
- 方案变更走 git；版本号语义化（加步骤=次版本，改结论口径=主版本）
- description 更新时必须同步"跳过半句"
