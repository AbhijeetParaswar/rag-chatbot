"""Citation parsing, validation, and formatting.

Parses [n] markers from LLM output, validates them against retrieved chunks,
and builds formatted citation lists for display.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from backend.app.schemas.schemas import Citation, RetrievedChunk


# Regex to find citation markers like [1], [2], [1][3], etc.
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")

# Extended pattern to match alternative formats emitted by certain LLMs (e.g. 【1†L1-L5】, 【1】, ［1］, [1†source])
_EXTENDED_CITATION_PATTERN = re.compile(r"[\[【［](\d+)(?:[†:][^\]】］]*)?[\]】］]")


def normalize_citation_markers(text: str) -> str:
    """Normalize non-standard citation markers like 【1†L1-L5】 or [1†source] to standard [1].

    Parameters
    ----------
    text : str
        The raw LLM output text.

    Returns
    -------
    str
        Text with all citation markers converted to standard [n] format.
    """
    return _EXTENDED_CITATION_PATTERN.sub(r"[\1]", text)


def parse_citation_markers(text: str) -> Set[int]:
    """Extract all unique citation indices from model output.

    Handles standard [1] markers as well as fullwidth brackets and tags like
    【1†L1-L5】 or 【1】.

    Parameters
    ----------
    text : str
        The LLM's response text.

    Returns
    -------
    set of int
        Unique 1-based citation indices found in the text.
    """
    return {int(m.group(1)) for m in _EXTENDED_CITATION_PATTERN.finditer(text)}


def validate_citations(
    used_indices: Set[int],
    chunks: List[RetrievedChunk],
) -> Tuple[List[int], List[int]]:
    """Validate citation indices against available chunks.

    Parameters
    ----------
    used_indices : set of int
        Citation indices found in the LLM output.
    chunks : list of RetrievedChunk
        The retrieved chunks (1-indexed by position).

    Returns
    -------
    tuple of (valid_indices, invalid_indices)
        Lists of valid and invalid citation indices.
    """
    max_index = len(chunks)
    valid = sorted(i for i in used_indices if 1 <= i <= max_index)
    invalid = sorted(i for i in used_indices if i < 1 or i > max_index)
    return valid, invalid


def build_citations(
    used_indices: Set[int],
    chunks: List[RetrievedChunk],
    snippet_length: int = 100,
) -> List[Citation]:
    """Build formatted citation objects from used indices.

    Only includes citations that map to real chunks (validates internally).

    Parameters
    ----------
    used_indices : set of int
        Citation indices from model output.
    chunks : list of RetrievedChunk
        The retrieved chunks in order.
    snippet_length : int
        Max length of the text snippet in each citation.

    Returns
    -------
    list of Citation
        Formatted citations with file name, page, section, and snippet.
    """
    valid, invalid = validate_citations(used_indices, chunks)

    citations = []
    for idx in valid:
        chunk = chunks[idx - 1]  # Convert to 0-indexed
        snippet = chunk.text[:snippet_length].strip()
        if len(chunk.text) > snippet_length:
            snippet += "…"

        citations.append(
            Citation(
                index=idx,
                file_name=chunk.file_name,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_title=chunk.section_title,
                snippet=snippet,
            )
        )

    return citations


def build_pre_sources(chunks: List[RetrievedChunk], snippet_length: int = 80) -> List[Citation]:
    """Build the 'Sources used' block shown before the answer streams.

    Lists all retrieved chunks as potential sources.
    """
    sources = []
    for i, chunk in enumerate(chunks, 1):
        snippet = chunk.text[:snippet_length].strip()
        if len(chunk.text) > snippet_length:
            snippet += "…"

        sources.append(
            Citation(
                index=i,
                file_name=chunk.file_name,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_title=chunk.section_title,
                snippet=snippet,
            )
        )
    return sources


def format_citation_footer(citations: List[Citation]) -> str:
    """Format citations as a readable footer string.

    Example output:
        [1] syllabus.pdf — p. 4, Section 2.3 "Grading"
        [2] policy.pdf — p. 12
    """
    if not citations:
        return "No relevant source found."

    lines = []
    for c in citations:
        parts = [f"[{c.index}] {c.file_name} — p. {c.page_start}"]
        if c.page_end != c.page_start:
            parts[0] = f"[{c.index}] {c.file_name} — pp. {c.page_start}–{c.page_end}"
        if c.section_title:
            parts.append(f'Section "{c.section_title}"')
        lines.append(", ".join(parts))
    return "\n".join(lines)


def clean_invalid_citations(text: str, chunks: List[RetrievedChunk]) -> str:
    """Remove invalid citation markers from model output.

    Replaces [n] markers that don't correspond to any chunk, and normalizes
    valid markers to standard [n] format.
    """
    max_index = len(chunks)

    def _replace(match: re.Match) -> str:
        idx = int(match.group(1))
        if 1 <= idx <= max_index:
            return f"[{idx}]"  # Keep valid and normalized
        return ""  # Remove invalid

    return _EXTENDED_CITATION_PATTERN.sub(_replace, text)
