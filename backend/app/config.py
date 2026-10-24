"""Application configuration via pydantic-settings.

All configuration is loaded from environment variables or a .env file.
No secrets are hard-coded.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — every knob is an env var."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────
    app_name: str = "rag-chatbot"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v):  # noqa: N805
        if isinstance(v, str):
            return json.loads(v)
        return v

    # ── Database ─────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/rag_chatbot.db"

    # ── ChromaDB ─────────────────────────────────
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_docs: str = "documents"
    chroma_collection_memories: str = "memories"

    # ── Embeddings ───────────────────────────────
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    gemini_embedding_model: str = "models/text-embedding-004"

    # ── LLM ──────────────────────────────────────
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.0-flash"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    @field_validator("llm_provider", "llm_model", "gemini_api_key", "groq_api_key", "openai_api_key", mode="before")
    @classmethod
    def _strip_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    # ── Chunking ─────────────────────────────────
    chunk_size: int = 800
    chunk_overlap: int = 120
    max_chunks_per_page: int = 50

    # ── Retrieval ────────────────────────────────
    retrieval_top_k: int = 8
    retrieval_score_threshold: float = 0.55
    retrieval_use_mmr: bool = False
    retrieval_mmr_diversity: float = 0.3
    reranking_enabled: bool = False
    reranking_model: str = "BAAI/bge-reranker-base"
    reranking_top_k: int = 5

    # ── Memory ───────────────────────────────────
    short_term_window: int = 10
    long_term_memory_enabled: bool = True
    long_term_top_k: int = 3

    # ── Rate Limiting ────────────────────────────
    rate_limit: str = "20/minute"

    # ── Derived paths ────────────────────────────
    @property
    def data_dir(self) -> Path:
        return Path("data")

    @property
    def pdfs_dir(self) -> Path:
        return self.data_dir / "pdfs"


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
