"""Tests for PDF ingestion idempotency and document record creation."""

from pathlib import Path
import pytest
from backend.app.core.ingestion import ingest_pdf
from backend.app.db.crud import list_documents
from backend.app.db.session import get_session


@pytest.mark.asyncio
async def test_ingestion_idempotency_unit():
    pdf_path = Path("data/pdfs/cs101_syllabus.pdf")
    if not pdf_path.exists():
        pytest.skip("Sample PDF not present")

    # Ingest once
    res1 = await ingest_pdf(pdf_path, force=False)
    assert res1["status"] in ("indexed", "skipped")
    assert res1["pages"] == 2
    assert res1["chunks"] > 0

    # Ingest again without force -> must be skipped
    res2 = await ingest_pdf(pdf_path, force=False)
    assert res2["status"] == "skipped"
    assert "already indexed" in res2["message"]
