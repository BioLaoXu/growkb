const S = {planned:['#60a5fa','已建未开工'], wip:['#f59e0b','进行中'],
           blocked:['#ef4444','受阻'], done:['#10b981','已完成'], delivered:['#0ea5e9','已交付']};
let STATE=null, PAGE=1; const PSIZE=15;
let mCb=null;

function toast(msg, err){
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = err ? 'err' : ''; t.style.display = 'block';
  clearTimeout(t._h); t._h = setTimeout(()=>t.style.display='none', 4200);
}
function mOpen(title, body, withInput, cb, okText){
  document.getElementById('mTitle').textContent = title;
  document.getElementById('mBody').textContent = body || '';
  const inp = document.getElementById('mInput');
  inp.style.display = withInput ? 'block' : 'none'; inp.value = '';
  document.getElementById('mOk').textContent = okText || '确定';
  document.getElementById('mask').style.display = 'flex';
  mCb = cb; if (withInput) inp.focus();
}
function mClose(ok){
  const v = document.getElementById('mInput').value;
  document.getElementById('mask').style.display = 'none';
  if (ok && mCb) mCb(v);
  mCb = null;
}
async function post(url, body){
  const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'},
                              body: JSON.stringify(body||{})});
  const j = await r.json();
  toast(j.ok ? (j.note || '完成') : ('失败：' + j.error + (j.log ? '\n' + j.log : '')), !j.ok);
  await load(); return j;
}
async function load(){
  const r = await fetch('/api/state'); STATE = await r.json();
  document.getElementById('time').textContent = '· 刷新于 ' + STATE.server_time;
  const fs = document.getElementById('fStatus'); const cur = fs.value;
  fs.innerHTML = '<option value="">全部状态</option>' +
    Object.keys(S).map(k=>`<option ${cur===k?'selected':''}>${k}</option>`).join('');
  if (PAGE > 1 && filtered().length <= (PAGE-1)*PSIZE) PAGE = 1;
  render();
}
function filtered(){
  const fs = document.getElementById('fStatus').value;
  const q = document.getElementById('fText').value.trim().toLowerCase();
  return STATE.tasks.filter(t =>
    (!fs || t.status === fs) &&
    (!q || [t.task_id,t.batch,t.contract,t.product,t.request].join(' ').toLowerCase().includes(q)));
}
function render(){
  const rows = filtered();
  const pages = Math.max(1, Math.ceil(rows.length / PSIZE));
  if (PAGE > pages) PAGE = pages;
  const slice = rows.slice((PAGE-1)*PSIZE, PAGE*PSIZE);
  const tb = document.querySelector('#tasks tbody'); tb.innerHTML = '';
  for (const t of slice){
    const [c, label] = S[t.status] || ['#9ca3af', t.status];
    const planned = t.status === 'planned';
    tb.insertAdjacentHTML('beforeend', `<tr>
      <td><span class="tag" style="background:${c}">${label}</span></td>
      <td><b>${t.task_id}</b><br><small>${t.rel_path}</small></td>
      <td>${t.batch||'—'}<br><small>${t.contract||'—'}</small></td>
      <td>${t.product||'—'}</td><td><small>${t.updated||'—'}</small></td>
      <td>${t.request||'—'}</td>
      <td>
        ${planned?`<button class="primary" onclick="receipt('${t.rel_path}')">受理</button>`:''}
        <button onclick="editStatus('${t.rel_path}','${t.status}')">改状态</button>
        <button onclick="editField('${t.rel_path}','request','${(t.request||'').replace(/'/g,'')}')">改需求</button>
        ${planned ? `<button class="danger" onclick="del('${t.rel_path}')">删除</button>`:''}
        ${(t.status==='done'||t.status==='wip')?`<button onclick="deliver('${t.rel_path}')">打包+交付</button>`:''}
      </td></tr>`);
  }
  document.getElementById('pager').innerHTML = rows.length > PSIZE ?
    `<button onclick="go(${PAGE-1})" ${PAGE<=1?'disabled':''}>‹ 上一页</button>
     第 ${PAGE} / ${pages} 页（共 ${rows.length} 行）
     <button onclick="go(${PAGE+1})" ${PAGE>=pages?'disabled':''}>下一页 ›</button>` : '';
  document.querySelector('#cards tbody').innerHTML = STATE.cards.map(c =>
    `<tr><td><b>${c.batch||'?'}</b>${c.state==='new'&&STATE.overview.duplicates.includes(c.file)
      ?' <b style="color:#f59e0b">疑似重复</b>':''}<br><small>${c.date||''}</small></td>
     <td>${c.contract||'—'}<br><small>${c.product||'—'}</small></td>
     <td>${(c.request||'详见卡文件').slice(0,90)}</td>
     <td>${c.state==='in-progress'?`<span class="mut">任务已 ${c.task_status}</span>`:''}
       ${c.state!=='in-progress'?`<button class="primary" onclick="accept('${c.file}')">受理</button>`:''}
       <button onclick="ignore('${c.file}')">忽略</button>
       <button onclick="viewCard('${c.file}')">查看</button></td></tr>`).join('')
    || '<tr><td colspan=4 class="mut">收件箱为空</td></tr>';
  const cnt = {}; rows.forEach(t=>cnt[t.status]=(cnt[t.status]||0)+1);
  document.getElementById('count').textContent = `显示 ${slice.length} / 筛选 ${rows.length} / 总 ${STATE.tasks.length}`;
  renderTrash();
  document.getElementById('sum').innerHTML = '汇总（当前筛选）：' +
    Object.keys(S).map(k=>`${S[k][1]} <b>${cnt[k]||0}</b>`).join(' · ') +
    ` · 待受理卡 <b>${STATE.cards.filter(c=>c.state==='new').length}</b>`;
}
function go(p){ PAGE = p; render(); }

