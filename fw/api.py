"""FastAPI 路由。相对路径基于工作区文件夹。"""
import csv
import shutil
import sqlite3
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, PlainTextResponse
from fw import db, storage, naming, config, export, imaging

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
def get_workspace(code: str, show_archived: int = 0):
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404, "not found")
        wid = ws["id"]
        payload = dict(ws)
        payload["tree"] = db.tree(con, wid, include_archived=bool(show_archived))
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
def _label_key(value: str) -> str:
    return str(value or "").strip().casefold()


def _sibling_folders(con, wid, parent_id, exclude_id=None) -> list[str]:
    rows = con.execute(
        "SELECT folder FROM node WHERE workspace_id=? AND parent_id IS ? AND id<>?",
        (wid, parent_id, exclude_id if exclude_id is not None else -1)).fetchall()
    return [r["folder"] for r in rows]


def _require_label_free(con, wid, parent_id, label, exclude_id=None) -> None:
    """同层级的 label 唯一（大小写不敏感）：Figure 重名 409，面板重名 400。"""
    rows = con.execute(
        "SELECT label FROM node WHERE workspace_id=? AND parent_id IS ? AND id<>?",
        (wid, parent_id, exclude_id if exclude_id is not None else -1)).fetchall()
    if any(_label_key(r["label"]) == _label_key(label) for r in rows):
        raise HTTPException(409 if parent_id is None else 400, f"标签「{label}」已存在")


def _panel_specs(raw) -> list[dict]:
    """规整面板入参，并拒绝同一批里的重名（大小写不敏感）。"""
    panels, seen = [], set()
    for item in raw or []:
        label = item.get("label") if isinstance(item, dict) else item
        label = str(label or "").strip()
        if not label:
            continue
        key = _label_key(label)
        if key in seen:
            raise HTTPException(400, f"面板标签「{label}」重复")
        seen.add(key)
        title = str(item.get("title") or "").strip() if isinstance(item, dict) else ""
        panels.append({"label": label, "title": title})
    return panels


def _create_figure_tree(con, ws, code: str, *, label: str, title: str = "", note: str = "",
                        methods: str = "", panels=()):
    """建 Figure 及其面板：先校验，再建夹、写库；任一步失败清掉新目录并回滚。"""
    _require_label_free(con, ws["id"], None, label)
    folder = naming.allocate_folder(label, _sibling_folders(con, ws["id"], None))
    ws_folder = storage.workspace_folder(code)
    root = storage.ensure_dir(ws_folder, folder)
    try:
        nid = db.create_node(con, ws["id"], kind="figure", label=label, title=title,
                             note=note, methods=methods, folder=folder)
        taken = []
        for p in panels:
            p_folder = naming.allocate_folder(p["label"], taken)
            taken.append(p_folder)
            storage.ensure_dir(root, p_folder)
            db.create_node(con, ws["id"], kind="panel", label=p["label"],
                           title=p["title"], parent_id=nid, folder=p_folder)
    except Exception:
        storage.discard_dir(ws_folder, root)
        raise
    return db.get_node(con, nid)


@router.post("/workspaces/{code}/nodes")
def create_node(code: str, body: dict):
    kind = body.get("kind")
    if kind not in ("figure", "panel"):
        raise HTTPException(400, "kind 需为 figure/panel")
    label = str(body.get("label") or "").strip() or ("Figure" if kind == "figure" else "panel")
    title = str(body.get("title") or "").strip()
    note = str(body.get("note") or "").strip()
    methods = str(body.get("methods") or "").strip()
    parent_id = body.get("parent_id")
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        parent = None
        if parent_id is not None:
            parent = db.get_node(con, parent_id)
            if not parent or parent["workspace_id"] != ws["id"]:
                raise HTTPException(400, "parent 不存在于本工作区")
        if kind == "figure" and parent is not None:
            raise HTTPException(400, "Figure 不能挂在其他节点下")
        if kind == "panel" and parent is None:
            raise HTTPException(400, "面板需要 parent_id")
        _require_label_free(con, ws["id"], parent_id, label)
        folder = naming.allocate_folder(label, _sibling_folders(con, ws["id"], parent_id))
        ws_folder = storage.workspace_folder(code)
        rel = folder if kind == "figure" else f"{db.node_rel_dir(con, parent)}/{folder}"
        target = storage.ensure_dir(ws_folder, rel)
        try:
            nid = db.create_node(con, ws["id"], kind=kind, label=label, title=title,
                                 parent_id=parent_id, note=note, methods=methods, folder=folder)
        except Exception:
            storage.discard_dir(ws_folder, target)
            raise
        return {"node": dict(db.get_node(con, nid))}


