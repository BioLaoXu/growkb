---
name: hide-meta-files-and-task-report
overview: 五类配置/元数据文件全部改为点前缀隐藏（.meta.yaml/.project.yaml/.source/.notes.md/.index.md，全小写），input.* 保持可见；交付包不再包含元数据文件；新增任务报告能力：收尾时写 report.md，ws_report.sh 渲染成 results/report.html（含思路/步骤/结果目录说明/表格图片解读/参考文献），随包交付。
todos:
  - id: rename-and-adapt
    content: 存量文件就地改名（.meta.yaml/.project.yaml/.source/.notes.md/.index.md），并适配九个脚本中的文件名引用与打包排除规则
    status: completed
  - id: add-report
    content: 新增 .ws/templates/report.md.tmpl 骨架与 .ws/bin/ws_report.sh（内置 stdlib md→html 转换器 + 报告头注入 + 打印友好 CSS）
    status: completed
    dependencies:
      - rename-and-adapt
  - id: sync-docs
    content: 同步 README（目录树/META 示例/流程加 report 步骤/容灾表）与 .codebuddy 规则（收尾必写 report.md）
    status: completed
    dependencies:
      - add-report
  - id: redraw-diagrams
    content: 用 [skill:dynamic-archify] 重渲染 tree/structure 图（节点标签改隐藏名，lifecycle 措辞检查）
    status: completed
    dependencies:
      - sync-docs
  - id: final-verify
    content: 全链路验收：索引/体检/回执/备份指向新文件名，打包 tar 无 .meta.yaml 且含 results/report.html，报告浏览器可看，全仓旧名零残留
    status: completed
    dependencies:
      - redraw-diagrams
---

## 需求描述

两部分改造（均基于现有工作空间脚本体系，无数据库架构不变）：

### 一、配置/元数据文件隐藏

将项目与任务中的五类配置文件改为点前缀隐藏（Linux 隐藏唯一方式），全小写命名：

| 原名 | 新名 | 位置 |
| --- | --- | --- |
| META.yaml | .meta.yaml | 任务目录（唯一事实来源，内容不变） |
| project.yaml | .project.yaml | 批次号目录根（项目级元数据） |
| _source | .source | 批次号目录根（生产目录软链） |
| _notes.md | .notes.md | 批次号目录根（可选备注） |
| INDEX.md | .index.md | 批次号目录根（本批次任务清单） |


- `input.*` 输入软链**不隐藏**（分析脚本按相对路径引用，是业务引用非配置）
- 全局索引 `.ws/INDEX.md` 本就隐藏，不动
- 打包交付**不再包含**元数据文件：客户包只含 scripts/、results/（含报告）等

### 二、新增任务报告能力（用户追加）

每次分析收尾时生成 `results/report.html` —— 一份像样的分析报告，包含：分析思路概述、方案详细步骤、结果目录说明、表格逐个解读、图片逐张解读、参考文献/参考资料引用。交付打包自动带上，客户可直接浏览器打开。

## 验收标准

1. `ls -A projects/<批次号>/` 与任务目录中配置文件全部点前缀隐藏，`ls` 默认视图干净
2. 索引/体检/回执/备份/打包/交付全部链路照常工作（指向新文件名）
3. 打包后 tar 内无 .meta.yaml，含 results/report.html
4. report.html 浏览器直接打开、results 内图片相对引用有效
5. 全仓 grep 旧文件名（META.yaml 等）仅剩 plans 历史档

## 技术栈

沿用现有体系：Bash（`.ws/bin/ws_*.sh`）+ Python 3.8 纯标准库（无 markdown 第三方库，已验证不可用）+ dynamic-archify 渲染架构图。

## 实施方式

### 一、文件名批量迁移（机械改名 + 引用适配）

存量演示数据就地 `mv` 改名；以下脚本内的文件名字符串逐一替换：

| 脚本 | 引用点 |
| --- | --- |
| ws_meta.py | scan 中 `'META.yaml' not in filenames` 与 parse 拼路径 → `.meta.yaml` |
| ws_new_task.sh | META 输出路径、project.yaml 读取路径 |
| ws_new_project.sh | project.yaml 写入、_source 软链、_notes.md、INDEX.md 占位 |
| ws_index.py | project_index 的 `_source`/`_notes.md`/写出 `INDEX.md` → `.index.md`（.ws/INDEX.md 全局份不动） |
| ws_check.sh | `_source` 检查、project.yaml 解析、meta_path |
| ws_receipt.sh | `meta="$task_abs/META.yaml"` |
| ws_deliver.sh | `-not -name META.yaml` → `.meta.yaml` |
| ws_pack.sh | find 名单追加 `! -name '.meta.yaml'`（tar 与 zip 两处），客户包排除元数据 |
| ws_backup.sh | find 名单 META.yaml/project.yaml/INDEX.md → 隐藏名（.ws/INDEX.md 独立行保持） |


### 二、报告能力（新增）

- `.ws/templates/report.md.tmpl`：报告骨架（分析思路概述 / 详细步骤 / 结果目录说明 / 表格解读 / 图片解读 / 参考文献），收尾时 Agent 按骨架填写任务根 `report.md`
- 新增 `.ws/bin/ws_report.sh -T <任务>`：

1. 校验任务根 `report.md` 存在（缺失报错并提示模板位置）
2. 从 `.meta.yaml` 读 id/contract/batch/product/status 生成报告头
3. 内置纯 stdlib 的 md→html 转换器（#~#### 标题、管道表格、-/ *列表、``` 代码块、![图片]（相对路径）、[链接]、**粗体** *斜体* `行内码`、--- 分隔线、空行分段）
4. 注入打印友好 CSS（中文无衬线、表格边框、图片 max-width:100%、@media print）
5. 输出 `results/report.html`（图片相对引用，浏览器与压缩包内均可看）

### 数据流

```mermaid
flowchart LR
  A["收尾：补 methods/output<br/>写 report.md"] --> B["ws_report.sh<br/>report.md → results/report.html"]
  B --> C["ws_index.sh<br/>刷新 .index.md"]
  C --> D["ws_receipt.sh -s done<br/>.outbox/ 回执"]
  D --> E["ws_pack.sh<br/>包内无元数据，含 report.html"]
```

## 注意事项

- ws_meta.py scan 的入口条件 `'META.yaml' not in filenames` 是扫描开关，漏改会导致索引/体检扫描到 0 任务——改名后必须立即验证
- ws_pack.sh 排除元数据后，客户包内容 = scripts/ + results/（含 report.html）+ input 软链天然排除，符合「交付只含分析产物」原则
- 文档同步：README（目录树/META 示例/流程/信息卡/容灾表）与规则文件中的文件名全部替换

## Agent Extensions

### Skill

- **dynamic-archify**
- Purpose: 重渲染 workspace-tree 与 workspace-structure 两张架构图（META.yaml/project.yaml/INDEX.md/_source 节点标签改为隐藏名，报告产物节点说明更新）
- Expected outcome: 两张 HTML 通过布局校验生成到 .ws/docs/，图中无旧文件名残留