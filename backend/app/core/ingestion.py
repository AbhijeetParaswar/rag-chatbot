"""PDF ingestion pipeline.

Idempotent: hashes each file, skips unchanged files, re-indexes changed ones.
Can be run as CLI: `python -m backend.app.core.ingestion --path data/pdfs`
or via API endpoint: POST /documents/upload.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import List, Optional

import chromadb
import fitz  # PyMuPDF

from backend.app.config import get_settings
from backend.app.core.chunking import Chunk, PageText, chunk_pages, detect_headings
from backend.app.core.embeddings import get_embedding_provider
from backend.app.db.crud import get_document_by_name, upsert_document
from backend.app.db.session import get_session

logger = logging.getLogger(__name__)
_settings = get_settings()


def _file_hash(path: Path) -> str:
    """SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def extract_pages(pdf_path: Path) -> List[PageText]:
    """Extract text and headings from each page of a PDF."""
    doc = fitz.open(str(pdf_path))
    pages: List[PageText] = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        headings = detect_headings(text)
        pages.append(PageText(page_number=i + 1, text=text, headings=headings))
    doc.close()
    return pages


def _get_chroma_client() -> chromadb.ClientAPI:
    """Get a persistent ChromaDB client."""
    persist_dir = _settings.chroma_persist_dir
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def get_chroma_collection(name: Optional[str] = None) -> chromadb.Collection:
    """Get or create a ChromaDB collection."""
    client = _get_chroma_client()
    collection_name = name or _settings.chroma_collection_docs
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


async def ingest_pdf(
    pdf_path: Path,
    force: bool = False,
) -> dict:
    """Ingest a single PDF file.

    Returns a dict with status, chunks count, and pages count.
    """
    file_name = pdf_path.name
    file_hash = _file_hash(pdf_path)

    # Check idempotency
    async with get_session() as db:
        existing = await get_document_by_name(db, file_name)
        if existing and existing.hash == file_hash and not force:
            logger.info(f"Skipping {file_name}: unchanged (hash match)")
            return {
                "file_name": file_name,
                "status": "skipped",
                "chunks": existing.chunk_count,
                "pages": existing.pages,
                "message": "File unchanged, already indexed",
            }

    # Extract text
    logger.info(f"Extracting text from {file_name}...")
    pages = extract_pages(pdf_path)
    if not pages:
        return {
            "file_name": file_name,
            "status": "error",
            "chunks": 0,
            "pages": 0,
            "message": "No text extracted from PDF",
        }

    # Generate doc_id from hash
    doc_id = file_hash[:16]

    # Chunk
    logger.info(f"Chunking {file_name} ({len(pages)} pages)...")
    chunks = chunk_pages(pages, doc_id=doc_id, file_name=file_name)
    if not chunks:
        return {
            "file_name": file_name,
            "status": "error",
            "chunks": 0,
            "pages": len(pages),
            "message": "No chunks generated",
        }

    # Embed
    logger.info(f"Embedding {len(chunks)} chunks from {file_name}...")
    embedder = get_embedding_provider()
    texts = [c.text for c in chunks]

    # Batch embedding (max 96 at a time for sentence-transformers)
    all_embeddings = []
    batch_size = 96
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embs = await embedder.embed_texts(batch)
        all_embeddings.extend(embs)

    # Store in ChromaDB
    logger.info(f"Storing {len(chunks)} chunks in ChromaDB...")
    collection = get_chroma_collection()

    # Remove old chunks for this document (re-indexing)
    try:
        existing_ids = collection.get(where={"doc_id": doc_id})["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids)
            logger.info(f"Removed {len(existing_ids)} old chunks for {file_name}")
    except Exception:
        pass  # Collection might be empty

    # Add new chunks in batches
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i : i + batch_size]
        batch_embs = all_embeddings[i : i + batch_size]

        collection.add(
            ids=[c.chunk_id for c in batch_chunks],
            embeddings=batch_embs,
            documents=[c.text for c in batch_chunks],
            metadatas=[
                {
                    "doc_id": c.doc_id,
                    "file_name": c.file_name,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "section_title": c.section_title or "",
                    "chunk_index": c.chunk_index,
                    "char_start": c.char_start,
                    "char_end": c.char_end,
                }
                for c in batch_chunks
            ],
        )

    # Update DB
    async with get_session() as db:
        await upsert_document(
            db,
            file_name=file_name,
            file_hash=file_hash,
            pages=len(pages),
            chunk_count=len(chunks),
        )

    logger.info(f"✓ Indexed {file_name}: {len(chunks)} chunks, {len(pages)} pages")
    return {
        "file_name": file_name,
        "status": "indexed",
        "chunks": len(chunks),
        "pages": len(pages),
        "message": "Successfully indexed",
    }


async def ingest_directory(dir_path: Path, force: bool = False) -> List[dict]:
    """Ingest all PDFs in a directory."""
    results = []
    pdf_files = sorted(dir_path.glob("*.pdf"))

    if not pdf_files:
        logger.warning(f"No PDF files found in {dir_path}")
        return results

    for pdf_path in pdf_files:
        try:
            result = await ingest_pdf(pdf_path, force=force)
            results.append(result)
        except Exception as e:
            logger.error(f"Error ingesting {pdf_path.name}: {e}")
            results.append({
                "file_name": pdf_path.name,
                "status": "error",
                "chunks": 0,
                "pages": 0,
                "message": str(e),
            })
    return results


# ── CLI entry point ──────────────────────────────

async def _cli_main():
    import argparse

    from backend.app.db.session import init_db

    parser = argparse.ArgumentParser(description="Ingest PDFs into the RAG system")
    parser.add_argument("--path", type=str, default="data/pdfs", help="Path to PDF directory")
    parser.add_argument("--force", action="store_true", help="Force re-indexing")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Init DB
    await init_db()

    path = Path(args.path)
    if path.is_file():
        results = [await ingest_pdf(path, force=args.force)]
    elif path.is_dir():
        results = await ingest_directory(path, force=args.force)
    else:
        logger.error(f"Path not found: {path}")
        return

    # Summary
    indexed = sum(1 for r in results if r["status"] == "indexed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    total_chunks = sum(r["chunks"] for r in results)
    print(f"\nDone: {indexed} indexed, {skipped} skipped, {errors} errors, {total_chunks} total chunks")


if __name__ == "__main__":
    asyncio.run(_cli_main())