@router.post("/workspaces/{code}/figures")
def create_figure(code: str, body: dict):
    """原子建图：Figure、面板、文件夹一次完成；失败不留下半成品。"""
    label = str(body.get("label") or "").strip()
    if not label:
        raise HTTPException(400, "label 不能为空")
    panels = _panel_specs(body.get("panels"))
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404)
        node = _create_figure_tree(
            con, ws, code, label=label,
            title=str(body.get("title") or "").strip(),
            note=str(body.get("note") or "").strip(),
            methods=str(body.get("methods") or "").strip(),
            panels=panels)
        return {"node": dict(node)}


def _folder_shared(con, wid, node) -> bool:
    """旧数据里是否有同层节点共用这个文件夹（新数据不会发生）。"""
    return con.execute(
        "SELECT 1 FROM node WHERE workspace_id=? AND id<>? AND folder=? AND parent_id IS ?"
        " LIMIT 1", (wid, node["id"], node["folder"], node["parent_id"])).fetchone() is not None


def _is_reserved_root(rel: str) -> bool:
    """节点文件夹是否正好占用了工作区保留目录（旧数据才可能）。"""
    return bool(rel) and rel.casefold() in {r.casefold() for r in naming.RESERVED_FOLDERS}


def _rename_path(old_path: Path, new_path: Path) -> None:
    """目录改名；仅大小写不同时借助临时名，兼容大小写不敏感的文件系统。"""
    if str(old_path).casefold() == str(new_path).casefold():
        tmp = old_path.with_name(old_path.name + ".__renaming__")
        old_path.rename(tmp)
        tmp.rename(new_path)
    else:
        old_path.rename(new_path)


def _rename_node(con, ws, node, new_label: str) -> None:
    """换 label 时同步改文件夹与已登记路径；磁盘改名失败则不动数据库。"""
    _require_label_free(con, ws["id"], node["parent_id"], new_label, exclude_id=node["id"])
    old_rel = db.node_rel_dir(con, node)
    if not old_rel:
        raise HTTPException(409, "节点没有可同步的文件夹")
    taken = _sibling_folders(con, ws["id"], node["parent_id"], exclude_id=node["id"])
    new_folder = naming.allocate_folder(new_label, taken)
    if new_folder == node["folder"]:
        db.update_node(con, node["id"], label=new_label)
        return
    if _folder_shared(con, ws["id"], node):
        raise HTTPException(409, "该节点与其它节点共用旧文件夹，改名可能误移对方文件；请先手动整理文件夹")
    if _is_reserved_root(old_rel):
        raise HTTPException(409, "该节点占用了保留目录名，无法安全改名；请先手动整理文件夹")
    parent = db.get_node(con, node["parent_id"]) if node["parent_id"] else None
    parent_rel = db.node_rel_dir(con, parent) if parent else ""
    new_rel = f"{parent_rel}/{new_folder}" if parent_rel else new_folder
    ws_folder = storage.workspace_folder(ws["code"])
    old_path = storage.resolve_in_workspace(ws_folder, old_rel)
    new_path = storage.resolve_in_workspace(ws_folder, new_rel)
    case_only = old_rel.casefold() == new_rel.casefold()
    if new_path.exists() and not case_only:
        raise HTTPException(409, f"文件夹「{new_folder}」已存在")
    if old_path.exists():
        try:
            _rename_path(old_path, new_path)
        except OSError as exc:
            raise HTTPException(409, f"文件夹改名失败：{exc}")
    try:
        db.update_node(con, node["id"], label=new_label, folder=new_folder)
        db.repath_prefix(con, ws["id"], old_rel, new_rel)
    except Exception:
        if new_path.exists():
            try:
                _rename_path(new_path, old_path)  # 数据库回滚，磁盘也改回去
            except OSError:
                pass
        raise


