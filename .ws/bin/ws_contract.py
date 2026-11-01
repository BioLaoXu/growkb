#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_contract.py — 统一事件/错误契约与连续失败熔断器 (Circuit Breaker)
符合 BioMCP / OpenHands / ToolUniverse 范式：
{
  "ok": bool,
  "action": str,
  "is_error": bool,
  "error": {"message": str, "retriable": bool, "next_steps": [str], "streak": int} | None,
  "data": dict
}
"""
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

STREAK_LIMIT = 2  # 同一任务同一 action 连续失败 >= 2 次自动熔断 retriable=False


def _streak_file(task_dir: Optional[Path]) -> Optional[Path]:
    if not task_dir:
        return None
    p = Path(task_dir)
    if p.exists() and p.is_dir():
        return p / ".error_streak.json"
    return None


def record_outcome(task_dir: Optional[Path], action: str, is_error: bool) -> int:
    sf = _streak_file(task_dir)
    if not sf:
        return 1 if is_error else 0
    state: Dict[str, Any] = {}
    if sf.exists():
        try:
            state = json.loads(sf.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    if not is_error:
        if action in state:
            del state[action]
            sf.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    entry = state.get(action, {"count": 0, "first_ts": time.time()})
    entry["count"] = int(entry.get("count", 0)) + 1
    entry["last_ts"] = time.time()
    state[action] = entry
    sf.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry["count"]


def emit_success(
    action: str,
    data: Optional[Dict[str, Any]] = None,
    task_dir: Optional[Path] = None,
    stage_hint: Optional[str] = None,
    exit_code: int = 0,
) -> Dict[str, Any]:
    record_outcome(task_dir, action, is_error=False)
    payload: Dict[str, Any] = {
        "ok": True,
        "action": action,
        "is_error": False,
        "error": None,
        "data": data or {},
    }
    if stage_hint:
        payload["stage_hint"] = stage_hint
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if exit_code >= 0:
        sys.exit(exit_code)
    return payload


def emit_error(
    action: str,
    message: str,
    retriable: bool = True,
    next_steps: Optional[List[str]] = None,
    data: Optional[Dict[str, Any]] = None,
    task_dir: Optional[Path] = None,
    scientific_violation: bool = False,
    exit_code: int = 1,
) -> Dict[str, Any]:
    streak = record_outcome(task_dir, action, is_error=True)
    steps = list(next_steps or ["Inspect error message and verify input parameters."])

    # 盲区4加固：科学参数越界或连续失败 >= STREAK_LIMIT 时强制熔断，防止静默降标自愈
    if scientific_violation:
        retriable = False
        steps = [
            "SCIENTIFIC GUARDRAIL TRIGGERED: Do NOT relax statistical thresholds (e.g. FDR/padj/min_replicates) to force non-empty output.",
            "Transition task status to 'blocked' via ws_meta.py and ask human reviewer for confirmation, or use the negative-result report section.",
        ]
    elif retriable and streak >= STREAK_LIMIT:
        retriable = False
        steps = [
            f"CIRCUIT BREAKER TRIPPED: Action '{action}' failed {streak} times consecutively.",
            "Stop automatic retry loops immediately. Record the blocker in META.yaml notes, set status to 'blocked', and ask the human user.",
        ]

    payload: Dict[str, Any] = {
        "ok": False,
        "action": action,
        "is_error": True,
        "error": {
            "message": message,
            "retriable": retriable,
            "streak": streak,
            "next_steps": steps,
        },
        "data": data or {},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if exit_code >= 0:
        sys.exit(exit_code)
    return payload
