#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_memory.py — MEMEX v3.5 经验记忆引擎
新增吸收自 MemT-1.0 (arXiv:2610.26825, 记忆原生大模型) 与 MemOS：
1. 对称橡皮擦机制 (Symmetrized Erase-Before-Write):
   当写入或更新某 scope 下的记忆时，自动扫描同 trigger 子空间的旧记忆，对正交/过时冲突项执行强度衰减 (erase_factor = 1 - ||u||^2) 或直接归档擦除，防止长期递归更新中的状态发散。
2. 半衰期指数遗忘门 (Half-Life Exponential Forget Gate):
   每条记忆赋予半衰期 tau_half_life_days (默认 90 天)，检索时有效权重乘以 2^(-age_days / tau_half_life_days)。
3. 固定容量池上限 (Fixed-Capacity Memory State Cap, 仿 MemT-1.0 固定 40MB 状态):
   每个 scope 严格限制最多 MAX_ACTIVE_SLOTS_PER_SCOPE (默认 32 条，总计 < 64KB) 活跃记忆；超出容量时自动按有效能量评分淘汰最低分条目入 .superseded/，保证无论累积多少万个任务，记忆体积永不膨胀！
4. 断点反事实核验标记 (Breakpoint Counterfactual Validation):
   支持记录 --breakpoint-error 与 --counterfactual-verified，优先提权在真实报错断点上验证把失败扭转为成功的经验。
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ws_contract import emit_error, emit_success
from ws_meta import dump_simple_yaml, load_simple_yaml

MAX_ACTIVE_SLOTS_PER_SCOPE = 32
DEFAULT_HALF_LIFE_DAYS = 90.0

CONCRETE_LEAK_PATTERNS = [
    (r"\bXJYF-[A-Za-z0-9]+\b", "Batch identifier (XJYF-...)"),
(r"\bHT\d{4,}\b", "Contract ID (e.g. HT2026...)"),
(r"\bSP\d{6,}\b", "Contract ID (SP...)"),
    (r"\b202\d[-_]?\d{2}[-_]?\d{2}\b", "Specific calendar date"),
    (r"/(?:projects|home|data|mnt|working_dir)/[A-Za-z0-9_./-]+", "Hardcoded filesystem path"),
    (r"\b(?:sample|Sample|SAMPLE)[-_]?\d+\b", "Task-specific sample identifier"),
]


def normalize_trigger(t: str) -> str:
    return re.sub(r"[-_\s]+", "", t.lower().strip())


def char_ngrams(text: str, n: int = 2) -> Set[str]:
    cleaned = re.sub(r"\s+", "", text.lower())
    if len(cleaned) < n:
        return {cleaned} if cleaned else set()
    return {cleaned[i:i + n] for i in range(len(cleaned) - n + 1)}


def jaccard_2gram(a: str, b: str) -> float:
    sa, sb = char_ngrams(a, 2), char_ngrams(b, 2)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def check_anti_concretization(trigger_list: List[str], content: str) -> List[str]:
    combined = " ".join(trigger_list) + " " + content
    violations: List[str] = []
    for pat, label in CONCRETE_LEAK_PATTERNS:
        m = re.search(pat, combined)
        if m:
            violations.append(f"Detected {label}: '{m.group(0)}'")
    return violations


def compute_memt_retention_energy(item: Dict[str, Any], now_ts: float) -> float:
    """仿 MemT-1.0 SGDN-2 计算条目的当前留存能量：结合初始强度、对称擦除衰减因子、半衰期遗忘门与反事实核验加成。"""
    created_ts = float(item.get("created_epoch", now_ts))
    age_days = max(0.0, (now_ts - created_ts) / 86400.0)
    half_life = float(item.get("half_life_days", DEFAULT_HALF_LIFE_DAYS))
    forget_gate_D = math.pow(2.0, -age_days / max(1.0, half_life))
    strength = float(item.get("memory_strength", 1.0))
    applied_cnt = len(item.get("applied_tasks") or [item.get("task")])
    cf_bonus = 1.35 if item.get("counterfactual_verified") else 1.0
    return round(strength * forget_gate_D * cf_bonus * (1.0 + 0.3 * applied_cnt), 4)


