import pytest
import uuid
import httpx
from app.main import app
from app.db import engine, init_db

transport = httpx.ASGITransport(app=app)


@pytest.fixture(autouse=True)
async def cleanup_db():
    await init_db()
    yield
    await engine.dispose()


@pytest.mark.anyio
async def test_health_endpoint():
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "gemini_chat_model" in data


@pytest.mark.anyio
async def test_session_header_generation():
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert "X-Session-Id" in response.headers
        session_id_str = response.headers["X-Session-Id"]
        parsed_uuid = uuid.UUID(session_id_str)
        assert str(parsed_uuid) == session_id_str


@pytest.mark.anyio
async def test_session_persistence_across_requests():
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        res1 = await ac.get("/health")
        sess_id = res1.headers["X-Session-Id"]

        res2 = await ac.get("/health", headers={"X-Session-Id": sess_id})
        assert res2.headers.get("X-Session-Id") == sess_id


@pytest.mark.anyio
async def test_collections_lifecycle():
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create or get collection
        col_res = await ac.post("/api/collections")
        assert col_res.status_code == 200
        col_data = col_res.json()
        col_id = col_data["collection_id"]
        sess_id = col_res.headers["X-Session-Id"]

        # 2. Check collection status (initially empty)
        headers = {"X-Session-Id": sess_id}
        status_res = await ac.get(f"/api/collections/{col_id}/status", headers=headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["total_videos"] == 0

        # 3. Delete collection
        del_res = await ac.delete(f"/api/collections/{col_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"
