# 吸收笔记（Wave 3 要点级）：生信 Agent 四仓（GeneGPT/scAgent/BioMANIA/BRAD）

## GeneGPT（NCBI 官方，README 精读）
- 底层逻辑：tool-augmented LLM + **in-context API demonstrations**（演示比文档更有效：Dm 优先于 Dc，main.py 111111 位掩码开关组合）+ **解码算法识别并执行 API 调用**
- 成绩：GeneTuring 8 任务平均 0.83（超 New Bing 0.44）
- 可移植：①"API 演示>文档"写入我们工具描述设计；②位掩码式配置开关组合提示组件；③evaluate.py 独立评分脚本
- 边界：仅 NCBI 系工具；Codex 依赖

## scAgent（deepmind11，README）
- 定位：agentic single-cell RNA-seq 分析系统，面向湿实验生物学家，自然语言驱动
- 特性：强制最佳实践、全程 provenance 追踪、产出可复现分析；不依赖特定 LLM
- 可移植：provenance 记录方式（每步输入输出/参数/版本）可加进我们 report.md 规范
- 边界：10x Chromium 数据专用

## BioMANIA（batmen-lab）
- 底层逻辑：从已有教程/API 文档**自动生成**领域对话助手（chatbot generation pipeline），用户友好后端服务
- 可移植：把我们 .kb 的方法文档自动转成"分析助手技能"的路径——文档即技能的生成器思路
- 边界：助手能力上限=教程覆盖面

## BRAD（Jpickard1，Bioinformatics 2025）
- 定位：RAG 增强的生信智能体（Bioinformatics Retrieval Augmented Data），pip 包 BRAD-Agent + Docker（thedoodler/brad:main）
- 能力：文献检索+代码执行+生标发现流程自动化
- 可移植：RAG 与代码执行的组合编排；Docker 一键部署形态
- 边界：偏发现型研究流程
