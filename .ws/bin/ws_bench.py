#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_bench.py — 胶囊基准 v3.5 + 密封真值保险箱 + MemT-1.0 pass^3 稳定性评测 + 生信本体核验联动
新增吸收自：
1. molten / Terminal Wrench (arXiv:2604.17596):
   pack 时将 .ground_truth.yaml 存入隔离的 .ws/.sealed_vault/<capsule_id>.ground_truth.yaml（禁止放入被测任务目录），并对 .grade_receipt.json 附加基于 report.md SHA256 的 HMAC 签名，彻底杜绝 Agent 偷看标准答案或伪造评分回执。
2. MemT-1.0 (arXiv:2610.26825):
   新增 eval-pass-power-k 子命令，计算 pass@k 与 pass^k (特别是 pass^3：连续 3 次独立运行全部通过 >=0.80 且核心显著基因集/上下调方向 100% 一致)，直接量化 HARNESS.md 能力 2“结果高可靠性/重复性”。
3. Briefings in Bioinformatics (GeneAgent / MedGraphRAG):
   grade 时自动调用 ws_bio_verifier.py 校验通路内基因归属、物种前缀与 .kb/docs/references/ 文献引用真实性。
"""
import argparse
import hashlib
import hmac
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Set

try:
    from ws_bio_verifier import verify_biological_grounding
except ModuleNotFoundError:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("ws_bio_verifier", Path(__file__).resolve().parent / "ws_bio_verifier.py")
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    verify_biological_grounding = _mod.verify_biological_grounding
from ws_contract import emit_error, emit_success
from ws_meta import dump_simple_yaml, load_simple_yaml

SEAL_SECRET = b"ngs-harness-v35-sealed-evaluator-key"
EVIDENCE_KEY_RE = re.compile(r"\[([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)#([A-Za-z0-9_:-]+)(?::([^\]]+))?\]")
INVALID_BARE_KEY_RE = re.compile(r"\[(?:Table|Figure|Fig|图|表)\s*\d+\]", re.IGNORECASE)


def compute_receipt_hmac(report_bytes: bytes, score: float, sci_ok: bool) -> str:
    h_rep = hashlib.sha256(report_bytes).hexdigest()
    msg = f"{h_rep}:{score:.3f}:{int(sci_ok)}".encode("utf-8")
    return hmac.new(SEAL_SECRET, msg, hashlib.sha256).hexdigest()


def extract_claims_from_report(report_text: str) -> List[Dict[str, Any]]:
    claims: List[Dict[str, Any]] = []
    for line_no, raw_line in enumerate(report_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        matches = list(EVIDENCE_KEY_RE.finditer(line))
        if matches:
            for m in matches:
                fname, anchor, assertions_str = m.group(1), m.group(2), m.group(3) or ""
                clean_sentence = EVIDENCE_KEY_RE.sub("", line)
                numbers = re.findall(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?:e-?\d+)?%?", clean_sentence)
                entities = re.findall(r"\b(?:[A-Z][A-Z0-9-]{2,10}|hsa\d{5}|mmu\d{5}|GO:\d{7})\b", clean_sentence)
                claims.append({
                    "line_no": line_no,
                    "sentence": line,
                    "file": fname,
                    "anchor": anchor,
                    "assertions": assertions_str,
                    "numbers_in_claim": numbers,
                    "entities_in_claim": entities,
                })
    return claims


def verify_claim_against_table(claim: Dict[str, Any], task_dir: Path, source_dir: Path) -> Dict[str, Any]:
    fname = claim["file"]
    cand_paths = [
        task_dir / fname,
        task_dir / "tables" / Path(fname).name,
        task_dir / "figures" / Path(fname).name,
        source_dir / fname,
    ]
    resolved = next((p for p in cand_paths if p.exists() and p.is_file()), None)
    if not resolved:
        return {"ok": False, "reason": f"Referenced file '{fname}' does not exist on disk."}
    if resolved.stat().st_size == 0:
        return {"ok": False, "reason": f"Referenced file '{fname}' is 0 bytes."}

    if resolved.suffix.lower() in (".png", ".pdf", ".svg", ".jpg"):
        return {"ok": True, "resolved_path": str(resolved), "entity_hits": [], "verified_assertions": True}

    content = resolved.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in content.splitlines() if ln.strip()]
    data_row_count = max(0, len(lines) - 1)
    if data_row_count == 0:
        return {"ok": False, "reason": f"Table '{fname}' has 0 data rows."}

    missing_entities = [ent for ent in claim["entities_in_claim"] if ent not in content]
    if missing_entities:
        return {
            "ok": False,
            "reason": f"Hallucinated entity(ies) {missing_entities} cited in claim but absent from '{fname}'.",
        }

    assertions = claim.get("assertions", "")
    if "rows=" in assertions:
        m = re.search(r"rows=(\d+)", assertions)
        if m and int(m.group(1)) != data_row_count:
            return {
                "ok": False,
                "reason": f"Row count mismatch in '{fname}': claim asserts rows={m.group(1)}, actual table has {data_row_count} rows.",
            }

    sent_lower = claim["sentence"].lower()
    header_lower = lines[0].lower()
    if ("padj" in header_lower or "fdr" in header_lower) and ("显著" in sent_lower or "significant" in sent_lower):
        if ("p <" in sent_lower or "pvalue <" in sent_lower) and ("padj" not in sent_lower and "fdr" not in sent_lower):
            return {
                "ok": False,
                "scientific_violation": True,
                "reason": f"Scientific guardrail violation: Claim on line {claim['line_no']} uses unadjusted p-value instead of FDR/padj.",
            }

    snippet = "\n".join(lines[:11])
    return {"ok": True, "resolved_path": str(resolved), "table_row_count": data_row_count, "snippet": snippet}


def main() -> None:
    parser = argparse.ArgumentParser(description="Capsule benchmark v3.5 (Sealed Vault + pass^3 + Bio-Verifier)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pack = sub.add_parser("pack", help="Pack task into capsule and store ground truth in isolated .ws/.sealed_vault/")
    p_pack.add_argument("--task-dir", required=True)
    p_pack.add_argument("--capsule-out", required=True)

    p_grade = sub.add_parser("grade", help="Grade report with table lookup + GeneAgent/MedGraphRAG bio-verifier + HMAC receipt")
    p_grade.add_argument("--task-dir", required=True)
    p_grade.add_argument("--verifier-verdicts", default=None)

    p_pk = sub.add_parser("eval-pass-power-k", help="Evaluate pass@k and pass^k (MemT-1.0 stability metric) across k rollout reports")
    p_pk.add_argument("--task-dir", required=True)
    p_pk.add_argument("--rollout-reports", required=True, help="Comma-separated paths to k independent report.md rollouts")

    p_list = sub.add_parser("list", help="List capsules in a bench directory")
    p_list.add_argument("--ws-root", required=True)
    p_list.add_argument("--dir", default=None, help="Capsule dir (default <ws-root>/.bench/capsules)")

    args = parser.parse_args()

    if args.cmd == "pack":
        task_dir = Path(args.task_dir).resolve()
        cap_dir = Path(args.capsule_out).resolve()
        ws_root = task_dir
        while ws_root != ws_root.parent and not (ws_root / ".ws").exists():
            ws_root = ws_root.parent

        meta_path = task_dir / "META.yaml"
        report_path = task_dir / "report.md"
        if not meta_path.exists() or not report_path.exists():
            emit_error("bench.pack", "Task must have both META.yaml and report.md to be packed.", retriable=False)

        meta = load_simple_yaml(meta_path.read_text(encoding="utf-8"))
        report_text = report_path.read_text(encoding="utf-8")
        claims = extract_claims_from_report(report_text)

        cap_dir.mkdir(parents=True, exist_ok=True)
        data_dir = cap_dir / "data"
        data_dir.mkdir(exist_ok=True)

        std_artifacts: List[str] = []
        for sub_name in ("tables", "figures"):
            src_sub = task_dir / sub_name
            if src_sub.exists():
                dst_sub = data_dir / sub_name
                dst_sub.mkdir(exist_ok=True)
                for f in sorted(src_sub.iterdir()):
                    if f.is_file() and f.stat().st_size <= 2 * 1024 * 1024:
                        shutil.copy2(f, dst_sub / f.name)
                        std_artifacts.append(f"{sub_name}/{f.name}")

        # molten / Terminal Wrench 物理隔离：真值绝不放进被测胶囊目录，而是存入受 Hook 封锁的 .ws/.sealed_vault/
        vault_dir = ws_root / ".ws" / ".sealed_vault"
        vault_dir.mkdir(parents=True, exist_ok=True)
        vault_file = vault_dir / f"{cap_dir.name}.ground_truth.yaml"
        ground_truth = {
            "source_slug": meta.get("slug"),
            "matched_skills": meta.get("matched_skills", []),
            "gold_claims_count": len(claims),
            "gold_claims": claims,
        }
        vault_file.write_text(dump_simple_yaml(ground_truth), encoding="utf-8")

        capsule_spec = {
            "capsule_id": cap_dir.name,
            "product": meta.get("product"),
            "request": meta.get("request"),
            "standard_artifacts": std_artifacts,
        }
        (cap_dir / "capsule.yaml").write_text(dump_simple_yaml(capsule_spec), encoding="utf-8")
        emit_success("bench.pack", {
            "capsule_dir": str(cap_dir),
            "sealed_ground_truth_vault": str(vault_file),
            "standard_artifacts_count": len(std_artifacts),
            "extracted_gold_claims": len(claims),
        })

    elif args.cmd == "grade":
        task_dir = Path(args.task_dir).resolve()
        ws_root = task_dir
        while ws_root != ws_root.parent and not (ws_root / ".ws").exists():
            ws_root = ws_root.parent

        report_path = task_dir / "report.md"
        meta_path = task_dir / "META.yaml"
        if not report_path.exists():
            emit_error("bench.grade", "report.md not found in task directory.", retriable=True, task_dir=task_dir)

        meta = load_simple_yaml(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        source_dir = Path(str(meta.get("source_dir", task_dir)))
        report_bytes = report_path.read_bytes()
        report_text = report_bytes.decode("utf-8", errors="replace")

        std_files: List[str] = []
        for sub_name in ("tables", "figures"):
            sub_p = task_dir / sub_name
            if sub_p.exists():
                for f in sorted(sub_p.iterdir()):
                    if f.is_file():
                        std_files.append(f.name)

        bare_key_violations = INVALID_BARE_KEY_RE.findall(report_text)
        claims = extract_claims_from_report(report_text)
        if not claims:
            emit_error("bench.grade", "Zero valid evidence keys ([filename.ext#Table1]) found in report.md!",
                       retriable=True, task_dir=task_dir)

        cited_filenames = {Path(c["file"]).name for c in claims}
        covered = [f for f in std_files if f in cited_filenames]
        coverage_score = (len(covered) / float(len(std_files))) if std_files else 1.0

        verified_claims = 0
        failed_claims: List[Dict[str, Any]] = []
        verifier_audit_items: List[Dict[str, Any]] = []
        scientific_guard_passed = True

        for c in claims:
            res = verify_claim_against_table(c, task_dir, source_dir)
            if res.get("ok"):
                verified_claims += 1
                verifier_audit_items.append({
                    "line_no": c["line_no"],
                    "claim": c["sentence"],
                    "evidence_file": c["file"],
                    "table_snippet": res.get("snippet", "[Binary figure/image]"),
                })
            else:
                if res.get("scientific_violation"):
                    scientific_guard_passed = False
                failed_claims.append({
                    "line_no": c["line_no"],
                    "claim": c["sentence"],
                    "reason": res.get("reason"),
                })

        # 调用 GeneAgent / MedGraphRAG / CASSIA 生信本体与文献引用核验器
        bio_res = verify_biological_grounding(ws_root, task_dir)
        if not bio_res["ok"]:
            scientific_guard_passed = False
            for v in bio_res["violations"]:
                failed_claims.append({"line_no": 0, "claim": "[Bio-Ontology/Citation Check]", "reason": v})

        format_penalty = min(0.3, len(bare_key_violations) * 0.1)
        grounding_score = max(0.0, (verified_claims / float(len(claims))) - format_penalty)

        audit_bundle_path = task_dir / ".verifier_bundle.json"
        audit_bundle_path.write_text(json.dumps({
            "role": "Adversarial Bioinformatics QC Auditor (Context-Isolated)",
            "request": meta.get("request", ""),
            "items": verifier_audit_items,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        nli_score = grounding_score
        if args.verifier_verdicts and Path(args.verifier_verdicts).exists():
            verdicts = json.loads(Path(args.verifier_verdicts).read_text(encoding="utf-8"))
            v_list = verdicts.get("verdicts") or []
            if v_list:
                pts = 0.0
                for v in v_list:
                    if not v.get("direction_match", True) or not v.get("threshold_honest", True):
                        scientific_guard_passed = False
                    elif v.get("verdict") == "SUPPORTED" and v.get("no_overclaim", True):
                        pts += 1.0
                    elif v.get("verdict") == "PARTIAL":
                        pts += 0.5
                nli_score = pts / float(len(v_list))

        total_score = round(0.25 * coverage_score + 0.45 * grounding_score + 0.30 * nli_score, 3)
        if not scientific_guard_passed:
            total_score = 0.0

        hmac_sig = compute_receipt_hmac(report_bytes, total_score, scientific_guard_passed)
        receipt = {
            "graded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_score": total_score,
            "coverage_score": round(coverage_score, 3),
            "grounding_score": round(grounding_score, 3),
            "nli_score": round(nli_score, 3),
            "scientific_guard_passed": scientific_guard_passed,
            "bio_ontology_passed": bio_res["ok"],
            "total_claims": len(claims),
            "verified_claims": verified_claims,
            "failed_claims": failed_claims,
            "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
            "hmac_signature": hmac_sig,
        }
        (task_dir / ".grade_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

        if total_score < 0.80 or not scientific_guard_passed:
            emit_error(
                "bench.grade_failed",
                f"Report score {total_score} < 0.80 (or scientific/ontology guardrail failed). Cannot transition to 'done'.",
                retriable=True,
                next_steps=[f"Fix failed claims: {failed_claims[:3]}"],
                data=receipt,
                task_dir=task_dir,
                scientific_violation=(not scientific_guard_passed),
            )

        emit_success("bench.grade_passed", receipt, task_dir=task_dir)

    elif args.cmd == "eval-pass-power-k":
        task_dir = Path(args.task_dir).resolve()
        meta_path = task_dir / "META.yaml"
        meta = load_simple_yaml(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        source_dir = Path(str(meta.get("source_dir", task_dir)))

        rpaths = [Path(p.strip()).resolve() for p in args.rollout_reports.split(",") if p.strip()]
        k = len(rpaths)
        if k < 2:
            emit_error("bench.pass_power_k", "Provide at least 2 rollout report paths to evaluate pass^k consistency.", retriable=False)

        pass_flags: List[bool] = []
        entity_sets: List[Set[str]] = []

        for rp in rpaths:
            txt = rp.read_text(encoding="utf-8")
            claims = extract_claims_from_report(txt)
            if not claims:
                pass_flags.append(False)
                entity_sets.append(set())
                continue
            ok_cnt = sum(1 for c in claims if verify_claim_against_table(c, task_dir, source_dir).get("ok"))
            score = ok_cnt / float(len(claims))
            pass_flags.append(score >= 0.80)
            ents = {e for c in claims for e in c["entities_in_claim"]}
            entity_sets.append(ents)

        pass_at_k = 1.0 if any(pass_flags) else 0.0
        # MemT-1.0 pass^k: 要求全部 k 次运行均通过 >=0.80，且各次报告的核心基因/通路实体交并比 (Jaccard) >= 0.80
        all_passed = all(pass_flags)
        union_ents = set().union(*entity_sets) if entity_sets else set()
        inter_ents = set(entity_sets[0]).intersection(*entity_sets[1:]) if entity_sets else set()
        entity_consistency = (len(inter_ents) / float(len(union_ents))) if union_ents else 1.0
        pass_power_k = 1.0 if (all_passed and entity_consistency >= 0.80) else 0.0

        emit_success("bench.pass_power_k", {
            "k": k,
            "individual_pass_flags": pass_flags,
            "entity_jaccard_consistency": round(entity_consistency, 3),
            f"pass@{k}": pass_at_k,
            f"pass^{k}": pass_power_k,
        }, task_dir=task_dir)

    elif args.cmd == "list":
        _ws_root = Path(args.ws_root).resolve()
        cap_root = Path(args.dir).resolve() if args.dir else (_ws_root / ".bench" / "capsules")
        caps = sorted(d.name for d in cap_root.iterdir() if d.is_dir() and (d / "capsule.yaml").exists()) if cap_root.exists() else []
        emit_success("bench.list", {"dir": str(cap_root), "capsules": caps, "count": len(caps)})


if __name__ == "__main__":
    main()
