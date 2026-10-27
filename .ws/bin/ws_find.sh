#!/usr/bin/env bash
# 回溯检索：在所有 .meta.yaml 中按关键词/产品/状态查找分析任务
#
# 用法：
#   ws_find.sh "关键词"
#   ws_find.sh -p <product> [-s <status>] [-k methods|request|notes]
# 例：
#   ws_find.sh "motif"
#   ws_find.sh -p cut_tag -s wip
#   ws_find.sh -k methods "ChIPseeker"

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

command -v python3 >/dev/null 2>&1 || die "未找到 python3"

product=""; status=""; field=""; keyword=""

while getopts ":p:s:k:h" opt; do
  case "$opt" in
    p) product="$OPTARG" ;;
    s) status="$OPTARG" ;;
    k) field="$OPTARG" ;;
    h) usage_die "用法：ws_find.sh [\"关键词\"] [-p <product>] [-s <status>] [-k <field>]" ;;
    *) usage_die "未知参数 -$OPTARG" ;;
  esac
done
shift $((OPTIND - 1))
[[ $# -gt 0 ]] && keyword="$1"

case "$field" in
  ""|methods|request|notes|output|scripts|input) ;;
  *) die "-k 字段必须是 methods|request|notes|output|scripts|input（默认全文）" ;;
esac

python3 - "$WS_ROOT" "$product" "$status" "$field" "$keyword" <<'PY'
import os, re, sys

ROOT, product, status, field, keyword = sys.argv[1:6]
LISTS = {'methods', 'input', 'output', 'scripts', 'logs'}


def parse(path):
    data = {}
    cur_list = None
    block = None
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        if not line.strip():
            continue
        if block is not None:
            if line[:1] in (' ', '\t'):
                data[block] = (data.get(block, '') + ' ' + line.strip()).strip()
                continue
            block = None
        m = re.match(r'^([A-Za-z_]\w*):\s*(.*)$', line)
        if m and not line[:1].isspace():
            k, v = m.group(1), m.group(2).strip()
            cur_list = None
            if v in ('>-', '|', '>', '|-'):
                data[k] = ''
                block = k
            elif v == '':
                data[k] = []
                cur_list = k
            else:
                data[k] = v
            continue
        m2 = re.match(r'^\s*-\s+(.*)$', line)
        if m2 and cur_list and isinstance(data.get(cur_list), list):
            data[cur_list].append(m2.group(1).strip())
    for k in LISTS:
        data.setdefault(k, [])
    return data


def flat(d):
    if field:
        v = d.get(field, [])
        return ' '.join(v) if isinstance(v, list) else str(v)
    parts = [str(v) for v in d.values() if not isinstance(v, list)]
    parts += [' '.join(v) for v in d.values() if isinstance(v, list)]
    return ' '.join(parts)


hits = []
for base in (os.path.join(ROOT, 'projects'), os.path.join(ROOT, 'scratch')):
    if not os.path.isdir(base):
        continue
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        if '.meta.yaml' not in filenames:
            continue
        rel = os.path.relpath(dirpath, ROOT)
        meta = parse(os.path.join(dirpath, '.meta.yaml'))
        if product and product not in rel:
            continue
        if status and meta.get('status') != status:
            continue
        if keyword and keyword.lower() not in flat(meta).lower():
            continue
        hits.append((rel, meta))

if not hits:
    cond = []
    if keyword: cond.append('关键词="%s"' % keyword)
    if product: cond.append('产品="%s"' % product)
    if status:  cond.append('状态="%s"' % status)
    print('[INFO] 无匹配结果（%s）' % ('，'.join(cond) or '无条件'))
    sys.exit(0)

print('[INFO] 命中 %d 个任务：\n' % len(hits))
for rel, meta in sorted(hits):
    ms = [m for m in meta.get('methods', []) if m and m != 'TODO']
    print('%s  [%s]' % (rel, meta.get('status', '?')))
    print('    methods : %s' % ('；'.join(ms) if ms else '—'))
    print('    request : %s' % re.sub(r'\s+', ' ', str(meta.get('request', '')))[:120])
    if meta.get('deliverable') != 'TODO' and isinstance(meta.get('deliverable'), dict):
        pass
    print('')
PY
