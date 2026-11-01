#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ws_table_peek.py — 防大表 head 采样位置偏见的结构化摘要工具
解决盲区 5（生信 TSV 默认按 chr1..chrY 或字母序排列，Agent 用 head -n 20 导致只看 chr1 写错结论）。
输出：
1. 行列总数、各列缺失率
2. 自动识别显著性列 (padj/FDR/qvalue/pvalue) 与效应量列 (log2FoldChange/log2FC/NES/diff)
3. 精确统计各显著性阈值档位 (FDR < 0.05, < 0.01, |log2FC| > 1) 的真实行数（供报告直接引用并由 ws_bench 核验）
4. 强制按显著性升序 + |效应量| 降序抽出全表真正的 Top-10 上调与 Top-10 下调行
"""
import argparse
import csv
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from ws_contract import emit_error, emit_success

PVAL_CANDIDATES = ("padj", "fdr", "qvalue", "q_val", "adj.p.val", "p_val_adj", "pvalue", "p_value", "pval")
EFFECT_CANDIDATES = ("log2foldchange", "log2fc", "avg_log2fc", "nes", "foldchange", "diff", "cor")


def try_float(v: str) -> Optional[float]:
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Statistical digest for NGS TSV/CSV tables (replaces head -n 20)")
    parser.add_argument("table_path", help="Path to .tsv or .csv file")
    parser.add_argument("--fdr-cutoff", type=float, default=0.05)
    parser.add_argument("--fc-cutoff", type=float, default=1.0)
    parser.add_argument("--top-n", type=int, default=5)
    args = parser.parse_args()

    p = Path(args.table_path).resolve()
    if not p.exists() or not p.is_file():
        emit_error("table_peek", f"Table file '{p}' not found.", retriable=False)

    delim = "," if p.suffix.lower() == ".csv" else "\t"
    rows: List[Dict[str, str]] = []
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delim)
        headers = list(reader.fieldnames or [])
        for r in reader:
            rows.append(r)

    if not headers:
        emit_error("table_peek", f"Table '{p.name}' has no valid header.", retriable=False)

    col_lower = {h.lower(): h for h in headers}
    pval_col = next((col_lower[c] for c in PVAL_CANDIDATES if c in col_lower), None)
    eff_col = next((col_lower[c] for c in EFFECT_CANDIDATES if c in col_lower), None)

    sig_up = 0
    sig_down = 0
    sig_total = 0
    valid_parsed: List[Dict[str, Any]] = []

    for r in rows:
        pv = try_float(r.get(pval_col, "")) if pval_col else None
        ef = try_float(r.get(eff_col, "")) if eff_col else None
        if pv is not None and pv < args.fdr_cutoff:
            sig_total += 1
            if ef is not None:
                if ef >= args.fc_cutoff:
                    sig_up += 1
                elif ef <= -args.fc_cutoff:
                    sig_down += 1
        valid_parsed.append({"raw": r, "pval": pv, "eff": ef})

    # 按显著性升序排序提取真正 Top Hits（而非文件物理前20行）
    ranked_up = [x for x in valid_parsed if x["pval"] is not None and (x["eff"] or 0.0) > 0]
    ranked_up.sort(key=lambda x: (x["pval"], -(abs(x["eff"] or 0.0))))

    ranked_down = [x for x in valid_parsed if x["pval"] is not None and (x["eff"] or 0.0) < 0]
    ranked_down.sort(key=lambda x: (x["pval"], -(abs(x["eff"] or 0.0))))

    digest = {
        "file": p.name,
        "total_rows": len(rows),
        "columns": headers,
        "detected_significance_col": pval_col,
        "detected_effect_col": eff_col,
        "exact_counts": {
            f"{pval_col or 'sig'} < {args.fdr_cutoff}": sig_total,
            f"upregulated ({pval_col} < {args.fdr_cutoff} & {eff_col} >= {args.fc_cutoff})": sig_up,
            f"downregulated ({pval_col} < {args.fdr_cutoff} & {eff_col} <= -{args.fc_cutoff})": sig_down,
        },
        "top_upregulated_rows": [x["raw"] for x in ranked_up[:args.top_n]],
        "top_downregulated_rows": [x["raw"] for x in ranked_down[:args.top_n]],
        "evidence_key_template": f"[{p.name}#Table1:rows={len(rows)},sig={sig_total},up={sig_up},down={sig_down}]",
    }
    emit_success("table_peek", digest)


if __name__ == "__main__":
    main()
