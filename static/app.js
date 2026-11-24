const $ = (sel) => document.querySelector(sel);
const state = { view: 'list', wsCode: null, tree: [], selectedNode: null, showArchived: false, journal: false, imgVer: null };

async function api(path, opts = {}) {
  let r;
  try {
    r = await fetch(path, opts);
  } catch (e) {
    toast('请求失败：无法连接服务器', 'error'); throw e;
  }
  if (!r.ok) {
    let msg = r.status;
    try { const j = await r.json(); if (j.detail) msg += ' ' + j.detail; }
    catch (_) { /* body 非 JSON（如 HTML 错误页）时略过 */ }
    toast('请求失败 ' + msg, 'error'); throw new Error(msg);
  }
  return r.json();
}

function show(view) {
  ['list','workspace','search','settings'].forEach(v => $('#view-' + v).classList.toggle('hidden', v !== view));
  state.view = view;
}
function esc(s){ return (s==null?'':String(s)).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
const ST = { candidate:'候选', adopted:'已采用', rejected:'已弃用', redo:'待重做' };
const IMP = { key:'关键', normal:'一般', aux:'辅助' };

let pendingResolve = null;
function toast(msg, kind = 'info') {
  let el = document.querySelector('#toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; document.body.appendChild(el); }
  el.textContent = msg;
  el.className = 'toast show ' + kind;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3200);
}
function dialog(html, mount) {
  return new Promise((resolve) => {
    $('#modal').innerHTML = html;
    $('#modal').classList.remove('hidden');
    pendingResolve = resolve;
    mount(resolve);
  });
}
window.askText = function ({ title, hint = '', value = '', placeholder = '' }) {
  return dialog(`
    <div class="modal-card dlg">
      <div class="row-between"><b class="drawer-title">${esc(title)}</b><button class="btn" onclick="closeModal()">✕</button></div>
      ${hint ? `<p class="muted-sm">${esc(hint)}</p>` : ''}
      <input id="dlgInput" class="dlg-input" value="${esc(value)}" placeholder="${esc(placeholder)}">
      <div class="actions dlg-actions">
        <button class="btn" onclick="closeModal()">取消</button>
        <button class="btn primary" id="dlgOk">确定</button>
      </div>
    </div>`, (resolve) => {
    const inp = $('#dlgInput');
    const ok = () => { const v = inp.value.trim(); pendingResolve = null; closeModal(); resolve(v || null); };
    $('#dlgOk').onclick = ok;
    inp.onkeydown = (e) => { if (e.key === 'Enter') ok(); };
    inp.focus(); inp.select();
  });
};
window.askConfirm = function ({ title, message = '', confirmText = '确定', danger = false }) {
  return dialog(`
    <div class="modal-card dlg">
      <b class="drawer-title">${esc(title)}</b>
      ${message ? `<pre class="dlg-msg">${esc(message)}</pre>` : ''}
      <div class="actions dlg-actions">
        <button class="btn" id="dlgNo">取消</button>
        <button class="btn ${danger ? 'danger' : 'primary'}" id="dlgYes">${esc(confirmText)}</button>
      </div>
    </div>`, (resolve) => {
    $('#dlgNo').onclick = () => closeModal();
    $('#dlgYes').onclick = () => { pendingResolve = null; closeModal(); resolve(true); };
    $('#dlgYes').focus();
  });
};
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !$('#modal').classList.contains('hidden')) closeModal();
});

async function loadList() {
  const { workspaces } = await api('/api/workspaces');
  $('#view-list').innerHTML = `
    <div class="actions" style="margin-bottom:16px;">
      <button class="btn primary" onclick="newWorkspaceModal()">+ 新建论文工作区</button>
    </div>
    ${workspaces.map(w => `
      <div class="ws-card ${w.archived ? 'archived' : ''}" data-code="${esc(w.code)}" role="button" tabindex="0">
        <span class="code">${esc(w.code)}</span>
        <b>${esc(w.name)}</b>
        ${w.archived ? '<span class="archived">（已归档）</span>' : ''}
      </div>`).join('') || '<p style="color:#8a97a5">还没有工作区，先新建一个。</p>'}`;
}

