from fw import config, db


def _ws(client, code="A1"):
    client.post("/api/workspaces", json={"code": code, "name": "原子建图"})


def test_atomic_create_with_panels(client):
    _ws(client)
    r = client.post("/api/workspaces/A1/figures", json={
        "label": "Figure 1", "title": "骨破坏", "note": "说明", "methods": "统计",
        "panels": ["1A", {"label": "1B", "title": "IL6"}]})
    assert r.status_code == 200
    node = r.json()["node"]
    assert node["folder"] == "Figure1" and node["title"] == "骨破坏"

    tree = client.get("/api/workspaces/A1").json()["workspace"]["tree"]
    assert [c["label"] for c in tree[0]["children"]] == ["1A", "1B"]
    root = config.root_dir() / "A1"
    assert (root / "Figure1" / "1A").is_dir()
    assert (root / "Figure1" / "1B").is_dir()


def test_atomic_duplicate_label_leaves_no_folder(client):
    _ws(client)
    first = client.post("/api/workspaces/A1/figures",
                        json={"label": "Figure 1"}).json()["node"]
    r = client.post("/api/workspaces/A1/figures", json={"label": "figure 1"})
    assert r.status_code == 409
    root = config.root_dir() / "A1"
    assert not (root / "Figure1 (2)").exists()
    tree = client.get("/api/workspaces/A1").json()["workspace"]["tree"]
    assert [n["id"] for n in tree] == [first["id"]]


def test_atomic_duplicate_panel_labels_rejected_without_trace(client):
    _ws(client)
    r = client.post("/api/workspaces/A1/figures",
                    json={"label": "Figure 1", "panels": ["1A", "1a"]})
    assert r.status_code == 400
    assert not (config.root_dir() / "A1" / "Figure1").exists()
    assert client.get("/api/workspaces/A1").json()["workspace"]["tree"] == []


def test_atomic_reserved_label_gets_suffix(client):
    _ws(client)
    node = client.post("/api/workspaces/A1/figures",
                       json={"label": "原始数据"}).json()["node"]
    assert node["folder"] == "原始数据 (2)"


def test_scan_import_skips_existing_label(client, tmp_path):
    _ws(client)
    src = tmp_path / "figs"
    src.mkdir()
    (src / "a.png").write_bytes(b"\x89PNG-a")
    picks = [{"name": "a.png", "label": "Figure A"}]
    first = client.post("/api/workspaces/A1/scan/import",
                        json={"folder_path": str(src), "picks": picks}).json()
    assert len(first["created"]) == 1 and first["skipped"] == []

    again = client.post("/api/workspaces/A1/scan/import",
                        json={"folder_path": str(src), "picks": picks}).json()
    assert again["created"] == []
    assert again["skipped"] == [{"name": "a.png", "label": "Figure A",
                                 "reason": "label_exists"}]
    assert not (config.root_dir() / "A1" / "FigureA (2)").exists()


def test_delete_reserved_legacy_folder_moves_only_its_files(client):
    _ws(client)
    fig = client.post("/api/workspaces/A1/nodes",
                      json={"kind": "figure", "label": "Figure 1"}).json()["node"]
    client.post(f"/api/nodes/{fig['id']}/files",
                files={"file": ("a.txt", b"node", "text/plain")})
    client.post("/api/workspaces/A1/files",
                files={"file": ("raw.txt", b"raw", "text/plain")})
    with db.conn() as con:
        con.execute("UPDATE node SET folder='原始数据' WHERE id=?", (fig["id"],))
    assert client.delete(f"/api/nodes/{fig['id']}").status_code == 200
    root = config.root_dir() / "A1"
    assert (root / "原始数据" / "raw.txt").is_file()
    assert not (root / "原始数据" / "a.txt").exists()
    assert any((root / ".trash").glob("a.txt"))


def test_download_rejects_path_outside_workspace(client):
    _ws(client)
    fig = client.post("/api/workspaces/A1/nodes",
                      json={"kind": "figure", "label": "Figure 1"}).json()["node"]
    fid = client.post(f"/api/nodes/{fig['id']}/files",
                      files={"file": ("a.txt", b"x", "text/plain")}).json()["files"][0]["id"]
    (config.root_dir().parent / "secret.txt").write_bytes(b"SECRET")
    with db.conn() as con:
        con.execute("UPDATE file_item SET rel_path='../secret.txt' WHERE id=?", (fid,))
    assert client.get(f"/api/files/{fid}").status_code == 400
