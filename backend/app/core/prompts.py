"""Prompt templates for the RAG chatbot.

All document text is wrapped in data fences to defend against prompt injection.
"""

from __future__ import annotations

from typing import List, Optional

from backend.app.schemas.schemas import RetrievedChunk


import re

# ── Query Intent Classification ──────────────────

_CONVERSATIONAL_PATTERNS = [
    r"^(hi|hello|hey|heya|howdy|hola|greetings|yo)(\s*|\s+.*)$",
    r"^(good\s+(morning|afternoon|evening|night|day))(\s*|\s+.*)$",
    r"^(how\s+are\s+you|how\'s\s+it\s+going|how\s+do\s+you\s+do|how\s+are\s+things)(\s*|\s+.*)$",
    r"^(who\s+are\s+you|what\s+are\s+you|what\s+is\s+your\s+name|introduce\s+yourself|what\s+can\s+you\s+do|tell\s+me\s+about\s+yourself)(\s*|\s+.*)$",
    r"^(thank\s+you|thanks|thx|thank\s+you\s+so\s+much|thanks\s+a\s+lot)(\s*|\s+.*)$",
    r"^(bye|goodbye|see\s+you|cya|take\s+care)(\s*|\s+.*)$",
    r"^(help|can\s+you\s+help\s+me|help\s+me)(\s*|\s+.*)$",
    r"^(what\'s\s+up|wassup|sup)(\s*|\s+.*)$",
    r"^(tell\s+me\s+a\s+joke|make\s+me\s+laugh)(\s*|\s+.*)$",
]

_DOC_SPECIFIC_KEYWORDS = {
    "document", "documents", "pdf", "pdfs", "knowledge base", "uploaded",
    "syllabus", "cs101", "policy", "academic integrity", "survey",
    "paper", "course", "grading", "assignment", "rubric", "in the text",
    "in the document", "according to the document", "according to the pdf",
}

_DETAILED_KEYWORDS = {
    "detailed", "detail", "in detail", "thoroughly", "explain thoroughly",
    "comprehensive", "deep dive", "deeply", "step by step", "elaborate",
    "breakdown", "complete explanation", "full overview"
}


def is_conversational_query(query: str) -> bool:
    """Check if the query is a greeting, polite remark, or general small talk."""
    cleaned = query.strip().lower()
    if not cleaned:
        return True
    # Strip basic punctuation
    cleaned = re.sub(r"[?!.,;]+$", "", cleaned).strip()
    for pattern in _CONVERSATIONAL_PATTERNS:
        if re.match(pattern, cleaned, re.IGNORECASE):
            return True
    return False


def is_document_specific_query(query: str) -> bool:
    """Check if the user is explicitly asking about uploaded documents/knowledge base."""
    cleaned = query.strip().lower()
    return any(kw in cleaned for kw in _DOC_SPECIFIC_KEYWORDS)


def is_detailed_query(query: str) -> bool:
    """Check if the user explicitly requested a detailed or in-depth answer."""
    cleaned = query.strip().lower()
    return any(kw in cleaned for kw in _DETAILED_KEYWORDS)


# ── System Prompts ───────────────────────────────

CONVERSATIONAL_SYSTEM_PROMPT = """You are DocuRAG Assistant, a friendly, intelligent, and helpful AI assistant.

Guidelines:
1. Respond to greetings, polite inquiries, and conversational remarks in a warm, polite, and natural tone.
2. If asked who you are or what you can do, explain that you can chat normally as well as provide detailed, document-grounded answers based on PDFs uploaded to the Knowledge Base.
3. Keep greetings concise and natural (1-3 sentences).
4. Do NOT say "I couldn't find this in the provided documents" for normal conversational messages."""


GENERAL_QA_SYSTEM_PROMPT = """You are DocuRAG Assistant, a knowledgeable, clear, and helpful AI assistant.

Guidelines:
1. Answer the user's question directly, clearly, and accurately.
2. Provide a normal, well-structured response as per the question asked.
3. If the user asks for a simple answer, keep it concise. If they ask for a detailed answer, provide a thorough breakdown.
4. Do NOT pretend to cite documents or invent citation markers [n] when answering general questions."""


