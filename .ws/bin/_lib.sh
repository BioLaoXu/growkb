#!/usr/bin/env bash
# 工作空间脚手架公共函数库（被 bin/ 下各脚本 source，不直接执行）

# 脚本位于 <工作空间>/.ws/bin/，故往上两级才是工作空间根
WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export WS_ROOT

TEMPLATE_DIR="$WS_ROOT/.ws/templates"
PROJECTS_DIR="$WS_ROOT/projects"
SCRATCH_DIR="$WS_ROOT/scratch"

die()  { printf '[ERROR] %s\n' "$*" >&2; exit 1; }
info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }

today()   { date +%Y%m%d; }
isodate() { date +%F; }

# 名称校验：仅允许 a-z 0-9 . _ -，且以字母或数字开头
validate_name() {
  local s="$1" what="${2:-名称}"
  [[ -n "$s" ]] || die "$what 不能为空"
  [[ "$s" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] \
    || die "非法$what '$s'：只允许字母数字及 . _ - ，且首字符为字母或数字"
}

# slug 严格小写
validate_slug() {
  local s="$1"
  validate_name "$s" "任务 slug"
  [[ "$s" =~ ^[a-z0-9][a-z0-9._-]*$ ]] \
    || die "任务 slug '$s' 必须为小写（用 - 连接单词，如 peak-anno）"
}

# 由 产品/年份/项目目录名 推导生产目录（<p>_project_<y> 或 <p>_<y> 两种命名都兼容）
resolve_source() {
  local product="$1" year="$2" site="$3"
  local base="/data/Report"
  local cand
  for cand in "${product}_project_${year}" "${product}_${year}"; do
    [[ -d "$base/$cand/$site" ]] && { printf '%s\n' "$base/$cand/$site"; return 0; }
  done
  return 1
}

# 渲染模板：render_template <tmpl文件> <KEY> <VAL> ...
render_template() {
  local tmpl="$1"; shift
  [[ -f "$tmpl" ]] || die "模板不存在：$tmpl"
  local out key val
  out="$(cat "$tmpl")"
  while [[ $# -gt 0 ]]; do
    key="$1"; val="$2"; shift 2
    out="${out//\{\{$key\}\}/$val}"
  done
  printf '%s\n' "$out"
}

# 建立软链（已存在则跳过）
link_if_absent() {
  local target="$1" link="$2"
  if [[ -e "$link" || -L "$link" ]]; then
    info "软链已存在，跳过：${link#$WS_ROOT/}"
    return 0
  fi
  ln -s "$target" "$link" && info "软链：${link#$WS_ROOT/} -> $target"
}

# 从生产项目目录名提取合同主编号（用于跨物种/跨批次聚合）
# demo_batch_mouse      -> demo_batch
# demo_batch_mouse_mouse_B1   -> demo_batch_mouse
# 20260921_demo_batch_SP -> demo_batch_SP
# 20261019_XJYF-cuttag20260910 -> XJYF-cuttag20260910
derive_contract() {
  local site="$1"
  if [[ "$site" =~ (SP[0-9]{5,}) ]];      then printf '%s\n' "${BASH_REMATCH[1]}"; return 0; fi
  if [[ "$site" =~ (XJYF-[A-Za-z0-9]+) ]]; then printf '%s\n' "${BASH_REMATCH[1]}"; return 0; fi
  if [[ "$site" =~ ^[0-9]{8}_(.+)$ ]];     then printf '%s\n' "${BASH_REMATCH[1]}"; return 0; fi
  local first="${site%%_*}"
  if [[ "$first" =~ ^[0-9]{6,}$ ]];        then printf '%s\n' "$first"; return 0; fi
  printf '%s\n' "$site"
}

# 统计目录下已有的任务目录数（<YYYYMMDD>_*），用于推导批次号
count_tasks() {
  local dir="$1" n=0 d
  [[ -d "$dir" ]] || { printf '0\n'; return 0; }
  for d in "$dir"/[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_*; do
    [[ -d "$d" ]] && n=$((n + 1))
  done
  printf '%d\n' "$n"
}

usage_die() { printf '%s\n' "$1" >&2; exit 1; }

# 读取项目级 .project.yaml 的一个字段（文件不存在或字段为空都返回空串）
read_project_field() {
  python3 - "$1" "$2" <<'PYEOF'
import sys
try:
    import yaml
    d = yaml.safe_load(open(sys.argv[1], encoding='utf-8')) or {}
    v = d.get(sys.argv[2])
    print('' if v is None else v)
except Exception:
    print('')
PYEOF
}
