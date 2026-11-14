#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_open_science_wal.py — 融合 Open-Science Agent (aipoch/open-science v1.2.1) 与“沙箱、凭据、审计三张清单”
核心机制：
1. Open-Science 预执行日志与幂等核实 (`pre-exec` / `reconcile-retry`):
   “没有收到返回，不等于操作没有发生，直接重试可能把同一件事做两遍。”
   在调用外部/重型工具前先写 `PRE_EXEC` 记录（含预期产出文件与参数指纹）；若中途超时或中断，重试前必须调用 `reconcile-retry` 核实预期产物是否已在磁盘生成且非空，若已完成则直接补写 `POST_EXEC` 跳过重跑！
2. 参数版本化产物血缘绑定 (`bind-lineage`):
   每次改参数重跑分析时，将 (run_id, script_sha256, params_json, output_files_sha256) 写入任务目录 `records/lineage.json`，确保每张图/表都能倒查到唯一对应的代码与参数快照。
3. 第二张安全清单——“密码/凭据不过模型” (`scrub-env-run`):
   启动子进程前自动剥离所有含 KEY / TOKEN / SECRET / PASSWORD 的环境变量，防止 Agent 通过 `env` 或报错栈读取凭据原文。
4. 第三张安全清单——“盯行为本身而非节奏”的权限与写操作审计 (`audit-log`):
   在 `.ws/audit/security_audit.jsonl` 记录 (actor_identity, timestamp, requested_scope, post_auth_mutation)。
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from ws_contract import emit_error, emit_success

SECRET_ENV_RE = re.compile(r"(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH|PRIVATE)", re.IGNORECASE)


