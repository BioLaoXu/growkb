# 工作空间管理规范（Agent Workspace Convention）

> 路径：`/data/Agent/xufa/workspace`
> 适用：非特定项目类别任务（合同制个性化分析、临时分析、方法验证）
> 目标：**分析跟着项目走** —— 任何一个产出都能在 30 秒内回答：属于哪个合同、第几批需求、做了什么分析、现在什么状态、交付包在哪。

---

## 一、三条核心原则

1. **项目是唯一锚点** —— 一切产物先归属项目；无合同归属的进 `scratch/`，根目录不许散落。
2. **一个任务目录 = 客户的一个需求批次** —— 目录内固定 `scripts/`（脚本）与 `results/`（结果），`.meta.yaml` 是唯一必须文件。
3. **生产数据只读、软链不拷贝** —— `/data` 余量紧张（约 4.1T / 92%），输入一律 `ln -s`。

---

## 二、目录结构

```
/data/Agent/xufa/workspace/
├── README.md                       # 本规范
├── projects/                       # ★ 批次号项目树（可见业务树）
│   └── <年>/<批次号>/              # 年份分目录管理；批次号来自工作台
│       ├── .project.yaml            # 项目级元数据：product/year/site/source_dir/contract
│       ├── .source -> /data/Report/…   # 软链到生产标准分析目录（能定位才建）
│       ├── .notes.md               # 可选：只有建项目时给了 -t 才生成
│       ├── .index.md                # 本批次任务清单（自动生成）
│       └── <YYYYMMDD>_<任务slug>/  # = 一个需求批次；-d 可自选日期前缀
│           ├── .meta.yaml           # ★ 唯一必须文件（product 从 .project.yaml 带入）
│           ├── scripts/            # 脚本：01_xxx.R / xxx.py / xxx.sh
│           ├── results/            # 结果与图：xxx.tsv / xxx.pdf / xxx.png / report.html
│           ├── <合同>_<任务>_<日期>.tar.gz  # 客户交付包（打包后就地生成）
│           └── input.<对象>.<ext>  # 输入软链，放任务根目录（不进交付包）
├── scratch/<YYYYMM>/<YYYYMMDD>_<slug>/   # 无合同归属的临时任务（结构同上）
├── .codebuddy/rules/workspace-convention.md     # Agent 强制规则
├── .outbox/                        # 回执（hidden）：受理/完成/交付，pwb 拉取后更新本地状态
├── .kb/                            # 代码与文档知识库（hidden）：规范化函数/CLI + 经验沉淀，sync 到 GitHub growkb
└── .ws/                            # 隐藏：工具、模板、索引、文档（都不是业务内容）
    ├── bin/                        #   管理脚本（见第六节）
    ├── templates/META.yaml.tmpl        #   唯一模板
    ├── .index.md                    #   全局索引（自动生成）
    ├── backup/                     #   元数据备份（ws_backup.sh 产出）
    └── docs/                       #   规范配图（HTML + 布局 JSON）
```

**根目录只有三样可见内容**：`projects/`、`scratch/`、`README.md`；其余全部收在隐藏目录 `.ws/` 下。

**一个任务目录常态三个条目**：`.meta.yaml` + `scripts/` + `results/`（外加若干 `input.*` 软链）；收尾时写 `report.md`（报告源稿），打包后同级多出一个交付包。

### 2.1 与生产目录的映射

一级目录 = **工作台的样本批次编号**（不再含产品/年份层级）；生产目录的定位信息收在 `.project.yaml`。

| 工作空间目录 | 生产目录（记在 .project.yaml，`.source` 软链指向） |
|---|---|
| `projects/2026/demo_batch_mouse/` | `/data/Report/cut_tag_project_2026/demo_batch_mouse` |
| `projects/B20261027-001/` | `/data/Report/rna_project_2026/demo_batch_SP`（举例） |

定位方式二选一：给 `site`（生产目录名）由脚本按 `/data/Report/<产品>_project_<年>/` 推导（年份缺省时依次尝试当年与近两年）；或直接给 `source_dir` 完整路径。产品类型参考值：`atac` / `chip` / `cut_tag` / `rna` / `LowVolumeRNA` / `m6A` / `cfRNA` / `multiOmics` / `InHouseProject` / `other`。

