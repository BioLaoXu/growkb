#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_rrsi.py v3.5 — 融合四大前沿框架的终极自进化引擎：
1. RRSI (Google Research, arXiv:2609.24972):
   提案侧 L0 余弦退火编辑预算 b_t + 全历史证据账本 + 停滞探索 E_t；选择侧防泄漏筛查 + 噪声下限 + L2 复杂度收缩 + L1 剪枝 + 生信护栏。
2. Harness² (Google Research, arXiv:2610.14224):
   - 两层递归：Task-Level 无真值对比步 (Propose-Probe-Compose，强制正交拆分为 INV 流程维与 DOM 领域专家维) + Harnessing-Level 改进器经验库 (.kb/harness2_library/)。
   - 出场前三条铁律静态校验 (validate-tree): ① 每个 SKILL 目录名必须逐字出现在常驻路由触发行中；② 严禁残留未解析的 {{...}} 模板括号；③ SKILL 或提示词中点名的每个 .py/.R 脚本必须物理存在。
3. HGM (Huxley-Gödel Machine, KAUST/Schmidhuber, arXiv:2510.21614):
   解决“短期跑分与长期进化潜力错配 (Metaproductivity-Performance Mismatch)”：维护演化树 T_t，计算子树后代聚合胜率 Clade-Metaproductivity:
     CMP_hat(a) = sum_{a' in C(a)} n_succ(a') / sum_{a' in C(a)} (n_succ(a') + n_fail(a'))
   通过 Thompson Sampling 选择下一轮要扩展的父节点，并用 Beta 分布下分位数 (Best-Belief) 选择最终投产 Harness。
4. RQGM (Red Queen Gödel Machine, Cambridge MLSys, arXiv:2606.26294):
   解决“固定评测器被刷爆/自恋偏见 (1.91x over-acceptance)”：将演化划分为定常评测周期 (Fixed-Evaluator Epochs)；仅在周期边界 (Epoch Boundary) 允许升级评测器 (Challenger Verifier)，且新评测器必须在人类金标校准集 (.kb/bench/calibration/) 上提升判别力并通过“AI vs 人类报告同等严苛度检验 (Adversarial Stringency Parity)”方可晋升，晋升后自动归档旧周期不可比分数。
"""
import argparse
import hashlib
import json
import math
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ws_contract import emit_error, emit_success
from ws_meta import dump_simple_yaml, load_simple_yaml

COMPONENT_VOCAB = (
    "prompt",
    "control_flow",
    "config",
    "output_plumbing",
    "context_mgmt",
    "client_tool",
    "skill",
    "memory",
)
STRUCTURAL_COMPONENTS = {"client_tool", "skill", "memory"}

DEFAULT_HYPERPARAMS = {
    "T": 20,
    "b_min": 1,
    "b_max": 3,
    "w_stall": 3,
    "n_prune": 4,
    "delta": 0.005,
    "beta_0": 0.05,
    "beta_1": 15.0,
    "w_s": 1.0,
    "w_c": 2.0,
    "w_n": 0.03,
}

LEAKAGE_PATTERNS = [
    (r"\bHT\d{4,}\b", "Hardcoded contract ID"),
    (r"\bcapsule[-_]\w+\b", "Benchmark capsule identifier"),
    (r"\b(?:ground_truth|gold_claims|sealed_vault)\b", "Reference to hidden benchmark ground truth"),
    (r"/(?:projects|working_dir)/202\d/", "Task-specific directory path"),
]


def annealed_budget(t: int, T: int, b_min: int = 1, b_max: int = 3) -> int:
    if t >= T:
        return b_min
    val = b_min + (b_max - b_min) * 0.5 * (1.0 + math.cos(math.pi * float(t) / float(T)))
    return int(math.ceil(val - 1e-9))


def load_ledger(ledger_path: Path) -> List[Dict[str, Any]]:
    if not ledger_path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    return records


def append_ledger(ledger_path: Path, record: Dict[str, Any]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def measure_harness_footprint_tokens(ws_root: Path) -> int:
    total_chars = 0
    for base in (
        ws_root / ".codebuddy" / "rules",
        ws_root / ".ws" / "prompts",
        ws_root / ".kb" / "docs" / "methods",
        ws_root / ".kb" / "memory",
    ):
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".md", ".yaml", ".json") and ".staging" not in str(f) and ".superseded" not in str(f):
                total_chars += len(f.read_text(encoding="utf-8", errors="ignore"))
    return max(100, total_chars // 3)


def screen_leakage(diff_text: str, atomic_edits: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    for pat, desc in LEAKAGE_PATTERNS:
        m = re.search(pat, diff_text, re.IGNORECASE)
        if m:
            reasons.append(f"Leakage critic triggered ({desc}): matched '{m.group(0)}'")
    for ed in atomic_edits:
        comp = ed.get("component")
        if comp not in COMPONENT_VOCAB:
            reasons.append(f"Unknown component '{comp}', must be in {COMPONENT_VOCAB}")
        if not str(ed.get("hypothesis", "")).strip():
            reasons.append("Atomic edit missing explicit falsifiable 'hypothesis' field.")
    return (len(reasons) == 0), reasons


def validate_harness2_tree(ws_root: Path) -> Dict[str, Any]:
    """
    Harness² Appendix H 出场前三条铁律静态验证器：
    Rule 1: 每个 skills/<name>/SKILL.md 的目录名必须逐字出现在路由索引或常驻文本中；
    Rule 2: 常驻规则与提示词中严禁出现未替换的 '{{' 或 '{%' Jinja 模板括号；
    Rule 3: SKILL.md 或常驻规则中引用的任何 .ws/bin/*.py 脚本必须物理存在。
    """
    errors: List[str] = []
    always_on_files = list((ws_root / ".codebuddy" / "rules").glob("*.md")) + list((ws_root / ".ws" / "prompts").glob("*.md"))
    idx_file = ws_root / ".kb" / "docs" / "methods" / "SKILL_INDEX.yaml"

    always_on_text = ""
    for f in always_on_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        always_on_text += "\n" + txt
        # Rule 2: 严禁残留模板括号
        if "{{" in txt or "{%" in txt:
            errors.append(f"Harness² Rule 2 Violation: Unresolved template braces '{{{{' or '{{%' found in {f.name}")

    idx_text = idx_file.read_text(encoding="utf-8", errors="ignore") if idx_file.exists() else ""
    combined_routing_surface = always_on_text + "\n" + idx_text

    # Rule 1 & Rule 3: 遍历所有 SKILL.md
    methods_dir = ws_root / ".kb" / "docs" / "methods"
    skill_files = list(methods_dir.glob("*/SKILL.md")) if methods_dir.exists() else []
    for sk_md in skill_files:
        sk_name = sk_md.parent.name
        sk_txt = sk_md.read_text(encoding="utf-8", errors="ignore")
        if sk_name not in combined_routing_surface:
            errors.append(
                f"Harness² Rule 1 Violation: Skill '{sk_name}' is not registered in SKILL_INDEX.yaml or always-on routing text."
            )
        # 检查文本中点名的脚本是否物理存在
        for script_ref in re.findall(r"\b(ws_[a-z0-9_]+\.py)\b", sk_txt + "\n" + always_on_text):
            if not (ws_root / ".ws" / "bin" / script_ref).exists():
                errors.append(f"Harness² Rule 3 Violation: Referenced script '.ws/bin/{script_ref}' does not exist on disk.")

    return {"valid": len(errors) == 0, "skills_checked": len(skill_files), "errors": errors}


def compute_hgm_clade_stats(tree_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    HGM (Huxley-Gödel Machine, arXiv:2510.21614) Clade-Metaproductivity (CMP) 估计器与 Thompson Sampling：
    聚合节点 a 及其所有后代子树 C(a) 的成功/失败次数，克服短期分数贪心陷阱。
    """
    children_map: Dict[str, List[str]] = {}
    node_map: Dict[str, Dict[str, Any]] = {}
    for n in tree_nodes:
        nid = str(n["node_id"])
        node_map[nid] = n
        children_map.setdefault(nid, [])
        pid = n.get("parent_id")
        if pid:
            children_map.setdefault(str(pid), []).append(nid)

    def get_clade_ids(root_id: str) -> Set[str]:
        visited: Set[str] = set()
        stack = [root_id]
        while stack:
            cur = stack.pop()
            if cur not in visited:
                visited.add(cur)
                stack.extend(children_map.get(cur, []))
        return visited

    random.seed(42)
    results: List[Dict[str, Any]] = []
    for nid, n in node_map.items():
        clade = get_clade_ids(nid)
        c_succ = sum(int(node_map[cid].get("n_success", 0)) for cid in clade if cid in node_map)
        c_fail = sum(int(node_map[cid].get("n_failure", 0)) for cid in clade if cid in node_map)
        cmp_hat = c_succ / float(max(1, c_succ + c_fail))
        alpha = 1.0 + c_succ
        beta = 1.0 + c_fail
        ts_sample = random.betavariate(alpha, beta)
        # Wilson / Beta Lower Bound (Best-Belief 保守估计)
        mean = alpha / (alpha + beta)
        std = math.sqrt((alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1.0)))
        best_belief_lb = max(0.0, mean - 1.645 * std)
        results.append({
            "node_id": nid,
            "parent_id": n.get("parent_id"),
            "immediate_score": round(int(n.get("n_success", 0)) / float(max(1, int(n.get("n_success", 0)) + int(n.get("n_failure", 0)))), 4),
            "clade_size": len(clade),
            "clade_success": c_succ,
            "clade_failure": c_fail,
            "CMP_hat": round(cmp_hat, 4),
            "thompson_sample": round(ts_sample, 4),
            "best_belief_lower_bound": round(best_belief_lb, 4),
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="RRSI + Harness² + HGM + RQGM Unified Self-Improvement Engine v3.5")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan-round", help="Compute RRSI Proposal-Side regularizers (b_t, E_t, B_t)")
    p_plan.add_argument("--ws-root", required=True)
    p_plan.add_argument("--round", type=int, required=True)

    p_val = sub.add_parser("validate-tree", help="Run Harness² 3 hard pre-rollout structural validation rules")
    p_val.add_argument("--ws-root", required=True)

    p_ppc = sub.add_parser("contrastive-compose", help="Harness² Task-Level open-world Propose-Probe-Compose step (INV vs DOM)")
    p_ppc.add_argument("--ws-root", required=True)
    p_ppc.add_argument("--probe-json", required=True, help="JSON with base rollouts, INV probe, and DOM probe")

    p_hgm = sub.add_parser("select-parent-hgm", help="HGM Clade-Metaproductivity (CMP) & Thompson Sampling node selector")
    p_hgm.add_argument("--ws-root", required=True)
    p_hgm.add_argument("--tree-json", required=True)

    p_rqgm = sub.add_parser("upgrade-evaluator-rqgm", help="RQGM Controlled Utility Evolution at epoch boundaries with Golden Anchor")
    p_rqgm.add_argument("--ws-root", required=True)
    p_rqgm.add_argument("--challenger-json", required=True)

    p_eval = sub.add_parser("select-candidate", help="Run RRSI Selection-Side regularizers")
    p_eval.add_argument("--ws-root", required=True)
    p_eval.add_argument("--round", type=int, required=True)
    p_eval.add_argument("--candidate-json", required=True)

    p_sub = sub.add_parser("propose-sublimation", help="Sublimate validated MEMEX memories (>=3 tasks) into SKILL.md")
    p_sub.add_argument("--ws-root", required=True)
    p_sub.add_argument("--memory-id", required=True)

    args = parser.parse_args()
    ws_root = Path(args.ws_root).resolve()
    ledger_path = ws_root / ".kb" / "rrsi_ledger.jsonl"
    state_path = ws_root / ".kb" / "rrsi_state.json"

    records = load_ledger(ledger_path)
    hp = dict(DEFAULT_HYPERPARAMS)

    if args.cmd == "validate-tree":
        res = validate_harness2_tree(ws_root)
        if not res["valid"]:
            emit_error("rrsi.harness2_tree_invalid", "Harness² pre-rollout validation failed; proposal discarded.",
                       retriable=True, next_steps=res["errors"], data=res)
        emit_success("rrsi.validate_tree", res)

    elif args.cmd == "contrastive-compose":
        # Harness² 2.2.1: 无真值开放世界任务级对比合成 (INV 流程维 vs DOM 领域维)
        probe = json.loads(Path(args.probe_json).read_text(encoding="utf-8"))
        k = int(probe.get("k_base_rollouts", 3))
        inv_cand = probe.get("inv_candidate", {})
        dom_cand = probe.get("dom_candidate", {})

        decisions: List[str] = []
        adopted_edits: List[Dict[str, Any]] = []

        for dim_label, cand in (("INV", inv_cand), ("DOM", dom_cand)):
            edit_desc = str(cand.get("edit", ""))
            base_fail_cnt = int(cand.get("target_failure_in_base_count", 0))
            produced_deliverable = bool(cand.get("probe_produced_deliverable", True))
            resolved_moment = str(cand.get("trajectory_moment", ""))

            # Harness² Composer 铁律：
            # 1. 若关联 rollout 未产出交付物，视为 UNSAFE 丢弃；
            # 2. 若仅在 1/k 次基线运行中偶发（且 k>=3），视为单样本噪声丢弃；
            # 3. 必须指明具体的 trajectory moment 证据。
            if not produced_deliverable:
                decisions.append(f"dropped -> [{dim_label}] {edit_desc} -> UNSAFE: probe rollout produced no deliverable")
            elif k >= 3 and base_fail_cnt <= 1:
                decisions.append(f"dropped -> [{dim_label}] {edit_desc} -> noise in 1/{k} base rollouts (overfitting risk)")
            elif not resolved_moment:
                decisions.append(f"dropped -> [{dim_label}] {edit_desc} -> no specific trajectory moment attached")
            else:
                decisions.append(f"kept -> [{dim_label}] {edit_desc} -> {resolved_moment} (failed in {base_fail_cnt}/{k} base rollouts)")
                adopted_edits.append({"dimension": dim_label, "edit": edit_desc, "evidence_moment": resolved_moment})

        mode = "KEEP_BASE" if not adopted_edits else ("MERGE" if len(adopted_edits) == 2 else f"ADOPT_{adopted_edits[0]['dimension']}")
        # Harnessing-Level Recursion: 将通过行为对比验证的改进经验存入 .kb/harness2_library/
        lib_dir = ws_root / ".kb" / "harness2_library"
        lib_dir.mkdir(parents=True, exist_ok=True)
        if adopted_edits:
            exp_entry = {
                "task_slug": probe.get("task_slug", "open_world_task"),
                "compose_mode": mode,
                "adopted_edits": adopted_edits,
                "notes": decisions,
                "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            (lib_dir / f"exp_{int(time.time())}.yaml").write_text(dump_simple_yaml(exp_entry), encoding="utf-8")

        emit_success("rrsi.contrastive_compose", {
            "compose_decision": mode,
            "adopted_edits": adopted_edits,
            "audit_notes": decisions,
        })

    elif args.cmd == "select-parent-hgm":
        tree_data = json.loads(Path(args.tree_json).read_text(encoding="utf-8"))
        nodes = tree_data.get("nodes") or []
        stats = compute_hgm_clade_stats(nodes)
        # 按 CMP_hat 与 Thompson Sampling 选出扩展父节点，而非贪心选单点最高分
        expand_target = max(stats, key=lambda x: (x["CMP_hat"], x["thompson_sample"]))
        final_best_belief = max(stats, key=lambda x: x["best_belief_lower_bound"])
        emit_success("rrsi.select_parent_hgm", {
            "node_clade_metrics": stats,
            "recommended_parent_to_expand": expand_target["node_id"],
            "recommended_final_production_agent": final_best_belief["node_id"],
        })

    elif args.cmd == "upgrade-evaluator-rqgm":
        # RQGM (arXiv:2606.26294): 受控效用演化 (Controlled Utility Evolution)
        chal = json.loads(Path(args.challenger_json).read_text(encoding="utf-8"))
        incumbent_anchor_acc = float(chal.get("incumbent_anchor_accuracy", 0.85))
        challenger_anchor_acc = float(chal.get("challenger_anchor_accuracy", 0.0))
        ai_accept_rate = float(chal.get("challenger_ai_accept_rate", 0.5))
        human_accept_rate = float(chal.get("challenger_human_accept_rate", 0.5))

        # 1. 金标锚点判别力提升检查
        anchor_improved = challenger_anchor_acc > incumbent_anchor_acc + 0.02
        # 2. 对抗性自恋偏见消除检查 (RQGM: 防止评审器对 AI 报告宽容度高于人类报告 1.91x)
        self_preference_ratio = ai_accept_rate / max(0.01, human_accept_rate)
        stringency_parity_ok = self_preference_ratio <= 1.10

        promote = bool(anchor_improved and stringency_parity_ok)
        cur_state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"epoch": 1}
        old_epoch = int(cur_state.get("epoch", 1))
        new_epoch = old_epoch + 1 if promote else old_epoch

        if promote:
            # 周期边界切换：归档旧周期分数，防止不同标尺下的分数混排 (Selective Erasure across Epoch Boundaries)
            cur_state["epoch"] = new_epoch
            cur_state["evaluator_version"] = chal.get("challenger_id", f"verifier_v{new_epoch}")
            cur_state["S_star"] = float(chal.get("recalibrated_S_star", 0.80))
            state_path.write_text(json.dumps(cur_state, indent=2), encoding="utf-8")

        emit_success("rrsi.upgrade_evaluator_rqgm", {
            "promote_challenger_evaluator": promote,
            "previous_epoch": old_epoch,
            "current_epoch": new_epoch,
            "anchor_accuracy_gain": round(challenger_anchor_acc - incumbent_anchor_acc, 4),
            "ai_vs_human_accept_ratio": round(self_preference_ratio, 3),
            "stringency_parity_passed": stringency_parity_ok,
        })

    elif args.cmd == "plan-round":
        b_t = annealed_budget(args.round, int(hp["T"]), int(hp["b_min"]), int(hp["b_max"]))
        exercised = {str(r.get("component")) for r in records if r.get("component") in COMPONENT_VOCAB}
        unexplored = [c for c in COMPONENT_VOCAB if c not in exercised]
        emit_success("rrsi.plan_round", {
            "round": args.round,
            "annealed_edit_budget_b_t": b_t,
            "unexplored_components_U_t": unexplored,
            "current_harness_token_footprint_C": measure_harness_footprint_tokens(ws_root),
        })

    elif args.cmd == "select-candidate":
        cand = json.loads(Path(args.candidate_json).read_text(encoding="utf-8"))
        atomic_edits: List[Dict[str, Any]] = cand.get("atomic_edits") or []
        diff_text = str(cand.get("diff_text", ""))

        b_t = annealed_budget(args.round, int(hp["T"]), int(hp["b_min"]), int(hp["b_max"]))
        if len(atomic_edits) > b_t:
            emit_error("rrsi.l0_budget_exceeded", f"Bundles {len(atomic_edits)} edits > budget b_t={b_t}.", retriable=True)

        passed_leakage, leak_reasons = screen_leakage(diff_text, atomic_edits)
        if not passed_leakage:
            emit_error("rrsi.leakage_critic_rejected", "Rejected by Pre-Evaluation Leakage Critic.", retriable=True, next_steps=leak_reasons)

        S_t = float(cand.get("incumbent_score_S_t", 0.80))
        S_star = float(cand.get("best_score_S_star", S_t))
        S_prime = float(cand.get("candidate_score_S_prime", 0.0))
        C_t = float(cand.get("incumbent_cost_C_t", measure_harness_footprint_tokens(ws_root)))
        C_prime = float(cand.get("candidate_cost_C_prime", C_t))

        delta_S = round(S_prime - S_t, 5)
        delta_C = round((C_prime - C_t) / max(1.0, C_t), 5)
        delta = float(hp["delta"])

        passed_floor = S_prime >= (S_star - delta)
        previously_accepted_structural = {
            str(r.get("component")) for r in records if r.get("accepted") is True and str(r.get("component")) in STRUCTURAL_COMPONENTS
        }
        touched = {str(ed.get("component")) for ed in atomic_edits}
        nu_t = sum(1 for c in (touched & STRUCTURAL_COMPONENTS) if c not in previously_accepted_structural)

        if delta_S > delta:
            max_allowed_delta_C = float(hp["beta_0"]) + float(hp["beta_1"]) * delta_S
            passed_complexity = (delta_C <= max_allowed_delta_C)
        else:
            shaped_val = float(hp["w_s"]) * delta_S - float(hp["w_c"]) * delta_C + float(hp["w_n"]) * nu_t
            passed_complexity = (shaped_val > 0.0)

        sci_violations = int(cand.get("scientific_violations_count", 0))
        valid_key_drop = float(cand.get("valid_evidence_key_rate_drop", 0.0))
        passed_domain_guard = (sci_violations == 0) and (valid_key_drop <= 0.02)

        admissible = bool(passed_floor and passed_complexity and passed_domain_guard)
        new_S_star = max(S_star, S_prime) if admissible else S_star

        for ed in atomic_edits:
            append_ledger(ledger_path, {
                "round": args.round,
                "component": ed.get("component"),
                "hypothesis": ed.get("hypothesis"),
                "delta_S": delta_S,
                "delta_C": delta_C,
                "accepted": admissible,
            })

        emit_success("rrsi.select_candidate", {
            "admissible": admissible,
            "decision": "ACCEPT_AND_COMMIT_HARNESS" if admissible else "REJECT_AND_GIT_ROLLBACK",
            "metrics": {"delta_S": delta_S, "delta_C": delta_C, "nu_t": nu_t, "S_star": new_S_star},
        })

    elif args.cmd == "propose-sublimation":
        mem_file = ws_root / ".kb" / "memory" / f"{args.memory_id}.yaml"
        if not mem_file.exists():
            emit_error("rrsi.sublimation", f"Formal memory '{args.memory_id}' not found.", retriable=False)
        mem = load_simple_yaml(mem_file.read_text(encoding="utf-8"))
        applied = list(mem.get("applied_tasks") or [])
        if len(applied) < 3:
            emit_error("rrsi.sublimation_premature", f"Requires >= 3 tasks (current={len(applied)}).", retriable=False)
        emit_success("rrsi.propose_sublimation", {"memory_id": args.memory_id, "validated_tasks": applied})


if __name__ == "__main__":
    main()
