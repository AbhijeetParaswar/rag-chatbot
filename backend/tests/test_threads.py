"""Integration tests for threads and messages CRUD."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_thread_crud_lifecycle(async_client: AsyncClient):
    # 1. Create thread
    res = await async_client.post("/threads", json={"user_id": "test_user", "title": "Initial Chat"})
    assert res.status_code == 201
    data = res.json()
    thread_id = data["id"]
    assert data["title"] == "Initial Chat"

    # 2. List threads
    list_res = await async_client.get("/threads?user_id=test_user")
    assert list_res.status_code == 200
    threads = list_res.json()
    assert any(t["id"] == thread_id for t in threads)

    # 3. Patch thread title
    patch_res = await async_client.patch(f"/threads/{thread_id}", json={"title": "Updated Title"})
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated Title"

    # 4. Get thread detail
    get_res = await async_client.get(f"/threads/{thread_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["title"] == "Updated Title"
    assert isinstance(detail["messages"], list)

    # 5. Delete thread
    del_res = await async_client.delete(f"/threads/{thread_id}")
    assert del_res.status_code == 204

    # 6. Verify 404 after deletion
    not_found = await async_client.get(f"/threads/{thread_id}")
    assert not_found.status_code == 404
