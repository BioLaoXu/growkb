#!/usr/bin/env bash
# 工作空间迁移工具：打包 → 在新位置/新机器一键部署
#
# 用法：
#   ws_migrate.sh pack [-o <out.tar.gz>]                 # 打包整个工作空间（默认输出到上级目录）
#   ws_migrate.sh deploy <tar.gz> --to <目标目录> [--remap 旧前缀=新前缀 ...]
#
# 例：
#   ws_migrate.sh pack                                   # → ../workspace-migrate-20261027.tar.gz
#   ws_migrate.sh deploy ../workspace-migrate-20261027.tar.gz --to /data/Agent/colleague/workspace
#   ws_migrate.sh deploy xx.tar.gz --to ~/ws --remap /data/Report=/data/Report2
#
# 行为：
#   pack    打全量（含 .git 历史与 .kb 知识库；排除 .ws/backup 与 __pycache__）
#   deploy  解包到目标目录 → （可选）重映射生产路径前缀：重建 .source/input.* 软链、
#           改写 .meta.yaml/.project.yaml 里的 source_dir → 跑 ws_index + ws_check 验证
#
# 说明：管理脚本零绝对路径（WS_ROOT 按脚本位置推导），换目录天然可用；
#       同一台服务器换目录直接 mv 即可，无需本工具。

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

cmd="${1:-}"; shift || true

do_pack() {
  local out=""
  while getopts ":o:h" opt; do
    case "$opt" in
      o) out="$OPTARG" ;;
      h) usage_die "用法：ws_migrate.sh pack [-o <out.tar.gz>]" ;;
      *) usage_die "未知参数 -$OPTARG" ;;
    esac
  done
  [[ -n "$out" ]] || out="$(dirname "$WS_ROOT")/$(basename "$WS_ROOT")-migrate-$(today).tar.gz"
  info "打包工作空间 → $out"
  tar czf "$out" -C "$(dirname "$WS_ROOT")" \
      --exclude='.ws/backup' --exclude='__pycache__' --exclude='*.pyc' \
      "$(basename "$WS_ROOT")"
  local size md5 n
  n=$(tar tzf "$out" | wc -l)
  size=$(du -h "$out" | cut -f1)
  md5=$(md5sum "$out" | cut -d' ' -f1)
  cat <<EOF

[完成] 迁移包
  文件：$out
  含 $n 个条目　大小：$size　MD5：$md5
  提醒：包内含业务数据与 git 历史，请通过安全渠道传给接收方。
EOF
}

do_deploy() {
  local tarball="" to="" remap=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --to)    to="$2"; shift 2 ;;
      --remap) remap+=("$2"); shift 2 ;;
      -h)      usage_die "用法：ws_migrate.sh deploy <tar.gz> --to <目标目录> [--remap 旧前缀=新前缀 ...]" ;;
      *)       if [[ -z "$tarball" ]]; then tarball="$1"; shift; else usage_die "多余参数：$1"; fi ;;
    esac
  done
  [[ -n "$tarball" && -f "$tarball" ]] || usage_die "必须给存在的 <tar.gz> 与 --to <目标目录>"
  [[ -n "$to" ]] || usage_die "必须给 --to <目标目录>"

  to="${to%/}"
  local parent wsname
  parent="$(dirname "$to")"
  wsname=$(tar tzf "$tarball" | head -1 | cut -d/ -f1)
  [[ -n "$wsname" ]] || die "迁移包为空或损坏"
  mkdir -p "$parent"
  [[ -e "$to" ]] && die "目标目录已存在：$to（请换 --to 或先移走）"

  info "解包 → $parent/$wsname"
  tar xzf "$tarball" -C "$parent"
  [[ "$parent/$wsname" != "$to" ]] && mv "$parent/$wsname" "$to"
  chmod 700 "$to/.kb/.git" 2>/dev/null || true

  # 路径重映射：软链重建 + META 文本替换
  if [[ ${#remap[@]} -gt 0 ]]; then
    local pair from to2 l t newt fixed=0 missing=0
    for pair in "${remap[@]}"; do
      from="${pair%%=*}"; to2="${pair#*=}"
      [[ -n "$from" && -n "$to2" ]] || die "--remap 格式：旧前缀=新前缀"
      info "重映射：$from → $to2"
      while IFS= read -r -d '' l; do
        t=$(readlink "$l")
        case "$t" in
          "$from"/*|"$from")
            newt="$to2${t#"$from"}"
            rm "$l"; ln -s "$newt" "$l"
            if [[ -e "$l" ]]; then fixed=$((fixed+1)); else warn "软链目标不存在：$l -> $newt"; missing=$((missing+1)); fi ;;
        esac
      done < <(find "$to/projects" "$to/scratch" -type l -print0 2>/dev/null)
      grep -rl "$from" --include='.meta.yaml' --include='.project.yaml' "$to/projects" "$to/scratch" 2>/dev/null \
        | while IFS= read -r f; do sed -i "s|$from|$to2|g" "$f"; done
    done
    [[ $missing -gt 0 ]] && warn "有 $missing 个软链目标在新环境不存在——确认生产数据位置后再分析"
  else
    info "未指定 --remap：保留原生产路径（同一台服务器/生产目录未变时正确）"
  fi

  # 验证：用新位置自己的脚本跑
  info "验证（索引 + 体检）"
  bash "$to/.ws/bin/ws_index.sh" >/dev/null
  bash "$to/.ws/bin/ws_check.sh" >/dev/null && echo "  体检通过" || warn "体检有告警，请查看 ws_check.sh 输出"

  cat <<EOF

[完成] 部署到 $to
  收尾清单（人工）：
    1. chown -R <接收用户> $to        # 归属改为接收方账号
    2. git remote 是原作者的 growkb —— 同事需替换为自己的仓库或申请协作者权限：
       git -C $to remote set-url origin git@github.com:<同事>/growkb.git
       git -C $to/.kb remote set-url origin <同上>
    3. 预览服务（可选）：cd $to && nohup python3 -m http.server 8792 >/dev/null 2>&1 &
    4. CodeBuddy 打开新目录 $to（Hook/规则随仓库自带，无需额外配置）
EOF
}

case "$cmd" in
  pack)   do_pack "$@" ;;
  deploy) do_deploy "$@" ;;
  *)      usage_die "用法：ws_migrate.sh pack [-o 输出] | deploy <tar.gz> --to <目录> [--remap 旧=新 ...]" ;;
esac
