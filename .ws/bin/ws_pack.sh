#!/usr/bin/env bash
# 把任务产物打包成客户交付压缩包（只含常规文件，输入软链自动排除）
#
# 用法：
#   ws_pack.sh -T <task_rel_path>                  # 打包单个任务
#   ws_pack.sh -P <project_rel_path> [-b b01,b02]  # 打包项目下若干批次（默认全部任务）
#   ws_pack.sh -T <task> -f zip                    # 输出 zip（Windows 客户更友好）
#   ws_pack.sh -T <task> -o <输出目录>              # 指定输出目录（默认就地，见下）
#
# 输出位置：默认**就地** —— 单任务打包落在任务目录内，项目批次打包落在项目目录内。
#   交付包跟着任务走：回溯时在任务目录里就能看到成品，不用再去别处找。
# 文件命名：<合同号>_<任务或批次>_<日期>.tar.gz
# 包内结构：<任务目录名>/文件…（不含深层路径、不含输入软链、不含已有的包）

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

task_rel=""; proj_rel=""; batches=""; fmt="tar.gz"; outdir=""

while getopts ":T:P:b:f:o:h" opt; do
  case "$opt" in
    T) task_rel="$OPTARG" ;;
    P) proj_rel="$OPTARG" ;;
    b) batches="$OPTARG" ;;
    f) fmt="$OPTARG" ;;
    o) outdir="$OPTARG" ;;
    h) usage_die "用法：ws_pack.sh -T <task_rel_path> | -P <project_rel_path> [-b b01,b02] [-f tar.gz|zip] [-o <dir>]" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done

[[ "$fmt" == "tar.gz" || "$fmt" == "zip" ]] || die "格式只支持 tar.gz 或 zip"
[[ -n "$task_rel" || -n "$proj_rel" ]] || usage_die "必须用 -T 指定任务，或用 -P 指定项目"

batch_of() { sed -n 's/^batch:[[:space:]]*//p' "$1/.meta.yaml" 2>/dev/null | head -1; }

# ---------- 收集待打包的任务目录 ----------
tasks=()
if [[ -n "$task_rel" ]]; then
  task_rel="${task_rel%/}"
  [[ -d "$WS_ROOT/$task_rel" ]] || die "任务目录不存在：$task_rel"
  tasks+=("$WS_ROOT/$task_rel")
