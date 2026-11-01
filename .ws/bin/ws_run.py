#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_run.py — 进程组沙箱执行器（防 CodeBuddy IDE 孤儿进程泄漏与并发重跑 OOM 踩踏）
解决盲区 2（Agent 调起 R/Python 超时后残留孤儿进程吃满内存，叠加重试导致整机 OOM）。
核心机制：
1. 任务级进程锁 (.running.pid)：检测同任务是否已有存活的计算子进程，拒绝并发踩踏
2. os.setsid() 独立进程组：超时或异常退出时通过 os.killpg(pgid, SIGKILL) 连同孙子进程彻底清理
3. resource.setrlimit 内存硬上限与耗时统计（自动记录 execution_tokens_proxy 供 RRSI 评估复杂度成本 C(H)）
"""
import argparse
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

from ws_contract import emit_error, emit_success


def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe process-group runner with OOM and orphan protection")
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    parser.add_argument("--max-mem-gb", type=int, default=16, help="Address space cap in GB")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute (after --)")
    args = parser.parse_args()

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        emit_error("ws_run", "No command specified after --", retriable=False)

    task_dir = Path(args.task_dir).resolve()
    task_dir.mkdir(parents=True, exist_ok=True)
    pid_file = task_dir / ".running.pid"

    if pid_file.exists():
        try:
            old_info = json.loads(pid_file.read_text(encoding="utf-8"))
            old_pid = int(old_info.get("pid", -1))
            if old_pid > 0 and is_pid_alive(old_pid):
                emit_error(
                    "ws_run.concurrent_stampede_blocked",
                    f"Task already has a running compute process (PID {old_pid}: {old_info.get('cmd')}).",
                    retriable=True,
                    next_steps=[
                        f"Wait for PID {old_pid} to finish, or kill process group {old_pid} before starting a new run."
                    ],
                    task_dir=task_dir,
                )
        except Exception:
            pass

    max_bytes = args.max_mem_gb * 1024 * 1024 * 1024

    def _preexec() -> None:
        os.setsid()
        try:
            resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
        except Exception:
            pass

    t0 = time.time()
    proc = subprocess.Popen(
        cmd,
        cwd=str(task_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=_preexec,
    )
    pid_file.write_text(json.dumps({"pid": proc.pid, "cmd": cmd, "started_at": t0}), encoding="utf-8")

    try:
        stdout, stderr = proc.communicate(timeout=args.timeout)
        elapsed = round(time.time() - t0, 3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            proc.kill()
        if pid_file.exists():
            pid_file.unlink()
        emit_error(
            "ws_run.timeout",
            f"Command timed out after {args.timeout}s. Entire process group (PGID {proc.pid}) was cleanly terminated.",
            retriable=True,
            next_steps=["Optimize script or downsample input before retrying."],
            task_dir=task_dir,
        )

    if pid_file.exists():
        pid_file.unlink()

    if proc.returncode != 0:
        emit_error(
            "ws_run.nonzero_exit",
            f"Command exited with code {proc.returncode}: {stderr.strip()[:400]}",
            retriable=True,
            next_steps=["Inspect stderr output and fix script parameters."],
            data={"returncode": proc.returncode, "stdout": stdout[-1000:], "stderr": stderr[-1000:], "elapsed_sec": elapsed},
            task_dir=task_dir,
        )

    emit_success("ws_run.completed", {
        "returncode": 0,
        "elapsed_sec": elapsed,
        "stdout": stdout[-2000:],
        "stderr": stderr[-1000:],
    }, task_dir=task_dir)


if __name__ == "__main__":
    main()
