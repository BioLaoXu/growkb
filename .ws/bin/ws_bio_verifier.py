#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_bio_verifier.py — 生物信息领域幻觉自核验器 (吸收自 Briefings in Bioinformatics 2026 综述: GeneAgent / MedGraphRAG / CASSIA)
解决生信 Agent 最致命的三类领域幻觉：
1. GeneAgent 基因-通路归属幻觉 (Ontology Affiliation Hallucination)：
   Agent 在报告中声称“STAT1 参与了某通路 GO:xxxx / hsa04630”，但实际上富集分析表 (enrichment.tsv) 的该通路 geneID 列里根本没有 STAT1，或该通路 padj 不显著。
2. MedGraphRAG 文献/方法依据伪造幻觉 (Fabricated Citation / PMID Hallucination)：
   Agent 在报告“方案依据/参考文献”中编造不存在的文献引用或未在 .kb/docs/references/ 登记的孤儿引用。
3. CASSIA 物种/组织跨界错配幻觉 (Species/Context Mismatch)：
   例如人类 (GRCh38/hg38) 样本报告中混入小鼠 (mm10/Mgi) 特有基因大小写格式或相反。
"""
import argparse
import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Set

from ws_contract import emit_error, emit_success
from ws_meta import load_simple_yaml

PATHWAY_ID_RE = re.compile(r"\b(GO:\d{7}|hsa\d{5}|mmu\d{5}|ko\d{5}|R-HSA-\d+)\b")
REF_CITE_RE = re.compile(r"\[Ref:\s*([A-Za-z0-9_.-]+)\]")
RAW_PMID_DOI_RE = re.compile(r"\b(?:PMID:\s*\d{5,9}|10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b", re.IGNORECASE)


def load_enrichment_map(task_dir: Path, source_dir: Path) -> Dict[str, Dict[str, Any]]:
    """扫描 tables/ 下所有富集分析表 (GO/KEGG/Reactome)，建立 pathway_id -> {genes, padj, desc} 映射。"""
    pmap: Dict[str, Dict[str, Any]] = {}
    cand_dirs = [task_dir / "tables", source_dir / "tables", source_dir]
    for d in cand_dirs:
        if not d.exists() or not d.is_dir():
            continue
        for f in sorted(d.glob("*.tsv")) + sorted(d.glob("*.csv")):
            delim = "," if f.suffix.lower() == ".csv" else "\t"
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fp:
                    reader = csv.DictReader(fp, delimiter=delim)
                    headers = {h.lower(): h for h in (reader.fieldnames or [])}
                    id_col = next((headers[c] for c in ("id", "pathway_id", "term_id", "go_id", "kegg_id") if c in headers), None)
                    gene_col = next((headers[c] for c in ("geneid", "genes", "gene_symbol", "core_enrichment", "Leading_edge") if c.lower() in headers), None)
                    padj_col = next((headers[c] for c in ("padj", "p.adjust", "qvalue", "fdr") if c in headers), None)
                    if not id_col:
                        continue
                    for row in reader:
                        pid = str(row.get(id_col, "")).strip()
                        if not pid:
                            continue
                        raw_genes = str(row.get(gene_col, "")) if gene_col else ""
                        genes = set(re.split(r"[/,;\s]+", raw_genes.strip())) - {""}
                        try:
                            padj = float(row.get(padj_col, "1.0")) if padj_col else 1.0
                        except Exception:
                            padj = 1.0
                        pmap[pid] = {"genes": genes, "padj": padj, "file": f.name}
            except Exception:
                continue
    return pmap


def load_registered_references(ws_root: Path) -> Set[str]:
    ref_dir = ws_root / ".kb" / "docs" / "references"
    ids: Set[str] = set()
    if ref_dir.exists():
        for f in ref_dir.rglob("*"):
            if f.is_file():
                ids.add(f.stem)
                ids.add(f.name)
    return ids


def verify_biological_grounding(ws_root: Path, task_dir: Path) -> Dict[str, Any]:
    report_path = task_dir / "report.md"
    meta_path = task_dir / "META.yaml"
    if not report_path.exists():
        return {"ok": False, "violations": ["report.md missing"]}

    report_text = report_path.read_text(encoding="utf-8")
    meta = load_simple_yaml(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    source_dir = Path(str(meta.get("source_dir", task_dir)))
    species = str(meta.get("species", "human")).lower()

    enrichment_map = load_enrichment_map(task_dir, source_dir)
    valid_refs = load_registered_references(ws_root)
    violations: List[str] = []

    for line_no, raw_line in enumerate(report_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # 1. GeneAgent 校验：若同一句同时提及通路 ID 与基因名，核对基因是否真属于该富集通路且通路显著
        pids = PATHWAY_ID_RE.findall(line)
        if pids and enrichment_map:
            candidate_genes = re.findall(r"\b[A-Z][A-Z0-9-]{2,10}\b", line)
            for pid in pids:
                if pid not in enrichment_map:
                    violations.append(f"Line {line_no}: Pathway '{pid}' is not present in any enrichment table.")
                    continue
                pinfo = enrichment_map[pid]
                if pinfo["padj"] >= 0.05 and ("显著" in line or "significant" in line.lower()):
                    violations.append(
                        f"Line {line_no}: Pathway '{pid}' claimed as significant but has padj={pinfo['padj']} >= 0.05 in {pinfo['file']}."
                    )
                if pinfo["genes"]:
                    for g in candidate_genes:
                        if g not in ("GO", "KEGG", "FDR", "TSS", "ATAC", "RNA", "DNA", "PCA", "UMAP", "NES") and not g.startswith(("HSA", "MMU", "TABLE", "FIG")):
                            if g not in pinfo["genes"]:
                                violations.append(
                                    f"Line {line_no} (GeneAgent Ontology Check): Gene '{g}' is paired with pathway '{pid}', but '{g}' is NOT in {pid}'s enriched gene set {sorted(pinfo['genes'])}."
                                )

        # 2. MedGraphRAG 校验：禁止未登记的裸写 PMID/DOI，所有文献引用必须走 [Ref: <id>] 并命中 .kb/docs/references/
        raw_dois = RAW_PMID_DOI_RE.findall(line)
        if raw_dois:
            violations.append(
                f"Line {line_no} (MedGraphRAG Citation Check): Unverified raw PMID/DOI '{raw_dois[0]}' detected. Must cite registered files in .kb/docs/references/ via [Ref: <id>]."
            )
        for ref_id in REF_CITE_RE.findall(line):
            if valid_refs and ref_id not in valid_refs:
                violations.append(
                    f"Line {line_no} (MedGraphRAG Citation Check): Cited '[Ref: {ref_id}]' does not exist in .kb/docs/references/."
                )

        # 3. CASSIA 物种前缀一致性检查
        if species in ("human", "homo_sapiens", "grch38", "hg38") and re.search(r"\bmmu\d{5}\b", line):
            violations.append(f"Line {line_no} (CASSIA Species Check): Mouse KEGG pathway 'mmu*' cited in a Human task.")
        elif species in ("mouse", "mus_musculus", "mm10", "grcm39") and re.search(r"\bhsa\d{5}\b", line):
            violations.append(f"Line {line_no} (CASSIA Species Check): Human KEGG pathway 'hsa*' cited in a Mouse task.")

    return {
        "ok": len(violations) == 0,
        "enrichment_terms_loaded": len(enrichment_map),
        "registered_references_count": len(valid_refs),
        "violations": violations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="GeneAgent + MedGraphRAG + CASSIA Biological Hallucination Verifier")
    parser.add_argument("--ws-root", required=True)
    parser.add_argument("--task-dir", required=True)
    args = parser.parse_args()

    ws_root = Path(args.ws_root).resolve()
    task_dir = Path(args.task_dir).resolve()
    res = verify_biological_grounding(ws_root, task_dir)
    if not res["ok"]:
        emit_error(
            "bio_verifier.hallucination_detected",
            f"Detected {len(res['violations'])} biological ontology/citation hallucination(s)!",
            retriable=True,
            next_steps=res["violations"][:5],
            data=res,
            task_dir=task_dir,
            scientific_violation=True,
        )
    emit_success("bio_verifier.passed", res, task_dir=task_dir)


if __name__ == "__main__":
    main()
