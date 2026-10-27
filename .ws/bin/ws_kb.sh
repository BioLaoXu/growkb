#!/usr/bin/env bash
# .kb 知识库管理：index（自动索引）/ check（语法体检）/ new（脚手架）/ sync（GitHub 备份）
#
# 用法：
#   ws_kb.sh index                       # 重建 .kb/.index.md（代码 + CLI + 文档）
#   ws_kb.sh check                       # R parse + py_compile 语法体检（坏代码不得入库）
#   ws_kb.sh new -l R -t annotation -n my_func      # 生成 R 函数脚手架
#   ws_kb.sh new -l python -t qc -n my_mod          # 生成 Python 模块脚手架
#   ws_kb.sh new -l python -c -n my_action          # 生成 CLI 薄壳（-c）
#   ws_kb.sh sync "feat: 说明"           # 规范化 commit + push 到 growkb 私库
#
# 约定：.index.md 自动生成勿手改；提炼入库走 new 脚手架保证合规。

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

KB="$WS_ROOT/.kb"
REMOTE="git@github.com:BioLaoXu/growkb.git"

cmd="${1:-index}"; shift || true

render_tmpl() {  # render_tmpl <tmpl> <NAME> <THEME> <TITLE>
  sed -e "s/{{NAME}}/$2/g" -e "s/{{THEME}}/$3/g" -e "s/{{TITLE}}/$4/g" \
      -e "s/{{DATE}}/$(isodate)/g" "$1"
}

do_index() {
  python3 - "$KB" <<'PY'
import os, re, sys, datetime
kb = sys.argv[1]
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def rel(p):
    return os.path.relpath(p, kb)

rows = {'r': [], 'py': [], 'cli': [], 'docs': []}

def walk(base, exts):
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if not d.startswith('.')]
        for fn in sorted(fns):
            if os.path.splitext(fn)[1] in exts:
                yield os.path.join(dp, fn)

code_r = os.path.join(kb, 'code', 'R')
if os.path.isdir(code_r):
    for p in walk(code_r, {'.R'}):
        theme = os.path.basename(os.path.dirname(p))
        text = open(p, encoding='utf-8').read()
        # Roxygen 块：@title 优先；无标签时取块内第一个非空行作为 title
        title = None
        for rox in re.finditer(r"^#'\s*(.+)$", text, re.M):
            line = rox.group(1).strip()
            if line.startswith('@'):
                if line.startswith('@title'):
                    title = line[len('@title'):].strip()
                continue
            if title is None and line:
                title = line
        n = re.search(r'^(\w+)\s*<-\s*function', text, re.M)
        # 签名提取：括号深度扫描（支持跨行与嵌套括号，如 default = c("a", "b")）
        sig_text = None
        try:
            j = text.find('function', n.start())
            j = text.find('(', j)
            depth, k = 0, j
            while k < len(text):
                if text[k] == '(':
                    depth += 1
                elif text[k] == ')':
                    depth -= 1
                    if depth == 0:
                        sig_text = text[j + 1:k].strip()
                        break
                k += 1
        except Exception:
            pass
        rows['r'].append((n.group(1) if n else fn[:-2], theme,
                          title or '（缺 title）',
                          ' '.join(sig_text.split()) if sig_text else '', rel(p)))

code_py = os.path.join(kb, 'code', 'python')
if os.path.isdir(code_py):
    for p in walk(code_py, {'.py'}):
        theme = os.path.basename(os.path.dirname(p))
        text = open(p, encoding='utf-8').read()
        n = re.search(r'^def\s+(\w+)\s*\(([^)]*)\)', text, re.M)
        d = re.search(r'"""(.*?)"""', text, re.S)
        first = d.group(1).strip().split('\n')[0] if d else '（缺 docstring）'
        rows['py'].append((n.group(1) if n else fn[:-3], theme, first,
                           n.group(2).strip() if n else '', rel(p)))