window.newWorkspaceModal = async function () {
  const code = await askText({ title: '新建论文工作区', hint: '代码用于文件夹名，如 SA-Osteomyelitis', placeholder: 'SA-Osteomyelitis' });
  if (!code) return;
  const name = (await askText({ title: '显示名称', value: code, placeholder: '如 SA 骨髓炎' })) || code;
  await api('/api/workspaces', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code, name }) });
  await loadList();
};

window.openWorkspace = function (code) {
  if (!code) return;
  state.wsCode = code;
  state.selectedNode = null;
  show('workspace');
  renderWorkspace();
};

// 用 data-code + 事件委托打开工作区，而不是把 code 拼进 onclick 的 JS 字符串：
// code 由 folder_slug 保留中文与撇号，拼字符串会语法错误 / 可注入。
$('#view-list').addEventListener('click', (e) => {
  const card = e.target.closest('.ws-card');
  if (card) openWorkspace(card.dataset.code);
});
$('#view-list').addEventListener('keydown', (e) => {
  const card = e.target.closest('.ws-card');
  if (card && e.key === 'Enter') openWorkspace(card.dataset.code);
});

// ---------------- 看板 ----------------
async function renderWorkspace() {
  const q = state.showArchived ? '?show_archived=1' : '';
  const { workspace } = await api('/api/workspaces/' + encodeURIComponent(state.wsCode) + q);
  state.tree = workspace.tree;
  state.wsName = workspace.name;
  $('#view-workspace').innerHTML = `
    <div class="ws-head">
      <button class="btn-ghost" onclick="backToList()">← 全部工作区</button>
      <b class="ws-title">${esc(workspace.name)}</b>
      <span class="ws-code">${esc(workspace.code)}</span>
      <span class="spacer"></span>
      <button class="btn" onclick="refreshBoard()" title="重新读取数据并刷新所有预览图">↻ 刷新</button>
      <button class="btn" onclick="toggleJournal()">${state.journal ? '卡片视图' : '📰 期刊视图'}</button>
      <button class="btn" onclick="toggleArchived()">${state.showArchived ? '只显示可见' : '显示已隐藏'}</button>
      <button class="btn" onclick="newFigureModal()">+ 新建 Figure</button>
      <button class="btn" onclick="scanModal()">📥 扫描导入</button>
    </div>
    <div id="figGrid" class="fig-grid"></div>`;
  renderBoard();
}

window.toggleArchived = function () {
  state.showArchived = !state.showArchived;
  renderWorkspace();
};

// 重取数据并用时间戳给预览图 URL 换版本，绕过浏览器/磁盘缓存。
window.refreshBoard = async function () {
  state.imgVer = Date.now();
  try {
    if (state.selectedNode) {
      await refreshNode(state.selectedNode);
    } else {
      await renderWorkspace();
    }
  } finally {
    state.imgVer = null;
  }
  toast('已刷新', 'ok');
};

window.toggleJournal = function () {
  state.journal = !state.journal;
  renderWorkspace();
};

