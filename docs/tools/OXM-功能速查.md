# OXM 功能速查（先查此包，能做就不从 0 写）

> 权威文档：`/data/InHousePackages/OXM/README.md`（527 行，16 模块详解，含官方示例与已知问题）。
> 本速查是按场景反查的索引 + 实战坑位记录。源码：`/data/InHousePackages/OXM/R/`，GitHub: https://github.com/BioLaoXu/OXM

## 环境激活（必须）

```r
.libPaths(c("/data/InHousePackages/OXM/library",   # 私有 ggplot2 4.0 系
            "/data/softwares/R/library",            # OXM/ChIPseeker/TxDb 所在地
            .libPaths()))
library(OXM)
# ⚠ 坑：requireNamespace("OXM", quietly=TRUE) 在此环境误报 FALSE，必须 library() 实载验证
```

## 按场景反查

| 场景 | 首选函数 | 备注 |
|---|---|---|
| 读表（csv/tsv/txt/gz/xlsx） | `readFile()` | 返回非 data.table，需 `as.data.table()` 包一层 |
| 建目录 / 存图 | `mkdir()` / `saveplot()` | saveplot 接受 ggplot/recordedplot/patchwork 等 |
| 主题 / 配色 | `custome_theme_bw1()` / `get_cols(n)` | 期刊白底风格；get_cols 自动选色 |
| **motif → peak 检索** | `getMotifTarget.homer()` | 见下方详解；内部调 HOMER findMotifs -find |
| 读取 motif PWM | `load_motif(file, pwmList=TRUE)` / `getHomerMotifs(dir)` | getHomerMotifs 只认 `knownN.motif`/`motifN.motif` 文件名 |
| motif 排序图 / seqlogo | `MotifResultPlot()` / `seqlogo_cus()` | seqlogo_cus 返回 **plot 列表**，需 `patchwork::wrap_plots()` 包一层 |
| peak→gene 注释 | `ChIPseeker::annotatePeak` + TxDb（OXM 生态常规组合） | promoter 占比另有 KB 函数 `promoter_ratio` |
| 热图 | `quickHeatmap()`（行列名/注释自动配色）/ `quickHeatmap_tri()`（相关矩阵） | 优先于手写 pheatmap |
| 信号矩阵（bw） | `deeptools_computeMatrix()`（超加速并行版）/ `deeptools_plot()` / `MatrixOperations()` | 消费 bigwig；profileplyr 对象管理见 README 模块3 |
| bigwig 运算 | `wiggletools_bws(bws, op, out)` | mean/sum/stddev 多文件运算 |
| TSS 富集分数 | `compute_enrichment(pp, type="tss")` / `plot_enrichment()` | 基于 deeptools bin 矩阵 |
| IP 质控（bam） | `TSSEscore1` / `FingerPrint` / `CrossCor.cus` / `PBC` | 消费 bamPeak_dt 元数据表 |
| 差异可视化 | `volcano_plots()`（需 gene_name/log2FC/padj/sig 列） | |
| Venn / Upset | `AutoVenn4List` / `AutoVenn4DT` / `Upset` | |
| 降维一站式 | `PCA_()` | biplot/碎石图输入 PCAtools 对象 |
| KEGG 通路图 | `ggpathview()`（缓存目录 XMLPath） | color 默认取 highlight_dt 的 log2FC 列 |
| 富集 / 注释库构建 | `build_KEGGdb(org)` / `build_uniprot_KGdb()` / `check_org_support()` | 首次需联网，缓存 species_db |
| STRING 网络 | `build_custom_stringdb()` | 无官方收录物种自动 MMseqs2 自建 |
| 表处理/统计 | `DataTrans.R` / `Stat.R` 模块 | 详见 README |
| shell 并行执行 | `runCMD(cmds, ncore=4)` | processx 封装，支持 OXM.dryrun |

## getMotifTarget.homer 详解（本任务实测）

```r
tgt <- getMotifTarget.homer(
  peak_files       = c(Consensus = "peaks.bed"),   # 命名 list/vector
  know_motif_files = c(Srebp2 = "srebp2.motif"),
  geno_fasta_file  = "/data/database/chip/genome/Mus_musculus/Mus_musculus_Ensemble_94.fa",
  summit           = NULL,     # NULL=用原始 peak 区间序列；c(-200,200)=summit 中心±窗
  outpath          = "results/MotifTarget")   # ⚠ 必须先 mkdir，normalizePath 不容忍不存在
```

- **bed 格式**：`formatbed="summit"`（默认）要求 **5 列**（chr/start/end/name/score）；6 列会报 `setnames: 5 names to 6-column`。bed 坐标 0-based，fasta 染色体名会被强制去 `chr` 前缀
- **返回结构**：单 peak 文件 × 单 motif 时为 `list(dt, MotifMatch)`；`dt` 含**全部** peak（seq/Motif/score/direction/Offset/match/MotifMatch/Sample），**`MotifMatch==1`（score≥match_score=7）才是命中**，直接 uniqueN(dt$seq) 会把全部 peak 算进去
- **内部流程**：提取 peak 序列 → HOMER `findMotifs.pl -find`（自动复用同目录 motifFindingParameters.txt 里的原始命令参数）→ R 内按 match_score 过滤
- 基因组 FASTA：mm10 用 `/data/database/chip/genome/Mus_musculus/Mus_musculus_Ensemble_94.fa`（2.6G，"1" 命名，即 pipeline 比对参考）

## 其他坑位（实战记录）

- `seqlogo_cus()` 返回列表不是单个 ggplot，直接 `saveplot()` 会报 "plot should be a ggplot2..."
- `getHomerMotifs()` 对非 `knownN.motif` 命名的文件返回空 PWMatrixList（单 motif 想出图用 `load_motif()`）
- 多线程绘图/分析注意包内同名函数重复定义前科：`plot_enrichment`（wig.R 两处）、`mplotPCA`——改包前先确认生效的那份
- 返回 `list(plot=)` 的函数：ScoreBubblePlot/fragSizePlot/gg_scatter3D/CorNet/biplot.all/PiePlot
