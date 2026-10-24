"""Unit tests for PDF text chunking and heading detection."""

import pytest
from backend.app.core.chunking import (
    Chunk,
    PageText,
    chunk_pages,
    detect_headings,
)


def test_detect_headings():
    sample_text = (
        "Section 1. Introduction to Machine Learning\n"
        "Here is some text about the basics.\n\n"
        "Unit 2: Supervised Learning Techniques\n"
        "More descriptions here.\n"
    )
    headings = detect_headings(sample_text)
    assert len(headings) >= 2
    assert any("Introduction" in h for h in headings)
    assert any("Supervised Learning" in h for h in headings)


def test_chunking_metadata():
    pages = [
        PageText(
            page_number=1,
            text="Section 1. Overview\n" + ("This is detailed algorithm text. " * 40),
            headings=["Section 1. Overview"],
        ),
        PageText(
            page_number=2,
            text="Section 2. Advanced Topics\n" + ("This is advanced graph text. " * 30),
            headings=["Section 2. Advanced Topics"],
        ),
    ]

    chunks = chunk_pages(
        pages=pages,
        doc_id="test_doc_123",
        file_name="algorithms.pdf",
        chunk_size=400,
        chunk_overlap=50,
    )

    assert len(chunks) > 1

    # Validate every chunk metadata requirement
    for c in chunks:
        assert isinstance(c, Chunk)
        assert c.doc_id == "test_doc_123"
        assert c.file_name == "algorithms.pdf"
        assert c.chunk_id is not None and len(c.chunk_id) > 0
        assert c.page_start in (1, 2)
        assert c.page_end in (1, 2)
        assert c.page_start <= c.page_end
        assert c.char_start >= 0
        assert c.char_end > c.char_start
        assert isinstance(c.chunk_index, int)
        assert len(c.text) > 0
