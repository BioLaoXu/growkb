---
name: add-motif-sheet
overview: step_4 Excel 增加 motif 匹配明细 sheet（全 peak 匹配状态 + 达标位点明细），并把 step_2 的匹配明细落盘为独立 TSV，重跑 step_4 重新生成交付 Excel。
todos:
  - id: step2-persist-motif
    content: 修改 step_2_target_genes.R：match_dt 全位点表落盘 results/Srebf2_motif_match.xls 并重跑 step_2
    status: completed
  - id: excel-add-motif-sheet
    content: 修改 step_4_excel.R 新增 motif 匹配位点 sheet 并重新生成交付 Excel
    status: completed
    dependencies:
      - step2-persist-motif
  - id: sync-meta-report
    content: 更新 .meta.yaml output 与 report.md 结果目录说明，ws_report.sh 重渲染
    status: completed
    dependencies:
      - excel-add-motif-sheet
---

## 需求概述

用户要求 motif 匹配到的表格一并交付。现状：motif 匹配明细（45 个位点级原始匹配、13 条 peak 级命中）只在 step_2 内存与中间产物 `results/MotifTarget/Srebp2.txt`（HOMER 原始格式）中，未纳入交付 Excel。

## 交付内容

1. motif 匹配位点独立明细表落盘（site 级：Peak / Offset / Sequence / Strand / MotifScore / MotifMatch 达标标记）
2. 交付 Excel 新增一个 sheet「motif 匹配位点」，与其他 4 个 sheet 同包交付
3. 同步更新 `.meta.yaml` output 清单与 `report.md` 结果目录说明，重渲染 report.html

## 边界

- 数据口径：以 OXM `getMotifTarget.homer` 的 HOMER findMotifs 全部输出位点（45 个）为基础，附 MotifMatch 列（score≥7 达标标记，14 个达标位点），保证透明可查
- 不改动既有 4 个 sheet 的结构与数据

## 技术方案

### 实现方式

1. **step_2_target_genes.R 补丁**：在 match_dt 解析后（`MotifMatch==1` 过滤前）将全位点表 `fwrite` 落盘为 `results/Srebf2_motif_match.xls`（TSV，真数据表，列：Peak/Motif/score/direction/Offset/match/MotifMatch；match_dt 已含全部 45 位点行与 MotifMatch 列）。保持现有主表/附表逻辑不变
2. **step_4_excel.R 修改**：sheets 增加 `"03_motif匹配位点"`（读 results/Srebf2_motif_match.xls），原 03/04 sheet 顺延改名为 04/05（sheet 名前缀统一两位序号）；方法说明 sheet 的 motif 检索行补一句"位点级明细见 motif 匹配位点 sheet"
3. **同步**：`.meta.yaml` output 追加新文件；report.md 结果目录表追加一行；`ws_report.sh` 重渲染
4. **执行顺序**：step_2（只重跑落盘段代价极低，且保证可复现）→ step_4 → meta/report 更新 → ws_report 渲染

### 关键事实（已核实）

- step_2 中 match_dt 在过滤前含全部位点行（45 个），setnames "seq"→"Peak" 后直接可写
- openxlsx 本会话已验证可用，writeDataTable 生成真 xlsx
- 任务 status: done，交付 Excel 覆盖重新生成本会话自产文件，不违反不可变约定；.meta.yaml 的 output 清单更新属收尾信息补充