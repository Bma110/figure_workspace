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


def test_delete_figure_cascades_subtree_and_sets_file_node_null():
    with db.conn() as con:
        wid = db.create_workspace(con, code="C1", name="c")
        fig = db.create_node(con, wid, "figure", "Figure 1", "x")
        pan = db.create_node(con, wid, "panel", "3A", "y", parent_id=fig)
        db.add_file(con, wid, node_id=pan, rel_path="Figure1/3A/a.txt", name="a.txt",
                    ext="txt", size=1, sha256="aa")
        db.delete_node(con, fig)
    with db.conn() as con:
        assert db.get_node(con, fig) is None
        assert db.get_node(con, pan) is None
        f = con.execute("SELECT * FROM file_item").fetchall()
        assert len(f) == 1 and f[0]["node_id"] is None


def test_remove_tag_removes_link():
    with db.conn() as con:
        wid = db.create_workspace(con, code="C2", name="c")
        nid = db.create_node(con, wid, "figure", "Figure 1", "x")
        db.add_tag(con, nid, "IL6")
        db.remove_tag(con, nid, "IL6")
        assert db.node_tags(con, nid) == []


def test_preview_rel_roundtrip():
    with db.conn() as con:
        wid = db.create_workspace(con, code="C3", name="c")
        nid = db.create_node(con, wid, "figure", "Figure 1", "x")
        db.update_node(con, nid, preview_rel="Figure1/preview.png")
    with db.conn() as con:
        assert db.get_node(con, nid)["preview_rel"] == "Figure1/preview.png"


def test_workspace_delete_cascades_nodes():
    with db.conn() as con:
        wid = db.create_workspace(con, code="C4", name="c")
        db.create_node(con, wid, "figure", "Figure 1", "x")
        db.add_file(con, wid, node_id=None, rel_path="原始数据/a.bin", name="a.bin",
                    ext="bin", size=1, sha256="aa")
        con.execute("DELETE FROM workspace WHERE id=?", (wid,))
    with db.conn() as con:
        assert con.execute("SELECT COUNT(*) c FROM node").fetchone()["c"] == 0
        assert con.execute("SELECT COUNT(*) c FROM file_item").fetchone()["c"] == 0
