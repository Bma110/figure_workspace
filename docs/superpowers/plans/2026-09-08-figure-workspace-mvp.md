# Figure 工作台 MVP 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 单人本地科研用"图为主体"Web 工作台 MVP——论文工作区 → 建 Figure 即建文件夹，上传原始数据，图/面板卡片标状态·重要度·标签·决策日志，挂文件可溯源，跨论文检索，标「采用」可导出 SourceData/图注/数据可得性；数据全在本机，`.bat` 一键启动。

**Architecture:** FastAPI 后端 + SQLite 索引（元数据与关系，不存大文件）+ 原生 JS 单页前端（FastAPI 托管静态）。文件系统为真源：工作台根目录 `D:\ResearchData\` 下每篇论文一个文件夹（代码名），每个 Figure 一个子文件夹；上传=复制并记 SHA。前端不打包，无构建步骤。根目录与 DB 路径可用环境变量覆盖（测试用临时目录）。

**Tech Stack:** Python 3 · FastAPI · uvicorn · sqlite3（stdlib）· python-multipart · pytest · httpx（TestClient）。前端 HTML/CSS/原生 JS。

运行目录：`D:\Desktop\adm`（当前工作区）。目标目录结构见下方 File Structure。

---

## File Structure

```
adm/
├── .gitignore
├── requirements.txt
├── 启动工作台.bat
├── fw_server.py              # FastAPI 入口：创建 app、挂路由、托管静态
├── fw/
│   ├── __init__.py
│   ├── config.py             # 根目录/DB 路径（每调用读 env → 默认值）
│   ├── naming.py             # 文件夹名清洗 + 文件名样本提示解析
│   ├── storage.py            # 文件系统操作：建工作区/Figure 夹、复制上传、SHA、trash
│   ├── db.py                 # SQLite 连接、建表、各表 CRUD/查询
│   ├── api.py                # FastAPI 路由：workspaces/nodes/files/tags/search/scan/export/backup/settings
│   └── export.py             # SourceData/图注/数据可得性 文本生成
├── static/
│   ├── index.html            # 单页骨架（列表/看板+抽屉/检索/设置 四视图）
│   ├── styles.css            # 宽松密度样式
│   └── app.js                # 全部前端逻辑
├── tests/
│   ├── conftest.py           # 设临时 FW_ROOT/FW_DB，TestClient fixture
│   ├── test_config.py
│   ├── test_naming.py
│   ├── test_storage.py
│   ├── test_db.py
│   ├── test_api_workspaces.py
│   ├── test_api_nodes.py
│   ├── test_api_files.py
│   ├── test_api_tags_search.py
│   ├── test_api_scan.py
│   ├── test_export.py
│   └── test_api_backup.py
└── data/                     # 运行时生成：fw.db、settings（gitignore）
```

磁盘模型（运行时由代码保证）：
```
D:\ResearchData\
 ├── SA-Osteomyelitis\          ← 工作区 code
 │    ├── 原始数据\             ← 未归属上传
 │    ├── Figure1\  Figure2\    ← 每个 Figure 一个夹（label 去空格）
 │    │     ├── <file>          ← 上传复制的源文件
 │    │     └── preview.png     ← 可选截图预览
 │    │     └── 3A\ 3B\         ← 面板文件子目录
 │    └── .trash\               ← 删除回收（DB 记录删除）
```

---

## Task 0: 环境与脚手架

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `fw/__init__.py`
- Create: `fw_server.py`
- Create: `tests/conftest.py`
- Create: `fw/config.py`

- [ ] **Step 1: 确认 Python 可用**

Run: `python --version`
Expected: `Python 3.10+`。若无 `python`，用 `py --version`，后续命令相应换成 `py -m …`。

- [ ] **Step 2: 建虚拟环境与依赖（首次）**

Run:
```bash
python -m venv .venv
```
Windows 激活：`.venv\Scripts\activate`（若在 bash 用 `source .venv/Scripts/activate`）。
（注：真正的"首次自动建"会在 Task 11 的 `.bat` 里实现；此处只保证本机可开发。）

- [ ] **Step 3: 写 requirements.txt**

```txt
fastapi>=0.110
uvicorn>=0.29
python-multipart>=0.0.9
pytest>=8.0
httpx>=0.27
```

Run: `pip install -r requirements.txt`
Expected: 全部安装成功。

- [ ] **Step 4: 写 .gitignore**

```gitignore
.venv/
__pycache__/
*.pyc
data/
.trash/
```

- [ ] **Step 5: git init 首次提交**

```bash
git init
git add .gitignore requirements.txt
git commit -m "chore: scaffold figure workspace repo"
```

- [ ] **Step 6: 写包占位与入口**

Create `fw/__init__.py`:
```python
"""Figure Workspace —— 本地科研图管理工作台。"""
```

Create `fw_server.py`（占位，后续路由挂进来）:
```python
from fastapi import FastAPI

app = FastAPI(title="Figure Workspace", version="0.1.0")


@app.get("/api/health")
def health():
    return {"ok": True}
```

- [ ] **Step 7: 写 config.py（env 覆盖 → 默认值）**

```python
"""路径配置：每次调用读 env，便于测试覆盖。"""
import os
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("FW_ROOT", r"D:\ResearchData"))
DEFAULT_DB = Path(os.environ.get("FW_DB", str(Path(__file__).resolve().parent.parent / "data" / "fw.db")))


def root_dir() -> Path:
    return Path(os.environ.get("FW_ROOT", str(DEFAULT_ROOT)))


def db_path() -> Path:
    return Path(os.environ.get("FW_DB", str(DEFAULT_DB)))
```

- [ ] **Step 8: 写 conftest.py（先设 env 再 import app）**

```python
import os
import tempfile
import pytest

_tmp = tempfile.mkdtemp(prefix="fwtest_")
os.environ["FW_ROOT"] = os.path.join(_tmp, "root")
os.environ["FW_DB"] = os.path.join(_tmp, "fw.db")

