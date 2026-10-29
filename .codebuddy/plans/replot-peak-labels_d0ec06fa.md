---
name: replot-peak-labels
overview: step_3 结合强度图重绘：给 plotProfile/plotHeatmap 加 --startLabel/--endLabel 参数，把横轴默认的 TSS/TES 标注改为 Peak start/Peak end（数据与区间不变，纯标签修正），复用已有 .mat.gz 矩阵只重跑绘图段。
todos:
  - id: patch-step3-labels
    content: 修改 step_3_binding_signal.R 绘图段：extraParams 追加 start/end 标注，矩阵存在时跳过 computeMatrix
    status: completed
  - id: replot-and-verify
    content: 复用 .mat.gz 重绘 8 个图文件并目检横轴标注
    status: completed
    dependencies:
      - patch-step3-labels
  - id: rerender-report
    content: ws_report.sh 重新渲染 report.html 并核对无 TSS 残留
    status: completed
    dependencies:
      - replot-and-verify
---

## 需求概述

重绘 step_3 的结合强度图（deeptools profile/heatmap）。当前图横轴两端标注为 deeptools 默认的 "TSS/TES"，但绘图区间实际是 Srebf2 结合的 peak（scale-regions 模式：peak body 400bp 归一化等长 + ±1kb 侧翼），与转录本无关，标注误导读者。

## 修正内容

- 数据与区间完全不变，仅修正横轴边界标注：`--startLabel "Peak start"`、`--endLabel "Peak end"`
- 涉及 2 组图 ×（profile + heatmap）×（png + pdf）共 8 个文件覆盖重生成：
- `results/Srebf2_peaks_profile.*`（全体 672 条 consensus peak）
- `results/Srebf2_motif_peaks_profile.*`（13 条 motif+ peak 子集）
- 复用已有信号矩阵 `results/matrix/consensus_peaks.AllPeaks.mat.gz` 与 `consensus_peaks.MotifPeaks.mat.gz`，跳过 computeMatrix，只重跑绘图段
- 重绘后重新渲染 `results/report.html`（report.md 无需改文字，但核对无 TSS 字样残留）

## 技术方案

### 实现方式

1. **脚本修改**（`scripts/step_3_binding_signal.R` 绘图段 `## ---- 4 ----`）：

- `heatmap.extraParams` 追加 `--startLabel "Peak start" --endLabel "Peak end"`（保留现有 `--missingDataColor white --sortUsing mean`）
- `profile.extraParams` 追加同款两个参数（当前为空串，改后非空）
- OXM `deeptools_plot` 对 extraParams 只做字符串追加、不校验，透传安全

2. **绘图入口**：脚本支持直接以已有 .mat.gz 路径调 `deeptools_plot`；为避免重跑 computeMatrix，在绘图循环中直接引用两个矩阵文件（加 `file.exists` 守卫：矩阵存在则跳过 computeMatrix 段，缺失则全流程重跑——保持脚本幂等）
3. **验证**：读取重绘后的 profile.png 目检横轴标注；确认 8 个文件时间戳已更新
4. **报告同步**：`bash .ws/bin/ws_report.sh -T projects/2026/SP20260907011/20261027_cut-tag` 重新渲染 report.html

### 关键事实（已核实）

- deeptools plotProfile/plotHeatmap 均支持 `--startLabel/--endLabel`
- deeptools_computeMatrix 返回 `list(组名=list(cmds,mat,rbind,label))`，`mat` 即合并矩阵路径
- 图文件为本会话自产，覆盖重生成不违反不可变约定