window.toggleArchivedNode = async function (id, next) {
  await api('/api/nodes/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ archived: next }) });
  state.selectedNode = null;
  closeDrawer();
  await renderWorkspace();
};

window.delNode = async function (id) {
  if (!await askConfirm({ title: '删除该节点？', message: '文件夹会移入 .trash（可找回）。', confirmText: '删除', danger: true })) return;
  await api('/api/nodes/' + id, { method: 'DELETE' });
  state.selectedNode = null;
  closeDrawer();
  await renderWorkspace();
};

function renderBoard() {
  const el = $('#figGrid');
  if (!el) return;
  const figs = state.tree.filter(n => n.kind === 'figure');
  if (state.journal) {
    el.className = 'journal';
    el.innerHTML = journalHtml(figs);
    return;
  }
  el.className = 'fig-grid';
  el.innerHTML = figs.map(cardHtml).join('')
    || '<p class="muted">还没有 Figure，点“新建 Figure”。</p>';
}

function journalHtml(figs) {
  const count = (s) => figs.filter(f => f.status === s).length;
  const today = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' });
  const head = `
    <header class="j-head">
      <div class="j-running">Figure 工作台 · ${esc(state.wsCode)}</div>
      <h1 class="j-title">${esc(state.wsName || state.wsCode)}</h1>
      <p class="j-dateline">图件状态稿 · 截至 ${esc(today)}</p>
    </header>
    <section class="j-abstract">
      <h2 class="j-h">摘要</h2>
      <p>本稿共 ${figs.length} 幅图。其中已采用 ${count('adopted')} 幅，候选 ${count('candidate')} 幅，待重做 ${count('redo')} 幅，已弃用 ${count('rejected')} 幅。</p>
    </section>`;
  if (!figs.length) return head + '<p class="j-empty">尚无 Figure，点“新建 Figure”开始编排。</p>';
  const entries = figs.map((f) => {
    const subs = (f.children || []).map((c, j) => {
      const letter = String.fromCharCode(97 + j);
      return `<figure class="j-subfig" onclick="event.stopPropagation(); selectNode(${c.id})">
          <div class="j-subframe">${journalThumb(c)}</div>
          <figcaption><span class="j-sub">${letter}</span> <b>${esc(c.label)}</b>${c.title ? '：' + esc(c.title) : ''}</figcaption>
        </figure>`;
    }).join('');
    const subCount = panelCount(f);
    const keywords = (f.tags || []).map(esc).join('；');
    const files = fileTotal(f);
    const source = files
      ? `来源 ${files} 个文件${subCount ? '（含子图）' : ''}`
      : '尚未上传源文件';
    // 主图没有预览、但有子图时，不再留一个空框，直接排子图。
    const mainFrame = f.preview_rel || !subs ? `<div class="j-frame">${journalThumb(f)}</div>` : '';
    return `
      <article class="j-fig s-${esc(f.status)}${state.selectedNode === f.id ? ' selected' : ''}" onclick="selectNode(${f.id})">
        <div class="j-fig-head">
          <span class="j-num">${esc(f.label)}.</span>
          <span class="j-stamp st-${esc(f.status)}">${ST[f.status] || ''}</span>
          ${f.importance === 'key' ? '<span class="j-key">★ 关键</span>' : ''}
          ${f.archived ? '<span class="j-hidden">[已隐藏]</span>' : ''}
        </div>
        ${f.title ? `<h3 class="j-fig-title">${esc(f.title)}</h3>` : ''}
        ${mainFrame}
        ${subs ? `<div class="j-subs" aria-label="子图">${subs}</div>` : ''}
        <p class="j-caption">${f.title ? esc(f.title) + '。' : ''}${source}${keywords ? '。关键词：' + keywords : ''}。</p>
        ${f.note ? `<p class="j-note"><i>图注：</i>${esc(f.note)}</p>` : ''}
        ${f.methods ? `<p class="j-note"><i>统计与方法：</i>${esc(f.methods)}</p>` : ''}
      </article>`;
  }).join('');
  return head + `<section class="j-body"><h2 class="j-h">图件</h2>${entries}</section>`;
}

function cardHtml(n) {
  return `<div class="fig-card s-${esc(n.status)}${state.selectedNode === n.id ? ' selected' : ''}${n.archived ? ' archived' : ''}"
      role="button" tabindex="0" onclick="selectNode(${n.id})" onkeydown="if(event.key==='Enter')selectNode(${n.id})">
    <div class="row-between">
      <b>${esc(n.label)}${n.title ? ' · ' + esc(n.title) : ''}</b>
      <span>${n.archived ? '<span class="badge-hidden">已隐藏</span> ' : ''}<span class="statchip st-${esc(n.status)}">${ST[n.status] || ''}</span></span>
    </div>
    <div class="fig-thumb">${thumbHtml(n)}</div>
    <div>
      <span class="imp-${esc(n.importance)}">${n.importance === 'key' ? '★' : ''}${IMP[n.importance] || ''}</span>
      ${(n.tags || []).map(t => `<span class="tagchip">${esc(t)}</span>`).join('')}
    </div>
    <div class="card-meta">↑ ${fileTotal(n)} 文件 · ${panelCount(n)} 面板</div>
  </div>`;
}

function fileTotal(n) {
  return (n.file_count || 0) + (n.children || []).reduce((sum, c) => sum + fileTotal(c), 0);
}

function panelCount(n) {
  return (n.children || []).reduce((sum, c) => sum + 1 + panelCount(c), 0);
}

function previewUrl(rel, ver) {
  const path = rel.split('/').map(encodeURIComponent).join('/');
  const v = state.imgVer || ver;
  return `/api/preview/${encodeURIComponent(state.wsCode)}/${path}` + (v ? `?v=${encodeURIComponent(v)}` : '');
}

function thumbHtml(n) {
  if (!n.preview_rel) return '<span class="thumb-empty">无预览<small>可粘贴截图</small></span>';
  return `<img src="${previewUrl(n.preview_rel, n.updated_at)}" alt="" onerror="this.replaceWith(document.createTextNode('预览读取失败'))">`;
}

function journalThumb(n) {
  if (!n.preview_rel) return '<span class="j-subempty">暂无预览</span>';
  return `<img src="${previewUrl(n.preview_rel, n.updated_at)}" alt="" onerror="this.replaceWith(document.createTextNode('预览读取失败'))">`;
}

window.selectNode = async function (id) {
  state.selectedNode = id;
  renderBoard();
  const { node } = await api('/api/nodes/' + id);
  renderDrawer(node);
};

// 分段表单：每段是一种期刊图件材料，给出插入提示与填写状态。
const FIG_SLOTS = [
  { key: 'label', name: 'Figure 标签', req: true, hint: '必填。将自动建同名文件夹，如 Figure 3' },
  { key: 'title', name: '图题', hint: '一句话写出这幅图的结论，如“感染后骨破坏加重”' },
  { key: 'note', name: '图注（legend）', area: true, hint: '逐面板说明内容、比例尺、样本量 n 与代表性' },
  { key: 'panels', name: '面板', area: true, hint: '每行一个面板标签，如 3A；建图后作为子节点创建' },
  { key: 'methods', name: '统计与方法', area: true, hint: '检验方法、显著性阈值、n 的定义' },
  { key: 'source', name: '源数据', info: true, hint: '无需在此填写。建图后上传源文件，即进入 SourceData 清单' },
];

window.newFigureModal = function () {
  const slots = FIG_SLOTS.map(s => `
    <div class="ms-slot">
      <div class="ms-head">
        <b>${esc(s.name)}</b>
        <span class="ms-status" data-status="${s.key}"></span>
      </div>
      <div class="muted-sm">${esc(s.hint)}</div>
      ${s.info ? '' : s.area
        ? `<textarea name="${s.key}" rows="${s.key === 'note' ? 3 : 2}"></textarea>`
        : `<input name="${s.key}" placeholder="${s.key === 'label' ? 'Figure 3' : ''}">`}
    </div>`).join('');
  $('#modal').innerHTML = `
    <div class="modal-card ms-form">
      <div class="row-between">
        <b class="drawer-title">新建 Figure · 期刊图件材料</b>
        <button class="btn" onclick="closeModal()">✕</button>
      </div>
      <form id="figForm" oninput="updateSlots()">${slots}</form>
      <div class="actions" style="justify-content:flex-end;">
        <button class="btn" onclick="closeModal()">取消</button>
        <button class="btn primary" onclick="submitFigure()">创建</button>
      </div>
    </div>`;
  $('#modal').classList.remove('hidden');
  updateSlots();
};

window.updateSlots = function () {
  const f = $('#figForm');
  FIG_SLOTS.forEach(s => {
    const el = document.querySelector(`[data-status="${s.key}"]`);
    if (!el) return;
    if (s.info) { el.textContent = '上传后生成'; el.className = 'ms-status'; return; }
    const filled = (f.elements[s.key]?.value || '').trim() !== '';
    el.textContent = filled ? '✓ 已填' : (s.req ? '必填' : '待填');
    el.className = 'ms-status ' + (filled ? 'ok' : (s.req ? 'req' : ''));
  });
};

window.closeModal = function () {
  const r = pendingResolve;
  pendingResolve = null;
  $('#modal').classList.add('hidden');
  $('#modal').innerHTML = '';
  if (r) r(null);
};

window.submitFigure = async function () {
  const f = $('#figForm');
  const v = (k) => (f.elements[k]?.value || '').trim();
  if (!v('label')) { updateSlots(); f.elements.label.focus(); return; }
  const panels = v('panels').split('\n').map(s => s.trim()).filter(Boolean);
  await api(`/api/workspaces/${encodeURIComponent(state.wsCode)}/figures`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label: v('label'), title: v('title'), note: v('note'),
                           methods: v('methods'), panels }) });
  closeModal();
  await renderWorkspace();
};

