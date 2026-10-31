---
name: SP20260929002_peak_overlap_r2
overview: 在 SP20260929002 项目下新建第二轮任务（新一批 6 个 chr3 客户关注区域，95.52–95.54Mb Ctss 附近），复用上一任务脚本框架做 ≥1bp 交集分析，输出英文明细/汇总表、区间条形图、OXM Venn 图并完成报告与收尾。
todos:
  - id: create-task-b02
    content: 用 ws_new_task.sh 建 20261030_peak-overlap-2 任务，软链注释表、写 input.customer_peaks.bed、补 .meta.yaml 并写受理回执
    status: in_progress
  - id: adapt-scripts
    content: 复用上一任务 step_1/2/3 脚本，改输入区域文件与 _r2 输出前缀，更新脚本头注释
    status: completed
  - id: run-verify
    content: 依次运行三脚本，核对命中与预检一致（3 个 Ctss peak、6 区域全命中），检查图表为英文且无标签重叠
    status: completed
  - id: finalize-report
    content: 回填 .meta.yaml methods/output，写 report.md（中文正文+英文图）并渲染 report.html，刷新索引、置 done、写回执
    status: completed
  - id: pack-deliver
    content: ws_pack.sh 打包交付压缩包
    status: completed
---

## Product Overview

在 SP20260929002 项目下新建第二轮交集分析任务（b02）：客户更新了 6 个 chr3 关注区域（95.52–95.54Mb，`Ctss` 基因附近），要求计算其与 MAnorm 最终 peak 注释表（M2_5vsM2_2）的交集。上一任务（20261028_peak-overlap）已 done，按不可变约定新建任务目录。

## Core Features

- 新建任务目录并受理：软链 peak 注释表输入、落盘客户 6 区域 bed、补全 .meta.yaml、写受理回执
- 交集分析（任意 ≥1bp 重叠，OXM::bed2gr + GenomicRanges::findOverlaps）：交集明细表（peak 全注释 + overlap_bp）、6 区域全覆盖汇总表
- 可视化（图表一律英文）：chr3 窗口区间条形图（客户区域/命中 peak/重叠区间）、OXM::AutoVenn4DT 交集 Venn 图（含 VennDetail 簇明细）
- 收尾：report.md 渲染 results/report.html、ws_index 刷新、status 置 done、写回执、ws_pack 打包

## 已知预期（预检）

窗口内 3 个最终 peak 全部命中，6 个客户区域全覆盖：

- 3:95523410-95524083（Ctss 启动子 2-3kb，M=-0.029）覆盖 region_01/05
- 3:95521246-95521539（Distal Intergenic，Ctss，M=+0.053）覆盖 region_02/03/04
- 3:95526684-95526887（Ctss 启动子 ≤1kb，M=-0.248）覆盖 region_06

## Tech Stack

- R 4.x + 私有库 `/data/InHousePackages/OXM/library`（脚本内 `.libPaths()` 显式激活）
- 核心依赖：OXM::bed2gr / merge_gr_ / MarkGRCluster / AutoVenn4DT、GenomicRanges::findOverlaps、data.table::fread、ggplot2
- 工作空间脚本：ws_new_task.sh / ws_receipt.sh / ws_report.sh / ws_index.sh / ws_pack.sh

## Implementation Approach

- **完整复用上一任务脚本框架**（projects/2026/SP20260929002/20261028_peak-overlap/scripts/），仅替换输入 bed 与输出前缀（加 `_r2` 区分），保证两轮任务产物可对比且互不覆盖
- 已知坑直接规避：bed2gr 的 data.frame 分支需预置合法 `strand="*"` 列、注释表 `geneStrand` 列需删除（值 1/2 非法）；两集合染色体命名统一 `sub("^chr","")` 归一化（本次客户区域无 chr 前缀，仍统一处理防脏数据）
- Venn 沿用教程流程（merge_gr_ → MarkGRCluster → AutoVenn4DT，catName 覆盖标签角度为纵向、英文短集合名 Regions/Peaks），按区间簇计数并在报告注明
- 性能：25MB TSV fread 秒级载入，findOverlaps 区间树 O(n log n)，全流程分钟级

## Key Code Structures

- step_1 输出：`M2_5vsM2_2_customer_peak_overlap_detail_r2.xls/.csv`（region_id, peak 坐标, overlap_bp, M_value, P_value, annotation, SYMBOL, sig）
- step_2 输出：`customer_peak_overlap_chr3_window_r2.png/pdf`
- step_3 输出：`customer_peak_venn_r2.png/pdf` + `customer_peak_venn_detail_r2.xls`
- 窗口定义：客户区域 min(start)-1000 ~ max(end)+1000，与区间图/Venn 同口径