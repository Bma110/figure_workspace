from fw import config, db


def _ws(client, code="R1"):
    client.post("/api/workspaces", json={"code": code, "name": "改名"})


def _fig(client, code="R1", label="Figure 1"):
    return client.post(f"/api/workspaces/{code}/nodes",
                       json={"kind": "figure", "label": label}).json()["node"]


def test_rename_figure_moves_folder_and_files(client):
    _ws(client)
    fig = _fig(client)
    fid = client.post(f"/api/nodes/{fig['id']}/files",
                      files={"file": ("a.xlsx", b"data", "text/plain")}).json()["files"][0]["id"]

    r = client.patch(f"/api/nodes/{fig['id']}", json={"label": "Figure 9"})
    assert r.status_code == 200
    assert r.json()["node"]["folder"] == "Figure9"

    root = config.root_dir() / "R1"
    assert not (root / "Figure1").exists()
    assert (root / "Figure9" / "a.xlsx").is_file()
    files = client.get(f"/api/nodes/{fig['id']}").json()["node"]["files"]
    assert files[0]["rel_path"] == "Figure9/a.xlsx"
    assert client.get(f"/api/files/{fid}").content == b"data"

    # 改名后继续上传应落在新文件夹，不再分裂出第二个目录
    client.post(f"/api/nodes/{fig['id']}/files",
                files={"file": ("b.txt", b"more", "text/plain")})
    assert (root / "Figure9" / "b.txt").is_file()
    assert not (root / "Figure1").exists()


def test_rename_figure_moves_preview(client):
    _ws(client)
    fig = _fig(client)
    client.post(f"/api/nodes/{fig['id']}/preview",
                files={"file": ("preview.png", b"\x89PNGdata", "image/png")})
    r = client.patch(f"/api/nodes/{fig['id']}", json={"label": "Figure 9"})
    assert r.status_code == 200
    assert client.get(f"/api/nodes/{fig['id']}").json()["node"]["preview_rel"] == \
        "Figure9/preview.png"
    assert client.get("/api/preview/R1/Figure9/preview.png").content == b"\x89PNGdata"
    assert client.get("/api/preview/R1/Figure1/preview.png").status_code == 404


def test_rename_panel_moves_subfolder_and_file(client):
    _ws(client)
    fig = _fig(client, label="Figure 2")
    panel = client.post("/api/workspaces/R1/nodes",
                        json={"kind": "panel", "label": "2A", "parent_id": fig["id"]}
                        ).json()["node"]
    client.post(f"/api/nodes/{panel['id']}/files",
                files={"file": ("IL6.xlsx", b"x", "text/plain")})

    r = client.patch(f"/api/nodes/{panel['id']}", json={"label": "2B"})
    assert r.status_code == 200
    root = config.root_dir() / "R1"
    assert not (root / "Figure2" / "2A").exists()
    assert (root / "Figure2" / "2B" / "IL6.xlsx").is_file()
    assert client.get(f"/api/nodes/{panel['id']}").json()["node"]["files"][0]["rel_path"] == \
        "Figure2/2B/IL6.xlsx"


def test_rename_to_existing_label_returns_409(client):
    _ws(client)
    _fig(client, label="Figure 1")
    other = _fig(client, label="Figure 2")
    r = client.patch(f"/api/nodes/{other['id']}", json={"label": "figure 1"})
    assert r.status_code == 409
    assert r.json()["detail"]
    root = config.root_dir() / "R1"
    assert (root / "Figure2").is_dir() and (root / "Figure1").is_dir()
    assert client.get(f"/api/nodes/{other['id']}").json()["node"]["label"] == "Figure 2"


def test_rename_to_reserved_folder_gets_suffix(client):
    _ws(client)
    fig = _fig(client)
    r = client.patch(f"/api/nodes/{fig['id']}", json={"label": "原始数据"})
    assert r.status_code == 200
    assert r.json()["node"]["folder"] == "原始数据 (2)"
    root = config.root_dir() / "R1"
    assert (root / "原始数据").is_dir()  # 保留目录不动
    assert (root / "原始数据 (2)").is_dir()


def test_case_only_label_change_renames_folder(client):
    _ws(client)
    fig = _fig(client)
    r = client.patch(f"/api/nodes/{fig['id']}", json={"label": "figure 1"})
    assert r.status_code == 200
    assert r.json()["node"]["folder"] == "figure1"
    assert (config.root_dir() / "R1" / "figure1").is_dir()


def test_rename_shared_legacy_folder_is_rejected(client):
    _ws(client)
    first = _fig(client, label="Figure 1")
    second = _fig(client, label="Figure-1")
    # 模拟旧版遗留：两个节点共用一个文件夹
    with db.conn() as con:
        con.execute("UPDATE node SET folder='Figure1' WHERE id=?", (second["id"],))
    r = client.patch(f"/api/nodes/{first['id']}", json={"label": "Figure 9"})
    assert r.status_code == 409
    assert (config.root_dir() / "R1" / "Figure1").is_dir()
    assert client.get(f"/api/nodes/{first['id']}").json()["node"]["label"] == "Figure 1"


def test_rename_reserved_legacy_folder_is_rejected(client):
    _ws(client)
    fig = _fig(client)
    with db.conn() as con:
        con.execute("UPDATE node SET folder='原始数据' WHERE id=?", (fig["id"],))
    r = client.patch(f"/api/nodes/{fig['id']}", json={"label": "Figure 9"})
    assert r.status_code == 409
    assert client.get(f"/api/nodes/{fig['id']}").json()["node"]["label"] == "Figure 1"


def test_patch_other_fields_still_work(client):
    _ws(client)
    fig = _fig(client)
    r = client.patch(f"/api/nodes/{fig['id']}", json={"status": "adopted"})
    assert r.json()["node"]["status"] == "adopted"


def test_delete_figure_removes_file_records(client):
    _ws(client)
    fig = _fig(client)
    client.post(f"/api/nodes/{fig['id']}/files",
                files={"file": ("a.txt", b"x", "text/plain")})
    assert client.delete(f"/api/nodes/{fig['id']}").status_code == 200
    ws = client.get("/api/workspaces/R1").json()["workspace"]
    assert ws["raw_files"] == []  # 不留指向已进 .trash 文件的幽灵记录
