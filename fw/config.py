"""路径配置：每次调用读 env，便于测试覆盖。"""
import os
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("FW_ROOT", r"D:\ResearchData"))
DEFAULT_DB = Path(os.environ.get("FW_DB", str(Path(__file__).resolve().parent.parent / "data" / "fw.db")))


def root_dir() -> Path:
    return Path(os.environ.get("FW_ROOT", str(DEFAULT_ROOT)))


def db_path() -> Path:
    return Path(os.environ.get("FW_DB", str(DEFAULT_DB)))
