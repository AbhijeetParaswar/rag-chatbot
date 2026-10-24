"""Document ingestion and listing API endpoints."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.core.ingestion import ingest_directory, ingest_pdf
from backend.app.db.crud import list_documents
from backend.app.db.session import get_db
from backend.app.schemas.schemas import DocumentOut, IngestionStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])
_settings = get_settings()


@router.get("", response_model=List[DocumentOut])
async def api_list_documents(db: AsyncSession = Depends(get_db)) -> List[DocumentOut]:
    """List all indexed documents, auto-syncing any new PDFs found on disk."""
    pdfs_dir = _settings.pdfs_dir
    if pdfs_dir.exists():
        disk_pdfs = list(pdfs_dir.glob("*.pdf"))
        docs = await list_documents(db)
        indexed_names = {d.file_name for d in docs}
        unindexed = [p for p in disk_pdfs if p.name not in indexed_names]
        if unindexed:
            logger.info(f"Auto-syncing {len(unindexed)} unindexed PDF(s) found on disk: {[p.name for p in unindexed]}")
            for p in unindexed:
                try:
                    await ingest_pdf(p, force=False)
                except Exception as e:
                    logger.error(f"Error auto-ingesting {p.name}: {e}")
            docs = await list_documents(db)
    else:
        docs = await list_documents(db)

    return [
        DocumentOut(
            id=d.id,
            file_name=d.file_name,
            hash=d.hash,
            pages=d.pages,
            chunk_count=d.chunk_count,
            indexed_at=d.indexed_at,
        )
        for d in docs
    ]


@router.post("/sync", response_model=List[IngestionStatus])
async def api_sync_documents() -> List[IngestionStatus]:
    """Scan data/pdfs directory and ingest any new or modified PDF files."""
    pdfs_dir = _settings.pdfs_dir
    if not pdfs_dir.exists():
        return []

    results = await ingest_directory(pdfs_dir, force=False)
    return [
        IngestionStatus(
            file_name=r["file_name"],
            status=r["status"],
            chunks=r["chunks"],
            pages=r["pages"],
            message=r["message"],
        )
        for r in results
    ]


@router.post("/upload", response_model=IngestionStatus)
async def api_upload_document(
    file: UploadFile,
    force: bool = False,
) -> IngestionStatus:
    """Upload and ingest a PDF document."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    pdfs_dir = _settings.pdfs_dir
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    target_path = pdfs_dir / file.filename

    # Save uploaded file
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {e}",
        )

    # Ingest
    res = await ingest_pdf(target_path, force=force)
    return IngestionStatus(
        file_name=res["file_name"],
        status=res["status"],
        chunks=res["chunks"],
        pages=res["pages"],
        message=res["message"],
    )


@router.post("/reindex", response_model=List[IngestionStatus])
async def api_reindex_all(force: bool = True) -> List[IngestionStatus]:
    """Re-index all documents in the data/pdfs directory."""
    pdfs_dir = _settings.pdfs_dir
    if not pdfs_dir.exists():
        return []

    results = await ingest_directory(pdfs_dir, force=force)
    return [
        IngestionStatus(
            file_name=r["file_name"],
            status=r["status"],
            chunks=r["chunks"],
            pages=r["pages"],
            message=r["message"],
        )
        for r in results
    ]
