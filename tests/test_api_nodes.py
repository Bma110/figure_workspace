def _ws(client):
    client.post("/api/workspaces", json={"code": "P001", "name": "项目1"})
    return "P001"


def test_create_figure_makes_folder(client):
    _ws(client)
    r = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "骨破坏"})
    assert r.status_code == 200
    import os
    from fw import config
    assert (config.root_dir() / "P001" / "Figure1").exists()
    nid = r.json()["node"]["id"]
    assert nid


def test_create_panel_under_figure(client):
    _ws(client)
    fig = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 3",
                                                          "title": "炎症"}).json()["node"]
    client.post("/api/workspaces/P001/nodes", json={"kind": "panel", "label": "3A", "title": "IL6",
                                                    "parent_id": fig["id"]})
    tree = client.get("/api/workspaces/P001").json()["workspace"]["tree"]
    assert tree[0]["children"][0]["label"] == "3A"


def test_patch_node(client):
    _ws(client)
    nid = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 1",
                                                          "title": "x"}).json()["node"]["id"]
    r = client.patch(f"/api/nodes/{nid}", json={"status": "adopted", "importance": "key",
                                                "note": "定稿"})
    assert r.status_code == 200
    assert r.json()["node"]["status"] == "adopted"


def test_patch_missing_node_404(client):
    r = client.patch("/api/nodes/999999", json={"status": "adopted"})
    assert r.status_code == 404


def test_figure_with_cross_workspace_parent_400(client):
    _ws(client)
    client.post("/api/workspaces", json={"code": "B", "name": "另一项目"})
    nid = client.post("/api/workspaces/B/nodes", json={"kind": "figure", "label": "Figure 9",
                                                      "title": "x"}).json()["node"]["id"]
    r = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "parent_id": nid})
    assert r.status_code == 400


def test_delete_figure_trashes_folder_and_record(client):
    from fw import config
    _ws(client)
    nid = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 1",
                                                          "title": "x"}).json()["node"]["id"]
    client.post(f"/api/nodes/{nid}/files", files={"file": ("raw.txt", b"hello", "text/plain")})
    fig_folder = config.root_dir() / "P001" / "Figure1"
    assert fig_folder.is_dir()

    assert client.delete(f"/api/nodes/{nid}").status_code == 200
    assert client.get(f"/api/nodes/{nid}").status_code == 404
    # 文件夹整体进 .trash（可找回），不在原位
    assert not fig_folder.exists()
    trashed = list((config.root_dir() / "P001" / ".trash").iterdir())
    assert [t.name for t in trashed] == ["Figure1"]
    assert (trashed[0] / "raw.txt").exists()


def test_archive_hides_node_from_board_and_can_be_shown(client):
    _ws(client)
    nid = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 1",
                                                          "title": "x"}).json()["node"]["id"]
    assert client.patch(f"/api/nodes/{nid}", json={"archived": 1}).status_code == 200

    hidden = client.get("/api/workspaces/P001").json()["workspace"]["tree"]
    assert hidden == []
    shown = client.get("/api/workspaces/P001?show_archived=1").json()["workspace"]["tree"]
    assert [n["id"] for n in shown] == [nid] and shown[0]["archived"] == 1

    client.patch(f"/api/nodes/{nid}", json={"archived": 0})
    assert [n["id"] for n in client.get("/api/workspaces/P001").json()["workspace"]["tree"]] == [nid]


def test_archive_figure_hides_its_panels_too(client):
    _ws(client)
    fig = client.post("/api/workspaces/P001/nodes", json={"kind": "figure", "label": "Figure 3",
                                                          "title": "炎症"}).json()["node"]
    client.post("/api/workspaces/P001/nodes", json={"kind": "panel", "label": "3A",
                                                    "parent_id": fig["id"]})
    client.patch(f"/api/nodes/{fig['id']}", json={"archived": 1})
    assert client.get("/api/workspaces/P001").json()["workspace"]["tree"] == []
    shown = client.get("/api/workspaces/P001?show_archived=1").json()["workspace"]["tree"]
    assert shown[0]["children"][0]["label"] == "3A"
