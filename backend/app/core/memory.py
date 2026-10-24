"""Memory system: short-term (per-thread) and long-term (per-user).

Short-term: rolling window of last N messages + LLM-generated summary of older ones.
Long-term: cross-thread fact extraction, deduplication, and retrieval via ChromaDB.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from backend.app.config import get_settings
from backend.app.core.embeddings import get_embedding_provider
from backend.app.core.ingestion import get_chroma_collection
from backend.app.core.llm import get_llm_provider
from backend.app.core.prompts import MEMORY_EXTRACTION_PROMPT, SUMMARY_PROMPT
from backend.app.db.crud import (
    add_memory,
    get_thread_messages,
    list_memories,
    update_thread,
)
from backend.app.db.session import get_session

logger = logging.getLogger(__name__)
_settings = get_settings()


# ── Short-term memory ────────────────────────────

async def get_short_term_context(
    thread_id: str,
    window: Optional[int] = None,
) -> tuple[List[Dict[str, str]], Optional[str]]:
    """Get recent messages and thread summary for context.

    Parameters
    ----------
    thread_id : str
        The conversation thread ID.
    window : int, optional
        Number of recent messages to include. Defaults to config.

    Returns
    -------
    tuple of (messages, summary)
        Recent messages as dicts and the thread summary.
    """
    n = window or _settings.short_term_window

    async with get_session() as db:
        from backend.app.db.crud import get_thread
        thread = await get_thread(db, thread_id)
        if not thread:
            return [], None

        messages = await get_thread_messages(db, thread_id)

    # Build message dicts
    recent = messages[-n:] if len(messages) > n else messages
    msg_dicts = [
        {"role": m.role, "content": m.content}
        for m in recent
    ]

    summary = thread.summary if thread else None

    # If we have older messages and no summary, generate one
    if len(messages) > n and not summary:
        await _update_thread_summary(thread_id, messages[:-n])

    return msg_dicts, summary


async def _update_thread_summary(
    thread_id: str,
    old_messages: list,
) -> None:
    """Generate and store a summary of older messages."""
    try:
        llm = get_llm_provider()
        messages_text = "\n".join(
            f"{m.role}: {m.content[:300]}" for m in old_messages
        )
        prompt = SUMMARY_PROMPT.format(messages=messages_text)
        summary = await llm.generate(prompt, system_prompt="You are a concise summarizer.")

        async with get_session() as db:
            await update_thread(db, thread_id, summary=summary.strip())

        logger.info(f"Updated summary for thread {thread_id}")
    except Exception as e:
        logger.error(f"Failed to update thread summary: {e}")


# ── Long-term memory ────────────────────────────

async def extract_and_store_memories(
    user_id: str,
    thread_id: str,
    user_message: str,
    assistant_message: str,
) -> List[str]:
    """Extract durable facts from an exchange and store them.

    Parameters
    ----------
    user_id : str
        The user identifier.
    thread_id : str
        Source thread.
    user_message : str
        The user's message.
    assistant_message : str
        The assistant's response.

    Returns
    -------
    list of str
        Newly stored memories.
    """
    if not _settings.long_term_memory_enabled:
        return []

    try:
        llm = get_llm_provider()
        prompt = MEMORY_EXTRACTION_PROMPT.format(
            user_message=user_message[:500],
            assistant_message=assistant_message[:500],
        )

        result = await llm.generate(
            prompt,
            system_prompt="You extract user facts from conversations. Be precise.",
        )

        if "NONE" in result.upper():
            return []

        # Parse extracted facts
        facts = []
        for line in result.strip().split("\n"):
            line = line.strip().lstrip("- ").strip()
            if line and len(line) > 5:
                facts.append(line)

        if not facts:
            return []

        # Deduplicate against existing memories
        new_memories = await _dedupe_memories(user_id, facts)

        if not new_memories:
            return []

        # Store in DB and ChromaDB
        embedder = get_embedding_provider()
        embeddings = await embedder.embed_texts(new_memories)
        collection = get_chroma_collection(_settings.chroma_collection_memories)

        async with get_session() as db:
            for mem_text, emb in zip(new_memories, embeddings):
                mem = await add_memory(db, user_id, mem_text, thread_id)
                collection.add(
                    ids=[mem.id],
                    embeddings=[emb],
                    documents=[mem_text],
                    metadatas=[{"user_id": user_id, "source_thread_id": thread_id}],
                )

        logger.info(f"Stored {len(new_memories)} new memories for user {user_id}")
        return new_memories

    except Exception as e:
        logger.error(f"Memory extraction failed: {e}")
        return []


async def _dedupe_memories(
    user_id: str,
    candidates: List[str],
    similarity_threshold: float = 0.85,
) -> List[str]:
    """Remove candidates that are too similar to existing memories."""
    async with get_session() as db:
        existing = await list_memories(db, user_id)

    if not existing:
        return candidates

    existing_texts = [m.text.lower() for m in existing]
    new = []
    for candidate in candidates:
        is_dupe = False
        candidate_lower = candidate.lower()
        for existing_text in existing_texts:
            # Simple substring/overlap check
            if candidate_lower in existing_text or existing_text in candidate_lower:
                is_dupe = True
                break
            # Jaccard similarity on words
            c_words = set(candidate_lower.split())
            e_words = set(existing_text.split())
            if c_words and e_words:
                jaccard = len(c_words & e_words) / len(c_words | e_words)
                if jaccard > similarity_threshold:
                    is_dupe = True
                    break
        if not is_dupe:
            new.append(candidate)
    return new


async def retrieve_relevant_memories(
    user_id: str,
    query: str,
    top_k: Optional[int] = None,
) -> List[str]:
    """Retrieve the most relevant long-term memories for a query.

    Parameters
    ----------
    user_id : str
        The user identifier.
    query : str
        The current query.
    top_k : int, optional
        Number of memories to retrieve. Defaults to config.

    Returns
    -------
    list of str
        Relevant memory texts.
    """
    if not _settings.long_term_memory_enabled:
        return []

    k = top_k or _settings.long_term_top_k
    collection = get_chroma_collection(_settings.chroma_collection_memories)

    if collection.count() == 0:
        return []

    try:
        embedder = get_embedding_provider()
        query_emb = await embedder.embed_query(query)

        results = collection.query(
            query_embeddings=[query_emb],
            n_results=min(k, collection.count()),
            where={"user_id": user_id},
            include=["documents"],
        )

        if results["documents"] and results["documents"][0]:
            return results["documents"][0]
    except Exception as e:
        logger.error(f"Memory retrieval failed: {e}")

    return []