else
  proj_rel="${proj_rel%/}"
  pabs="$WS_ROOT/$proj_rel"
  [[ -d "$pabs" ]] || die "项目目录不存在：$proj_rel"
  want=()
  [[ -n "$batches" ]] && IFS=',' read -ra want <<< "$batches"
  for d in "$pabs"/[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_*; do
    [[ -d "$d" ]] || continue
    if [[ ${#want[@]} -gt 0 ]]; then
      b="$(batch_of "$d")"; skip=1
      for w in "${want[@]}"; do [[ "$b" == "$w" ]] && skip=0; done
      [[ $skip -eq 1 ]] && continue
    fi
    tasks+=("$d")
  done
fi

[[ ${#tasks[@]} -gt 0 ]] || die "没有匹配到待打包的任务"

# ---------- 命名 ----------
first_meta="${tasks[0]}/.meta.yaml"
[[ -f "$first_meta" ]] || die "缺少 .meta.yaml：${tasks[0]}"
contract="$(sed -n 's/^contract:[[:space:]]*//p' "$first_meta" | head -1)"
[[ -n "$contract" ]] || contract="nocontract"

if [[ ${#tasks[@]} -eq 1 ]]; then
  name_part="$(basename "${tasks[0]}")"
  name_part="${name_part:9}"                 # 去掉 YYYYMMDD_ 前缀
else
  bs=()
  for t in "${tasks[@]}"; do
    b="$(batch_of "$t")"; [[ -n "$b" ]] && bs+=("$b")
  done
  name_part="batch-$(IFS='-'; echo "${bs[*]:-all}")"
fi

# 默认就地：单任务 → 任务目录；项目批次 → 项目目录
if [[ -z "$outdir" ]]; then
  if [[ ${#tasks[@]} -eq 1 ]]; then
    outdir="${tasks[0]}"
  else
    outdir="$WS_ROOT/$proj_rel"
  fi
fi
mkdir -p "$outdir"
out="$outdir/${contract}_${name_part}_$(today).${fmt}"
rel_out="${out#$WS_ROOT/}"          # META 里存相对工作空间根目录的路径，换机器也不失效
[[ -e "$out" ]] && die "目标压缩包已存在：$rel_out（请先移走或改名，避免覆盖已交付文件）"

# ---------- 文件清单：相对 WS_ROOT 的常规文件（软链天然排除） ----------
list="$(mktemp)"
cleanup() { rm -f "$list"; [[ -n "${tmpdir:-}" ]] && rm -rf "$tmpdir"; }
trap cleanup EXIT

for t in "${tasks[@]}"; do
  # 排除已有的包：否则重打一次会把上次的包再压进去，越打越大（自我嵌套）
  (cd "$WS_ROOT" && find "${t#$WS_ROOT/}" -type f \
      ! -name '.meta.yaml' ! -name 'report.md' \
      ! -name '*.tar.gz' ! -name '*.zip' -print0) >> "$list"
done
nfile=$(tr -cd '\0' < "$list" | wc -c)
[[ "$nfile" -gt 0 ]] || die "待打包任务里没有常规文件（软链、空目录与已有压缩包均不计）"

# ---------- 打包 ----------
# 三级结构：剥掉 projects/<年>/<批次号>/<任务名>/ 前缀（scratch 同理剥一层）
transform='s|^projects/[^/]*/[^/]*/[^/]*/||;s|^scratch/[^/]*/||'
if [[ "$fmt" == "tar.gz" ]]; then
  if tar --version 2>/dev/null | grep -q GNU; then
    tar czf "$out" -C "$WS_ROOT" --transform="$transform" --null -T "$list"
  else
    warn "非 GNU tar，包内将保留 projects/... 完整路径"
    tar czf "$out" -C "$WS_ROOT" --null -T "$list"
  fi
else
  command -v zip >/dev/null 2>&1 || die "未找到 zip 命令，请改用 -f tar.gz"
  tmpdir="$(mktemp -d)"
  for t in "${tasks[@]}"; do
    dest="$tmpdir/$(basename "$t")"
    mkdir -p "$dest"
    (cd "$t" && find . -type f ! -name '.meta.yaml' ! -name 'report.md' \
        ! -name '*.tar.gz' ! -name '*.zip' \
        -exec cp -p --parents {} "$dest/" \;)
  done
  (cd "$tmpdir" && zip -qr "$out" .)
fi

size="$(du -h "$out" | cut -f1)"
md5="$(md5sum "$out" | cut -d' ' -f1)"

# ---------- 回填 .meta.yaml ----------
for t in "${tasks[@]}"; do
  m="$t/.meta.yaml"
  [[ -f "$m" ]] || continue
  python3 - "$m" "$rel_out" <<'PY'
import re, sys
path, out = sys.argv[1], sys.argv[2]
text = open(path, encoding='utf-8').read()
if re.search(r'^\s*packed:', text, re.M):
    text = re.sub(r'^(\s*)packed:.*$', r'\1packed: %s' % out, text, count=1, flags=re.M)
elif re.search(r'^deliverable:', text, re.M):
    text = re.sub(r'^(\s*)synced_to:', r'  synced_to: null', text, count=0, flags=re.M)
    text = text.rstrip('\n') + '\n  packed: %s\n' % out
else:
    text += '\ndeliverable:\n  packed: %s\n' % out
open(path, 'w', encoding='utf-8').write(text)
PY
done

cat <<EOF

[完成] 交付压缩包
  文件：$rel_out
  大小：$size　文件数：$nfile　格式：$fmt
  MD5  ：$md5
  含任务：${#tasks[@]} 个（各 .meta.yaml 的 deliverable.packed 已回填）
  提醒：包内不含输入软链与已有的包；调用 .ws/bin/ws_deliver.sh 同步时也会跳过压缩包
EOF
