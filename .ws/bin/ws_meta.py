#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作空间元数据解析与扫描 —— 索引与任务受理共用同一份事实。

只依赖标准库（yaml 可用时用它，缺失时回退内置解析器），Python >= 3.8。
被 ws_index.py（生成 .index.md）与 ws_receipt.sh（回执）共同使用，
保证「看板数字」与「目录里的 .meta.yaml」永远一致。
"""

import os
import re

LISTS = ('methods', 'input', 'output', 'scripts')
STATUS_ORDER = {'wip': 0, 'blocked': 1, 'planned': 2, 'done': 3, 'delivered': 4}

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _minimal_parse(path):
    """YAML 库缺失时的兜底解析：标量 + 块列表 + `>-` / `|` 文本块。"""
    data, cur, block = {}, None, None
    with open(path, encoding='utf-8') as fh:
        for raw in fh:
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
                key, val = m.group(1), m.group(2).strip()
                cur = None
                if val in ('>-', '|', '>', '|-'):
                    data[key] = ''
                    block = key
                elif val == '':
                    data[key] = []
                    cur = key
                else:
                    data[key] = val
                continue
            m2 = re.match(r'^\s*-\s+(.*)$', line)
            if m2 and cur and isinstance(data.get(cur), list):
                data[cur].append(m2.group(1).strip())
    return data


def parse_meta(path):
    """解析单个 .meta.yaml，列表字段（methods/output/scripts/input）统一成 list[str]。"""
    if yaml is not None:
        with open(path, encoding='utf-8') as fh:
            data = yaml.safe_load(fh) or {}
    else:
        data = _minimal_parse(path)
    for key in LISTS:
        val = data.get(key)
        if val is None:
            data[key] = []
        elif isinstance(val, str):
            data[key] = [val] if val != 'TODO' else []
        else:
            data[key] = [str(x) for x in val if str(x) != 'TODO']
    return data


def cut(text, n=60):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    return text if len(text) <= n else text[:n - 1] + '…'


def methods_of(task):
    ms = [m for m in task.get('methods') or [] if m]
    return '；'.join(cut(m, 40) for m in ms) if ms else '—'


def scan(root):
    """扫描工作空间。

    返回 (projects, tasks)：
      projects: {project_rel: {project_rel, product, year, site_dir, source_dir,
                               contract, task_count, created_at, updated_at}}
      tasks:    [{task_id, project_rel(无合同为 None), group, rel_path, abs_path,
                  product, year, site, contract, batch, status, request, methods,
                  scripts, output, notes, source_dir, created, updated,
                  packed, synced_to}]
    """
    projects, tasks = {}, []
    for base_name in ('projects', 'scratch'):
        base = os.path.join(root, base_name)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            if '.meta.yaml' not in filenames:
                continue
            meta = parse_meta(os.path.join(dirpath, '.meta.yaml'))
            rel_path = os.path.relpath(dirpath, root)
            group = os.path.relpath(os.path.dirname(dirpath), root)
            # 两级结构：projects/<批次号>/<YYYYMMDD>_<slug>/
            parts = group.split(os.sep)
            is_proj = parts[0] == 'projects' and len(parts) == 3   # projects/<年>/<批次号>
            project_rel = group if is_proj else None
            site = parts[2] if is_proj else None                  # 批次号
            product = meta.get('product') or None                 # 受理时从 .project.yaml 带入
            year = meta.get('year') or None
            deliver = meta.get('deliverable') or {}
            if not isinstance(deliver, dict):
                deliver = {}
            tasks.append({
                'task_id': os.path.basename(dirpath),
                'project_rel': project_rel,
                'group': group,
                'rel_path': rel_path,
                'abs_path': dirpath,
                'product': product,
                'year': year,
                'site': site,
                'contract': meta.get('contract'),
                'batch': meta.get('batch'),
                'sample_batch': meta.get('sample_batch'),
                'species': meta.get('species'),
                'status': meta.get('status') or 'planned',
                'request': meta.get('request') or '',
                'methods': meta.get('methods'),
                'scripts': meta.get('scripts'),
                'output': meta.get('output'),
                'notes': meta.get('notes') or '',
                'source_dir': meta.get('source_dir') or '',
                'created': meta.get('created') or '',
                'updated': meta.get('updated') or '',
                'packed': deliver.get('packed') or '',
                'synced_to': deliver.get('synced_to') or '',
            })
            if project_rel:
                proj = projects.setdefault(project_rel, {
                    'project_rel': project_rel,
                    'product': product,
                    'year': year,
                    'site_dir': meta.get('source_dir') and os.path.basename(str(meta['source_dir']).rstrip('/')) or site,
                    'source_dir': meta.get('source_dir') or '',
                    'contract': meta.get('contract'),
                    'task_count': 0,
                    'created_at': meta.get('created') or '',
                    'updated_at': meta.get('updated') or '',
                })
                proj['task_count'] += 1
                if (meta.get('updated') or '') > (proj['updated_at'] or ''):
                    proj['updated_at'] = meta.get('updated')
                if meta.get('created') and (not proj['created_at'] or meta['created'] < proj['created_at']):
                    proj['created_at'] = meta['created']
    tasks.sort(key=lambda t: (t['group'], STATUS_ORDER.get(t['status'], 9), t['task_id']))
    return projects, tasks


def groups_of(tasks):
    """按 group（项目目录 / scratch 月份）聚合任务。"""
    out = {}
    for task in tasks:
        out.setdefault(task['group'], []).append(task)
    return out


if __name__ == '__main__':
    import json
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    projs, tks = scan(root)
    print(json.dumps({'projects': projs, 'tasks': tks}, ensure_ascii=False, indent=2)[:2000])
