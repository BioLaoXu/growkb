---
name: SP20260929002_customer_peak_overlap
overview: 为项目 SP20260929002 新建工作空间项目与任务，用 OXM（bed2gr + GenomicRanges）对 MAnorm 最终 peak 注释表与客户关注的 6 个 chr3 区域做 ≥1bp 交集分析，输出交集明细表（CSV）、汇总表与重叠关系示意图（区间条形图），并完成元数据收尾。
todos:
  - id: create-project-task
    content: 用 ws_new_project.sh/ws_new_task.sh 建项目 SP20260929002 与 peak-overlap 任务，软链输入、写 input.customer_peaks.bed、补 .meta.yaml、写受理回执
    status: completed
  - id: write-overlap-script
    content: 编写 scripts/step_1_peak_overlap.R：bed2gr 转 GRanges、统一染色体命名、findOverlaps ≥1bp、输出交集明细与汇总 CSV
    status: completed
    dependencies:
      - create-project-task
  - id: write-plot-script
    content: 编写 scripts/step_2_overlap_plot.R：ggplot2 客户区域 vs peak 重叠区间条形图，输出 PNG/PDF 到 results/
    status: completed
    dependencies:
      - write-overlap-script
  - id: run-and-verify
    content: 以 R_PROFILE_USER 指向私有库运行两脚本，核对命中结果与预检一致（2 peak：Arnt 启动子区等）
    status: completed
    dependencies:
      - write-plot-script
  - id: finalize-meta-report
    content: 回填 .meta.yaml methods/output，写 report.md 并用 ws_report.sh 渲染，跑 ws_index.sh，置 status done 并写回执
    status: completed
    dependencies:
      - run-and-verify
---

## Product Overview

为项目 SP20260929002（cut_tag 产品线）新增一个分析任务：将 MAnorm 差异分析的最终 peak（ChIPseeker 注释表，约 6.8 万条）与客户关注的 6 个 chr3 区域做交集分析，明确客户区域被哪些最终 peak 覆盖、peak 的注释信息（最近基因、启动子注释、M_value、P_value、sig 等）。

## Core Features

- 建立工作空间项目 `projects/2026/SP20260929002`（批次号=SP20260929002，产品=cut_tag，生产目录=/data/Report/cut_tag_project_2026/20261025_SP20260929002，合同号=926092206501）并受理任务
- 用 OXM（bed2gr）将最终 peak 表与客户 6 个区域转为 GRanges，统一染色体命名后以“任意 ≥1bp 重叠”判定交集（GenomicRanges::findOverlaps）
- 输出：交集明细表（每个客户区域命中的 peak 全注释信息 + overlap_bp）、各客户区域命中情况汇总表（CSV）
- 可视化：客户区域 vs 最终 peak 的重叠关系区间条形图（PNG）
- 按工作空间规范收尾：methods/output 回填、report.md 渲染、ws_index 刷新、状态置 done

## Tech Stack

- 语言：R 4.x，私有库 `/data/InHousePackages/OXM/library`（经 `R_PROFILE_USER` / 项目 `.Rprofile` 激活）
- 核心依赖：OXM::bed2gr（data.frame 输入自动矫正 chr/start/end 列名并保留附加列）、GenomicRanges::findOverlaps（OXM 依赖）、data.table::fread（读 25MB TSV）、ggplot2（区间条形图）
- 任务管理：工作空间脚本 ws_new_project.sh / ws_new_task.sh / ws_receipt.sh / ws_report.sh / ws_index.sh

## Implementation Approach

1. **建项目与任务**：`ws_new_project.sh -b SP20260929002 -p cut_tag -f /data/Report/cut_tag_project_2026/20261025_SP20260929002`，再 `ws_new_task.sh -t peak-overlap -r "<客户需求原文>"`；输入软链 `input.M2_5vsM2_2_peak_ChIPseeker_annotation.txt -> /data/Report/.../M2_5vsM2_2_peak_ChIPseeker_annotation.txt`（只读资源，禁止拷贝）；客户 6 个区域另存为任务根目录 `input.customer_peaks.bed`；.meta.yaml 补 sample_batch=SP20260929002、species=mouse、contract=926092206501。
2. **交集分析脚本**（scripts/step_1_peak_overlap.R）：

- `fread` 读注释表 → `OXM::bed2gr(peak_dt)` 转 GRanges（keep.extra.columns=T）
- 客户区域 data.frame → bed2gr，统一 seqnames：把 `chr` 前缀去掉（或给 peak 加 chr），与注释文件 `3` 风格一致
- `GenomicRanges::findOverlaps(query=customer_gr, subject=peak_gr, ignore.strand=TRUE, minoverlap=1)`；用 `pintersect` 计算 overlap_bp
- 输出明细表：customer_region、peak 坐标、M_value、A_value、P_value、Peak_Group、annotation、SYMBOL、distanceToTSS、sig、overlap_bp；未命中的客户区域在汇总表中标 0，保证 6 区域全覆盖呈现
- 汇总表：每区域 → 命中 peak 数、overlap bp、命中基因列表

3. **可视化脚本**（scripts/step_2_overlap_plot.R）：ggplot2 区间条形图——y 轴为客户 6 个区域（同区间聚类排列），x 轴为 chr3 坐标（95.42–95.45Mb 窗口），客户区域画深色粗条，命中的最终 peak 画浅色细条并用 hit 区间高亮交集段，导出 300dpi PNG + PDF。
4. **核对**：运行结果须与预检一致（预期命中 2 个 peak：3:95428595-95428803 与 3:95434106-95434753/Arnt 启动子）；不一致时排查坐标约定（0/1-based）。
5. **收尾**：回填 methods/output、写 report.md 并渲染 results/report.html、`ws_index.sh`、status=done、`ws_receipt.sh -s done`。

## Key Code Structures

```
# scripts/step_1_peak_overlap.R 核心（签名示意）
peak_dt  <- data.table::fread("input.M2_5vsM2_2_peak_ChIPseeker_annotation.txt")
peak_gr  <- OXM::bed2gr(peak_dt)                      # keep.extra.columns=T
cust_gr  <- OXM::bed2gr(read customer_peaks.bed)
seqnames(peak_gr) <- sub("^chr", "", seqnames(peak_gr))  # 统一命名
hits <- GenomicRanges::findOverlaps(cust_gr, peak_gr,
          ignore.strand = TRUE, minoverlap = 1L)      # 任意 >=1bp
```

## Performance & Reliability

- 25MB TSV 用 fread 一次载入（约 7 万行，内存 <500MB），无 N+1；findOverlaps 为区间树查询，O(n log n) 量级，秒级完成
- 染色体命名统一是本任务最大坑点（`3` vs `chr3`），脚本内置一致性断言：若交集为 0 且两边 seqnames 风格不同则报错提示，防止静默空结果
- 脚本幂等可重跑；结果文件带日期戳不覆盖既有交付