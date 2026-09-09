"""FastAPI 路由。相对路径基于工作区文件夹。"""
import csv
import shutil
import sqlite3
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fw import db, storage, naming

router = APIRouter(prefix="/api")


# ---------------- workspaces ----------------
@router.get("/workspaces")
def list_workspaces():
    with db.conn() as con:
        return {"workspaces": [dict(w) for w in db.list_workspaces(con)]}


@router.post("/workspaces")
def create_workspace(body: dict):
    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip() or code
    if not code:
        raise HTTPException(400, "code 不能为空")
    slug = naming.folder_slug(code)
    try:
        with db.conn() as con:
            wid = db.create_workspace(con, code=slug, name=name)
    except sqlite3.IntegrityError:
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
        if parent_id is not None:
            par = db.get_node(con, parent_id)
            if not par or par["workspace_id"] != ws["id"]:
                raise HTTPException(400, "parent 不存在于本工作区")
        if kind == "figure":
            storage.figure_folder(code, label)          # 建图即建夹
        nid = db.create_node(con, ws["id"], kind=kind, label=label, title=title,
                             parent_id=parent_id)
        node = db.get_node(con, nid)
        return {"node": dict(node)}


@router.patch("/nodes/{nid}")
def patch_node(nid: int, body: dict):
    allowed = {"label", "title", "status", "importance", "note"}
    clean = {k: v for k, v in body.items() if k in allowed and v is not None}
    if "status" in clean and clean["status"] not in ("candidate", "adopted", "rejected", "redo"):
        raise HTTPException(400, "bad status")
    if "importance" in clean and clean["importance"] not in ("key", "normal", "aux"):
        raise HTTPException(400, "bad importance")
    with db.conn() as con:
        node = db.get_node(con, nid)
        if not node:
            raise HTTPException(404)
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


# ---------------- files / preview ----------------
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


def _upload_to(con, ws, node_id, data: bytes, filename: str, dest_rel: str):
    """复制字节到 ws 文件夹下的 dest_rel，写 file_item，返回新记录。ws 为 workspace Row。"""
    ws_folder = storage.workspace_folder(ws["code"])
    rel = storage.save_upload(ws_folder, data, filename, dest_rel=dest_rel)
    fid = db.add_file(con, ws["id"], node_id=node_id, rel_path=rel, name=Path(rel).name,
                      ext=Path(rel).suffix.lstrip(".").lower(), size=len(data),
                      sha256=storage.sha256_bytes(data),
                      sample_note=naming.parse_sample_hint(filename))
    return db.get_file(con, fid)


def _figure_ancestor(con, nid):
    """向上找最近的 figure 祖先（含本节点）。返回 Row 或 None。"""
    return con.execute(
        "WITH RECURSIVE up(id,parent_id,label,kind) AS ("
        " SELECT id,parent_id,label,kind FROM node WHERE id=? "
        " UNION ALL SELECT n.id,n.parent_id,n.label,n.kind FROM node n "
        " JOIN up ON n.id=up.parent_id) SELECT id,label FROM up WHERE kind='figure' LIMIT 1",
        (nid,)).fetchone()


@router.post("/nodes/{nid}/files")
async def upload_node_file(nid: int, file: UploadFile = File(...)):
    data = await file.read()
    filename = file.filename or "file"
    with db.conn() as con:
        n = db.get_node(con, nid)
        if not n:
            raise HTTPException(404)
        ws = db.get_workspace(con, n["workspace_id"])
        ws_folder = storage.workspace_folder(ws["code"])
        if n["kind"] == "figure":
            dest_rel = storage.figure_folder(ws["code"], n["label"]).relative_to(ws_folder).as_posix()
        else:
            fig = _figure_ancestor(con, nid)
            dest_rel = (storage.panel_folder(ws["code"], fig["label"], n["label"])
                        .relative_to(ws_folder).as_posix()) if fig else ""
        _upload_to(con, ws, nid, data, filename, dest_rel)
        return {"files": [dict(x) for x in db.node_files(con, nid)]}


@router.post("/workspaces/{code}/files")
async def upload_raw_file(code: str, file: UploadFile = File(...)):
    data = await file.read()
    filename = file.filename or "file"
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        _upload_to(con, ws, None, data, filename, "原始数据")
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
        ws_folder = storage.workspace_folder(ws["code"])
        if n["preview_rel"]:
            storage.move_to_trash(ws_folder, n["preview_rel"])
        if n["kind"] == "figure":
            dest_rel = storage.figure_folder(ws["code"], n["label"]).relative_to(ws_folder).as_posix()
        else:
            dest_rel = "原始数据"
        rel = storage.save_upload(ws_folder, data, "preview.png", dest_rel=dest_rel)
        db.update_node(con, nid, preview_rel=rel)
        return {"ok": True, "preview_rel": rel}


# ---------------- tags / search ----------------
@router.post("/nodes/{nid}/tags")
def add_tag(nid: int, body: dict):
    tag = (body.get("tag") or "").strip()
    if not tag:
        raise HTTPException(400, "空标签")
    with db.conn() as con:
        if not db.get_node(con, nid):
            raise HTTPException(404)
        db.add_tag(con, nid, tag)
        return {"tags": [t["name"] for t in db.node_tags(con, nid)]}


