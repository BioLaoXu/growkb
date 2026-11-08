---
name: data-report-inhouse
displayName: InHouse 项目研发数据总结报告
version: 1.0.0
description: >
  使用时机：InHouse 系列批次（生产目录形如 InHouseProject_2026/<PRODUCT>/<site>）的
  "研发数据总结"类需求——按参考模板整理各分析板块、核对已完成列、拟结论草稿。
  不适用时：全新探索性分析或临床向报告，转 data-report-clinical（未建）。
tags: [atac, cuttag, data-report, inhouse]
---

## When to use

- 卡片 request 含"研发数据总结/参考模板/已完成列"字样
- 生产目录为标准流程产出（QC/Map/<PRODUCT>/ 三层），含 config 与 sample.txt
- 参考：demo_batch_cuttag/20261028_data-report-inhouseproject-2026-template（首例）

## Inputs

| 输入 | 来源 | 格式 | 缺失处理 |
|---|---|---|---|
| 参考模板 | InHouseProject_2026/templates/*.html 或 wolai 链接 | HTML | 无模板时按 report.md 六章节 |
| 已完成列参照 | 上一同类任务 results/summary_pipeline_data_sources.md | MD | 缺失则自建对照表 |
| 流程产出 | 生产目录 QC/Summary、Map/Summary、<PRODUCT>/IPEval、Peaks | txt/xls/png | 缺板块则在报告中标注"未提供" |

## Workflow

1. 读模板 html，提取板块名与层级（校验点：板块清单与参考任务一致）
2. 盘点生产目录，写 summary_pipeline_data_sources.md（对照表：模板板块↔数据文件↔整理方式）
3. 逐板块取数：表入 results/tables/，图入 results/figures/（只复制 KB 级图，禁拷大文件）
4. 拟结论草稿（标"待审核"），每句挂证据键（文件名+表号/图号）
5. 汇总 report.md → 渲染 report.html → 收尾回执

## Gotchas

- summary.table.csv / GenomeCoverage.xls 是逐 bin 大表，**只取对应 png，不读内容**（来源：cut_tag 首例）
- "已完成一列"指模板中的核对清单，不是分析结果列（来源：demo_batch_cuttag 任务澄清）

## Evidence

- 模板：/data/Report/InHouseProject_2026/templates/（html）
- 首例：projects/2026/demo_batch_cuttag/20261028_data-report-inhouseproject-2026-template/

## Outputs

- results/report.html（六章节+板块对照）· summary_pipeline_data_sources.md · tables/ · figures/
- 验收：板块齐全、每个结论句挂证据键、"已完成列"核对无误

## Dependencies

- 生产目录读权限；HTML 渲染器（ws_report 内置）
