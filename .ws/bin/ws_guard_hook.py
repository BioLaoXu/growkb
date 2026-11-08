#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_guard_hook.py — CodeBuddy IDE Hooks 守门员 v3.5
新增吸收自 DGM (防 Agent 自关幻觉检测)、Terminal Wrench (防评测劫持) 与 molten (被测基准与 Agent 物理隔离)：
1. 严禁 Agent 修改评测与护栏内核文件 (ws_bench.py, ws_bio_verifier.py, ws_guard_hook.py, ws_contract.py)
2. 严禁 Agent 读取或写隐藏真值保险箱 (.ws/.sealed_vault/ 或 .ground_truth.yaml)
3. 严禁 Agent 直接写 .grade_receipt.json 或 META.yaml
"""
import argparse
import json
import re
import sys
from pathlib import Path

SEALED_KERNEL_FILES = (
    "ws_bench.py",
    "ws_bio_verifier.py",
    "ws_guard_hook.py",
    "ws_contract.py",
    ".grade_receipt.json",
    "SEALED_KERNEL_MANIFEST.json",
)
FORBIDDEN_READ_WRITE_PATTERNS = (
    ".sealed_vault",
    ".ground_truth.yaml",
)


def handle_session_start(ws_root: Path) -> None:
    inbox_dir = ws_root / ".inbox"
    projects_dir = ws_root / "projects"
    pending_cards = list(inbox_dir.glob("*.yaml")) if inbox_dir.exists() else []
    wip_count = 0
    if projects_dir.exists():
        for m in projects_dir.rglob("META.yaml"):
            txt = m.read_text(encoding="utf-8", errors="ignore")
            if "status: wip" in txt or 'status: "wip"' in txt:
                wip_count += 1
    sentinel = (
        f"[Workspace Sentinel] Inbox pending cards: {len(pending_cards)} | Active WIP tasks: {wip_count}. "
        f"(Do NOT inspect .inbox unless the user asks to accept/dispatch new tasks.)"
    )
    print(json.dumps({"ok": True, "hook": "SessionStart", "inject_context": sentinel}, ensure_ascii=False))


def handle_pre_tool_use(tool_name: str, tool_input_json: str) -> None:
    try:
        params = json.loads(tool_input_json) if tool_input_json else {}
    except Exception:
        params = {"raw": tool_input_json}

    raw_str = json.dumps(params, ensure_ascii=False)

    # 1. molten / Terminal Wrench 铁律：禁止对真值保险箱的路径级访问（文档正文提及不算，防误伤）
    def _touches_vault(txt: str) -> bool:
        return ('.sealed_vault' in txt) or ('.ground_truth.yaml' in txt)

    _write_tools = ("write_to_file", "edit_file", "replace_in_file")
    _path_params = ("filePath", "target_file", "file_path", "path")
    _hit = False
    if tool_name in _write_tools:
        _hit = any(_touches_vault(str(params.get(k, ""))) for k in _path_params)
    elif tool_name in ("execute_bash", "bash", "run_command", "execute_command", "read_file"):
        _hit = _touches_vault(str(params.get("command", "")) or str(params.get("filePath", "")) or raw_str)
    if _hit:
        print(json.dumps({
            "ok": False,
            "decision": "block",
            "reason": "ANTI-REWARD-HACKING GUARD: Path-level access to the sealed vault is forbidden (benchmark answer leakage protection).",
        }))
        sys.exit(2)

    # 2. DGM 防自关幻觉检测铁律：禁止修改受保护的评测器与护栏脚本或伪造 .grade_receipt.json
    if tool_name in ("write_to_file", "edit_file", "replace_in_file", "execute_bash", "bash"):
        for kernel_f in SEALED_KERNEL_FILES:
            if kernel_f in raw_str and (
                tool_name in ("write_to_file", "edit_file", "replace_in_file")
                or re.search(rf"(?:>|rm|mv|cp|sed\s+-i|chmod)\s+.*{re.escape(kernel_f)}", raw_str)
            ):
                print(json.dumps({
                    "ok": False,
                    "decision": "block",
                    "reason": f"DGM SELF-MODIFICATION GUARD: '{kernel_f}' is part of the sealed evaluation kernel and cannot be modified or forged by the Agent.",
                }))
                sys.exit(2)

    # 3. 拦截对 META.yaml 的直接文件写操作（强制走 ws_meta.py）
    if tool_name in ("write_to_file", "edit_file", "replace_in_file") and "META.yaml" in raw_str:
        print(json.dumps({
            "ok": False,
            "decision": "block",
            "reason": "Direct file write to META.yaml is forbidden by Harness guardrail. Use '.ws/bin/ws_meta.py patch' with --expected-rev instead.",
        }))
        sys.exit(2)

    # 4. 拦截在 projects/ 目录下直接 rm -rf 或重定向覆盖 META.yaml
    if tool_name in ("execute_bash", "bash", "run_command"):
        cmd = str(params.get("command", raw_str))
        if re.search(r"rm\s+-[rf]+\s+.*projects/", cmd):
            print(json.dumps({
                "ok": False,
                "decision": "block",
                "reason": "Direct 'rm -rf' inside projects/ is forbidden. Only 'planned' tasks may be moved to .trash/ via workspace scripts.",
            }))
            sys.exit(2)
        if re.search(r">\s*[^\s]*META\.yaml", cmd):
            print(json.dumps({
                "ok": False,
                "decision": "block",
                "reason": "Shell redirection into META.yaml is forbidden. Use '.ws/bin/ws_meta.py'.",
            }))
            sys.exit(2)

    print(json.dumps({"ok": True, "decision": "allow"}))


def main() -> None:
    parser = argparse.ArgumentParser(description="CodeBuddy Hook Guard v3.5")
    sub = parser.add_subparsers(dest="hook", required=True)

    p_ss = sub.add_parser("session-start")
    p_ss.add_argument("--ws-root", required=True)

    p_pre = sub.add_parser("pre-tool-use")
    p_pre.add_argument("--tool-name", default="")
    p_pre.add_argument("--tool-input", default="{}")

    args = parser.parse_args()
    if args.hook == "session-start":
        handle_session_start(Path(args.ws_root).resolve())
    elif args.hook == "pre-tool-use":
        tool_name, tool_input = args.tool_name, args.tool_input
        # CodeBuddy 实际协议：工具输入经 stdin JSON 传入（{tool_name, tool_input}）
        if not tool_name or tool_input == "{}":
            try:
                _raw = sys.stdin.read()
                _data = json.loads(_raw) if _raw.strip() else {}
                tool_name = tool_name or str(_data.get("tool_name") or _data.get("toolName") or "")
                _ti = _data.get("tool_input") or _data.get("toolInput")
                if _ti is not None:
                    tool_input = json.dumps(_ti, ensure_ascii=False)
            except Exception:
                pass  # stdin 解析失败 → fail-open
        if not tool_name:
            # 拿不到工具名时必须放行，绝不因 hook 自身故障阻断正常工作
            print(json.dumps({"ok": True, "decision": "allow", "note": "fail-open: no tool_name"}))
            sys.exit(0)
        handle_pre_tool_use(tool_name, tool_input)


if __name__ == "__main__":
    main()
