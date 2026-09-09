from fw import db, config


def test_create_and_list(client):
    r = client.post("/api/workspaces", json={"code": "SA-Osteomyelitis", "name": "SA 骨髓炎"})
    assert r.status_code == 200
    assert (config.root_dir() / "SA-Osteomyelitis").exists()
    lst = client.get("/api/workspaces").json()["workspaces"]
    assert any(w["code"] == "SA-Osteomyelitis" for w in lst)


def test_create_duplicate_code_409(client):
    client.post("/api/workspaces", json={"code": "Dup", "name": "x"})
    r = client.post("/api/workspaces", json={"code": "Dup", "name": "y"})
    assert r.status_code == 409


def test_archive(client):
    client.post("/api/workspaces", json={"code": "A", "name": "a"})
    client.post("/api/workspaces/A/archive")
    assert client.get("/api/workspaces/A").json()["workspace"]["archived"] == 1


def test_create_empty_code_400(client):
    r = client.post("/api/workspaces", json={"code": "   ", "name": "x"})
    assert r.status_code == 400
