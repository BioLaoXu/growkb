#!/usr/bin/env bash
# 把任务根的 report.md 渲染成 results/report.html（分析报告，随包交付给客户）
#
# 用法：
#   ws_report.sh -T <task_rel_path>
#
# 约定：
#   - 任务根须有 report.md（骨架见 .ws/templates/report.md.tmpl，复制到任务根后填写）
#   - 图片用相对路径引用 results/ 内文件，如 ![图题](xxx.png)
#   - 报告头（任务/合同/批次/产品/日期/状态）从 .meta.yaml 自动注入，无需手写
#
# 输出：results/report.html（自包含单文件，浏览器直接打开，可打印成 PDF）

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

task_rel=""
while getopts ":T:h" opt; do
  case "$opt" in
    T) task_rel="$OPTARG" ;;
    h) usage_die "用法：ws_report.sh -T <task_rel_path>" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done

task_rel="${task_rel%/}"
task_abs="$WS_ROOT/$task_rel"
[[ -d "$task_abs" ]] || die "任务目录不存在：$task_rel"
meta="$task_abs/.meta.yaml"
[[ -f "$meta" ]] || die "缺少 .meta.yaml：$task_rel"
report_md="$task_abs/report.md"
if [[ ! -f "$report_md" ]]; then
  die "缺少 report.md：$task_rel
  请从骨架开始填写：cp $WS_ROOT/.ws/templates/report.md.tmpl $report_md"
fi

mkdir -p "$task_abs/results"
python3 - "$meta" "$report_md" "$task_abs/results/report.html" <<'PY'
import html
import re
import sys

meta_path, md_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

# ---------- 元数据报告头 ----------
fields = {}
for line in open(meta_path, encoding='utf-8'):
    m = re.match(r'^(\w+):\s*(.*?)\s*(?:#.*)?$', line)
    if m:
        fields[m.group(1)] = m.group(2)

def esc(s):
    return html.escape(str(s), quote=True)

header_items = [
    ('任务', fields.get('id', '—')),
    ('合同号', fields.get('contract', '—')),
    ('批次号', fields.get('project', '—')),
    ('产品', fields.get('product', '—')),
    ('需求批次', fields.get('batch', '—')),
    ('状态', fields.get('status', '—')),
]

# ---------- Markdown → HTML（纯标准库） ----------
def inline(s):
    s = html.escape(s, quote=True)
    s = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s

def render(md_text):
    out, i = [], 0
    lines = md_text.split('\n')
    para = []

    def flush_para():
        if para:
            out.append('<p>%s</p>' % inline(' '.join(para)))
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith('```'):                       # 代码块
            flush_para()
            lang = stripped[3:].strip()
            code, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code.append(lines[i])
                i += 1
            cls = ' class="language-%s"' % esc(lang) if lang else ''
            out.append('<pre><code%s>%s</code></pre>' % (cls, html.escape('\n'.join(code))))
            i += 1
            continue

        m = re.match(r'^(#{1,4})\s+(.*)$', stripped)         # 标题
        if m:
            flush_para()
            lvl = len(m.group(1))
            out.append('<h%d>%s</h%d>' % (lvl + 1, inline(m.group(2)), lvl + 1))
            i += 1
            continue

        if re.match(r'^\|.*\|$', stripped) and i + 1 < len(lines) and \
                re.match(r'^\|[\s:|-]+\|$', lines[i + 1].strip()):   # 表格
            flush_para()
            header = [c.strip() for c in stripped.strip('|').split('|')]
            i += 2
            rows = []
            while i < len(lines) and re.match(r'^\|.*\|$', lines[i].strip()):
                rows.append([c.strip() for c in lines[i].strip().split('|')])
                i += 1
            out.append('<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
                ''.join('<th>%s</th>' % inline(c) for c in header),
                ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c) for c in row)
                        for row in rows)))
            continue

        if re.match(r'^([-*]|\d+\.)\s+', stripped):          # 列表
            flush_para()
            ordered = bool(re.match(r'^\d+\.', stripped))
            items = []
            while i < len(lines) and re.match(r'^([-*]|\d+\.)\s+', lines[i].strip()):
                items.append('<li>%s</li>' % inline(re.sub(r'^([-*]|\d+\.)\s+', '', lines[i].strip())))
                i += 1
            tag = 'ol' if ordered else 'ul'
            out.append('<%s>%s</%s>' % (tag, ''.join(items), tag))
            continue

        if re.match(r'^-{3,}$', stripped):                   # 分隔线
            flush_para()
            out.append('<hr>')
            i += 1
            continue

        if not stripped:
            flush_para()
            i += 1
            continue

        para.append(stripped)
        i += 1
    flush_para()
    return '\n'.join(out)

body = render(open(md_path, encoding='utf-8').read())
head_cells = ''.join('<td><span class="k">%s</span><br>%s</td>' % (esc(k), esc(v)) for k, v in header_items)

CSS = '''
  body{font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
       max-width:860px;margin:0 auto;padding:32px 24px;color:#1f2937;line-height:1.75}
  h1{font-size:1.7em;border-bottom:3px solid #2563eb;padding-bottom:.3em}
  h2{font-size:1.3em;border-bottom:1px solid #d1d5db;padding-bottom:.25em;margin-top:2em}
  h3{font-size:1.1em;margin-top:1.5em}
  table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.92em}
  th,td{border:1px solid #d1d5db;padding:6px 10px;text-align:left;vertical-align:top}
  th{background:#f3f4f6}
  tr:nth-child(even) td{background:#fafafa}
  code{background:#f3f4f6;padding:1px 5px;border-radius:3px;font-size:.9em}
  pre{background:#111827;color:#e5e7eb;padding:14px;border-radius:6px;overflow-x:auto}
  pre code{background:none;color:inherit}
  img{max-width:100%;border:1px solid #e5e7eb;border-radius:4px;margin:8px 0}
  blockquote{border-left:4px solid #93c5fd;margin:1em 0;padding:.2em 1em;color:#4b5563;background:#f8fafc}
  .report-head{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;
               padding:12px 16px;margin:1.2em 0 2em}
  .report-head td{border:none;padding:2px 18px 2px 0;background:none}
  .report-head .k{color:#6b7280;font-size:.85em}
  hr{border:none;border-top:1px solid #d1d5db;margin:2em 0}
  a{color:#2563eb}
  @media print{body{padding:0}h2{page-break-after:avoid}table,pre,img{page-break-inside:avoid}}
'''

html_doc = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>分析报告 - %s</title>
<style>%s</style>
</head>
<body>
<h1>分析报告</h1>
<table class="report-head"><tr>%s</tr></table>
%s
</body>
</html>
''' % (esc(fields.get('id', '')), CSS, head_cells, body)

with open(out_path, 'w', encoding='utf-8') as fh:
    fh.write(html_doc)
print('渲染完成：%s' % out_path)
PY

info "报告已生成：${task_abs#$WS_ROOT/}/results/report.html"