@router.patch("/nodes/{nid}")
def patch_node(nid: int, body: dict):
    allowed = {"label", "title", "status", "importance", "note", "methods", "archived"}
    clean = {k: v for k, v in body.items() if k in allowed and v is not None}
    if "status" in clean and clean["status"] not in ("candidate", "adopted", "rejected", "redo"):
        raise HTTPException(400, "bad status")
    if "importance" in clean and clean["importance"] not in ("key", "normal", "aux"):
        raise HTTPException(400, "bad importance")
    with db.conn() as con:
        node = db.get_node(con, nid)
        if not node:
            raise HTTPException(404)
        if "label" in clean:
            raw_label = clean.pop("label")
            if not isinstance(raw_label, str):
                raise HTTPException(400, "label 需为字符串")
            new_label = raw_label.strip()
            if new_label and new_label != node["label"]:
                ws = db.get_workspace(con, node["workspace_id"])
                _rename_node(con, ws, node, new_label)
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
    """删节点：库记录级联清掉，磁盘上对应的文件夹移进 .trash（可找回）。"""
    with db.conn() as con:
        node = db.get_node(con, nid)
        if not node:
            raise HTTPException(404)
        ws = db.get_workspace(con, node["workspace_id"])
        ws_folder = storage.workspace_folder(ws["code"])
        rel = db.node_rel_dir(con, node)
        # 旧版按 label slug 建夹，可能出现两个节点共用一个文件夹。共用时不动整个目录，
        # 只把本节点子树登记的文件逐个移进 .trash，避免误伤对方。
        shared = con.execute(
            "SELECT 1 FROM node WHERE workspace_id=? AND id<>? AND folder=? AND parent_id IS ?"
            " LIMIT 1", (ws["id"], nid, node["folder"], node["parent_id"])).fetchone()
        ids = _descendant_ids(con, nid)
        if rel and not shared and not _is_reserved_root(rel):
            storage.move_dir_to_trash(
                ws_folder, storage.resolve_in_workspace(ws_folder, rel))
        else:
            for did in ids:
                for f in db.node_files(con, did):
                    storage.move_to_trash(ws_folder, f["rel_path"])
                child = db.get_node(con, did)
                if child and child["preview_rel"]:
                    storage.move_to_trash(ws_folder, child["preview_rel"])
        if ids:
            con.execute(
                f"DELETE FROM file_item WHERE node_id IN ({','.join('?' * len(ids))})", ids)
        db.delete_node(con, nid)
    return {"ok": True}


def _descendant_ids(con, nid) -> list[int]:
    """自身 + 全部后代 id（广度优先）。"""
    ids, queue = [], [nid]
    while queue:
        cur = queue.pop(0)
        ids.append(cur)
        queue.extend(c["id"] for c in db.children(con, nid=cur))
    return ids


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
        d["ancestors"] = db.ancestors(con, nid)
        # 子图在抽屉里要显示文件数，前端才能把子图文件计入本图。
        d["children"] = []
        for x in db.children(con, nid=nid):
            c = dict(x)
            c["file_count"] = db.file_count(con, x["id"])
            c["tags"] = [t["name"] for t in db.node_tags(con, x["id"])]
            d["children"].append(c)
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
        dest_rel = db.node_rel_dir(con, n) or ""
        if dest_rel:
            storage.ensure_dir(ws_folder, dest_rel)
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
        try:
            path = storage.resolve_in_workspace(
                storage.workspace_folder(ws["code"]), f["rel_path"])
        except ValueError:
            raise HTTPException(400, "非法路径")
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
    ext = Path(file.filename or "").suffix.lower()
    if ext and imaging.needs_conversion(ext):
        try:
            data = imaging.to_png(data)  # 浏览器渲染不了的格式（tif 等）转成 PNG 再存
        except Exception:
            raise HTTPException(400, f"无法转换的图片格式：{ext}")
    with db.conn() as con:
        n = db.get_node(con, nid)
        if not n:
            raise HTTPException(404)
        ws = db.get_workspace(con, n["workspace_id"])
        ws_folder = storage.workspace_folder(ws["code"])
        if n["preview_rel"]:
            storage.move_to_trash(ws_folder, n["preview_rel"])
        # 预览图跟着节点走：Figure 落自己的文件夹，面板落父 Figure 下的面板子文件夹。
        dest_rel = db.node_rel_dir(con, n)
        if not dest_rel:
            raise HTTPException(400, "节点缺少文件夹，无法保存预览")
        storage.ensure_dir(ws_folder, dest_rel)
        rel = storage.save_upload(ws_folder, data, "preview.png", dest_rel=dest_rel)
        db.update_node(con, nid, preview_rel=rel)
        return {"ok": True, "preview_rel": rel}


