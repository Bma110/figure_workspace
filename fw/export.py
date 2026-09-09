"""对「已采用」节点生成 SourceData 清单 / 图注草稿 / 数据可得性骨架。

导出只纳入 status='adopted' 的内容。figure 是其面板的容器：某 figure 采用即整幅采用，
其下面板若也采用则并入父 figure 导出行（不单独重复成行）；父 figure 未采用时，孤立的
采用面板仍单独导出。data_availability 的计数取采用 figure 数。"""
from fw import db


def _adopted_nodes(con, wid):
    return con.execute(
        "SELECT * FROM node WHERE workspace_id=? AND status='adopted' ORDER BY id", (wid,)).fetchall()


def _export_roots(con, wid):
    """已采用且父节点未被采用的节点：顶层 figure 行，或父 figure 未采用的孤立 panel 行。"""
    adopted = _adopted_nodes(con, wid)
    adopted_ids = {n["id"] for n in adopted}
    return [n for n in adopted if n["parent_id"] not in adopted_ids]


def source_data(con, wid) -> str:
    """CSV 文本：采用 figure（含其采用面板的文件）或孤立采用 panel → 源文件清单。"""
    lines = ["Figure,File,RelativePath,SHA256,Size"]
    for n in _export_roots(con, wid):
        if n["kind"] == "figure":
            files = con.execute(
                "SELECT * FROM file_item WHERE node_id=? OR node_id IN "
                "(SELECT id FROM node WHERE parent_id=? AND status='adopted') ORDER BY id",
                (n["id"], n["id"])).fetchall()
        else:
            files = con.execute(
                "SELECT * FROM file_item WHERE node_id=? ORDER BY id", (n["id"],)).fetchall()
        for f in files:
            lines.append(f'{n["label"]},{f["name"]},{f["rel_path"]},{f["sha256"]},{f["size"]}')
    return "\n".join(lines)


def legend_draft(con, wid) -> str:
    out = []
    for n in con.execute(
            "SELECT * FROM node WHERE workspace_id=? AND parent_id IS NULL AND kind='figure' "
            "AND status='adopted' ORDER BY id", (wid,)).fetchall():
        note = (n["note"] or "").strip().replace("\n", " ")
        out.append(f'{n["label"]} ({n["title"] or "待补标题"}). {note}')
        for p in db.children(con, nid=n["id"]):
            out.append(f'  {p["label"]} {p["title"] or ""}'.rstrip())
    return "\n".join(out)


def data_availability(con, wid, repo_hint: str = "") -> str:
    ws = con.execute("SELECT * FROM workspace WHERE id=?", (wid,)).fetchone()
    n_figs = con.execute(
        "SELECT COUNT(*) c FROM node WHERE workspace_id=? AND status='adopted' "
        "AND kind='figure'", (wid,)).fetchone()["c"]
    hint = repo_hint or "[填写：原始数据仓库 / DOI 占位]"
    return (f"Data availability.\n\n"
            f"All source data underlying the {n_figs} adopted figure(s) of this manuscript "
            f"({ws['name']}) are provided as Source Data files. Raw sequencing / imaging datasets "
            f"are deposited at {hint}.\n\n"
            f"Uncropped blots and statistical source tables are included with the paper's "
            f"supplementary Source Data file set.")
