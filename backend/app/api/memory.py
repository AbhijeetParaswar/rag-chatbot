"""Memory management API endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.ingestion import get_chroma_collection
from backend.app.db.crud import delete_memory, list_memories
from backend.app.db.session import get_db
from backend.app.schemas.schemas import MemoryOut

router = APIRouter(prefix="/memory", tags=["memory"])
_settings = get_settings()


@router.get("", response_model=List[MemoryOut])
async def api_list_memories(
    user_id: str = "default",
    db: AsyncSession = Depends(get_db),
) -> List[MemoryOut]:
    """Retrieve all long-term memories for a user."""
    memories = await list_memories(db, user_id=user_id)
    return [
        MemoryOut(
            id=m.id,
            text=m.text,
            source_thread_id=m.source_thread_id,
            created_at=m.created_at,
        )
        for m in memories
    ]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a memory from both SQLite and the vector store."""
    deleted = await delete_memory(db, memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory '{memory_id}' not found",
        )

    # Delete from ChromaDB
    try:
        collection = get_chroma_collection(_settings.chroma_collection_memories)
        collection.delete(ids=[memory_id])
    except Exception:
        pass  # Memory might not have been embedded or collection empty