@router.get("/preview/{code}/{rel:path}")
def serve_preview(code: str, rel: str):
    """回传工作区内文件的原始字节，供缩略图 <img> 使用。仅限已登记工作区。"""
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
    if not ws:
        raise HTTPException(404)
    try:
        path = storage.resolve_in_workspace(storage.workspace_folder(code), rel)
    except ValueError:
        raise HTTPException(400, "非法路径")
    if not path.is_file():
        raise HTTPException(404, "预览不存在")
    return FileResponse(str(path))


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
    created, skipped = [], []
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
            label = (pick.get("label") or f"Figure {i}").strip()
            try:
                fig = _create_figure_tree(con, ws, code, label=label, title="")
            except HTTPException as exc:
                if exc.status_code == 409:
                    skipped.append({"name": name, "label": label, "reason": "label_exists"})
                    continue
                raise
            nid = fig["id"]
            rel_dir = fig["folder"]
            ffolder = storage.ensure_dir(storage.workspace_folder(code), rel_dir)

            # 原图按原名留档（SHA 对得上原文件，溯源可信）
            orig_name = naming.unique_name(src.name, [x.name for x in ffolder.iterdir()])
            shutil.copy2(str(src), str(ffolder / orig_name))
            orig_rel = f"{rel_dir}/{orig_name}"
            db.add_file(con, ws["id"], node_id=nid, rel_path=orig_rel,
                        name=src.name, ext=src.suffix.lstrip(".").lower(),
                        size=src.stat().st_size, sha256=storage.sha256_file(src))

            # 缩略图：可渲染的就直接用原图，否则转成真 PNG。
            # 转不了（文件损坏等）就留空，不让整批导入失败。
            preview_rel = orig_rel
            if imaging.needs_conversion(src.suffix):
                try:
                    png_name = naming.unique_name("preview.png", [x.name for x in ffolder.iterdir()])
                    (ffolder / png_name).write_bytes(imaging.to_png(src.read_bytes()))
                    preview_rel = f"{rel_dir}/{png_name}"
                except Exception:
                    preview_rel = None
            db.update_node(con, nid, preview_rel=preview_rel)
            created.append({"id": nid, "label": label})
    return {"created": created, "skipped": skipped}


# ---------------- settings / export ----------------
@router.get("/settings")
def get_settings():
    return {"root": str(config.root_dir()), "db": str(config.db_path())}


_EXPORTS = {
    "source_data": (export.source_data, "source-data.csv"),
    "legend": (export.legend_draft, "figure-legends.txt"),
    "data_availability": (export.data_availability, "data-availability.txt"),
}


@router.get("/workspaces/{code}/export/{kind}")
def export_workspace(code: str, kind: str):
    """对「已采用」节点导出 SourceData / 图注草稿 / 数据可得性文本。"""
    if kind not in _EXPORTS:
        raise HTTPException(404, "未知导出类型")
    fn, fname = _EXPORTS[kind]
    with db.conn() as con:
        ws = con.execute("SELECT * FROM workspace WHERE code=?", (code,)).fetchone()
        if not ws:
            raise HTTPException(404, "工作区不存在")
        body = fn(con, ws["id"])
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ---------------- backup ----------------
@router.post("/backup")
def run_backup(backup_dir: str = ""):
    """备份：复制 SQLite db 到 target，并生成全量 file_item 清单 manifest.csv。"""
    target = Path(backup_dir) if backup_dir else (config.root_dir().parent / "backups")
    target.mkdir(parents=True, exist_ok=True)
    db_src = config.db_path()
    if db_src.exists():
        db_name = naming.unique_name(f"fw_{int(time.time())}.db",
                                     [p.name for p in target.glob("fw_*.db")])
        shutil.copy2(str(db_src), str(target / db_name))
    manifest = []
    with db.conn() as con:
        for f in con.execute("SELECT * FROM file_item").fetchall():
            ws = db.get_workspace(con, f["workspace_id"])
            p = config.root_dir() / ws["code"] / f["rel_path"]
            manifest.append({"name": f["name"], "rel_path": f["rel_path"],
                             "workspace": ws["code"], "exists": p.exists()})
        # manifest.csv: header workspace,rel_path,name,exists — use csv module so
        # names/rels containing commas or quotes stay well-formed.
        with (target / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["workspace", "rel_path", "name", "exists"])
            for m in manifest:
                w.writerow([m["workspace"], m["rel_path"], m["name"], m["exists"]])
    return {"backup_dir": str(target), "manifest_count": len(manifest)}
