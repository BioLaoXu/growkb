#!/usr/bin/env bash
# 一致性校验 + 空间占用体检（只读，不修改任何文件）
#
# 用法：.ws/bin/ws_check.sh
#
# 检查项：
#   1. 项目是否关联到生产目录、软链是否失效
#   2. 任务是否缺 .meta.yaml、done/delivered 是否漏填 methods、是否空目录
#   3. 生产目录中尚未纳入工作空间的新项目
#   4. 各项目磁盘占用（软链不计，验证"不拷贝大文件"是否执行到位）

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

command -v python3 >/dev/null 2>&1 || die "未找到 python3"

python3 - "$WS_ROOT" <<'PY'
import os, re, sys, glob, posixpath, subprocess

ROOT = sys.argv[1]
LISTS = {'methods', 'input', 'output', 'scripts'}
REPORT = "/data/Report"
SIZE_WARN_GB = 2.0


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


def du(path):
    try:
        out = subprocess.run(['du', '-sh', path], capture_output=True, text=True,
                             timeout=120).stdout.split('\t')[0]
        return out.strip()
    except Exception:
        return '?'


def du_bytes(path):
    # 排除交付包：它是 results/ 的压缩副本，计入会把项目体积算成两倍
    try:
        out = subprocess.run(
            ['du', '-s', '--exclude=*.tar.gz', '--exclude=*.zip', path],
            capture_output=True, text=True, timeout=120).stdout.split('\t')[0]
        return int(out.strip())
    except Exception:
        return 0


projects_dir = os.path.join(ROOT, 'projects')
projects = []          # {'year','batch','dir','product','site','source'}
if os.path.isdir(projects_dir):
    for y in sorted(os.listdir(projects_dir)):
        ydir = os.path.join(projects_dir, y)
        if not os.path.isdir(ydir):
            continue
        for b in sorted(os.listdir(ydir)):
            bdir = os.path.join(ydir, b)
            if not os.path.isdir(bdir):
                continue
            pr = {'year': y, 'batch': b, 'dir': bdir, 'product': '', 'site': '', 'source': ''}
        pj = os.path.join(bdir, '.project.yaml')
        if os.path.isfile(pj):
            meta = parse(pj) or {}
            pr['product'] = str(meta.get('product') or '')
            pr['site'] = str(meta.get('site') or '')
            pr['source'] = str(meta.get('source_dir') or '')
            pr['year'] = str(meta.get('year') or '')
        projects.append(pr)

issues = {'link': [], 'meta': [], 'todo': [], 'empty': []}
task_total = 0

for pr in projects:
    b, sdir = pr['batch'], pr['dir']
    link = os.path.join(sdir, '.source')
    if not os.path.islink(link):
        issues['link'].append('%s：无 .source 软链' % b)
    else:
        target = os.readlink(link)
        if not os.path.isdir(target):
            issues['link'].append('%s：.source 指向失效 -> %s' % (b, target))

    for name in sorted(os.listdir(sdir)):
        tdir = os.path.join(sdir, name)
        if not os.path.isdir(tdir) or not re.match(r'^\d{8}_', name):
            continue
        task_total += 1
        rel = 'projects/%s/%s/%s' % (y, b, name)
        meta_path = os.path.join(tdir, '.meta.yaml')
        if not os.path.isfile(meta_path):
            issues['meta'].append('%s：缺 .meta.yaml' % rel)
            continue
        meta = parse(meta_path)
        status = meta.get('status', '?')
        methods = [m for m in meta.get('methods', []) if m and m != 'TODO']
        if status in ('done', 'delivered') and not methods:
            issues['todo'].append('%s：状态 %s 但 methods 未填' % (rel, status))
        if status == 'delivered' and str(meta.get('deliverable', '')) in ('', 'TODO'):
            issues['todo'].append('%s：状态 delivered 但未回填 synced_to' % rel)
        real = [f for f in os.listdir(tdir) if f != '.meta.yaml']
        if not real:
            issues['empty'].append('%s：只有 .meta.yaml，尚未开工' % rel)

print('══════ 工作空间体检报告 ══════')
print('\n[1] 项目关联：共 %d 个项目，%d 个任务' % (len(projects), task_total))
if issues['link']:
    for i in issues['link']:
        print('    ! %s' % i)
else:
    print('    OK 全部项目已关联有效生产目录')

print('\n[2] 元数据完整性')
for key, label in (('meta', '缺 .meta.yaml'), ('todo', '应填未填'), ('empty', '未开工')):
    if issues[key]:
        print('    %s（%d）：' % (label, len(issues[key])))
        for i in issues[key][:10]:
            print('      - %s' % i)
    else:
        print('    OK 无%s' % label)

print('\n[3] 生产目录中未纳入工作空间的项目')
# 依据 .project.yaml 的 product/year/site 精确对账；缺任一字段的项目跳过
known = {}
for pr in projects:
    if not pr['product'] or not pr['site'] or not pr.get('year'):
        continue
    known.setdefault((pr['product'], pr['year']), set()).add(pr['site'])
new_found = 0
if not known:
    print('    （暂无可对账的项目元数据，跳过）')
for (p, y), sites in sorted(known.items()) if known else []:
    for cand in ('%s_project_%s' % (p, y), '%s_%s' % (p, y)):
        base = os.path.join(REPORT, cand)
        if not os.path.isdir(base):
            continue
        missing = [d for d in sorted(os.listdir(base))
                   if os.path.isdir(os.path.join(base, d)) and d not in sites]
        if missing:
            print('    %s（%d 个未纳入）：%s%s' % (
                cand, len(missing), '、'.join(missing[:6]),
                ' …' if len(missing) > 6 else ''))
            new_found += len(missing)
        break
if not new_found:
    print('    OK 已覆盖全部已登记产品/年份下的项目')

print('\n[4] 磁盘占用（软链不计入，阈值 %.1f GB/项目）' % SIZE_WARN_GB)
sized = []
for pr in projects:
    b = du_bytes(pr['dir'])
    if b:
        sized.append((b, pr['batch']))
sized.sort(reverse=True)
for b, name in sized[:8]:
    gb = b / 1024 ** 3
    flag = '  <-- 超阈值，检查是否误拷了大文件' if gb > SIZE_WARN_GB else ''
    print('    %6.1f GB  %s%s' % (gb, name, flag))
if not sized:
    print('    （无占用）')
total = du_bytes(projects_dir) if os.path.isdir(projects_dir) else 0
print('    合计：%.2f GB（不含软链指向的生产数据）' % (total / 1024 ** 3))
print()
PY
