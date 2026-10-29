#!/usr/bin/env python3
"""ControlTower 看板生成器：磁盘扫描 → SQLite 派生缓存(board.db) → 静态看板(index.html)。

board.db 是可重建的查询缓存（删除无损，META.yaml 仍是唯一事实）；
index.html 是对 board.db 一次查询的渲染产物。刷新 = 重跑本脚本。
"""
import html, json, os, re, glob, sqlite3, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(ROOT, '.ws/bin'))
sys.path.insert(0, os.path.join(ROOT, '.codebuddy/hooks'))
from ws_meta import scan
from check_inbox import parse_card

BOARD_DIR = os.path.join(ROOT, '.ws/board')
DB = os.path.join(BOARD_DIR, 'board.db')

def collect_cards():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, '.inbox', '*_dispatch.yaml')), reverse=True):
        c = parse_card(p)
        c['file'] = os.path.basename(p)
        tp = c.get('taskPath') or ''
        tdir = os.path.join(ROOT, tp) if tp else ''
        st = None
        if tp and os.path.isdir(tdir):
            mp = os.path.join(tdir, '.meta.yaml')
            if os.path.isfile(mp):
                m = re.search(r'^status:\s*(\S+)', open(mp, encoding='utf-8').read(), re.M)
                st = m.group(1) if m else None
        c['task_status'] = st
        c['state'] = ('in-progress' if st in ('wip', 'done', 'delivered')
                      else 'created' if st == 'planned' else 'new')
        out.append(c)
    for c in out:
        if c['state'] == 'new':
            c['dup'] = sum(1 for x in out if x['state'] == 'new'
                           and x.get('batch') == c.get('batch')
                           and x.get('slug') == c.get('slug')) > 1
    return out

def collect_tasks():
    _, tasks = scan(ROOT)
    keys = ('task_id', 'rel_path', 'project_rel', 'contract', 'batch', 'status',
            'packed', 'updated', 'product', 'species', 'request', 'methods')
    out = []
    for t in tasks:
        d = {k: t.get(k) for k in keys}
        d['request'] = (d.get('request') or '')[:200]
        out.append(d)
    return out

def build_db(tasks, cards):
    os.makedirs(BOARD_DIR, exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    db = sqlite3.connect(DB)
    db.executescript('''
CREATE TABLE tasks(
  taskPath TEXT PRIMARY KEY, taskId TEXT, year TEXT, batch TEXT, projectRel TEXT,
  contractNo TEXT, productName TEXT, speciesName TEXT, sampleBatch TEXT,
  status TEXT, request TEXT, methods TEXT, sourceDir TEXT, packed TEXT, updatedAt TEXT);
CREATE TABLE cards(
  file TEXT PRIMARY KEY, batch TEXT, contract TEXT, product TEXT, slug TEXT,
  date TEXT, request TEXT, taskPath TEXT, taskStatus TEXT, state TEXT, dup INTEGER);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
''')
    for t in tasks:
        year = (t['rel_path'].split('/')[1] if t['rel_path'].startswith('projects/') else None)
        db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            t['rel_path'], t['task_id'], year, t.get('batch'), t.get('project_rel'),
            t.get('contract'), t.get('product'), t.get('species'), None, t.get('status'),
            t.get('request'), json.dumps(t.get('methods'), ensure_ascii=False),
            t.get('source_dir'), t.get('packed'), t.get('updated')))
    for c in cards:
        db.execute('INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?,?,?)', (
            c['file'], c.get('batch'), c.get('contract'), c.get('product'),
            c.get('slug'), c.get('date'), c.get('request'), c.get('taskPath'),
            c.get('task_status'), c['state'], int(bool(c.get('dup')))))
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.executemany('INSERT INTO meta VALUES(?,?)', [
        ('board_version', '1'), ('generated_at', now),
        ('task_count', str(len(tasks))), ('card_count', str(len(cards)))])
    db.commit()
    return db