@router.delete("/nodes/{nid}/tags/{tag}")
def del_tag(nid: int, tag: str):
    with db.conn() as con:
        if not db.get_node(con, nid):
            raise HTTPException(404)
        db.remove_tag(con, nid, tag)
    return {"ok": True}


@router.get("/search")
def search(q: str = ""):
    q = q.strip()
    if not q:
        return {"results": []}
    like = f"%{q}%"
    results = []
    with db.conn() as con:
        for ws in con.execute("SELECT * FROM workspace WHERE code LIKE ? OR name LIKE ?",
                              (like, like)).fetchall():
            results.append({"type": "workspace", "workspace_code": ws["code"],
                            "label": ws["name"], "node_id": None, "tag": None, "file_id": None})
        for tag in con.execute("SELECT t.name, nt.node_id FROM tag t "
                               "JOIN node_tag nt ON nt.tag_id=t.id "
                               "WHERE t.name LIKE ? LIMIT 50", (like,)).fetchall():
            results.append({"type": "tag", "workspace_code": None, "label": tag["name"],
                            "node_id": tag["node_id"], "tag": tag["name"], "file_id": None})
        for n in con.execute("SELECT * FROM node WHERE label LIKE ? OR title LIKE ? LIMIT 50",
                             (like, like)).fetchall():
            results.append({"type": "node", "workspace_code": None,
                            "label": f"{n['label']} {n['title']}".strip(),
                            "node_id": n["id"], "tag": None, "file_id": None})
        for f in con.execute("SELECT * FROM file_item WHERE name LIKE ? LIMIT 50",
                             (like,)).fetchall():
            results.append({"type": "file", "workspace_code": None, "label": f["name"],
                            "node_id": f["node_id"], "tag": None, "file_id": f["id"]})
        for r in results:
            if r["node_id"]:
                n = db.get_node(con, r["node_id"])
                if n:
                    ws = db.get_workspace(con, n["workspace_id"])
                    r["workspace_code"] = ws["code"] if ws else None
    return {"results": results}


# ---------------- scan import ----------------
_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}


@router.post("/workspaces/{code}/scan")
def scan_folder(code: str, body: dict):
    folder = Path(body.get("folder_path") or "")
    if not folder.is_dir():
        raise HTTPException(400, "folder_path 无效目录")
    images = []
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in _IMG_EXT:
            images.append({"name": p.name, "size": p.stat().st_size,
                           "sample_hint": naming.parse_sample_hint(p.name)})
    return {"images": images}


@router.post("/workspaces/{code}/scan/import")
def apply_scan(code: str, body: dict):
    """把选中的图片导入为 Figure：复制该图作预览并挂为源文件；源目录只读，其它文件不动。"""
    folder = Path(body.get("folder_path") or "")
    picks = body.get("picks") or []
    if not folder.is_dir() or not picks:
        raise HTTPException(400, "缺 folder_path 或 picks")
    created = []
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        for i, pick in enumerate(picks, start=1):
            name = pick.get("name") or ""
            # 仅接受纯文件名，杜绝通过 name 读目录外文件
            if not name or name in (".", "..") or "/" in name or "\\" in name:
                continue
            src = folder / name
            if not src.is_file():
                continue
            label = pick.get("label") or f"Figure {i}"
            nid = db.create_node(con, ws["id"], kind="figure", label=label, title="")
            ffolder = storage.figure_folder(code, label)
            preview_name = naming.unique_name("preview.png",
                                              [x.name for x in ffolder.iterdir()])
            shutil.copy2(str(src), str(ffolder / preview_name))
            rel_dir = ffolder.relative_to(storage.workspace_folder(code))
            preview_rel = (rel_dir / preview_name).as_posix()
            db.update_node(con, nid, preview_rel=preview_rel)
            db.add_file(con, ws["id"], node_id=nid,
                        rel_path=(rel_dir / preview_name).as_posix(),
                        name=src.name, ext=src.suffix.lstrip(".").lower(),
                        size=src.stat().st_size, sha256=storage.sha256_file(src))
            created.append({"id": nid, "label": label})
    return {"created": created}


# ---------------- backup ----------------
@router.post("/backup")
def run_backup(backup_dir: str = ""):
    """备份：复制 SQLite db 到 target，并生成全量 file_item 清单 manifest.csv。"""
    from fw import config
    target = Path(backup_dir) if backup_dir else (config.root_dir().parent / "backups")
    target.mkdir(parents=True, exist_ok=True)
    db_src = config.db_path()
    if db_src.exists():
        shutil.copy2(str(db_src), str(target / f"fw_{int(time.time())}.db"))
    manifest = []
    with db.conn() as con:
        for f in con.execute("SELECT * FROM file_item").fetchall():
            ws = db.get_workspace(con, f["workspace_id"])
            p = storage.workspace_folder(ws["code"]) / f["rel_path"]
            manifest.append({"name": f["name"], "rel": f["rel_path"],
                             "workspace": ws["code"], "exists": p.exists()})
        # manifest.csv: header workspace,rel_path,name,exists — use csv module so
        # names/rels containing commas or quotes stay well-formed.
        with (target / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["workspace", "rel_path", "name", "exists"])
            for m in manifest:
                w.writerow([m["workspace"], m["rel"], m["name"], m["exists"]])
    return {"backup_dir": str(target), "manifest_count": len(manifest)}
