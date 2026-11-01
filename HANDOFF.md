# HANDOFF —— 服务器分析工作空间 × personal-workbench 对接文档

> 本文写给**本地 personal-workbench 的 CodeBuddy（WorkBuddy）**：读完即可了解服务器工作空间的全貌，并按第五节的协议完成「提单 → 受理 → 回执」对接。
> 文档版本：2026-10-27 · 服务器路径：`/data/Agent/xufa/workspace` · 维护者：服务器侧 CodeBuddy（xufa）

---

## 一、这个项目是什么

服务器上的**售后个性化分析工作空间**：承接生产标准分析完成后客户提出的二次分析需求（不同项目需求高度重复）。

核心设计（三条，违反任何一条都算事故）：

1. **无数据库** —— 磁盘上的 `.meta.yaml` 是唯一事实来源；台账 = 自动生成的 `INDEX.md`；一切可重建
2. **项目制落盘** —— 一切产物归属 `projects/<年>/<批次号>/<YYYYMMDD>_<slug>/`；无合同归属进 `scratch/`
3. **生产数据只读** —— 输入一律软链（`ln -s`），禁止拷贝；`/data` 余量紧张（约 4.1T / 92%）

## 二、目录结构（当前快照）

```
/data/Agent/xufa/workspace/
├── projects/2026/92512126902_mouse/      # ★ 业务树：projects/<年>/<批次号>/
│   ├── .project.yaml                     #   项目元数据：product/year/site/source_dir/contract
│   ├── .source -> /data/Report/...       #   生产目录软链（只读）
│   ├── .notes.md  .index.md              #   备注 / 本批次任务清单（自动生成）
│   └── 20261027_peak-anno/               #   任务 = 客户的一个需求批次
│       ├── .meta.yaml                    #   ★ 唯一事实来源（隐藏）
│       ├── report.md                     #   报告源稿（收尾时写，收尾必填）
│       ├── scripts/  results/            #   脚本 / 结果与图（含 results/report.html）
│       ├── input.peaks.R -> /data/...    #   输入软链（不进交付包）
│       └── 92512126902_peak-anno_20261027.tar.gz   # 交付包（就地生成）
├── scratch/202610/...                    # 无合同归属的临时任务（结构同上）
├── .outbox/                              # 回执：accepted/done/delivered，给 pwb 对账
├── .inbox/                               # 收件箱：待受理的「项目信息卡」（pwb 可 scp 投递，Agent 新会话自动查收）
├── .kb/                                  # 代码+文档知识库（GitHub 私库 growkb 同步）
│   ├── code/R/<主题>/*.R                 #   R 函数（Roxygen Skeleton，一函数一文件）
│   ├── code/python/<主题>/*.py           #   Python 模块（Google docstring）
│   ├── cli/{R,python}/kb_*.{R,py}        #   独立 CLI（R=optparse，Python=argparse）
│   ├── docs/{requirements,methods,references,results}/   # 经验沉淀
│   └── .index.md                         #   自动索引（Agent 检索入口）
├── .ws/                                  # 管理工具区
│   ├── bin/ws_*.sh|py                    #   管理脚本（见第四节）
│   ├── templates/                        #   META/report/kb 脚手架模板
│   ├── backup/                           #   元数据+脚本备份 tar（保留 10 份）
│   └── docs/                             #   架构图 HTML
└── README.md                             # 完整规范（最权威，本文是其对接摘要）
```

命名规则：目录/文件仅 `a-z 0-9 . _ -`，任务 slug 小写连字符；交付包 `<合同号>_<任务名>_<日期>.tar.gz`。

## 三、服务器环境

| 项 | 值 |
|---|---|
| 用户 / 属主 | xufa:xufa（目录 775、文件 664；元数据 640、工具区 755/644） |
| R | 4.4.2（roxygen2 ✅ optparse ✅） |
| Python | 3.8（**无 markdown 库**；argparse 标准库可用） |
| git | 2.25.1（SSH key = BioLaoXu，可推 GitHub 私库） |
| 磁盘 | /data 约 4.1T 可用（92% 已用）——**大文件必须软链** |
| 预览服务 | `python3 -m http.server 8792`（服务根 = 工作空间根） |

## 四、管理命令速查（均在 `.ws/bin/`）

