# [Stage-Gated SOP: 报告校验与收尾阶段 (`wip` -> `done`)]
1. **证据键规范**：
   - 正例：`实验组显著上调峰共 128 个（FDR < 0.05, log2FC >= 1），其中 STAT1 位点富集最显著 [diff_peaks.tsv#Table1:rows=500,sig=180]`
   - 反例（严禁）：`见 [表1]`、`[diff_peaks.tsv]`（无锚点）、引用未校正 pvalue 宣称显著、编造不在表中的基因名。
2. **双门禁交卷**：
   - 先运行 `ws_env_skill_router.py verify-drift --task-dir <dir>` 确认分析期间上游生产数据未被静默覆盖；
   - 再运行 `ws_bench.py grade --task-dir <dir>` 执行确定性源表反查与评分，生成 `.grade_receipt.json`（得分 `>= 0.80` 方可调用 `ws_meta.py` 置为 `done`）。
3. **阻力信号经验提炼**：仅当本任务曾经历 `blocked`、错误重试或 `-v2` 返工时，调用 `ws_memory.py add` 将泛化经验存入 `.staging/`（严禁带入合同号、日期、具体路径）。
