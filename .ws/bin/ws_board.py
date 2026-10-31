#!/usr/bin/env python3
"""ControlTower P2 动态看板服务（单进程双职能，绑定 127.0.0.1）。

  GET  /                看板页（每次请求实时渲染，无生成步骤）
  GET  /api/state       任务/卡片/概览 JSON
  GET  /<静态路径>       工作空间内静态文件（README、.ws/docs…）
  POST /api/create      新建任务（等价 ws_dispatch：建项目如缺 + 建任务 + 回执）
  POST /api/delete      删除任务（仅 planned；移入 .trash/ 回收站，非真删）
  POST /api/accept      受理信息卡
  POST /api/ignore      忽略信息卡
  POST /api/deliver     打包 + 交付回执
写操作仅调用既有 ws_* 脚本（复用全部保护），不引入第二事实源。
"""
import json, os, glob, re, shutil, subprocess, sys, datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, '.ws/bin'))
sys.path.insert(0, os.path.join(ROOT, '.codebuddy/hooks'))
from ws_meta import scan
from check_inbox import parse_card

PORT = 8792
BIND = '127.0.0.1'   # 经 IDE 端口转发访问（工作站 localhost → 服务器）；IP 直连如需开放再改 0.0.0.0
INBOX = os.path.join(ROOT, '.inbox')
TRASH = os.path.join(ROOT, '.trash')
TODAY = datetime.date.today().strftime('%Y%m%d')

def run(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=600)
    tail = (r.stdout + '\n' + r.stderr).strip().splitlines()[-6:]
    return r.returncode, '\n'.join(tail)

def accepted_receipts():
    """从 .outbox 回执反查：哪些任务已写过 accepted 回执。"""
    done = set()
    for p in glob.glob(os.path.join(ROOT, '.outbox', '*_accepted.yaml')):
        m = re.search(r'^taskPath:\s*(.+)$', open(p, encoding='utf-8').read(), re.M)
        if m:
            done.add(m.group(1).strip())
    return done

def scan_tasks():
    _, tasks = scan(ROOT)
    keys = ('task_id','rel_path','project_rel','contract','batch','status',
            'packed','updated','product','species','request','methods')
    out = []
    accepted = accepted_receipts()
    for t in tasks:
        d = {k: t.get(k) for k in keys}
        d['request'] = (d.get('request') or '').replace('\n',' ')[:70]
        d['receipt_accepted'] = (t.get('rel_path') or '') in accepted
        out.append(d)
    return out

def list_cards():
    """收件箱对账：卡对应的任务已存在（任意状态）→ 自动归档到 .inbox/accepted/。

    归档的两种来源：看板 [受理]（即时归档）与 Agent 会话受理（靠本对账补归档）。
    """
    _, tasks = scan(ROOT)
    out, archived = [], []
    for p in sorted(glob.glob(os.path.join(INBOX,'*_dispatch.yaml')), reverse=True):
        c = parse_card(p); c['file'] = os.path.basename(p)
        tp = c.get('taskPath') or ''
        tdir = os.path.join(ROOT, tp) if tp else ''
        st = None
        if tp and os.path.isdir(tdir):
            mp = os.path.join(tdir, '.meta.yaml')
            if os.path.isfile(mp):
                m = re.search(r'^status:\s*(\S+)', open(mp, encoding='utf-8').read(), re.M)
                st = m.group(1) if m else None
        c['task_status'] = st
        # 对账：卡无 taskPath 时按 slug 匹配已有任务（会话受理未归档的情况）
        if not st and c.get('slug') and c.get('batch'):
            # 双匹配：slug 相同 且 卡的批次出现在任务路径里（防同名 slug 的不同批次误归档）
            ms = sorted([t for t in tasks
                         if c['slug'] in (t['task_id'] or '')
                         and c['batch'] in (t['rel_path'] or '')],
                        key=lambda t: t.get('updated') or '', reverse=True)
            if ms:
                tp = ms[0]['rel_path']; st = ms[0]['status']
                c['taskPath'] = tp; c['task_status'] = st
        c['state'] = ('in-progress' if st in ('wip','done','delivered')
                      else 'created' if st == 'planned' else 'new')
        if c['state'] in ('created', 'in-progress'):
            os.makedirs(os.path.join(INBOX,'accepted'), exist_ok=True)
            dst = os.path.join(INBOX,'accepted', c['file'])
            if not os.path.exists(dst):
                os.replace(p, dst); archived.append(c['file'])
            continue   # 已受理的卡不再出现在待受理列表
        out.append(c)
    return out, archived