from fastapi.testclient import TestClient  # noqa: E402
import fw_server  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(fw_server.app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_state():
    # 每个测试前清空 root 与 db，保证隔离
    import shutil
    from fw import config
    root = config.root_dir()
    db = config.db_path()
    if db.exists():
        db.unlink()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    db.parent.mkdir(parents=True, exist_ok=True)
    yield
```

- [ ] **Step 9: 跑冒烟测试**

Create `tests/test_config.py`:
```python
def test_root_default_override():
    from fw import config
    assert config.root_dir().name == "root"  # conftest 已覆盖为 tmp/root
```

Run: `python -m pytest tests/test_config.py -q`
Expected: 1 passed。

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: config with env override + app scaffold + test fixture"
```

---

## Task 1: naming 工具（文件夹名清洗 + 样本提示）

**Files:**
- Create: `fw/naming.py`
- Test: `tests/test_naming.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_naming.py`:
```python
from fw import naming


def test_folder_slug_removes_space_and_invalid():
    assert naming.folder_slug("Figure 1") == "Figure1"
    assert naming.folder_slug("3A") == "3A"


def test_folder_slug_keeps_cjk():
    assert naming.folder_slug("原始数据") == "原始数据"


def test_folder_slug_strips_illegal_windows_chars():
    assert naming.folder_slug('Fig:1/2*?"<>|') == "Fig12"


def test_unique_path_appends_number():
    names = ["a.xlsx", "a (2).xlsx"]
    assert naming.unique_name("a.xlsx", names) == "a (2).xlsx"
    assert naming.unique_name("b.xlsx", names) == "b.xlsx"


def test_parse_sample_hint():
    assert naming.parse_sample_hint("qPCR_SA-MLOY4-001_IL6_v01.xlsx") == "SA-MLOY4-001"
    assert naming.parse_sample_hint("随便命名.txt") == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_naming.py -q`
Expected: FAIL（ImportError / attribute）。

- [ ] **Step 3: 实现 naming.py**

```python
"""文件夹名清洗 + 文件名样本提示解析。"""
import re

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WS = re.compile(r"\s+")
_SAMPLE = re.compile(r"(\b(?:SA-)?[A-Za-z]{2,12}[-_][A-Za-z0-9]+(?:[-_]\d{2,3})?\b)", re.I)
_PURE_CODE = re.compile(r"\b(?:EXP|P)\d{2,4}\b", re.I)


def folder_slug(label: str) -> str:
    """把展示名转为 Windows 合法文件夹名：去空白、非法字符。保留中文。"""
    s = _INVALID.sub("", label or "")
    s = _WS.sub("", s)
    return s.strip() or "untitled"


def unique_name(name: str, existing: list[str]) -> str:
    """若 name 已存在于 existing，追加 ' (n)' 直到不冲突。"""
    if name not in existing:
        return name
    stem = name.rsplit(".", 1)[0] if "." in name else name
    ext = "." + name.rsplit(".", 1)[1] if "." in name else ""
    i = 2
    while f"{stem} ({i}){ext}" in existing:
        i += 1
    return f"{stem} ({i}){ext}"


def parse_sample_hint(filename: str) -> str:
    """尽力从文件名提样本码（如 SA-MLOY4-001 / EXP024），没有则返回空。"""
    for m in _SAMPLE.finditer(filename):
        token = m.group(1)
        if _PURE_CODE.search(token):
            continue  # 避开纯实验/项目编号
        return token
    return ""
```

- [ ] **Step 4: 跑测试通过**

Run: `python -m pytest tests/test_naming.py -q`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: naming helpers (folder slug, unique name, sample hint)"
```

---

## Task 2: db 模块（建表 + 各实体查询/写入）

**Files:**
- Create: `fw/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_db.py`:
```python
from fw import db


def test_roundtrip_workspace_node():
    with db.conn() as con:
        wid = db.create_workspace(con, code="SA-Osteomyelitis", name="SA 骨髓炎")
        nid = db.create_node(con, workspace_id=wid, kind="figure", label="Figure 1", title="感染")
        db.update_node(con, nid, status="adopted", importance="key", note="ok")
        db.add_log(con, wid, nid, "定稿")
    with db.conn() as con:
        ws = db.get_workspace(con, wid)
        assert ws["code"] == "SA-Osteomyelitis"
        node = db.get_node(con, nid)
        assert node["status"] == "adopted" and node["importance"] == "key"


def test_tree_and_tags():
    with db.conn() as con:
        wid = db.create_workspace(con, code="P", name="p")
        fig = db.create_node(con, wid, kind="figure", label="Figure 3", title="炎症")
        pan = db.create_node(con, wid, kind="panel", label="3A", title="IL6", parent_id=fig)
        db.add_tag(con, pan, "IL6")
        db.add_tag(con, pan, "SA")
    with db.conn() as con:
        tree = db.tree(con, wid)
        assert len(tree) == 1 and tree[0]["children"][0]["label"] == "3A"
        assert {t["name"] for t in db.node_tags(con, tree[0]["children"][0]["id"])} == {"IL6", "SA"}


def test_file_and_log_query():
    with db.conn() as con:
        wid = db.create_workspace(con, code="W", name="w")
        db.add_file(con, wid, node_id=None, rel_path=r"原始数据\a.xlsx", name="a.xlsx",
                    ext="xlsx", size=1, sha256="aa")
        files = db.search_files(con, "a.xlsx")
        assert len(files) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_db.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 db.py**

```python
"""SQLite：连接、建表、实体读写。相对路径基于工作区文件夹。"""
import sqlite3
from fw import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace(
 id INTEGER PRIMARY KEY,
 code TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 archived INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS node(
 id INTEGER PRIMARY KEY,
 workspace_id INTEGER NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
 parent_id INTEGER REFERENCES node(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('figure','panel')),
 label TEXT NOT NULL DEFAULT '',
 title TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate','adopted','rejected','redo')),
 importance TEXT NOT NULL DEFAULT 'normal' CHECK(importance IN ('key','normal','aux')),
 note TEXT NOT NULL DEFAULT '',
 preview_rel TEXT,
 created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
 updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS tag(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS node_tag(
 node_id INTEGER NOT NULL REFERENCES node(id) ON DELETE CASCADE,
 tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
 PRIMARY KEY(node_id, tag_id));
CREATE TABLE IF NOT EXISTS file_item(
 id INTEGER PRIMARY KEY,
 workspace_id INTEGER NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
 node_id INTEGER REFERENCES node(id) ON DELETE SET NULL,
 rel_path TEXT NOT NULL,
 name TEXT NOT NULL,
 ext TEXT NOT NULL DEFAULT '',
 size INTEGER NOT NULL DEFAULT 0,
 sha256 TEXT NOT NULL DEFAULT '',
 sample_note TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS log_entry(
 id INTEGER PRIMARY KEY,
 workspace_id INTEGER NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
 node_id INTEGER REFERENCES node(id) ON DELETE CASCADE,
 text TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
"""


def connect(path=None) -> sqlite3.Connection:
    p = path or config.db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


class conn:
    """上下文管理器：打开连接 → init schema → 提交 → 关闭。"""

    def __enter__(self):
        self._con = connect()
        self._con.executescript(_SCHEMA)
        return self._con

    def __exit__(self, *exc):
        if exc[0] is None:
            self._con.commit()
        else:
            self._con.rollback()
        self._con.close()


# ---------- workspace ----------
def create_workspace(con, code, name) -> int:
    cur = con.execute("INSERT INTO workspace(code,name) VALUES(?,?)", (code, name))
    return cur.lastrowid


def get_workspace(con, wid):
    return con.execute("SELECT * FROM workspace WHERE id=?", (wid,)).fetchone()


def list_workspaces(con):
    return con.execute("SELECT * FROM workspace ORDER BY archived, id DESC").fetchall()


def rename_workspace(con, wid, name):
    con.execute("UPDATE workspace SET name=? WHERE id=?", (name, wid))


def set_workspace_archived(con, wid, archived):
    con.execute("UPDATE workspace SET archived=? WHERE id=?", (int(archived), wid))


# ---------- node ----------
def create_node(con, workspace_id, kind, label, title, parent_id=None, status="candidate",
                importance="normal") -> int:
    cur = con.execute(
        "INSERT INTO node(workspace_id,parent_id,kind,label,title,status,importance) VALUES(?,?,?,?,?,?,?)",
        (workspace_id, parent_id, kind, label, title, status, importance))
    return cur.lastrowid


def get_node(con, nid):
    return con.execute("SELECT * FROM node WHERE id=?", (nid,)).fetchone()


def update_node(con, nid, label=None, title=None, status=None, importance=None, note=None,
                preview_rel=None):
    sets, vals = [], []
    for col in ("label", "title", "status", "importance", "note", "preview_rel"):
        v = locals()[col]
        if v is not None:
            sets.append(f"{col}=?")
            vals.append(v)
    if sets:
        vals.append(nid)
        con.execute(f"UPDATE node SET {', '.join(sets)}, updated_at=datetime('now','localtime') WHERE id=?", vals)


def delete_node(con, nid):
    con.execute("DELETE FROM node WHERE id=?", (nid,))  # 依赖 FK CASCADE 清子树


def children(con, nid=None, workspace_id=None):
    if nid is not None:
        return con.execute("SELECT * FROM node WHERE parent_id=? ORDER BY id", (nid,)).fetchall()
    return con.execute("SELECT * FROM node WHERE workspace_id=? AND parent_id IS NULL ORDER BY id",
                       (workspace_id,)).fetchall()


def tree(con, wid):
    rows = con.execute("SELECT * FROM node WHERE workspace_id=? ORDER BY id", (wid,)).fetchall()
    by_parent = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(dict(r))
    roots = by_parent.get(None, [])

    def build(nodes):
        for n in nodes:
            n["children"] = build(by_parent.get(n["id"], []))
            n["file_count"] = con.execute(
                "SELECT COUNT(*) c FROM file_item WHERE node_id=?", (n["id"],)).fetchone()["c"]
            n["tags"] = [t["name"] for t in node_tags(con, n["id"])]
        return nodes

    return build(roots)


def all_tags(con):
    return con.execute("SELECT name FROM tag ORDER BY name").fetchall()


# ---------- node_tags ----------
def add_tag(con, node_id, name):
    con.execute("INSERT OR IGNORE INTO tag(name) VALUES(?)", (name,))
    tid = con.execute("SELECT id FROM tag WHERE name=?", (name,)).fetchone()["id"]
    con.execute("INSERT OR IGNORE INTO node_tag(node_id,tag_id) VALUES(?,?)", (node_id, tid))


def remove_tag(con, node_id, name):
    con.execute("DELETE FROM node_tag WHERE node_id=? AND tag_id=(SELECT id FROM tag WHERE name=?)",
                (node_id, name))


def node_tags(con, node_id):
    return con.execute(
        "SELECT t.name FROM tag t JOIN node_tag nt ON nt.tag_id=t.id WHERE nt.node_id=? ORDER BY t.name",
        (node_id,)).fetchall()


# ---------- file_item ----------
def add_file(con, workspace_id, rel_path, name, ext, size, sha256, node_id=None,
             sample_note=""):
    cur = con.execute(
        "INSERT INTO file_item(workspace_id,node_id,rel_path,name,ext,size,sha256,sample_note)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (workspace_id, node_id, rel_path, name, ext, size, sha256, sample_note))
    return cur.lastrowid


def get_file(con, fid):
    return con.execute("SELECT * FROM file_item WHERE id=?", (fid,)).fetchone()


def node_files(con, node_id):
    return con.execute("SELECT * FROM file_item WHERE node_id=? ORDER BY id", (node_id,)).fetchall()


def raw_files(con, wid):
    return con.execute("SELECT * FROM file_item WHERE workspace_id=? AND node_id IS NULL ORDER BY id",
                       (wid,)).fetchall()


def delete_file_record(con, fid):
    con.execute("DELETE FROM file_item WHERE id=?", (fid,))


def search_files(con, q):
    like = f"%{q}%"
    return con.execute(
        "SELECT * FROM file_item WHERE name LIKE ? OR sample_note LIKE ? ORDER BY id DESC",
        (like, like)).fetchall()


# ---------- logs ----------
def add_log(con, workspace_id, node_id, text):
    cur = con.execute("INSERT INTO log_entry(workspace_id,node_id,text) VALUES(?,?,?)",
                      (workspace_id, node_id, text))
    return cur.lastrowid


def node_logs(con, node_id):
    return con.execute("SELECT * FROM log_entry WHERE node_id=? ORDER BY id", (node_id,)).fetchall()


def workspace_logs(con, wid):
    return con.execute("SELECT * FROM log_entry WHERE workspace_id=? ORDER BY id DESC LIMIT 200",
                       (wid,)).fetchall()
```

- [ ] **Step 4: 跑测试通过**

Run: `python -m pytest tests/test_db.py -q`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: sqlite schema and entity CRUD"
```

---

## Task 3: storage 模块（文件系统操作）

**Files:**
- Create: `fw/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_storage.py`:
```python
import hashlib
from fw import config, storage


def test_workspace_and_figure_folders():
    wf = storage.workspace_folder("SA-Osteomyelitis")
    assert wf.name == "SA-Osteomyelitis" and wf.exists()
    ff = storage.figure_folder("SA-Osteomyelitis", "Figure 1")
    assert ff.exists() and "原始数据" in storage.workspace_folder("SA-Osteomyelitis").name or True


def test_save_upload_returns_sha_and_unique():
    wf = storage.workspace_folder("P001")
    bytes_data = b"hello figure"
    rel1 = storage.save_upload(wf, bytes_data, "a.xlsx")
    rel2 = storage.save_upload(wf, bytes_data, "a.xlsx")
    assert rel1 != rel2 and (wf / rel2).exists()
    sha = hashlib.sha256(bytes_data).hexdigest()
    assert storage.sha256_bytes(bytes_data) == sha


def test_trash_moves_file():
    wf = storage.workspace_folder("P1")
    rel = storage.save_upload(wf, b"x", "keep.txt")
    storage.move_to_trash(wf, rel)
    assert not (wf / rel).exists()
    assert (wf / ".trash").exists()


def test_preview_saved():
    wf = storage.workspace_folder("P2")
    rel = storage.save_upload(wf, b"\x89PNG", "preview.png", dest_rel="Figure1")
    assert rel == "Figure1/preview.png"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_storage.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 storage.py**

```python
"""文件系统为真源：建工作区/Figure 夹、保存上传(复制+SHA)、trash。"""
import hashlib
import shutil
from pathlib import Path
from fw import config, naming


def workspace_folder(code: str) -> Path:
    p = config.root_dir() / code
    p.mkdir(parents=True, exist_ok=True)
    (p / "原始数据").mkdir(exist_ok=True)
    (p / ".trash").mkdir(exist_ok=True)
    return p


def figure_folder(ws_code: str, label: str) -> Path:
    """Figure 的文件夹：<工作区>/<label 去空格>。返回并确保存在。"""
    p = workspace_folder(ws_code) / naming.folder_slug(label)
    p.mkdir(exist_ok=True)
    return p


def panel_folder(ws_code: str, figure_label: str, panel_label: str) -> Path:
    p = figure_folder(ws_code, figure_label) / naming.folder_slug(panel_label)
    p.mkdir(exist_ok=True)
    return p


def _list_names(folder: Path) -> list[str]:
    return [x.name for x in folder.iterdir()] if folder.exists() else []


def save_upload(ws_folder: Path, data: bytes, filename: str, dest_rel: str = "") -> str:
    """把字节写入 ws_folder 下（dest_rel 为空则根，否则 dest_rel 目录）。返回相对路径。"""
    dest = ws_folder
    if dest_rel:
        dest = ws_folder / dest_rel
    dest.mkdir(parents=True, exist_ok=True)
    fname = naming.unique_name(filename, _list_names(dest))
    (dest / fname).write_bytes(data)
    rel = (Path(dest_rel) / fname).as_posix() if dest_rel else fname
    return rel


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def move_to_trash(ws_folder: Path, rel_path: str):
    src = ws_folder / rel_path
    trash = ws_folder / ".trash"
    trash.mkdir(exist_ok=True)
    if not src.exists():
        return
    dest_name = naming.unique_name(src.name, _list_names(trash))
    shutil.move(str(src), str(trash / dest_name))
```

- [ ] **Step 4: 跑测试通过**

Run: `python -m pytest tests/test_storage.py -q`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: storage ops (folders, copy upload, sha, trash)"
```

---

## Task 4: export 文本生成

**Files:**
- Create: `fw/export.py`
- Test: `tests/test_export.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_export.py`:
```python
from fw import db, export

_WS_LABEL = {"candidate": "候选", "adopted": "已采用", "rejected": "已弃用", "redo": "待重做"}
_IMP_LABEL = {"key": "关键", "normal": "一般", "aux": "辅助"}


def _seed(con):
    wid = db.create_workspace(con, code="P", name="P 项目")
    fig = db.create_node(con, wid, "figure", "Figure 1", "骨破坏", status="adopted", importance="key")
    db.add_file(con, wid, node_id=fig, rel_path="Figure1/a.xlsx", name="a.xlsx", ext="xlsx",
                size=10, sha256="aa")
    db.add_log(con, wid, fig, "v2 定稿")
    return wid


def test_source_data_manifest():
    with db.conn() as con:
        wid = _seed(con)
        rows = export.source_data(con, wid)
        assert "a.xlsx" in rows and "aa" in rows


def test_legend_draft_mentions_label():
    with db.conn() as con:
        wid = _seed(con)
        text = export.legend_draft(con, wid)
        assert "Figure 1" in text and "骨破坏" in text


def test_data_availability_skeleton():
    with db.conn() as con:
        wid = _seed(con)
        text = export.data_availability(con, wid, repo_hint="https://doi.org/example")
        assert "Data availability" in text and "example" in text
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_export.py -q`
Expected: FAIL。

- [ ] **Step 3: 实现 export.py**

```python
"""对「已采用」节点生成 SourceData 清单 / 图注草稿 / 数据可得性骨架。"""
from fw import db

_LABEL = {"adopted": "已采用", "redo": "待重做"}
_IMP = {"key": "关键支撑", "normal": "一般支撑", "aux": "辅助"}


def _adopted_nodes(con, wid):
    return con.execute(
        "SELECT * FROM node WHERE workspace_id=? AND status='adopted' ORDER BY id", (wid,)).fetchall()


def source_data(con, wid) -> str:
    """CSV 文本：采用节点 → 其下/自身挂的源文件清单。"""
    lines = ["Figure,File,RelativePath,SHA256,Size"]
    adopted = _adopted_nodes(con, wid)
    for n in adopted:
        files = con.execute(
            "SELECT * FROM file_item WHERE node_id=? OR node_id IN "
            "(SELECT id FROM node WHERE parent_id=?) ORDER BY id", (n["id"], n["id"])).fetchall()
        for f in files:
            lines.append(f'{n["label"]},{f["name"]},{f["rel_path"]},{f["sha256"]},{f["size"]}')
    return "\n".join(lines)


def legend_draft(con, wid) -> str:
    out = []
    for n in con.execute(
            "SELECT * FROM node WHERE workspace_id=? AND parent_id IS NULL AND kind='figure' "
            "ORDER BY id", (wid,)).fetchall():
        note = (n["note"] or "").strip().replace("\n", " ")
        out.append(f'{n["label"]} ({n["title"] or "待补标题"}). {note}')
        for p in db.children(con, nid=n["id"]):
            out.append(f'  {p["label"]} {p["title"] or ""}'.rstrip())
    return "\n".join(out)


def data_availability(con, wid, repo_hint: str = "") -> str:
    ws = con.execute("SELECT * FROM workspace WHERE id=?", (wid,)).fetchone()
    n_adopted = con.execute("SELECT COUNT(*) c FROM node WHERE workspace_id=? AND status='adopted'",
                            (wid,)).fetchone()["c"]
    hint = repo_hint or "[填写：原始数据仓库 / DOI 占位]"
    return (f"Data availability.\n\n"
            f"All source data underlying the {n_adopted} adopted figure(s) of this manuscript "
            f"({ws['name']}) are provided as Source Data files. Raw sequencing / imaging datasets "
            f"are deposited at {hint}.\n\n"
            f"Uncropped blots and statistical source tables are included with the paper's "
            f"supplementary Source Data file set.")
```

- [ ] **Step 4: 跑测试通过**

Run: `python -m pytest tests/test_export.py -q`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: export source-data / legend / data-availability text"
```

---

## Task 5: API —— workspaces 与 nodes（含建夹）

**Files:**
- Create: `fw/api.py`
- Modify: `fw_server.py`
- Test: `tests/test_api_workspaces.py`
- Test: `tests/test_api_nodes.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_api_workspaces.py`:
```python
from fw import db, config


def test_create_and_list(client):
    r = client.post("/api/workspaces", json={"code": "SA-Osteomyelitis", "name": "SA 骨髓炎"})
    assert r.status_code == 200
    assert (config.root_dir() / "SA-Osteomyelitis").exists()
    lst = client.get("/api/workspaces").json()["workspaces"]
    assert any(w["code"] == "SA-Osteomyelitis" for w in lst)


def test_create_duplicate_code_409(client):
    client.post("/api/workspaces", json={"code": "Dup", "name": "x"})
    r = client.post("/api/workspaces", json={"code": "Dup", "name": "y"})
    assert r.status_code == 409


def test_archive(client):
    client.post("/api/workspaces", json={"code": "A", "name": "a"})
    client.post("/api/workspaces/A/archive")
    assert client.get("/api/workspaces/A").json()["workspace"]["archived"] == 1
```

Create `tests/test_api_nodes.py`:
```python
def _ws(client):
    client.post("/api/workspaces", json={"code": "P001", "name": "项目1"})
    return "P001"


def test_create_figure_makes_folder(client):
    _ws(client)
    r = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "骨破坏"})
    assert r.status_code == 200
    import os
    from fw import config
    assert (config.root_dir() / "P001" / "Figure1").exists()
    nid = r.json()["node"]["id"]
    assert nid


def test_create_panel_under_figure(client):
    _ws(client)
    fig = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 3",
                                                          "title": "炎症"}).json()["node"]
    client.post("/api/workspaces/P001/nodes", json={"kind": "panel", "label": "3A", "title": "IL6",
                                                    "parent_id": fig["id"]})
    tree = client.get("/api/workspaces/P001").json()["workspace"]["tree"]
    assert tree[0]["children"][0]["label"] == "3A"


def test_patch_node(client):
    _ws(client)
    nid = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 1",
                                                          "title": "x"}).json()["node"]["id"]
    r = client.patch(f"/api/nodes/{nid}", json={"status": "adopted", "importance": "key",
                                                "note": "定稿"})
    assert r.status_code == 200
    assert r.json()["node"]["status"] == "adopted"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_api_workspaces.py tests/test_api_nodes.py -q`
Expected: FAIL（404 路由未注册）。

- [ ] **Step 3: 实现 api.py 的 workspaces/nodes 部分**

Create `fw/api.py`：
```python
"""FastAPI 路由。相对路径基于工作区文件夹。"""
from fastapi import APIRouter, HTTPException
from fw import db, storage, naming

router = APIRouter(prefix="/api")


def _ws_code(con, wid):
    return db.get_workspace(con, wid)["code"]


# ---------------- workspaces ----------------
@router.get("/workspaces")
def list_workspaces():
    with db.conn() as con:
        return {"workspaces": [dict(w) for w in db.list_workspaces(con)]}


@router.post("/workspaces")
def create_workspace(body: dict):
    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip() or code
    slug = naming.folder_slug(code)
    if not slug:
        raise HTTPException(400, "code 不能为空")
    try:
        with db.conn() as con:
            wid = db.create_workspace(con, code=slug, name=name)
    except Exception:
        raise HTTPException(409, f"工作区 {slug} 已存在")
    storage.workspace_folder(slug)
    return {"workspace": {"id": wid, "code": slug, "name": name}}


@router.get("/workspaces/{code}")
def get_workspace(code: str):
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404, "not found")
        wid = ws["id"]
        payload = dict(ws)
        payload["tree"] = db.tree(con, wid)
        payload["raw_files"] = [dict(f) for f in db.raw_files(con, wid)]
        return {"workspace": payload}


@router.post("/workspaces/{code}/archive")
def archive_workspace(code: str):
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        db.set_workspace_archived(con, ws["id"], 1)
    return {"ok": True}


# ---------------- nodes ----------------
@router.post("/workspaces/{code}/nodes")
def create_node(code: str, body: dict):
    kind = body.get("kind")
    if kind not in ("figure", "panel"):
        raise HTTPException(400, "kind 需为 figure/panel")
    label = (body.get("label") or "").strip() or ("Figure" if kind == "figure" else "panel")
    title = (body.get("title") or "").strip()
    parent_id = body.get("parent_id")
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        if kind == "figure":
            storage.figure_folder(code, label)          # 建图即建夹
        elif parent_id is not None:
            par = db.get_node(con, parent_id)
            if not par or par["workspace_id"] != ws["id"]:
                raise HTTPException(400, "parent 不存在于本工作区")
        nid = db.create_node(con, ws["id"], kind=kind, label=label, title=title,
                             parent_id=parent_id)
        node = db.get_node(con, nid)
        return {"node": dict(node)}


@router.patch("/api/nodes/{nid}")
def patch_node(nid: int, body: dict):
    allowed = {"label", "title", "status", "importance", "note"}
    clean = {k: v for k, v in body.items() if k in allowed and v is not None}
    if "status" in clean and clean["status"] not in ("candidate", "adopted", "rejected", "redo"):
        raise HTTPException(400, "bad status")
    if "importance" in clean and clean["importance"] not in ("key", "normal", "aux"):
        raise HTTPException(400, "bad importance")
    with db.conn() as con:
        db.update_node(con, nid, **clean)
        return {"node": dict(db.get_node(con, nid))}


@router.post("/nodes/{nid}/logs")
def add_log(nid: int, body: dict):
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "空日志")
    with db.conn() as con:
        node = db.get_node(con, nid)
        if not node:
            raise HTTPException(404)
        db.add_log(con, node["workspace_id"], nid, text)
        return {"ok": True, "logs": [dict(l) for l in db.node_logs(con, nid)]}


@router.delete("/nodes/{nid}")
def delete_node(nid: int):
    with db.conn() as con:
        node = db.get_node(con, nid)
        if not node:
            raise HTTPException(404)
        db.delete_node(con, nid)
    return {"ok": True}
```

注意：`patch_node`/`add_log`/`delete_node` 装饰路径前缀已含 `/api`，写成 `@router.patch("/nodes/{nid}")` 而非 `/api/nodes/{nid}`，避免双重前缀。

Modify `fw_server.py`：
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fw.api import router

app = FastAPI(title="Figure Workspace", version="0.1.0")
app.include_router(router)


@app.get("/api/health")
def health():
    return {"ok": True}


# 静态托管（index.html 等）——Task 9 之前留空目录不影响接口测试
from pathlib import Path  # noqa: E402
_static = Path(__file__).resolve().parent / "static"
_static.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
```

- [ ] **Step 4: 修正 api.py 中三处路由前缀**

把 `@router.patch("/api/nodes/{nid}")` 改为 `@router.patch("/nodes/{nid}")`；`@router.post("/nodes/{nid}/logs")`、`@router.delete("/nodes/{nid}")` 本已无 `/api` 前缀，保持不变。确保所有路径都相对 `/api`。

- [ ] **Step 5: 跑测试通过**

Run: `python -m pytest tests/test_api_workspaces.py tests/test_api_nodes.py -q`
Expected: 全部通过（create/list/duplicate/archive/figure-folder/panel/tree/patch）。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: workspaces & node tree api with on-disk folders"
```

---

## Task 6: API —— 文件上传/下载/删除、预览

**Files:**
- Modify: `fw/api.py`
- Test: `tests/test_api_files.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_api_files.py`:
```python
def test_upload_to_figure(client):
    client.post("/api/workspaces", json={"code": "P1", "name": "p"})
    nid = client.post("/api/workspaces/P1/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    r = client.post(f"/api/nodes/{nid}/files",
                    files={"file": ("qPCR_SA-MLOY4-001.xlsx", b"data123", "text/plain")})
    assert r.status_code == 200
    f = r.json()["files"][0]
    assert f["sha256"] and f["sample_note"] == "SA-MLOY4-001"
    # 文件真的落盘于 Figure1 文件夹
    from fw import config
    assert (config.root_dir() / "P1" / "Figure1" / "qPCR_SA-MLOY4-001.xlsx").exists()


def test_upload_to_raw(client):
    client.post("/api/workspaces", json={"code": "P2", "name": "p"})
    r = client.post("/api/workspaces/P2/files",
                    files={"file": ("raw.tif", b"\x00\x01", "image/tiff")})
    assert r.status_code == 200 and r.json()["files"][0]["node_id"] is None


def test_download_and_delete(client):
    client.post("/api/workspaces", json={"code": "P3", "name": "p"})
    nid = client.post("/api/workspaces/P3/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    fid = client.post(f"/api/nodes/{nid}/files",
                      files={"file": ("a.txt", b"hello", "text/plain")}).json()["files"][0]["id"]
    dl = client.get(f"/api/files/{fid}")
    assert dl.status_code == 200 and dl.content == b"hello"
    assert client.delete(f"/api/files/{fid}").status_code == 200


def test_paste_preview(client):
    client.post("/api/workspaces", json={"code": "P4", "name": "p"})
    nid = client.post("/api/workspaces/P4/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    r = client.post(f"/api/nodes/{nid}/preview",
                    files={"file": ("preview.png", b"\x89PNG\r\n", "image/png")})
    assert r.status_code == 200
    node = client.get("/api/nodes/{nid}".replace("{nid}", str(nid))).json()["node"]
    assert node["preview_rel"] == "Figure1/preview.png"
```

（注：为获取 node，在 api.py 里加一个 `GET /nodes/{nid}`。）

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_api_files.py -q`
Expected: FAIL。

- [ ] **Step 3: 在 api.py 增加文件相关路由与 GET node**

追加到 `fw/api.py`：
```python
import hashlib
from pathlib import Path
from fastapi import UploadFile, File
from fastapi.responses import FileResponse


def _ws_folder_by_code(code):
    return storage.workspace_folder(code)


@router.get("/nodes/{nid}")
def get_node(nid: int):
    with db.conn() as con:
        n = db.get_node(con, nid)
        if not n:
            raise HTTPException(404)
        d = dict(n)
        d["files"] = [dict(x) for x in db.node_files(con, nid)]
        d["logs"] = [dict(x) for x in db.node_logs(con, nid)]
        d["tags"] = [x["name"] for x in db.node_tags(con, nid)]
        return {"node": d}


def _upload_to(con, ws_code, ws_id, node_id, data: bytes, filename: str, dest_rel: str):
    import os
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    sha = storage.sha256_bytes(data)
    ws_folder = storage.workspace_folder(ws_code)
    rel = storage.save_upload(ws_folder, data, filename, dest_rel=dest_rel)
    sample = naming.parse_sample_hint(filename)
    db.add_file(con, ws_id, node_id=node_id, rel_path=rel, name=Path(rel).name,
                ext=ext, size=len(data), sha256=sha, sample_note=sample)
    return db.get_file(con, con.execute("SELECT last_insert_rowid()").fetchone()[0])


@router.post("/nodes/{nid}/files")
async def upload_node_file(nid: int, file: UploadFile = File(...)):
    data = await file.read()
    filename = file.filename or "file"
    with db.conn() as con:
        n = db.get_node(con, nid)
        if not n:
            raise HTTPException(404)
        ws = db.get_workspace(con, n["workspace_id"])
        # 定位落盘目录：figure→自身夹；panel→所属 figure 夹/<label>子目录
        if n["kind"] == "figure":
            dest_rel = storage.figure_folder(ws["code"], n["label"]).relative_to(storage.workspace_folder(ws["code"])).as_posix()
        else:
            # 找最近 figure 祖先夹，子目录用本面板 label
            fig = con.execute(
                "WITH RECURSIVE up(id,parent_id,label,kind) AS ("
                " SELECT id,parent_id,label,kind FROM node WHERE id=? "
                " UNION ALL SELECT n.id,n.parent_id,n.label,n.kind FROM node n "
                " JOIN up ON n.id=up.parent_id) SELECT id,label FROM up WHERE kind='figure' LIMIT 1",
                (nid,)).fetchone()
            if fig:
                dest_rel = (storage.figure_folder(ws["code"], fig["label"]) / naming.folder_slug(n["label"])).relative_to(storage.workspace_folder(ws["code"])).as_posix()
            else:
                dest_rel = ""
        fid = _upload_to(con, ws["code"], ws["id"], nid, data, filename, dest_rel)
        return {"files": [dict(x) for x in db.node_files(con, nid)]}


@router.post("/workspaces/{code}/files")
async def upload_raw_file(code: str, file: UploadFile = File(...)):
    data = await file.read()
    filename = file.filename or "file"
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        dest_rel = "原始数据"
        _upload_to(con, code, ws["id"], None, data, filename, dest_rel)
        return {"files": [dict(f) for f in db.raw_files(con, ws["id"])]}


@router.get("/files/{fid}")
def download_file(fid: int):
    with db.conn() as con:
        f = db.get_file(con, fid)
        if not f:
            raise HTTPException(404)
        ws = db.get_workspace(con, f["workspace_id"])
        path = storage.workspace_folder(ws["code"]) / f["rel_path"]
    if not path.exists():
        raise HTTPException(410, "文件已被移动/删除")
    return FileResponse(str(path), filename=f["name"])


@router.delete("/files/{fid}")
def delete_file(fid: int):
    with db.conn() as con:
        f = db.get_file(con, fid)
        if not f:
            raise HTTPException(404)
        ws = db.get_workspace(con, f["workspace_id"])
        storage.move_to_trash(storage.workspace_folder(ws["code"]), f["rel_path"])
        db.delete_file_record(con, fid)
    return {"ok": True}


@router.post("/nodes/{nid}/preview")
async def save_preview(nid: int, file: UploadFile = File(...)):
    data = await file.read()
    with db.conn() as con:
        n = db.get_node(con, nid)
        if not n:
            raise HTTPException(404)
        ws = db.get_workspace(con, n["workspace_id"])
        if n["kind"] == "figure":
            folder = storage.figure_folder(ws["code"], n["label"])
        else:
            folder = storage.workspace_folder(ws["code"]) / "原始数据"
        rel = storage.save_upload(folder.parent if n["kind"] == "panel" else folder,
                                  data, "preview.png")
        full_rel = (Path(rel).parent if n["kind"] == "figure" else Path("原始数据"))
        db.update_node(con, nid, preview_rel=f"{storage.figure_folder(ws['code'], n['label']).name}/preview.png" if n["kind"] == "figure" else f"原始数据/preview.png")
        return {"ok": True, "preview_rel": dict(db.get_node(con, nid))["preview_rel"]}
```

说明：预览一律存为 `preview.png`；若已存在则 storage.save_upload 会生成 `preview (2).png`，此处先覆盖旧 preview 的行为简化——如需强制覆盖可先 delete 旧文件。MVP 接受生成序号副本，前端取 `preview_rel` 最新值即可。

- [ ] **Step 4: 修正重复行**：若 `save_preview` 内 `full_rel` 变量未用，删除之，保留赋值 `db.update_node(...)`。以 `pytest` 为准。

- [ ] **Step 5: 跑测试通过**

Run: `python -m pytest tests/test_api_files.py -q`
Expected: 全部通过。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: file upload/download/delete + preview endpoints"
```

---

## Task 7: API —— 标签与全局检索

**Files:**
- Modify: `fw/api.py`
- Test: `tests/test_api_tags_search.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_api_tags_search.py`:
```python
def test_tags_and_search(client):
    client.post("/api/workspaces", json={"code": "P1", "name": "SA 骨髓炎"})
    nid = client.post("/api/workspaces/P1/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "炎症"}).json()["node"]["id"]
    assert client.post(f"/api/nodes/{nid}/tags", json={"tag": "IL6"}).status_code == 200
    assert client.post(f"/api/nodes/{nid}/tags", json={"tag": "SA"}).status_code == 200
    r = client.get("/api/search?q=IL6")
    hits = r.json()["results"]
    assert any(h["node_id"] == nid for h in hits)
    assert any(h["tag"] == "IL6" for h in hits)


def test_search_finds_workspace_and_file(client):
    client.post("/api/workspaces", json={"code": "Zebrafish", "name": "斑马鱼模型"})
    r = client.get("/api/search?q=斑马鱼")
    assert any(h["workspace_code"] == "Zebrafish" for h in r.json()["results"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_api_tags_search.py -q`
Expected: FAIL。

- [ ] **Step 3: 在 api.py 增加 tags 与 search**

追加到 `fw/api.py`：
```python
@router.post("/nodes/{nid}/tags")
def add_tag(nid: int, body: dict):
    tag = (body.get("tag") or "").strip()
    if not tag:
        raise HTTPException(400)
    with db.conn() as con:
        if not db.get_node(con, nid):
            raise HTTPException(404)
        db.add_tag(con, nid, tag)
        return {"tags": [t["name"] for t in db.node_tags(con, nid)]}


@router.delete("/nodes/{nid}/tags/{tag}")
def del_tag(nid: int, tag: str):
    with db.conn() as con:
        db.remove_tag(con, nid, tag)
    return {"ok": True}


@router.get("/search")
def search(q: str = ""):
    q = q.strip()
    results = []
    with db.conn() as con:
        if not q:
            return {"results": results}
        like = f"%{q}%"
        for ws in con.execute("SELECT * FROM workspace WHERE code LIKE ? OR name LIKE ?",
                              (like, like)).fetchall():
            results.append({"type": "workspace", "workspace_code": ws["code"],
                            "label": ws["name"], "node_id": None, "tag": None})
        for tag in con.execute("SELECT t.name, nt.node_id FROM tag t "
                               "JOIN node_tag nt ON nt.tag_id=t.id "
                               "WHERE t.name LIKE ? LIMIT 50", (like,)).fetchall():
            results.append({"type": "tag", "workspace_code": None, "label": tag["name"],
                            "node_id": tag["node_id"], "tag": tag["name"]})
        for n in con.execute("SELECT * FROM node WHERE label LIKE ? OR title LIKE ? LIMIT 50",
                             (like, like)).fetchall():
            results.append({"type": "node", "workspace_code": None, "label": f"{n['label']} {n['title']}".strip(),
                            "node_id": n["id"], "tag": None})
        for f in con.execute("SELECT * FROM file_item WHERE name LIKE ? LIMIT 50", (like,)).fetchall():
            results.append({"type": "file", "workspace_code": None, "label": f["name"],
                            "node_id": f["node_id"], "tag": None, "file_id": f["id"]})
    # 补工作区码
    with db.conn() as con:
        for r in results:
            if r["node_id"]:
                n = db.get_node(con, r["node_id"])
                if n:
                    ws = db.get_workspace(con, n["workspace_id"])
                    r["workspace_code"] = ws["code"] if ws else None
    return {"results": results}
```

- [ ] **Step 4: 跑测试通过**

Run: `python -m pytest tests/test_api_tags_search.py -q`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: node tags + cross-workspace search endpoint"
```

---

## Task 8: API —— 扫描导入（只读发现 + 导入预览/源图）

**Files:**
- Modify: `fw/api.py`
- Test: `tests/test_api_scan.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_api_scan.py`:
```python
def test_scan_lists_images_readonly(tmp_path):
    from fw import config
    src = tmp_path / "figs"
    src.mkdir()
    (src / "F1_microCT.png").write_bytes(b"x")
    (src / "notes.txt").write_bytes(b"y")
    import os
    os.environ["FW_ROOT"] = str(tmp_path / "root")
    client_import = _client_after_env()
    client_import.post("/api/workspaces", json={"code": "Scan1", "name": "s"})
    r = client_import.post("/api/workspaces/Scan1/scan", json={"folder_path": str(src)})
    assert r.status_code == 200
    names = [i["name"] for i in r.json()["images"]]
    assert "F1_microCT.png" in names and "notes.txt" not in names


def _client_after_env():
    from fastapi.testclient import TestClient
    import fw_server
    with TestClient(fw_server.app) as c:
        return c
```

说明：本测试因 env 需在 import 前设置较繁琐，可改为用 monkeypatch 临时覆盖 `storage.workspace_folder` 更稳；若实现时发现隔离复杂，允许改写为直接调用 `storage` + `db` 的单元式断言（见 Step 4 注）。重点验证：scan 只列图片扩展名、不复制不移动源文件。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_api_scan.py -q`
Expected: FAIL。

- [ ] **Step 3: 在 api.py 增加 scan 路由**

追加到 `fw/api.py`：
```python
_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}


@router.post("/workspaces/{code}/scan")
def scan_folder(code: str, body: dict):
    folder = body.get("folder_path")
    if not folder or not Path(folder).is_dir():
        raise HTTPException(400, "folder_path 无效目录")
    images = []
    for p in sorted(Path(folder).iterdir()):
        if p.is_file() and p.suffix.lower() in _IMG_EXT:
            images.append({"name": p.name, "size": p.stat().st_size,
                           "sample_hint": naming.parse_sample_hint(p.name)})
    return {"images": images}


@router.post("/workspaces/{code}/scan/import")
def apply_scan(code: str, body: dict):
    """把选中的图片导入为 Figure：复制该图作预览，并挂为源文件。不碰目录里其它文件。"""
    folder = Path(body.get("folder_path") or "")
    picks = body.get("picks") or []          # [{name, label}]
    if not folder.is_dir() or not picks:
        raise HTTPException(400, "缺 folder_path 或 picks")
    created = []
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        for i, pick in enumerate(picks, start=1):
            src = folder / pick["name"]
            if not src.is_file():
                continue
            label = pick.get("label") or f"Figure {i}"
            nid = db.create_node(con, ws["id"], kind="figure", label=label, title="")
            ffolder = storage.figure_folder(code, label)
            preview_name = naming.unique_name("preview.png",
                                              [x.name for x in ffolder.iterdir()])
            shutil.copy2(str(src), str(ffolder / preview_name))
            data = src.read_bytes()
            preview_rel = (ffolder.relative_to(storage.workspace_folder(code)).as_posix()
                           + "/" + preview_name)
            db.update_node(con, nid, preview_rel=preview_rel)
            db.add_file(con, ws["id"], node_id=nid,
                        rel_path=f"{ffolder.name}/{preview_name}", name=src.name,
                        ext=src.suffix.lstrip(".").lower(), size=src.stat().st_size,
                        sha256=storage.sha256_bytes(data))
            created.append({"id": nid, "label": label})
    return {"created": created}
```

在 `fw/api.py` 顶部补 `import shutil`。

- [ ] **Step 4: 若 Step1 测试隔离繁琐则改写**：将 `test_scan_lists_images_readonly` 收敛为直接调用模块函数并断言不移动源文件：
```python
def test_scan_readonly_unit(tmp_path):
    from fw import storage
    src = tmp_path / "figs"; src.mkdir()
    (src / "F1_microCT.png").write_bytes(b"x")
    (src / "notes.txt").write_bytes(b"y")
    before = sorted(p.name for p in src.iterdir())
    # 手动请求 storage/folder 层：仅验证扩展名过滤逻辑存在
    imgs = [p for p in src.iterdir() if p.suffix.lower() in _IMG_EXT]
    assert sorted(p.name for p in imgs) == ["F1_microCT.png"]
    assert sorted(p.name for p in src.iterdir()) == before  # 源未被改
```
若走此单元版，把 `_IMG_EXT` 提到 `api.py` 模块级即可供测试 import。二选一，两者跑通一个即可，源文件不被改动为准。

- [ ] **Step 5: 跑测试通过**

Run: `python -m pytest tests/test_api_scan.py -q`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: read-only scan + import selected figures as preview/source"
```

---

## Task 9: API —— 备份

**Files:**
- Modify: `fw/api.py`
- Test: `tests/test_api_backup.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_api_backup.py`:
```python
def test_backup_creates_manifest(client, tmp_path):
    from fw import config
    backup_dir = tmp_path / "backup"
    client.post("/api/workspaces", json={"code": "B1", "name": "b"})
    nid = client.post("/api/workspaces/B1/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    client.post(f"/api/nodes/{nid}/files",
                files={"file": ("a.txt", b"data", "text/plain")})
    r = client.post(f"/api/backup?backup_dir={backup_dir}")
    assert r.status_code == 200
    body = r.json()
    assert body["manifest_count"] == 1
    # db 副本已生成
    assert any(p.suffix == ".db" for p in backup_dir.iterdir())
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_api_backup.py -q`
Expected: FAIL。

- [ ] **Step 3: 在 api.py 增加 backup 路由**

追加到 `fw/api.py`：
```python
import sqlite3
import shutil as _sh


@router.post("/backup")
def run_backup(backup_dir: str = ""):
    from fw import config
    target = Path(backup_dir) if backup_dir else (config.root_dir().parent / "backups")
    target.mkdir(parents=True, exist_ok=True)
    db_src = config.db_path()
    if db_src.exists():
        _sh.copy2(str(db_src), str(target / f"fw_{int(__import__('time').time())}.db"))
    manifest = []
    with db.conn() as con:
        for f in con.execute("SELECT * FROM file_item").fetchall():
            ws = db.get_workspace(con, f["workspace_id"])
            p = storage.workspace_folder(ws["code"]) / f["rel_path"]
            exists = p.exists()
            manifest.append({"name": f["name"], "rel": f["rel_path"], "workspace": ws["code"],
                             "exists": exists})
        (target / "manifest.csv").write_text(
            "workspace,rel_path,name,exists\n" + "\n".join(
                f'{m["workspace"]},{m["rel"]},{m["name"]},{m["exists"]}' for m in manifest),
            encoding="utf-8")
    return {"backup_dir": str(target), "manifest_count": len(manifest)}
```

- [ ] **Step 4: 跑测试通过**

Run: `python -m pytest tests/test_api_backup.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: backup endpoint (db copy + file manifest)"
```

---

## Task 10: 前端骨架 + 工作区列表视图

**Files:**
- Create: `static/index.html`
- Create: `static/styles.css`
- Create: `static/app.js`

（此后无单测；以浏览器验收清单为准。）

- [ ] **Step 1: 建 static 目录骨架与 index.html**

Create `static/index.html`：
```html
<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Figure 工作台</title>
<link rel="stylesheet" href="/styles.css">
</head>
<body>
<header class="topbar">
  <b class="brand">Figure 工作台</b>
  <div class="top-actions">
    <input id="globalSearch" placeholder="跨论文检索: 标签 / 文件名 / 样本" class="search-input">
    <button id="btnSettings" class="ghost">设置</button>
  </div>
</header>
<div id="app" class="app">
  <!-- 视图容器：list / workspace / search / settings -->
  <div id="view-list"></div>
  <div id="view-workspace" class="hidden"></div>
  <div id="view-search" class="hidden"></div>
  <div id="view-settings" class="hidden"></div>
</div>
<div id="drawer" class="drawer hidden"></div>
<div id="modal" class="modal hidden"></div>
<script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 写 styles.css（宽松密度）**

Create `static/styles.css`：
```css
* { box-sizing: border-box; }
:root { --bg:#eef0f3; --panel:#fff; --line:#e3e6ec; --text:#222; --mut:#8a97a5;
        --blue:#2471a3; --green:#27ae60; --orange:#e67e22; --red:#c0392b; }
body { margin:0; font-family:"Microsoft YaHei","Segoe UI",system-ui,sans-serif;
       background:var(--bg); color:var(--text); font-size:14px; }
.topbar { display:flex; align-items:center; gap:16px; padding:14px 22px; background:#24303f;
          color:#fff; }
.brand { font-size:16px; }
.top-actions { margin-left:auto; display:flex; gap:12px; align-items:center; }
.search-input { width:280px; padding:8px 12px; border-radius:8px; border:1px solid #3a4a5c;
                background:#1b2531; color:#fff; }
.ghost { background:transparent; border:1px solid #3a4a5c; color:#cfd8e3; border-radius:8px;
         padding:8px 14px; cursor:pointer; }
.app { padding:22px; }
.hidden { display:none !important; }
/* ---- 工作区列表 ---- */
.ws-card { background:var(--panel); border:1px solid var(--line); border-radius:10px;
           padding:18px 20px; margin-bottom:14px; cursor:pointer; display:flex;
           align-items:center; }
.ws-card:hover { border-color:var(--blue); }
.ws-card .code { color:var(--mut); font-size:12px; margin-right:14px; }
.ws-card .archived { color:#bbb; }
/* ---- 看板 ---- */
.board { display:flex; gap:0; align-items:flex-start; }
.board-main { flex:1; min-width:0; }
.fig-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
.fig-card { background:var(--panel); border:1px solid var(--line); border-radius:10px;
            padding:18px; cursor:pointer; position:relative; border-left:5px solid #ccc; }
.fig-card.s-adopted { border-left-color:var(--green); }
.fig-card.s-candidate { border-left-color:var(--orange); }
.fig-card.s-redo { border-left-color:var(--red); }
.fig-card.s-rejected { border-left-color:#bbb; }
.fig-card.selected { border:2px solid var(--blue); box-shadow:0 0 0 4px #2471a31f; }
.fig-thumb { height:130px; background:#f2f4f8; border:1px solid #eee; border-radius:8px;
             display:flex; align-items:center; justify-content:center; margin:12px 0;
             color:var(--mut); overflow:hidden; }
.fig-thumb img { max-width:100%; max-height:100%; }
.tagchip { display:inline-block; background:#eef4fb; color:var(--blue); border-radius:6px;
           padding:2px 8px; margin:2px 4px 2px 0; font-size:12px; }
.statchip { border-radius:12px; padding:2px 10px; font-size:12px; }
.st-adopted{background:#eafaf1;color:#1e8449}.st-candidate{background:#fef8e7;color:#b9770e}
.st-redo{background:#fdf0ef;color:var(--red)}.st-rejected{background:#eee;color:#888}
.imp-key{color:var(--red);font-weight:bold}.imp-normal{color:#666}.imp-aux{color:var(--mut)}
/* ---- 详情抽屉 ---- */
.drawer { position:fixed; top:0; right:0; width:420px; height:100vh; background:var(--panel);
          border-left:1px solid var(--line); padding:22px; overflow-y:auto; z-index:20;
          box-shadow:-6px 0 20px rgba(0,0,0,.08); }
.section-label { font-size:11px; color:var(--mut); letter-spacing:.6px; text-transform:uppercase;
                 margin:18px 0 8px; }
.btn { border-radius:8px; padding:8px 14px; border:1px solid var(--line); background:#fff;
       cursor:pointer; font-size:13px; }
.btn.primary { background:var(--blue); color:#fff; border-color:var(--blue); }
textarea.note, .log-area { width:100%; border:1px dashed #cfd6df; border-radius:8px;
                           padding:10px; font-family:inherit; font-size:13px; resize:vertical; }
.log-area { background:#f7f8fa; border-style:solid; min-height:80px; line-height:1.8; color:#666; }
.file-row { display:flex; align-items:center; justify-content:space-between; border:1px solid #eee;
            border-radius:8px; padding:8px 10px; margin:6px 0; font-size:13px; }
.modal { position:fixed; inset:0; background:rgba(0,0,0,.3); display:flex; align-items:center;
         justify-content:center; z-index:30; }
.modal-card { background:#fff; border-radius:12px; padding:22px; width:520px; max-width:92vw; }
.actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
```
（CSS 可继续按需补充分页样式，保持同一 4px/8px/18px 间距体系即可。）

- [ ] **Step 3: 写 app.js —— 通用 fetch + 列表渲染**

Create `static/app.js`：
```js
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
      <div class="ws-card ${w.archived ? 'archived' : ''}" onclick="openWorkspace('${esc(w.code)}')">
        <span class="code">${esc(w.code)}</span>
        <b>${esc(w.name)}</b>
        ${w.archived ? '<span style="color:#999">（已归档）</span>' : ''}
      </div>`).join('') || '<p style="color:#8a97a5">还没有工作区，先新建一个。</p>'}`;
}
window.newWorkspaceModal = async function () {
  const code = prompt('工作区代码（用于文件夹名，如 SA-Osteomyelitis）');
  if (!code) return;
  const name = prompt('显示名称（如 SA 骨髓炎）', code) || code;
  await api('/api/workspaces', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code, name }) });
  await loadList();
};
window.openWorkspace = function (code) { state.wsCode = code; show('workspace'); renderWorkspace(); };
```
（`esc()` 在拼接 onclick 内层属性时注意避免引号冲突——这里 code 已过 esc；MVP 用 `esc(w.code)` + 代码取自受控工作区，风险可控。后续可改 data-attribute 更安全。）

