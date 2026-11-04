#!/usr/bin/env bash
# 把一个任务的产物同步到生产目录的 Analysis/<日期>/，只做新增，绝不覆盖
#
# 用法：
#   ws_deliver.sh -T <task_rel_path>            # 预演（默认，只打印清单）
#   ws_deliver.sh -T <task_rel_path> -y         # 真正执行并回填 META
#   ws_deliver.sh -T <task_rel_path> -d 20261026  # 指定生产子目录日期
#
# 规则：
#   1. 只复制常规文件，输入软链一律跳过（避免把大文件 cp 进生产目录）
#   2. 目标已存在同名文件时跳过（cp -n），不覆盖任何既有产物
#   3. 执行成功后回填 META.yaml 的 deliverable.*，status 置 delivered，并重建索引

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

command -v python3 >/dev/null 2>&1 || die "未找到 python3"

task_rel=""; apply=0; date_tag=""

while getopts ":T:d:yh" opt; do
  case "$opt" in
    T) task_rel="$OPTARG" ;;
    d) date_tag="$OPTARG" ;;
    y) apply=1 ;;
    h) usage_die "用法：ws_deliver.sh -T <task_rel_path> [-d <日期>] [-y]" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done

[[ -n "$task_rel" ]] || usage_die "必须用 -T 指定任务相对路径，如 projects/cut_tag/2026/demo_batch_mouse/20261026_peak-anno"
task_rel="${task_rel%/}"
task_abs="$WS_ROOT/$task_rel"
[[ -d "$task_abs" ]] || die "任务目录不存在：$task_rel"
[[ -f "$task_abs/META.yaml" ]] || die "缺少 META.yaml：$task_rel"

# 从 META.yaml 读取 source_dir 与任务日期
read_meta() {
  python3 -c "
import re,sys
key=sys.argv[1]
for line in open(sys.argv[2],encoding='utf-8'):
    m=re.match(r'^'+key+r':\s*(.*)$',line.rstrip('\n'))
    if m:
        print(m.group(1).strip()); break
" "$1" "$task_abs/META.yaml"
}

source_dir="$(read_meta source_dir)"
[[ -n "$source_dir" && "$source_dir" != "("* ]] || die "META.yaml 的 source_dir 无效（'$source_dir'），无法定位生产目录"
[[ "$source_dir" == /data/Report/* ]] || die "source_dir 不在 /data/Report 下，拒绝同步：$source_dir"
[[ -d "$source_dir" ]] || die "生产目录不存在（可能被清理）：$source_dir"

task_name="$(basename "$task_abs")"
[[ -n "$date_tag" ]] || date_tag="${task_name:0:8}"
[[ "$date_tag" =~ ^[0-9]{8}$ ]] || die "日期标签必须是 8 位数字，如 20261026"

dest="$source_dir/Analysis/$date_tag"

# 待同步文件：常规文件，排除 META.yaml 与压缩包（交付包不同步进生产目录）
#   软链（输入数据）自动排除
mapfile -t files < <(cd "$task_abs" && find . -type f -not -name META.yaml \
    -not -name '*.tar.gz' -not -name '*.zip' | sed 's|^\./||' | sort)

if [[ ${#files[@]} -eq 0 ]]; then
  warn "任务目录下没有可交付的常规文件（软链、压缩包与 META.yaml 已排除）"
  exit 0
fi

echo "—— 交付清单 ——"
echo "源：$task_rel"
echo "目标：$dest"
printf '文件 %d 个：\n' "${#files[@]}"
for f in "${files[@]}"; do
  if [[ -e "$dest/$f" ]]; then
    printf '  [跳过·已存在] %s\n' "$f"
  else
    printf '  [新增] %s\n' "$f"
  fi
done

if [[ "$apply" -eq 0 ]]; then
  echo
  echo "[预演] 未做任何写入。确认无误后加 -y 执行。"
  exit 0
fi

mkdir -p "$dest"
added=0
for f in "${files[@]}"; do
  mkdir -p "$dest/$(dirname "$f")"
  if cp -pn "$task_abs/$f" "$dest/$f" 2>/dev/null; then
    printf '  [已写入] %s\n' "$f"
    added=$((added + 1))
  else
    printf '  [跳过] %s（目标已存在，未覆盖）\n' "$f"
  fi
done

# 回填 META.yaml
python3 - "$task_abs/META.yaml" "$dest" "$added" <<'PY'
import re, sys
from datetime import datetime

path, dest, added = sys.argv[1], sys.argv[2], int(sys.argv[3])
text = open(path, encoding='utf-8').read()
now = datetime.now().strftime('%Y-%m-%d %H:%M')

if re.search(r'^status:', text, re.M):
    text = re.sub(r'^status:.*$', 'status: delivered', text, count=1, flags=re.M)
else:
    text += '\nstatus: delivered\n'

if re.search(r'^deliverable:', text, re.M):
    text = re.sub(r'^(\s*)synced_to:.*$', r'\1synced_to: %s' % dest, text, count=1, flags=re.M)
    text = re.sub(r'^(\s*)synced_at:.*$', r'\1synced_at: %s' % now, text, count=1, flags=re.M)
else:
    text += '\ndeliverable:\n  synced_to: %s\n  synced_at: %s\n' % (dest, now)

if re.search(r'^updated:', text, re.M):
    text = re.sub(r'^updated:.*$', 'updated: %s' % datetime.now().strftime('%Y-%m-%d'), text, count=1, flags=re.M)

open(path, 'w', encoding='utf-8').write(text)
print('[INFO] META.yaml 已回填：status=delivered, synced_to=%s（新增 %d 个文件）' % (dest, added))
PY

bash "$WS_ROOT/.ws/bin/ws_index.sh"
