"""Chat API endpoints: non-streaming POST /chat and SSE streaming POST /chat/stream."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.app.config import get_settings
from backend.app.core.citations import (
    build_citations,
    build_pre_sources,
    parse_citation_markers,
)
from backend.app.core.llm import get_llm_provider
from backend.app.core.memory import (
    extract_and_store_memories,
    get_short_term_context,
    retrieve_relevant_memories,
)
from backend.app.core.prompts import (
    CONVERSATIONAL_SYSTEM_PROMPT,
    GENERAL_QA_SYSTEM_PROMPT,
    TITLE_GENERATION_PROMPT,
    build_rag_context,
    build_rag_system_prompt,
    build_rag_user_prompt,
    is_conversational_query,
    is_detailed_query,
    is_document_specific_query,
)
from backend.app.core.retriever import needs_query_rewriting, retrieve, rewrite_query
from backend.app.db.crud import (
    add_message,
    create_thread,
    get_thread,
    list_documents,
    update_thread,
)
from backend.app.db.session import get_db, get_session
from backend.app.schemas.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    RetrievedChunk,
    SSEDoneData,
    SSEErrorData,
    SSESourcesData,
    SSETokenData,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
_settings = get_settings()


async def _ensure_thread_and_title(
    db: AsyncSession,
    thread_id: Optional[str],
    user_id: str,
    first_query: str,
) -> str:
    """Ensure a thread exists and auto-generate title if it's the first message."""
    if thread_id:
        existing = await get_thread(db, thread_id)
        if existing:
            return existing.id

    # Create thread
    new_t = await create_thread(db, user_id=user_id, title="New Chat")
    thread_id = new_t.id

    # Auto-generate title in background
    asyncio.create_task(_generate_thread_title(thread_id, first_query))
    return thread_id


async def _generate_thread_title(thread_id: str, query: str) -> None:
    """Auto-generate a short descriptive title from the first message."""
    try:
        llm = get_llm_provider()
        prompt = TITLE_GENERATION_PROMPT.format(message=query[:300])
        title = await llm.generate(prompt, system_prompt="You generate brief chat titles.")
        cleaned = title.strip().strip('"\'')[:60]
        if cleaned:
            async with get_session() as db:
                await update_thread(db, thread_id, title=cleaned)
    except Exception as e:
        logger.warning(f"Failed to auto-generate thread title: {e}")


