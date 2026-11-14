#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_rsiflow_diag.py — 吸收自 RSIFlow: Adaptive Self-Improvement Workflows with an Evolving Meta-Agent (arXiv:2610.21791)
解决核心问题：“自我改进的第一步不是改进，而是诊断——此刻的瓶颈到底在任务产物 (ARTIFACTS)、执行框架 (HARNESS)、还是模型先验 (MODEL)？”

核心实现机制：
1. 瓶颈状态诊断与范围匹配原则 (Principle of Scope & Budget, RSIFlow Fig. 13):
   - 当错误属于单任务的局部交付物缺陷（如某行数值笔误、漏挂证据键、局部代码语法报错）且历史同类型错误频次 < 2 时：
     路由至 `ARTIFACTS`（仅在当前任务目录内局部修补提交，保持全局 Harness 与 SKILL 不动，避免拿局部特例污染全局框架！）。
   - 当错误属于跨任务复发的执行接口或契约缺陷（如未核验回执即报完成、输出格式违约、同类型报错跨 >= 2 个任务出现）时：
     路由至 `HARNESS`（定位 Action / Skill / Planning 模块并生成可复用框架补丁）。
   - 当框架契约完备但复杂生信领域推理持续不足且积累了足够验证成功轨迹时：
     路由至 `MODEL_REPLAY`（筛选经过来源核验的成功轨迹构建 Few-Shot / LoRA Replay 数据集）。
2. 错误词 4 倍加权检索器 (RSIFlow Eq. 20 Explicit Error-Weighted Retriever):
   r(k, z) = |Q(z) ∩ B(k)| + 3 * |Q(z) ∩ B(k) ∩ F(z)|
   对错误信号词 F(z) 赋予 4 倍总权重（普通查询词 1 倍），精准召回能解决当前报错的元技能。
3. 失败记账与反自我确认膨胀 (Failure Accounting & Anti-Inflation Maintenance, RSIFlow Eq. 21-24):
   - 记录配对增益 ΔJ = (n_01 - n_10) / N（同时追踪救回任务数 n_01 与倒退任务数 n_10）；
   - 失败的候选干预同样记入元经验账本（标记该方向在当前条件下不适用）；
   - 严格执行“一次独立干预只计一次支持事件 (1 intervention = 1 support event)”，引用或汇总旧 ID 绝不虚增置信度！
