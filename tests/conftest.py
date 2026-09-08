import os
import tempfile
import pytest

_tmp = tempfile.mkdtemp(prefix="fwtest_")
os.environ["FW_ROOT"] = os.path.join(_tmp, "root")
os.environ["FW_DB"] = os.path.join(_tmp, "fw.db")

from fastapi.testclient import TestClient  # noqa: E402
import fw_server  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(fw_server.app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_state():
    # 每个测试前清空 root 与 db，保证隔离
    import shutil
    from fw import config
    root = config.root_dir()
    db = config.db_path()
    if db.exists():
        db.unlink()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    db.parent.mkdir(parents=True, exist_ok=True)
    yield
