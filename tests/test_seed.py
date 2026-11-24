from fw import seed, storage


def test_first_run_auto_imports_tutorial(client):
    # 首次调用 /api/workspaces 时应自动创建「入门教程」工作区并把 docs/tutorial_scans 导入。
    r = client.get("/api/workspaces").json()
    ws = next(w for w in r["workspaces"] if w["name"] == seed.WORKSPACE_NAME)
    folder = storage.workspace_folder(ws["code"])
    assert (folder / "fig_1" / "fig_1.png").exists()
    tree = client.get(f"/api/workspaces/{ws['code']}").json()["workspace"]["tree"]
    assert [n["label"] for n in tree] == ["fig_1", "fig_2", "fig_3", "fig_4", "fig_5"]
