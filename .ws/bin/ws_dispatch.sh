#!/usr/bin/env bash
# 一键发起分析任务：建项目（如缺）→ 建任务 → 生成信息卡到 .inbox/ → 提示调起 CodeBuddy 受理
#
# 用法：
#   ws_dispatch.sh -b <批次号> -p <产品> (-s <site> | -f <source_dir>) -r "<需求>" \
#                 [-t <slug>] [-d <YYYYMMDD>] [-y <year>] [-c <contract>] [-m <备注>]
#   追加 -C：卡-only 模式（只投卡到 .inbox/，受理时才建项目/任务）
# 例：
#   ws_dispatch.sh -b 92512126902_mouse -p cut_tag -s 92512126902_mouse \
#                 -r "用最新 TxDb 重做 peak 注释" -t peak-anno
#
# 流程：项目不存在则建 → 建任务 → 完整信息卡写入 .inbox/<日期>_<任务>_dispatch.yaml
#       然后打开 CodeBuddy 新会话（工作空间根），说「受理 <卡文件>」即可。

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

batch=""; product=""; site=""; source_dir=""; request=""; slug=""; date_prefix=""; year=""; contract=""; note=""

card_only=0
while getopts ":b:p:s:f:r:t:d:y:c:m:Ch" opt; do
  case "$opt" in
    b) batch="$OPTARG" ;;
    p) product="$OPTARG" ;;
    s) site="$OPTARG" ;;
    f) source_dir="$OPTARG" ;;
    r) request="$OPTARG" ;;
    t) slug="$OPTARG" ;;
    d) date_prefix="$OPTARG" ;;
    y) year="$OPTARG" ;;
    c) contract="$OPTARG" ;;
    m) note="$OPTARG" ;;
    C) card_only=1 ;;
    h) usage_die "用法：ws_dispatch.sh -b <批次号> -p <产品> (-s <site>|-f <source_dir>) -r \"<需求>\" [-t slug] [-d YYYYMMDD] [-y 年] [-c 合同] [-m 备注]" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done

[[ -n "$batch" && -n "$product" && -n "$request" ]] || usage_die "必须给 -b <批次号> -p <产品> -r \"<需求>\""
[[ -n "$site" || -n "$source_dir" ]] || usage_die "必须给 -s <site>（推导）或 -f <source_dir>（全路径）"
[[ -z "$year" ]] && year="$(date +%Y)"
[[ -n "$slug" ]] || slug="req-$(date +%H%M%S)"

# ⓪ 卡-only 模式：只投卡，受理时才建项目/任务
if [[ $card_only -eq 1 ]]; then
  mkdir -p "$WS_ROOT/.inbox"
  card="$WS_ROOT/.inbox/$(today)_${slug}_card.yaml"
  request_flat="${request//$'\n'/ }"
  cat > "$card" <<EOF
# 卡-only 投递（ws_dispatch -C）：未建任务，受理时创建
【分析请求】
batch: $batch
contract: ${contract:-null}
product: $product
site: ${site:-null}
source_dir: ${source_dir:-null}
year: $year
slug: $slug
date: $(today)
request: >-
  $request_flat
species: null
sample_batch: null
notes: ${note:-null}
EOF
  cat <<EOF

[完成] 卡-only 投递：${card#$WS_ROOT/}
  任务未创建——在看板点 [受理]，或会话说「受理 $slug」时创建项目/任务。
EOF
  exit 0
fi

# ① 建项目（已存在则复用）
proj_rel="projects/${year}/${batch}"
if [[ -d "$WS_ROOT/$proj_rel" ]]; then
  info "项目已存在：$proj_rel（复用）"
else
  proj_args=(-b "$batch" -p "$product" -y "$year")
  [[ -n "$site" ]] && proj_args+=(-s "$site")
  [[ -n "$source_dir" ]] && proj_args+=(-f "$source_dir")
  [[ -n "$contract" ]] && proj_args+=(-c "$contract")
  bash "$WS_ROOT/.ws/bin/ws_new_project.sh" "${proj_args[@]}" >/dev/null
  info "项目就绪：$proj_rel"
fi

# ② 建任务
task_args=(-P "$proj_rel" -t "$slug" -r "$request")
[[ -n "$date_prefix" ]] && task_args+=(-d "$date_prefix")
bash "$WS_ROOT/.ws/bin/ws_new_task.sh" "${task_args[@]}" >/dev/null
task_dir="$(ls -1d "$WS_ROOT/$proj_rel"/*"$slug" 2>/dev/null | tail -1)"
task_dir="${task_dir#$WS_ROOT/}"
task_base="${task_dir##*/}"

# ③ 生成信息卡（CodeBuddy 受理入口）
field() { sed -n "s/^$1:[[:space:]]*//p" "$WS_ROOT/$task_dir/.meta.yaml" | head -1 | cut -d'#' -f1 | sed 's/[[:space:]]*$//'; }
meta_project="$(field project)"
meta_contract="$(field contract)"
meta_source="$(field source_dir)"

mkdir -p "$WS_ROOT/.inbox"
card="$WS_ROOT/.inbox/$(today)_${task_dir##*/}_dispatch.yaml"
cat > "$card" <<EOF
# 一键发起的分析请求（ws_dispatch.sh 生成）——CodeBuddy 会话说「受理 <本文件>」即走 README 第七节流程
【分析请求】
batch: ${meta_project##*/}
contract: ${meta_contract:-null}
product: ${product}
site: ${site:-null}
source_dir: ${source_dir:-${meta_source:-null}}
year: ${year}
slug: ${slug}
date: ${task_base:0:8}
request: >-
  ${request}
inputs: []
deadline: null
notes: ${note:-null}
taskPath: $task_dir            # 任务已创建，受理时无需重复建目录
EOF

# ④ 刷新索引
bash "$WS_ROOT/.ws/bin/ws_index.sh" >/dev/null

cat <<EOF

[完成] 任务已发起：${task_dir}
  信息卡：${card#$WS_ROOT/}
  下一步（二选一）：
    A. 打开 CodeBuddy 新会话（工作空间根），说一句：受理 ${card#$WS_ROOT/}
    B. 把上面信息卡内容直接贴进任意 CodeBuddy 会话
  说明：slug 为自动生成时，受理的 Agent 可与你确认更名后重建。
EOF
