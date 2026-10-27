#!/usr/bin/env bash
# 在已有项目（或 scratch）下新建一个分析任务目录（= 客户的一个需求批次）
#
# 用法：
#   ws_new_task.sh -P <project_rel_path> -t <slug> [-r <request>] [-s <status>] [-b <batch>] [-d <YYYYMMDD>] [-c <contract>]
#   ws_new_task.sh -S -t <slug> [-r <request>]
# 例：
#   ws_new_task.sh -P projects/2026/92512126902_mouse -t peak-anno -r "重做peak注释"
#   ws_new_task.sh -P projects/2026/92512126902_mouse -t peak-anno -d 20261101   # 自选日期前缀
#
# 说明：创建任务目录，内含 scripts/（脚本）与 results/（结果）两个固定子目录，
#       以及 .meta.yaml。除此之外不要再建其他子目录。
#       项目的 product/year/contract/source_dir 来自 .project.yaml（ws_new_project.sh 生成），
#       建任务时自动带入任务 META，使任务自包含。

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

proj_rel=""; slug=""; request=""; status="planned"; batch=""; date_prefix=""; contract_ovr=""; use_scratch=0

while getopts ":P:t:r:s:b:d:c:Sh" opt; do
  case "$opt" in
    P) proj_rel="$OPTARG" ;;
    t) slug="$OPTARG" ;;
    r) request="$OPTARG" ;;
    s) status="$OPTARG" ;;
    b) batch="$OPTARG" ;;
    d) date_prefix="$OPTARG" ;;
    c) contract_ovr="$OPTARG" ;;
    S) use_scratch=1 ;;
    h) usage_die "用法：ws_new_task.sh -P <project_rel_path> -t <slug> [-r <request>] [-s <status>] [-b <batch>] [-d <YYYYMMDD>] [-c <contract>]" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done

validate_slug "${slug:?缺少 -t <任务slug>，如 peak-anno}"

case "$status" in
  planned|wip|blocked|done|delivered) ;;
  *) die "非法状态 '$status'（允许：planned|wip|blocked|done|delivered）" ;;
esac

# 任务日期前缀：默认当天，-d 可自选
if [[ -n "$date_prefix" ]]; then
  [[ "$date_prefix" =~ ^[0-9]{8}$ ]] || die "-d 必须是 8 位日期，如 20261101"
  task_date="$date_prefix"
else
  task_date="$(today)"
fi

# 目标父目录
if [[ "$use_scratch" -eq 1 ]]; then
  parent_abs="$SCRATCH_DIR/$(date +%Y%m)"
  parent_rel="scratch/$(date +%Y%m)"
  meta_project="scratch/$(date +%Y%m)"
  contract="(无)"
  source_dir="(无)"
  product=""
else
  [[ -n "$proj_rel" ]] || usage_die "必须用 -P 指定项目相对路径，或用 -S 建临时任务"
  proj_rel="${proj_rel%/}"
  parent_abs="$WS_ROOT/$proj_rel"
  parent_rel="$proj_rel"
  [[ -d "$parent_abs" ]] || die "项目目录不存在：$proj_rel（先用 ws_new_project.sh 创建）"
  meta_project="${proj_rel#projects/}"          # = 年/批次号

  # 项目级元数据：product/year/contract/source_dir
  pj="$parent_abs/.project.yaml"
  if [[ -f "$pj" ]]; then
    product="$(read_project_field "$pj" product)"
    py_contract="$(read_project_field "$pj" contract)"
    py.source="$(read_project_field "$pj" source_dir)"
  else
    warn "项目缺少 .project.yaml（旧结构或手工创建），product 将留空"
    product=""; py_contract=""; py.source=""
  fi

  # 合同号：-c 显式 > .project.yaml > 从批次号/site 推导兜底
  if [[ -n "$contract_ovr" ]]; then
    contract="$contract_ovr"
  elif [[ -n "$py_contract" && "$py_contract" != "null" ]]; then
    contract="$py_contract"
  else
    contract="$(derive_contract "$(basename "$parent_abs")")"
  fi

  # 生产目录：.project.yaml > .source 软链 > 未匹配
  if [[ -n "$py.source" && "$py.source" != "null" ]]; then
    source_dir="$py.source"
  elif [[ -L "$parent_abs/.source" ]]; then
    source_dir="$(readlink "$parent_abs/.source")"
  else
    source_dir="(未匹配，请人工确认)"
  fi
fi

# 需求批次号：未指定则按已有任务数自动编号（b01、b02 …）
if [[ -z "$batch" ]]; then
  batch="$(printf 'b%02d' "$(( $(count_tasks "$parent_abs") + 1 ))")"
fi

mkdir -p "$parent_abs"
task_dir="${task_date}_${slug}"
task_abs="$parent_abs/$task_dir"

[[ -d "$task_abs" ]] && die "任务目录已存在：${parent_rel}/${task_dir}
  如需重做，请用同名加 -v2 后缀：$(today)_${slug}-v2"

mkdir -p "$task_abs/scripts" "$task_abs/results"
info "创建任务：${parent_rel}/${task_dir}（批次 $batch）→ scripts/ + results/"

[[ -n "$request" ]] || request="TODO：填写客户的原始需求"

render_template "$TEMPLATE_DIR/META.yaml.tmpl" \
  ID "$task_dir" \
  PROJECT "$meta_project" \
  PRODUCT "${product:-null}" \
  CONTRACT "$contract" \
  BATCH "$batch" \
  SOURCE "$source_dir" \
  CREATED "$(isodate)" \
  STATUS "$status" \
  REQUEST "$request" > "$task_abs/.meta.yaml"
info "生成：.meta.yaml"

cat <<EOF

[完成] ${parent_rel}/${task_dir}
  脚本放 scripts/，结果与图放 results/，输入仍用 ln -s（禁止 cp 大文件，单任务产出 ≤200MB）。
  收尾：补 methods/scripts/output 与 status: done，然后 bash .ws/bin/ws_index.sh
EOF
