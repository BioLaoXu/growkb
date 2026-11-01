# [Stage-Gated SOP: 分析执行阶段 (`wip`)]
1. 按 `matched_skills` 路径读取对应 `.kb/docs/methods/<skill_id>/SKILL.md` 正文，并调用 `ws_memory.py search --ws-root . --scope <skill_id> --query "<需求关键词>"` 检索历史避坑经验。
2. 推进 `plan.md` 勾选清单（单次只允许将一个 `[ ]` 置为 `[✓]`，严禁批量谎报）。
3. 探查任何结果表格前，先运行 `ws_table_peek.py <table.tsv>` 获取全表精确显著行数与真实排序 Top-10，禁止裸跑 `head`。