---

## 三、命名规范

- 字符集 `a-z 0-9 . _ -`；slug 全小写连字符；日期 `YYYYMMDD`；**禁止空格与中文**。
- 项目目录名例外：原样复制生产目录名（含大写也不改）。
- 重做任务加 `-v2` 后缀，**不覆盖**既有产物。

### 3.1 任务 slug 词表

| 类别 | slug |
|---|---|
| 富集/注释 | `go-kegg`、`gsea`、`peak-anno`、`gene-anno` |
| 差异 | `diff-peaks`、`diff-expr`、`batch-correction` |
| 可视化 | `volcano`、`heatmap`、`pca`、`venn`、`coverage-profile` |
| motif/序列 | `motif-scan`、`motif-compare`、`seqlogo` |
| 整合 | `multiomics-cor`、`overlap-peaks-rna` |
| 交付 | `fig-revision`、`report-supplement`、`reanalysis-v2` |
| 质控 | `qc-recheck`、`sample-filter`、`spikein-check` |

### 3.2 文件命名

```
脚本   scripts/01_<动作>.R          例：scripts/01_peak_anno.R
结果   results/<对象>.<动作>.tsv     例：results/peak.anno.tsv
图     results/<对象>.<动作>.pdf     例：results/peak.anno.pie.pdf
输入   input.<对象>.<ext>           例：input.peaks.R（软链，放任务根目录）
```

---

## 四、.meta.yaml（唯一事实来源）

```yaml
id: 20261027_peak-anno
project: 2026/demo_batch_mouse  # 年/批次号（= projects/ 下的相对路径）
contract: demo_contract          # 受理时从 .project.yaml 带入，用于按合同聚合
product: cut_tag               # 受理时从 .project.yaml 带入（pwb 对账字段）
batch: b01                     # 自动编号，b01/b02…；可用 -b 覆盖
sample_batch: null             # 可选：样本批次（B1/B2）
species: mouse                 # 可选：物种
source_dir: /data/Report/cut_tag_project_2026/demo_batch_mouse
created: 2026-10-26
updated: 2026-10-26
status: wip

request: >-                    # 客户的原始需求（必填）
  客户要求用最新 TxDb 重做 peak 注释，补充 promoter 比例饼图

methods:                       # ★ 必填，回溯检索的唯一依据
  - peak annotation (ChIPseeker)

scripts:
  - scripts/01_peak_anno.R

output:
  - results/peak.anno.tsv

deliverable:
  synced_to: null              # ws_deliver.sh 回填
  packed: null                 # ws_pack.sh 回填

notes: |
  客户定义 promoter 为 TSS ±3kb。
```

**只有两个字段必填**：`request`（需求）和 `methods`（做了什么）。其余脚本会自动填。

### 4.1 状态机

```
planned ──▶ wip ──▶ done ──▶ delivered
              └──▶ blocked ──▶ wip
```

| 状态 | 含义 |
|---|---|
| `planned` | 已建未开工 |
| `wip` | 执行中 |
| `blocked` | 卡住（**必须在 notes 写明卡点**） |
| `done` | 分析完成、methods 已填 |
| `delivered` | 已打包/已同步，回填 `packed` 或 `synced_to` |

---

## 五、标准作业流程

```
1. 建项目  ws_new_project.sh -b demo_batch_mouse -p cut_tag -s demo_batch_mouse   # -y 缺省当年
2. 建任务  ws_new_task.sh -P <项目> -t peak-anno -r "客户需求"     ← 自动分配批次 b01
3. 开工    scripts/ 写脚本，软链输入（input.*），results/ 出结果
4. 收尾    补 methods / scripts / output，写 report.md（报告源稿），置 status: done
4b.报告   ws_report.sh -T <任务>     → results/report.html（随包交付给客户）
5. 刷新    ws_index.sh               → .index.md（全局索引）
6. 回执    ws_receipt.sh -T <任务> -s done    → .outbox/（pwb 拉取更新状态）
7. 打包    ws_pack.sh -T <任务>      → 任务目录/<合同>_<任务>_<日期>.tar.gz（就地；批次包在项目目录）
8. 同步    ws_deliver.sh -T <任务> -y → 生产目录 Analysis/<日期>/（只做新增）
```

