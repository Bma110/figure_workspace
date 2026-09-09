"""FastAPI 路由。相对路径基于工作区文件夹。"""
from fastapi import APIRouter, HTTPException
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
    except Exception:
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
        if kind == "figure":
            storage.figure_folder(code, label)          # 建图即建夹
        elif parent_id is not None:
            par = db.get_node(con, parent_id)
            if not par or par["workspace_id"] != ws["id"]:
                raise HTTPException(400, "parent 不存在于本工作区")
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