for lang, sub in (('R', os.path.join(kb, 'cli', 'R')),
                  ('python', os.path.join(kb, 'cli', 'python'))):
    if os.path.isdir(sub):
        for p in walk(sub, {'.R', '.py'}):
            text = open(p, encoding='utf-8').read()
            d = re.search(r'"""(.*?)"""', text, re.S)
            c = re.search(r'^#\s*(kb_\S+.*)$', text, re.M)
            first = (d.group(1).strip().split('\n')[0] if d
                     else (c.group(1) if c else '（缺说明）'))
            rows['cli'].append((os.path.basename(p), lang, first, '', rel(p)))

docs_base = os.path.join(kb, 'docs')
if os.path.isdir(docs_base):
    for p in walk(docs_base, {'.md'}):
        text = open(p, encoding='utf-8').read()
        cat = os.path.basename(os.path.dirname(p))
        fm_batch = fm_tags = ''
        fm = re.match(r'^---\n(.*?)\n---', text, re.S)
        if fm:
            b = re.search(r'^batch:\s*(.+)$', fm.group(1), re.M)
            t = re.search(r'^tags:\s*(.+)$', fm.group(1), re.M)
            fm_batch = b.group(1).strip() if b else ''
            fm_tags = t.group(1).strip() if t else ''
        h1 = re.search(r'^#\s+(.+)$', text, re.M)
        rows['docs'].append((h1.group(1).strip() if h1 else os.path.basename(p)[:-3],
                             cat, fm_tags, fm_batch, rel(p)))

out = ['# .kb 知识库索引（自动生成，勿手改）', '',
       '> 生成时间：%s　检索：grep 关键词命中后读源文件。' % now, '']

def table(title, header, data):
    if not data:
        return
    out.append('## %s' % title)
    out.append('')
    out.append('| ' + ' | '.join(header) + ' |')
    out.append('|' + '---|' * len(header))
    for row in data:
        out.append('| ' + ' | '.join(str(c) for c in row) + ' |')
    out.append('')

table('代码 · R（source 调用）', ['函数', '主题', '说明', '参数签名', '文件'],
      [(r[0], r[1], r[2], '`%s`' % r[3] if r[3] else '—', '`%s`' % r[4]) for r in rows['r']])
table('代码 · Python', ['函数', '主题', '说明', '参数', '文件'],
      [(r[0], r[1], r[2], '`%s`' % r[3] if r[3] else '—', '`%s`' % r[4]) for r in rows['py']])
table('CLI（独立调用）', ['脚本', '语言', '说明', '文件'],
      [(r[0], r[1], r[2], '`%s`' % r[4]) for r in rows['cli']])
table('文档（经验沉淀）', ['标题', '分类', '标签', '批次', '文件'],
      [(r[0], r[1], r[2], r[3], '`%s`' % r[4]) for r in rows['docs']])

with open(os.path.join(kb, '.index.md'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('[INFO] 知识库索引已重建：%s' % rel(os.path.join(kb, '.index.md')))
PY
}

do_check() {
  fail=0; n=0
  while IFS= read -r f; do
    n=$((n + 1))
    if ! Rscript -e "invisible(parse('$f'))" >/dev/null 2>&1; then
      echo "  [FAIL] $f（R parse 失败）"; fail=$((fail + 1))
    fi
  done < <(find "$KB/code/R" "$KB/cli/R" -name '*.R' 2>/dev/null)
  while IFS= read -r f; do
    n=$((n + 1))
    if ! python3 -m py_compile "$f" >/dev/null 2>&1; then
      echo "  [FAIL] $f（py_compile 失败）"; fail=$((fail + 1))
    fi
  done < <(find "$KB/code/python" "$KB/cli/python" -name '*.py' 2>/dev/null)
  if [[ $fail -eq 0 ]]; then
    echo "[OK] 语法体检通过：$n 个文件"
  else
    echo "[ERROR] $fail / $n 个文件体检失败（修复后重跑，坏代码不得入库）"
    exit 1
  fi
}

do_new() {
  local lang="" theme="general" name="" cli=0
  while getopts ":l:t:n:ch" opt; do
    case "$opt" in
      l) lang="$OPTARG" ;;
      t) theme="$OPTARG" ;;
      n) name="$OPTARG" ;;
      c) cli=1 ;;
      h) usage_die "用法：ws_kb.sh new -l R|python -t <主题> -n <名称> [-c 生成CLI]" ;;
      *) usage_die "未知参数 -$OPTARG" ;;
    esac
  done
  [[ "$lang" == "R" || "$lang" == "python" ]] || die "-l 只支持 R 或 python"
  validate_name "$name"
  local tmpl_dir="$WS_ROOT/.ws/templates" title
  title="TODO：一句话标题"
  if [[ $cli -eq 1 ]]; then
    if [[ "$lang" == "R" ]]; then
      local out="$KB/cli/R/kb_${name}.R"
      render_tmpl "$tmpl_dir/kb-cli.R.tmpl" "kb_${name}" "$theme" "$title" > "$out"
    else
      local out="$KB/cli/python/kb_${name}.py"
      render_tmpl "$tmpl_dir/kb-cli.py.tmpl" "kb_${name}" "$theme" "$title" > "$out"
    fi
  else
    if [[ "$lang" == "R" ]]; then
      local out="$KB/code/R/$theme/${name}.R"
      mkdir -p "$(dirname "$out")"
      render_tmpl "$tmpl_dir/kb-function.R.tmpl" "$name" "$theme" "$title" > "$out"
    else
      local out="$KB/code/python/$theme/${name}.py"
      mkdir -p "$(dirname "$out")"
      render_tmpl "$tmpl_dir/kb-function.py.tmpl" "$name" "$theme" "$title" > "$out"
    fi
  fi
  info "脚手架已生成：${out#$WS_ROOT/}（填写后跑 ws_kb.sh check && ws_kb.sh index）"
  do_index
}

