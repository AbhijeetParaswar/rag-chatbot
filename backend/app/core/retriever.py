"""Retriever: vector search + optional reranking + query rewriting.

Retrieves top-k chunks from ChromaDB with optional MMR diversity
and cross-encoder reranking.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from backend.app.config import get_settings
from backend.app.core.embeddings import get_embedding_provider
from backend.app.core.ingestion import get_chroma_collection
from backend.app.schemas.schemas import RetrievedChunk

logger = logging.getLogger(__name__)
_settings = get_settings()

# Lazy-loaded reranker
_reranker = None


def _get_reranker():
    """Lazy-load the cross-encoder reranker."""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(_settings.reranking_model)
    return _reranker


async def retrieve(
    query: str,
    top_k: Optional[int] = None,
    use_reranking: Optional[bool] = None,
    score_threshold: Optional[float] = None,
    collection_name: Optional[str] = None,
) -> Tuple[List[RetrievedChunk], bool]:
    """Retrieve relevant chunks for a query.

    Parameters
    ----------
    query : str
        The search query (should be standalone, already rewritten).
    top_k : int, optional
        Number of results. Defaults to config.
    use_reranking : bool, optional
        Whether to use cross-encoder reranking. Defaults to config.
    score_threshold : float, optional
        Minimum similarity score. Defaults to config.
    collection_name : str, optional
        ChromaDB collection to search. Defaults to documents.

    Returns
    -------
    tuple of (list of RetrievedChunk, bool)
        The retrieved chunks and whether the query is answerable.
    """
    k = top_k or _settings.retrieval_top_k
    threshold = score_threshold or _settings.retrieval_score_threshold
    do_rerank = use_reranking if use_reranking is not None else _settings.reranking_enabled

    # Embed query
    embedder = get_embedding_provider()
    query_embedding = await embedder.embed_query(query)

    # Query ChromaDB
    collection = get_chroma_collection(collection_name)
    # Fetch more if we're going to rerank
    fetch_k = k * 3 if do_rerank else k

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(fetch_k, collection.count() or 1),
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"] or not results["ids"][0]:
        logger.info("No results found in ChromaDB")
        return [], False

    # Convert distances to similarity scores (ChromaDB cosine distance = 1 - similarity)
    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # Build candidate chunks
    candidates: List[Tuple[RetrievedChunk, float]] = []
    for i, (cid, doc, meta, dist) in enumerate(zip(ids, documents, metadatas, distances)):
        score = 1.0 - dist  # cosine similarity
        chunk = RetrievedChunk(
            chunk_id=cid,
            doc_id=meta.get("doc_id", ""),
            file_name=meta.get("file_name", ""),
            page_start=meta.get("page_start", 0),
            page_end=meta.get("page_end", 0),
            section_title=meta.get("section_title") or None,
            chunk_index=meta.get("chunk_index", 0),
            text=doc,
            score=round(score, 4),
        )
        candidates.append((chunk, score))

    # Optional reranking
    if do_rerank and len(candidates) > 1:
        logger.info(f"Reranking {len(candidates)} candidates...")
        import asyncio

        reranker = _get_reranker()
        pairs = [(query, c.text) for c, _ in candidates]
        loop = asyncio.get_event_loop()
        rerank_scores = await loop.run_in_executor(
            None, lambda: reranker.predict(pairs)
        )

        # Re-score and re-sort
        reranked = []
        for (chunk, _), new_score in zip(candidates, rerank_scores):
            chunk.score = round(float(new_score), 4)
            reranked.append((chunk, float(new_score)))
        candidates = sorted(reranked, key=lambda x: x[1], reverse=True)

    # Apply threshold and top-k: only keep candidates meeting the similarity threshold
    final_k = _settings.reranking_top_k if do_rerank else k
    filtered = [chunk for chunk, score in candidates if score >= threshold][:final_k]

    # Determine answerability
    if not filtered:
        is_answerable = False
    else:
        best_score = max(c.score for c in filtered)
        is_answerable = best_score >= threshold

    logger.info(
        f"Retrieved {len(filtered)} chunks (best_score={filtered[0].score if filtered else 0:.4f}, "
        f"answerable={is_answerable})"
    )

    return filtered, is_answerable


def needs_query_rewriting(
    query: str,
    conversation_history: List[Dict[str, str]],
) -> bool:
    """Determine whether a follow-up query actually requires LLM rewriting.

    Avoids expensive LLM roundtrips for standalone questions or greetings.
    """
    if not conversation_history:
        return False

    from backend.app.core.prompts import is_conversational_query
    if is_conversational_query(query):
        return False

    q = query.strip().lower()
    words = q.split()

    # Phrases indicating context dependency
    phrase_markers = [
        "what about", "how about", "why is that", "explain more",
        "tell me more", "the first one", "the second one", "the former", "the latter",
        "in that case", "what else", "continue", "elaborate"
    ]
    if any(p in q for p in phrase_markers):
        return True

    # Referential words
    referential_words = {
        "it", "its", "that", "this", "these", "those", "they", "them", "their",
        "he", "him", "his", "she", "her", "above", "more", "why", "how so"
    }
    if any(w in referential_words for w in words[:4]) or len(words) <= 3:
        return True

    # Standalone question with sufficient length
    return False


async def rewrite_query(
    query: str,
    conversation_history: List[Dict[str, str]],
) -> str:
    """Rewrite a follow-up question into a standalone query.

    Uses recent conversation history to resolve references like
    "it", "that", "the previous topic", etc.

    If the query seems standalone, returns it as-is.
    """
    if not conversation_history:
        return query

    from backend.app.core.llm import get_llm_provider

    llm = get_llm_provider()
    history_text = "\n".join(
        f"{msg['role']}: {msg['content'][:200]}"
        for msg in conversation_history[-6:]
    )

    rewrite_prompt = (
        "Given the following conversation history and a follow-up question, "
        "rewrite the follow-up question to be a standalone question that "
        "captures all necessary context. If the question is already standalone, "
        "return it as-is. Return ONLY the rewritten question, nothing else.\n\n"
        f"Conversation history:\n{history_text}\n\n"
        f"Follow-up question: {query}\n\n"
        "Standalone question:"
    )

    rewritten = ""
    async for token in llm.stream(rewrite_prompt, system_prompt="You are a helpful query rewriter."):
        rewritten += token

    rewritten = rewritten.strip()
    if rewritten and len(rewritten) > 5:
        logger.info(f"Query rewritten: '{query}' → '{rewritten}'")
        return rewritten
    return query