def overview(tasks, cards):
    st = {}
    for t in tasks: st[t['status']] = st.get(t['status'],0)+1
    new = [c for c in cards if c['state']=='new']
    return {'projects': len({t['project_rel'] for t in tasks if t['project_rel']}),
            'tasks': len(tasks), 'by_status': st,
            'pending_cards': len(new),
            'duplicates': [c['file'] for c in new
                           if sum(1 for x in new if x.get('batch')==c.get('batch')
                                  and x.get('slug')==c.get('slug')) > 1]}

def md2html(md):
    """极简 Markdown→HTML：标题/表格/代码块/列表/引用/粗体/行内码。"""
    import html as H
    def inline(t):
        t = H.escape(t)
        t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
        t = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', t)
        return t
    out, i, lines = [], 0, md.split('\n')
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('```'):
            i += 1; buf = []
            while i < len(lines) and not lines[i].startswith('```'):
                buf.append(lines[i]); i += 1
            i += 1
            out.append('<pre>' + H.escape('\n'.join(buf)) + '</pre>')
            continue
        m = re.match(r'^(#{1,4})\s+(.*)$', ln)
        if m:
            lv = len(m.group(1))
            out.append('<h%d>%s</h%d>' % (lv+1, inline(m.group(2)), lv+1)); i += 1; continue
        if ln.strip().startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                if not re.match(r'^\s*\|?[\s:\-|]+\|?\s*$', lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            out.append('<table>')
            for j, cells in enumerate(rows):
                tag = 'th' if j == 0 else 'td'
                out.append('<tr>' + ''.join('<%s>%s</%s>' % (tag, inline(c), tag) for c in cells) + '</tr>')
            out.append('</table>')
            continue
        if re.match(r'^\s*[-*]\s+', ln):
            items = []
            while i < len(lines) and re.match(r'^\s*[-*]\s+', lines[i]):
                items.append(re.sub(r'^\s*[-*]\s+', '', lines[i])); i += 1
            out.append('<ul>' + ''.join('<li>%s</li>' % inline(x) for x in items) + '</ul>')
            continue
        if ln.strip() == '---':
            out.append('<hr>'); i += 1; continue
        if ln.strip():
            out.append('<p>%s</p>' % inline(ln))
        i += 1
    return '\n'.join(out)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/api/state':
            tasks = scan_tasks(); cards, auto_archived = list_cards()
            ov = overview(tasks, cards); ov['auto_archived'] = auto_archived
            return self._json({'tasks':tasks,'cards':cards,'trash':self.trash_list(),
                               'overview':ov,
                               'server_time':datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        if path == '/api/help':
            hp = os.path.join(ROOT, '.ws/board/help.md')
            md = open(hp, encoding='utf-8').read() if os.path.isfile(hp) else '# 帮助文档缺失'
            return self._json({'html': md2html(md)})
        if path == '/':
            self.path = '/.ws/board/index.html'
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        path = self.path.split('?')[0]
        table = {'/api/create':self.api_create,'/api/update':self.api_update,
                 '/api/delete':self.api_delete,'/api/accept':self.api_accept,
                 '/api/ignore':self.api_ignore,'/api/deliver':self.api_deliver,'/api/receipt':self.api_receipt,
                 '/api/trash/restore':self.api_trash_restore,
                 '/api/trash/purge':self.api_trash_purge}
        fn = table.get(path)
        if not fn: return self._json({'ok':False,'error':'未知接口 '+path},404)
        try:
            n = int(self.headers.get('Content-Length',0))
            body = json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return self._json({'ok':False,'error':'请求体不是合法 JSON'},400)
        try:
            return self._json(fn(body))
        except Exception as e:
            return self._json({'ok':False,'error':'服务器异常：%s' % e},500)

    EDITABLE = ('status','request','notes','species','sample_batch')
    STATUS = ('planned','wip','blocked','done','delivered')

    def api_update(self, b):
        """行内编辑：只允许白名单字段；改 META.yaml（唯一事实）后刷新索引。"""
        tp = (b.get('task') or '').strip('/')
        field = b.get('field'); value = str(b.get('value') or '').strip()
        tdir = os.path.join(ROOT, tp)
        if field not in self.EDITABLE:
            return {'ok':False,'error':'字段不可编辑：'+str(field)}
        if not tp or not os.path.isfile(os.path.join(tdir,'.meta.yaml')):
            return {'ok':False,'error':'任务不存在：'+tp}
        if field == 'status' and value not in self.STATUS:
            return {'ok':False,'error':'非法状态：'+value}
        if not value:
            return {'ok':False,'error':'值不能为空'}
        mp = os.path.join(tdir,'.meta.yaml')
        s = open(mp, encoding='utf-8').read()
        if re.search(r'^%s:' % field, s, re.M):
            s = re.sub(r'^%s:.*$' % field, '%s: %s' % (field, value), s, flags=re.M)
        else:
            s = s.replace('updated:', '%s: %s\nupdated:' % (field, value), 1)
        open(mp,'w',encoding='utf-8').write(s)
        subprocess.run(['bash',ROOT+'/.ws/bin/ws_index.sh'], cwd=ROOT, capture_output=True)
        return {'ok':True,'note':'%s 已更新为 %s' % (field, value)}

    def api_delete(self, b):
        tp = (b.get('task') or '').strip('/')
        tdir = os.path.join(ROOT, tp)
        if not tp or not os.path.isdir(tdir):
            return {'ok':False,'error':'任务不存在：'+str(b.get('task'))}
        if not (tp.startswith('projects/') or tp.startswith('scratch/')):
            return {'ok':False,'error':'路径越界'}
        if b.get('confirm') != 'DELETE':
            return {'ok':False,'error':'安全确认失败：confirm 必须为 DELETE'}
        mp = os.path.join(tdir,'.meta.yaml')
        if not os.path.isfile(mp):
            return {'ok':False,'error':'缺 .meta.yaml，拒绝删除非标准目录'}
        st = re.search(r'^status:\s*(\S+)', open(mp, encoding='utf-8').read(), re.M)
        st = st.group(1) if st else '?'
        if st != 'planned':
            return {'ok':False,'error':'任务状态为 %s（已开工/已交付），不允许删除；'
                    '如需弃用请先人工确认' % st}
        os.makedirs(TRASH, exist_ok=True)
        dst = os.path.join(TRASH, datetime.datetime.now().strftime('%Y%m%d_%H%M%S_') + os.path.basename(tp))
        shutil.move(tdir, dst)
        open(os.path.join(dst, '.origin'), 'w', encoding='utf-8').write(tp)
        subprocess.run(['bash',ROOT+'/.ws/bin/ws_index.sh'], cwd=ROOT, capture_output=True)
        return {'ok':True,'note':'已移入回收站 %s（未真删）' % dst}

    def api_create(self, b):
        for k in ('batch','product'):
            if not b.get(k): return {'ok':False,'error':'缺少 %s' % k}
        if not b.get('site') and not b.get('source_dir'):
            return {'ok':False,'error':'site 与 source_dir 至少一个'}
        args = ['bash', ROOT+'/.ws/bin/ws_dispatch.sh','-b',b['batch'],'-p',b['product']]
        if b.get('site'): args += ['-s',b['site']]
        if b.get('source_dir'): args += ['-f',b['source_dir']]
        if b.get('request'): args += ['-r',b['request']]
        if b.get('slug'): args += ['-t',b['slug']]
        if b.get('date'): args += ['-d',b['date']]
        if b.get('contract'): args += ['-c',b['contract']]
        if b.get('notes'): args += ['-m',b['notes']]
        rc, out = run(args)
        if rc: return {'ok':False,'error':'发起失败','log':out}
        # 补可选字段 species / sample_batch 到新任务 META
        proj_rel = 'projects/%s/%s' % (datetime.date.today().year, b['batch'])
        created = None
        for tdir in sorted(glob.glob(os.path.join(ROOT,proj_rel,'*'+(b.get('slug') or '*'))),
                           key=os.path.getmtime)[-1:]:
            mp = os.path.join(tdir,'.meta.yaml')
            if os.path.isfile(mp):
                s = open(mp, encoding='utf-8').read()
                for k in ('species','sample_batch'):
                    if b.get(k):
                        s = re.sub(r'^%s:.*$' % k, '%s: %s' % (k, b[k]), s, flags=re.M)
                open(mp,'w',encoding='utf-8').write(s)
            created = tdir
        subprocess.run(['bash',ROOT+'/.ws/bin/ws_index.sh'], cwd=ROOT, capture_output=True)
        return {'ok':True,'taskPath':created.replace(ROOT+'/', '') if created else None,
                'note':'任务已创建并生成信息卡'}

    def api_accept(self, b):
        name = os.path.basename(b.get('card') or '')
        card = os.path.join(INBOX, name)
        if not name or not os.path.isfile(card):
            return {'ok':False,'error':'卡文件不存在：'+str(b.get('card'))}
        info = parse_card(card)
        if info.get('task_status') in ('wip','done','delivered'):
            return {'ok':False,'error':'对应任务已 %s，拒绝重复受理' % info['task_status']}
        logs = []
        if not info.get('taskPath') or not os.path.isdir(os.path.join(ROOT, info['taskPath'])):
            for k in ('batch','product'):
                if not info.get(k): return {'ok':False,'error':'卡缺少 %s' % k}
            if not info.get('site') and not info.get('source_dir'):
                return {'ok':False,'error':'卡缺少 site/source_dir'}
            args = ['bash',ROOT+'/.ws/bin/ws_new_project.sh','-b',info['batch'],'-p',info['product']]
            if info.get('year'): args += ['-y',info['year']]
            if info.get('site'): args += ['-s',info['site']]
            if info.get('source_dir'): args += ['-f',info['source_dir']]
            if info.get('contract'): args += ['-c',info['contract']]
            rc,out = run(args); logs.append(out)
            if rc: return {'ok':False,'error':'建项目失败','log':logs}
            args = ['bash',ROOT+'/.ws/bin/ws_new_task.sh','-P','projects/%s/%s' % (info.get('year') or datetime.date.today().year, info['batch'])]
            if info.get('slug'): args += ['-t',info['slug']]
            if info.get('date'): args += ['-d',info['date']]
            args += ['-r', info.get('request') or '（卡内无需求原文，请人工补充）']
            rc,out = run(args); logs.append(out)
            if rc: return {'ok':False,'error':'建任务失败','log':logs}
        tp = info.get('taskPath') or ''
        if not tp:
            # 卡-only：按 建任务输出 定位刚创建的任务（项目目录下 slug 最新匹配）
            proj_rel = 'projects/%s/%s' % (info.get('year') or datetime.date.today().year, info['batch'])
            cand = sorted(glob.glob(os.path.join(ROOT, proj_rel, '*' + (info.get('slug') or ''))),
                          key=os.path.getmtime)
            if cand:
                tp = cand[-1].replace(ROOT + '/', '')
        rc,out = run(['bash',ROOT+'/.ws/bin/ws_receipt.sh','-T',tp,'-s','accepted','-m','看板受理'])
        logs.append(out)
        if rc or not tp:
            return {'ok':False,'error':'受理回执失败'+('（未定位到新任务）' if not tp else ''),'log':logs}
        # 环境预核验（P0-1.2）：结果落盘任务目录，开工提示词直接引用
        try:
            sd = info.get('source_dir') or ''
            if not sd:
                pp = os.path.join(ROOT, os.path.dirname(tp), '.project.yaml')
                if os.path.isfile(pp):
                    mm = re.search(r'^source_dir:\s*(.+?)\s*(?:#.*)?$', open(pp, encoding='utf-8').read(), re.M)
                    sd = mm.group(1).strip().strip(chr(39)).strip(chr(34)) if mm else ''
            env = {'source_dir': sd or None, 'source_dir_exists': bool(sd and os.path.isdir(sd))}
            for rel in ('sample.txt', 'group.txt', 'config.yaml'):
                env[rel] = bool(sd and os.path.isfile(os.path.join(sd, rel)))
            if sd and env['source_dir_exists']:
                try:
                    env['top_entries'] = sorted(os.listdir(sd))[:12]
                except Exception:
                    env['top_entries'] = []
            import datetime as _dt
            env['checked_at'] = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(os.path.join(ROOT, tp, '.env_check.yaml'), 'w', encoding='utf-8') as fh:
                fh.write('# 环境预核验（受理时生成；开工提示词引用）\n')
                for k, v in env.items():
                    fh.write('%s: %s\n' % (k, v))
        except Exception:
            pass
        os.makedirs(os.path.join(INBOX,'accepted'), exist_ok=True)
        os.replace(card, os.path.join(INBOX,'accepted',name))
        return {'ok':True,'taskPath':tp,'note':'受理完成，已写回执与环境预核验','log':logs}

    def api_receipt(self, b):
        """总表 [受理]：对已建任务写 accepted 回执（接单确认，不改状态）。"""
        tp = (b.get('task') or '').strip('/')
        if not tp or not os.path.isfile(os.path.join(ROOT, tp, '.meta.yaml')):
            return {'ok': False, 'error': '任务不存在：' + tp}
        rc, out = run(['bash', ROOT + '/.ws/bin/ws_receipt.sh', '-T', tp,
                       '-s', 'accepted', '-m', '看板受理'])
        if rc:
            return {'ok': False, 'error': '回执写入失败', 'log': out}
        return {'ok': True, 'note': '受理回执已写（' + tp + '）'}

    def api_ignore(self, b):
        name = os.path.basename(b.get('card') or '')
        card = os.path.join(INBOX, name)
        if not name or not os.path.isfile(card):
            return {'ok':False,'error':'卡文件不存在'}
        os.makedirs(os.path.join(INBOX,'ignored'), exist_ok=True)
        os.replace(card, os.path.join(INBOX,'ignored',name))
        return {'ok':True,'note':'已忽略'}

    def trash_list(self):
        out = []
        for d in sorted(glob.glob(os.path.join(TRASH, '*')), reverse=True):
            if not os.path.isdir(d):
                continue
            of = os.path.join(d, '.origin')
            origin = open(of, encoding='utf-8').read().strip() if os.path.isfile(of) else ''
            out.append({'name': os.path.basename(d), 'origin': origin})
        return out

    def api_trash_restore(self, b):
        name = os.path.basename(b.get('name') or '')
        src = os.path.join(TRASH, name)
        of = os.path.join(src, '.origin')
        if not name or not os.path.isdir(src) or not os.path.isfile(of):
            return {'ok': False, 'error': '回收站条目不存在或缺 .origin：' + name}
        origin = open(of, encoding='utf-8').read().strip()
        target = os.path.join(ROOT, origin)
        if os.path.exists(target):
            return {'ok': False, 'error': '原位置已被占用：' + origin}
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(src, target)
        os.remove(of)
        subprocess.run(['bash', ROOT + '/.ws/bin/ws_index.sh'], cwd=ROOT, capture_output=True)
        return {'ok': True, 'note': '已找回至 ' + origin}

    def api_trash_purge(self, b):
        name = os.path.basename(b.get('name') or '')
        src = os.path.join(TRASH, name)
        if not name or not os.path.isdir(src):
            return {'ok': False, 'error': '回收站条目不存在：' + name}
        if b.get('confirm') != 'DELETE':
            return {'ok': False, 'error': '彻底删除不可恢复，confirm 必须为 DELETE'}
        shutil.rmtree(src)
        return {'ok': True, 'note': '已彻底删除 ' + name}

    def api_deliver(self, b):
        tp = (b.get('task') or '').strip('/')
        if not tp or not os.path.isdir(os.path.join(ROOT,tp)):
            return {'ok':False,'error':'任务不存在'}
        rc,out = run(['bash',ROOT+'/.ws/bin/ws_pack.sh','-T',tp])
        if rc: return {'ok':False,'error':'打包失败（同名包已存在或无文件）','log':out}
        rc,out = run(['bash',ROOT+'/.ws/bin/ws_receipt.sh','-T',tp,'-s','delivered','-m','看板交付'])
        if rc: return {'ok':False,'error':'打包成功但回执失败','log':out}
        return {'ok':True,'note':'已打包并写交付回执'}

    def log_message(self, fmt, *args):
        sys.stderr.write('[board] %s\n' % (fmt % args))

if __name__ == '__main__':
    os.chdir(ROOT)
    print('[ControlTower] http://%s:%d  (root=%s)' % (BIND, PORT, ROOT))
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
