# .kb —— 工作空间代码与文档知识库

> 唯一事实源在服务器本目录；GitHub（growkb 私库）是同步备份，外部知识库（如 ima）只做只读镜像，**严禁双写**。

## 目录结构

```
.kb/
├── code/                 # 代码知识库（可 source/import，任务直接调用）
│   ├── R/<主题>/         #   annotation / visualization / …
│   └── python/<主题>/    #   qc / visualization / …
├── cli/                  # 独立 CLI（薄壳：只做参数解析，业务逻辑在 code/）
│   ├── R/                #   Rscript + optparse
│   └── python/           #   argparse
├── docs/                 # 文档知识库（提炼后的经验，供借鉴优化）
│   ├── requirements/     #   需求解读与任务拆解（按 <批次号>-<slug>.md 归档）
│   ├── methods/          #   分析方法笔记（按主题归档）
│   ├── references/       #   参考文献 / 软件引用
│   └── results/          #   结果与图像说明沉淀
├── .index.md             # 自动索引（ws_kb.sh index 生成，勿手改）
└── CHANGELOG.md          # 同步记录（ws_kb.sh sync 自动追加）
```

## 代码库编写规范

### R（一函数一文件，文件名 = 函数名，Roxygen Skeleton）

```r
#' 一句话标题（INDEX 用）
#'
#' 详细描述：做什么、什么时候用、口径/假设。
#'
#' @param peaks 数据框，必须包含 `annotation` 列（区域类型）
#' @param promoter_level 字符串，promoter 区域的判定值，默认 "Promoter"
#' @return 数据框，含 `region` 与 `ratio` 两列（占比 0-1）
#' @export
#' @examples
#' \dontrun{
#' promoter_ratio(read.delim("results/peak.anno.tsv"))
#' }
promoter_ratio <- function(peaks, promoter_level = "Promoter") {
  stopifnot(is.data.frame(peaks), "annotation" %in% names(peaks))
  ...
}
```

要点：每个参数一条 `@param`（含类型与默认值含义）；`@examples` 纯计算示例可直接跑，依赖真实数据的用 `\dontrun{}` 包裹；导出给任务用的函数加 `@export`。

### Python（Google-style docstring + 类型注解）

```python
def tsv_stats(df: "pd.DataFrame", columns: list[str] | None = None) -> dict:
    """计算数值列的摘要统计。

    Args:
        df: 输入数据框。
        columns: 要统计的列名，缺省为全部数值列。

    Returns:
        dict: 列名 -> {count, mean, min, max}。

    Raises:
        ValueError: 指定列不存在或全为非数值。
    """
```

### CLI 约定（薄壳原则）

- 文件名：`kb_<动作>.<ext>`；参数长名统一 snake_case；`--input/--output` 语义固定
- CLI 只做参数解析 + 调用 `code/` 里的库函数，**业务逻辑不写在 CLI 里**（为封装 skill/agent 工具铺路）
- R 用 optparse，Python 用 argparse；`--help` 必须完整可读

## 文档库编写规范

- 一个主题一份 md，文件名小写连字符；需求拆解类按 `<批次号>-<slug>.md` 归档
- 文件头写 front-matter（会被索引提取）：

```markdown
---
batch: 92512126902_mouse
tags: promoter, TxDb
---
# 标题
正文……
```

- 写「可借鉴的经验」而非流水账：口径怎么定、坑在哪、下次怎么做更快

## 提炼流程（积累与优化闭环）

1. **受理时**：Agent 先查 `.index.md`，有现成函数/CLI/方法笔记直接复用
2. **收尾时**：任务中可泛化的函数 → `ws_kb.sh new` 生成脚手架 → 规范化填入 → `ws_kb.sh check` 体检 → `ws_kb.sh index` 更新索引
3. **文档沉淀**：需求拆解、方法笔记、结果说明按主题写入 `docs/` 对应子目录
4. **同步备份**：`ws_kb.sh sync "feat: 说明"` —— 规范化 commit + push 到 growkb 私库，CHANGELOG 自动追加

## 主题新增原则

按语义归入现有主题；确实无合适主题才新建子目录（宁可主题略宽，不要碎片化）。
