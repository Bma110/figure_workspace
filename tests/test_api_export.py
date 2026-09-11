def test_settings_reports_paths(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["root"] and body["db"]


def test_export_three_kinds(client):
    client.post("/api/workspaces", json={"code": "EX", "name": "导出项目"})
    fig = client.post("/api/workspaces/EX/nodes",
                      json={"kind": "figure", "label": "Figure 1", "title": "骨破坏"}).json()["node"]
    client.patch(f"/api/nodes/{fig['id']}", json={"status": "adopted"})
    client.post(f"/api/nodes/{fig['id']}/files",
                files={"file": ("a.xlsx", b"data", "text/plain")})

    sd = client.get("/api/workspaces/EX/export/source_data")
    assert sd.status_code == 200 and "a.xlsx" in sd.text
    assert "attachment" in sd.headers["content-disposition"]

    lg = client.get("/api/workspaces/EX/export/legend")
    assert lg.status_code == 200 and "Figure 1" in lg.text

    da = client.get("/api/workspaces/EX/export/data_availability")
    assert da.status_code == 200 and "Data availability" in da.text

    assert client.get("/api/workspaces/EX/export/nope").status_code == 404
    assert client.get("/api/workspaces/missing/export/legend").status_code == 404
