---
name: ATAC-seq Inhouse Differential Accessibility & Motif Report
version: 2.4.0
license: Internal-SOP
product_codes: ["ATAC-seq", "ChIP-seq"]
tags: ["atac", "peak", "differential", "motif", "chromatin", "染色质开放性", "差异峰"]
description: "LOAD WHEN: Customer requests ATAC-seq or ChIP-seq quality control, differential peak calling (DARs), genomic feature annotation (promoter/enhancer), or TF motif enrichment summary from standard production output. SKIP WHEN: Single-cell ATAC (scATAC-seq), multiome RNA+ATAC, or de novo genome assembly is requested."
locked_params: {"fdr_cutoff": 0.05, "min_abs_log2fc": 1.0, "min_replicates": 2}
required_inputs: ["tables/diff_peaks.tsv", "tables/qc_summary.tsv"]
---
# ATAC-seq Standard Delivery Skill

## When to use
Use for standard bulk ATAC-seq post-pipeline delivery reports.

## Inputs
- `tables/qc_summary.tsv`: FRiP score, TSS enrichment, mitochondrial ratio.
- `tables/diff_peaks.tsv`: Differential accessibility peaks with `log2FoldChange` and `padj`.

## Workflow
1. Verify FRiP > 0.20 and TSS enrichment > 5.0 across replicates.
2. Run `ws_table_peek.py tables/diff_peaks.tsv` to obtain exact counts of DARs (`padj < 0.05`, `|log2FC| >= 1.0`).
3. Summarize top upregulated/downregulated promoter-associated genes with exact evidence keys.

## Gotchas
- Never sort by chromosome coordinate (`chr1`) when reporting top genes; always sort by `padj` ascending.

## Evidence
Every quantitative claim must carry `[tables/diff_peaks.tsv#Table1:rows=N]` or `[tables/qc_summary.tsv#Table2]`.

## Outputs
- `report.md` and rendered `report.html`.

## Dependencies
- Standard Linux + Python 3.8+