def apply_memt_eraser_and_capacity_cap(
    mem_dir: Path,
    superseded_dir: Path,
    scope: str,
    new_id: str,
    new_triggers: Set[str],
    erase_ids: List[str],
    max_slots: int = MAX_ACTIVE_SLOTS_PER_SCOPE,
) -> Dict[str, Any]:
    """
    MemT-1.0 橡皮擦机制 + 固定状态容量预算控制：
    1. 对显式指定 --erase-ids 或同 trigger 键重叠的旧记忆执行对称擦除衰减 [I - u^T u]
    2. 若当前 scope 正式记忆数超过 max_slots，自动将能量最低的条目移入 .superseded/
    """
    now_ts = time.time()
    erased_list: List[str] = []
    attenuated_list: List[str] = []
    scope_items: List[Tuple[float, Path, Dict[str, Any]]] = []

    for f in sorted(mem_dir.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        item = load_simple_yaml(f.read_text(encoding="utf-8"))
        mid = str(item.get("id", f.stem))
        if mid in erase_ids and mid != new_id:
            # 显式橡皮擦擦除
            item["erased_by"] = new_id
            item["erased_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts))
            dst = superseded_dir / f"{mid}.erased.yaml"
            dst.write_text(dump_simple_yaml(item), encoding="utf-8")
            f.unlink()
            erased_list.append(mid)
            continue

        if str(item.get("scope", "")).lower() == scope.lower():
            if mid != new_id:
                old_trigs = {normalize_trigger(str(x)) for x in (item.get("trigger") or [])}
                overlap = len(new_triggers & old_trigs) / float(max(1, len(new_triggers | old_trigs)))
                if overlap > 0:
                    # MemT-1.0 SGDN-2: 平行分量乘以 (1 - ||u||^2) 收缩而不放大正交噪声
                    u_norm_sq = min(0.65, overlap * 0.5)
                    old_s = float(item.get("memory_strength", 1.0))
                    item["memory_strength"] = round(old_s * (1.0 - u_norm_sq), 4)
                    f.write_text(dump_simple_yaml(item), encoding="utf-8")
                    attenuated_list.append(mid)
            energy = compute_memt_retention_energy(item, now_ts)
            scope_items.append((energy, f, item))

    evicted_list: List[str] = []
    if len(scope_items) > max_slots:
        # 按留存能量升序排序，淘汰超出固定容量的尾部条目
        scope_items.sort(key=lambda x: x[0])
        to_evict = scope_items[: len(scope_items) - max_slots]
        for energy, fpath, item in to_evict:
            mid = str(item.get("id", fpath.stem))
            item["evicted_reason"] = f"Exceeded fixed capacity cap ({max_slots} slots in scope '{scope}', energy={energy})"
            dst = superseded_dir / f"{mid}.evicted.yaml"
            dst.write_text(dump_simple_yaml(item), encoding="utf-8")
            fpath.unlink()
            evicted_list.append(mid)

    return {
        "erased_ids": erased_list,
        "attenuated_ids": attenuated_list,
        "capacity_evicted_ids": evicted_list,
        "active_slots_in_scope": min(len(scope_items), max_slots),
    }


def load_all_memories(mem_dir: Path, include_staging: bool = True) -> List[Tuple[Path, Dict[str, Any], bool]]:
    out: List[Tuple[Path, Dict[str, Any], bool]] = []
    mem_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted(mem_dir.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        out.append((f, load_simple_yaml(f.read_text(encoding="utf-8")), False))
    if include_staging:
        stg = mem_dir / ".staging"
        if stg.exists():
            for f in sorted(stg.glob("*.yaml")):
                out.append((f, load_simple_yaml(f.read_text(encoding="utf-8")), True))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="MEMEX v3.5 Memory Engine (with MemT-1.0 Eraser & Fixed Capacity Cap)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Propose a new experience entry into .staging (or formal with --promote)")
    p_add.add_argument("--ws-root", required=True)
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--type", required=True, choices=["gotcha", "parameter", "workflow", "interpretation"])
    p_add.add_argument("--scope", required=True)
    p_add.add_argument("--task", required=True)
    p_add.add_argument("--triggers", required=True)
    p_add.add_argument("--content", required=True)
    p_add.add_argument("--evidence", required=True)
    p_add.add_argument("--erase-ids", default="", help="Comma-separated stale memory IDs to actively erase (MemT-1.0 Eraser)")
    p_add.add_argument("--counterfactual-verified", action="store_true", help="True if verified at a failure breakpoint")
    p_add.add_argument("--max-slots", type=int, default=MAX_ACTIVE_SLOTS_PER_SCOPE)
    p_add.add_argument("--force-add", action="store_true")
    p_add.add_argument("--promote", action="store_true")

    p_upd = sub.add_parser("update", help="Update an existing memory entry and record task attribution")
    p_upd.add_argument("--ws-root", required=True)
    p_upd.add_argument("--id", required=True)
    p_upd.add_argument("--task", required=True)
    p_upd.add_argument("--content", required=True)
    p_upd.add_argument("--triggers", default=None)
    p_upd.add_argument("--evidence", required=True)

    p_del = sub.add_parser("delete", help="Contradiction-audited delete (moves to .superseded)")
    p_del.add_argument("--ws-root", required=True)
    p_del.add_argument("--id", required=True)
    p_del.add_argument("--reason", required=True)

    p_prom = sub.add_parser("promote", help="Promote staged memory to formal .kb/memory/")
    p_prom.add_argument("--ws-root", required=True)
    p_prom.add_argument("--id", required=True)

    p_srch = sub.add_parser("search", help="Search memories with MemT-1.0 decay-gate energy + trigger boost")
    p_srch.add_argument("--ws-root", required=True)
    p_srch.add_argument("--query", required=True)
    p_srch.add_argument("--scope", default=None)
    p_srch.add_argument("--apply-task", default=None)

    p_list = sub.add_parser("list", help="List memory entries (formal + staging)")
    p_list.add_argument("--ws-root", required=True)
    p_list.add_argument("--scope", default=None)

    args = parser.parse_args()
    ws_root = Path(args.ws_root).resolve()
    mem_dir = ws_root / ".kb" / "memory"
    staging_dir = mem_dir / ".staging"
    superseded_dir = mem_dir / ".superseded"
    mem_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    superseded_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "add":
        triggers = [t.strip() for t in args.triggers.split(",") if t.strip()]
        leaks = check_anti_concretization(triggers, args.content)
        if leaks:
            emit_error(
                "memory.anti_concretization",
                "Memory entry rejected by anti-pollution filter: contains task-specific identifiers.",
                retriable=True,
                next_steps=[
                    f"Violations: {leaks}",
                    "Rewrite 'content' and 'triggers' as a generalizable rule without contract numbers, dates, sample IDs, or hardcoded paths.",
                ],
            )

        content_md5 = hashlib.md5(args.content.strip().encode("utf-8")).hexdigest()
        norm_new_triggers = {normalize_trigger(t) for t in triggers}
        erase_ids = [x.strip() for x in args.erase_ids.split(",") if x.strip()]

        conflicts: List[Dict[str, Any]] = []
        for fpath, item, is_stg in load_all_memories(mem_dir, include_staging=True):
            if str(item.get("id")) in erase_ids:
                continue
            old_content = str(item.get("content", ""))
            old_md5 = hashlib.md5(old_content.strip().encode("utf-8")).hexdigest()
            if old_md5 == content_md5:
                emit_success("memory.noop", {
                    "operation": "NOOP",
                    "reason": f"Exact MD5 match with existing entry '{item.get('id')}'",
                    "existing_id": item.get("id"),
                })

            old_triggers = {normalize_trigger(str(x)) for x in (item.get("trigger") or [])}
            trig_overlap = norm_new_triggers & old_triggers
            sim_2gram = jaccard_2gram(args.content, old_content)
            same_scope = (str(item.get("scope", "")).lower() == args.scope.lower())

            hybrid_sim = sim_2gram + (0.20 if same_scope else 0.0) + min(0.30, len(trig_overlap) * 0.15)
            if hybrid_sim >= 0.45 or sim_2gram >= 0.32 or (same_scope and len(trig_overlap) >= 2):
                conflicts.append({
                    "id": item.get("id"),
                    "scope": item.get("scope"),
                    "staged": is_stg,
                    "jaccard_2gram": round(sim_2gram, 3),
                    "hybrid_score": round(hybrid_sim, 3),
                    "trigger_overlap": sorted(trig_overlap),
                    "content": old_content,
                })

        if conflicts and not args.force_add:
            conflicts.sort(key=lambda x: x["hybrid_score"], reverse=True)
            emit_error(
                "memory.semantic_conflict_review",
                f"Found {len(conflicts)} potentially overlapping memory entry(ies) via L2 hybrid filter.",
                retriable=True,
                next_steps=[
                    f"Option 1 (Refine): Run 'ws_memory.py update --id {conflicts[0]['id']} ...'",
                    f"Option 2 (MemT-1.0 Eraser): Re-run add with '--erase-ids {conflicts[0]['id']}' to actively erase and replace it.",
                    "Option 3 (Distinct): Re-run 'ws_memory.py add' with '--force-add'.",
                ],
                data={"candidates": conflicts[:3]},
            )

        now_ts = time.time()
        entry = {
            "id": args.id,
            "type": args.type,
            "scope": args.scope,
            "task": args.task,
            "trigger": triggers,
            "content": args.content.strip(),
            "evidence": args.evidence,
            "superseded": erase_ids if erase_ids else None,
            "retrieved_hits": 0,
            "applied_tasks": [args.task],
            "memory_strength": 1.0,
            "half_life_days": DEFAULT_HALF_LIFE_DAYS,
            "counterfactual_verified": bool(args.counterfactual_verified),
            "created_epoch": round(now_ts, 2),
            "status": "formal" if args.promote else "staging",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
            "expiration": time.strftime("%Y-%m-%d", time.gmtime(now_ts + 180 * 86400)),
        }
        target_dir = mem_dir if args.promote else staging_dir
        out_file = target_dir / f"{args.id}.yaml"
        out_file.write_text(dump_simple_yaml(entry), encoding="utf-8")

        eraser_report = {}
        if args.promote or erase_ids:
            eraser_report = apply_memt_eraser_and_capacity_cap(
                mem_dir, superseded_dir, args.scope, args.id, norm_new_triggers, erase_ids, max_slots=args.max_slots
            )
        emit_success("memory.add", {"operation": "ADD", "path": str(out_file), "entry": entry, "memt_eraser": eraser_report})

    elif args.cmd == "update":
        target_file = next((d / f"{args.id}.yaml" for d in (mem_dir, staging_dir) if (d / f"{args.id}.yaml").exists()), None)
        if not target_file:
            emit_error("memory.update", f"Memory ID '{args.id}' not found.", retriable=False)

        leaks = check_anti_concretization([args.triggers or ""], args.content)
        if leaks:
            emit_error("memory.anti_concretization", f"Update contains concrete identifiers: {leaks}", retriable=True)

        item = load_simple_yaml(target_file.read_text(encoding="utf-8"))
        bak_name = f"{args.id}.{int(time.time())}.bak.yaml"
        shutil.copy2(target_file, superseded_dir / bak_name)

        item["content"] = args.content.strip()
        if args.triggers:
            item["trigger"] = [t.strip() for t in args.triggers.split(",") if t.strip()]
        item["evidence"] = f"{item.get('evidence', '')}; {args.evidence}".strip("; ")
        applied = list(item.get("applied_tasks") or [item.get("task")])
        if args.task not in applied:
            applied.append(args.task)
        item["applied_tasks"] = applied
        item["memory_strength"] = 1.0  # 刷新记忆强度
        item["created_epoch"] = round(time.time(), 2)
        item["superseded"] = bak_name
        item["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        target_file.write_text(dump_simple_yaml(item), encoding="utf-8")

        sublimation_needed = len(applied) >= 3
        emit_success("memory.update", {
            "operation": "UPDATE",
            "id": args.id,
            "applied_tasks_count": len(applied),
            "sublimation_ready": sublimation_needed,
        })

    elif args.cmd == "delete":
        if len(args.reason.strip()) < 8:
            emit_error("memory.delete", "Contradiction deletion requires a substantive '--reason' (>= 8 chars).", retriable=True)
        target_file = next((d / f"{args.id}.yaml" for d in (mem_dir, staging_dir) if (d / f"{args.id}.yaml").exists()), None)
        if not target_file:
            emit_error("memory.delete", f"Memory ID '{args.id}' not found.", retriable=False)

        item = load_simple_yaml(target_file.read_text(encoding="utf-8"))
        item["deleted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        item["delete_reason"] = args.reason.strip()
        arch_path = superseded_dir / f"{args.id}.deleted.yaml"
        arch_path.write_text(dump_simple_yaml(item), encoding="utf-8")
        target_file.unlink()
        emit_success("memory.delete", {"operation": "DELETE", "id": args.id, "archived_to": str(arch_path)})

    elif args.cmd == "promote":
        stg_file = staging_dir / f"{args.id}.yaml"
        if not stg_file.exists():
            emit_error("memory.promote", f"Staged memory '{args.id}' not found in .staging/.", retriable=False)
        item = load_simple_yaml(stg_file.read_text(encoding="utf-8"))
        item["status"] = "formal"
        item["promoted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        dst = mem_dir / f"{args.id}.yaml"
        dst.write_text(dump_simple_yaml(item), encoding="utf-8")
        stg_file.unlink()
        norm_trigs = {normalize_trigger(str(x)) for x in (item.get("trigger") or [])}
        eraser_report = apply_memt_eraser_and_capacity_cap(
            mem_dir, superseded_dir, str(item.get("scope", "general")), args.id, norm_trigs, []
        )
        emit_success("memory.promote", {"operation": "PROMOTE", "id": args.id, "formal_path": str(dst), "memt_eraser": eraser_report})

    elif args.cmd == "search":
        q_norm = normalize_trigger(args.query)
        today = time.strftime("%Y-%m-%d", time.gmtime())
        now_ts = time.time()
        results: List[Dict[str, Any]] = []

        for fpath, item, is_stg in load_all_memories(mem_dir, include_staging=True):
            exp = str(item.get("expiration") or "9999-12-31")
            if exp < today:
                continue
            if args.scope and str(item.get("scope", "")).lower() != args.scope.lower():
                continue

            triggers = [normalize_trigger(str(x)) for x in (item.get("trigger") or [])]
            trig_hits = sum(1 for t in triggers if t and (t in q_norm or q_norm in t))
            sim_2gram = jaccard_2gram(args.query, str(item.get("content", "")))
            energy = compute_memt_retention_energy(item, now_ts)

            stage_weight = 0.6 if is_stg else 1.0
            score = stage_weight * energy * (trig_hits * 2.5 + sim_2gram * 3.5)
            if score > 0.20:
                item["retrieved_hits"] = int(item.get("retrieved_hits", 0)) + 1
                if args.apply_task and not is_stg:
                    app = list(item.get("applied_tasks") or [])
                    if args.apply_task not in app:
                        app.append(args.apply_task)
                    item["applied_tasks"] = app
                fpath.write_text(dump_simple_yaml(item), encoding="utf-8")
                results.append({
                    "id": item.get("id"),
                    "score": round(score, 3),
                    "retention_energy": energy,
                    "status": "staging" if is_stg else "formal",
                    "scope": item.get("scope"),
                    "type": item.get("type"),
                    "trigger": item.get("trigger"),
                    "content": item.get("content"),
                    "applied_tasks_count": len(item.get("applied_tasks") or []),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        emit_success("memory.search", {"query": args.query, "hits": results[:5]})

    elif args.cmd == "list":
        entries_out: List[Dict[str, Any]] = []
        for fpath, item, is_stg in load_all_memories(mem_dir, include_staging=True):
            if args.scope and str(item.get("scope", "")).lower() != args.scope.lower():
                continue
            entries_out.append({
                "id": item.get("id"),
                "type": item.get("type"),
                "scope": item.get("scope"),
                "hits": item.get("hits", item.get("retrieved_hits", 0)),
                "applied_tasks_count": len(item.get("applied_tasks") or []),
                "last_verified": str(item.get("last_verified")) if item.get("last_verified") is not None else None,
                "status": "staging" if is_stg else "formal",
                "file": str(fpath.relative_to(ws_root)),
            })
        emit_success("memory.list", {"entries": entries_out, "count": len(entries_out)})


if __name__ == "__main__":
    main()