def append_security_audit(ws_root: Path, actor: str, scope: str, action: str, details: Dict[str, Any]) -> None:
    audit_dir = ws_root / ".ws" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    rec = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor_identity": actor,
        "requested_scope": scope,
        "post_auth_action": action,
        "details": details,
    }
    with open(audit_dir / "security_audit.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Open-Science WAL Reconciler & Security Sandbox/Credential/Audit Engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pre = sub.add_parser("pre-exec", help="Write PRE_EXEC intent log before invoking a tool/script")
    p_pre.add_argument("--task-dir", required=True)
    p_pre.add_argument("--call-id", required=True)
    p_pre.add_argument("--tool-cmd", required=True)
    p_pre.add_argument("--expected-outputs", required=True, help="Comma-separated relative output file paths")

    p_rec = sub.add_parser("reconcile-retry", help="Verify whether an interrupted/unacknowledged call actually succeeded on disk before retrying")
    p_rec.add_argument("--task-dir", required=True)
    p_rec.add_argument("--call-id", required=True)

    p_lin = sub.add_parser("bind-lineage", help="Bind figure/table outputs to exact script SHA256 and parameter snapshot")
    p_lin.add_argument("--task-dir", required=True)
    p_lin.add_argument("--run-id", required=True)
    p_lin.add_argument("--script-path", required=True)
    p_lin.add_argument("--params-json", required=True)
    p_lin.add_argument("--outputs", required=True, help="Comma-separated output files")

    p_srun = sub.add_parser("scrub-env-run", help="Execute command in credential-scrubbed environment with security audit logging")
    p_srun.add_argument("--ws-root", required=True)
    p_srun.add_argument("--task-dir", required=True)
    p_srun.add_argument("--actor", default="task_agent")
    p_srun.add_argument("command", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    if args.cmd == "pre-exec":
        task_dir = Path(args.task_dir).resolve()
        rec_dir = task_dir / "records"
        rec_dir.mkdir(parents=True, exist_ok=True)
        wal_path = rec_dir / "wal.json"
        wal = json.loads(wal_path.read_text(encoding="utf-8")) if wal_path.exists() else {}
        exp_outs = [x.strip() for x in args.expected_outputs.split(",") if x.strip()]
        wal[args.call_id] = {
            "call_id": args.call_id,
            "state": "PRE_EXEC_DISPATCHED",
            "tool_cmd": args.tool_cmd,
            "expected_outputs": exp_outs,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        wal_path.write_text(json.dumps(wal, ensure_ascii=False, indent=2), encoding="utf-8")
        emit_success("open_science.pre_exec", wal[args.call_id], task_dir=task_dir)

    elif args.cmd == "reconcile-retry":
        task_dir = Path(args.task_dir).resolve()
        wal_path = task_dir / "records" / "wal.json"
        if not wal_path.exists():
            emit_error("open_science.reconcile", "No WAL file found.", retriable=False, task_dir=task_dir)
        wal = json.loads(wal_path.read_text(encoding="utf-8"))
        entry = wal.get(args.call_id)
        if not entry:
            emit_error("open_science.reconcile", f"Call ID '{args.call_id}' not found in WAL.", retriable=False, task_dir=task_dir)

        exp_outs = entry.get("expected_outputs") or []
        verified_files: List[str] = []
        missing_files: List[str] = []
        for rel in exp_outs:
            p = task_dir / rel
            if p.exists() and p.stat().st_size > 0:
                verified_files.append(rel)
            else:
                missing_files.append(rel)

        already_succeeded = (len(exp_outs) > 0 and len(missing_files) == 0)
        if already_succeeded:
            entry["state"] = "POST_EXEC_RECONCILED_SUCCESS"
            entry["reconciled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            wal[args.call_id] = entry
            wal_path.write_text(json.dumps(wal, ensure_ascii=False, indent=2), encoding="utf-8")

        emit_success("open_science.reconcile_retry", {
            "call_id": args.call_id,
            "already_completed_on_disk": already_succeeded,
            "retry_decision": "SKIP_RETRY_ALREADY_DONE" if already_succeeded else "SAFE_TO_RETRY",
            "verified_outputs": verified_files,
            "missing_outputs": missing_files,
        }, task_dir=task_dir)

    elif args.cmd == "bind-lineage":
        task_dir = Path(args.task_dir).resolve()
        rec_dir = task_dir / "records"
        rec_dir.mkdir(parents=True, exist_ok=True)
        lin_path = rec_dir / "lineage.json"
        lin = json.loads(lin_path.read_text(encoding="utf-8")) if lin_path.exists() else {"runs": []}

        sp = Path(args.script_path).resolve()
        script_sha = hashlib.sha256(sp.read_bytes()).hexdigest() if sp.exists() else "missing"
        out_hashes: Dict[str, str] = {}
        for rel in [x.strip() for x in args.outputs.split(",") if x.strip()]:
            op = task_dir / rel
            if op.exists() and op.is_file():
                out_hashes[rel] = hashlib.sha256(op.read_bytes()).hexdigest()

        run_rec = {
            "run_id": args.run_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "script_path": str(args.script_path),
            "script_sha256": script_sha,
            "parameters": json.loads(args.params_json),
            "output_artifacts_sha256": out_hashes,
        }
        lin["runs"].append(run_rec)
        lin_path.write_text(json.dumps(lin, ensure_ascii=False, indent=2), encoding="utf-8")
        emit_success("open_science.bind_lineage", run_rec, task_dir=task_dir)

    elif args.cmd == "scrub-env-run":
        ws_root = Path(args.ws_root).resolve()
        task_dir = Path(args.task_dir).resolve()
        cmd = args.command
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        if not cmd:
            emit_error("security.scrub_env_run", "No command provided after --", retriable=False)

        # 清单 2: 密码不过模型 —— 剥离所有敏感环境变量
        clean_env: Dict[str, str] = {}
        scrubbed_keys: List[str] = []
        for k, v in os.environ.items():
            if SECRET_ENV_RE.search(k):
                scrubbed_keys.append(k)
            else:
                clean_env[k] = v

        proc = subprocess.run(cmd, cwd=str(task_dir), env=clean_env, capture_output=True, text=True, timeout=120)
        # 清单 3: 记录权限与后置动作审计日志
        append_security_audit(
            ws_root,
            actor=args.actor,
            scope=str(task_dir.name),
            action=" ".join(cmd),
            details={"returncode": proc.returncode, "scrubbed_secret_env_keys": scrubbed_keys},
        )
        emit_success("security.scrub_env_run", {
            "returncode": proc.returncode,
            "scrubbed_secret_env_count": len(scrubbed_keys),
            "scrubbed_keys": scrubbed_keys,
            "stdout": proc.stdout.strip()[:1000],
        }, task_dir=task_dir)


if __name__ == "__main__":
    main()