第 6-8 步按需取用：回执给 personal-workbench 对账；客户要压缩包就打包，要求并入生产目录就同步，两者都做也行。

### 5.1 报告排版规范（report.md 表格）

> 背景：曾因渲染器未对齐数据行与表头列数，导致交付 HTML 表格整体错位（v2.4.1 修复并加保护）。写报告时遵守以下规则，`ws_check.sh` 会在收尾体检时自动检查（检查项 [2] 报告表格错位）：

1. 表格**每一行**（含表头与分隔行）都以 `|` 开头、`|` 结尾；
2. 数据行的**列数必须与表头一致**——空列写 `| |`，不要省略尾部竖线；
3. 单元格内容禁止出现裸 `|`（需转义为 `\|` 或改写文字）；
4. 渲染器已加保护：行缺列自动补空、多列并入末列，并向 stderr 打 `WARN: 表格行列数不一致`——见到告警必须回改 report.md，不要带病交付。

---

## 六、脚本一览

| 脚本 | 作用 | 常用法 |
|---|---|---|
| `ws_new_project.sh` | 建批次号项目 + .project.yaml + 软链 | `-b demo_batch_mouse -p cut_tag -s demo_batch_mouse` |
| `ws_new_task.sh` | 建任务（含 scripts/ results/） | `-P <项目> -t peak-anno -r "需求"`；`-d 20261101` 自选日期；`-S` 临时任务 |
| `ws_index.sh` | 重建索引（含按合同聚合） | 无参数 |
| `ws_find.sh` | 回溯检索 | `"motif"`、`-p cut_tag -s wip` |
| `ws_report.sh` | report.md → results/report.html 分析报告 | `-T <任务>` |
| `ws_kb.sh` | 知识库：索引/语法体检/脚手架/GitHub 同步 | `index`、`check`、`new -l R -t 主题 -n 名称`、`sync "msg"` |
| `ws_receipt.sh` | 写回执到 `.outbox/`（pwb 对账） | `-T <任务> -s accepted|done|delivered` |
| `ws_pack.sh` | 打包交付压缩包 | `-T <任务>`、`-P <项目> -b b01,b02`、`-f zip` |
| `ws_deliver.sh` | 同步到生产目录（**默认预演**） | `-T <任务>` 预演，加 `-y` 才写入 |
| `ws_check.sh` | 体检：关联/元数据/未纳入项目/空间 | 无参数 |
| `ws_backup.sh` | 备份不可替代的元数据（见「九·容灾」） | 无参数；`-k 30` 保 30 份 |

---

## 七、从 pwb 提单到受理完成（无 DB 链路）

工作台（personal-workbench）持有任务的完整上下文（合同号、产品、物种、数据路径、客户需求），
CodeBuddy 持有执行环境。两者之间**不共享数据库**，靠一段固定格式的「项目信息卡」交接。

### 7.1 提单：把项目信息卡贴给 CodeBuddy

在 pwb 里选中任务，把下面这张卡贴进 CodeBuddy 对话（标"必填"的不能少，其余可缺省）：

```yaml
【分析请求】
batch: demo_batch_mouse     # 样本批次号（必填，= projects/<年>/ 下的一级目录名）
contract: demo_contract        # 合同号（必填，pwb 对账字段）
product: cut_tag             # 产品（必填，.project.yaml 元数据）
site: demo_batch_mouse      # 生产目录名（与 source_dir 二选一）
source_dir: /data/Report/cut_tag_project_2026/demo_batch_mouse   # 完整路径（与 site 二选一）
species: mouse               # 物种（可选）
sample_batch: B1             # 样本批次（可选，B1/B2）
year: 2026                   # 可缺省，默认当年
slug: peak-anno              # 可缺省，由 Agent 从需求提炼
date: 20261027               # 可缺省，任务日期前缀，默认当天
request: >-                  # 客户需求原文（必填）
  用最新 TxDb 重做 peak 注释，补充 promoter 比例饼图
inputs:                      # 可选：要软链的输入（生产路径 -> 任务内名字）
  - /data/Report/cut_tag_project_2026/demo_batch_mouse/voclano.R -> input.peaks.R
deadline: 2026-11-05         # 可选
notes: promoter 定义为 TSS±3kb   # 可选：卡点/特殊口径
```