"""
import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Set

from ws_contract import emit_error, emit_success


def tokenize_set(text: str) -> Set[str]:
    norm = re.sub(r"[-_/:.,;()\[\]]", " ", text.lower())
    en = set(re.findall(r"[a-z0-9]{2,}", norm))
    zh = {norm[i:i+2] for i in range(len(norm) - 1) if "\u4e00" <= norm[i] <= "\u9fff" and "\u4e00" <= norm[i+1] <= "\u9fff"}
    return en | zh


def rsiflow_error_weighted_score(query_tokens: Set[str], error_tokens: Set[str], skill_tokens: Set[str]) -> int:
    """RSIFlow Eq. (20): r(k, z) = |Q(z) ∩ B(k)| + 3 * |Q(z) ∩ B(k) ∩ F(z)|"""
    base_overlap = len(query_tokens & skill_tokens)
    err_overlap = len(query_tokens & skill_tokens & error_tokens)
    return base_overlap + 3 * err_overlap


def main() -> None:
    parser = argparse.ArgumentParser(description="RSIFlow Adaptive Bottleneck Diagnostician & Meta-Skill Maintainer (arXiv:2610.21791)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_diag = sub.add_parser("diagnose", help="Diagnose bottleneck state z_t and route to ARTIFACTS, HARNESS, or MODEL_REPLAY")
    p_diag.add_argument("--ws-root", required=True)
    p_diag.add_argument("--task-slug", required=True)
    p_diag.add_argument("--error-signature", required=True, help="Observed error message or failure type")
    p_diag.add_argument("--stage", required=True, choices=["accept", "plan", "execute", "report", "review"])
    p_diag.add_argument("--recurring-task-count", type=int, default=1, help="How many distinct tasks exhibited this failure")
    p_diag.add_argument("--is-contract-or-interface-bug", action="store_true")

    p_rec = sub.add_parser("record-intervention", help="Record paired outcome (n_01, n_10) including failed interventions without confidence inflation")
    p_rec.add_argument("--ws-root", required=True)
    p_rec.add_argument("--intervention-id", required=True, help="Unique ID of this intervention experiment")
    p_rec.add_argument("--skill-id", required=True)
    p_rec.add_argument("--scope", required=True, choices=["ARTIFACTS", "HARNESS", "MODEL_REPLAY"])
    p_rec.add_argument("--n01-rescued", type=int, required=True, help="Tasks flipping 0 -> 1")
    p_rec.add_argument("--n10-regressed", type=int, required=True, help="Tasks flipping 1 -> 0 (preservation violation)")
    p_rec.add_argument("--total-tasks", type=int, required=True)
    p_rec.add_argument("--notes", required=True)

    args = parser.parse_args()
    ws_root = Path(args.ws_root).resolve()
    meta_lib_path = ws_root / ".kb" / "memory" / "rsiflow_meta_skills.json"
    meta_lib_path.parent.mkdir(parents=True, exist_ok=True)

    lib_data: Dict[str, Any] = json.loads(meta_lib_path.read_text(encoding="utf-8")) if meta_lib_path.exists() else {"skills": []}
    skills_list: List[Dict[str, Any]] = list(lib_data.get("skills") or [])

    if args.cmd == "diagnose":
        # 1. RSIFlow Principle (Fig. 13): Match intervention scope to failure scale
        if args.recurring_task_count == 1 and not args.is_contract_or_interface_bug:
            selected_route = "ARTIFACTS"
            rationale = (
                "Single-task localized defect with actionable feedback: route to ARTIFACTS (revise current task output in-place within <=2 attempts; "
                "preserve global Harness and SKILL.md unchanged to prevent local noise from polluting global rules)."
            )
        elif args.is_contract_or_interface_bug or args.recurring_task_count >= 2:
            selected_route = "HARNESS"
            rationale = (
                f"Recurring execution/interface bottleneck observed across {args.recurring_task_count} task(s): "
                "route to HARNESS (localize Action/Skill/Planning module and apply reusable structural check)."
            )
        else:
            selected_route = "MODEL_REPLAY"
            rationale = "Persistent semantic capability bottleneck with intact Harness contract: route to MODEL_REPLAY (consolidate verified successful trajectories)."

        # 2. RSIFlow Eq. (20) Error-Token 4x Weighted Retrieval
        q_tokens = tokenize_set(f"{args.stage} {args.error_signature}")
        f_tokens = tokenize_set(args.error_signature)
        retrieved: List[Dict[str, Any]] = []
        for sk in skills_list:
            b_tokens = tokenize_set(json.dumps(sk, ensure_ascii=False))
            score = rsiflow_error_weighted_score(q_tokens, f_tokens, b_tokens)
            if score > 0:
                retrieved.append({"skill_id": sk.get("skill_id"), "rsiflow_eq20_score": score, "record": sk})
        retrieved.sort(key=lambda x: x["rsiflow_eq20_score"], reverse=True)

        emit_success("rsiflow.diagnose", {
            "diagnosed_state_z_t": {
                "task_slug": args.task_slug,
                "stage": args.stage,
                "error_signature": args.error_signature,
                "recurring_task_count": args.recurring_task_count,
            },
            "selected_workflow_route": selected_route,
            "routing_rationale": rationale,
            "retrieved_meta_skills": retrieved[:3],
        })

    elif args.cmd == "record-intervention":
        # RSIFlow Eq. (23): ΔJ = (n_01 - n_10) / N
        n_total = max(1, args.total_tasks)
        delta_J = round((args.n01_rescued - args.n10_regressed) / float(n_total), 4)
        accepted = (delta_J > 0.0 and args.n10_regressed == 0)

        existing = next((s for s in skills_list if s.get("skill_id") == args.skill_id), None)
        if existing is None:
            existing = {
                "skill_id": args.skill_id,
                "scope": args.scope,
                "support_interventions": [],
                "counterexample_interventions": [],
                "support_count": 0,
                "counterexample_count": 0,
            }
            skills_list.append(existing)

        # RSIFlow Prompt 8 铁律: One intervention = One support event (同一 intervention_id 重复登记不虚增置信度！)
        supp_ids: List[str] = list(existing.get("support_interventions") or [])
        counter_ids: List[str] = list(existing.get("counterexample_interventions") or [])

        already_counted = (args.intervention_id in supp_ids) or (args.intervention_id in counter_ids)
        if not already_counted:
            if accepted:
                supp_ids.append(args.intervention_id)
            else:
                # “失败也记账”：即使候选未提高得分 (ΔJ <= 0)，也作为反例证据记入，防止下一轮重蹈覆辙
                counter_ids.append(args.intervention_id)

        existing["support_interventions"] = supp_ids
        existing["counterexample_interventions"] = counter_ids
        existing["support_count"] = len(supp_ids)
        existing["counterexample_count"] = len(counter_ids)
        existing["last_delta_J"] = delta_J
        existing["last_notes"] = args.notes
        existing["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        lib_data["skills"] = skills_list
        meta_lib_path.write_text(json.dumps(lib_data, ensure_ascii=False, indent=2), encoding="utf-8")

        emit_success("rsiflow.record_intervention", {
            "skill_id": args.skill_id,
            "intervention_id": args.intervention_id,
            "paired_gain_delta_J": delta_J,
            "candidate_accepted": accepted,
            "deduplicated_support_events": len(supp_ids),
            "failure_counterexamples_logged": len(counter_ids),
            "confidence_inflation_blocked": already_counted,
        })


if __name__ == "__main__":
    main()
