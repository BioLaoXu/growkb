#!/usr/bin/env python3
"""MEMEX 记忆条目管理（P1-4.3/4.7）：冲突四操作+双层去重+可解释检索。
输出统一事件契约（P1-6.1/6.4）：{ok, action, is_error, error{message,retriable,next_steps}, data}
子命令：add <条目.yaml> [--update-conflict] / update <id> --set k=v / delete <id> --reason
        search <关键词...> [--scope X] [--use] / list [scope]
"""
import difflib
import glob
import hashlib
import json
import os
import re
import sys
import datetime

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEMDIR = os.path.join(ROOT, '.kb', 'memory')
SUPER = os.path.join(MEMDIR, '.superseded')
try:
    import yaml
except ImportError:
    yaml = None

def contract(action, ok=True, data=None, message='', retriable=False, next_steps=None):
    err = None if ok else {'message': message, 'retriable': retriable,
                           'next_steps': next_steps or []}
    return {'ok': ok, 'action': action, 'is_error': not ok, 'error': err, 'data': data or {}}

def fail(action, message, steps, retriable=True):
    print(json.dumps(contract(action, False, message=message,
                              retriable=retriable, next_steps=steps), ensure_ascii=False))
    sys.exit(0 if retriable else 1)

def load_entry(path):
    if yaml is not None:
        try:
            d = yaml.safe_load(open(path, encoding='utf-8')) or {}
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    d = {}
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^(\w+):\s*(.*?)\s*(?:#.*)?$', line.strip())
        if m and m.group(2) and m.group(2) != 'null':
            d[m.group(1)] = m.group(2)
    return d

def entries():
    out = []
    for p in sorted(glob.glob(os.path.join(MEMDIR, '*.yaml'))):
        d = load_entry(p)
        if d.get('id'):
            d['_path'] = p
            d['_norm'] = re.sub(r'\s+', ' ', str(d.get('content', ''))).lower().strip()
            d['_md5'] = hashlib.md5(d['_norm'].encode()).hexdigest()
            out.append(d)
    return out

def similar(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

def save(path, d):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(yaml.safe_dump(d, allow_unicode=True, sort_keys=False) if yaml
                 else json.dumps(d, ensure_ascii=False, indent=2))

def main():
    if len(sys.argv) < 2:
        fail('usage', '缺少子命令', ['add|update|delete|search|list'], False)
    cmd, args = sys.argv[1], sys.argv[2:]
    os.makedirs(MEMDIR, exist_ok=True)
    today = datetime.date.today().strftime('%Y-%m-%d')

    if cmd == 'add':
        src = args[0] if args else ''
        if not (src and os.path.isfile(src)):
            fail('add', '条目文件不存在：' + src, ['schema 见 .kb/memory/_schema.md'], False)
        e = load_entry(src)
        need = [k for k in ('id', 'type', 'scope', 'trigger', 'content') if not e.get(k)]
        if need:
            fail('add', '缺必填字段：%s' % ','.join(need), ['对照 _schema.md 补齐'], False)
        norm = re.sub(r'\s+', ' ', str(e.get('content'))).lower().strip()
        md5 = hashlib.md5(norm.encode()).hexdigest()
        existing = entries()
        best = max(existing, key=lambda x: similar(norm, x['_norm'])) if existing else None
        if best and best['_md5'] == md5:
            fail('add', '与 %s 完全重复（MD5 命中），NOOP' % best['id'],
                 ['如需修词：ws_memory.py update %s --set content=…' % best['id']], False)
        if best and similar(norm, best['_norm']) >= 0.85 and '--update-conflict' not in args:
            fail('add', '与 %s 语义相似度 %.2f（阈值 0.85），疑似重复' % (best['id'], similar(norm, best['_norm'])),
                 ['UPDATE：ws_memory.py update %s --set content=<新文本>' % best['id'],
                  'DELETE（矛盾）：ws_memory.py delete %s --reason "…"' % best['id'],
                  '确属新知：重跑加 --update-conflict'])
        dst = os.path.join(MEMDIR, os.path.basename(src))
        open(dst, 'w', encoding='utf-8').write(open(src, encoding='utf-8').read())
        note = '强制新增（与 %s 相似度 %.2f）' % (best['id'], similar(norm, best['_norm'])) \
            if best and similar(norm, best['_norm']) >= 0.85 else None
        print(json.dumps(contract('add', data={'id': e['id'], 'file': dst, 'note': note}),
                         ensure_ascii=False))

    elif cmd == 'update':
        tid = args[0] if args else ''
        sets, i = {}, 1
        while i < len(args):
            if args[i] == '--set' and i + 1 < len(args) and '=' in args[i + 1]:
                k, v = args[i + 1].split('=', 1)
                sets[k] = v
                i += 2
            else:
                i += 1
        tgt = next((x for x in entries() if x['id'] == tid), None)
        if not tgt:
            fail('update', '条目不存在：' + tid, ['ws_memory.py list'], False)
        if not sets:
            fail('update', '未提供 --set 字段=值', [], False)
        d = load_entry(tgt['_path'])
        d.update(sets)
        d['last_verified'] = today
        save(tgt['_path'], d)
        print(json.dumps(contract('update', data={'id': tid, 'fields': sorted(sets)}),
                         ensure_ascii=False))

    elif cmd == 'delete':
        tid = args[0] if args else ''
        reason = args[args.index('--reason') + 1] if '--reason' in args else ''
        tgt = next((x for x in entries() if x['id'] == tid), None)
        if not tgt:
            fail('delete', '条目不存在：' + tid, [], False)
        if not reason:
            fail('delete', '矛盾删除必须写 --reason（审计要求）', ['示例：--reason "新口径 ±5kb"'], False)
        os.makedirs(SUPER, exist_ok=True)
        d = load_entry(tgt['_path'])
        d['superseded_reason'] = reason
        d['superseded_at'] = today
        save(os.path.join(SUPER, os.path.basename(tgt['_path'])), d)
        os.remove(tgt['_path'])
        print(json.dumps(contract('delete', data={'id': tid, 'archived': SUPER}),
                         ensure_ascii=False))

    elif cmd == 'search':
        kws = [a for a in args if not a.startswith('--')]
        scope = args[args.index('--scope') + 1] if '--scope' in args else None
        use = '--use' in args
        rows = []
        for x in entries():
            if scope and x.get('scope') != scope:
                continue
            hay = (str(x.get('trigger', '')) + ' ' + str(x.get('content', ''))).lower()
            score = sum(hay.count(k.lower()) * (3 if k.lower() in str(x.get('trigger', '')).lower() else 1)
                        for k in kws)
            if kws and score > 0:
                rows.append((score, x))
        rows.sort(key=lambda r: -r[0])
        if use:
            for sc, x in rows:
                d = load_entry(x['_path'])
                d['hits'] = int(d.get('hits', 0)) + 1
                d['last_verified'] = today
                save(x['_path'], d)
                x['hits'] = d['hits']
        data = [{'id': x['id'], 'type': x.get('type'), 'scope': x.get('scope'),
                 'trigger': x.get('trigger'), 'content': x.get('content'),
                 'hits': x.get('hits', 0), '_score': sc} for sc, x in rows[:10]]
        print(json.dumps(contract('search', data={'matches': data, 'count': len(data)}),
                         ensure_ascii=False))

    elif cmd == 'list':
        scope = args[0] if args and not args[0].startswith('-') else None
        data = [{'id': x['id'], 'type': x.get('type'), 'scope': x.get('scope'),
                 'hits': x.get('hits', 0), 'last_verified': x.get('last_verified')}
                for x in entries() if not scope or x.get('scope') == scope]
        print(json.dumps(contract('list', data={'entries': data, 'count': len(data)}),
                         ensure_ascii=False))
    else:
        fail(cmd, '未知子命令', ['add | update | delete | search | list'], False)

if __name__ == '__main__':
    main()
