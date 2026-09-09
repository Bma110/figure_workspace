def test_upload_to_figure(client):
    client.post("/api/workspaces", json={"code": "P1", "name": "p"})
    nid = client.post("/api/workspaces/P1/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    r = client.post(f"/api/nodes/{nid}/files",
                    files={"file": ("qPCR_SA-MLOY4-001.xlsx", b"data123", "text/plain")})
    assert r.status_code == 200
    f = r.json()["files"][0]
    assert f["sha256"] and f["sample_note"] == "SA-MLOY4-001"
    # 文件真的落盘于 Figure1 文件夹
    from fw import config
    assert (config.root_dir() / "P1" / "Figure1" / "qPCR_SA-MLOY4-001.xlsx").exists()


def test_upload_to_raw(client):
    client.post("/api/workspaces", json={"code": "P2", "name": "p"})
    r = client.post("/api/workspaces/P2/files",
                    files={"file": ("raw.tif", b"\x00\x01", "image/tiff")})
    assert r.status_code == 200 and r.json()["files"][0]["node_id"] is None


def test_download_and_delete(client):
    client.post("/api/workspaces", json={"code": "P3", "name": "p"})
    nid = client.post("/api/workspaces/P3/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    fid = client.post(f"/api/nodes/{nid}/files",
                      files={"file": ("a.txt", b"hello", "text/plain")}).json()["files"][0]["id"]
    dl = client.get(f"/api/files/{fid}")
    assert dl.status_code == 200 and dl.content == b"hello"
    assert client.delete(f"/api/files/{fid}").status_code == 200


def test_paste_preview(client):
    client.post("/api/workspaces", json={"code": "P4", "name": "p"})
    nid = client.post("/api/workspaces/P4/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "x"}).json()["node"]["id"]
    r = client.post(f"/api/nodes/{nid}/preview",
                    files={"file": ("preview.png", b"\x89PNG\r\n", "image/png")})
    assert r.status_code == 200
    node = client.get(f"/api/nodes/{nid}").json()["node"]
    assert node["preview_rel"] == "Figure1/preview.png"