### 7.2 受理：Agent 自动落地

Agent 收到信息卡后按规则受理（见 `.codebuddy/rules/workspace-convention.md`）：

1. 批次号项目不存在时先 `ws_new_project.sh -b <batch> -p <product>`（site/source_dir 按信息卡传入），已存在则复用；
2. 校验生产目录（`resolve.source`），对不上**先问、不猜**；
3. `ws_new_task.sh` 建任务（date 有值加 `-d`）：目录、`scripts/` + `results/`、`.meta.yaml` 自动填好，product 从 `.project.yaml` 带入；
4. 补 `sample_batch` / `species` / 需求原文，按 `inputs` 建 `input.*` 软链；
5. `ws_receipt.sh -s accepted` 写受理回执，然后照第五节流程开工（收尾记得写 `report.md` 并用 `ws_report.sh` 渲染）；
6. 收尾、交付时分别补 `done` / `delivered` 回执。

### 7.3 回执：`.outbox/` 对账

```bash
.ws/bin/ws_receipt.sh -T <任务> -s accepted            # 受理
.ws/bin/ws_receipt.sh -T <任务> -s done                # 完成
.ws/bin/ws_receipt.sh -T <任务> -s delivered           # 交付（自动带上 packed 路径）
```

回执是 YAML 文本，pwb 拉取后按 `contractNo + batch + taskId` 对齐更新本地状态。
没有数据库、没有同步进程 —— **一次交接就是一份文件，受理后即归档**。

## 八、空间策略（重要）

| 规则 | 说明 |
|---|---|
| 输入一律软链 | `ln -s`，软链不占空间，`ws_check.sh` 的 du 也不计入 |
| 单任务产出 ≤ 200MB | 超出说明应软链回生产目录，或只保留交付级结果 |
| 复用资源不复制 | 参考基因组、TxDb 等用软链指向生产目录的共享位置，工作空间内不留副本 |
| 压缩包定期清理 | 任务目录（批次包在项目目录）里已发出的包可归档或删除（先确认） |
| 回执与索引极小 | 纯文本元数据，不存文件内容；合计 < 100KB |

目录本身几乎不占空间（空目录约 4KB），**真正的空间风险只来自拷贝大文件**，所以红线就是"禁止 `cp` 生产数据"。

---

## 九、容灾：权限与恢复

### 9.1 设计依据（工业界原则）

| 原则 | 出处 | 在本工作空间的落地 |
|---|---|---|
| 最小权限（PoLP） | NIST SP 800-53 AC-6 | 每个目录只给必需的写权限（见 9.2 三档） |
| 职责分离（SoD） | ISO 27001 | 三区分离：业务数据（projects/scratch）/ 工具配置（.ws）/ 版本化资产（.kb） |
| 不可变产物 | Immutable Infrastructure | done/delivered 产物不得覆盖；交付包同名报错不覆盖 |
| 审计追加（append-only） | ISO 27001 12.4 | .outbox/ 回执只由脚本追加，不手工伪造 |
| GitOps | CNCF 实践 | .kb/ → growkb：版本化、可回滚，远端为备份非事实源 |
| 3-2-1 备份法则 | US-CERT | 3 份数据（生产 + 备份 tar + 本地 scp）、2 种介质、1 份异地 |

### 9.2 权限三档（按"谁能写"划分）

