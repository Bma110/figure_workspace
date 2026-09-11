const $ = (sel) => document.querySelector(sel);
const state = { view: 'list', wsCode: null, tree: [], selectedNode: null, showArchived: false };

async function api(path, opts = {}) {
  let r;
  try {
    r = await fetch(path, opts);
  } catch (e) {
    alert('请求失败：无法连接服务器 ' + path); throw e;
  }
  if (!r.ok) {
    let msg = r.status;
    try { const j = await r.json(); if (j.detail) msg += ' ' + j.detail; }
    catch (_) { /* body 非 JSON（如 HTML 错误页）时略过 */ }
    alert('请求失败 ' + msg); throw new Error(msg);
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

async function loadList() {
  const { workspaces } = await api('/api/workspaces');
  $('#view-list').innerHTML = `
    <div class="actions" style="margin-bottom:16px;">
      <button class="btn primary" onclick="newWorkspaceModal()">+ 新建论文工作区</button>
    </div>
    ${workspaces.map(w => `
      <div class="ws-card ${w.archived ? 'archived' : ''}" data-code="${esc(w.code)}">
        <span class="code">${esc(w.code)}</span>
        <b>${esc(w.name)}</b>
        ${w.archived ? '<span class="archived">（已归档）</span>' : ''}
      </div>`).join('') || '<p style="color:#8a97a5">还没有工作区，先新建一个。</p>'}`;
}

window.newWorkspaceModal = async function () {
  const code = prompt('工作区代码（用于文件夹名，如 SA-Osteomyelitis）');
  if (!code) return;
  const name = prompt('显示名称（如 SA 骨髓炎）', code) || code;
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

// ---------------- 看板 ----------------
async function renderWorkspace() {
  const q = state.showArchived ? '?show_archived=1' : '';
  const { workspace } = await api('/api/workspaces/' + encodeURIComponent(state.wsCode) + q);
  state.tree = workspace.tree;
  $('#view-workspace').innerHTML = `
    <div class="ws-head">
      <button class="btn ghost-onlight" onclick="backToList()">← 全部工作区</button>
      <b class="ws-title">${esc(workspace.name)}</b>
      <span class="ws-code">${esc(workspace.code)}</span>
      <span class="spacer"></span>
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

window.toggleArchivedNode = async function (id, next) {
  await api('/api/nodes/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ archived: next }) });
  state.selectedNode = null;
  closeDrawer();
  await renderWorkspace();
};

window.delNode = async function (id) {
  if (!confirm('删除该节点？文件夹会移入 .trash（可找回）。')) return;
  await api('/api/nodes/' + id, { method: 'DELETE' });
  state.selectedNode = null;
  closeDrawer();
  await renderWorkspace();
};

function renderBoard() {
  const el = $('#figGrid');
  if (!el) return;
  const figs = state.tree.filter(n => n.kind === 'figure');
  el.innerHTML = figs.map(cardHtml).join('')
    || '<p class="muted">还没有 Figure，点“新建 Figure”。</p>';
}

function cardHtml(n) {
  return `<div class="fig-card s-${esc(n.status)}${state.selectedNode === n.id ? ' selected' : ''}${n.archived ? ' archived' : ''}"
      onclick="selectNode(${n.id})">
    <div class="row-between">
      <b>${esc(n.label)}${n.title ? ' · ' + esc(n.title) : ''}</b>
      <span>${n.archived ? '<span class="stagged">已隐藏</span> ' : ''}<span class="statchip st-${esc(n.status)}">${ST[n.status] || ''}</span></span>
    </div>
    <div class="fig-thumb">${thumbHtml(n)}</div>
    <div>
      <span class="imp-${esc(n.importance)}">${n.importance === 'key' ? '★' : ''}${IMP[n.importance] || ''}</span>
      ${(n.tags || []).map(t => `<span class="tagchip">${esc(t)}</span>`).join('')}
    </div>
    <div class="card-meta">↑ ${n.file_count} 文件 · ${(n.children || []).length} 面板</div>
  </div>`;
}

function thumbHtml(n) {
  if (!n.preview_rel) return '<span class="muted-sm">无预览（可贴截图）</span>';
  const rel = n.preview_rel.split('/').map(encodeURIComponent).join('/');
  const url = `/api/preview/${encodeURIComponent(state.wsCode)}/${rel}`;
  return `<img src="${url}" alt="" onerror="this.replaceWith(document.createTextNode('预览读取失败'))">`;
}

window.selectNode = async function (id) {
  state.selectedNode = id;
  renderBoard();
  const { node } = await api('/api/nodes/' + id);
  renderDrawer(node);
};

window.newFigureModal = async function () {
  const label = prompt('Figure 标签，如 "Figure 3"（自动建同名文件夹）');
  if (!label) return;
  const title = prompt('标题（可空）') || '';
  await api(`/api/workspaces/${encodeURIComponent(state.wsCode)}/nodes`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'figure', label, title }) });
  await renderWorkspace();
};

// ---------------- 详情抽屉 ----------------
function renderDrawer(n) {
  const dr = $('#drawer');
  dr.classList.remove('hidden');
  const isFig = n.kind === 'figure';
  dr.innerHTML = `
    <div class="row-between">
      <b class="drawer-title">${esc(n.label)}${n.title ? ' · ' + esc(n.title) : ''}</b>
      <button class="btn" onclick="closeDrawer()">✕</button>
    </div>
    <div class="actions">
      <select class="btn" onchange="patchSel(${n.id},'status',this.value)">
        ${Object.entries(ST).map(([k, v]) => `<option value="${k}" ${n.status === k ? 'selected' : ''}>${v}</option>`).join('')}
      </select>
      <select class="btn" onchange="patchSel(${n.id},'importance',this.value)">
        ${Object.entries(IMP).map(([k, v]) => `<option value="${k}" ${n.importance === k ? 'selected' : ''}>${v}</option>`).join('')}
      </select>
      <button class="btn" onclick="previewUpload(${n.id})">贴/传预览图</button>
      <button class="btn" onclick="toggleArchivedNode(${n.id},${n.archived ? 0 : 1})">${n.archived ? '取消隐藏' : '隐藏'}</button>
      <button class="btn danger" onclick="delNode(${n.id})">删除${isFig ? ' Figure' : '面板'}</button>
    </div>
    <div class="fig-thumb">${thumbHtml(n)}</div>
    ${isFig ? `<div class="section-label">面板</div>
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
    <button class="btn" onclick="uploadTo(${n.id})">+ 上传源文件</button>
    <div class="section-label">溯源全链</div>
    <div class="chain">${chainHtml(n)}</div>
    <div class="section-label">备注 · 决策日志</div>
    <div class="log-area">${(n.logs || []).map(l => `<div><b>${esc(l.created_at)}</b> ${esc(l.text)}</div>`).join('') || '<span class="muted-sm">还没有记录</span>'}</div>
    <textarea class="note" id="logText" placeholder="记一条：为什么这张对 / 条件 / 结论依据"></textarea>
    <div class="actions"><button class="btn primary" onclick="addLog(${n.id})">记入日志</button></div>
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

window.closeDrawer = function () { $('#drawer').classList.add('hidden'); };
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
  const label = prompt('面板标签，如 3A');
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
  if (!confirm('删除记录并移入 .trash？')) return;
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

window.previewUpload = function (nid) {
  const input = document.createElement('input');
  input.type = 'file'; input.accept = 'image/*';
  input.onchange = async () => {
    const fd = new FormData(); fd.append('file', input.files[0]);
    await api(`/api/nodes/${nid}/preview`, { method: 'POST', body: fd });
    await refreshNode(nid);
  };
  input.click();
};

// 标签撤销/加标签/删文件：用 data-* + 事件委托，避免把用户输入拼进 onclick 字符串。
$('#drawer').addEventListener('click', (e) => {
  const x = e.target.closest('.tag-x');
  if (x) { e.preventDefault(); delTag(Number(x.dataset.node), x.dataset.tag); return; }
  const add = e.target.closest('[data-add-tag]');
  if (add) { addTag(Number(add.dataset.addTag), prompt('标签名，如 IL6 / SA / microCT')); return; }
  const del = e.target.closest('[data-del-file]');
  if (del) delFile(Number(del.dataset.delFile));
});

// ---------------- 扫描导入 ----------------
window.scanModal = async function () {
  const folder = prompt('要扫描的文件夹完整路径（只读，不动原文件）');
  if (!folder) return;
  const data = await api(`/api/workspaces/${encodeURIComponent(state.wsCode)}/scan`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder_path: folder }) });
  if (!data.images.length) { alert('该目录没有发现图片'); return; }
  const picks = data.images.map(im => ({
    name: im.name,
    label: 'Figure ' + im.name.replace(/\.[^.]+$/, '').replace(/[_\s-]+/g, ' ').trim(),
  }));
  const preview = picks.map(p => `· ${p.name}\n    → ${p.label}`).join('\n');
  if (!confirm(`将各建一个 Figure，并复制该图作预览（源目录不动）：\n\n${preview}\n\n继续？`)) return;
  const res = await api(`/api/workspaces/${encodeURIComponent(state.wsCode)}/scan/import`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder_path: folder, picks }) });
  await renderWorkspace();
  alert(`已导入 ${res.created.length} 个 Figure`);
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

window.exportKind = function (kind) {
  if (!state.wsCode) { alert('先进入一个工作区再导出'); return; }
  const names = { source_data: 'source-data.csv', legend: 'figure-legends.txt',
                  data_availability: 'data-availability.txt' };
  const a = document.createElement('a');
  a.href = `/api/workspaces/${encodeURIComponent(state.wsCode)}/export/${kind}`;
  a.download = names[kind];
  document.body.appendChild(a); a.click(); a.remove();
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