```bash
# 一键发起（建项目如缺 + 建任务 + 生成信息卡到 .inbox/）
bash .ws/bin/ws_dispatch.sh -b <批次号> -p <产品> -s <生产目录名> -r "<需求>" [-t slug] [-d YYYYMMDD]
#    （或 -f <生产目录全路径>；-d 自选任务日期前缀；slug 缺省自动生成）

# 建项目 / 建任务（分开操作时）
bash .ws/bin/ws_new_project.sh -b <批次号> -p <产品> [-y <年>] -s <生产目录名>   # 或 -f <全路径>
bash .ws/bin/ws_new_task.sh -P projects/<年>/<批次号> -t <slug> -r "<需求>"      # -d 日期可自选

# 索引 / 检索 / 体检
bash .ws/bin/ws_index.sh                        # 重建 .ws/.index.md + 各批次 .index.md
bash .ws/bin/ws_find.sh "<关键词>"              # 回溯检索（也可 -p 产品 -s 状态）
bash .ws/bin/ws_check.sh                        # 体检：关联/元数据/未纳入/空间

# 报告 / 回执 / 打包 / 交付
bash .ws/bin/ws_report.sh -T <任务>             # report.md → results/report.html
bash .ws/bin/ws_receipt.sh -T <任务> -s accepted|done|delivered   # 写回执到 .outbox/
bash .ws/bin/ws_pack.sh -T <任务>               # 打包（就地，排除元数据与软链）
bash .ws/bin/ws_deliver.sh -T <任务>            # 同步生产目录（默认预演，-y 才写入）

# 收尾封印（评分门禁 + 产物只读 + 知识快照 + 回显收尾 SOP）
python3 .ws/bin/ws_meta.py seal <任务> --grade <总分>     # 总分>=0.8 才允许；之后报告/表/图只读
python3 .ws/bin/ws_meta.py patch <任务>/.meta.yaml --set KEY=VALUE --expected-rev <N>  # 并发安全修改

# 记忆（MEMEX）/ 评测（胶囊）/ 路由与校验
python3 .ws/bin/ws_memory.py add <条目.yaml>|promote <文件>|search <词> --use|list   # add 默认入 .staging/
python3 .ws/bin/ws_bench.py pack <任务> --name <slug>       # 任务→评测胶囊；grade 评分
python3 .ws/bin/ws_env_skill_router.py build-index --ws-root .   # 方案路由索引
python3 .ws/bin/ws_table_peek.py <数据表>                   # 大表防位置偏见摘要
python3 .ws/bin/ws_bio_verifier.py --task-dir <任务>        # 证据键源表反查
python3 .ws/bin/ws_run.py -- <命令...>                      # 进程组沙箱执行（超时连根清理）

# 看板（动态：状态/筛选/受理/回收站/帮助文档）
bash .ws/bin/ws_board.sh start|stop|restart     # 127.0.0.1:8792，cron 每 5 分钟守护

# 迁移
bash .ws/bin/ws_migrate.sh --to <新路径> | pack | deploy | handover   # 四模式见 --help

# 知识库 / 备份
bash .ws/bin/ws_kb.sh index|check|new|sync      # .kb 索引/体检/脚手架/推 growkb
bash .ws/bin/ws_backup.sh                       # 元数据+脚本+工具区 tar（留 10 份）
```

## 五、对接协议（核心）

### 5.0 发起通道与两种投递语义

**通道（三选一）**

| 通道 | 流程 | 适用 |
|---|---|---|
| A. 工作台投递 | pwb 生成信息卡 → `scp 卡.yaml xufa@<服务器>:/data/Agent/xufa/workspace/.inbox/` → 打开 CodeBuddy 新会话说「受理 <卡文件名>」 | 推荐的自动化路径 |
| B. 服务器命令行 | `ws_dispatch.sh -b <批次号> -p <产品> -s <生产目录名> -r "<需求>"` | 服务器上直接操作 |
| C. 对话粘贴 | 把信息卡直接贴进 CodeBuddy 对话 | 最简单 |

**两种投递语义（B 通道可选）**

| 语义 | 命令 | 行为 |
|---|---|---|
| 投递即受理（默认） | `ws_dispatch.sh -b … -p … -r …` | 建项目+建任务+写卡一步完成；卡瞬时归档；任务直接出现在看板总表（planned） |
| 卡-only（谨慎） | 同上 + `-C` | **只写卡到 `.inbox/`，任务不创建**；看板待受理区出现该卡，点 [受理]（或会话说受理）时才建项目/任务+写回执 |

