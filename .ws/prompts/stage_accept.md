# [Stage-Gated SOP: 受理与环境预核验阶段 (`planned`)]
1. 运行 `.ws/bin/ws_env_skill_router.py check --ws-root . --task-dir <dir> --source-dir <src> --product <prod> --request "<req>"`。
2. 检查输出的 `.env_check.yaml`：
   - 若存在 `broken_symlinks`、`empty_files` 或 `missing_required_inputs`，立即保持 `planned` 或切为 `blocked` 向用户汇报，禁止猜路径。
   - 阅读 `candidate_skills` 的 `load_when` 与 `skip_when`，选出匹配方案并通过 `ws_meta.py patch --expected-rev <rev> --set 'matched_skills=["<skill_id>"]' --set status=wip` 正式开工。
