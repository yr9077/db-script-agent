"""End-to-end API tests using the ASGI test client."""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_home_page(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "AI SQL Generator" in resp.text or "DB Script Agent" in resp.text


@pytest.mark.asyncio
async def test_scripts_page(client):
    resp = await client.get("/scripts")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_list_scripts_empty(client):
    resp = await client.get("/api/scripts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_api_create_script(client):
    payload = {
        "title": "Create users table",
        "description": "Test script",
        "dialect": "mysql",
        "script_type": "ddl",
        "content": "CREATE TABLE users (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255));",
        "prompt": "Create users table",
    }
    resp = await client.post("/api/scripts", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] > 0
    assert data["title"] == "Create users table"
    assert data["dialect"] == "mysql"
    return data["id"]


@pytest.mark.asyncio
async def test_api_get_script(client):
    # Create first
    payload = {
        "title": "Get test",
        "dialect": "postgresql",
        "script_type": "dml",
        "content": "SELECT id FROM users WHERE id = 1;",
        "prompt": "test",
    }
    create_resp = await client.post("/api/scripts", json=payload)
    script_id = create_resp.json()["id"]

    resp = await client.get(f"/api/scripts/{script_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == script_id


@pytest.mark.asyncio
async def test_api_get_nonexistent_script(client):
    resp = await client.get("/api/scripts/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_update_script(client):
    payload = {
        "title": "Update test",
        "dialect": "sqlite",
        "script_type": "ddl",
        "content": "CREATE TABLE t (id INTEGER PRIMARY KEY);",
        "prompt": "",
    }
    create_resp = await client.post("/api/scripts", json=payload)
    script_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/scripts/{script_id}", json={"title": "Updated title"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated title"


@pytest.mark.asyncio
async def test_api_approve_script(client):
    payload = {
        "title": "Approve test",
        "dialect": "mysql",
        "script_type": "ddl",
        "content": "CREATE TABLE foo (id INT PRIMARY KEY);",
        "prompt": "",
    }
    create_resp = await client.post("/api/scripts", json=payload)
    script_id = create_resp.json()["id"]

    resp = await client.post(f"/api/scripts/{script_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_api_reject_script(client):
    payload = {
        "title": "Reject test",
        "dialect": "mysql",
        "script_type": "dml",
        "content": "DELETE FROM users;",
        "prompt": "",
    }
    create_resp = await client.post("/api/scripts", json=payload)
    script_id = create_resp.json()["id"]

    resp = await client.post(f"/api/scripts/{script_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_api_recheck_script(client):
    payload = {
        "title": "Recheck test",
        "dialect": "mysql",
        "script_type": "dml",
        "content": "DROP TABLE dangerous;",
        "prompt": "",
    }
    create_resp = await client.post("/api/scripts", json=payload)
    script_id = create_resp.json()["id"]

    resp = await client.post(f"/api/scripts/{script_id}/check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_level"] == "critical"


@pytest.mark.asyncio
async def test_api_delete_script(client):
    payload = {
        "title": "Delete test",
        "dialect": "sqlite",
        "script_type": "ddl",
        "content": "CREATE TABLE tmp (id INTEGER);",
        "prompt": "",
    }
    create_resp = await client.post("/api/scripts", json=payload)
    script_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/scripts/{script_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/scripts/{script_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_api_generate_sql_mock(client):
    """In mock mode, generation should always return SQL."""
    payload = {
        "prompt": "Create a products table with id, name and price",
        "dialect": "mysql",
        "script_type": "ddl",
    }
    resp = await client.post("/api/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sql"] != "" or data["needs_clarification"] is True
    assert "session_id" in data


@pytest.mark.asyncio
async def test_api_generate_and_list(client):
    """Generated script should appear in the list."""
    payload = {
        "prompt": "Create an orders table",
        "dialect": "postgresql",
        "script_type": "ddl",
    }
    gen_resp = await client.post("/api/generate", json=payload)
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    if gen_data.get("script_id"):
        list_resp = await client.get("/api/scripts")
        ids = [s["id"] for s in list_resp.json()]
        assert gen_data["script_id"] in ids


@pytest.mark.asyncio
async def test_api_filter_by_dialect(client):
    payload = {
        "title": "Filter dialect test",
        "dialect": "sqlite",
        "script_type": "ddl",
        "content": "CREATE TABLE x (id INTEGER PRIMARY KEY);",
        "prompt": "",
    }
    await client.post("/api/scripts", json=payload)
    resp = await client.get("/api/scripts?dialect=sqlite")
    assert resp.status_code == 200
    for s in resp.json():
        assert s["dialect"] == "sqlite"


@pytest.mark.asyncio
async def test_script_detail_page(client):
    payload = {
        "title": "UI detail test",
        "dialect": "mysql",
        "script_type": "ddl",
        "content": "CREATE TABLE ui_test (id INT PRIMARY KEY);",
        "prompt": "",
    }
    create_resp = await client.post("/api/scripts", json=payload)
    script_id = create_resp.json()["id"]
    resp = await client.get(f"/scripts/{script_id}")
    assert resp.status_code == 200