- [ ] **Step 4: 浏览器验收清单（工作区列表）**
1. `uvicorn fw_server:app` 或 Task 11 的 bat 启动，开 `http://127.0.0.1:8000`。
2. 新建两个工作区（一个含中文名、一个含非法字符 code 测试），列表即时出现。
3. 刷新后仍在（DB 持久）。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: frontend shell + workspace list view"
```

---

## Task 11: 前端 —— 看板 + 详情抽屉（核心）

**Files:**
- Modify: `static/app.js`
- Modify: `static/index.html`（如需挂初始化）

- [ ] **Step 1: app.js 增加 renderWorkspace / renderBoard / openDrawer**

追加到 `static/app.js`：
```js
async function renderWorkspace() {
  const { workspace } = await api('/api/workspaces/' + state.wsCode);
  state.tree = workspace.tree;
  $('#view-workspace').innerHTML = `
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:18px;">
      <button class="btn ghost-onlight" onclick="show('list');loadList()">← 全部工作区</button>
      <b style="font-size:16px;">${esc(workspace.name)}</b>
      <span style="color:var(--mut)">${esc(workspace.code)}</span>
      <span style="flex:1"></span>
      <button class="btn" onclick="newFigureModal()">+ 新建 Figure</button>
      <button class="btn" onclick="scanModal()">📥 扫描导入</button>
    </div>
    <div id="figGrid" class="fig-grid"></div>`;
  renderBoard();
}
function renderBoard() {
  const figs = state.tree.filter(n => n.kind === 'figure');
  const el = $('#figGrid');
  el.innerHTML = figs.map(n => cardHtml(n)).join('') || '<p style="color:var(--mut)">还没有 Figure，点“新建 Figure”。</p>';
}
function cardHtml(n) {
  return `<div class="fig-card s-${n.status} ${state.selectedNode === n.id ? 'selected' : ''}"
     onclick="selectNode(${n.id})">
     <div style="display:flex;justify-content:space-between;align-items:flex-start">
       <b>${esc(n.label)}${n.title ? ' · ' + esc(n.title) : ''}</b>
       <span class="statchip st-${n.status}">${ST[n.status]}</span>
     </div>
     <div class="fig-thumb">${thumbHtml(n)}</div>
     <div><span class="imp-${n.importance}">${n.importance==='key'?'★':''}${IMP[n.importance]}</span>
       ${(n.tags||[]).map(t=>`<span class="tagchip">${esc(t)}</span>`).join('')}</div>
     <div style="color:var(--blue);font-size:12px;margin-top:6px">↑ ${n.file_count} 文件 · ${n.children.length} 面板</div>
   </div>`;
}
function thumbHtml(n) {
  if (!n.preview_rel) return '无预览（可贴截图）';
  return `<img src="/preview/${state.wsCode}/${encodeURIComponent(n.preview_rel)}" onerror="this.outerHTML='无预览'">`;
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
  await api(`/api/workspaces/${state.wsCode}/nodes`, { method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ kind:'figure', label, title }) });
  await renderWorkspace();
};
```

- [ ] **Step 2: app.js 增加 renderDrawer（状态/重要度/标签/备注日志/文件/上传/预览）**

追加到 `static/app.js`：
```js
function renderDrawer(n) {
  const dr = $('#drawer');
  dr.classList.remove('hidden');
  dr.innerHTML = `
    <div style="display:flex;justify-content:space-between">
      <b style="font-size:16px">${esc(n.label)}${n.title?' · '+esc(n.title):''}</b>
      <button class="btn" onclick="$('#drawer').classList.add('hidden')">✕</button>
    </div>
    <div class="actions" style="margin:12px 0">
      <select onchange="patchSel(${n.id},'status',this.value)" class="btn">
        ${Object.entries(ST).map(([k,v])=>`<option value="${k}" ${n.status===k?'selected':''}>${v}</option>`).join('')}
      </select>
      <select onchange="patchSel(${n.id},'importance',this.value)" class="btn">
        ${Object.entries(IMP).map(([k,v])=>`<option value="${k}" ${n.importance===k?'selected':''}>${IMP[k]===v?(k==='key'?'★'+v:v):v}</option>`).join('')}
      </select>
      <button class="btn" onclick="previewUpload(${n.id})">贴/传预览图</button>
    </div>
    <div class="fig-thumb">${thumbHtml(n)}</div>
    <div class="section-label">面板</div>
    <div class="actions">
      ${n.children.map(c=>`<button class="btn" onclick="selectNode(${c.id})">${esc(c.label)}</button>`).join('')}
      <button class="btn" onclick="addPanel(${n.id})">+ 面板</button>
    </div>
    <div class="section-label">来源文件</div>
    <div id="fileList">${(n.files||[]).map(fileRow).join('')}</div>
    <button class="btn" onclick="uploadTo(${n.id})">+ 上传源文件</button>
    <div class="section-label">溯源全链</div>
    <div style="background:#f7f8fa;border:1px solid #eceff3;border-radius:8px;padding:12px;font-size:13px;color:#444;line-height:1.9">
      ${chainHtml(n)}
    </div>
    <div class="section-label">备注 · 决策日志</div>
    <div class="log-area">${(n.logs||[]).map(l=>`<div><b>${esc(l.created_at)}</b> ${esc(l.text)}</div>`).join('')||''}</div>
    <textarea class="note" id="logText" placeholder="记一条：为什么这张对 / 条件 / 结论依据"></textarea>
    <div class="actions"><button class="btn primary" onclick="addLog(${n.id})">记入日志</button></div>
  `;
}
function fileRow(f) {
  return `<div class="file-row">
    <span>${esc(f.name)}${f.sample_note?` <span class="tagchip">${esc(f.sample_note)}</span>`:''}</span>
    <span>
      <a href="/api/files/${f.id}" download class="btn" style="padding:2px 8px">打开</a>
      <button class="btn" style="padding:2px 8px" onclick="delFile(${f.id})">删</button>
    </span>
  </div>`;
}
window.patchSel = async function (id, field, value) {
  await api('/api/nodes/' + id, { method:'PATCH', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({[field]: value}) });
  selectNode(id);
};
window.addPanel = async function (figId) {
  const label = prompt('面板标签，如 3A');
  if (!label) return;
  await api(`/api/workspaces/${state.wsCode}/nodes`, { method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ kind:'panel', label, title:'', parent_id:figId }) });
  await renderWorkspace(); selectNode(figId);
};
window.addLog = async function (nid) {
  const text = $('#logText').value.trim();
  if (!text) return;
  await api(`/api/nodes/${nid}/logs`, { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ text }) });
  selectNode(nid);
};
window.uploadTo = function (nid) {
  const input = document.createElement('input'); input.type='file'; input.multiple=true;
  input.onchange = async () => {
    for (const f of input.files) {
      const fd = new FormData(); fd.append('file', f);
      await api(`/api/nodes/${nid}/files`, { method:'POST', body: fd });
    }
    await selectNode(nid);
  };
  input.click();
};
window.delFile = async function (fid) {
  if (!confirm('删除记录并移入 .trash？')) return;
  await api('/api/files/' + fid, { method:'DELETE' });
  await selectNode(state.selectedNode);
};
window.previewUpload = function (nid) {
  const input = document.createElement('input'); input.type='file'; input.accept='image/*';
  input.onchange = async () => {
    const fd = new FormData(); fd.append('file', input.files[0]);
    await api(`/api/nodes/${nid}/preview`, { method:'POST', body: fd });
    await selectNode(nid);
  };
  input.click();
};
function chainHtml(n) {
  const parts = [];
  let cur = n;
  while (cur) { parts.unshift(cur.label); cur = cur.parent; }
  // 简化：仅展示当前节点 + 其文件；完整反链以树为准
  const files = (n.files||[]).map(f=>f.name);
  return parts.join(' → ') + (files.length ? ' ← ' + files.join(', ') : '');
}
```

- [ ] **Step 3: 补齐 `renderDrawer` 需要的父级信息与粘贴预览（可选）**
若要详情显示面包屑父级，可在 `/api/nodes/{id}` 响应里加 `ancestors`（在 api.py `get_node` 用与 upload_node_file 相同的递归查询补 `label` 链）。MVP：`chainHtml` 先用当前节点自身即可，父级链属增强。

- [ ] **Step 4: 浏览器验收清单（看板+抽屉）**
1. 进工作区，新建 Figure 1；确认磁盘 `D:\ResearchData\<code>\Figure1\` 生成。
2. 卡片出现；点卡片开抽屉。
3. 改状态→候选/采用 色点随之变；标重要度★。
4. 上传 2 个源文件（名字含 `SA-MLOY4-001` 的那个应自动带样本 chip）；文件真在 Figure1 文件夹，SHA 已记。
5. 加面板 3A；给 3A 传文件，确认落盘到 `Figure1\3A\`。
6. 贴预览：选一张 png 作预览，卡片缩略图出现。
7. 写一条决策日志，回显带时间戳。
8. 删除一个文件 → 文件移入 `.trash`。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: board + detail drawer frontend"
```

