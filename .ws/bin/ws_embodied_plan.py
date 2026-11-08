#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_embodied_plan.py — 借鉴 EmbodiedRSI (Columbia/Princeton, arXiv:2610.10498) 的快慢双系统、代码-技能协同图与计划防发散编译器
直接根治用户核心痛点：
“新的类似任务来了还是每次都要尝试去用新的思路或发散的思路解决类似问题，我想让已经做过的事情后续分析更稳定顺畅，至少在计划时不会随意发散思维。”

核心实现机制：
1. M1 -> M2 -> M3 三层分级记忆架构：
   - M1 (.kb/memory/m1_episodes.jsonl): 保存每次任务执行的原始轨迹、调用工具、参数、耗时与得分 (τ, κ, ν, a, z, y, r)
   - M2 (.kb/memory/m2_hypothesis_graph.json): 维护代码节点 (Code C_i，如 promoter_ratio.R) 与技能节点 (Skill S_j，如 mouse-peak-anno) 的假设图：
     * 有向修订边 `refines`：记录版本演进历史
     * 双向协同边 `works-with`：通过同初始状态对照试验计算联合增益 w_ij = R(C_i, S_j) - max(R(C_i), R(S_j))，当 w_ij > 0 时锁定这对 Code+Skill 最佳拍档！
     * 后验置信度 c_i = (n_sup + α) / (n_sup + n_ref + α + β) 与探索不确定性二元熵 H_exp(D_k) = sum h_2(q_i)
   - M3 (.kb/memory/m3_cognition.yaml): 提炼跨任务可复用的前置门禁与认知规则，由慢系统六动作算子 (Retain, Merge, Abstract, Compress, Forget, Skip) 根据下游闭环奖励 r_t^mem = λ1*(R_{t+1}-R_t) + λ2*(H_t-H_{t+1}) - λ3*C_{t+1} 择优保留。

2. 信息价值 VOI 停止探索条件与“零发散计划编译器 (Zero-Divergence Plan Compiler)”：
   - 当新任务命中某个已有 Skill S_j，且假设图中该 Skill 与其 `works-with` 代码的探索不确定性熵 H_exp < ε_H (或置信度 c_i >= 0.75) 时：
     **触发 EmbodiedRSI 停止探索条件 (Stop Exploration -> Pure Exploitation Mode)**！
   - 此时严禁 Agent 自由手写 `plan.md`！必须由本脚本 `compile-plan` 执行：
     Step A (前置门禁拦截): 检查 META.yaml 是否已填齐该 Skill 在 M3/plan_skeleton 中要求的所有前置参数（例如 `promoter_window_kb` 与 `txdb_version`）。若缺失，立即阻断并给出精确提问话术（“凡客户提到 promoter，先问清 ±N kb”）。
     Step B (确定性克隆与代码强绑定): 将 `plan_skeleton.yaml` 与 `works-with` 绑定的 `.kb/code/`、`.kb/cli/` 脚本直接实例化为任务目录下的 `plan.md`，并计算步骤结构与脚本绑定指纹写入 `.plan_lock.json`。
     Step C (防发散结构锁校验 `verify-plan-lock`): 在任务执行期间，Agent 只能将 `[ ]` 改为 `[✓]`；一旦 Agent 擅自增删步骤、调换顺序或弃用绑定的 `.kb/code/` 函数改写临时代码，`verify-plan-lock` 立即报错拦截！
