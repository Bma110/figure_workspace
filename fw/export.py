"""对「已采用」节点生成 SourceData 清单 / 图注草稿 / 数据可得性骨架。

投稿导出以 status='adopted' 为门槛，figure 是整幅进稿的容器：
- legend_draft 只列已采用 figure，并把其全部子面板（状态仅供参考）作为缩进行，
  因为 figure 采用即整幅（含其面板）进入投稿。
- source_data 每行一个导出口径根：已采用 figure 行并入其自身及同样已采用子面板的
  源文件（候选/弃用面板文件不进入 SourceData）；父 figure 未采用时，孤立的已采用
  panel 单独成行。
- data_availability 的计数取已采用 figure 数。
"""
from io import StringIO
import csv

from fw import db


def _csv_text(header, rows):
    """CSV 文本：文件名/路径可能含逗号，用标准 csv 库输出。"""
    buf = StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().rstrip("\n")


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
    rows = []
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
            # Panel 行用 Kind 区分；Figure 行合并其子图的文件，清单更可追溯。
            kind = "panel" if (n["kind"] == "panel" or f["node_id"] != n["id"]) else "figure"
            rows.append([n["label"], kind, f["name"], f["rel_path"], f["sha256"], f["size"]])
    return _csv_text(["Node", "Kind", "File", "RelativePath", "SHA256", "Size"], rows)


def legend_draft(con, wid) -> str:
    out = []
    for n in con.execute(
            "SELECT * FROM node WHERE workspace_id=? AND parent_id IS NULL AND kind='figure' "
            "AND status='adopted' ORDER BY id", (wid,)).fetchall():
        note = (n["note"] or "").strip().replace("\n", " ").strip()
        line = f'{n["label"]} ({n["title"] or "待补标题"}).'
        if note:
            line += f' {note}'
        out.append(line)
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
            f"Source Data files for the {n_figs} adopted figure(s) of this manuscript "
            f"({ws['name']}) are available. Raw sequencing / imaging datasets are deposited at {hint}.\n\n"
            f"Uncropped blots and statistical source tables are included in the supplementary "
            f"Source Data file set.")
