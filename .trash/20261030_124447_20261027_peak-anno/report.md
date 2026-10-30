# 分析思路概述

> 用 3-6 句话说清：客户要什么、数据是什么、你打算怎么做、预期产出什么。

客户要求基于最新 TxDb（GENCODE vM36）重做小鼠 Cut&Tag peak 注释，并按 TSS±3kb 口径统计启动子覆盖比例。数据为批次 92512126902_mouse 的 peak 文件，预期产出注释结果表与启动子比例饼图。

## 详细步骤

> 按执行顺序写清每一步做了什么、用了什么工具/参数/阈值。可分小节。

### 1. 第一步名称

使用 ChIPseeker（v1.42）annotatePeak，TxDb 采用 GENCODE vM36 构建版本；promoter 定义为 TSS±3kb（客户口径，非默认 ±1kb）。

```bash
# 关键命令或代码片段（可选）
```

### 2. 第二步名称

TODO：……

## 结果目录说明

> 逐项说明 results/ 下每个文件是什么、怎么产生的。

| 文件 | 内容 | 产生步骤 |
|---|---|---|
| results/peak.anno.tsv | peak 注释主表（含最近基因/距离/区域类型） | 第 1 步 |
| results/report.html | 本报告 | 收尾生成 |

## 表格解读

> 每个表格单独一小节：关键列是什么、重点看哪些行、数值怎么解读。

### results/peak.anno.tsv

关键列：`annotation`（峰落点区域类型）、`geneId`（最近基因）、`distanceToTSS`。重点关注 promoter 占比行：本轮为 62%，高于上版（41%），差异来自 TxDb 更新。

## 图片解读

> 每张图单独一小节：图上有什么、坐标轴含义、能得出什么结论。

![启动子比例饼图](peak.anno.pie.pdf)

TODO：贴出饼图后在此写结论。

## 参考文献 / 参考资料

1. Yu G, et al. ChIPseeker: an R/Bioconductor package for ChIP peak annotation. Bioinformatics, 2015.
2. 软件引用：如 Yongxin Yao, et al. xxx. Bioinformatics, 2024.
