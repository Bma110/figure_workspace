from fw import db, export


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