def render(db):
    tasks = db.execute('SELECT * FROM tasks ORDER BY updatedAt DESC').fetchall()
    tcols = [r[0] for r in db.execute('PRAGMA table_info(tasks)').description] \
        if False else ['taskPath','taskId','year','batch','projectRel','contractNo',
                       'productName','speciesName','sampleBatch','status','request',
                       'methods','sourceDir','packed','updatedAt']
    tasks = [dict(zip(tcols, t)) for t in tasks]
    ccols = ['file','batch','contract','product','slug','date','request',
             'taskPath','taskStatus','state','dup']
    cards = [dict(zip(ccols, c)) for c in
             db.execute('SELECT * FROM cards ORDER BY file DESC').fetchall()]
    meta = dict(db.execute('SELECT key, value FROM meta').fetchall())

    def esc(s):
        return html.escape(str(s if s is not None else '—'))
    def task_row(t, actions):
        st = t['status']; color = {'wip':'#f59e0b','planned':'#60a5fa','blocked':'#ef4444',
                                   'done':'#10b981','delivered':'#10b981'}.get(st, '#9ca3af')
        btns = ''.join('<button onclick="cp(%s)">%s</button>' % (json.dumps(a[1]), a[0]) for a in actions)
        return ('<tr><td><span class="tag" style="background:%s">%s</span></td>'
                '<td><b>%s</b><br><small>%s</small></td><td>%s</td>'
                '<td><small>%s</small></td><td>%s</td></tr>') % (
            color, esc(st), esc(t['taskId']), esc(t['batch']), esc(t['contractNo']),
            esc(t['updatedAt']), esc(t['request']) + btns)

    new = [c for c in cards if c['state'] == 'new']
    created = [c for c in cards if c['state'] == 'created']
    prog = [t for t in tasks if t['status'] in ('wip', 'blocked')]
    planned = [t for t in tasks if t['status'] == 'planned']
    fin = [t for t in tasks if t['status'] in ('done', 'delivered')]

    def card_row(c):
        dup = ' <b style="color:#f59e0b">疑似重复</b>' if c['dup'] else ''
        cmd = 'buddycn chat \\"受理 .inbox/%s\\"' % c['file']
        return ('<tr><td><b>%s</b>%s<br><small>合同 %s · 产品 %s</small></td>'
                '<td><small>%s</small></td><td><small>%s</small></td>'
                '<td><button onclick="cp(%s)">复制受理命令</button>'
                '<button onclick="cp(%s)">scp 投递命令</button></td></tr>') % (
            esc(c['batch']), dup, esc(c['contract']), esc(c['product']),
            esc((c.get('request') or '')[:80]), esc(c['date'] or '—'),
            json.dumps(cmd), json.dumps('bash .ws/bin/ws_dispatch.sh -h  # 或 scp 卡到服务器 .inbox/'))

    def trow_group(rows, actions_fn):
        return ''.join(task_row(t, actions_fn(t)) for t in rows) if rows else ''

    data = json.dumps({'tasks': tasks, 'cards': cards}, ensure_ascii=False)
    page = '''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>ControlTower · 工作空间看板</title><style>
body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#0f172a;color:#e2e8f0;
margin:0;padding:24px;max-width:1100px;margin:0 auto}
h1{font-size:1.5em} h2{font-size:1.1em;margin:28px 0 10px;border-bottom:1px solid #334155;padding-bottom:6px}
.tag{padding:2px 8px;border-radius:4px;font-size:.8em;color:#0f172a}
table{width:100%%;border-collapse:collapse;margin:8px 0}
td,th{padding:8px 10px;border-bottom:1px solid #1e293b;vertical-align:top;text-align:left;font-size:.92em}
small{color:#94a3b8} button{background:#1e293b;color:#93c5fd;border:1px solid #334155;
border-radius:4px;padding:4px 10px;cursor:pointer;font-size:.85em;margin:2px}
button:hover{background:#334155}
.ov{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0}
.ov div{background:#1e293b;border-radius:8px;padding:10px 18px;text-align:center}
.ov b{display:block;font-size:1.6em}
.mut{color:#64748b;font-size:.85em}
</style></head><body>
<h1>🛫 ControlTower · 工作空间看板</h1>
<p class="mut">生成于 %s · 数据源：磁盘 .meta.yaml + .inbox/（board.db 为派生缓存，可随时重建）</p>
<div class="ov">
<div><b>%(np)d</b>待受理卡</div><div><b>%(tasks)d</b>任务</div>
<div><b>%(wip)d</b>进行中</div><div><b>%(done)d</b>已完成/交付</div><div><b>%(proj)d</b>批次项目</div>
</div>
<h2>🔴 待受理（.inbox/）</h2>%(new)s
<h2>🟡 已建未开工（planned）</h2>%(created_table)s
<h2>🟠 进行中（wip/blocked）</h2>%(prog_table)s
<h2>🟢 已完成 / 已交付</h2>%(fin_table)s
<p class="mut">SQL 直查：sqlite3 .ws/board/board.db（表：tasks / cards / meta）</p>
<script>const DATA = %(data)s;
function cp(s){navigator.clipboard.writeText(s).then(()=>alert('已复制：'+s),()=>prompt('手动复制：',s));}</script>
</body></html>''' % dict(
        now=meta['generated_at'], np=len(new), tasks=len(tasks),
        wip=len(prog), done=len(fin),
        proj=len({t['projectRel'] for t in tasks if t['projectRel']}),
        new='<table>' + ''.join(card_row(c) for c in new) + '</table>' if new else '<p class="mut">无待受理卡</p>',
        created_table='<table>' + trow_group(created, lambda t: []) + '</table>',
        prog_table='<table>' + trow_group(prog, lambda t: [
            ('复制开工命令', 'buddycn chat "继续 %s：按 META 推进"' % t['taskPath']),
            ('复制打包命令', 'bash .ws/bin/ws_pack.sh -T %s' % t['taskPath'])]) + '</table>',
        fin_table='<table>' + trow_group(fin, lambda t: [
            ('复制包路径', t['packed'] or '（未打包）')]) + '</table>',
        data=data)

    out = os.path.join(BOARD_DIR, 'index.html')
    open(out, 'w', encoding='utf-8').write(page)
    print('[完成] 看板已生成：%s' % out)
    print('  任务 %d · 待受理卡 %d · 缓存 %s' % (len(tasks), len(new), DB))

def main():
    tasks = collect_tasks()
    cards = collect_cards()
    db = build_db(tasks, cards)
    render(db)
    db.close()

if __name__ == '__main__':
    main()
