"""对「已采用」节点生成 SourceData 清单 / 图注草稿 / 数据可得性骨架。"""
from fw import db


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