# ──────────────────────────────────────────────────
# Non-streaming POST /chat (used for Evaluation & Sync QA)
# ──────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
async def api_chat_sync(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Non-streaming chat endpoint returning complete answer, citations, and chunks."""
    start_time = time.perf_counter()

    # 1. Thread handling
    thread_id = await _ensure_thread_and_title(db, payload.thread_id, payload.user_id, payload.query)
    llm = get_llm_provider()

    # 2. Check for conversational / greeting queries
    if is_conversational_query(payload.query):
        answer = await llm.generate(payload.query, system_prompt=CONVERSATIONAL_SYSTEM_PROMPT)
        final_citations: List[Citation] = []
        chunks: List[RetrievedChunk] = []
        not_answerable = False

    else:
        # 3. Short-term memory & Smart Query Rewriting
        history, _ = await get_short_term_context(thread_id)
        if history and needs_query_rewriting(payload.query, history):
            search_query = await rewrite_query(payload.query, history)
        else:
            search_query = payload.query

        # 4. Long-term memory retrieval
        memories = await retrieve_relevant_memories(payload.user_id, search_query)

        # 5. Retrieval from Knowledge Base
        chunks, is_answerable = await retrieve(
            query=search_query,
            top_k=payload.top_k,
            use_reranking=payload.use_reranking,
        )

        is_detailed = is_detailed_query(payload.query)

        # 6. Answer generation
        if is_answerable and chunks:
            system_prompt = build_rag_system_prompt(memories, is_detailed=is_detailed)
            context = build_rag_context(chunks)
            user_prompt = build_rag_user_prompt(payload.query, context, is_detailed=is_detailed)

            raw_answer = await llm.generate(user_prompt, system_prompt=system_prompt)
            used_indices = parse_citation_markers(raw_answer)
            if not used_indices and chunks:
                used_indices = {i for i in range(1, min(len(chunks) + 1, 4))}
            final_citations = build_citations(used_indices, chunks)
            answer = raw_answer
            not_answerable = False
        else:
            final_citations = []
            chunks = []
            is_doc_specific = is_document_specific_query(payload.query)

            if is_doc_specific:
                available_docs = await list_documents(db)
                doc_names = [d.file_name for d in available_docs]
                doc_names_str = ", ".join(doc_names) if doc_names else "none"
                answer = (
                    f"I couldn't find specific information regarding this in the uploaded documents.\n\n"
                    f"**Indexed Documents in Knowledge Base:**\n{doc_names_str}\n\n"
                    f"If you have relevant materials on this topic, please upload them to the Knowledge Base."
                )
                not_answerable = True
            else:
                answer = await llm.generate(payload.query, system_prompt=GENERAL_QA_SYSTEM_PROMPT)
                not_answerable = False

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # 7. Save messages to DB
    await add_message(
        db,
        thread_id=thread_id,
        role="user",
        content=payload.query,
    )

    citations_json = json.dumps([c.model_dump() for c in final_citations]) if final_citations else None
    chunks_json = json.dumps([c.model_dump() for c in chunks]) if chunks else None

    assistant_msg = await add_message(
        db,
        thread_id=thread_id,
        role="assistant",
        content=answer,
        citations_json=citations_json,
        retrieved_chunks_json=chunks_json,
        latency_ms=latency_ms,
        model=llm.model_name,
    )

    # 8. Background long-term memory extraction
    background_tasks.add_task(
        extract_and_store_memories,
        user_id=payload.user_id,
        thread_id=thread_id,
        user_message=payload.query,
        assistant_message=answer,
    )

    return ChatResponse(
        message_id=assistant_msg.id,
        thread_id=thread_id,
        answer=answer,
        citations=final_citations,
        retrieved_chunks=chunks,
        latency_ms=latency_ms,
        model=llm.model_name,
        not_answerable=not_answerable,
    )


# ──────────────────────────────────────────────────
# Streaming POST /chat/stream (SSE)
# ──────────────────────────────────────────────────

@router.post("/stream")
async def api_chat_stream(payload: ChatRequest):
    """Server-Sent Events streaming chat endpoint.

    Event sequence:
    1. sources_start: candidate retrieved chunks (empty if conversational / no matches)
    2. token: streamed text delta
    3. sources_end: verified citations actually referenced by [n] markers
    4. done: completion metadata
    """
    start_time = time.perf_counter()

    async def event_generator() -> AsyncGenerator[dict, None]:
        nonlocal start_time
        llm = get_llm_provider()
        full_response = ""

        try:
            # 1. Thread handling
            async with get_session() as db:
                thread_id = await _ensure_thread_and_title(
                    db, payload.thread_id, payload.user_id, payload.query
                )

            # 2. Check for conversational / greeting queries
            if is_conversational_query(payload.query):
                # Conversational queries never show document sources
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": []}),
                }

                async for token in llm.stream(payload.query, system_prompt=CONVERSATIONAL_SYSTEM_PROMPT):
                    if token:
                        full_response += token
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}),
                        }

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": []}),
                }

                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                async with get_session() as save_db:
                    await add_message(
                        save_db,
                        thread_id=thread_id,
                        role="user",
                        content=payload.query,
                    )
                    saved_msg = await add_message(
                        save_db,
                        thread_id=thread_id,
                        role="assistant",
                        content=full_response,
                        citations_json=None,
                        retrieved_chunks_json=None,
                        latency_ms=latency_ms,
                        model=llm.model_name,
                    )
                    msg_id = saved_msg.id

                yield {
                    "event": "done",
                    "data": json.dumps({
                        "message_id": msg_id,
                        "thread_id": thread_id,
                        "latency_ms": latency_ms,
                        "model": llm.model_name,
                        "not_answerable": False,
                    }),
                }
                return

            # 3. Short-term memory & Smart Query Rewriting
            history, _ = await get_short_term_context(thread_id)
            if history and needs_query_rewriting(payload.query, history):
                search_query = await rewrite_query(payload.query, history)
            else:
                search_query = payload.query

            # 4. Long-term memory retrieval
            memories = await retrieve_relevant_memories(payload.user_id, search_query)

            # 5. Retrieval
            chunks, is_answerable = await retrieve(
                query=search_query,
                top_k=payload.top_k,
                use_reranking=payload.use_reranking,
            )

            is_detailed = is_detailed_query(payload.query)

            if is_answerable and chunks:
                # Relevant document chunks found
                initial_sources = build_pre_sources(chunks)
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": [s.model_dump() for s in initial_sources]}),
                }

                system_prompt = build_rag_system_prompt(memories, is_detailed=is_detailed)
                context = build_rag_context(chunks)
                user_prompt = build_rag_user_prompt(payload.query, context, is_detailed=is_detailed)

                async for token in llm.stream(user_prompt, system_prompt=system_prompt):
                    if token:
                        full_response += token
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}),
                        }

                used_indices = parse_citation_markers(full_response)
                if not used_indices and chunks:
                    used_indices = {i for i in range(1, min(len(chunks) + 1, 4))}
                final_citations = build_citations(used_indices, chunks)
                not_answerable = False

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": [c.model_dump() for c in final_citations]}),
                }

            else:
                # No relevant document chunks found — do NOT show ghost sources
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": []}),
                }

                final_citations = []
                chunks = []
                is_doc_specific = is_document_specific_query(payload.query)

                if is_doc_specific:
                    # User specifically asked for document/syllabus content, but not found
                    async with get_session() as db:
                        available_docs = await list_documents(db)
                    doc_names = [d.file_name for d in available_docs]
                    doc_names_str = ", ".join(doc_names) if doc_names else "none"

                    unanswerable_text = (
                        f"I couldn't find specific information about this in the uploaded documents.\n\n"
                        f"**Currently Indexed Documents in Knowledge Base:**\n"
                        f"{doc_names_str}\n\n"
                        f"If you have relevant materials on this topic, please upload them via the Knowledge Base panel."
                    )
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": unanswerable_text}),
                    }
                    full_response = unanswerable_text
                    not_answerable = True
                else:
                    # Normal general question: Answer helpfully as per the question!
                    system_prompt = GENERAL_QA_SYSTEM_PROMPT
                    async for token in llm.stream(payload.query, system_prompt=system_prompt):
                        if token:
                            full_response += token
                            yield {
                                "event": "token",
                                "data": json.dumps({"token": token}),
                            }
                    not_answerable = False

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": []}),
                }

            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Persist messages
            async with get_session() as save_db:
                await add_message(
                    save_db,
                    thread_id=thread_id,
                    role="user",
                    content=payload.query,
                )
                c_json = json.dumps([c.model_dump() for c in final_citations]) if final_citations else None
                ch_json = json.dumps([c.model_dump() for c in chunks]) if (chunks and not not_answerable) else None

                saved_msg = await add_message(
                    save_db,
                    thread_id=thread_id,
                    role="assistant",
                    content=full_response,
                    citations_json=c_json,
                    retrieved_chunks_json=ch_json,
                    latency_ms=latency_ms,
                    model=llm.model_name,
                )
                msg_id = saved_msg.id

            # Trigger long-term memory extraction in background
            asyncio.create_task(
                extract_and_store_memories(
                    user_id=payload.user_id,
                    thread_id=thread_id,
                    user_message=payload.query,
                    assistant_message=full_response,
                )
            )

            # Done event
            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": msg_id,
                    "thread_id": thread_id,
                    "latency_ms": latency_ms,
                    "model": llm.model_name,
                    "not_answerable": not_answerable,
                }),
            }

        except Exception as e:
            err_msg = str(e)
            if "getaddrinfo" in err_msg or "Connection error" in err_msg or "11001" in err_msg:
                err_msg = "Network connection error: Unable to reach the LLM API provider. Please check your internet connection."
                logger.warning(f"Network error in chat stream: {err_msg}")
            else:
                logger.exception("Error during chat stream")
            yield {
                "event": "error",
                "data": json.dumps({"error": err_msg}),
            }

    return EventSourceResponse(event_generator())