// ---------------- 详情抽屉 ----------------
function renderDrawer(n) {
  const dr = $('#drawer');
  dr.classList.remove('hidden');
  document.body.classList.add('drawer-open');
  const isFig = n.kind === 'figure';
  dr.innerHTML = `
    <div class="row-between">
      <b class="drawer-title">${esc(n.label)}${n.title ? ' · ' + esc(n.title) : ''}</b>
      <button class="btn" onclick="closeDrawer()">✕</button>
    </div>
    <div class="section-label">状态</div>
    <div class="seg-group" role="radiogroup" aria-label="状态">
      ${Object.entries(ST).map(([k, v]) => `<button class="seg seg-${k}${n.status === k ? ' on' : ''}" role="radio" aria-checked="${n.status === k}" onclick="patchSel(${n.id},'status','${k}')">${v}</button>`).join('')}
    </div>
    <div class="section-label">重要度</div>
    <div class="seg-group" role="radiogroup" aria-label="重要度">
      ${Object.entries(IMP).map(([k, v]) => `<button class="seg${n.importance === k ? ' on' : ''}" role="radio" aria-checked="${n.importance === k}" onclick="patchSel(${n.id},'importance','${k}')">${v}</button>`).join('')}
    </div>
    <div class="actions">
      <button class="btn" onclick="previewUpload(${n.id})">贴/传预览图</button>
      <button class="btn" onclick="toggleArchivedNode(${n.id},${n.archived ? 0 : 1})">${n.archived ? '取消隐藏' : '隐藏'}</button>
    </div>
    <div class="fig-thumb fig-thumb--lg">${thumbHtml(n)}</div>
    ${isFig ? `<div class="section-label">面板（子图）</div>
      <div class="actions">
        ${(n.children || []).map(c => `<button class="btn" onclick="selectNode(${c.id})">${esc(c.label)}</button>`).join('')}
        <button class="btn" onclick="addPanel(${n.id})">+ 面板</button>
      </div>` : ''}
    <div class="section-label">标签</div>
    <div class="actions" id="tagRow">
      ${(n.tags || []).map(t => `<span class="tagchip">${esc(t)}<a href="#" class="tag-x" data-node="${n.id}" data-tag="${esc(t)}">✕</a></span>`).join('')}
      <button class="btn" data-add-tag="${n.id}">+ 标签</button>
    </div>
    <div class="section-label">来源文件</div>
    <div>${(n.files || []).map(fileRow).join('') || '<span class="muted-sm">无</span>'}</div>
    ${isFig && (n.children || []).some(c => fileTotal(c) > 0)
      ? `<p class="muted-sm">子图源文件计入本图：${(n.children || []).map(c => fileTotal(c) > 0 ? `${esc(c.label)}（${fileTotal(c)}）` : '').filter(Boolean).join('、')}。</p>`
      : ''}
    <button class="btn" onclick="uploadTo(${n.id})">+ 上传源文件</button>
    <div class="section-label">溯源全链</div>
    <div class="chain">${chainHtml(n)}</div>
    ${isFig ? `<div class="section-label">图注（legend）</div>
      <textarea class="note" id="noteText" rows="3" placeholder="逐面板说明内容、比例尺、样本量 n 与代表性">${esc(n.note)}</textarea>
      <div class="actions"><button class="btn" onclick="saveField(${n.id},'note','noteText')">保存图注</button></div>
      <div class="section-label">统计与方法</div>
      <textarea class="note" id="methodsText" rows="2" placeholder="检验方法、显著性阈值、n 的定义">${esc(n.methods)}</textarea>
      <div class="actions"><button class="btn" onclick="saveField(${n.id},'methods','methodsText')">保存方法</button></div>` : ''}
    <div class="section-label">备注 · 决策日志</div>
    <div class="log-area">${(n.logs || []).map(l => `<div><b>${esc(l.created_at)}</b> ${esc(l.text)}</div>`).join('') || '<span class="muted-sm">还没有记录</span>'}</div>
    <textarea class="note" id="logText" placeholder="记一条：为什么这张对 / 条件 / 结论依据"></textarea>
    <div class="actions"><button class="btn primary" onclick="addLog(${n.id})">记入日志</button></div>
    <div class="drawer-foot">
      <button class="btn danger" onclick="delNode(${n.id})">删除${isFig ? ' Figure' : '面板'}</button>
      <span class="muted-sm">删除会把文件夹移入 .trash，可找回</span>
    </div>
  `;
}

