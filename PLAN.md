# RAG Chatbot — Implementation Plan

## Overview
Production-quality RAG chatbot over PDFs with streaming, citations, memory, and thread persistence.
Built for a GDG club-interview pre-task.

---

## Phase 0: Project Scaffolding & Config → Test: structure exists
- Repo structure: backend/app/, frontend/src/, data/, eval/, docs/
- Move existing PDFs from `DATA/` → `data/pdfs/`
- `.gitignore` (venv, __pycache__, .env, data/chroma/, node_modules, dist)
- `.env.example` with all config vars documented
- `backend/app/config.py` — pydantic-settings, all knobs
- `requirements.txt` — already done (pin versions)
- `ruff.toml` / `pyproject.toml` — linting config

## Phase 1: Database Layer (SQLite + SQLAlchemy 2.0)
- Tables: `users`, `threads`, `messages`, `memories`, `documents`
- `backend/app/db/models.py` — SQLAlchemy ORM models
- `backend/app/db/session.py` — async engine + sessionmaker
- `backend/app/db/crud.py` — CRUD helpers (async)
- `backend/app/schemas/` — Pydantic v2 request/response schemas
- **Test**: CRUD unit tests (create thread, add message, fetch thread)

## Phase 2: PDF Ingestion & Chunking
- `backend/app/core/ingestion.py` — CLI + API, idempotent via SHA-256 hash
- `backend/app/core/chunking.py` — recursive splitting, ~800 chars, ~120 overlap,
  page-boundary aware, heading detection
- Chunk metadata: doc_id, file_name, page_start, page_end, section_title,
  chunk_index, char_start, char_end, chunk_id (stable hash)
- **Test**: chunk metadata correctness, idempotency (re-run = no change)

## Phase 3: Embeddings & Vector Store
- `backend/app/core/embeddings.py` — provider interface (sentence-transformers default,
  Gemini optional), configurable via .env
- ChromaDB persistent client in `data/chroma/`, collection `documents`
- Collection `memories` for long-term memory
- **Test**: embed a chunk, retrieve it, verify metadata round-trip

## Phase 4: Retrieval Pipeline
- `backend/app/core/retriever.py`
  - Top-k vector search (default k=8)
  - Optional MMR diversity
  - Similarity threshold ("not answerable" guard)
  - Optional cross-encoder reranking (bge-reranker-base), toggleable
  - Query rewriting using short-term conversation context
- **Test**: retrieve correct page metadata for a known chunk

## Phase 5: LLM Provider Interface
- `backend/app/core/llm.py` — abstract provider, Gemini default, OpenAI/Anthropic/Ollama swappable
- `backend/app/core/prompts.py` — system prompt templates
- Token streaming support via async generators
- Prompt-injection defense: document text wrapped in data fences
- **Test**: mock LLM returns expected structured output

## Phase 6: Answer Generation & Citations
- `backend/app/core/citations.py`
  - Number passages [1], [2], ... in prompt
  - Parse [n] markers from model output
  - Validate every [n] maps to a real chunk
  - Build final citation list with file_name, page, section, snippet
  - Handle "not answerable" case
- **Test**: citation parser, validator, "not found" response

## Phase 7: Memory System
- Short-term: rolling window (last N=10 messages) + LLM summary of older
- Long-term: `backend/app/core/memory.py`
  - Background task: extract facts → dedupe → store in SQLite + Chroma
  - Query-time: retrieve top-3 memories → inject in system prompt
  - Memories NEVER cited as document sources
- **Test**: memory extraction, dedup logic

## Phase 8: API Endpoints
- POST /chat (full JSON), POST /chat/stream (SSE)
- SSE events: sources_start → token* → sources_end → done | error
- Thread CRUD, document upload, memory GET/DELETE, health
- Rate limiting, CORS, structured logging
- **Test**: SSE streaming with mocked LLM, thread CRUD

## Phase 9: Frontend (React + Vite + TypeScript + Tailwind)
- ChatGPT-style UI with sidebar, streaming, citations
- Dark/light mode, upload panel, settings panel
- fetch + ReadableStream + AbortController

## Phase 10: Docker & Infra
- Backend/Frontend Dockerfiles, docker-compose.yml, Makefile

## Phase 11: Documentation
- docs/architecture.md, README.md, EVALUATION.md stub

## Phase 12: Final Testing & Polish
- Full test suite, E2E verification, persistence check

---

## Execution Order
Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12
Each phase tested before moving on.
