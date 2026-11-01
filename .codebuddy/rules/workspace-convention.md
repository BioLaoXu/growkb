---
description: 工作空间项目制管理规范：约束 AI 助手的落盘归属、命名、.meta.yaml 维护、pwb 提单受理、索引刷新与交付打包，使分析跟着项目走
alwaysApply: true
enabled: true
updatedAt: 2026-10-26T00:00:00.000Z
---

# 工作空间项目制管理规范

> 完整规范见 `/data/Agent/xufa/workspace/README.md`。本文件是 **Agent 强制执行的精简版**。

## 一、落盘归属

| 场景 | 落盘位置 |
|---|---|
| 有合同/项目归属 | `projects/<年>/<批次号>/<YYYYMMDD>_<slug>/`（批次号来自工作台；-y 缺省当年） |
| 无合同归属的临时任务 | `scratch/<YYYYMM>/<YYYYMMDD>_<slug>/` |
| 跨项目复用资源 | 软链指向生产目录的共享资源，不在工作空间内复制 |

判断不了归属就**先问用户合同号或生产目录路径**，不要猜，不要落在根目录。

## 二、建目录必须用脚本

- `bash .ws/bin/ws_new_project.sh -b <批次号> -p <产品> [-y <年>] -s <生产目录名>`（或 `-f <生产目录全路径>`；-y 缺省当年）
- `bash .ws/bin/ws_new_task.sh -P <项目相对路径> -t <slug> -r "<客户需求>"`（`-d YYYYMMDD` 自选日期；临时任务用 `-S`）
- 任务目录 = **客户的一个需求批次**，脚本自动分配 `batch`（b01、b02…）与 `contract`，**不要手工改这两个字段**。
- **任务目录内固定两个子目录**：`scripts/` 放脚本，`results/` 放结果与图；输入软链放任务根目录，命名 `input.*`。不要再建其他子目录。
- 命名：`a-z 0-9 . _ -`，slug 小写连字符，日期 `YYYYMMDD`，禁止空格中文。项目目录名例外（原样复制生产目录名）。

## 三、数据只读，软链不拷贝

- `/data/Report`、`/data/rawdata`、`/data/database` 只读。
- 输入一律 `ln -s`（命名为 `input.*`），**禁止 `cp` 大文件**；单任务产出控制在 **200MB** 内。
- 小于 100MB 的结果文件可复制。

## 四、.meta.yaml 生命周期

1. 建任务时写入 `request`（客户原话）。
2. 开工置 `status: wip`；卡住置 `blocked` 并在 `notes` 写卡点。
3. 收尾（**不可跳过**）：补 `methods`（做了哪些分析，回溯的唯一依据）、`scripts`、`output`；**写 `report.md`**（按 `.ws/templates/report.md.tmpl` 骨架：思路/步骤/结果目录说明/表格图片解读/参考文献）并用 `ws_report.sh` 渲染成 `results/report.html`；置 `status: done`。
4. 刷新（**不可跳过**）：`bash .ws/bin/ws_index.sh` 重建 .index.md。
5. 提炼入库（**收尾时评估**）：任务中可泛化的函数/CLI 用 `bash .ws/bin/ws_kb.sh new -l R|python -t <主题> -n <名称>` 生成脚手架入 `.kb/`（R 用 Roxygen、Python 用 Google docstring、CLI 用 optparse/argparse），填好后 `ws_kb.sh check` + `ws_kb.sh index`；规范详见 `.kb/README.md`。
6. **受理新需求前先查库**：读 `.kb/.index.md` 判断是否有现成函数/CLI/方法笔记可复用，避免重复造轮子；有更新随手 `ws_kb.sh sync "feat: 说明"` 同步到 GitHub growkb。

## 五、交付两步走

```bash
bash .ws/bin/ws_pack.sh -T <任务>          # 打包 → 任务目录/<合同>_<任务>_<日期>.tar.gz（就地）
bash .ws/bin/ws_deliver.sh -T <任务>       # 预演（默认，只打印清单）
bash .ws/bin/ws_deliver.sh -T <任务> -y    # 确认后同步到生产 Analysis/<日期>/（只做新增）
```

- 打包**只含分析产物**：自动排除输入软链与元数据，`results/report.html` 随包交付；同名压缩包**报错退出**，不覆盖已交付文件。
- 同步到生产目录前需向用户确认目标路径；只新增，不覆盖任何既有文件。

## 六、回溯用工具，不靠猜

```bash
bash .ws/bin/ws_find.sh "<关键词>"          # 关键词检索
bash .ws/bin/ws_find.sh -p <产品> -s <状态>  # 按产品+状态过滤
bash .ws/bin/ws_check.sh                   # 体检：关联/元数据/未纳入项目/空间占用
bash .ws/bin/ws_receipt.sh -T <任务> -s accepted|done|delivered   # 写回执到 .outbox/
```