do_sync() {
  local msg="${1:-}"
  [[ -d "$KB" ]] || die ".kb 不存在"
  command -v git >/dev/null || die "未安装 git"
  if [[ ! -d "$KB/.git" ]]; then
    git -C "$KB" init -q && git -C "$KB" symbolic-ref HEAD refs/heads/main
    git -C "$KB" remote add origin "$REMOTE"
    info "已初始化 git 仓库并挂载远程：$REMOTE"
  fi
  local nfile
  nfile=$(git -C "$KB" status --porcelain | wc -l)
  # 本地是否领先远端（含远端还没有 main 的情况）
  local ahead=1
  if git -C "$KB" rev-parse -q --verify origin/main >/dev/null 2>&1; then
    ahead=$(git -C "$KB" rev-list --count origin/main..main)
  fi
  if [[ "$nfile" -eq 0 && "$ahead" -eq 0 ]]; then
    info "没有变更需要同步"
    return 0
  fi
  if [[ "$nfile" -gt 0 ]]; then
    [[ -n "$msg" ]] || msg="chore(kb): sync $(isodate)"
    # CHANGELOG 追加（备份记录）
    { echo "## $(isodate) — $msg"; echo "- 变更文件：$nfile"; echo ""; } >> "$KB/CHANGELOG.md"
    git -C "$KB" add -A
    git -C "$KB" commit -q -m "$msg" || die "commit 失败"
    info "已提交：$msg（$nfile 个文件）"
  else
    info "工作区无变更，但本地领先远端 $ahead 个提交，继续推送"
  fi
  # push：捕获输出与退出码，杜绝误报
  local push_out push_rc
  if push_out=$(git -C "$KB" push -u origin main 2>&1); then
    push_rc=0
  else
    push_rc=$?
  fi
  printf '%s\n' "$push_out" | tail -3
  if [[ $push_rc -ne 0 ]]; then
    die "push 失败（exit $push_rc）：最常见原因是 GitHub 上还没有 growkb 私库——
  请在 github.com 手动创建 Private 空仓库 growkb 后重跑 ws_kb.sh sync"
  fi
  # 远端复核：main 分支必须真实存在
  if ! git -C "$KB" ls-remote --exit-code origin refs/heads/main >/dev/null 2>&1; then
    die "push 后远端仍无 main 分支，同步未生效，请检查 growkb 仓库"
  fi
  info "已推送到 growkb 私库（远端 main 已确认）"
}

case "$cmd" in
  index)  do_index ;;
  check)  do_check ;;
  new)    do_new "$@" ;;
  sync)   do_sync "${1:-}" ;;
  *)      usage_die "用法：ws_kb.sh index | check | new -l R|python -t <主题> -n <名称> [-c] | sync \"<msg>\"" ;;
esac
