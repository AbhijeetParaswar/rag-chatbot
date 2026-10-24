"""PDF text chunking with page-boundary awareness and heading detection.

Produces chunks with rich metadata suitable for ChromaDB ingestion.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from backend.app.config import get_settings

_settings = get_settings()


@dataclass
class PageText:
    """Raw text extracted from a single PDF page."""
    page_number: int       # 1-indexed
    text: str
    headings: List[str] = field(default_factory=list)


@dataclass
class Chunk:
    """A single text chunk with metadata."""
    chunk_id: str           # stable hash-based ID
    doc_id: str
    file_name: str
    text: str
    page_start: int
    page_end: int
    section_title: Optional[str]
    chunk_index: int
    char_start: int
    char_end: int


# ── Heading detection ────────────────────────────

# Common heading patterns in academic/policy PDFs
_HEADING_PATTERNS = [
    # "Chapter 1:", "Unit 1:", "Section 2.3"
    re.compile(r"^(Chapter|Unit|Section|Part|Module)\s+[\dIVXivx]+[.:]\s*(.+)", re.IGNORECASE | re.MULTILINE),
    # "1. Introduction", "2.3 Methods", "1.1.1 Sub-section"
    re.compile(r"^(\d+\.[\d.]*)\s+([A-Z][^\n]{2,80})$", re.MULTILINE),
    # ALL CAPS lines that are likely headings
    re.compile(r"^([A-Z][A-Z\s]{4,60})$", re.MULTILINE),
]


def detect_headings(text: str) -> List[str]:
    """Extract likely heading/section titles from page text."""
    headings = []
    for pattern in _HEADING_PATTERNS:
        for match in pattern.finditer(text):
            heading = match.group(0).strip()
            if len(heading) > 3 and heading not in headings:
                headings.append(heading)
    return headings[:5]  # cap to avoid noise


def _current_section(headings_so_far: List[str]) -> Optional[str]:
    """Return the most recent section title."""
    return headings_so_far[-1] if headings_so_far else None


# ── Chunking logic ───────────────────────────────

def _stable_chunk_id(doc_id: str, chunk_index: int, text: str) -> str:
    """Generate a deterministic chunk ID from content."""
    raw = f"{doc_id}:{chunk_index}:{text[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _split_text_recursive(
    text: str,
    max_size: int,
    overlap: int,
    separators: Tuple[str, ...] = ("\n\n", "\n", ". ", " "),
) -> List[str]:
    """Recursively split text on separators, with overlap."""
    if len(text) <= max_size:
        return [text] if text.strip() else []

    # Try each separator in order of preference
    for sep in separators:
        parts = text.split(sep)
        if len(parts) <= 1:
            continue

        chunks = []
        current = ""
        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) > max_size and current:
                chunks.append(current.strip())
                # Overlap: keep the tail of current
                if overlap > 0:
                    current = current[-overlap:] + sep + part
                else:
                    current = part
            else:
                current = candidate

        if current.strip():
            chunks.append(current.strip())

        if len(chunks) > 1:
            return chunks

    # Fallback: hard split at max_size
    chunks = []
    for i in range(0, len(text), max_size - overlap):
        chunk = text[i : i + max_size]
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks


def chunk_pages(
    pages: List[PageText],
    doc_id: str,
    file_name: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Chunk]:
    """Split page texts into overlapping chunks, respecting page boundaries.

    Each chunk stays within a single page unless the page text is shorter
    than the overlap, in which case adjacent pages may be merged.

    Parameters
    ----------
    pages : list of PageText
        Extracted page texts with headings.
    doc_id : str
        The document identifier.
    file_name : str
        The original PDF file name.
    chunk_size : int, optional
        Max characters per chunk. Defaults to config.
    chunk_overlap : int, optional
        Overlap characters. Defaults to config.

    Returns
    -------
    list of Chunk
        Chunks with full metadata.
    """
    size = chunk_size or _settings.chunk_size
    overlap = chunk_overlap or _settings.chunk_overlap

    all_chunks: List[Chunk] = []
    chunk_index = 0
    all_headings: List[str] = []

    for page in pages:
        # Accumulate headings for section tracking
        all_headings.extend(page.headings)
        section = _current_section(all_headings)

        if not page.text.strip():
            continue

        # Split this page's text
        fragments = _split_text_recursive(page.text, size, overlap)

        char_offset = 0
        for frag in fragments:
            char_start = page.text.find(frag[:50], char_offset)
            if char_start == -1:
                char_start = char_offset
            char_end = char_start + len(frag)

            cid = _stable_chunk_id(doc_id, chunk_index, frag)
            all_chunks.append(
                Chunk(
                    chunk_id=cid,
                    doc_id=doc_id,
                    file_name=file_name,
                    text=frag,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    section_title=section,
                    chunk_index=chunk_index,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
            chunk_index += 1
            char_offset = max(char_offset, char_end - overlap)

    return all_chunks
