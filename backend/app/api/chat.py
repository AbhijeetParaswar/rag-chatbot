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
    ASK_FALLBACK_PROMPT,
    CONVERSATIONAL_SYSTEM_PROMPT,
    GENERAL_QA_LABELED_PROMPT,
    GENERAL_QA_SYSTEM_PROMPT,
    PARTIAL_EVIDENCE_PROMPT,
    STRICT_UNANSWERABLE_RESPONSE,
    TITLE_GENERATION_PROMPT,
    build_rag_context,
    build_rag_system_prompt,
    build_rag_user_prompt,
    clean_generated_title,
    evaluate_evidence,
    is_conversational_query,
    is_detailed_query,
    is_document_specific_query,
    is_generic_title,
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
    AnswerMode,
    AnswerSource,
    ChatRequest,
    ChatResponse,
    Citation,
    EvidenceStatus,
    RetrievedChunk,
    SSEDoneData,
    SSEErrorData,
    SSESourcesData,
    SSETokenData,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
_settings = get_settings()


async def _ensure_thread(
    db: AsyncSession,
    thread_id: Optional[str],
    user_id: str,
) -> str:
    """Ensure a thread exists."""
    if thread_id:
        existing = await get_thread(db, thread_id)
        if existing:
            return existing.id

    # Create thread with default title
    new_t = await create_thread(db, user_id=user_id, title="New Chat")
    return new_t.id