def build_rag_system_prompt(
    memories: Optional[List[str]] = None,
    is_detailed: bool = False,
) -> str:
    """Build the system prompt for RAG answer generation.

    Parameters
    ----------
    memories : list of str, optional
        Long-term user memories to inject (never used as factual sources).
    is_detailed : bool
        Whether the user requested a detailed, thorough answer.
    """
    memory_section = ""
    if memories:
        memory_lines = "\n".join(f"- {m}" for m in memories)
        memory_section = (
            "\n\n## User Context (from long-term memory, NOT a document source)\n"
            "These are things you know about the user. Use them to personalize "
            "your response style, but NEVER cite these as document sources:\n"
            f"{memory_lines}\n"
        )

    detail_instruction = (
        "Provide a comprehensive, in-depth, and well-structured answer with clear headings, bullet points, and deep technical or policy detail as present in the passages."
        if is_detailed
        else "Provide a clear, accurate, and direct answer as per the user's question based on the passages."
    )

    return f"""You are DocuRAG Assistant, a precise, helpful document Q&A assistant. You answer questions grounded in the provided document passages.

## INSTRUCTIONS:
1. Ground your answer in the retrieved document passages provided below.
2. {detail_instruction}
3. Cite your sources inline using [1], [2], etc. immediately after each factual claim. The numbers correspond to the passage numbers in the context.
4. If multiple passages support a claim, cite all of them: [1][2].
5. NEVER fabricate or hallucinate information or citation markers.
6. Use clean GitHub-flavored markdown formatting.
{memory_section}"""


def build_rag_context(chunks: List[RetrievedChunk]) -> str:
    """Format retrieved chunks as numbered passages for the LLM.

    Document text is wrapped in data fences to prevent prompt injection.
    """
    if not chunks:
        return "No relevant passages were found in the documents."

    passages = []
    for i, chunk in enumerate(chunks, 1):
        section_info = f", Section: {chunk.section_title}" if chunk.section_title else ""
        header = f"[{i}] {chunk.file_name} — Page {chunk.page_start}{section_info}"
        passages.append(
            f"{header}\n"
            f"<document_passage>\n{chunk.text}\n</document_passage>"
        )

    return "## Retrieved Document Passages:\n\n" + "\n\n".join(passages)


def build_rag_user_prompt(query: str, context: str, is_detailed: bool = False) -> str:
    """Build the user prompt with context, query, and detail instructions."""
    detail_guidance = (
        "Please provide a detailed, comprehensive answer covering all relevant points from the passages."
        if is_detailed
        else "Answer the question directly as per what is asked, citing sources inline with [n] markers."
    )
    return f"""{context}

## Question:
{query}

## Instructions:
{detail_guidance}
Cite inline with [n] markers.
"""


# ── Supporting prompts ───────────────────────────

MEMORY_EXTRACTION_PROMPT = """Analyze the following conversation exchange and extract any durable facts or preferences about the user.

Examples of extractable facts:
- "User is a 2nd-year CS student"
- "User prefers concise answers"
- "User is studying for exams in data structures"
- "User's name is Alex"

Rules:
- Extract ONLY factual, durable information about the user
- Do NOT extract information about the documents or questions asked
- Return each fact on a separate line, prefixed with "- "
- If no durable facts are found, return "NONE"

Conversation:
User: {user_message}
Assistant: {assistant_message}

Extracted facts:"""


SUMMARY_PROMPT = """Summarize the following conversation messages into a concise summary that captures the key topics discussed and any important context. Keep it under 200 words.

Messages:
{messages}

Summary:"""


TITLE_GENERATION_PROMPT = """Generate a short, descriptive title (3-8 words) for a conversation that starts with this message. Return ONLY the title, no quotes or punctuation.

Message: {message}

Title:"""