function fileRow(f) {
  return `<div class="file-row">
    <span>${esc(f.name)}${f.sample_note ? ` <span class="tagchip">${esc(f.sample_note)}</span>` : ''}</span>
    <span>
      <a class="btn small" href="/api/files/${f.id}" download>打开</a>
      <button class="btn small" data-del-file="${f.id}">删</button>
    </span>
  </div>`;
}

function chainHtml(n) {
  const chain = [...(n.ancestors || []), { label: n.label }];
  const files = (n.files || []).map(f => esc(f.name));
  return chain.map(x => esc(x.label)).join(' → ')
    + (files.length ? ' ← ' + files.join(', ') : '');
}

window.closeDrawer = function () {
  $('#drawer').classList.add('hidden');
  document.body.classList.remove('drawer-open');
};

window.saveField = async function (id, field, elId) {
  const value = $('#' + elId).value;
  await api('/api/nodes/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ [field]: value }) });
  await refreshNode(id);
};
window.backToList = function () { closeDrawer(); show('list'); loadList(); };

async function refreshNode(id) {
  await renderWorkspace();
  await selectNode(id);
}

window.patchSel = async function (id, field, value) {
  await api('/api/nodes/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ [field]: value }) });
  await refreshNode(id);
};

window.addPanel = async function (figId) {
  const label = await askText({ title: '新建面板', placeholder: '如 3A' });
  if (!label) return;
  await api(`/api/workspaces/${encodeURIComponent(state.wsCode)}/nodes`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'panel', label, title: '', parent_id: figId }) });
  await refreshNode(figId);
};