| 档 | 路径 | 现状 | 目标 | 谁可写 |
|---|---|---|---|---|
| 业务数据 | `projects/` `scratch/` | 775/664 | **保持 775/664** | 属主 + 组（协作） |
| 业务元数据 | 各任务 `.meta.yaml` `.project.yaml` | 664 | **640**（组只读） | 仅属主 + Agent |
| 工具区 | `.ws/bin` `.ws/templates` `.ws/docs` | 775/664 | **755/644** + 脚本 755 | 仅属主 + Agent |
| 知识库 | `.kb/` | 775/664 | **755/644** + 代码 755 + `.kb/.git` **700** | 仅属主 + Agent |
| 回执/备份 | `.outbox/` `.ws/backup/` | 775/664 | **750** | 仅属主 + Agent |
| 入口 | `README.md` | 664 | 保持 | — |

执行命令（**由你自行运行**；新建任务后新文件回默认 664，`.meta.yaml` 的 640 需重跑最后一行）：

```bash
cd /data/Agent/xufa/workspace
find .ws .kb -type d -not -path '*/.git/*' -exec chmod 755 {} +
find .ws .kb -type f -not -path '*/.git/*' -exec chmod 644 {} +
find .ws .kb -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod 755 {} +
chmod 700 .kb/.git && chmod 750 .ws/backup .outbox
find projects scratch \( -name '.meta.yaml' -o -name '.project.yaml' \) -exec chmod 640 {} +
```

两个边界：① 权限防不住属主自己的误删（Linux 无针对属主的禁删），`chattr +i` 需要 root 且会锁死 Agent 写 `.meta.yaml`，不采用；② 真正的安全网是 9.3 的恢复矩阵。

### 9.3 恢复矩阵（RPO = 会丢多少 / RTO = 多久恢复）

| 被删/损坏 | 严重度 | RPO | RTO | 恢复方式 |
|---|---|---|---|---|
| 任务 `.meta.yaml` `.project.yaml` `.notes.md` | 🔴 不可再生 | 上次 backup | 分钟 | `tar xzf .ws/backup/ws-meta-<日期>.tar.gz -C /` |
| 任务 `report.md` `scripts/` 代码 | 🟡 | 上次 backup | 分钟 | 同上（已纳入备份） |
| `.ws/bin` `.ws/templates` | 🟡 | 上次 backup | 分钟 | 同上（已纳入备份）；README 规范可兜底 |
| `results/` 产物 | 🟠 可重算 | 0 | 小时~天 | 生产 `Analysis/` 回捞，或重跑（脚本在） |
| `.kb/` | 🟡 | 上次 sync | 分钟 | `git clone git@github.com:BioLaoXu/growkb.git .kb` |
| `.index.md`（全局/批次级） | 🟢 0 | — | 秒 | `ws_index.sh` |
| `.outbox/` | 🟢 | — | 分钟 | `ws_receipt.sh` 重写 |
| `.ws/docs/*.html` | 🟢 0 | — | 秒 | `.ws/docs/*.json` 重渲染 |
| `.ws/backup/` 本身 | 🔴 仅整机事故 | — | — | 依赖 9.4 的异地副本 |

### 9.4 备份与运维例程

```bash
.ws/bin/ws_backup.sh            # 收尾后随手跑：元数据+任务脚本+工具区（KB 级），默认留 10 份
tar tzf .ws/backup/ws-meta-<日期>.tar.gz         # 演练：看包内容
tar xzf .ws/backup/ws-meta-<日期>.tar.gz -C /tmp/ws_restore_test && ls -R /tmp/ws_restore_test
```

- **每周**：`scp` 最新备份 tar 到本地（3-2-1 的"1 份异地"；工作空间内部的包挡不住整机事故）
- **每月**：restore 演练一次 —— 没有验证过的备份等于没有备份
- **`.kb/`**：`ws_kb.sh sync` 即远端备份，git log 就是历史
- **`results/` 不进备份**：产物可重算或从生产 `Analysis/` 回捞，避免备份膨胀

### 9.5 版本管理（GitOps）

