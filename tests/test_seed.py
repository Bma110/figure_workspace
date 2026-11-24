from fw import seed, storage


def test_first_run_auto_imports_tutorial(client):
    # 首次调用 /api/workspaces 时应自动创建「入门教程」工作区，并把 _assets() 中的素材导入。
    assets = seed._assets()
    assert assets
    r = client.get("/api/workspaces").json()
    ws = next(w for w in r["workspaces"] if w["name"] == seed.WORKSPACE_NAME)
    folder = storage.workspace_folder(ws["code"])
    assert (folder / assets[0].stem / assets[0].name).exists()
    tree = client.get(f"/api/workspaces/{ws['code']}").json()["workspace"]["tree"]
    assert [n["label"] for n in tree] == [p.stem for p in assets]
