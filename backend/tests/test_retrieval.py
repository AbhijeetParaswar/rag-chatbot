"""Integration tests for retriever vector search and metadata accuracy."""

import pytest
from backend.app.core.retriever import retrieve


@pytest.mark.asyncio
async def test_retrieval_returns_correct_page_metadata():
    # Query for something specific in cs101_syllabus.pdf
    query = "What is the grading breakdown for CS 101 assignments and midterm?"
    chunks, is_answerable = await retrieve(query=query, top_k=3)

    assert len(chunks) > 0
    assert is_answerable is True

    # Best chunk should be from cs101_syllabus.pdf
    top_chunk = chunks[0]
    assert "syllabus" in top_chunk.file_name.lower()
    assert top_chunk.page_start in (1, 2)
    assert top_chunk.score > 0.4
    assert "grading" in top_chunk.text.lower() or "assignments" in top_chunk.text.lower()


@pytest.mark.asyncio
async def test_retrieval_unanswerable_query():
    # Query completely unrelated to syllabus, policy, or deep learning
    query = "What is the capital city of ancient Atlantis and how to build a submarine?"
    chunks, is_answerable = await retrieve(query=query, top_k=3, score_threshold=0.85)

    # Either empty or below the strict threshold
    assert is_answerable is False
