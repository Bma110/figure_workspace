def test_scan_lists_images_readonly(client, tmp_path):
    src = tmp_path / "figs"
    src.mkdir()
    (src / "F1_microCT.png").write_bytes(b"x")
    (src / "notes.txt").write_bytes(b"y")
    r = client.post("/api/workspaces/NOWHERE/scan", json={"folder_path": str(src)})
    assert r.status_code == 200
    names = [i["name"] for i in r.json()["images"]]
    assert "F1_microCT.png" in names and "notes.txt" not in names


def test_scan_import_creates_figure_copying_only_pick(client, tmp_path):
    from fw import config
    src = tmp_path / "figs"
    src.mkdir()
    (src / "F1_microCT.png").write_bytes(b"\x89PNG\r\n")
    (src / "F2_wb.tif").write_bytes(b"\x89PNG\r\n")
    client.post("/api/workspaces", json={"code": "Scan1", "name": "s"})
    r = client.post("/api/workspaces/Scan1/scan/import", json={
        "folder_path": str(src),
        "picks": [{"name": "F1_microCT.png", "label": "Figure 1"}]})
    assert r.status_code == 200
    created = r.json()["created"]
    assert len(created) == 1 and created[0]["label"] == "Figure 1"
    nid = created[0]["id"]
    node = client.get(f"/api/nodes/{nid}").json()["node"]
    assert node["preview_rel"] == "Figure1/preview.png"
    assert [f["name"] for f in node["files"]] == ["F1_microCT.png"]
    # 源文件夹只读：图片被复制进工作区，源仍原位
    assert (config.root_dir() / "Scan1" / "Figure1" / "preview.png").exists()
    assert (src / "F1_microCT.png").exists() and (src / "F2_wb.tif").exists()