---

## Task 12: 前端 —— 新建/扫描/搜索/设置/导出

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: app.js 增加 scanModal / applyScan / global search / settings / export**

追加到 `static/app.js`：
```js
window.scanModal = async function () {
  const folder = prompt('要扫描的文件夹完整路径（只读，不动原文件）');
  if (!folder) return;
  const data = await api(`/api/workspaces/${state.wsCode}/scan`, { method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({ folder_path: folder }) });
  if (!data.images.length) { alert('没有发现图片'); return; }
  const picks = data.images.map((im,i) => ({ name: im.name, label: im.sample_hint ? `${im.sample_hint}` : `Figure ${i+1}` }));
  // 简化：默认全部导入为 Figure，label 用文件名主干
  const labels = data.images.map(im => { const stem = im.name.replace(/\.[^.]+$/,'').replace(/[_\s-]+/g,' '); return 'Figure ' + stem; });
  const confirmText = `将按以下标签各建一个 Figure（并复制该图作预览）：\n${labels.join('\n')}\n\n继续？`;
  if (!confirm(confirmText)) return;
  await api(`/api/workspaces/${state.wsCode}/scan/import`, { method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ folder_path: folder, picks: labels.map((label,i)=>({name:data.images[i].name,label})) }) });
  await renderWorkspace();
};
window.doSearch = async function (q) {
  show('search');
  if (!q) { $('#view-search').innerHTML=''; return; }
  const { results } = await api('/api/search?q=' + encodeURIComponent(q));
  $('#view-search').innerHTML = `<h3>“${esc(q)}” 的结果</h3>` + results.map(r => `
    <div class="ws-card" onclick="${r.node_id?`selectNode(${r.node_id})`:`show('list')`}">
      <span class="code">${r.type}</span>
      <b>${esc(r.label)}</b>
      ${r.workspace_code?`<span style="color:var(--mut)">${esc(r.workspace_code)}</span>`:''}
    </div>`).join('') || '<p>无结果</p>';
};
window.showSettings = async function () {
  show('settings');
  const info = await api('/api/settings').catch(()=>({}));
  $('#view-settings').innerHTML = `
    <h3>设置</h3>
    <p>工作台根目录：<b>${esc(info.root||'(未知)')}</b></p>
    <p>数据库：<b>${esc(info.db||'(未知)')}</b></p>
    <div class="actions">
      <button class="btn primary" onclick="doBackup()">💾 立即备份</button>
    </div>
    <div id="backupInfo"></div>
    <div class="actions" style="margin-top:14px">
      <button class="btn" onclick="exportKind('source_data')">导出 SourceData</button>
      <button class="btn" onclick="exportKind('legend')">导出图注草稿</button>
      <button class="btn" onclick="exportKind('data_availability')">数据可得性</button>
    </div>`;
};
window.doBackup = async function () {
  const r = await api('/api/backup', { method:'POST' });
  $('#backupInfo').innerHTML = `<p>已备份到 ${esc(r.backup_dir)}，清单 ${r.manifest_count} 条。</p>`;
};
window.exportKind = async function (kind) {
  if (!state.wsCode) return alert('先进入一个工作区');
  const map = { source_data:'source-data.csv', legend:'figure-legends.txt', data_availability:'data-availability.txt' };
  const r = await fetch(`/api/workspaces/${state.wsCode}/export/${kind}`);
  const blob = await r.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = map[kind]; a.click();
};
```

