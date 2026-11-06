#!/usr/bin/env bash
# 备份「删了就回不来」的东西：
#   任务 .meta.yaml / .project.yaml / .notes.md / 各级 .index.md / report.md 源稿 /
#   任务脚本（scripts/ 下的 .R .py .sh .Rmd）/ .ws/bin + .ws/templates 工具区 / 回执 .outbox/
#
# 用法：
#   .ws/bin/ws_backup.sh          # 备份到 .ws/backup/，默认保留最近 10 份
#   .ws/bin/ws_backup.sh -k 30    # 自定义保留份数
#   .ws/bin/ws_backup.sh -o /tmp  # 输出到其它位置（建议偶尔拷到本地，见 README 容灾）
#
# 恢复：
#   tar xzf .ws/backup/ws-meta-<日期>.tar.gz -C /   # 包内是相对 workspace 根的完整路径
#
# 不进包：results/ 产物（可重算或从生产 Analysis/ 回捞）、交付压缩包、.kb（growkb 私库有独立备份）

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

keep=10
outdir=""
while getopts ":k:o:h" opt; do
  case "$opt" in
    k) keep="$OPTARG" ;;
    o) outdir="$OPTARG" ;;
    h) usage_die "用法：ws_backup.sh [-k 保留份数] [-o 输出目录]" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done
[[ "$keep" =~ ^[0-9]+$ ]] || die "保留份数必须是数字"
[[ $keep -ge 1 ]] || die "保留份数至少为 1"

[[ -n "$outdir" ]] || outdir="$WS_ROOT/.ws/backup"
mkdir -p "$outdir"

list="$(mktemp)"
cleanup() { rm -f "$list"; }
trap cleanup EXIT

# ① 任务与项目元数据 + 索引 + 报告源稿 + 任务脚本（小文本文件，results/ 产物不进包）
for scope in projects scratch; do
  [[ -d "$WS_ROOT/$scope" ]] || continue
  (cd "$WS_ROOT" && find "$scope" -type f \
      \( -name '.meta.yaml' -o -name '.project.yaml' -o -name '.index.md' \
         -o -name '.notes.md' -o -name 'report.md' \
         -o -path '*/scripts/*.R' -o -path '*/scripts/*.py' \
         -o -path '*/scripts/*.sh' -o -path '*/scripts/*.Rmd' \) -print0)
done >> "$list"

# ② 工具区：管理脚本 + 模板（README 有规范可重建，但进了备份恢复更快）
(cd "$WS_ROOT" && find .ws/bin .ws/templates -type f -not -path '*/__pycache__/*' -print0) >> "$list"

# ③ 回执
[[ -d "$WS_ROOT/.outbox" ]] && (cd "$WS_ROOT" && find .outbox -type f -name '*.yaml' -print0) >> "$list"
[[ -f "$WS_ROOT/.ws/.index.md" ]] && printf '%s\0' '.ws/.index.md' >> "$list"

# 去重（防御性）
sort -u -z "$list" -o "$list"

nfile=$(tr -cd '\0' < "$list" | wc -c)
[[ "$nfile" -gt 0 ]] || die "没有找到任何可备份文件"

out="$outdir/ws-meta-$(today).tar.gz"
if [[ -e "$out" ]]; then
  out="$outdir/ws-meta-$(today)-$(date +%H%M%S).tar.gz"
fi
tar czf "$out" -C "$WS_ROOT" --null -T "$list"

# 只保留最近 N 份
ls -1t "$outdir"/ws-meta-*.tar.gz 2>/dev/null | tail -n +$((keep + 1)) | while read -r old; do
  rm -f "$old"
done

count=$(ls -1 "$outdir"/ws-meta-*.tar.gz 2>/dev/null | wc -l)
size="$(du -h "$out" | cut -f1)"
md5="$(md5sum "$out" | cut -d' ' -f1)"

cat <<EOF

[完成] 元数据与代码备份
  文件：${out#$WS_ROOT/}
  含 ${nfile} 个文件　大小：$size
  MD5  ：$md5
  保留：最多 $keep 份（当前 $count 份）
  提醒：这个包在工作空间内部，整机事故挡不住 —— 重要节点请 scp 一份到本地（见 README 3-2-1）。
EOF
