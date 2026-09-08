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
