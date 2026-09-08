"""文件系统为真源：建工作区/Figure 夹、保存上传(复制+SHA)、trash。"""
import hashlib
import shutil
from pathlib import Path
from fw import config, naming


def workspace_folder(code: str) -> Path:
    p = config.root_dir() / code
    p.mkdir(parents=True, exist_ok=True)
    (p / "原始数据").mkdir(exist_ok=True)
    (p / ".trash").mkdir(exist_ok=True)
    return p


def figure_folder(ws_code: str, label: str) -> Path:
    """Figure 的文件夹：<工作区>/<label 去空格>。返回并确保存在。"""
    p = workspace_folder(ws_code) / naming.folder_slug(label)
    p.mkdir(exist_ok=True)
    return p


def panel_folder(ws_code: str, figure_label: str, panel_label: str) -> Path:
    p = figure_folder(ws_code, figure_label) / naming.folder_slug(panel_label)
    p.mkdir(exist_ok=True)
    return p


def _list_names(folder: Path) -> list[str]:
    return [x.name for x in folder.iterdir()] if folder.exists() else []


def save_upload(ws_folder: Path, data: bytes, filename: str, dest_rel: str = "") -> str:
    """把字节写入 ws_folder 下（dest_rel 为空则根，否则 dest_rel 目录）。返回相对路径。"""
    dest = ws_folder
    if dest_rel:
        dest = ws_folder / dest_rel
    dest.mkdir(parents=True, exist_ok=True)
    fname = naming.unique_name(filename, _list_names(dest))
    (dest / fname).write_bytes(data)
    rel = (Path(dest_rel) / fname).as_posix() if dest_rel else fname
    return rel


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def move_to_trash(ws_folder: Path, rel_path: str):
    src = ws_folder / rel_path
    trash = ws_folder / ".trash"
    trash.mkdir(exist_ok=True)
    if not src.exists():
        return
    dest_name = naming.unique_name(src.name, _list_names(trash))
    shutil.move(str(src), str(trash / dest_name))
