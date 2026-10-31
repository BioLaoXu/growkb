---
batch: SP20260929002
tags: [harness, agent, workspace, review, ngs, optimization]
---

# Agent + 工作空间系统评审文档（Harness Review）

> 版本：v1.0 ｜ 日期：2026-10-31 ｜ 维护：随系统演进同步更新（放 KB 常驻）
> 目标读者：受托优化本系统的外部专家。目标：在不接触生产数据的前提下，完整理解当前「CodeBuddy Agent + 分析工作空间」的架构、规范、流程与 harness 现状，据此提出优化方案，使后续 NGS 任务的受理、分析、交付**准确率更高、速度更快**。
> 素材来源：全部经只读核对（README、规则原文、.ws/bin 脚本源码、.kb 规范、两轮实战任务复盘），文中路径与行为均有源码依据。

---

## 目录

1. [系统目标与全景](#1-系统目标与全景)
2. [工作空间架构与目录](#2-工作空间架构与目录)
3. [全生命周期流程](#3-全生命周期流程)
4. [规范层（Agent 行为约束）](#4-规范层agent-行为约束)
5. [Harness 层清单](#5-harness-层清单)
6. [工具链盘点（.ws/bin）](#6-工具链盘点wsbin)
7. [知识库体系（.kb → growkb）](#7-知识库体系kb--growkb)
8. [关键技术资产与已知坑（OXM）](#8-关键技术资产与已知坑oxm)
9. [基准用例复盘](#9-基准用例复盘)
10. [规划与遗留项](#10-规划与遗留项)
11. [痛点诊断](#11-痛点诊断)
12. [优化建议清单](#12-优化建议清单)
- [附录 A：关键文件路径索引](#附录-a关键文件路径索引)

---

## 1. 系统目标与全景

**一句话**：让 AI 编码助手（CodeBuddy Agent，GLM 模型）在一个强规范的工作空间里，承接生信分析公司「合同制个性化分析」的 NGS 任务——从受理、分析、报告到交付全流程可回溯、可交接、可审计。

**业务背景**：分析工作流为「pwb（personal-workbench，工作台）管客户/合同 → 生产 pipeline（/data/Report/）出标准分析 → 本工作空间承接客户个性化追加需求」。pwb 与 CodeBuddy **不共享数据库**，靠纯文本「项目信息卡」（.yaml）交接。

```
pwb 提单 ──► .inbox/*_dispatch.yaml（信息卡）
                 │
                 ▼  SessionStart 钩子自动查收（新会话开场注入上下文）
           CodeBuddy Agent ──按规范受理──► projects/<年>/<批次号>/<日期>_<任务>/
                 │                              ├── .meta.yaml（唯一事实源）
                 │                              ├── scripts/ + results/
                 ▼                              └── input.* 软链 → /data/Report/（只读）
           分析执行（R/Python + OXM 包 + KB 复用）
                 │
                 ▼
           收尾（report.md → report.html、methods 回填、status: done）
                 │
                 ▼
           ws_pack 打包 ──► ws_deliver 同步生产目录（只新增） ──► .outbox/ 回执 ──► pwb 对账
```

**成效基线**（以 SP20260929002 两轮任务为准）：一轮「最终 peak vs 客户区域」交集分析（含 3 脚本、3 类产出、报告）从受理到打包约 10–15 分钟，全程可回溯。

---

## 2. 工作空间架构与目录

路径：`/data/Agent/xufa/workspace`（git 化，workspace 分支，远端 growkb 私库，当前 v2.0.0）。规范全文：`README.md`（370 行）。

```
workspace/
├── README.md                  # 工作空间管理规范（唯一权威文档）
├── projects/<年>/<批次号>/     # ★ 可见业务树：批次号项目（来自工作台）
│   ├── .project.yaml          # 项目级元数据：product/year/site/source_dir/contract
│   ├── .source → /data/Report/…   # 软链到生产标准分析目录
│   ├── .index.md              # 任务清单（ws_index.sh 自动生成）
│   └── <YYYYMMDD>_<任务slug>/ # = 客户的一个需求批次
│       ├── .meta.yaml         # ★ 唯一必须文件（唯一事实源）
│       ├── scripts/ results/  # 固定两个子目录
│       └── input.<对象>.<ext> # 输入软链（禁止 cp 大数据）
├── scratch/<YYYYMM>/…         # 无合同归属的临时任务（结构同上）
├── .inbox/                    # pwb 投递的分析信息卡（受理入口）
├── .outbox/                   # 回执（append-only，pwb 对账用）
├── .kb/                       # 知识库（函数/CLI/文档，git→growkb 私库）
├── .ws/                       # 工具区（bin 脚本/templates/索引/backup/docs 配图）
└── .codebuddy/                # Agent 配置（settings.json 钩子、hooks/、rules/、plans/）
```

**三条核心原则**：① 项目是唯一锚点（无归属进 scratch/）；② 一个任务目录 = 客户的一个需求批次（.meta.yaml 唯一必须）；③ 生产数据只读、输入一律软链（磁盘 4.1T 用量 92%）。

**.meta.yaml 生命周期与状态机**：`planned→wip→done→delivered`（wip 可转 blocked 后回 wip）。只有 `request`（客户原话）与 `methods`（回溯检索唯一依据）必填，其余由脚本自动填。done 硬性要求 methods 已填；delivered 要求回填 packed 或 synced_to。

**命名规范**：`a-z 0-9 . _ -`，slug 小写连字符，禁止空格中文；重做加 `-v2` 后缀不覆盖既有产物；脚本 `01_<动作>.R`、结果 `<对象>.<动作>.tsv`。

**空间策略**：输入软链不拷贝；单任务产出 ≤ 200MB；结果文件 <100MB 可复制；红线——禁止 `cp` 生产数据、禁止改动 /data/Report 既有文件。

---

## 3. 全生命周期流程

标准作业 8 步（README 第五节）：

1. **建项目**：`ws_new_project.sh -b <批次号> -p <产品> -s <site> | -f <source_dir>`（.project.yaml 防覆盖；合同号由 `derive_contract` 自动推导，4 种模式兼容）。
2. **建任务**：`ws_new_task.sh -P <项目> -t <slug> -r "<需求>"`（batch 自动 b01/b02…；product/contract/source_dir 从 .project.yaml 带入；同名任务 die）。
3. **开工**：置 `status: wip`；输入 `ln -s` 成 `input.*`。
4. **收尾**：补 methods/scripts/output → 写 `report.md` → `status: done`（**不可跳过**）。
5. **渲染**：`ws_report.sh -T <任务>`（report.md → results/report.html，自包含单文件，报告头从 .meta.yaml 自动注入）。
6. **索引**：`ws_index.sh` 重建项目级与全局索引（勿手改）。
7. **回执**：`ws_receipt.sh -s done`（受理时 `-s accepted`，交付时 `-s delivered`）。
8. **交付**：`ws_pack.sh`（打包就地落盘）+ `ws_deliver.sh`（预演 → `-y` 同步生产目录 `Analysis/<日期>/`，`cp -n` 只新增）。

**pwb 提单受理（README 第七节，无 DB 链路）**：信息卡必填 batch/contract/product/request，site|source_dir 二选一；Agent 受理六步 = 建项目 → 校验生产目录（对不上先问不猜）→ 建任务 → 补 sample_batch/species/需求原文/input 软链 → 受理回执 → 开工。回执按 `contractNo+batch+taskId` 三键对账。

**会话开场自动化**：`.codebuddy/settings.json` 配置 SessionStart 钩子（matcher=`startup|resume`），新会话自动执行 `.codebuddy/hooks/check_inbox.py` 查收 .inbox 信息卡并注入上下文（详见第 5 节）。

**回溯工具**：`ws_find.sh "<关键词>"`（按 methods/request/notes 检索）、`ws_check.sh`（四项体检：软链/元数据/生产对账/磁盘占用）、`.index.md`（全局 + 项目级）。

---

## 4. 规范层（Agent 行为约束）

规则注入机制：`~/.codebuddy/rules/`（用户全局，每个会话 always-applied）+ `workspace/.codebuddy/rules/`（项目级）。四份规则内容如下：

| 规则文件 | 关键条款 |
|---|---|
| `global-safety.md` | 删除红线（禁 rm -rf 除非逐字确认完整路径、rsync 禁 --delete、禁删 workspace 外文件）；环境保护（禁改 ~/.bashrc 等、禁系统级安装、新增依赖入 venv/conda、/data/database|softwares|rawdata 只读）；数据与凭证安全（凭证不落明文、客户测序数据不上传外部、Git 不提交数据）；破坏性命令逐条批准 |
| `global-agent-redlines.md` | 高危命令拦截扩充（chmod 777/chown、truncate、跨内网请求先说明、kill 非本会话进程）；人工确认补充（大批量重构先出方案、>5 分钟重命令先说明耗时、无人值守脚本先展示全文）；算力保护（大文件先探规模、ulimit/nice 限资源、死循环立即终止）；并发派生限制（子代理 ≤2、后台进程 ≤2、禁递归派生） |
| `global-visualization.md` | 正式交付图（架构/流程/时序/数据流）一律用 dynamic-archify 技能渲染（自包含 HTML+主题切换+导出，布局 JSON 与 HTML 一并存 docs/）；临时示意才可用 Mermaid 代码块 |
| `workspace-convention.md` | 项目制管理精简版（README 的强制执行摘要：落盘归属/建目录脚本/软链不拷贝/meta 生命周期/交付两步走/回溯工具/受理流程/八条不可变约定） |

**会话命名约定**（2026-10-30 新增，注入式）：受理类会话首条消息带批次号（如「受理 92512126902_mouse」），使 IDE 会话标题自动含批次号；Agent 受理后按「批次号_产品」主动建议命名。依赖 IDE 自动标题，非接口级重命名。

---

## 5. Harness 层清单

### 5.1 钩子（.codebuddy/settings.json + hooks/）

| 钩子 | 实现 | 行为 |
|---|---|---|
| SessionStart（startup\|resume） | `.codebuddy/hooks/check_inbox.py`（Python 标准库） | 扫 `.inbox/*_dispatch.yaml`，解析 batch/contract/product/taskPath/request，把待受理卡清单注入 additionalContext；无卡提示收件箱为空；有待卡时取第一张 batch 有效的卡，追加「会话命名约定」提醒 |

- 输出协议：`{"continue": true, "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": …}}`，stdout 纯 JSON、调试走 stderr（KB_HOOK_DEBUG 开关）。
- 已验证：3 张卡场景下注入正常；JSON 合法。
- 局限：仅 SessionStart 一个钩子；无 PreToolUse/Stop 等防御性钩子；钩子无法重命名会话（IDE 无此接口）。

### 5.2 CodeBuddy 记忆条目（跨会话持久化）

| 记忆 | 内容要点 |
|---|---|
| 可视化偏好 | 正式详图一律 dynamic-archify（HTML+JSON 存 docs/），临时示意才用 Mermaid |
| 交付语言约定 | 交付给客户的图/表一律英文（标题/图例/轴标签），报告正文可中文 |
| OXM 环境 | 私有库 /data/InHousePackages/OXM/library；激活用 .libPaths 或 R_PROFILE_USER（R_LIBS 不可靠） |
| OXM ggplot2 4.0 适配史 | 43 处修复/10 文件（element_markdown、linewidth、aes/.data、6 个预存 bug）；3 个未修非 bug 项；包内同名函数重复定义前科（plot_enrichment/mplotPCA），改前必确认生效份 |
| OXM 官方文档 | README 527 行 16 模块 + docs/ 4 张 archify 图；GitHub BioLaoXu/OXM |

### 5.3 规则与提示词注入

- Always-applied 用户规则（4 份，见第 4 节）+ workspace 规则：每轮对话自动注入，构成 Agent 的"系统纪律"。
- 内置 agent_skills（按需加载）：dynamic-archify（图表）、playwright-cli（浏览器自动化）、pdf/docx/xlsx/pptx（Office 读写）、lsp-code-analysis（语义代码分析）、brainstorming/writing-plans/verification-before-completion 等工程方法技能。
- 任务内工作方式：Plan 模式（复杂需求先 plan_create → 用户确认 → todo 逐项执行）、todo_write 跟踪、subagent（code-explorer/code-reviewer，≤2 并发）做大规模探索以免污染主上下文。

### 5.4 任务执行的隐式工程约定（实战沉淀）

- 动手前预检：只读 awk/grep 验证数据坐标约定、染色体命名风格、预期命中数（每轮任务必做，已多次提前暴露坑点）。
- 脚本头注释：任务路径、运行方式、输入输出清单、核心逻辑与已知坑——脚本自解释，交接零成本。
- 结果核对：运行输出必须与预检一致，不一致即排查坐标 0/1-based 等约定问题。

---

## 6. 工具链盘点（.ws/bin）

公共库 `_lib.sh`：WS_ROOT 解析、validate_name/slug（字符集白名单）、resolve_source（按 `<产品>_project_<年>` 推导生产目录）、render_template（{{KEY}} 占位符）、link_if_absent（软链防覆盖）、derive_contract（4 种模式提取合同号）、read_project_field。

| 脚本 | 用途 | 关键保护 | 已发现缺陷 |
|---|---|---|---|
| ws_new_project.sh | 建批次号项目目录 | .project.yaml/.notes.md 只建不覆盖 | `-f` 指向不存在目录仅 warn 不拦截 |
| ws_new_task.sh | 建任务（需求批次） | 同名任务直接 die（不可变约定落地） | — |
| ws_receipt.sh | 写回执 YAML 到 .outbox/（追加式） | 状态白名单 accepted/done/delivered | 头注释承诺 `-p 包路径` 选项但 getopts 未实现 |
| ws_report.sh | report.md → results/report.html（自包含） | 缺 report.md die 提示从模板复制 | **`.ws/templates/report.md.tmpl` 实际不存在**（提示指向空） |
| ws_index.sh/py | 重建项目级+全局索引（含按合同聚合表） | 自动生成勿手改 | — |
| ws_find.sh | 全库 .meta.yaml 检索（关键词/产品/状态/字段） | 只读 | 内嵌简化 YAML 解析（与 ws_meta.py 重复的历史副本） |
| ws_check.sh | 四项体检：软链/元数据/生产对账/磁盘（>2GB 标红） | 只读 | 轻微变量泄漏（y），跨年路径可能拼错 |
| ws_pack.sh | 打客户交付包（就地，排除 META/软链/旧包） | 同名包 die；回填 deliverable.packed；MD5 | — |
| ws_deliver.sh | 同步生产 Analysis/<日期>/（cp -n 只新增） | source_dir 必须在 /data/Report 且存在；默认预演 | **:35 校验 `META.yaml`（无点前缀）而非 `.meta.yaml`，标准任务会被拦死**（改名遗留 bug） |
| ws_kb.sh | KB 四子命令：index/check/new/sync→git@github.com:BioLaoXu/growkb.git | check 语法不过 exit 1；sync 远端复核 main 分支 | `new` 脚手架无防覆盖 |
| ws_meta.py | 元数据唯一事实解析器（索引/回执/看板共用） | 标准库，PyYAML 缺失自动回退 | — |
| ws_board.sh/py | ControlTower 看板（127.0.0.1:8792，IDE 端口转发） | POST 全部转调 ws_* 脚本（单一事实源）；删除仅 planned+双重确认+.trash | — |
| ws_dispatch.sh | pwb 一键发单：建项目/任务/投卡到 .inbox/ | `-C` 卡-only 模式（受理时才建目录） | — |
| ws_migrate.sh | 工作空间迁移/交接（pack/deploy/handover/--remap 软链重写） | 目标已存在 die；部署后 chmod+索引+体检 | **handover 子命令不可用**（函数定义在 case 之后）+重复 case 行；`--move` 不确认直接 rm -rf |

---

## 7. 知识库体系（.kb → growkb）

**事实源原则**：服务器 .kb/ 是唯一事实源；GitHub growkb 私库（main 分支）是同步备份；外部只读镜像严禁双写。

**三分区入库标准**：
- `code/<语言>/<主题>/`：可 source/import 的库函数。R：一函数一文件、文件名=函数名、Roxygen skeleton（标题/描述/@param 含类型/@return/@examples 可跑）；Python：Google docstring + 类型注解。
- `cli/<语言>/`：**薄壳原则**——只做参数解析+调 code/ 库函数，业务逻辑不上移到 CLI；文件名 `kb_<动作>.<ext>`；`--input/--output` 语义固定。
- `docs/`：一主题一 md，文件头 front-matter（batch/tags 供 index 提取）；写"可借鉴经验"非流水账。五个子分类：methods（方法笔记）/references（文献引用）/requirements（需求拆解 `<批次号>-<slug>.md`）/results/tools（工具速查）。

**提炼闭环**：受理前先查 `.kb/.index.md` 避免重复造轮子 → 收尾时泛化函数走 `ws_kb.sh new -l R|python -t 主题 -n 名称` → `check`（R parse + py_compile，坏代码不得入库）→ `index`（四张表：R/Python/CLI/docs）→ `sync "feat: …"`（git add -A → commit → push → ls-remote 复核）。

**现有条目**（截至 2026-10-31）：R 函数 1 个（promoter_ratio，annotation 主题）、CLI 1 个（kb_tsv_stats.py）、需求拆解文档 1 篇（92512126902_mouse-peak-anno）、工具速查 1 篇（OXM-功能速查）、references 2 篇。**覆盖仍薄**，是当前主要短板之一。

---

## 8. 关键技术资产与已知坑（OXM）

OXM：自研 R 包（`/data/InHousePackages/OXM`），覆盖 peak/注释/motif/富集/可视化全流程，是 NGS 任务的主力武器库。

**环境激活**（每脚本必备）：
```r
.libPaths(c("/data/InHousePackages/OXM/library", "/data/softwares/R/library", .libPaths()))
library(OXM)
```
私有库内置 ggplot2 4.0.3/ggraph/ggpp/ggtext 等（R_LIBS 环境变量方式不可靠，用 .libPaths 或项目 .Rprofile）。

**实战踩坑清单**（均有源码行号依据，NGS 任务高频相关）：

| 坑 | 现象 | 解法 |
|---|---|---|
| bed2gr data.frame 分支缺 strand 列 | tidyselect "Selections can't have missing values" 报错 | 输入前预置 `strand := "*"` 列 |
| 注释表 geneStrand 列（值 1/2） | 被 bed2gr 误识别为 strand 非法 | 读入后删除该列再转 GRanges |
| 包内同名函数重复定义 | 改了一处不生效（plot_enrichment 在 wig.R 两处、mplotPCA 两个文件） | 修改前 grep 确认生效的那份 |
| ggVennDiagram 2 集合标签相撞 | 集合名水平重叠 | ggvenn_wrapper 的 catName 参数覆盖 angle（配合整图 -90° 旋转后标签纵向排布）；集合名用短名防画布裁切 |
| AutoVenn4DT Venn 语义 | 数字≠原始区间数 | 按聚类后区间簇（cluster_id）计数，彼此重叠区域先合并；报告必须注明口径 |
| 染色体命名风格 | 注释文件 "3" vs 客户区域 "chr3"（或反之） | 统一 `sub("^chr","",seqlevels(...))`，交集前断言 seqnames 相容 |
| 坐标 0/1-based | 命中数与预期差 1bp 量级 | 预检阶段用 awk 独立验证 |
| 3 个未修非 bug 项 | enrichDotplot 需 GeneRatio 列、seqlogo_cus 需 S4 motif 对象、preview_plot 仅 RStudio 可用 | 已记录，选用时规避 |

---

## 9. 基准用例复盘

**项目 SP20260929002（cut_tag，mouse）两轮「最终 peak vs 客户区域交集」任务**，作为流程基准：

| 维度 | b01（20261028_peak-overlap） | b02（20261030_peak-overlap-2） |
|---|---|---|
| 需求 | 客户 6 个 chr3 区域（95.43Mb）vs MAnorm 最终 peak 注释表 | 客户更新区域（95.52–95.54Mb，Ctss 附近），同口径重做 |
| 判定 | 任意 ≥1bp 重叠（findOverlaps, ignore.strand） | 同 |
| 脚本 | step_1 交集（bed2gr+findOverlaps+汇总）、step_2 区间条形图（ggplot2）、step_3 Venn（OXM 教程流程） | 复制 b01 脚本改 `_r2` 输出前缀与动态标题 |
| 结果 | 4/6 区域命中（Arnt 启动子等 2 peak） | 6/6 全命中（3 个 Ctss peak），Venn 100% 共享 |
| 踩坑 | bed2gr 缺 strand 列报错、Venn 标签相撞、detail peak_id 与图内 label 不匹配致红色交集段静默丢失 | 无新坑（复用模式生效） |
| 交付 | tar.gz 460K/18 文件 + MD5；report.html | tar.gz 476K/18 文件；同样回执链路 |

**流程耗时**：b01（含方法探索）约 40 分钟；b02（纯复用）约 10 分钟——复用模式使同类任务提速 ~4 倍。

---

## 10. 规划与遗留项

| 项 | 现状 | 计划 |
|---|---|---|
| 断点续跑机制 | 无；任务脚本全量重算，仅靠脚本间依赖人工跳步 | 已评估方案（KB `resume_guard(output_files, input_files)` 通用函数+脚本一行接入），暂缓待任务复杂度上来再启用 |
| OXM 上 GitHub | BioLaoXu/OXM 已建仓，README/文档齐 | 待 push |
| KB 泛化入库 | 收尾时评估惯例已建立 | 持续：peak 交集、resume_guard 等候选 |
| contract 对账 | ws_new_project 的 derive_contract 按批次号推合同号，与生产 Result-<合同号> 可能不一致（SP20260929002 案例：META contract=SP20260929002 vs 生产合同 926092206501） | 待与工作台对账口径统一 |
| 看板 ControlTower | 已实现（8792 端口，写操作全部转调 ws_* 脚本） | 评估后与 pwb/CodeBuddy 链路整合 |

---

## 11. 痛点诊断

按对「准确率/速度」的影响排序，均有实战证据：

**P1 影响准确率**
1. **工具脚本存在实际失效路径**：ws_deliver.sh 校验 `META.yaml`（无点前缀）而标准任务只有 `.meta.yaml`——同步生产目录的主链路会被自己拦死；ws_migrate.sh handover 子命令因函数定义位置错误不可用。防覆盖纪律落地严格，但**核心交付链路缺乏回归测试**。
2. **OXM 已知坑靠记忆与脚本注释传递**：bed2gr/geneStrand/染色体命名等坑的解法散落在任务脚本注释与记忆里，新任务靠 Agent 记得才不踩；KB 中尚无对应"防坑函数/文档"沉淀。
3. **contract 字段口径不一**：META 的 contract 可能与生产合同号不一致，pwb 按 contractNo 对账时会失配。
4. **无自动化验收**：结果正确性靠 Agent 预检+人工比对，无 snapshot/回归测试（b01→b02 复用时尤其依赖人眼）。

**P2 影响速度**
5. **脚本复用靠复制粘贴改前缀**：b02 模式（cp + 改 `_r2`）有效但靠 Agent 手工，参数化程度低（区域文件路径、窗口、输出前缀散落硬编码）。
6. **报告模板缺失**：`.ws/templates/report.md.tmpl` 不存在，每轮报告靠参照上一任务，结构与详略不稳定。
7. **KB 覆盖薄**：仅 1 R 函数 + 1 CLI；peak 交集这类已跑通两次的通用模式尚未入库，检索命中率为 0。
8. **检索工具原始**：ws_find.sh 是 grep 级检索（内嵌简化 YAML 解析），跨任务找"做过什么分析"仍依赖 Agent 记忆 + .index.md 通读。
9. **README 滞后于实现**：脚本表未收录 ws_dispatch/ws_board/ws_migrate；.kb README 目录树漏 docs/tools/——文档权威性被稀释。

**P3 可维护性**
10. **无断点续跑**：长任务中断即全量重算（当前任务小影响有限，pipeline 级任务会放大）。
11. **钩子面窄**：仅 SessionStart；无 PostToolUse 级防误操作钩子（目前靠规则文本约束+工具脚本自身保护）。
12. **会话命名靠约定**：无 IDE 接口级重命名，依赖用户首条消息带批次号。

---

## 12. 优化建议清单

按「准确率 → 速度 → 可维护性」分组，每条含现状→建议→预期收益→成本（S=半天内 / M=1–3 天 / L=更大）。

### A. 准确率

| # | 现状 | 建议 | 收益 | 成本 |
|---|---|---|---|---|
| A1 | ws_deliver.sh :35 校验 META.yaml 失配 | 修为 `.meta.yaml`；对 ws_* 全套做 shellcheck + 一轮 dry-run 冒烟测试 | 消除交付主链路拦死风险 | S |
| A2 | ws_migrate.sh handover 不可用、重复 case | 修函数定义位置；删除重复行 | 交接能力可用 | S |
| A3 | ws_receipt.sh -p 未实现 | 补实现或删注释 | 文档与行为一致 | S |
| A4 | OXM 坑靠记忆传递 | 把"防坑"做成 KB：① `safe_bed2gr()` 包装函数（自动处理 strand 列/geneStrand/命名归一）入 .kb/code；② 坑清单成文入 .kb/docs/tools/ | 新任务天然免疫历史坑 | M |
| A5 | contract 口径不一 | ws_new_project 的 derive_contract 增加对生产目录 `Result-<合同号>` 的探测；不一致时 warn 并让用户确认 | pwb 对账零失配 | S |
| A6 | 无自动化验收 | 任务脚本加 `--selftest` 或独立 test 脚本（用 b01/b02 小样本做 fixture，比对输出快照） | 复用改造有回归网 | M |
| A7 | 钩子面窄 | 增加 PreToolUse 钩子：拦截对 `/data/Report`、`projects/**/results/`（已 done 任务）的写操作，与规则文本双保险 | 防误操作从"靠自觉"变"硬拦截" | M |

### B. 速度

| # | 现状 | 建议 | 收益 | 成本 |
|---|---|---|---|---|
| B1 | 脚本靠复制改前缀 | 抽参数化模板：公共逻辑（读 bed/注释表→GRanges→交集→三件套产出）封装为 KB 函数库 + 一个参数驱动的主脚本（`--regions --anno --out-prefix`），任务脚本薄壳化 | 同类任务从 10 分钟到 2 分钟；且天然消除复制遗漏 | M |
| B2 | 报告模板缺失 | 补 `.ws/templates/report.md.tmpl`（含固定小节：思路/步骤/结果目录/表格解读/图片解读/参考文献），ws_new_task 时可选预填 | 报告结构稳定，收尾提速 | S |
| B3 | KB 覆盖薄 | 把已跑通两次的 peak-overlap 模式入库（函数+需求拆解文档+OXM Venn 流程笔记）；建立"每任务收尾必评估入库"的硬检查（ws_check 增加提示） | 检索命中率从 0 起步累积 | S/M |
| B4 | 检索原始 | ws_index.py 的 scan 已是结构化事实源——给 ws_find 换底为 ws_meta.scan（顺带消灭重复解析器）；再加按基因/区域关键词搜 results 文件名的轻量索引 | 回溯从"读索引"变"精准查询" | M |
| B5 | 受理链路手工 | pwb→inbox 链路已通；下一步把"受理六步"固化为一键脚本（ws_accept.sh：读卡→建任务→软链→回执），Agent 只做校验与补充 | 受理环节从多步交互变单命令 | M |

### C. 可维护性

| # | 现状 | 建议 | 收益 | 成本 |
|---|---|---|---|---|
| C1 | 断点续跑缺失 | 落地已评估方案：KB `resume_guard()` + 任务脚本一行接入（输出齐全且新于输入则跳过） | 长任务中断可续 | S |
| C2 | README 滞后 | README 脚本表补 ws_dispatch/ws_board/ws_migrate；.kb README 补 docs/tools/；规定"新增脚本必须同步 README"（可由 ws_check 体检项覆盖） | 文档恢复权威 | S |
| C3 | 会话命名靠约定 | 无 IDE 接口，短期维持注入提醒；可在 .meta.yaml 增加 `session:` 字段记录受理会话标识，供人工对齐 | 可回溯性 | S |
| C4 | 记忆条目无版本治理 | 定期（如每月）审计记忆：过期条目（如 OXM 适配史已入文档）降级为 KB 文档引用，避免记忆膨胀失真 | 长期上下文质量 | S |

**建议优先级**：A1（交付拦死 bug）> A2/C2（失效路径与文档一致性）> B1/A4（速度与准确率的乘数项）> 其余按需。

---

## 附录 A：关键文件路径索引

| 类别 | 路径 |
|---|---|
| 工作空间规范 | `/data/Agent/xufa/workspace/README.md` |
| 全局规则 | `~/.codebuddy/rules/global-{safety,agent-redlines,visualization}.md`；`workspace/.codebuddy/rules/workspace-convention.md` |
| Agent 配置 | `workspace/.codebuddy/settings.json`（钩子）、`.codebuddy/hooks/check_inbox.py`、`.codebuddy/plans/` |
| 工具区 | `workspace/.ws/bin/`（18 脚本）、`.ws/templates/`、`.ws/.index.md`、`.ws/docs/` |
| 知识库 | `workspace/.kb/{README.md,CHANGELOG.md,.index.md,code/,cli/,docs/}` |
| 受理链路 | `workspace/.inbox/`（信息卡）、`.outbox/`（回执） |
| OXM | `/data/InHousePackages/OXM/`（R 源码 `R/*.R`）；私有库 `/data/InHousePackages/OXM/library` |
| 基准任务 | `workspace/projects/2026/SP20260929002/{20261028_peak-overlap, 20261030_peak-overlap-2}/` |
| 生产目录（只读） | `/data/Report/cut_tag_project_2026/20261025_SP20260929002/` |
| growkb | `git@github.com:BioLaoXu/growkb.git`（.kb main 分支；workspace 本体在其 workspace 分支） |
