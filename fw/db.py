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
 archived INTEGER NOT NULL DEFAULT 0,
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


# 老库缺的列：CREATE TABLE IF NOT EXISTS 不会补，需显式 ALTER。
_COLUMNS = {"node": {"archived": "INTEGER NOT NULL DEFAULT 0"}}


def _migrate(con):
    """幂等补列：给已存在的旧表加新列。"""
    for table, cols in _COLUMNS.items():
        have = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


class conn:
    """上下文管理器：打开连接 → init schema → 提交 → 关闭。"""

    def __enter__(self):
        self._con = connect()
        self._con.executescript(_SCHEMA)
        _migrate(self._con)
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
                preview_rel=None, archived=None):
    sets, vals = [], []
    for col in ("label", "title", "status", "importance", "note", "preview_rel", "archived"):
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


def tree(con, wid, include_archived=False):
    rows = con.execute("SELECT * FROM node WHERE workspace_id=? ORDER BY id", (wid,)).fetchall()
    by_parent = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(dict(r))
    roots = by_parent.get(None, [])

    def build(nodes):
        kept = []
        for n in nodes:
            if not include_archived and n["archived"]:
                continue  # 隐藏的节点连同其子树整体剪掉
            n["children"] = build(by_parent.get(n["id"], []))
            n["file_count"] = con.execute(
                "SELECT COUNT(*) c FROM file_item WHERE node_id=?", (n["id"],)).fetchone()["c"]
            n["tags"] = [t["name"] for t in node_tags(con, n["id"])]
            kept.append(n)
        return kept

    return build(roots)


def ancestors(con, nid):
    """自顶向下的祖先链（不含自身），用于面包屑。"""
    rows = con.execute(
        "WITH RECURSIVE up(id,parent_id,label,kind) AS ("
        " SELECT id,parent_id,label,kind FROM node WHERE id=? "
        " UNION ALL SELECT n.id,n.parent_id,n.label,n.kind FROM node n "
        " JOIN up ON n.id=up.parent_id) "
        "SELECT id,label,kind FROM up WHERE id<>? ORDER BY id", (nid, nid)).fetchall()
    return [dict(r) for r in rows]


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
