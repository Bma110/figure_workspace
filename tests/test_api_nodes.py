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
