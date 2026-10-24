"""FastAPI application entrypoint for RAG Chatbot.

Configured with CORS, slowapi rate limiting, lifespan startup/shutdown,
and structured routing.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend.app.api.chat import router as chat_router
from backend.app.api.documents import router as documents_router
from backend.app.api.health import router as health_router
from backend.app.api.memory import router as memory_router
from backend.app.api.threads import router as threads_router
from backend.app.config import get_settings
from backend.app.db.session import init_db

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rag-chatbot")

_settings = get_settings()

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[_settings.rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Initializing RAG Chatbot backend...")
    # Ensure data directories exist
    Path(_settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    _settings.pdfs_dir.mkdir(parents=True, exist_ok=True)

    # Initialize SQLite database schema
    await init_db()
    logger.info("Database schema initialized.")

    # Auto-sync any PDFs in data/pdfs folder on startup
    try:
        from backend.app.core.ingestion import ingest_directory
        if _settings.pdfs_dir.exists():
            logger.info(f"Scanning {_settings.pdfs_dir} for documents...")
            results = await ingest_directory(_settings.pdfs_dir, force=False)
            indexed_count = sum(1 for r in results if r.get("status") == "indexed")
            logger.info(f"Auto-sync completed: {indexed_count} new/updated document(s) indexed.")
    except Exception as e:
        logger.warning(f"Auto-sync on startup encountered an error: {e}")

    yield
    logger.info("Shutting down RAG Chatbot backend...")


app = FastAPI(
    title=_settings.app_name,
    version="1.0.0",
    description="Production-grade RAG chatbot over PDFs with citations, memory, and streaming.",
    lifespan=lifespan,
)

# Attach state and middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health_router)
app.include_router(threads_router)
app.include_router(documents_router)
app.include_router(memory_router)
app.include_router(chat_router)


@app.get("/")
async def root():
    return {
        "app": _settings.app_name,
        "docs_url": "/docs",
        "health_check": "/health",
        "status": "online",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
