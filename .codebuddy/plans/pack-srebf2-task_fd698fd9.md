---
name: pack-srebf2-task
overview: 执行工作空间打包流程：ws_pack.sh 将任务 projects/2026/SP20260907011/20261027_cut-tag 打包为就地 tar.gz（仅分析产物，自动排除输入软链与元数据，含 report.html）。
todos:
  - id: pack-task
    content: 执行 ws_pack.sh 打包任务 20261027_cut-tag 并核对包内清单与体积
    status: completed
---

## 需求概述

用户要求对已完成（done）的分析任务进行打包。

## 打包对象

任务目录：`projects/2026/SP20260907011/20261027_cut-tag`（Srebf2 靶基因分析，合同 92609076602，批次 SP20260907011，产品 cut_tag）

## 交付内容（随包）

- 交付 Excel：`results/92609076602_20261027_cut-tag_Srebf2_targets.xlsx`（5 sheets）
- 主表/附表/明细：`Srebf2_target_genes_main.xls`、`consensus_peak_annotated.xls`、`Srebf2_motif_match.xls`
- 结合强度图 8 件：`Srebf2_peaks_profile.*` / `Srebf2_motif_peaks_profile.*`（profile+heatmap × png/pdf）
- QC 图：`results/qc/Srebp2_seqlogo.png`
- 报告：`results/report.html`（随包交付）
- 脚本：`scripts/step_1..4 + run_all.sh`

## 排除项（脚本自动处理）

- `input.*` 软链、`.meta.yaml` 等元数据文件
- 同名压缩包已存在时报错退出，不覆盖

## 边界

- 仅打包，不同步生产目录（`ws_deliver.sh` 交付需另行确认后执行）
- 预计压缩包体积约 1-2MB（图片+表格为主，远小于 200MB 单任务产出上限）

## 技术方案

- 执行工作空间标准打包脚本：`bash .ws/bin/ws_pack.sh -T projects/2026/SP20260907011/20261027_cut-tag`
- 脚本自动完成：产物收集（排除输入软链与元数据）→ 就地生成 `<合同>_<任务>_<日期>.tar.gz`
- 验证步骤：`tar -tzf` 列出包内清单核对（确认 report.html、xlsx、图片齐全且无 input.* 泄入），`ls -lh` 确认体积合理
- 异常处理：若同名包已存在则脚本报错退出，此时向用户报告并列出既有包，等待人工决定（不自动覆盖，遵守不可变约定）