async def _generate_thread_title(
    thread_id: str,
    query: str,
    assistant_reply: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> Optional[str]:
    """Auto-generate a 3 to 4 word ChatGPT-style topic title from what was discussed."""
    try:
        # If query is purely conversational greeting and assistant reply is short, do NOT generate generic greeting title
        if is_conversational_query(query) and (not assistant_reply or len(assistant_reply.strip()) < 15):
            return None

        # Build context from what was discussed
        content_snippet = f"User: {query[:300]}"
        if assistant_reply:
            content_snippet += f"\nAssistant: {assistant_reply[:300]}"

        llm = get_llm_provider()
        prompt = TITLE_GENERATION_PROMPT.format(message=content_snippet)
        raw_title = await llm.generate(
            prompt,
            system_prompt="You generate punchy 3-4 word conversation titles like ChatGPT."
        )
        cleaned = clean_generated_title(raw_title)
        if cleaned and cleaned.lower() != "new chat":
            if db:
                await update_thread(db, thread_id, title=cleaned)
            else:
                async with get_session() as session:
                    await update_thread(session, thread_id, title=cleaned)
            return cleaned
    except Exception as e:
        logger.warning(f"Failed to auto-generate thread title: {e}")
    return None


async def _maybe_update_title(
    thread_id: str,
    query: str,
    assistant_reply: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> Optional[str]:
    """Check if thread title is generic and update to 3-4 word topic title if discussion is substantive."""
    try:
        if db:
            t = await get_thread(db, thread_id)
        else:
            async with get_session() as session:
                t = await get_thread(session, thread_id)

        if not t or not is_generic_title(t.title):
            return t.title if t else None

        if not is_conversational_query(query) or (assistant_reply and len(assistant_reply.strip()) > 20):
            new_title = await _generate_thread_title(thread_id, query, assistant_reply, db=db)
            if new_title:
                return new_title
    except Exception as e:
        logger.warning(f"Failed in _maybe_update_title: {e}")
    return None

async def _stream_linear_tokens(text: str) -> AsyncGenerator[dict, None]:
    """Stream text tokens linearly at human typing speed for ChatGPT-like continuous flow."""
    import re
    tokens = re.findall(r"\S+\s*|\s+", text)
    for tok in tokens:
        yield {
            "event": "token",
            "data": json.dumps({"token": tok}),
        }
        await asyncio.sleep(0.012)


def _route_answer_decision(
    answer_mode: AnswerMode,
    evidence_status: EvidenceStatus,
    is_doc_specific: bool,
    has_doc_filter: bool,
    fallback_approved: Optional[bool],
) -> str:
    """Decide the answer routing based on mode, evidence, and intent.

    Returns one of: 'rag', 'partial_rag', 'general', 'strict_refuse',
                     'doc_specific_refuse', 'ask_fallback', 'doc_filter_refuse'
    """
    # Sufficient evidence → always answer with RAG
    if evidence_status == EvidenceStatus.sufficient:
        return "rag"

    # Partial evidence handling
    if evidence_status == EvidenceStatus.partial:
        if answer_mode == AnswerMode.strict:
            # Strict mode: use what we have (partial RAG), but don't fill gaps with general knowledge
            return "rag"
        elif answer_mode == AnswerMode.smart_fallback:
            return "partial_rag"
        elif answer_mode == AnswerMode.ask_before_fallback:
            return "partial_rag"
        return "rag"

    # Insufficient evidence or retrieval error
    # --- Doc filter active (user attached specific files)
    if has_doc_filter:
        return "doc_filter_refuse"

    # --- Document-specific question (mentions syllabus, policy, PDF, etc.)
    if is_doc_specific:
        if answer_mode == AnswerMode.strict:
            return "strict_refuse"
        elif answer_mode == AnswerMode.smart_fallback:
            return "doc_specific_refuse"
        elif answer_mode == AnswerMode.ask_before_fallback:
            return "doc_specific_refuse"
        return "doc_specific_refuse"

    # --- General question with insufficient KB evidence
    if answer_mode == AnswerMode.strict:
        return "strict_refuse"
    elif answer_mode == AnswerMode.smart_fallback:
        return "general"
    elif answer_mode == AnswerMode.ask_before_fallback:
        if fallback_approved is True:
            return "general"
        elif fallback_approved is False:
            return "strict_refuse"
        else:
            return "ask_fallback"

    return "general"


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
    thread_id = await _ensure_thread(db, payload.thread_id, payload.user_id)
    llm = get_llm_provider()
    answer_mode = payload.answer_mode

    # 2. Check for conversational / greeting queries (skip if specific document attached)
    if is_conversational_query(payload.query) and not payload.doc_filter:
        answer = await llm.generate(payload.query, system_prompt=CONVERSATIONAL_SYSTEM_PROMPT)
        final_citations: List[Citation] = []
        chunks: List[RetrievedChunk] = []
        not_answerable = False
        evidence_status = None
        answer_source = AnswerSource.conversational
        fallback_prompt = None

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
        try:
            chunks, is_answerable = await retrieve(
                query=search_query,
                top_k=payload.top_k,
                use_reranking=payload.use_reranking,
                doc_filter=payload.doc_filter,
            )
            evidence_status = evaluate_evidence(chunks, is_answerable, _settings.retrieval_score_threshold)
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            chunks = []
            is_answerable = False
            evidence_status = EvidenceStatus.retrieval_error

        is_detailed = is_detailed_query(payload.query)
        is_doc_specific = is_document_specific_query(payload.query)
        fallback_prompt = None

        # 6. Route answer decision
        decision = _route_answer_decision(
            answer_mode=answer_mode,
            evidence_status=evidence_status,
            is_doc_specific=is_doc_specific,
            has_doc_filter=bool(payload.doc_filter),
            fallback_approved=payload.fallback_approved,
        )

        if decision == "rag":
            system_prompt = build_rag_system_prompt(memories, is_detailed=is_detailed)
            context = build_rag_context(chunks)
            user_prompt = build_rag_user_prompt(payload.query, context, is_detailed=is_detailed)
            raw_answer = await llm.generate(user_prompt, system_prompt=system_prompt)
            used_indices = parse_citation_markers(raw_answer)
            final_citations = build_citations(used_indices, chunks) if used_indices else []
            answer = raw_answer
            not_answerable = False
            answer_source = AnswerSource.knowledge_base if final_citations else AnswerSource.general_ai

        elif decision == "partial_rag":
            system_prompt = PARTIAL_EVIDENCE_PROMPT
            context = build_rag_context(chunks)
            user_prompt = build_rag_user_prompt(payload.query, context, is_detailed=is_detailed)
            raw_answer = await llm.generate(user_prompt, system_prompt=system_prompt)
            used_indices = parse_citation_markers(raw_answer)
            final_citations = build_citations(used_indices, chunks) if used_indices else []
            answer = raw_answer
            not_answerable = False
            answer_source = AnswerSource.partial_document

        elif decision == "general":
            final_citations = []
            chunks = []
            answer = await llm.generate(payload.query, system_prompt=GENERAL_QA_LABELED_PROMPT)
            not_answerable = False
            answer_source = AnswerSource.general_ai

        elif decision == "strict_refuse":
            final_citations = []
            chunks = []
            answer = STRICT_UNANSWERABLE_RESPONSE
            not_answerable = True
            answer_source = AnswerSource.insufficient_info

        elif decision == "doc_specific_refuse":
            available_docs = await list_documents(db)
            doc_names = [d.file_name for d in available_docs]
            doc_names_str = ", ".join(doc_names) if doc_names else "none"
            answer = (
                f"I couldn't find specific information regarding this in the uploaded documents.\n\n"
                f"**Indexed Documents in Knowledge Base:**\n{doc_names_str}\n\n"
                f"If you have relevant materials on this topic, please upload them to the Knowledge Base."
            )
            final_citations = []
            chunks = []
            not_answerable = True
            answer_source = AnswerSource.insufficient_info

        elif decision == "doc_filter_refuse":
            attached_str = ", ".join(payload.doc_filter)
            answer = (
                f"I couldn't find specific information regarding this in the attached document(s): **{attached_str}**.\n\n"
                f"Please try rephrasing your question or verify the document contents."
            )
            final_citations = []
            chunks = []
            not_answerable = True
            answer_source = AnswerSource.insufficient_info

        elif decision == "ask_fallback":
            answer = ASK_FALLBACK_PROMPT
            final_citations = []
            chunks = []
            not_answerable = True
            answer_source = AnswerSource.pending_fallback
            fallback_prompt = ASK_FALLBACK_PROMPT

        else:
            # Fallback safety
            answer = await llm.generate(payload.query, system_prompt=GENERAL_QA_SYSTEM_PROMPT)
            final_citations = []
            chunks = []
            not_answerable = False
            answer_source = AnswerSource.general_ai

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

    updated_title = await _maybe_update_title(thread_id, payload.query, answer, db=db)

    return ChatResponse(
        message_id=assistant_msg.id,
        thread_id=thread_id,
        thread_title=updated_title,
        answer=answer,
        citations=final_citations,
        retrieved_chunks=chunks,
        latency_ms=latency_ms,
        model=llm.model_name,
        not_answerable=not_answerable,
        evidence_status=evidence_status,
        answer_source=answer_source,
        fallback_prompt=fallback_prompt,
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
        answer_mode = payload.answer_mode

        try:
            # 1. Thread handling
            async with get_session() as db:
                thread_id = await _ensure_thread(
                    db, payload.thread_id, payload.user_id
                )

            # 2. Check for conversational / greeting queries (skip if specific document attached)
            if is_conversational_query(payload.query) and not payload.doc_filter:
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

                updated_title = await _maybe_update_title(thread_id, payload.query, full_response)

                yield {
                    "event": "done",
                    "data": json.dumps({
                        "message_id": msg_id,
                        "thread_id": thread_id,
                        "thread_title": updated_title,
                        "latency_ms": latency_ms,
                        "model": llm.model_name,
                        "not_answerable": False,
                        "evidence_status": None,
                        "answer_source": AnswerSource.conversational.value,
                        "fallback_prompt": None,
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
            try:
                chunks, is_answerable = await retrieve(
                    query=search_query,
                    top_k=payload.top_k,
                    use_reranking=payload.use_reranking,
                    doc_filter=payload.doc_filter,
                )
                evidence_status = evaluate_evidence(chunks, is_answerable, _settings.retrieval_score_threshold)
            except Exception as e:
                logger.error(f"Retrieval failed in stream: {e}")
                chunks = []
                is_answerable = False
                evidence_status = EvidenceStatus.retrieval_error

            is_detailed = is_detailed_query(payload.query)
            is_doc_specific = is_document_specific_query(payload.query)

            # 6. Route answer decision
            decision = _route_answer_decision(
                answer_mode=answer_mode,
                evidence_status=evidence_status,
                is_doc_specific=is_doc_specific,
                has_doc_filter=bool(payload.doc_filter),
                fallback_approved=payload.fallback_approved,
            )

            # --- RAG (sufficient evidence) ---
            if decision == "rag":
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
                final_citations = build_citations(used_indices, chunks) if used_indices else []
                not_answerable = False
                answer_source = AnswerSource.knowledge_base if final_citations else AnswerSource.general_ai

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": [c.model_dump() for c in final_citations]}),
                }

            # --- Partial RAG (partial evidence + general knowledge fill) ---
            elif decision == "partial_rag":
                initial_sources = build_pre_sources(chunks) if chunks else []
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": [s.model_dump() for s in initial_sources]}),
                }

                system_prompt = PARTIAL_EVIDENCE_PROMPT
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
                final_citations = build_citations(used_indices, chunks) if used_indices else []
                not_answerable = False
                answer_source = AnswerSource.partial_document

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": [c.model_dump() for c in final_citations]}),
                }

            # --- General AI knowledge ---
            elif decision == "general":
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": []}),
                }

                async for token in llm.stream(payload.query, system_prompt=GENERAL_QA_LABELED_PROMPT):
                    if token:
                        full_response += token
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}),
                        }

                final_citations = []
                chunks = []
                not_answerable = False
                answer_source = AnswerSource.general_ai

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": []}),
                }

            # --- Strict refuse ---
            elif decision == "strict_refuse":
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": []}),
                }

                full_response = STRICT_UNANSWERABLE_RESPONSE
                async for tok_event in _stream_linear_tokens(full_response):
                    yield tok_event

                final_citations = []
                chunks = []
                not_answerable = True
                answer_source = AnswerSource.insufficient_info

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": []}),
                }

            # --- Document-specific refuse ---
            elif decision == "doc_specific_refuse":
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": []}),
                }

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
                full_response = unanswerable_text
                async for tok_event in _stream_linear_tokens(full_response):
                    yield tok_event

                final_citations = []
                chunks = []
                not_answerable = True
                answer_source = AnswerSource.insufficient_info

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": []}),
                }

            # --- Doc filter refuse ---
            elif decision == "doc_filter_refuse":
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": []}),
                }

                attached_str = ", ".join(payload.doc_filter)
                unanswerable_text = (
                    f"I couldn't find specific information regarding this in the attached document(s): **{attached_str}**.\n\n"
                    f"Please try rephrasing your question or verify the document contents."
                )
                full_response = unanswerable_text
                async for tok_event in _stream_linear_tokens(full_response):
                    yield tok_event

                final_citations = []
                chunks = []
                not_answerable = True
                answer_source = AnswerSource.insufficient_info

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": []}),
                }

            # --- Ask before fallback ---
            elif decision == "ask_fallback":
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": []}),
                }

                full_response = ASK_FALLBACK_PROMPT
                async for tok_event in _stream_linear_tokens(full_response):
                    yield tok_event

                final_citations = []
                chunks = []
                not_answerable = True
                answer_source = AnswerSource.pending_fallback

                yield {
                    "event": "sources_end",
                    "data": json.dumps({"sources": []}),
                }

            else:
                # Safety fallback
                yield {
                    "event": "sources_start",
                    "data": json.dumps({"sources": []}),
                }

                async for token in llm.stream(payload.query, system_prompt=GENERAL_QA_SYSTEM_PROMPT):
                    if token:
                        full_response += token
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}),
                        }

                final_citations = []
                chunks = []
                not_answerable = False
                answer_source = AnswerSource.general_ai

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

            updated_title = await _maybe_update_title(thread_id, payload.query, full_response)

            # Done event
            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": msg_id,
                    "thread_id": thread_id,
                    "thread_title": updated_title,
                    "latency_ms": latency_ms,
                    "model": llm.model_name,
                    "not_answerable": not_answerable,
                    "evidence_status": evidence_status.value if evidence_status else None,
                    "answer_source": answer_source.value if answer_source else None,
                    "fallback_prompt": ASK_FALLBACK_PROMPT if answer_source == AnswerSource.pending_fallback else None,
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
