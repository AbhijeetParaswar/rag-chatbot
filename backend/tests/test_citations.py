"""Unit tests for citation marker parsing and validation."""

import pytest
from backend.app.core.citations import (
    build_citations,
    build_pre_sources,
    clean_invalid_citations,
    format_citation_footer,
    parse_citation_markers,
    validate_citations,
)
from backend.app.schemas.schemas import RetrievedChunk


def _mock_chunk(idx: int, file_name: str, page: int, section: str = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chk_{idx}",
        doc_id="doc_1",
        file_name=file_name,
        page_start=page,
        page_end=page,
        section_title=section,
        chunk_index=idx - 1,
        text=f"Text for chunk {idx} regarding academic policies and grading.",
        score=0.88,
    )


def test_parse_citation_markers():
    text = "The midterm is worth 25% [1] and homework is 30% [2]. Also note [1][3]."
    indices = parse_citation_markers(text)
    assert indices == {1, 2, 3}


def test_validate_citations():
    chunks = [_mock_chunk(1, "doc.pdf", 1), _mock_chunk(2, "doc.pdf", 2)]
    used = {1, 2, 5, 0}
    valid, invalid = validate_citations(used, chunks)
    assert valid == [1, 2]
    assert invalid == [0, 5]


def test_build_citations():
    chunks = [
        _mock_chunk(1, "syllabus.pdf", 1, "Grading"),
        _mock_chunk(2, "policy.pdf", 4, "Plagiarism"),
    ]
    used = {1, 99}  # 99 is invalid and must be dropped
    citations = build_citations(used, chunks)
    assert len(citations) == 1
    assert citations[0].index == 1
    assert citations[0].file_name == "syllabus.pdf"
    assert citations[0].page_start == 1
    assert citations[0].section_title == "Grading"


def test_format_citation_footer():
    chunks = [_mock_chunk(1, "syllabus.pdf", 4, "Section 2.3 Grading")]
    citations = build_citations({1}, chunks)
    footer = format_citation_footer(citations)
    assert "syllabus.pdf" in footer
    assert "p. 4" in footer
    assert "Section 2.3 Grading" in footer


def test_clean_invalid_citations():
    chunks = [_mock_chunk(1, "doc.pdf", 1)]
    text = "Valid [1] but invalid [9] here."
    cleaned = clean_invalid_citations(text, chunks)
    assert cleaned == "Valid [1] but invalid  here."