用户问"这个项目做过哪些分析""之前那个 motif 分析在哪"时，先跑上述命令再结合 `.index.md` 回答。

## 六A、会话开场：先查收件箱

任何新会话开始（或用户说"有新任务吗/受理"）时，**第一步**执行：

```bash
ls -1t .inbox/*_dispatch.yaml 2>/dev/null | head -5
```

有待受理卡则按第七节流程处理（卡里已含 batch/contract/product/需求与 taskPath）；
没有则正常进入对话。这是 pwb → CodeBuddy 提单链路的接收入口。

## 七、pwb 提单受理（项目信息卡）

用户会从 personal-workbench 把「项目信息卡」贴进对话，格式见 README 第七节（batch/contract/product 必填，site 或 source_dir 二选一）。受理流程：

1. 批次号项目不存在时先建：`ws_new_project.sh -b <batch> -p <product> -s <site>`（或 `-f <source_dir>`）；已存在则复用；
2. **先校验再动手**：生产目录定位不到就问用户，禁止猜路径；
3. `ws_new_task.sh` 建任务（信息卡带 date 时加 `-d`），META 自动填 contract/product/batch；再补 `sample_batch`、`species`、`request` 原文与 `notes`；
4. 信息卡里的 `inputs` 逐条 `ln -s` 成 `input.*`（目标不存在要先问）；
5. `ws_receipt.sh -T <任务> -s accepted` 写受理回执；收尾、交付时再补 `done` / `delivered` 回执；
5B. **经验沉淀（MEMEX）**（**防污染纪律**：只从用户消息与生产数据提炼；禁止把 Agent 自己的计划/自述当经验——防角色泄漏；入库一律走 `python3 .ws/bin/ws_memory.py add <条目.yaml>`，自动 MD5+语义双层去重；矛盾删除必须写 --reason）：任务 done 后按 `.kb/memory/_schema.md` 提炼 0-3 条经验写入 `.kb/memory/`（变更类写"转变前后"）；检索到 ≥3 条同类 → 提示升华进 `.kb/docs/methods/`；
5C. **长任务断点续跑**：开工时建 `plan.md`（3-7 项勾选清单，模板 `.ws/templates/plan.md.tmpl`），规则：单次只完成一项、禁复活已取消项、阶段产物落盘即状态（重入先查 plan.md 跳过已完成）；
5A. **收尾自评**：按 `.kb/docs/methods/report-scoring.md` 逐子步骤打分写入 META notes；总分 <0.8 不置 done；
5A2. **收尾封印**：自评通过后用 `python3 .ws/bin/ws_meta.py seal <任务> --grade <总分>` 一键完成（status=done + report/tables/figures 只读 + .kb 知识快照烙印 + 回显收尾阶段 SOP）；之后如需改报告先 chmod 加回写权限并在 notes 记录原因；
6. **环境预注入**：受理完成时核验生产目录（存在性、样本表/config.yaml/config 是否齐备），结果写入任务目录 `.env_check.yaml`；开工提示词必须引用"已核验环境清单"，禁止凭记忆假设数据位置；
7. **勾选清单状态机**：开工/收尾会话的任务清单用 `[ ]`→`[✓]`→`[✗]` 标记并每步回显；单次回复只允许直接完成一项；禁止复活已取消项（违规拒绝执行并说明）；
8. **NGS 黄金实践段**：开工提示词末尾附 `.kb/docs/methods/ngs-golden-practices.md` 的条目（按产品线勾选适用项）。
6. **受理后归档信息卡**：把 `.inbox/<卡文件>` 移入 `.inbox/accepted/`（避免已受理的卡滞留收件箱；看板对账也会自动归档，但主动归档优先）。
6. 信息卡字段有歧义（如 slug 撞名、产品未知）时**先问再建**，不要自作主张。

## 八、不可变约定

- 已 `done`/`delivered` 的产物**不得覆盖**；重做建 `<日期>_<slug>-v2` 新任务。
- 状态只写在 `.meta.yaml`；回执由脚本生成，**不要手工伪造 `.outbox/` 内容**。
- 索引文件 `.index.md` 由脚本生成，不要手工编辑；备注写进 `.notes.md`。
- 禁止删除 `projects/` 下任何内容（确需结项归档，须先向用户确认）。
- **改工作空间结构前先提交**：目录/脚本/文档的结构性修改，动手前 `git commit`（根仓库，分支 workspace，排除 projects/scratch），改完回归验证再提交并打 tag（语义化：架构→主版本，功能→次版本，修复→补丁）。
- **删除类操作前先备份元数据**：`bash .ws/bin/ws_backup.sh`（KB 级，秒级完成）—— 全套勾稽不能丢「客户需求」这类人工信息。
