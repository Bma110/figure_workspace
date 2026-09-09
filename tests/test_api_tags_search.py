def test_tags_and_search(client):
    client.post("/api/workspaces", json={"code": "P1", "name": "SA 骨髓炎"})
    nid = client.post("/api/workspaces/P1/nodes", json={"kind": "figure", "label": "Figure 1",
                                                        "title": "炎症"}).json()["node"]["id"]
    assert client.post(f"/api/nodes/{nid}/tags", json={"tag": "IL6"}).status_code == 200
    assert client.post(f"/api/nodes/{nid}/tags", json={"tag": "SA"}).status_code == 200
    r = client.get("/api/search?q=IL6")
    hits = r.json()["results"]
    assert any(h["node_id"] == nid for h in hits)
    assert any(h["tag"] == "IL6" for h in hits)


def test_search_finds_workspace_and_file(client):
    client.post("/api/workspaces", json={"code": "Zebrafish", "name": "斑马鱼模型"})
    r = client.get("/api/search?q=斑马鱼")
    assert any(h["workspace_code"] == "Zebrafish" for h in r.json()["results"])
