---
name: mouse-peak-anno-promoter
displayName: "Peak-Annotation-Promoter-Ratio (mouse-peak-anno-promoter)"
version: 1.0.0
area: "Epigenomics"
family: "Peak-Annotation-Promoter-Ratio"
product_codes: ["ATAC-seq", "ChIP-seq", "CUT&Tag"]
tags: ["ATAC-seq", "ChIP-seq", "CUT&Tag", "Epigenomics", "Peak-Annotation-Promoter-Ratio", "promoter", "TxDb", "peak注释"]
description: "LOAD WHEN: 任务涉及 Peak-Annotation-Promoter-Ratio（如 Peak 注释重做、指定 TxDb 版本、计算 Promoter 比例饼图与统计表）。SKIP WHEN: 原始 FASTQ 比对或单细胞聚类分析。"
---
# mouse-peak-anno-promoter（DisCo 三层已验证操作性知识技能包）

## When to use
当客户需求匹配 `Epigenomics -> Peak-Annotation-Promoter-Ratio`，特别是基于已有 Peak 表使用指定参考基因组注释版本（`TxDb`）重做注释并统计特定基因组特征（如 `Promoter TSS±N kb`）占比时加载。**命中本技能且置信度达标时，禁止自由发散编写计划，必须由 `ws_embodied_plan.py compile-plan` 锁死实例化标准计划！**

## Preconditions & Anti-Guessing Gates（计划前强制核验门禁）
- **`txdb_version`** (GENCODE/TxDb 注释版本): 必须明确指定版本（如 GENCODE_vM36），严禁默认旧版
- **`promoter_window_kb`** (Promoter TSS 上下游窗口大小): 凡客户提到 promoter，必须先确认 ±N kb（如 TSS±3kb），严禁默认按 ±1kb 开工

## Inputs
- 生产目录或上游 Peak 表：`tables/peaks.bed` 或 `tables/peak.anno.tsv`

## Workflow (Locked Canonical Steps)
1. **[S1_ANNO] 使用指定 TxDb 重跑 Peak 注释主表** — 调用 `.kb/code/R/annotation/promoter_ratio.R`，产出 `tables/peak.anno.tsv`
2. **[S2_RATIO] 调用标准库函数计算 Promoter 占比并生成统计摘要** — 调用 `.kb/cli/python/kb_tsv_stats.py`，产出 `tables/promoter_ratio.tsv`

## Gotchas
- 严禁未经确认默认使用 ChIPseeker 的 `TSS±1kb` 口径（见 `references/demo_batch_mouse-peak-anno.md` 两次返工教训）。
- 严禁在任务目录内手写临时 R 代码重算 Promoter 比例，必须直接调用绑定的标准库函数 `.kb/code/R/annotation/promoter_ratio.R` 与统计 CLI `.kb/cli/python/kb_tsv_stats.py`。

## Evidence
- 先例需求与踩坑归档：`references/demo_batch_mouse-peak-anno.md`
- 绑定核心 R 模块：`.kb/code/R/annotation/promoter_ratio.R`
- 绑定 CLI 统计薄壳：`.kb/cli/python/kb_tsv_stats.py`

## Outputs
- `tables/peak.anno.tsv`, `tables/promoter_ratio.tsv`, `figures/promoter_pie.png`, `report.md`

## Dependencies
- R (`ChIPseeker`, `.kb/code/R/annotation/promoter_ratio.R`), Python 3 (`.kb/cli/python/kb_tsv_stats.py`)
