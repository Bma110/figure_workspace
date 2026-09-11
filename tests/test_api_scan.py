import hashlib

from PIL import Image


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
    # 可渲染格式：原图按原名留档，缩略图直接指向它（不重复存文件）
    assert node["preview_rel"] == "Figure1/F1_microCT.png"
    assert [f["name"] for f in node["files"]] == ["F1_microCT.png"]
    # 源文件夹只读：图片被复制进工作区，源仍原位
    assert (config.root_dir() / "Scan1" / "Figure1" / "F1_microCT.png").exists()
    assert (src / "F1_microCT.png").exists() and (src / "F2_wb.tif").exists()


def test_scan_import_corrupt_tif_still_imports(client, tmp_path):
    # 坏图不能让整批导入失败：原图照样留档，只是没有缩略图
    src = tmp_path / "figs"
    src.mkdir()
    (src / "broken.tif").write_bytes(b"not a real tiff")
    client.post("/api/workspaces", json={"code": "Scan3", "name": "s"})
    r = client.post("/api/workspaces/Scan3/scan/import", json={
        "folder_path": str(src), "picks": [{"name": "broken.tif", "label": "Figure B"}]})
    assert r.status_code == 200
    node = client.get(f"/api/nodes/{r.json()['created'][0]['id']}").json()["node"]
    assert node["preview_rel"] is None
    assert [f["name"] for f in node["files"]] == ["broken.tif"]


def test_scan_import_tif_stores_original_plus_png_thumbnail(client, tmp_path):
    from fw import config
    src = tmp_path / "figs"
    src.mkdir()
    tif_bytes = tmp_path / "src.tif"
    Image.new("L", (12, 8), color=200).save(tif_bytes, format="TIFF")
    (src / "gyh40x.tif").write_bytes(tif_bytes.read_bytes())

    client.post("/api/workspaces", json={"code": "Scan2", "name": "s"})
    r = client.post("/api/workspaces/Scan2/scan/import", json={
        "folder_path": str(src),
        "picks": [{"name": "gyh40x.tif", "label": "Figure T"}]})
    assert r.status_code == 200
    nid = r.json()["created"][0]["id"]
    node = client.get(f"/api/nodes/{nid}").json()["node"]

    # 缩略图是真正的 PNG，浏览器能解
    assert node["preview_rel"] == "FigureT/preview.png"
    png_path = config.root_dir() / "Scan2" / "FigureT" / "preview.png"
    assert png_path.read_bytes().startswith(b"\x89PNG")

    # 原 tif 也留了一份，SHA 与原文件一致
    files = node["files"]
    assert [f["name"] for f in files] == ["gyh40x.tif"]
    assert files[0]["rel_path"] == "FigureT/gyh40x.tif"
    stored = (config.root_dir() / "Scan2" / "FigureT" / "gyh40x.tif").read_bytes()
    assert files[0]["sha256"] == hashlib.sha256(tif_bytes.read_bytes()).hexdigest()
    assert stored == tif_bytes.read_bytes()