**受理的两个层次**

- 总表 planned 行的 [受理] 按钮 / `ws_receipt.sh -s accepted`：**接单确认**（只写回执，不改任务状态）
- 待受理卡的 [受理]：**接单 + 建项目/任务**（一次完成）

**看板可视化操作一览**（ControlTower，`http://localhost:8792/`，服务 `ws_board.sh start|stop|restart`，cron 每 5 分钟守护）：
筛选/搜索 · ➕ 新建任务 · 待受理卡 [受理]/[忽略]/[查看] · 总表行 [受理]/[改状态]/[改需求]/[删除(回收站)]/[打包+交付] · 回收站 [找回]/[彻底删除]（DELETE 确认） · 底部随筛选联动的状态汇总

居家/外网访问：IDE 端口转发失效时用 SSH 隧道 `ssh -N -L 18792:127.0.0.1:8792 xufa@<服务器地址>`，
然后开 `http://localhost:18792/.ws/board/index.html`（注意 `-L` 的目标是**服务器视角**的 `127.0.0.1:8792`）。

> Agent 新会话开场会**自动查收 `.inbox/`**（规则已内置），待受理卡会被主动发现；
> 看板扫描亦会**对账归档**（卡对应任务已存在 → 自动移入 accepted/，双匹配：批次+slug）；
> slug 自动生成时（`req-<时分秒>`），受理的 Agent 会与你确认更名后重建。

**工作站侧一键入口**（Windows，IDE 为 VSCode 变体、自带 CLI 垫片 `buddycn.cmd`，版本 1.106.1）：

```powershell
# 桌面快捷方式目标：新窗口打开项目空间（SessionStart Hook 自动注入待受理卡）
E:\CodeBuddy\install\CodeBuddy CN\bin\buddycn.cmd -n

# 进阶：新窗口 + 直达信息卡原文（人工过目后再说受理）
& "E:\CodeBuddy\install\CodeBuddy CN\bin\buddycn.cmd" -n -g ".inbox/<卡文件名>:1"

# 终极：chat 子命令——传入 prompt 直接运行一个会话（官方能力，待验证其工作目录解析）
& "E:\CodeBuddy\install\CodeBuddy CN\bin\buddycn.cmd" chat "受理 .inbox/ 中的待受理分析请求；没有则告知"
```

> CLI 无"预填对话首条消息"的参数，但 **`chat` 子命令**本质上就是这件事（prompt 随启动传入），
> 与 SessionStart Hook 互补：Hook 保证上下文，`chat` 免掉手打第一句话。
> 待验证：`chat` 在 Windows 本地目录运行时，能否落到服务器工作空间（取决于 IDE 的远程机制）。

### 5.1 你（workbuddy）要做的：生成「项目信息卡」

从 pwb 的 tasks.db 记录映射出一张 YAML 卡，**贴给服务器侧的 CodeBuddy 对话**（或投递文件）：

```yaml
【分析请求】
batch: 92512126902_mouse     # ← sampleBatch 或生产目录名（必填，= projects/<年>/ 下目录名）
contract: 92512126902        # ← contractNo（必填）
product: cut_tag             # ← productName（必填）
site: 92512126902_mouse      # ← 生产目录名（与 source_dir 二选一）
source_dir: /data/Report/cut_tag_project_2026/92512126902_mouse   # 完整路径（二选一）
species: mouse               # ← speciesName（可选）
sample_batch: B1             # ← 样本批次（可选）
year: 2026                   # 可缺省，默认当年
slug: peak-anno              # 可缺省，由 Agent 从需求提炼
date: 20261027               # 可缺省，任务日期前缀，默认当天
request: >-                  # ← analyzeRemark（必填，客户需求原文）
  用最新 TxDb 重做 peak 注释，补充 promoter 比例饼图
inputs:                      # 可选：要软链的输入（生产路径 -> 任务内名字）
  - /data/Report/cut_tag_project_2026/92512126902_mouse/voclano.R -> input.peaks.R
deadline: 2026-11-05         # ← limitTime（可选）
notes: promoter 定义为 TSS±3kb   # 可选：卡点/特殊口径
```

**字段映射表（pwb tasks.db → 信息卡）**：