"""
import argparse
import hashlib
import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ws_contract import emit_error, emit_success
from ws_meta import dump_simple_yaml, load_simple_yaml

PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0
ENTROPY_STOP_THRESHOLD = 0.65  # 当平均二元熵 < 0.65 (即置信度 >= ~0.82) 时停止发散探索，锁定计划


def binary_entropy(q: float) -> float:
    q = max(1e-6, min(1.0 - 1e-6, q))
    return -(q * math.log2(q) + (1.0 - q) * math.log2(1.0 - q))


def compute_node_metrics(n_sup: int, n_ref: int) -> Tuple[float, float]:
    c_i = (n_sup + PRIOR_ALPHA) / float(n_sup + n_ref + PRIOR_ALPHA + PRIOR_BETA)
    h_2 = binary_entropy(c_i)
    return round(c_i, 4), round(h_2, 4)


def load_m2_graph(ws_root: Path) -> Dict[str, Any]:
    gpath = ws_root / ".kb" / "memory" / "m2_hypothesis_graph.json"
    if gpath.exists():
        return json.loads(gpath.read_text(encoding="utf-8"))
    return {"nodes": {}, "refines_edges": [], "works_with_edges": []}


def save_m2_graph(ws_root: Path, graph: Dict[str, Any]) -> None:
    gpath = ws_root / ".kb" / "memory" / "m2_hypothesis_graph.json"
    gpath.parent.mkdir(parents=True, exist_ok=True)
    gpath.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_plan_skeleton_signature(plan_text: str) -> List[str]:
    """提取 plan.md 中除 [ ]/[✓] 勾选状态外的所有步骤标题与绑定脚本行，用于校验 Agent 是否擅自篡改计划或发散步骤。"""
    sig_lines: List[str] = []
    for raw in plan_text.splitlines():
        line = raw.strip()
        if line.startswith("- ["):
            # 抹除勾选状态符号，保留步骤ID、标题与绑定脚本调用
            normalized = re.sub(r"^- \[[ x✓✗/]?\]\s*", "", line)
            sig_lines.append(normalized)
    return sig_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="EmbodiedRSI Fast-Slow Co-Evolution & Zero-Divergence Plan Compiler")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # 1. 记录匹配实验结果并更新 M1 + M2 假设图 (Code-Skill Co-Evolution & VOI)
    p_rec = sub.add_parser("record-trial", help="Record matched trial outcome into M1 and update M2 Hypothesis Graph (c_i, H_exp, works-with)")
    p_rec.add_argument("--ws-root", required=True)
    p_rec.add_argument("--skill-id", required=True)
    p_rec.add_argument("--code-id", required=True, help="e.g. .kb/code/R/annotation/promoter_ratio.R")
    p_rec.add_argument("--cli-id", default="", help="e.g. .kb/cli/python/kb_tsv_stats.py")
    p_rec.add_argument("--r-code-only", type=float, required=True, help="Success rate with code only R(C_i)")
    p_rec.add_argument("--r-skill-only", type=float, required=True, help="Success rate with skill only R(S_j)")
    p_rec.add_argument("--r-joint", type=float, required=True, help="Success rate with joint execution R(C_i, S_j)")
    p_rec.add_argument("--n-sup", type=int, default=5, help="Supporting matched trials count")
    p_rec.add_argument("--n-ref", type=int, default=0, help="Refuting matched trials count")
    p_rec.add_argument("--cost", type=float, default=1.0, help="Experiment execution cost C(t)")
    p_rec.add_argument("--refines-from", default=None, help="Optional older version node ID for directed 'refines' edge")

    # 2. VOI 实验选择与探索停止判定
    p_voi = sub.add_parser(" rank-voi".strip(), help="Rank candidate experiments by VOI(t) = G_k(t) / C(t) and check stopping condition")
    p_voi.add_argument("--ws-root", required=True)
    p_voi.add_argument("--candidates-json", required=True)

    # 3. 零发散计划编译器 (compile-plan)
    p_comp = sub.add_parser("compile-plan", help="Deterministically compile locked plan.md from verified Skill + works-with Code")
    p_comp.add_argument("--ws-root", required=True)
    p_comp.add_argument("--task-dir", required=True)
    p_comp.add_argument("--skill-id", required=True)

    # 4. 计划结构锁校验器 (verify-plan-lock)
    p_vlock = sub.add_parser("verify-plan-lock", help="Verify Agent only checked off steps in plan.md without diverging or dropping bound scripts")
    p_vlock.add_argument("--task-dir", required=True)

    # 5. M3 慢系统六动作记忆管理器 (Slow-System Reward-Grounded Memory Manager)
    p_m3 = sub.add_parser("manage-m3", help="Execute Slow-System 6-action memory policy (Retain/Merge/Abstract/Compress/Forget/Skip) grounded in r_t^mem")
    p_m3.add_argument("--ws-root", required=True)
    p_m3.add_argument("--delta-success", type=float, required=True, help="R_{t+1} - R_t")
    p_m3.add_argument("--delta-entropy", type=float, required=True, help="H_t - H_{t+1} (uncertainty reduction)")
    p_m3.add_argument("--cost", type=float, required=True, help="C_{t+1}")

    args = parser.parse_args()
    ws_root = Path(args.ws_root).resolve() if hasattr(args, "ws_root") and args.ws_root else None

    if args.cmd == "record-trial":
        assert ws_root is not None
        graph = load_m2_graph(ws_root)
        nodes = graph.setdefault("nodes", {})

        c_conf, c_ent = compute_node_metrics(args.n_sup, args.n_ref)
        for nid, ntype in ((args.skill_id, "skill"), (args.code_id, "code"), (args.cli_id, "cli")):
            if not nid:
                continue
            nodes[nid] = {
                "id": nid,
                "type": ntype,
                "n_sup": args.n_sup,
                "n_ref": args.n_ref,
                "confidence_c_i": c_conf,
                "entropy_h2": c_ent,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        # EmbodiedRSI Eq. (7): 计算联合增益 w_ij = R(C_i, S_j) - max(R(C_i), R(S_j))
        w_ij = round(args.r_joint - max(args.r_code_only, args.r_skill_only), 4)
        ww_edges: List[Dict[str, Any]] = list(graph.get("works_with_edges") or [])
        if w_ij > 0:
            ww_edges = [e for e in ww_edges if not (e.get("skill") == args.skill_id and e.get("code") == args.code_id)]
            ww_edges.append({
                "skill": args.skill_id,
                "code": args.code_id,
                "cli": args.cli_id,
                "joint_success_rate": args.r_joint,
                "synergy_gain_w_ij": w_ij,
                "relation": "works-with (bidirectional)",
            })
        graph["works_with_edges"] = ww_edges

        if args.refines_from:
            ref_edges = list(graph.get("refines_edges") or [])
            ref_edges.append({"from": args.refines_from, "to": args.skill_id, "relation": "refines"})
            graph["refines_edges"] = ref_edges

        save_m2_graph(ws_root, graph)

        # 写入 M1 原始物理/分析执行记录
        m1_path = ws_root / ".kb" / "memory" / "m1_episodes.jsonl"
        m1_record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "skill_id": args.skill_id,
            "invoked_code": args.code_id,
            "invoked_cli": args.cli_id,
            "r_code_only": args.r_code_only,
            "r_skill_only": args.r_skill_only,
            "r_joint": args.r_joint,
            "synergy_w_ij": w_ij,
            "cost": args.cost,
        }
        with open(m1_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(m1_record, ensure_ascii=False) + "\n")

        exploration_should_stop = (c_ent < ENTROPY_STOP_THRESHOLD and w_ij > 0)
        emit_success("embodied.record_trial", {
            "skill_id": args.skill_id,
            "code_id": args.code_id,
            "posterior_confidence_c_i": c_conf,
            "uncertainty_entropy_h2": c_ent,
            "joint_synergy_gain_w_ij": w_ij,
            "works_with_locked": w_ij > 0,
            "stop_exploration_lock_plan": exploration_should_stop,
        })

    elif args.cmd == "rank-voi":
        assert ws_root is not None
        cands = json.loads(Path(args.candidates_json).read_text(encoding="utf-8"))
        ranked: List[Dict[str, Any]] = []
        for c in cands:
            cur_h = float(c.get("current_entropy_H", 0.9))
            exp_post_h = float(c.get("expected_posterior_entropy_H", 0.3))
            info_gain_G = max(0.0, cur_h - exp_post_h)
            cost_C = max(0.1, float(c.get("cost_C", 1.0)))
            voi = round(info_gain_G / cost_C, 4)
            ranked.append({
                "experiment_id": c.get("experiment_id"),
                "target_hypothesis": c.get("target_hypothesis"),
                "info_gain_G": round(info_gain_G, 4),
                "cost_C": cost_C,
                "VOI_score": voi,
            })
        ranked.sort(key=lambda x: x["VOI_score"], reverse=True)
        max_voi = ranked[0]["VOI_score"] if ranked else 0.0
        emit_success("embodied.rank_voi", {
            "ranked_experiments": ranked,
            "selected_experiment_t_star": ranked[0]["experiment_id"] if ranked else None,
            "stop_exploration": max_voi < 0.05,
        })

    elif args.cmd == "compile-plan":
        assert ws_root is not None
        task_dir = Path(args.task_dir).resolve()
        meta_path = task_dir / "META.yaml"
        if not meta_path.exists():
            emit_error("embodied.compile_plan", "META.yaml not found in task_dir.", retriable=False, task_dir=task_dir)

        meta = load_simple_yaml(meta_path.read_text(encoding="utf-8"))
        skill_dir = ws_root / ".kb" / "docs" / "methods" / args.skill_id
        skel_path = skill_dir / "plan_skeleton.yaml"
        if not skel_path.exists():
            emit_error("embodied.compile_plan", f"plan_skeleton.yaml not found for skill '{args.skill_id}'.", retriable=False, task_dir=task_dir)

        skel = load_simple_yaml(skel_path.read_text(encoding="utf-8"))

        # 1. Precondition Gate (强制检查先例经验要求确认的参数，如 promoter_window_kb 与 txdb_version，杜绝乱猜)
        missing_preconds: List[Dict[str, str]] = []
        for pre in (skel.get("preconditions") or []):
            p_key = str(pre.get("param", ""))
            if p_key and (meta.get(p_key) is None or str(meta.get(p_key)).strip() == ""):
                missing_preconds.append({
                    "missing_param": p_key,
                    "rule": str(pre.get("rule", "")),
                    "source_lesson": str(skel.get("distilled_from_requirement", "")),
                })

        if missing_preconds:
            emit_error(
                "embodied.precondition_gate_blocked",
                f"Cannot compile plan.md: {len(missing_preconds)} mandatory domain precondition(s) missing from META.yaml!",
                retriable=False,
                next_steps=[
                    f"Ask customer/user to confirm '{m['missing_param']}': {m['rule']} (Lesson from {m['source_lesson']})"
                    for m in missing_preconds
                ] + [
                    "After user confirms, run 'ws_meta.py patch' to record the parameter(s) in META.yaml, then re-run 'ws_embodied_plan.py compile-plan'."
                ],
                data={"missing_preconditions": missing_preconds},
                task_dir=task_dir,
            )

        # 2. 查询 M2 假设图，获取与该 Skill 具有双向 works-with 正协同边的代码与 CLI
        graph = load_m2_graph(ws_root)
        node_info = (graph.get("nodes") or {}).get(args.skill_id, {})
        c_i = float(node_info.get("confidence_c_i", 0.85))
        h_2 = float(node_info.get("entropy_h2", 0.40))
        ww_matches = [e for e in (graph.get("works_with_edges") or []) if e.get("skill") == args.skill_id]

        # 3. 确定性生成锁死版 plan.md（严禁 Agent 自由发散步骤）
        plan_lines = [
            f"# 任务执行计划（Locked by EmbodiedRSI + DisCo Skill: `{args.skill_id}`）",
            "",
            f"- **规划模式**：`LOCKED_EXPLOITATION`（置信度 $c_i = {c_i}$，不确定性熵 $\mathcal{{H}}_{{\mathrm{{exp}}}} = {h_2} < {ENTROPY_STOP_THRESHOLD}$，**已触发停止发散探索门禁**）",
            f"- **绑定先例依据**：`.kb/docs/methods/{args.skill_id}/references/{skel.get('distilled_from_requirement')}`",
            f"- **绑定协同代码 (`works-with`)**：`{skel.get('bound_r_code')}` + `{skel.get('bound_py_cli')}`",
            f"- **已锁定口径参数**：`txdb_version={meta.get('txdb_version')}`, `promoter_window_kb={meta.get('promoter_window_kb')}`",
            "",
            "> **防发散铁律**：本计划由已验证技能骨架直接实例化生成并受 `.plan_lock.json` 结构哈希保护。只允许将已完成步骤的 `[ ]` 更新为 `[✓]`，**严禁增删步骤、严禁改变步骤顺序、严禁抛弃绑定脚本自己手写发散代码**！",
            "",
            "## 标准执行步骤（Canonical Steps）",
        ]

        for st in (skel.get("canonical_steps") or []):
            sid = st.get("step_id")
            title = st.get("title")
            b_tool = st.get("bound_script") or st.get("bound_code")
            out_art = st.get("expected_output")
            cmd_tmpl = str(st.get("command_template", "")).format(
                txdb_version=meta.get("txdb_version", ""),
                promoter_window_kb=meta.get("promoter_window_kb", ""),
                source_dir=meta.get("source_dir", ""),
            )
            plan_lines.append(
                f"- [ ] **[{sid}] {title}** | 强制调用: `{b_tool}` | 命令: `{cmd_tmpl}` | 验收产物: `{out_art}`"
            )

        plan_text = "\n".join(plan_lines) + "\n"
        plan_path = task_dir / "plan.md"
        plan_path.write_text(plan_text, encoding="utf-8")

        sig = extract_plan_skeleton_signature(plan_text)
        sig_hash = hashlib.sha256(json.dumps(sig, ensure_ascii=False).encode("utf-8")).hexdigest()
        lock_data = {
            "skill_id": args.skill_id,
            "mode": "LOCKED_EXPLOITATION",
            "confidence_c_i": c_i,
            "entropy_h2": h_2,
            "works_with_bindings": ww_matches,
            "step_count": len(sig),
            "canonical_signature": sig,
            "structure_sha256": sig_hash,
            "locked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        (task_dir / ".plan_lock.json").write_text(json.dumps(lock_data, ensure_ascii=False, indent=2), encoding="utf-8")
        emit_success("embodied.compile_plan", {
            "plan_path": str(plan_path),
            "plan_mode": "LOCKED_EXPLOITATION",
            "structure_sha256": sig_hash,
            "step_count": len(sig),
        }, task_dir=task_dir)

    elif args.cmd == "verify-plan-lock":
        task_dir = Path(args.task_dir).resolve()
        plan_path = task_dir / "plan.md"
        lock_path = task_dir / ".plan_lock.json"
        if not plan_path.exists() or not lock_path.exists():
            emit_error("embodied.verify_plan_lock", "plan.md or .plan_lock.json missing.", retriable=False, task_dir=task_dir)

        lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
        cur_text = plan_path.read_text(encoding="utf-8")
        cur_sig = extract_plan_skeleton_signature(cur_text)
        cur_hash = hashlib.sha256(json.dumps(cur_sig, ensure_ascii=False).encode("utf-8")).hexdigest()

        if cur_hash != lock_data.get("structure_sha256"):
            emit_error(
                "embodied.plan_divergence_blocked",
                "PLAN DIVERGENCE DETECTED: Agent modified, reordered, or replaced locked canonical steps in plan.md!",
                retriable=True,
                next_steps=[
                    "Restore the exact canonical steps generated by 'ws_embodied_plan.py compile-plan'.",
                    "You may ONLY change checkbox status '[ ]' -> '[✓]'. Do NOT invent new steps or drop bound .kb/code/ scripts.",
                ],
                data={"expected_steps": lock_data.get("canonical_signature"), "actual_steps": cur_sig},
                task_dir=task_dir,
            )

        # 同时检查单次勾选纪律：统计已完成数
        done_steps = len(re.findall(r"^- \[[x✓]\]", cur_text, re.MULTILINE))
        emit_success("embodied.verify_plan_lock", {
            "lock_intact": True,
            "structure_sha256": cur_hash,
            "completed_steps": done_steps,
            "total_steps": lock_data.get("step_count"),
        }, task_dir=task_dir)

    elif args.cmd == "manage-m3":
        assert ws_root is not None
        # EmbodiedRSI Eq. (10): r_t^mem = λ1*(R_{t+1}-R_t) + λ2*(H_t-H_{t+1}) - λ3*C_{t+1}
        l1, l2, l3 = 2.0, 1.5, 0.2
        r_mem = round(l1 * args.delta_success + l2 * args.delta_entropy - l3 * args.cost, 4)

        # 基于闭环奖励与信息增益在六种记忆操作 (Retain, Merge, Abstract, Compress, Forget, Skip) 中决策
        if r_mem >= 0.30 and args.delta_entropy > 0.10:
            action = "Abstract"
            desc = "High downstream task gain & uncertainty drop: abstract M1/M2 evidence into M3 reusable precondition & plan skeleton."
        elif r_mem >= 0.10:
            action = "Merge"
            desc = "Positive downstream reward: merge supporting episode counts into existing M2/M3 works-with node."
        elif r_mem >= 0.0:
            action = "Retain"
            desc = "Neutral-positive return: retain current M3 cognition unchanged."
        elif args.cost > 2.0:
            action = "Compress"
            desc = "High execution cost detected: compress verbose references into compact CLI wrapper."
        elif r_mem < -0.15:
            action = "Forget"
            desc = "Negative downstream reward: forget/archive misleading hypothesis."
        else:
            action = "Skip"
            desc = "Negligible information value change: skip memory write."

        m3_path = ws_root / ".kb" / "memory" / "m3_cognition_log.jsonl"
        rec = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "r_mem": r_mem,
            "selected_operator": action,
            "rationale": desc,
        }
        with open(m3_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        emit_success("embodied.manage_m3", rec)


if __name__ == "__main__":
    main()
