#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_env_skill_router.py — 两阶段方案路由器 + 深度环境预核验与防篡改快照引擎
解决求教 B.1（需求类型→标准方案路由）、隐患 A.3（存在性≠完备性）、盲区 1（分析中途上游文件静默漂移）。
核心功能：
1. build-index: 扫描 .kb/docs/methods/*/SKILL.md 的 frontmatter 生成 SKILL_INDEX.yaml
2. check:
   - 核验生产目录真实路径、软链接是否断裂 (broken symlink)、文件是否非空 (>0 bytes)
   - 提取样本表 (sample_sheet.tsv) 首列样本 ID 与产物目录文件名做交集校验
   - 计算上游核心结果表格的 (size, mtime, sha256_head64k) 指纹并写入 .env_check.yaml
   - 执行两阶段方案路由：Stage 1 按 product_codes 硬过滤；Stage 2 按 tags/load_when 词面打分并检查 skip_when 冲突
3. verify-drift: 收尾前二次校验上游文件指纹，拦截中途静默重跑覆盖
"""
import argparse
import glob
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ws_contract import emit_error, emit_success
from ws_meta import dump_simple_yaml, load_simple_yaml


def parse_skill_frontmatter(md_path: Path) -> Dict[str, Any]:
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = load_simple_yaml(parts[1])
    fm["skill_id"] = md_path.parent.name
    fm["path"] = str(md_path)
    desc = str(fm.get("description", ""))
    # 解析 load/skip 双半描述
    load_part, skip_part = desc, ""
    if "SKIP WHEN:" in desc.upper():
        idx = desc.upper().index("SKIP WHEN:")
        load_part = desc[:idx].replace("LOAD WHEN:", "").replace("load when:", "").strip()
        skip_part = desc[idx + 10:].strip()
    fm["load_when"] = fm.get("load_when", load_part)
    fm["skip_when"] = fm.get("skip_when", skip_part)
    return fm


def file_fingerprint(p: Path) -> Dict[str, Any]:
    real = p.resolve()
    st = real.stat()
    h = hashlib.sha256()
    with open(real, "rb") as f:
        h.update(f.read(65536))
    return {
        "rel_path": p.name,
        "real_path": str(real),
        "size_bytes": st.st_size,
        "mtime": round(st.st_mtime, 3),
        "sha256_head64k": h.hexdigest(),
    }


def tokenize_terms(text: str) -> List[str]:
    norm = re.sub(r"[-_/]", " ", text.lower())
    en_tokens = re.findall(r"[a-z0-9]{2,}", norm)
    zh_bigrams = [norm[i:i+2] for i in range(len(norm) - 1) if "\u4e00" <= norm[i] <= "\u9fff" and "\u4e00" <= norm[i+1] <= "\u9fff"]
    return list(set(en_tokens + zh_bigrams))


def route_skills(index_items: List[Dict[str, Any]], product: str, request_text: str) -> List[Dict[str, Any]]:
    req_tokens = set(tokenize_terms(product + " " + request_text))
    candidates: List[Dict[str, Any]] = []

    for item in index_items:
        prod_codes = [str(x).lower() for x in (item.get("product_codes") or [])]
        product_match = (not prod_codes) or (product.lower() in prod_codes) or any(p in product.lower() for p in prod_codes)

        tags = [str(x) for x in (item.get("tags") or [])]
        load_text = str(item.get("load_when", "")) + " " + " ".join(tags)
        skip_text = str(item.get("skip_when", ""))

        load_tokens = set(tokenize_terms(load_text))
        skip_tokens = set(tokenize_terms(skip_text))

        overlap_load = len(req_tokens & load_tokens)
        # 仅统计特定负向词命中
        negative_triggers = [t for t in skip_tokens if len(t) >= 2 and t not in load_tokens and t in req_tokens]

        score = (10.0 if product_match else 0.0) + overlap_load * 1.5 - len(negative_triggers) * 4.0
        candidates.append({
            "skill_id": item.get("skill_id"),
            "name": item.get("name", item.get("skill_id")),
            "product_match": product_match,
            "route_score": round(score, 2),
            "load_when": item.get("load_when", ""),
            "skip_when": item.get("skip_when", ""),
            "skip_warnings": negative_triggers,
            "locked_params": item.get("locked_params", {}),
            "required_inputs": item.get("required_inputs", []),
            "path": item.get("path"),
        })

    candidates.sort(key=lambda x: x["route_score"], reverse=True)
    # 优先返回同产品线 Top-5，若无同产品线则返回全局 Top-3
    prod_filtered = [c for c in candidates if c["product_match"]]
    return (prod_filtered[:5] if prod_filtered else candidates[:3])


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-stage SKILL router and deep environment pre-verifier")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_idx = sub.add_parser("build-index", help="Build .kb/docs/methods/SKILL_INDEX.yaml")
    p_idx.add_argument("--ws-root", required=True)

    p_chk = sub.add_parser("check", help="Deep verify production source_dir and route candidate skills")
    p_chk.add_argument("--ws-root", required=True)
    p_chk.add_argument("--task-dir", required=True)
    p_chk.add_argument("--source-dir", required=True)
    p_chk.add_argument("--product", required=True)
    p_chk.add_argument("--request", required=True)

    p_drift = sub.add_parser("verify-drift", help="Verify upstream files have not mutated mid-analysis")
    p_drift.add_argument("--task-dir", required=True)

    args = parser.parse_args()

    if args.cmd == "build-index":
        ws_root = Path(args.ws_root).resolve()
        methods_dir = ws_root / ".kb" / "docs" / "methods"
        methods_dir.mkdir(parents=True, exist_ok=True)
        items: List[Dict[str, Any]] = []
        for sk_md in sorted(methods_dir.glob("*/SKILL.md")):
            fm = parse_skill_frontmatter(sk_md)
            if fm:
                items.append(fm)
        idx_path = methods_dir / "SKILL_INDEX.yaml"
        idx_path.write_text(dump_simple_yaml({"updated_at": time.time(), "skills": items}), encoding="utf-8")
        emit_success("skill_router.build_index", {"index_path": str(idx_path), "skill_count": len(items)})

    elif args.cmd == "check":
        ws_root = Path(args.ws_root).resolve()
        task_dir = Path(args.task_dir).resolve()
        source_dir = Path(args.source_dir).resolve()
        methods_dir = ws_root / ".kb" / "docs" / "methods"

        if not source_dir.exists() or not source_dir.is_dir():
            emit_error(
                "env_check.missing_source_dir",
                f"Production directory '{source_dir}' does not exist or is not a directory.",
                retriable=False,
                next_steps=["Ask human user to verify 'source_dir' on the inbox card before accepting."],
                task_dir=task_dir,
            )

        # 1. 扫描悬空软链接、0字节空文件与有效数据文件指纹
        broken_symlinks: List[str] = []
        empty_files: List[str] = []
        fingerprints: Dict[str, Dict[str, Any]] = {}

        for p in sorted(source_dir.rglob("*")):
            rel = str(p.relative_to(source_dir))
            if p.is_symlink() and not p.exists():
                broken_symlinks.append(rel)
                continue
            if p.is_file():
                if p.stat().st_size == 0:
                    empty_files.append(rel)
                elif p.suffix.lower() in (".tsv", ".csv", ".txt", ".yaml", ".json", ".bed", ".xls", ".xlsx"):
                    fingerprints[rel] = file_fingerprint(p)

        # 2. 样本表 ID 与产物文件交集核验
        sample_sheet_check: Dict[str, Any] = {"found": False}
        for ss_name in ("sample_sheet.tsv", "samples.tsv", "sample_info.txt", "metadata.tsv"):
            ss_path = source_dir / ss_name
            if ss_path.exists() and ss_path.stat().st_size > 0:
                lines = [ln.strip() for ln in ss_path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
                if len(lines) > 1:
                    samples = [ln.split("\t")[0].strip() for ln in lines[1:] if ln.split("\t")[0].strip()]
                    all_filenames = " ".join(fingerprints.keys())
                    matched = [s for s in samples if s in all_filenames]
                    sample_sheet_check = {
                        "found": True,
                        "file": ss_name,
                        "total_samples": len(samples),
                        "matched_in_filenames": len(matched),
                        "unmatched_samples": [s for s in samples if s not in matched],
                    }
                break

        # 3. 加载或自动构建 SKILL_INDEX 并执行两阶段路由
        skills_list: List[Dict[str, Any]] = []
        for sk_md in sorted(methods_dir.glob("*/SKILL.md")):
            fm = parse_skill_frontmatter(sk_md)
            if fm:
                skills_list.append(fm)
        candidates = route_skills(skills_list, args.product, args.request)

        # 4. 校验 Top-1 候选 SKILL 的 required_inputs glob 是否满足
        missing_required_inputs: List[str] = []
        if candidates:
            top_req = candidates[0].get("required_inputs") or []
            for pattern in top_req:
                matches = list(source_dir.glob(pattern))
                if not matches:
                    missing_required_inputs.append(pattern)

        env_report = {
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_dir": str(source_dir),
            "valid_file_count": len(fingerprints),
            "broken_symlinks": broken_symlinks,
            "empty_files": empty_files,
            "sample_sheet_check": sample_sheet_check,
            "missing_required_inputs": missing_required_inputs,
            "candidate_skills": candidates,
            "upstream_fingerprints": fingerprints,
        }

        task_dir.mkdir(parents=True, exist_ok=True)
        env_file = task_dir / ".env_check.yaml"
        env_file.write_text(dump_simple_yaml(env_report), encoding="utf-8")

        if broken_symlinks or empty_files or missing_required_inputs:
            emit_error(
                "env_check.incomplete_upstream",
                "Upstream production directory exists but failed completeness checks (broken symlinks, 0-byte files, or missing required skill inputs).",
                retriable=False,
                next_steps=[
                    f"Broken symlinks: {broken_symlinks}",
                    f"0-byte empty files: {empty_files}",
                    f"Missing required skill inputs: {missing_required_inputs}",
                    "Do NOT guess or fabricate missing tables. Keep task in 'planned' or 'blocked' and ask upstream engineer.",
                ],
                data=env_report,
                task_dir=task_dir,
            )

        emit_success("env_check.passed", env_report, task_dir=task_dir)

    elif args.cmd == "verify-drift":
        task_dir = Path(args.task_dir).resolve()
        env_file = task_dir / ".env_check.yaml"
        if not env_file.exists():
            emit_error("env_check.verify_drift", ".env_check.yaml not found.", retriable=False,
                       next_steps=["Run ws_env_skill_router.py check first."], task_dir=task_dir)
        env_data = load_simple_yaml(env_file.read_text(encoding="utf-8"))
        source_dir = Path(str(env_data.get("source_dir", "")))
        recorded_fps: Dict[str, Any] = env_data.get("upstream_fingerprints") or {}
        drifted: List[Dict[str, Any]] = []

        for rel, old_fp in recorded_fps.items():
            p = source_dir / rel
            if not p.exists():
                drifted.append({"file": rel, "reason": "deleted_mid_flight"})
                continue
            cur_fp = file_fingerprint(p)
            if cur_fp["sha256_head64k"] != old_fp.get("sha256_head64k") or cur_fp["size_bytes"] != old_fp.get("size_bytes"):
                drifted.append({
                    "file": rel,
                    "reason": "modified_mid_flight",
                    "old_sha256": old_fp.get("sha256_head64k"),
                    "new_sha256": cur_fp["sha256_head64k"],
                })

        if drifted:
            emit_error(
                "env_check.upstream_drift_detected",
                f"{len(drifted)} upstream file(s) were silently modified or overwritten during analysis!",
                retriable=True,
                next_steps=[
                    "Re-run ws_env_skill_router.py check to refresh .env_check.yaml.",
                    "Re-generate affected tables/figures and update report.md so all numbers reflect the new upstream batch.",
                ],
                data={"drifted_files": drifted},
                task_dir=task_dir,
            )
        emit_success("env_check.verify_drift", {"drifted_files": [], "checked_count": len(recorded_fps)}, task_dir=task_dir)


if __name__ == "__main__":
    main()
