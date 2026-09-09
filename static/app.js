const $ = (sel) => document.querySelector(sel);
const state = { view: 'list', wsCode: null, tree: [], selectedNode: null };

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) { const t = await r.text().catch(() => ''); alert('请求失败 ' + r.status + ' ' + t); throw new Error(t); }
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
  show('workspace');
  renderWorkspace(); // Task 11 定义；当前任务点卡片属未接线状态，验收不含该动作
};

// 用 data-code + 事件委托打开工作区，而不是把 code 拼进 onclick 的 JS 字符串：
// code 由 folder_slug 保留中文与撇号，拼字符串会语法错误 / 可注入。
$('#view-list').addEventListener('click', (e) => {
  const card = e.target.closest('.ws-card');
  if (card) openWorkspace(card.dataset.code);
});

loadList();
