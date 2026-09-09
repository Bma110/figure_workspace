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


def _basename(filename: str) -> str:
    """取末段文件名，容忍 '/' 与 '\\' 分隔，拒绝空/./.. 及含 '..' 段的越界路径。"""
    norm = filename.replace("\\", "/")
    if ".." in norm.split("/"):
        raise ValueError("非法文件名")
    name = norm.rsplit("/", 1)[-1].strip()
    if name in ("", ".", ".."):
        raise ValueError("非法文件名")
    return name


def _dest_dir(ws_folder: Path, dest_rel: str) -> Path:
    ws = ws_folder.resolve()
    if not dest_rel:
        return ws
    rel = dest_rel.replace("\\", "/")
    target = (ws / rel).resolve()
    if not target.is_relative_to(ws):
        raise ValueError("dest_rel 越界")
    return target


def save_upload(ws_folder: Path, data: bytes, filename: str, dest_rel: str = "") -> str:
    """把字节写入 ws_folder 下（dest_rel 为空则根，否则 dest_rel 目录）。返回相对路径。"""
    ws = ws_folder.resolve()
    target_dir = _dest_dir(ws, dest_rel)
    target_dir.mkdir(parents=True, exist_ok=True)
    fname = naming.unique_name(_basename(filename), _list_names(target_dir))
    (target_dir / fname).write_bytes(data)
    return target_dir.relative_to(ws).joinpath(fname).as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def move_to_trash(ws_folder: Path, rel_path: str):
    if not rel_path or rel_path in (".", ".."):
        return
    ws = ws_folder.resolve()
    src = (ws / rel_path).resolve()
    if not src.is_relative_to(ws) or not src.is_file():
        return
    trash = ws / ".trash"
    trash.mkdir(exist_ok=True)
    dest_name = naming.unique_name(src.name, _list_names(trash))
    shutil.move(str(src), str(trash / dest_name))
