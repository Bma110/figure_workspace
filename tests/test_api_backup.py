import csv
import urllib.parse

from fw import config


def test_backup_creates_manifest(client, tmp_path):
    backup_dir = tmp_path / "backup"
    client.post("/api/workspaces", json={"code": "B1", "name": "b"})
    nid = client.post("/api/workspaces/B1/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    up = client.post(f"/api/nodes/{nid}/files",
                     files={"file": ("a.txt", b"data", "text/plain")}).json()
    rel_path = up["files"][0]["rel_path"]
    query = urllib.parse.urlencode({"backup_dir": str(backup_dir)})
    r = client.post(f"/api/backup?{query}")
    assert r.status_code == 200
    body = r.json()
    assert body["manifest_count"] == 1
    assert any(p.suffix == ".db" for p in backup_dir.iterdir())
    with (backup_dir / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["workspace", "rel_path", "name", "exists"]
    assert rows[1:] == [["B1", rel_path, "a.txt", "True"]]


def test_backup_flags_missing_file(client, tmp_path):
    backup_dir = tmp_path / "backup"
    client.post("/api/workspaces", json={"code": "B2", "name": "b"})
    nid = client.post("/api/workspaces/B2/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    up = client.post(f"/api/nodes/{nid}/files",
                     files={"file": ("a.txt", b"data", "text/plain")}).json()
    rel_path = up["files"][0]["rel_path"]
    # 直接从磁盘删文件，保留 file_item 行（模拟 DB 有记录但磁盘缺失）
    disk = config.root_dir() / "B2" / rel_path
    disk.unlink()
    query = urllib.parse.urlencode({"backup_dir": str(backup_dir)})
    r = client.post(f"/api/backup?{query}")
    assert r.status_code == 200
    with (backup_dir / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["workspace", "rel_path", "name", "exists"]
    assert rows[1:] == [["B2", rel_path, "a.txt", "False"]]
