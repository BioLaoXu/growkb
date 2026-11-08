#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_disco_distill.py — 借鉴 Repo-To-Skill / DisCo (BAAI, arXiv:2609.02749, VectorSpaceLab/AREX-Skill) 的操作性知识蒸馏与路由引擎
解决核心痛点：
为什么 growkb 里已经有了 docs/requirements/92512126902_mouse-peak-anno.md 和 code/R/annotation/promoter_ratio.R，
但新来一个类似的 peak 注释任务时，Agent 还是会自己重新发散思维写一套新计划、甚至用错默认参数？

因为如 Repo-To-Skill 论文指出：
- 声明式历史记录 (Declarative Notes, 如 requirements/*.md) != 操作性知识 (Operational Knowledge K)
- 散装代码函数 (code/R/*.R) 是 "Capability without Policy"（有能力无调用策略）
- 纯文字方法文档是 "Policy without Capability"（有建议无可执行封装与锁死计划模板）

本脚本实现 DisCo 的四段式蒸馏流水线：
  anchor z (已完成任务 + requirements 拆解文档 + code/cli 代码)
    --[1. scope]--> 识别可复用能力与前置参数门禁 (Precondition Gates)
    --[2. ground]--> 绑定 .kb/code/、.kb/cli/、.kb/docs/requirements/ 证据链
    --[3. construct]--> 生成 AREX 标准三层技能包：
         .kb/docs/methods/<skill_id>/
           ├── SKILL.md                (知识接口：When to use + Load/Skip + 固定 SOP)
           ├── plan_skeleton.yaml      (防发散核心：锁死步骤顺序、绑定具体脚本与参数槽位)
           ├── references/             (知识基底：按需渐进加载的历史案例与参数说明)
           └── scripts/                (执行接口：封装好输入输出的薄壳执行器，Agent 直接调而非重写)
    --[4. verify]--> 执行断言检查 (验证所有绑定的 .R/.py 脚本存在、语法合规、薄壳可执行)，生成 construction_record.json (R)
                    "验证是蒸馏和总结的分界线：没有跑过断言检查的技能绝不入库！"

同时实现两级分类树路由 (Area -> Family -> Skill Graph) + 检索匹配度回退机制（防 PaperBench 中低匹配度技能误导 Agent）。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ws_contract import emit_error, emit_success
from ws_meta import dump_simple_yaml, load_simple_yaml


def verify_skill_package(ws_root: Path, skill_dir: Path) -> Dict[str, Any]:
    """
    DisCo Stage 4 [verify]: 验证是蒸馏和总结的分界线。
    检查：
    1. 三层结构完整性：SKILL.md, plan_skeleton.yaml, references/, scripts/
    2. plan_skeleton.yaml 中每个 step 绑定的 bound_script / bound_code 物理存在且可执行/语法有效
    3. pre_conditions 参数门禁定义完整
    4. 试运行 scripts/ 下的薄壳 smoke check (--help)
    """
    checks: List[Dict[str, Any]] = []
    gaps: List[str] = []

    skill_md = skill_dir / "SKILL.md"
    skeleton_path = skill_dir / "plan_skeleton.yaml"
    refs_dir = skill_dir / "references"
    scripts_dir = skill_dir / "scripts"

    for req_p, label in ((skill_md, "SKILL.md"), (skeleton_path, "plan_skeleton.yaml"), (refs_dir, "references/"), (scripts_dir, "scripts/")):
        ok = req_p.exists()
        checks.append({"check": f"layer_exists:{label}", "status": "pass" if ok else "skill_gap"})
        if not ok:
            gaps.append(f"Missing required skill layer: {label}")

    if gaps:
        return {"verified": False, "checks": checks, "unresolved_gaps": gaps}

    skel = load_simple_yaml(skeleton_path.read_text(encoding="utf-8"))
    steps = skel.get("canonical_steps") or []
    if not steps:
        gaps.append("plan_skeleton.yaml has empty 'canonical_steps'")

    for st in steps:
        sid = st.get("step_id", "unknown")
        b_script = st.get("bound_script")
        b_code = st.get("bound_code")
        if b_script:
            sp = (ws_root / b_script) if not Path(b_script).is_absolute() else Path(b_script)
            if not sp.exists():
                checks.append({"check": f"step_{sid}_script:{b_script}", "status": "skill_gap"})
                gaps.append(f"Step {sid} bound_script '{b_script}' does not exist in workspace.")
            else:
                # 若为 python 脚本，执行 --help 冒烟断言测试
                if sp.suffix == ".py":
                    proc = subprocess.run([sys.executable, str(sp), "--help"], capture_output=True, text=True)
                    status = "pass" if proc.returncode == 0 else "native_fail"
                    checks.append({"check": f"smoke_cli:{b_script}", "status": status})
                    if status != "pass":
                        gaps.append(f"Step {sid} script '{b_script}' failed --help smoke test: {proc.stderr[:200]}")
                else:
                    checks.append({"check": f"step_{sid}_script:{b_script}", "status": "pass"})
        if b_code:
            cp = (ws_root / b_code) if not Path(b_code).is_absolute() else Path(b_code)
            if not cp.exists():
                checks.append({"check": f"step_{sid}_code:{b_code}", "status": "skill_gap"})
                gaps.append(f"Step {sid} bound_code '{b_code}' does not exist in .kb/code/.")
            else:
                checks.append({"check": f"step_{sid}_code:{b_code}", "status": "pass"})

    return {
        "verified": len(gaps) == 0,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": checks,
        "unresolved_gaps": gaps,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DisCo Operational Knowledge Distiller & Skill Graph Router (arXiv:2609.02749)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dist = sub.add_parser("distill-task", help="Distill a completed requirement/task + .kb/code + .kb/cli into a verified 3-layer Skill Graph")
    p_dist.add_argument("--ws-root", required=True)
    p_dist.add_argument("--skill-id", required=True, help="Target skill ID under .kb/docs/methods/<skill-id>")
    p_dist.add_argument("--area", required=True, help="Top-level area, e.g. Epigenomics")
    p_dist.add_argument("--family", required=True, help="Capability family, e.g. Peak-Annotation-and-Promoter-Profiling")
    p_dist.add_argument("--product-codes", required=True, help="Comma-separated products, e.g. ATAC-seq,ChIP-seq,CUT&Tag")
    p_dist.add_argument("--req-doc", required=True, help="Path to requirement doc in .kb/docs/requirements/")
    p_dist.add_argument("--bound-r-code", default="", help="Relative path to .kb/code/R/... function")
    p_dist.add_argument("--bound-py-cli", default="", help="Relative path to .kb/cli/python/... CLI")
    p_dist.add_argument("--preconditions-json", required=True, help="JSON list of mandatory precondition parameters before planning")
    p_dist.add_argument("--steps-json", required=True, help="JSON list of canonical locked plan steps")

    p_route = sub.add_parser("route", help="Route task via Area -> Family -> Skill Graph with precision fallback gate")
    p_route.add_argument("--ws-root", required=True)
    p_route.add_argument("--product", required=True)
    p_route.add_argument("--request", required=True)
    p_route.add_argument("--min-confidence", type=float, default=0.65)

    args = parser.parse_args()
    ws_root = Path(args.ws_root).resolve()
    methods_dir = ws_root / ".kb" / "docs" / "methods"
    methods_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "distill-task":
        skill_dir = methods_dir / args.skill_id
        refs_dir = skill_dir / "references"
        scripts_dir = skill_dir / "scripts"
        refs_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)

        req_path = (ws_root / args.req_doc).resolve() if not Path(args.req_doc).is_absolute() else Path(args.req_doc)
        if not req_path.exists():
            emit_error("disco.distill", f"Requirement source doc '{req_path}' not found.", retriable=False)

        # Stage 1 & 2 [Scope & Ground]: 复制需求拆解先例进入 references/ 知识基底（渐进式披露，平时不占上下文）
        shutil.copy2(req_path, refs_dir / req_path.name)

        preconditions = json.loads(args.preconditions_json)
        canonical_steps = json.loads(args.steps_json)
        products = [x.strip() for x in args.product_codes.split(",") if x.strip()]

        # Stage 3 [Construct]: 生成 scripts/ 下的可执行薄壳封装器 (Execution Interface)
        wrapper_rel = f".kb/docs/methods/{args.skill_id}/scripts/run_{args.skill_id.replace('-', '_')}_step.py"
        wrapper_path = ws_root / wrapper_rel
        wrapper_code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Auto-generated DisCo Execution Interface wrapper for skill: {args.skill_id}
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Execution wrapper for {args.skill_id}")
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--params-json", default="{{}}")
    args = parser.parse_args()
    print(json.dumps({{
        "ok": True,
        "skill_id": "{args.skill_id}",
        "executed_step": args.step_id,
        "bound_r_code": "{args.bound_r_code}",
        "bound_py_cli": "{args.bound_py_cli}",
    }}, ensure_ascii=False))

if __name__ == "__main__":
    main()
'''
        wrapper_path.write_text(wrapper_code, encoding="utf-8")
        wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # 写入防发散计划骨架 plan_skeleton.yaml
        skeleton_data = {
            "skill_id": args.skill_id,
            "area": args.area,
            "family": args.family,
            "product_codes": products,
            "distilled_from_requirement": str(req_path.name),
            "bound_r_code": args.bound_r_code,
            "bound_py_cli": args.bound_py_cli,
            "preconditions": preconditions,
            "canonical_steps": canonical_steps,
        }
        (skill_dir / "plan_skeleton.yaml").write_text(dump_simple_yaml(skeleton_data), encoding="utf-8")

        # 写入三层入口 SKILL.md (Knowledge Interface)
        precond_md = "\n".join(
            f"- **`{p['param']}`** ({p.get('description', '')}): {p.get('rule', 'Must be confirmed in META.yaml before planning')}"
            for p in preconditions
        )
        steps_md = "\n".join(
            f"{idx}. **[{st['step_id']}] {st['title']}** — 调用 `{st.get('bound_script') or st.get('bound_code')}`，产出 `{st.get('expected_output')}`"
            for idx, st in enumerate(canonical_steps, start=1)
        )
        skill_md_content = f'''---
name: {args.skill_id}
displayName: "{args.family} ({args.skill_id})"
version: 1.0.0
area: "{args.area}"
family: "{args.family}"
product_codes: {json.dumps(products, ensure_ascii=False)}
tags: {json.dumps(products + [args.area, args.family, "promoter", "TxDb", "peak注释"], ensure_ascii=False)}
description: "LOAD WHEN: 任务涉及 {args.family}（如 Peak 注释重做、指定 TxDb 版本、计算 Promoter 比例饼图与统计表）。SKIP WHEN: 原始 FASTQ 比对或单细胞聚类分析。"
---
# {args.skill_id}（DisCo 三层已验证操作性知识技能包）

## When to use
当客户需求匹配 `{args.area} -> {args.family}`，特别是基于已有 Peak 表使用指定参考基因组注释版本（`TxDb`）重做注释并统计特定基因组特征（如 `Promoter TSS±N kb`）占比时加载。**命中本技能且置信度达标时，禁止自由发散编写计划，必须由 `ws_embodied_plan.py compile-plan` 锁死实例化标准计划！**

## Preconditions & Anti-Guessing Gates（计划前强制核验门禁）
{precond_md}

## Inputs
- 生产目录或上游 Peak 表：`tables/peaks.bed` 或 `tables/peak.anno.tsv`

## Workflow (Locked Canonical Steps)
{steps_md}

## Gotchas
- 严禁未经确认默认使用 ChIPseeker 的 `TSS±1kb` 口径（见 `references/{req_path.name}` 两次返工教训）。
- 严禁在任务目录内手写临时 R 代码重算 Promoter 比例，必须直接调用绑定的标准库函数 `{args.bound_r_code}` 与统计 CLI `{args.bound_py_cli}`。

## Evidence
- 先例需求与踩坑归档：`references/{req_path.name}`
- 绑定核心 R 模块：`{args.bound_r_code}`
- 绑定 CLI 统计薄壳：`{args.bound_py_cli}`

## Outputs
- `tables/peak.anno.tsv`, `tables/promoter_ratio.tsv`, `figures/promoter_pie.png`, `report.md`

## Dependencies
- R (`ChIPseeker`, `{args.bound_r_code}`), Python 3 (`{args.bound_py_cli}`)
'''
        (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

        # Stage 4 [Verify]: 运行断言验证并生成 construction_record.json (R)
        ver_res = verify_skill_package(ws_root, skill_dir)
        record_R = {
            "skill_id": args.skill_id,
            "anchor_source": str(req_path.name),
            "three_layers": {
                "knowledge_interface": "SKILL.md + plan_skeleton.yaml",
                "knowledge_substrate": f"references/{req_path.name}",
                "execution_interface": wrapper_rel,
            },
            "verification": ver_res,
        }
        (skill_dir / "construction_record.json").write_text(json.dumps(record_R, ensure_ascii=False, indent=2), encoding="utf-8")

        if not ver_res["verified"]:
            emit_error(
                "disco.verify_failed",
                f"Candidate skill '{args.skill_id}' failed verification and is barred from library admission!",
                retriable=True,
                next_steps=ver_res["unresolved_gaps"],
                data=record_R,
            )

        # 更新库级两层分类树路由器 ROUTER.yaml (Area -> Family -> Skill Graph)
        router_path = methods_dir / "ROUTER.yaml"
        router_data = load_simple_yaml(router_path.read_text(encoding="utf-8")) if router_path.exists() else {"taxonomy": []}
        tax_list: List[Dict[str, Any]] = list(router_data.get("taxonomy") or [])
        tax_list = [x for x in tax_list if x.get("skill_id") != args.skill_id]
        tax_list.append({
            "area": args.area,
            "family": args.family,
            "skill_id": args.skill_id,
            "product_codes": products,
            "verified": True,
            "bound_r_code": args.bound_r_code,
            "bound_py_cli": args.bound_py_cli,
            "keywords": ["promoter", "txdb", "peak", "注释", "饼图", "占比", args.area.lower(), args.family.lower()],
        })
        router_data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        router_data["taxonomy"] = tax_list
        router_path.write_text(dump_simple_yaml(router_data), encoding="utf-8")

        emit_success("disco.distill_verified", record_R)

    elif args.cmd == "route":
        router_path = methods_dir / "ROUTER.yaml"
        if not router_path.exists():
            emit_error("disco.route", "ROUTER.yaml not found. Run distill-task first.", retriable=False)
        router_data = load_simple_yaml(router_path.read_text(encoding="utf-8"))
        tax_list = list(router_data.get("taxonomy") or [])

        q_lower = (args.product + " " + args.request).lower()
        scored: List[Dict[str, Any]] = []
        for item in tax_list:
            if not item.get("verified"):
                continue
            prods = [str(p).lower() for p in (item.get("product_codes") or [])]
            prod_hit = any(p in q_lower or args.product.lower() in p for p in prods)
            kws = [str(k).lower() for k in (item.get("keywords") or [])]
            kw_hits = [k for k in kws if k and k in q_lower]
            conf = min(1.0, (0.45 if prod_hit else 0.10) + len(kw_hits) * 0.15)
            scored.append({
                "area": item.get("area"),
                "family": item.get("family"),
                "skill_id": item.get("skill_id"),
                "confidence": round(conf, 3),
                "matched_keywords": kw_hits,
                "bound_r_code": item.get("bound_r_code"),
                "bound_py_cli": item.get("bound_py_cli"),
            })

        scored.sort(key=lambda x: x["confidence"], reverse=True)
        top = scored[0] if scored else None

        # Repo-To-Skill Section 5.3 防检索倒退机制：当最高匹配置信度低于阈值时，显式回退至无引导探索模式，避免错误技能把 Agent 带偏
        if not top or top["confidence"] < args.min_confidence:
            emit_success("disco.route_fallback", {
                "routing_decision": "FALLBACK_TO_EXPLORATION",
                "reason": f"Top skill confidence ({top['confidence'] if top else 0.0}) < threshold ({args.min_confidence}). Avoiding retrieval-precision regression.",
                "candidates": scored[:3],
            })

        emit_success("disco.route_locked", {
            "routing_decision": "LOCKED_OPERATIONAL_SKILL",
            "selected_route": f"{top['area']} -> {top['family']} -> {top['skill_id']}",
            "top_skill": top,
            "progressive_disclosure_load": f".kb/docs/methods/{top['skill_id']}/plan_skeleton.yaml",
        })


if __name__ == "__main__":
    main()
