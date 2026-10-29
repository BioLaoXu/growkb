---
name: accept-xjyf-cuttag20260908-data-report
overview: 受理内部研发卡 XJYF-cuttag20260908：新建项目与任务目录并写受理回执；然后基于生产目录的 CUT&Tag 流程结果，参照 InHouseProject_2026 模板撰写微量 CUT&Tag 研发数据总结报告（results/report.md → report.html）。
todos:
  - id: accept-create-task
    content: 执行 ws_new_project.sh/ws_new_task.sh 建项目与任务，软链 input.*，补 request/sample_batch/species/notes，写 accepted 回执
    status: pending
  - id: survey-pipeline-outputs
    content: 巡检生产目录 QC/Map/CUTTAG 各子目录，定位模板 3.1-3.8 各节对应的数据文件与图源
    status: pending
    dependencies:
      - accept-create-task
  - id: extract-metrics-plot
    content: 在 scripts/ 编写脚本汇总指标表并绘制英文图（FRiP/TSS/复杂度/重复性/片段长度等），输出到 results/
    status: pending
    dependencies:
      - survey-pipeline-outputs
  - id: write-report-md
    content: 按模板章节结构撰写 results/report.md，含各组结论、阈值对照与总结&优化建议
    status: pending
    dependencies:
      - extract-metrics-plot
  - id: finalize-report
    content: "用 ws_report.sh 渲染 report.html，回填 .meta.yaml（methods/scripts/output，status: done），ws_index.sh 刷新，写 done 回执"
    status: pending
    dependencies:
      - write-report-md
---

## Product Overview

受理内部研发分析卡 XJYF-cuttag20260908（微量 CUT&Tag 体系研发测试，小鼠，抗体 H3），在工作空间建立对应项目与任务，并参照 InHouseProject_2026 模板（XJ-2026616：微量cuttag测试1）撰写本次数据的研发数据总结报告。

## Core Features

- 受理落盘：新建项目（batch=XJYF-cuttag20260908）与任务目录（data-report-inhouseproject-2026-template），软链必要输入、写受理回执
- 数据摸底：梳理生产目录 QC/Map/CUTTAG 各阶段流程输出（样本设计：S1K_H3_1/2、S5K_H3_1/2、S5W_H3 vs S5W_IgG）
- 指标汇总：按模板章节提取测序质控、比对率/dup、染色体与线粒体占比、FRiP、TSS 富集分布与得分、Fingerprint、链交叉相关、NRF/PBC1/PBC2、peak 一致性与 Region 分布、peak 属性、片段长度分布等指标
- 报告撰写：按模板 1-5 章结构输出结论式报告（含 500/1k 细胞组与 5k 细胞组横向对比、与推荐阈值对照），图表全英文、正文中文，渲染为 results/report.html
- 收尾：回填 .meta.yaml、刷新索引、写 done 回执

## Tech Stack

- 受理与落盘：工作空间脚本 `ws_new_project.sh` / `ws_new_task.sh` / `ws_receipt.sh`（README 第七节标准流程）
- 指标提取：R（data.table/ggplot2）或 Python 脚本，解析流程输出中的统计文本/TSV/PDF 图源数据
- 报告：Markdown（`results/report.md`）→ `ws_report.sh` 渲染 `results/report.html`

## Implementation Approach

- 参照模板已核实的章节骨架（项目回顾/实验设计/数据分析结果 3.1-3.8/寻因测试/总结&优化建议）逐节对照生产目录输出定位数据源：QC/（fastqc、dup）、Map/（比对率、染色体分布）、CUTTAG/IPEval/（FRiP、TSS、Fingerprint、BinCov、PeakSim）、CUTTAG/Peaks/（peak 数量与一致性）、CUTTAG/IPEval/PeakAttr/（peak 属性）、片段长度（Eval_Fragment/insert size）
- 生产目录只读：输入以 `ln -s input.*` 软链（fastq 不链不拷），产出图片/表格放 results/，总量控制在 200MB 内
- 结论写法对齐模板风格：每小节给「结论：」并对照推荐阈值（FRiP>10%、TSS 得分>0.3、NRF>0.7、PBC1>0.7、PBC2>3、线粒体<10% 等），突出 1k 细胞组 vs 5k 细胞组稳定性对比与研发优化建议
- 模板中不适用项（如 Motif 未知、寻因测试无）按实际情况标注「结果无/略」

## Architecture

```
生产目录(只读) --ln -s--> 任务目录(input.*)
        │
        └─> scripts/step_*.R|py（指标汇总+英文图）──> results/（图、表）
                     └──────────> results/report.md ──ws_report.sh──> results/report.html
```