| pwb 字段 | 信息卡字段 | 必填 |
|---|---|---|
| contractNo | contract | ✅ |
| productName | product | ✅ |
| serviceDataPath / reportDataPath | site 或 source_dir | ✅ 二选一 |
| analyzeRemark | request | ✅ |
| speciesName | species | 可选 |
| sampleBatch | sample_batch | 可选 |
| limitTime | deadline | 可选 |
| bioinforId | （建议 workbuddy 自行留存，回执按 contractNo+batch+taskId 对账） | — |

### 5.2 服务器侧 CodeBuddy 的受理动作（你不需要做，仅供了解）

1. 校验 batch/contract/product 与生产目录（对不上先问，不猜）
2. 批次号项目不存在则 `ws_new_project.sh -b ... -p ...`；已存在复用
3. `ws_new_task.sh` 建任务（date → `-d`），`.meta.yaml` 自动填 contract/product/batch/source_dir
4. 按 inputs 建 `input.*` 软链；写受理回执
5. 分析 → 收尾（methods/output + report.md → report.html）→ done/delivered 回执

### 5.3 我（workbuddy）收回执：`.outbox/*.yaml`

回执文件：`.outbox/<日期>_<taskId>_<status>.yaml`，字段如下：

```yaml
at: 2026-10-27 11:19:31
status: accepted          # accepted | done | delivered
taskId: 20261026_peak-anno
taskPath: projects/2026/92512126902_mouse/20261027_peak-anno
contractNo: 92512126902
batch: b01
productName: cut_tag
packed: projects/.../92512126902_peak-anno_20261026.tar.gz   # delivered 时有值
note: >-                  # 可选备注
```

**对账键：`contractNo + batch + taskId`**。获取方式二选一：
- 你能 SSH：`scp xufa@<服务器>:/data/Agent/xufa/workspace/.outbox/*.yaml <本地目录>`
- 不能 SSH：让服务器侧 CodeBuddy 把回执文本直接贴回对话

### 5.4 知识库对接（可选但推荐）

- 服务器侧受理/收尾前会先查 `.kb/.index.md` 复用现成函数——**提单时在 notes 里写清分析类型，有助于命中**
- 沉淀的通用函数/CLI 在 `.kb/`（R=Roxygen，Python=Google docstring，CLI=薄壳）
- `.kb/` 已 git 化并同步私库 `git@github.com:BioLaoXu/growkb.git`（main 分支），你本地可 clone 只读
- 想在本地语义问答？ ima 等外部知识库可作为**只读镜像**（导出功能 `ws_kb.sh export` 未来按需添加），严禁双写

## 六、约束与红线（违反即事故）

1. 输入一律 `ln -s`，禁止 cp 大文件；单任务产出 ≤ 200MB
2. `done/delivered` 的产物**不得覆盖**；重做建 `<日期>_<slug>-v2` 新任务
3. `projects/` `scratch/` 下任何删除须先向用户确认
4. `.outbox/` 回执只由脚本生成，不手工伪造
5. 根目录不散落任何业务文件
6. 客户口径（如 promoter ±N kb）必须写进 `.meta.yaml` 的 `notes`

## 七、运维例程（服务器侧已建立）

| 例程 | 频率 | 命令 |
|---|---|---|
| 元数据+代码备份 | 每次收尾后 | `ws_backup.sh`（tar 留 10 份，KB 级） |
| 异地副本 | 每周 | `scp .ws/backup/ws-meta-*.tar.gz` 到本地 |
| restore 演练 | 每月 | tar 解包到临时目录核对 |
| .kb 同步 | 每次入库后 | `ws_kb.sh sync "feat: 说明"`（规范化 commit） |
| 权限维护 | 建任务后 | `find projects scratch -name '.meta.yaml' -exec chmod 640 {} +` |

## 八、当前状态快照（2026-10-27）

- 批次项目：`projects/2026/92512126902_mouse/`（cut_tag，contract 92512126902）
- 任务：`20261027_peak-anno`（wip，含 report.html 与交付包示例）
- 知识库种子：R 函数 `promoter_ratio`、CLI `kb_tsv_stats.py`、需求拆解文档 1 篇
- growkb 私库：已同步（main @ 9bdcc0a+）
- 无数据库（曾经的 ws.db 已废弃删除）；一切状态在磁盘文件中
