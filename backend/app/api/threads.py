"""Thread management API endpoints."""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.crud import (
    create_thread,
    delete_thread,
    get_thread,
    list_threads,
    update_thread,
)
from backend.app.db.session import get_db
from backend.app.schemas.schemas import (
    Citation,
    MessageOut,
    ThreadCreate,
    ThreadDetailOut,
    ThreadOut,
    ThreadUpdate,
)

router = APIRouter(prefix="/threads", tags=["threads"])


@router.post("", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
async def api_create_thread(
    payload: ThreadCreate,
    db: AsyncSession = Depends(get_db),
) -> ThreadOut:
    """Create a new conversation thread."""
    thread = await create_thread(db, user_id=payload.user_id, title=payload.title or "New Chat")
    return ThreadOut(
        id=thread.id,
        title=thread.title,
        summary=thread.summary,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=0,
    )


@router.get("", response_model=List[ThreadOut])
async def api_list_threads(
    user_id: str = "default",
    db: AsyncSession = Depends(get_db),
) -> List[ThreadOut]:
    """List all threads for a user."""
    threads = await list_threads(db, user_id=user_id)
    out: List[ThreadOut] = []
    for t in threads:
        msg_count = len(t.messages) if hasattr(t, "messages") and t.messages is not None else 0
        out.append(
            ThreadOut(
                id=t.id,
                title=t.title or "New Chat",
                summary=t.summary,
                created_at=t.created_at,
                updated_at=t.updated_at,
                message_count=msg_count,
            )
        )
    return out


@router.get("/{thread_id}", response_model=ThreadDetailOut)
async def api_get_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
) -> ThreadDetailOut:
    """Get thread details including message history."""
    thread = await get_thread(db, thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found",
        )

    formatted_messages: List[MessageOut] = []
    for msg in thread.messages:
        citations = None
        if msg.citations_json:
            try:
                raw_cites = json.loads(msg.citations_json)
                citations = [Citation(**c) for c in raw_cites]
            except Exception:
                citations = None

        formatted_messages.append(
            MessageOut(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                citations=citations,
                latency_ms=msg.latency_ms,
                model=msg.model,
                created_at=msg.created_at,
            )
        )

    return ThreadDetailOut(
        id=thread.id,
        title=thread.title or "New Chat",
        summary=thread.summary,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=len(formatted_messages),
        messages=formatted_messages,
    )


@router.patch("/{thread_id}", response_model=ThreadOut)
async def api_update_thread(
    thread_id: str,
    payload: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
) -> ThreadOut:
    """Update thread metadata (e.g., rename title)."""
    thread = await update_thread(db, thread_id, title=payload.title)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found",
        )
    return ThreadOut(
        id=thread.id,
        title=thread.title,
        summary=thread.summary,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=len(thread.messages) if thread.messages else 0,
    )


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a thread and its messages."""
    deleted = await delete_thread(db, thread_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found",
        )
