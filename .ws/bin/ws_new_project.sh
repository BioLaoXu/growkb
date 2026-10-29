#!/usr/bin/env bash
# 新建一个批次号项目目录（含 .project.yaml、生产目录软链与索引占位）
#
# 用法：
#   ws_new_project.sh -b <批次号> -p <product> [-y <year>] [-s <site> | -f <source_dir>] [-c <contract>] [-t <title>]
# 例：
#   ws_new_project.sh -b 92512126902_mouse -p cut_tag -s 92512126902_mouse
#   ws_new_project.sh -b B20261027-001 -p rna -f /data/Report/rna_project_2026/SP001 -t "xx项目"
#
# 说明：
#   - 批次号 = personal-workbench 带来的样本批次编号，直接作为目录名（不再含产品/年份层级）
#   - 生产目录定位二选一：-s 给生产目录名（按 /data/Report/<产品>_project_<年>/ 推导，
#     年份缺省时依次尝试当年与近两年，再 glob 兜底）；-f 直接给完整路径
#   - 项目元数据写入 .project.yaml，建任务时自动带入任务 META

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

batch=""; product=""; site=""; source_dir=""; year=""; contract=""; title=""

while getopts ":b:p:s:f:y:c:t:h" opt; do
  case "$opt" in
    b) batch="$OPTARG" ;;
    p) product="$OPTARG" ;;
    s) site="$OPTARG" ;;
    f) source_dir="$OPTARG" ;;
    y) year="$OPTARG" ;;
    c) contract="$OPTARG" ;;
    t) title="$OPTARG" ;;
    h) usage_die "用法：ws_new_project.sh -b <批次号> -p <product> [-s <site> | -f <source_dir>] [-y <year>] [-c <contract>] [-t <title>]" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done

[[ -n "$batch" ]] || usage_die "必须用 -b 指定批次号（来自 personal-workbench 的样本批次编号）"
[[ -n "$product" ]] || usage_die "必须用 -p 指定产品类型（对账字段，来自工作台）"
validate_name "$batch"   "批次号"
validate_name "$product" "产品类型"
[[ -z "$year" ]] || { validate_name "$year" "年份"; [[ "$year" =~ ^[0-9]{4}$ ]] || die "年份必须为 4 位数字，如 2026"; }
[[ -z "$year" ]] && year="$(date +%Y)"

# 解析生产目录：-f 全路径直给 > -s site 推导 > 都没有则留空（仅提示）
if [[ -z "$source_dir" && -z "$site" ]]; then
  warn "未给 -s <site> 或 -f <source_dir>：不建立 .source 软链，生产目录定位信息留空"
elif [[ -n "$source_dir" ]]; then
  [[ -d "$source_dir" ]] || warn "指定的源目录不存在：$source_dir（仍会建链，注意失效风险）"
else
  if source_dir="$(resolve_source "$product" "${year:-}" "$site")"; then
    info "自动匹配生产目录：$source_dir"
  else
    warn "未在 /data/Report 下推导到 ${product} 项目的 ${site}；可用 -f <路径> 显式指定，或稍后手工补 .source 软链。"
    source_dir=""
  fi
fi

# 合同号：-c 显式 > 从 site/批次号推导 > 空
[[ -n "$contract" ]] || contract="$(derive_contract "${site:-$batch}")"

proj_rel="projects/${year}/${batch}"
proj_abs="$WS_ROOT/$proj_rel"
[[ -d "$proj_abs" ]] && info "项目已存在：$proj_rel（只刷新 .project.yaml 缺失字段不会覆盖已有任务）"
mkdir -p "$proj_abs"

# 项目级元数据（建任务时自动带入任务 META）
if [[ ! -f "$proj_abs/.project.yaml" ]]; then
  cat > "$proj_abs/.project.yaml" <<EOF
# 项目级元数据：批次号目录的定位信息（.ws/bin/ws_new_task.sh 建任务时自动带入任务 META）
batch: $batch          # 工作台样本批次号（= 本目录名）
product: ${product:-null}
year: $year
site: ${site:-null}           # 生产目录名（可空）
source_dir: ${source_dir:-null}
contract: ${contract:-null}   # 合同号
created: $(isodate)
EOF
  info "生成：.project.yaml"
fi

# 备注文件：只有给了 -t 才建（默认不建，保持目录清爽）
if [[ -n "$title" && ! -f "$proj_abs/.notes.md" ]]; then
  {
    printf '# %s\n\n' "$title"
    printf -- '- 批次号：%s\n' "$batch"
    printf -- '- 合同号：%s\n' "${contract:-（未定）}"
    printf -- '- 生产目录：%s\n' "${source_dir:-（未匹配）}"
    printf -- '- 创建日期：%s\n\n' "$(isodate)"
    printf '## 合同背景\n\nTODO：客户、物种、样本数量、分组设计、合同特殊条款\n\n'
    printf '## 交付要求\n\nTODO：交付内容、格式、截止日期\n'
  } > "$proj_abs/.notes.md"
  info "生成：.notes.md（可选备注，会被 .index.md 引用）"
fi

# 生产目录软链
[[ -n "$source_dir" ]] && link_if_absent "$source_dir" "$proj_abs/.source"

# 空索引占位（内容由 ws_index.sh 生成）
[[ -f "$proj_abs/.index.md" ]] || printf '# 分析任务索引\n\n> 由 `.ws/bin/ws_index.sh` 自动生成，请勿手工编辑。\n\n暂无任务。\n' > "$proj_abs/.index.md"

cat <<EOF

[完成] $proj_rel
  下一步：
    bash .ws/bin/ws_new_task.sh -P $proj_rel -t <任务slug> -r "<客户需求>"
    （可选 -d YYYYMMDD 自选任务日期前缀）
EOF
