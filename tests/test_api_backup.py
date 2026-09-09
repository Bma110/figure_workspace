import urllib.parse


def test_backup_creates_manifest(client, tmp_path):
    from fw import config
    backup_dir = tmp_path / "backup"
    client.post("/api/workspaces", json={"code": "B1", "name": "b"})
    nid = client.post("/api/workspaces/B1/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    client.post(f"/api/nodes/{nid}/files",
                files={"file": ("a.txt", b"data", "text/plain")})
    query = urllib.parse.urlencode({"backup_dir": str(backup_dir)})
    r = client.post(f"/api/backup?{query}")
    assert r.status_code == 200
    body = r.json()
    assert body["manifest_count"] == 1
    assert any(p.suffix == ".db" for p in backup_dir.iterdir())
