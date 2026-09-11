import sqlite3

from fw import config, db

# 老版本 node 表：没有 archived 列。
_OLD_NODE = """
CREATE TABLE node(
 id INTEGER PRIMARY KEY,
 workspace_id INTEGER NOT NULL,
 parent_id INTEGER,
 kind TEXT NOT NULL,
 label TEXT NOT NULL DEFAULT '',
 title TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'candidate',
 importance TEXT NOT NULL DEFAULT 'normal',
 note TEXT NOT NULL DEFAULT '',
 preview_rel TEXT,
 created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
 updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
"""


def test_migrate_adds_archived_to_existing_db(client):
    con = sqlite3.connect(str(config.db_path()))
    con.executescript(_OLD_NODE)
    con.execute("INSERT INTO node(workspace_id,kind,label) VALUES(1,'figure','Figure 1')")
    con.commit()
    con.close()

    with db.conn() as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(node)")}
        assert "archived" in cols
        row = c.execute("SELECT archived FROM node WHERE label='Figure 1'").fetchone()
        assert row["archived"] == 0  # 老行补默认值，不丢数据

    # 幂等：再开一次不报错
    with db.conn() as c:
        assert "archived" in {r["name"] for r in c.execute("PRAGMA table_info(node)")}
