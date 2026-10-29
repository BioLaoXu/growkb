#!/usr/bin/env bash
# 工作空间迁移工具：一条命令换路径 / 交接给同事
#
# 用法：
#   ws_migrate.sh --to <新路径> [--remap 旧前缀=新前缀 ...] [--move]
#       同机换路径：整目录复制到新位置并验证（--move 改为移动，原目录消失）
#   ws_migrate.sh pack [-o <out.tar.gz>]
#       打包全量（含 git 历史与 .kb；排除 backup/pycache），默认输出到上级目录
#   ws_migrate.sh deploy <tar.gz> --to <目标目录> [--remap 旧=新 ...]
#       从迁移包部署（跨机场景的解包端）
#   ws_migrate.sh handover <user@host:~/目标目录> [--remap 旧=新 ...]
#       一键交接：打包 → scp → 远端解包部署 → 远端验证（需 SSH 免密）
#
# 路径绑定说明：管理脚本零绝对路径；仅 .source / input.* 软链与 META 的 source_dir
# 指向生产数据（默认 /data/Report），跨机器且生产数据根变化时用 --remap 重映射。

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

# 复制/移动本体到目标 + 可选路径重映射 + 验证（--to 与 handover 共用）
setup_and_verify() {
  local to="$1"; shift
  local remap=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --remap) remap+=("$2"); shift 2 ;;
      *) shift ;;
    esac
  done
  chmod 700 "$to/.kb/.git" 2>/dev/null || true

  if [[ ${#remap[@]} -gt 0 ]]; then
    local pair from to2 l t newt missing=0
    for pair in "${remap[@]}"; do
      from="${pair%%=*}"; to2="${pair#*=}"
      info "重映射：$from → $to2"
      while IFS= read -r -d '' l; do
        t=$(readlink "$l")
        case "$t" in
          "$from"/*|"$from")
            newt="$to2${t#"$from"}"
            rm "$l"; ln -s "$newt" "$l"
            [[ -e "$l" ]] || { warn "软链目标不存在：$l -> $newt"; missing=$((missing+1)); } ;;
        esac
      done < <(find "$to/projects" "$to/scratch" -type l -print0 2>/dev/null)
      grep -rl "$from" --include='.meta.yaml' --include='.project.yaml' "$to/projects" "$to/scratch" 2>/dev/null \
        | while IFS= read -r f; do sed -i "s|$from|$to2|g" "$f"; done
      [[ $missing -gt 0 ]] && warn "共 $missing 个软链目标在新环境不存在，确认生产数据位置后再分析"
    done
  else
    info "未指定 --remap：保留原生产路径"
  fi

  info "验证（索引 + 体检）"
  bash "$to/.ws/bin/ws_index.sh" >/dev/null
  bash "$to/.ws/bin/ws_check.sh" >/dev/null && echo "  体检通过" || warn "体检有告警，请自行查看"
}

print_checklist() {
  cat <<EOF

[完成] 部署到 $1
  收尾清单（人工）：
    1. chown -R <接收用户> $1
    2. git remote 指向原作者的 growkb —— 同事需换自己的仓库或申请协作权限：
       git -C $1 remote set-url origin git@github.com:<同事>/growkb.git
       git -C $1/.kb remote set-url origin <同上>
    3. 预览服务（可选）：cd $1 && nohup python3 -m http.server 8792 >/dev/null 2>&1 &
    4. CodeBuddy 打开 $1（Hook/规则随仓库自带，无需额外配置）
EOF
}

do_direct() {
  local to="" move=0 remap=()
  # 路径可写作 --to <路径> 或直接位置参数
  if [[ "${1:-}" == "--to" ]]; then to="${2:-}"; shift 2; elif [[ $# -gt 0 ]]; then to="$1"; shift; fi
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --move)  move=1; shift ;;
      --remap) remap+=("$2"); shift 2 ;;
      -h)      usage_die "用法：ws_migrate.sh --to <新路径> [--remap 旧=新 ...] [--move]" ;;
      *)       usage_die "未知参数：$1" ;;
    esac
  done
  [[ -n "$to" ]] || usage_die "必须给 --to <新路径>"
  to="${to%/}"
  [[ "$to" != "$WS_ROOT" && "$to" != "$WS_ROOT/" ]] || die "目标与当前路径相同"
  [[ -e "$to" ]] && die "目标已存在：$to"

  info "复制工作空间 → $to"
  mkdir -p "$(dirname "$to")"
  tar cf - -C "$(dirname "$WS_ROOT")" \
      --exclude='.ws/backup' --exclude='__pycache__' --exclude='*.pyc' \
      "$(basename "$WS_ROOT")" | tar xf - -C "$(dirname "$to")"
  [[ "$(dirname "$to")/$(basename "$WS_ROOT")" != "$to" ]] \
    && mv "$(dirname "$to")/$(basename "$WS_ROOT")" "$to"
  setup_and_verify "$to" ${remap[@]+"${remap[@]}"}
  [[ $move -eq 1 ]] && { info "--move：删除原目录"; rm -rf "$WS_ROOT"; }
  echo "[完成] 新工作空间：$to"
}

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
  echo "[完成] 迁移包：$out（$(tar tzf "$out" | wc -l) 条目，$(du -h "$out" | cut -f1)，MD5 $(md5sum "$out" | cut -d' ' -f1)）"
}

do_deploy() {
  local tarball="" to="" remap=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --to)    to="$2"; shift 2 ;;
      --remap) remap+=("$2"); shift 2 ;;
      -h)      usage_die "用法：ws_migrate.sh deploy <tar.gz> --to <目标目录> [--remap 旧=新 ...]" ;;
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
  [[ -e "$to" ]] && die "目标目录已存在：$to"
  info "解包 → $parent/$wsname"
  tar xzf "$tarball" -C "$parent"
  [[ "$parent/$wsname" != "$to" ]] && mv "$parent/$wsname" "$to"
  setup_and_verify "$to" ${remap[@]+"${remap[@]}"}
  print_checklist "$to"
}

case "${1:-}" in
  --to)      shift; do_direct "$@" ;;
  pack)      shift; do_pack "$@" ;;
  deploy)    shift; do_deploy "$@" ;;
  handover)  shift; do_handover "$@" ;;
  handover)  shift; do_handover "$@" ;;
  *)         usage_die "用法：ws_migrate.sh --to <新路径> | pack | deploy | handover（详见文件头注释）" ;;
esac

# 一键交接：打包 → scp → 远端解包部署 → 远端验证（需已配 SSH 免密）
do_handover() {
  local dest="" remap=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --remap) remap+=("$2"); shift 2 ;;
      -h)      usage_die "用法：ws_migrate.sh handover <user@host:~/目标目录> [--remap 旧=新 ...]" ;;
      *)       if [[ -z "$dest" ]]; then dest="$1"; shift; else usage_die "多余参数：$1"; fi ;;
    esac
  done
  [[ -n "$dest" ]] || usage_die "必须给 <user@host:~/目标目录>（需已配 SSH 免密）"
  local host="${dest%%:*}" rdir="${dest#*:}"
  command -v ssh >/dev/null && command -v scp >/dev/null || die "需要 ssh/scp"

  local tmp
  tmp=$(mktemp /tmp/ws-handover-XXXXXX.tar.gz)
  bash "$0" pack -o "$tmp" >/dev/null
  info "传输 → $dest"
  scp -q "$tmp" "$host:/tmp/$(basename "$tmp")"
  info "远端解包部署"
  ssh "$host" "mkdir -p '$(dirname "$rdir")'"
  ssh "$host" "tar xzf '/tmp/$(basename "$tmp")' -C '$(dirname "$rdir")'"
  ssh "$host" "cd '$rdir' && bash .ws/bin/ws_index.sh >/dev/null && bash .ws/bin/ws_check.sh >/dev/null && echo '远端验证通过'"
  ssh "$host" "rm -f '/tmp/$(basename "$tmp")'"
  print_checklist "$rdir"
}
