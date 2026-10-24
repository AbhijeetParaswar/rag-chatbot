"""Pydantic v2 request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request body for /chat and /chat/stream."""
    query: str = Field(..., min_length=1, max_length=4000)
    thread_id: Optional[str] = None
    user_id: str = "default"
    top_k: Optional[int] = None
    use_reranking: Optional[bool] = None


class RetrievedChunk(BaseModel):
    """A single chunk returned by retrieval."""
    chunk_id: str
    doc_id: str
    file_name: str
    page_start: int
    page_end: int
    section_title: Optional[str] = None
    chunk_index: int
    text: str
    score: float


class Citation(BaseModel):
    """A formatted citation."""
    index: int          # [1]-based
    file_name: str
    page_start: int
    page_end: int
    section_title: Optional[str] = None
    snippet: str


class ChatResponse(BaseModel):
    """Response body for non-streaming /chat."""
    message_id: str
    thread_id: str
    answer: str
    citations: List[Citation]
    retrieved_chunks: List[RetrievedChunk]
    latency_ms: float
    model: str
    not_answerable: bool = False


# ──────────────────────────────────────────────────
# SSE event data shapes
# ──────────────────────────────────────────────────

class SSESourcesData(BaseModel):
    """Payload for sources_start / sources_end events."""
    sources: List[Citation]


class SSETokenData(BaseModel):
    """Payload for token events."""
    token: str


class SSEDoneData(BaseModel):
    """Payload for the done event."""
    message_id: str
    thread_id: str
    latency_ms: float
    model: str
    not_answerable: bool = False


class SSEErrorData(BaseModel):
    """Payload for error events."""
    error: str


# ──────────────────────────────────────────────────
# Threads
# ──────────────────────────────────────────────────

class ThreadCreate(BaseModel):
    user_id: str = "default"
    title: Optional[str] = None


class ThreadUpdate(BaseModel):
    title: Optional[str] = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    citations: Optional[List[Citation]] = None
    latency_ms: Optional[float] = None
    model: Optional[str] = None
    created_at: datetime


class ThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ThreadDetailOut(ThreadOut):
    messages: List[MessageOut] = []


# ──────────────────────────────────────────────────
# Documents
# ──────────────────────────────────────────────────

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_name: str
    hash: str
    pages: int
    chunk_count: int
    indexed_at: datetime


class IngestionStatus(BaseModel):
    file_name: str
    status: str  # "indexed" | "skipped" | "error"
    chunks: int = 0
    pages: int = 0
    message: str = ""


# ──────────────────────────────────────────────────
# Memory
# ──────────────────────────────────────────────────

class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    text: str
    source_thread_id: Optional[str] = None
    created_at: datetime


# ──────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    documents_indexed: int = 0
    chroma_status: str = "unknown"