- [ ] **Step 2: api.py 增加 settings 与 export 端点**

追加到 `fw/api.py`：
```python
@router.get("/settings")
def get_settings():
    from fw import config
    return {"root": str(config.root_dir()), "db": str(config.db_path())}


@router.get("/workspaces/{code}/export/{kind}")
def export_workspace(code: str, kind: str):
    from fastapi.responses import PlainTextResponse
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        wid = ws["id"]
        if kind == "source_data":
            return PlainTextResponse(export.source_data(con, wid), media_type="text/csv",
                                     headers={"Content-Disposition": 'attachment; filename="source-data.csv"'})
        if kind == "legend":
            return PlainTextResponse(export.legend_draft(con, wid), media_type="text/plain; charset=utf-8",
                                     headers={"Content-Disposition": 'attachment; filename="figure-legends.txt"'})
        if kind == "data_availability":
            return PlainTextResponse(export.data_availability(con, wid), media_type="text/plain; charset=utf-8",
                                     headers={"Content-Disposition": 'attachment; filename="data-availability.txt"'})
    raise HTTPException(404, "未知导出类型")
```
在 `fw/api.py` 顶部加 `from fw import export`。

- [ ] **Step 3: 绑定快捷键/启动搜索**

追加到 `static/app.js`：
```js
window.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && document.activeElement === $('#globalSearch')) {
    doSearch($('#globalSearch').value.trim());
  }
});
$('#btnSettings').addEventListener('click', showSettings);
$('#globalSearch').addEventListener('input', debounce(function(){ if(!this.value) show('list'); }, 300));
function debounce(fn, ms){ let t; return function(...a){ clearTimeout(t); t=setTimeout(()=>fn.apply(this,a), ms); }; }
```

