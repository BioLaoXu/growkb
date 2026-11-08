#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作空间元数据解析与扫描 —— 索引与任务受理共用同一份事实。

只依赖标准库（yaml 可用时用它，缺失时回退内置解析器），Python >= 3.8。
被 ws_index.py（生成 .index.md）与 ws_receipt.sh（回执）共同使用，
保证「看板数字」与「目录里的 .meta.yaml」永远一致。
"""

import os
import re
from typing import Any, Dict, List  # noqa: E402

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


def legacy_summary(root=None):
    import json as _json
    root = root or os.getcwd()
    projs, tks = scan(root)
    print(_json.dumps({'projects': projs, 'tasks': tks}, ensure_ascii=False, indent=2)[:2000])

# ================= P1-03 并发安全层（flock + 原子替换 + rev 乐观锁，移植自专家方案） =================
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def atomic_patch_meta(task_meta_path, updates, expected_rev=None):
    """并发安全的 META 增量修改：flock 排他 + rev 乐观锁 + os.replace 原子落盘。
    updates: {字段: 新值}；expected_rev 不一致时拒绝（返回磁盘最新 rev）。
    rev 计数存 <task>/.meta.rev（首次自动为 0）。"""
    import fcntl
    import tempfile
    task_meta_path = os.path.abspath(task_meta_path)
    tdir = os.path.dirname(task_meta_path)
    lock_path = os.path.join(tdir, '.meta.lock')
    rev_path = os.path.join(tdir, '.meta.rev')
    with open(lock_path, 'w') as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            with open(task_meta_path, encoding='utf-8') as fh:
                text = fh.read()
            cur_rev = 0
            if os.path.exists(rev_path):
                try:
                    cur_rev = int(open(rev_path).read().strip())
                except Exception:
                    cur_rev = 0
            if expected_rev is not None and expected_rev != cur_rev:
                return {'ok': False, 'rev': cur_rev,
                        'error': 'rev 不一致（磁盘=%d，预期=%d），拒绝覆写' % (cur_rev, expected_rev)}
            for k, v in updates.items():
                k = str(k)
                v = str(v)
                if re.search(r'^%s:' % re.escape(k), text, re.M):
                    text = re.sub(r'^%s:.*$' % re.escape(k), '%s: %s' % (k, v), text, flags=re.M)
                else:
                    text = text.rstrip('\n') + '\n%s: %s\n' % (k, v)
            fd, tmp = tempfile.mkstemp(dir=tdir, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(text)
            os.replace(tmp, task_meta_path)
            with open(rev_path, 'w') as fh:
                fh.write(str(cur_rev + 1))
            return {'ok': True, 'rev': cur_rev + 1, 'updated': sorted(updates)}
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def lock_artifacts_readonly(task_dir):
    """P1-04：done/delivered 产物设为 OS 级只读（report.md + tables/ + figures/ 递归）。"""
    import stat
    locked = []
    targets = [os.path.join(task_dir, 'report.md'),
               os.path.join(task_dir, 'results', 'tables'),
               os.path.join(task_dir, 'results', 'figures')]
    for t in targets:
        if not os.path.exists(t):
            continue
        if os.path.isfile(t):
            mode = os.stat(t).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            os.chmod(t, mode)
            locked.append(os.path.relpath(t, task_dir))
        elif os.path.isdir(t):
            for root, dirs, files in os.walk(t):
                for f in files:
                    fp = os.path.join(root, f)
                    mode = os.stat(fp).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
                    os.chmod(fp, mode)
                    locked.append(os.path.relpath(fp, task_dir))
    return locked


def load_stage_prompt(ws_root, new_status):
    """P1-01 阶段门控：按新状态回显对应 SOP（stage_accept/wip/report）。"""
    mapping = {'planned': 'stage_accept.md', 'wip': 'stage_wip.md', 'done': 'stage_report.md'}
    rel = mapping.get(new_status)
    p = os.path.join(ws_root, '.ws', 'prompts', rel) if rel else None
    return open(p, encoding='utf-8').read().strip() if p and os.path.isfile(p) else None


def kb_snapshot():
    """P1-12 知识快照：当前 .kb 的 git HEAD（溯源烙印）。"""
    import subprocess
    kb = os.path.join(ROOT, '.kb')
    try:
        r = subprocess.run(['git', '-C', kb, 'rev-parse', '--short', 'HEAD'],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or 'unknown'
    except Exception:
        return 'unknown'


def seal_task(task_dir, grade=None, no_memory=False):
    """收尾封印：status=done（原子）+ 产物只读 + 知识快照 + 回显阶段 SOP。
    grade<0.8 拒绝封印（评分协议）。附带记忆提炼检查（非阻断警告，P1-4.7b）。"""
    if grade is None or float(grade) < 0.8:
        return {'ok': False,
                'error': '评分协议：grade 缺失或 <0.8，不封印（先完成 report-scoring 自评）'}
    r = atomic_patch_meta(os.path.join(task_dir, '.meta.yaml'),
                          {'status': 'done', 'grade': grade, 'kb_snapshot': kb_snapshot()})
    if not r.get('ok'):
        return r
    locked = lock_artifacts_readonly(task_dir)
    prompt = load_stage_prompt(ROOT, 'done')
    # 记忆提炼检查：本任务是否已有溯源经验（.kb/memory 含 .staging 全域搜任务 id）
    tid = ''
    mp = os.path.join(task_dir, '.meta.yaml')
    if os.path.isfile(mp):
        m = re.search(r'^id:\s*(\S+)', open(mp, encoding='utf-8').read(), re.M)
        tid = m.group(1) if m else ''
    extracted = False
    if tid:
        mem_dir = os.path.join(ROOT, '.kb', 'memory')
        for p2 in glob.glob(os.path.join(mem_dir, '**', '*.yaml'), recursive=True):
            try:
                if tid in open(p2, encoding='utf-8').read():
                    extracted = True
                    break
            except Exception:
                pass
    r2 = {'ok': True, 'rev': r['rev'], 'locked_files': len(locked),
          'kb_snapshot': kb_snapshot(), 'stage_hint': prompt,
          'memory_check': {'source_task': tid, 'extracted': extracted}}
    if not extracted and not no_memory:
        r2['memory_warning'] = ('本任务尚无提炼经验条目——请提炼 0-3 条（ws_memory.py add，'
                                '默认进 staging）或确认确无新经验后加 --no-memory 重跑')
    return r2



def dump_simple_yaml(data: Dict[str, Any]) -> str:
    """零第三方依赖的标准 YAML 序列化器（兼容 PyYAML，若无 PyYAML 则使用内置确定性格式）。"""
    try:
        import yaml  # type: ignore
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    except ImportError:
        lines: List[str] = []
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            elif v is None:
                lines.append(f"{k}: null")
            elif isinstance(v, bool):
                lines.append(f"{k}: {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k}: {v}")
            else:
                lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
        return "\n".join(lines) + "\n"


def load_simple_yaml(text: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
        res = yaml.safe_load(text)
        return res if isinstance(res, dict) else {}
    except ImportError:
        out: Dict[str, Any] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if not v or v == "null":
                out[k] = None
            elif v in ("true", "false"):
                out[k] = (v == "true")
            else:
                try:
                    out[k] = json.loads(v)
                except Exception:
                    out[k] = v.strip("'\"")
        return out

if __name__ == '__main__':
    import glob
    import argparse
    ap = argparse.ArgumentParser(description='META 并发安全管理（flock+rev+原子替换）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    pp = sub.add_parser('patch', help='原子增量修改 META 字段')
    pp.add_argument('task')
    pp.add_argument('--set', action='append', default=[], help='KEY=VALUE')
    pp.add_argument('--expected-rev', type=int, default=None)
    sl = sub.add_parser('seal', help='收尾封印：status=done + 产物只读 + 知识快照 + 记忆提炼检查')
    sl.add_argument('task')
    sl.add_argument('--grade', required=True, help='评分协议总分（>=0.8 才允许）')
    sl.add_argument('--no-memory', action='store_true', help='申报本任务确无新经验（跳过提炼警告）')
    sp = sub.add_parser('stage-prompt', help='回显指定状态的阶段 SOP')
    sp.add_argument('status')
    sm = sub.add_parser('summary', help='旧版：输出全空间扫描 JSON')
    sm.add_argument('--root', default=None)
    import json
    a = ap.parse_args()
    if a.cmd == 'patch':
        t = os.path.join(ROOT, a.task) if not os.path.isabs(a.task) else a.task
        upd = dict(x.split('=', 1) for x in a.set)
        print(json.dumps(atomic_patch_meta(t, upd, a.expected_rev), ensure_ascii=False))
    elif a.cmd == 'seal':
        t = os.path.join(ROOT, a.task) if not os.path.isabs(a.task) else a.task
        r = seal_task(t, a.grade, no_memory=a.no_memory)
        r['stage_hint'] = r.pop('stage_hint', None)
        print(json.dumps(r, ensure_ascii=False))
    elif a.cmd == 'stage-prompt':
        print(load_stage_prompt(ROOT, a.status) or '（无对应阶段 SOP）')
    elif a.cmd == 'summary':
        legacy_summary(a.root if hasattr(a, 'root') else None)