- 工作空间根已 git 化：版本化对象 = `.ws/bin` + `.ws/templates` + `.ws/docs` + `.codebuddy` + README/HANDOFF/CHANGELOG；**排除** projects/scratch（业务数据走 ws_backup）、`.ws/backup`、`.outbox`、`.kb`（独立仓库 growkb main 分支）
- 远端：growkb 私库的 **`workspace` 分支**（`.kb/` 在同仓库的 `main` 分支，互不干扰）
- 当前版本：**v2.4.0**（2026-11-01）——变更历史见 `CHANGELOG.md`
- 新增能力速览：一键发起 ws_dispatch、迁移四模式 ws_migrate、动态看板 ws_board（含回收站/帮助）、
  MEMEX 经验记忆 ws_memory、胶囊基准 ws_bench、并发安全 META（ws_meta seal/patch）、
  阶段门控 SOP（.ws/prompts/）、方案路由与生信校验（ws_env_skill_router/ws_bio_verifier/ws_table_peek）
- 语义化规则：架构变更 → v3；加脚本/功能 → v2.x；修 bug → v2.0.x
- **改架构铁律：动任何结构前先 `git commit`（或至少 `git stash`），改完回归验证再 commit——每改一步都有回滚点**

```bash
git log --oneline                # 看历史
git diff HEAD~1                  # 看上次改动
git tag -a v2.1.0 -m "说明"      # 发新版本
git push origin main:workspace --follow-tags   # 同步远端
```

## 十、硬性约束

1. 禁止在根目录直接落盘任何分析产物。
2. 禁止 `cp` 生产数据到工作空间；小于 100MB 的结果文件可复制。
3. 禁止改动 `/data/Report` 既有文件；`ws_deliver.sh` 只做新增（`cp -n` 不覆盖）。
4. 已 `done`/`delivered` 的产物不得覆盖；重做建 `-v2` 新任务。
5. 任务收尾必填 `methods`，否则索引检索不到。
6. `ws_pack.sh` 遇到同名压缩包直接报错退出，绝不覆盖已交付文件。
7. 状态只写在 `.meta.yaml`；回执（`.outbox/`）只由脚本生成，不要手工伪造。
8. 禁止删除 `projects/` 下任何内容；确需结项归档须先向用户确认（不设专用归档区）。

---

## 十一、与旧习惯的关系

过去个性化分析放在 `/data/Report/<产品>_project_<年>/<项目>/Analysis/<日期>/`。本规范**不取代**它，只是把开发调试过程前移：

| 环节 | 旧做法 | 新做法 |
|---|---|---|
| 代码调试 | 直接在生产目录写 | 在 `projects/…/<任务>/scripts/` 写 |
| 结果暂存 | 混在生产目录 | 在 `projects/…/<任务>/results/` |
| 元数据 | 无（靠记忆） | `.meta.yaml` + `.index.md`（纯文本，人机都能读） |
| 交付 | 就地生成 | 先打包 `ws_pack.sh`，再同步 `ws_deliver.sh` |

---

## 十二、配套图示

| 图 | 文件 | 看什么 |
|---|---|---|
| **目录管理架构（主图）** | [`.ws/docs/workspace-tree.html`](.ws/docs/workspace-tree.html) | 根 → 项目 → 任务三级树、`scripts/`+`results/`、提单与回执流向 |
| 结构与交付链路 | [`.ws/docs/workspace-structure.html`](.ws/docs/workspace-structure.html) | 生产目录 ↔ 工作空间 ↔ 交付包 |
| 标准作业流程 | [`.ws/docs/workspace-lifecycle.html`](.ws/docs/workspace-lifecycle.html) | 立项 → 执行 → 收尾 → 交付 |

自包含 HTML（内置明暗主题与 PNG/SVG 导出），浏览器直接打开；布局源文件 `*.json` 同目录存放，改完用 dynamic-archify 重渲染。

---

## 十三、内置示例

- `projects/2026/demo_batch_mouse/` —— 批次号项目示例（`.project.yaml` + `.source` 软链 + `.notes.md`）。
- `projects/2026/demo_batch_mouse/20261027_peak-anno/` —— `b01` 批次、`wip` 状态，`scripts/01_peak_anno.R` + `results/` 一件产物 + 一个输入软链 + 打包产物（就地）。
- `scratch/202610/20261026_oxm-theme-check/` —— 无合同归属的临时任务。
- `.outbox/20261027_20261026_peak-anno_accepted.yaml` —— 回执示例（受理/完成/交付三种状态）。
