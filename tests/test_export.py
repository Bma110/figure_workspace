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


def _seed_mixed(con):
    """一采用图带文件 + 一候选图带文件 + 采用图下挂 采用面板(带文件) 与 候选面板(带文件)。"""
    wid = db.create_workspace(con, code="M", name="M 项目")
    fig = db.create_node(con, wid, "figure", "Figure 1", "好图", status="adopted", importance="key")
    cand = db.create_node(con, wid, "figure", "Figure 2", "备选", status="candidate")
    db.add_file(con, wid, node_id=fig, rel_path="F1/own.xlsx", name="own.xlsx", ext="xlsx",
                size=1, sha256="o1")
    db.add_file(con, wid, node_id=cand, rel_path="F2/cand.xlsx", name="cand.xlsx", ext="xlsx",
                size=1, sha256="c1")
    pa = db.create_node(con, wid, "panel", "1A", "", parent_id=fig, status="adopted")
    pc = db.create_node(con, wid, "panel", "1C", "", parent_id=fig, status="candidate")
    db.add_file(con, wid, node_id=pa, rel_path="F1/panelA.xlsx", name="panelA.xlsx", ext="xlsx",
                size=1, sha256="pA")
    db.add_file(con, wid, node_id=pc, rel_path="F1/panelC.xlsx", name="panelC.xlsx", ext="xlsx",
                size=1, sha256="pC")
    return wid


def test_source_data_excludes_non_adopted_figure_and_children():
    with db.conn() as con:
        wid = _seed_mixed(con)
        rows = export.source_data(con, wid)
        assert "own.xlsx" in rows and "panelA.xlsx" in rows
        assert "cand.xlsx" not in rows and "panelC.xlsx" not in rows


def test_source_data_folds_adopted_child_into_figure_row():
    with db.conn() as con:
        wid = _seed_mixed(con)
        rows = export.source_data(con, wid)
        # RelativePath 列会回显文件名，故按完整路径计数：该文件只列一行（并入父 Figure 行，无重复 1A 行）
        assert rows.count("F1/panelA.xlsx") == 1


def test_legend_draft_excludes_non_adopted_figure():
    with db.conn() as con:
        wid = _seed_mixed(con)
        text = export.legend_draft(con, wid)
        assert "Figure 1" in text and "Figure 2" not in text
