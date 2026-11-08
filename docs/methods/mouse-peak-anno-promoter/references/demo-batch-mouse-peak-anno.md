---
title: "需求拆解：peak 注释重做与 promoter 占比（20261027_peak-anno）"
batch: "demo_batch_mouse"
tags: ["promoter", "TxDb", "peak注释", "mouse", "atac"]
date: 2026-10-27
author: BioLaoXu
---
# 需求拆解：peak 注释重做与 promoter 占比（20261027_peak-anno）

## 客户原始需求
用最新 TxDb 重做 peak 注释，补充 promoter 比例饼图。

## 拆解与口径
1. TxDb 升级到 `GENCODE vM36`（旧版注释偏少是本轮返工主因）。
2. promoter 口径 = `TSS±3kb`（客户自定义，非 ChIPseeker 默认 ±1kb——两次踩坑点）。
3. 产出：注释主表 (`tables/peak.anno.tsv`) + promoter 比例统计表 (`tables/promoter_ratio.tsv`) + 饼图 (`figures/promoter_pie.png`) + 报告 (`report.md`)。

## 可复用沉淀
- R 函数 `promoter_ratio()`: `.kb/code/R/annotation/promoter_ratio.R`（口径参数化）。
- CLI 统计工具: `.kb/cli/python/kb_tsv_stats.py`。
- 报告模板：`.ws/templates/report.md.tmpl`。

## 经验（强制前置门禁）
- 凡客户提到 promoter，先问清 `±N kb`（寫入 `META.yaml` 的 `promoter_window_kb`）與參考基因組注释版本（`txdb_version`），未確認前严禁默认按 ±1kb 开工！
