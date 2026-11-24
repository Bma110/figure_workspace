def _ws(client):
    client.post("/api/workspaces", json={"code": "P002", "name": "项目2"})
    return "P002"


def test_create_figure_with_legend_and_methods(client):
    _ws(client)
    r = client.post("/api/workspaces/P002/nodes", json={
        "kind": "figure", "label": "Figure 2", "title": "感染后骨破坏",
        "note": "A-C 为代表图，比例尺 100 µm；n=6/组", "methods": "双侧 t 检验，P<0.05"})
    assert r.status_code == 200
    node = r.json()["node"]
    assert node["note"].startswith("A-C")
    assert node["methods"] == "双侧 t 检验，P<0.05"


def test_patch_methods(client):
    _ws(client)
    nid = client.post("/api/workspaces/P002/nodes", json={"kind": "figure", "label": "Figure 4"}).json()["node"]["id"]
    r = client.patch(f"/api/nodes/{nid}", json={"methods": "Mann-Whitney U"})
    assert r.json()["node"]["methods"] == "Mann-Whitney U"
