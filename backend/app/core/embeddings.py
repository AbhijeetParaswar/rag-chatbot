"""Embedding provider interface.

Supports sentence-transformers (local, default) and Gemini embeddings.
Configurable via EMBEDDING_PROVIDER env var.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List

import numpy as np

from backend.app.config import get_settings


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts, returning a list of vectors."""

    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""


class SentenceTransformerEmbeddings(EmbeddingProvider):
    """Local sentence-transformers embeddings (BAAI/bge-small-en-v1.5)."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        try:
            self._model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            self._model = SentenceTransformer(model_name)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: self._model.encode(texts, normalize_embeddings=True)
        )
        return embeddings.tolist()

    async def embed_query(self, query: str) -> List[float]:
        # BGE models recommend "Represent this sentence: " prefix for queries
        result = await self.embed_texts([f"Represent this sentence: {query}"])
        return result[0]


class GeminiEmbeddings(EmbeddingProvider):
    """Google Gemini embedding API."""

    def __init__(self, model_name: str, api_key: str):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model_name

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        from google.genai import types
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._client.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            ),
        )
        return [list(e.values) for e in result.embeddings]

    async def embed_query(self, query: str) -> List[float]:
        from google.genai import types
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._client.models.embed_content(
                model=self._model,
                contents=[query],
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
            ),
        )
        return list(result.embeddings[0].values)


_provider_instance: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Factory: return (cached) embedding provider based on config."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    settings = get_settings()
    if settings.embedding_provider == "gemini":
        _provider_instance = GeminiEmbeddings(
            model_name=settings.gemini_embedding_model,
            api_key=settings.gemini_api_key,
        )
    else:
        _provider_instance = SentenceTransformerEmbeddings(
            model_name=settings.embedding_model,
        )
    return _provider_instance