window.addLog = async function (nid) {
  const text = ($('#logText').value || '').trim();
  if (!text) return;
  await api(`/api/nodes/${nid}/logs`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
  await refreshNode(nid);
};

window.addTag = async function (nid, tag) {
  const t = (tag || '').trim();
  if (!t) return;
  await api(`/api/nodes/${nid}/tags`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tag: t }) });
  await refreshNode(nid);
};

window.delTag = async function (nid, tag) {
  await api(`/api/nodes/${nid}/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' });
  await refreshNode(nid);
};

window.delFile = async function (fid) {
  if (!await askConfirm({ title: '删除来源文件？', message: '记录会移入 .trash（可找回）。', confirmText: '删除', danger: true })) return;
  await api('/api/files/' + fid, { method: 'DELETE' });
  await refreshNode(state.selectedNode);
};

window.uploadTo = function (nid) {
  const input = document.createElement('input');
  input.type = 'file'; input.multiple = true;
  input.onchange = async () => {
    for (const f of input.files) {
      const fd = new FormData(); fd.append('file', f);
      await api(`/api/nodes/${nid}/files`, { method: 'POST', body: fd });
    }
    await refreshNode(nid);
  };
  input.click();
};

function previewFileName(blob) {
  const sub = (blob.type.split('/')[1] || 'png').replace('jpeg', 'jpg').replace('svg+xml', 'svg');
  return 'clipboard.' + sub;
}

async function uploadPreview(nid, blob) {
  const fd = new FormData();
  fd.append('file', blob, previewFileName(blob));
  await api(`/api/nodes/${nid}/preview`, { method: 'POST', body: fd });
  toast('预览已更新', 'ok');
  await refreshNode(nid);
}

function pickPreviewImage() {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (file) => {
      if (settled) return;
      settled = true;
      document.removeEventListener('paste', onPaste);
      resolve(file || null);
    };
    const onPaste = (e) => {
      const item = [...((e.clipboardData && e.clipboardData.items) || [])]
        .find(i => i.kind === 'file' && i.type.startsWith('image/'));
      if (!item) return;
      const file = item.getAsFile();
      if (!file) return;
      e.preventDefault();
      finish(file);
      closeModal();
    };
    document.addEventListener('paste', onPaste);
    dialog(`
      <div class="modal-card dlg">
        <div class="row-between"><b class="drawer-title">贴/传预览图</b><button class="btn" onclick="closeModal()">✕</button></div>
        <p class="muted-sm">按 Ctrl+V 粘贴剪贴板里的截图，或选择图片文件。</p>
        <div class="paste-zone" id="pasteZone" tabindex="0">在这里按 Ctrl+V 粘贴</div>
        <div class="actions dlg-actions">
          <button class="btn" id="pickFile">选择文件…</button>
          <button class="btn" onclick="closeModal()">取消</button>
        </div>
      </div>`, () => {
      const input = document.createElement('input');
      input.type = 'file'; input.accept = 'image/*';
      input.onchange = () => { if (input.files[0]) { finish(input.files[0]); closeModal(); } };
      $('#pickFile').onclick = () => input.click();
      $('#pasteZone').focus();
    }).then(() => finish(null));
  });
}

// 每次都弹出选择框：Ctrl+V 粘贴 或 选择文件，两条路径始终可选。
window.previewUpload = async function (nid) {
  const file = await pickPreviewImage();
  if (file) await uploadPreview(nid, file);
};

// 标签撤销/加标签/删文件：用 data-* + 事件委托，避免把用户输入拼进 onclick 字符串。
$('#drawer').addEventListener('click', (e) => {
  const x = e.target.closest('.tag-x');
  if (x) { e.preventDefault(); delTag(Number(x.dataset.node), x.dataset.tag); return; }
  const add = e.target.closest('[data-add-tag]');
  if (add) { askText({ title: '添加标签', placeholder: '如 IL6 / SA / microCT' }).then(t => t && addTag(Number(add.dataset.addTag), t)); return; }
  const del = e.target.closest('[data-del-file]');
  if (del) delFile(Number(del.dataset.delFile));
});

// ---------------- 扫描导入 ----------------
window.scanModal = async function () {
  const folder = await askText({ title: '扫描导入', hint: '要扫描的文件夹完整路径（只读，不动原文件）' });
  if (!folder) return;
  const data = await api(`/api/workspaces/${encodeURIComponent(state.wsCode)}/scan`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder_path: folder }) });
  if (!data.images.length) { toast('该目录没有发现图片', 'warn'); return; }
  const picks = data.images.map(im => ({
    name: im.name,
    label: 'Figure ' + im.name.replace(/\.[^.]+$/, '').replace(/[_\s-]+/g, ' ').trim(),
  }));
  const preview = picks.map(p => `· ${p.name}\n    → ${p.label}`).join('\n');
  if (!await askConfirm({ title: `将导入 ${picks.length} 个 Figure`, message: `各建一个 Figure，并复制该图作预览（源目录不动）：\n\n${preview}`, confirmText: '导入' })) return;
  const res = await api(`/api/workspaces/${encodeURIComponent(state.wsCode)}/scan/import`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder_path: folder, picks }) });
  await renderWorkspace();
  const skipped = (res.skipped || []).length;
  toast(`已导入 ${res.created.length} 个 Figure${skipped ? `，跳过 ${skipped} 个重名` : ''}`, 'ok');
};

// ---------------- 全局检索 ----------------
window.doSearch = async function (q) {
  show('search');
  const el = $('#view-search');
  if (!q) { el.innerHTML = ''; return; }
  const { results } = await api('/api/search?q=' + encodeURIComponent(q));
  el.innerHTML = `<h3>“${esc(q)}” 的结果（${results.length}）</h3>`
    + (results.map(r => `
      <div class="ws-card" data-node="${r.node_id ?? ''}" data-ws="${esc(r.workspace_code || '')}">
        <span class="code">${esc(r.type)}</span>
        <b>${esc(r.label)}</b>
        ${r.workspace_code ? `<span class="ws-code">${esc(r.workspace_code)}</span>` : ''}
      </div>`).join('') || '<p class="muted">无结果</p>');
};

$('#view-search').addEventListener('click', (e) => {
  const card = e.target.closest('.ws-card');
  if (!card) return;
  const ws = card.dataset.ws, nid = card.dataset.node;
  if (nid && ws) {
    state.wsCode = ws; state.selectedNode = null;
    show('workspace');
    renderWorkspace().then(() => selectNode(Number(nid)));
  } else if (ws) {
    openWorkspace(ws);
  } else {
    backToList();
  }
});

// ---------------- 设置 / 备份 / 导出 ----------------
window.showSettings = async function () {
  show('settings');
  const info = await api('/api/settings');
  $('#view-settings').innerHTML = `
    <h3>设置</h3>
    <p>工作台根目录：<b>${esc(info.root)}</b></p>
    <p>数据库：<b>${esc(info.db)}</b></p>
    <div class="actions"><button class="btn primary" onclick="doBackup()">💾 立即备份</button></div>
    <div id="backupInfo"></div>
    <div class="section-label">投稿导出（以状态「已采用」的图为准）</div>
    <div class="actions">
      <button class="btn" onclick="exportKind('source_data')">导出 SourceData</button>
      <button class="btn" onclick="exportKind('legend')">导出图注草稿</button>
      <button class="btn" onclick="exportKind('data_availability')">导出数据可得性</button>
    </div>
    <p class="muted-sm">导出针对当前所在工作区${state.wsCode ? `：${esc(state.wsCode)}` : '（请先进入一个工作区）'}</p>`;
};

window.doBackup = async function () {
  const r = await api('/api/backup', { method: 'POST' });
  $('#backupInfo').innerHTML =
    `<p>已备份到 <b>${esc(r.backup_dir)}</b>，清单 ${r.manifest_count} 条。</p>`;
};

window.exportKind = async function (kind) {
  if (!state.wsCode) { toast('先进入一个工作区再导出', 'warn'); return; }
  const names = { source_data: 'source-data.csv', legend: 'figure-legends.txt',
                  data_availability: 'data-availability.txt' };
  try {
    const r = await fetch(`/api/workspaces/${encodeURIComponent(state.wsCode)}/export/${kind}`);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = names[kind];
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast(`已导出 ${names[kind]}`, 'ok');
  } catch (e) {
    toast('导出失败', 'error');
  }
};

// ---------------- 顶栏绑定 ----------------
$('#btnSettings').addEventListener('click', showSettings);
$('#globalSearch').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') doSearch(e.target.value.trim());
});
$('#globalSearch').addEventListener('input', debounce(function () {
  if (!this.value && state.view === 'search') backToList();
}, 300));
function debounce(fn, ms) {
  let t;
  return function (...a) { clearTimeout(t); t = setTimeout(() => fn.apply(this, a), ms); };
}

loadList();
