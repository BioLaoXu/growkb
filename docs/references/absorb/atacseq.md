# 吸收笔记：atacseq（nf-core ATAC-seq 标准管线）

## 1. 提示词/流程配置
无 LLM prompt，"提示词"即参数契约：nextflow_schema.json（38.9KB 全参数 schema，nf-validation 插件校验）；conf/igenomes.config（42KB 参考基因组预设：fasta/bowtie2 索引/黑名单，main.nf:20-31 经 getGenomeAttribute 自动装配）；conf/modules.config（37KB 进程级参数）；conf/test*.config 测试三档

## 2. 流程
main.nf:63 include ATACSEQ → workflows/atacseq.nf（32KB）:121 workflow ATACSEQ。步骤链（:69-110 include 即清单）：input_check→prepare_genome→fastq_fastqc_umitools_trimgalore→三选一比对（bwa/bowtie2/chromap，另 align_star）→bam_markduplicates_picard→过滤→bigwig/peak calling（merged_library 与 merged_replicate 双通道并行）→consensus peaks→featurecounts/deseq2→multiqc/ataqv/deeptools。断点：Nextflow 原生 work/ 缓存+-resume 步级重跑；:766 onComplete 收尾汇总。nf-core 两段式：modules/nf-core/*（中心化版本锁 modules.json）+modules/local/*，subworkflows 组合复用

## 3. 工具
每进程一个目录（main.nf+test.yml+meta.yml）；biocontainers/singularity 镜像统一在 conf/base.config；bin/ 放脚本工具，lib/ Groovy 工具类

## 4. 记忆
无对话记忆；work/ 任务缓存+tower.yml 充当运行状态记录；docs/output.md 28KB 记录全部产物路径约定

## 5. 护栏
参数校验（nf-validation 插件 main.nf:39）；每 module 自带 stub+test.yml；.github/ CI（nf-core lint）、pre-commit、CITATIONS.md 引用合规

## 6. 可移植清单
① schema 驱动参数校验（nextflow_schema.json 模式）→ 收件箱表单校验；② 双通道 merged_library/merged_replicate 命名与 include 别名→状态机并行分支建模；③ module 目录三件套（main+test+meta）→ NGS 脚本族标准化；④ igenomes.config 基因组预设表→知识库参考数据组织；⑤ -resume 缓存式断点→每步回滚/续跑的管线版 D3

## 7. 知识库/技能清单
自带 nf-core modules/subworkflows 生态（Git 子模块+modules.json 版本锁）；docs/（usage.md 19.9KB、output.md）+ nf-core 线上文档；assets/ 样例、CHANGELOG/CITATIONS 元文档