function editStatus(task, cur){
  mOpen('修改状态', '任务：' + task, true, v => {
    if (!v || !S[v]) return toast('非法状态：' + v, true);
    post('/api/update', {task, field:'status', value:v});
  }, '保存');
}
function editField(task, field, cur){
  mOpen('修改 ' + field, '任务：' + task, true, v => {
    if (!v) return toast('值不能为空', true);
    post('/api/update', {task, field, value:v});
  }, '保存');
}
function del(task){
  mOpen('删除任务', '将把 ' + task + ' 移入回收站 .trash/（未开工任务；未真删）。请输入 DELETE 确认：',
        true, v => {
    if (v !== 'DELETE') return toast('未输入 DELETE，已取消', true);
    post('/api/delete', {task, confirm:'DELETE'});
  }, '删除');
}
function receipt(task){
  mOpen('受理确认', '将为 ' + task + ' 写受理回执（接单确认；不改任务状态）。', false,
        v => post('/api/receipt', {task}), '受理');
}
function deliver(task){
  mOpen('打包 + 交付', '将对 ' + task + ' 执行 ws_pack.sh 打包并写交付回执（同名包已存在会失败）。', false,
        v => post('/api/deliver', {task}), '执行');
}
function accept(card){
  mOpen('受理信息卡', '将自动建项目/任务（如缺）并写受理回执。', false,
        v => post('/api/accept', {card}), '受理');
}
function ignore(card){
  mOpen('忽略信息卡', '卡将移入 .inbox/ignored/（不受理）。', false,
        v => post('/api/ignore', {card}), '忽略');
}
function viewCard(f){ window.open('/.inbox/' + f); }
function create(f){
  const b = Object.fromEntries(new FormData(f).entries());
  mOpen('创建任务', '批次 ' + b.batch + ' · 产品 ' + b.product +
        (b.site ? ' · site ' + b.site : '') + (b.source_dir ? ' · ' + b.source_dir : ''), false,
        v => { post('/api/create', b); f.reset(); }, '创建');
}
document.getElementById('fStatus').onchange = ()=>{ PAGE=1; render(); };
document.getElementById('fText').oninput = ()=>{ PAGE=1; render(); };
load();

// 模态框按钮接线（此前漏绑导致点击无效）+ 回车确认 / Esc 取消
document.getElementById('mOk').onclick = () => mClose(true);
document.getElementById('mInput').addEventListener('keydown', e => { if (e.key === 'Enter') mClose(true); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') mClose(false); });

// ---------- 回收站 ----------
function renderTrash(){
  const tb = document.querySelector('#trash tbody');
  const items = STATE.trash || [];
  document.getElementById('trashN').textContent = items.length;
  tb.innerHTML = items.map(t =>
    `<tr><td><b>${t.name}</b></td><td><small>${t.origin||'—（手工移入，无原始路径记录）'}</small></td>
     <td><button onclick="trashRestore('${t.name}')">找回</button>
     <button class="danger" onclick="trashPurge('${t.name}')">彻底删除</button></td></tr>`).join('')
    || '<tr><td colspan=3 class="mut">回收站为空</td></tr>';
}
function trashRestore(name){
  mOpen('找回任务', '将把 ' + name + ' 移回原路径（原路径被占用则报错）。', false,
        v => post('/api/trash/restore', {name}), '找回');
}
function trashPurge(name){
  mOpen('彻底删除', '将永久删除 ' + name + '（含全部脚本与结果，不可恢复！）。请输入 DELETE 确认：',
        true, v => {
    if (v !== 'DELETE') return toast('未输入 DELETE，已取消', true);
    post('/api/trash/purge', {name, confirm:'DELETE'});
  }, '永久删除');
}
