"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.crud import list_documents
from backend.app.db.session import get_db
from backend.app.schemas.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """System health check."""
    docs = await list_documents(db)
    try:
        from backend.app.core.ingestion import get_chroma_collection
        collection = get_chroma_collection()
        chroma_status = f"ok ({collection.count()} chunks)"
    except Exception as e:
        chroma_status = f"error: {e}"

    return HealthResponse(
        status="ok",
        documents_indexed=len(docs),
        chroma_status=chroma_status,
    )
