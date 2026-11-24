"""首次运行自动导入教程素材。

目标是让新用户一开始就能在工作区列表里看到「入门教程」工作区（按 Figure 建成 Figure，
预览与源文件落盘到 workspace 目录），配合 [docs/tutorial.md](../docs/tutorial.md) 与
[docs/tutorial_scans/README.md](../docs/tutorial_scans/README.md) 一起使用。
"""
import shutil
from pathlib import Path

from fw import db, storage

WORKSPACE_NAME = "入门教程"
WORKSPACE_CODE = "tutorial"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "docs" / "tutorial_scans"


def _assets():
    return sorted(ASSETS_DIR.glob("*.png")) if ASSETS_DIR.is_dir() else []


def has_workspace(con) -> bool:
    return _existing(con)


def _existing(con) -> bool:
    row = con.execute(
        "SELECT 1 FROM workspace WHERE code=? OR name=? LIMIT 1", (WORKSPACE_CODE, WORKSPACE_NAME)
    ).fetchone()
    return row is not None


def seed_tutorial_workspace(con):
    """把 docs/tutorial_scans 里的示例图导入为「入门教程」工作区下的若干 Figure。"""
    if _existing(con) or not _assets():
        return None
    ws = db.get_workspace(con, db.create_workspace(con, code=WORKSPACE_CODE, name=WORKSPACE_NAME))
    if not ws:
        return None
    ws_folder = storage.workspace_folder(ws["code"])
    created = 0
    for p in _assets():
        label = p.stem
        nid = db.create_node(con, ws["id"], kind="figure", label=label, title="", folder=label)
        rel = f"{label}/{p.name}"
        dst = storage.ensure_dir(ws_folder, label)
        dst = dst / p.name
        shutil.copy2(p, dst)
        db.add_file(con, ws["id"], rel_path=rel, name=p.name, ext=p.suffix.lstrip(".").lower(),
                    size=dst.stat().st_size, sha256=storage.sha256_file(dst), node_id=nid)
        db.update_node(con, nid, preview_rel=rel)
        db.add_log(con, ws["id"], nid, "自动导入教程素材")
        created += 1
    return ws
