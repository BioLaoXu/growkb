#!/usr/bin/env bash
# 写任务回执到 .outbox/，供 personal-workbench 拉取后更新自己任务库的状态
#
# 用法：
#   ws_receipt.sh -T <task_rel_path> -s accepted              # 受理回执
#   ws_receipt.sh -T <task_rel_path> -s done                  # 完成回执
#   ws_receipt.sh -T <task_rel_path> -s delivered [-p 包路径]  # 交付回执（自动读 META 的 packed）
#   ws_receipt.sh -T <task_rel_path> -s done -m "备注一句话"   # 附加说明
#
# 回执文件：.outbox/<日期>_<taskId>_<status>.yaml
#   status ∈ accepted | done | delivered

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

task_rel=""; status=""; note=""
while getopts ":T:s:m:h" opt; do
  case "$opt" in
    T) task_rel="$OPTARG" ;;
    s) status="$OPTARG" ;;
    m) note="$OPTARG" ;;
    h) usage_die "用法：ws_receipt.sh -T <task_rel_path> -s accepted|done|delivered [-m 备注] [-p 包路径]" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done

[[ -n "$task_rel" && -n "$status" ]] || usage_die "必须给 -T <任务> 与 -s accepted|done|delivered"
case "$status" in
  accepted|done|delivered) ;;
  *) die "status 只支持 accepted / done / delivered" ;;
esac

task_rel="${task_rel%/}"
task_abs="$WS_ROOT/$task_rel"
[[ -d "$task_abs" ]] || die "任务目录不存在：$task_rel"
meta="$task_abs/.meta.yaml"
[[ -f "$meta" ]] || die "缺少 .meta.yaml：$task_rel"

field() { sed -n "s/^$1:[[:space:]]*//p" "$meta" | head -1 | cut -d'#' -f1 | sed 's/[[:space:]]*$//'; }

taskId="$(field id)"
contractNo="$(field contract)"
product="$(field product)"
batch="$(field batch)"
packed="$(python3 - "$meta" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1], encoding='utf-8')) or {}
print((d.get('deliverable') or {}).get('packed') or 'null')
PY
)"

# 产品线来自任务 .meta.yaml（受理时从 .project.yaml 带入）；scratch 任务为空/占位
[[ -z "$product" ]] && product="null"

outdir="$WS_ROOT/.outbox"
mkdir -p "$outdir"
out="$outdir/$(today)_${taskId}_${status}.yaml"

cat > "$out" <<EOF
# personal-workbench 回执：拉取后可按 contractNo+batch+taskId 对齐更新本地状态
at: $(date '+%Y-%m-%d %H:%M:%S')
status: $status
taskId: ${taskId:-未知}
taskPath: $task_rel
contractNo: ${contractNo:-null}
batch: ${batch:-null}
productName: ${product:-null}
packed: $packed
EOF

if [[ -n "$note" ]]; then
  printf 'note: >-\n  %s\n' "$note" >> "$out"
fi

info "回执已写入：${out#$WS_ROOT/}"
cat "$out"
