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


def test_title_helpers():
    from backend.app.core.prompts import clean_generated_title, is_generic_title

    assert is_generic_title("Friendly Greeting and Introduction") is True
    assert is_generic_title("Friendly Greeting") is True
    assert is_generic_title("New Chat") is True
    assert is_generic_title("Quantum Computing Overview") is False

    # Title cleanup strips quotes, prefixes, limits to 3-4 words
    assert clean_generated_title('"Title: CS101 Grading Policy"') == "Cs101 Grading Policy"
    assert clean_generated_title("Friendly Greeting and Introduction") == "New Chat"
    assert clean_generated_title("This Is A Very Long Title That Should Be Truncated To Four Words") == "This Is A Very"


@pytest.mark.asyncio
async def test_legacy_greeting_title_cleanup(async_client: AsyncClient):
    # Create thread with legacy title
    res = await async_client.post(
        "/threads",
        json={"user_id": "cleanup_user", "title": "Friendly Greeting and Introduction"},
    )
    assert res.status_code == 201
    tid = res.json()["id"]

    # When listing threads, it should auto-clean it
    list_res = await async_client.get("/threads?user_id=cleanup_user")
    assert list_res.status_code == 200
    threads = list_res.json()
    cleaned = next(t for t in threads if t["id"] == tid)
    assert cleaned["title"] != "Friendly Greeting and Introduction"
    assert cleaned["title"] == "New Chat"