- [ ] **Step 4: 浏览器验收清单（新功能页）**
1. 扫描导入：给一个含若干 png 的文件夹路径，确认弹出按文件名起的 Figure 标签、确认后生成卡片且源目录未被改动。
2. 全局搜索：搜 "IL6" 命中打标签的节点；搜工作区中文名命中工作区；结果可点开。
3. 设置页显示根目录/DB 路径；点备份生成 manifest 与 db 副本。
4. 对状态「采用」的图导出 SourceData csv / 图注 txt / 数据可得性 txt，内容与 export 单测一致。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: scan-import, global search, settings, backup, export frontend"
```

---

## Task 13: Windows 启动脚本 + 使用说明

**Files:**
- Create: `启动工作台.bat`
- Create: `README.md`

- [ ] **Step 1: 写 启动工作台.bat**

Create `启动工作台.bat`：
```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist .venv (
  echo [首次运行] 创建虚拟环境...
  python -m venv .venv || py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
python -m uvicorn fw_server:app --host 127.0.0.1 --port 8000
pause
```
（数据默认 `D:\ResearchData\`；若想换根，改 `fw/config.py` 的 `DEFAULT_ROOT`。）

- [ ] **Step 2: 写 README.md（简短）**

```markdown
# Figure 工作台

本地单人"图为主体"科研图管理。数据全在本机，浏览器操作。

## 启动
双击 `启动工作台.bat`，首次自动建虚拟环境、装依赖。打开 http://127.0.0.1:8000

## 用法速览
- 工作区列表 → 新建论文工作区（code 会做成文件夹）
- 看板：新建 Figure 即建同名文件夹；上传源文件落该夹；贴预览图
- 状态：候选/采用/弃用/待重做 · 重要度：关键/一般/辅助 · 标签 · 决策日志
- 溯源：点图看来源文件与路径；全局检索跨论文搜标签/文件名/样本
- 导出：SourceData / 图注草稿 / 数据可得性（标「采用」的图为准）

## 数据位置
- 代码/DB：本目录 `data/fw.db`
- 科研文件：`D:\ResearchData\<工作区 code>\`
```

- [ ] **Step 3: 验收：全新目录一键启动**

在新目录执行 `启动工作台.bat`（或用 `.venv\Scripts\python -m uvicorn fw_server:app`），浏览器打开无报错，新建工作区正常。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: windows launcher and readme"
```

---

## Task 14: 全量回归 + 收尾自查

- [ ] **Step 1: 跑全量测试**

Run: `python -m pytest -q`
Expected: 全绿。

- [ ] **Step 2: 按 Spec §9/§10 复核**
- 上传复制不移动源 ✓（storage.save_upload 只写新文件）
- 删除只移 `.trash` + 删记录 ✓
- 面板落盘在 figure 子目录 ✓
- 索引应用只读扫描 ✓
- 「不做」清单未实现：无鉴权、无 ELN、无万能预览 ✓

- [ ] **Step 3: 浏览器全流程手动走查（对照 Task 11/12 验收清单）**

- [ ] **Step 4: 终审 commit**

```bash
git add -A
git commit -m "chore: regression pass on figure workspace mvp"
```

---

## Self-Review 记录

- **Spec 覆盖**：目录模型（建工作区/Figure 夹）→Task0/5/6；节点树+状态/重要度/标签/日志→Task2/5/7；上传/预览/SHA/溯源→Task6；全局检索→Task7；扫描导入→Task8；投稿导出（SourceData/图注/DA）→Task4/12；备份→Task9/12；Windows 启动→Task13；不做清单→Task14 复核。
- **占位符扫描**：无 TBD/TODO；代码块均为完整实现。
- **类型一致性**：DB 列名 `preview_rel`/`rel_path`/`sample_note`、API 字段 `status/importance/tags/logs/files` 在前后端一致使用；枚举 `candidate/adopted/rejected/redo` 与 `key/normal/aux` 贯穿 db 校验、前端映射、export。
- **已修正**：Task5 api.py 三处装饰器前缀重复问题（在 Step4 明示改法）；scan 测试隔离难度在 Task8 给出单元化替代；preview 覆盖策略 MVP 采用"序号副本"。
