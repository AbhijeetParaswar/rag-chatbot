"""Unit tests for Answer Modes (Strict, Smart Fallback, Ask Before Fallback)

Tests the evidence classification, routing logic, and schema validation.
"""

import pytest
from backend.app.api.chat import _route_answer_decision
from backend.app.core.prompts import evaluate_evidence
from backend.app.schemas.schemas import AnswerMode, AnswerSource, ChatRequest, EvidenceStatus, RetrievedChunk


def _mock_chunk(idx: int, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chk_{idx}",
        doc_id="doc_1",
        file_name="test.pdf",
        page_start=1,
        page_end=1,
        section_title=None,
        chunk_index=idx,
        text=f"Mock chunk text content {idx}",
        score=score,
    )


class TestEvidenceEvaluation:
    def test_sufficient_evidence(self):
        chunks = [_mock_chunk(1, 0.85), _mock_chunk(2, 0.75)]
        status = evaluate_evidence(chunks, is_answerable=True, score_threshold=0.55)
        assert status == EvidenceStatus.sufficient

    def test_partial_evidence(self):
        chunks = [_mock_chunk(1, 0.60)]
        status = evaluate_evidence(chunks, is_answerable=True, score_threshold=0.55)
        assert status == EvidenceStatus.partial

    def test_insufficient_evidence_low_score(self):
        chunks = [_mock_chunk(1, 0.30)]
        status = evaluate_evidence(chunks, is_answerable=False, score_threshold=0.55)
        assert status == EvidenceStatus.insufficient

    def test_insufficient_evidence_empty(self):
        status = evaluate_evidence([], is_answerable=False, score_threshold=0.55)
        assert status == EvidenceStatus.insufficient


class TestAnswerRouting:
    # ── Mode A: Strict ──────────────────────────────────────────
    def test_strict_sufficient(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.strict,
            evidence_status=EvidenceStatus.sufficient,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=None,
        )
        assert decision == "rag"

    def test_strict_partial(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.strict,
            evidence_status=EvidenceStatus.partial,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=None,
        )
        assert decision == "rag"

    def test_strict_insufficient_refuses(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.strict,
            evidence_status=EvidenceStatus.insufficient,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=None,
        )
        assert decision == "strict_refuse"

    # ── Mode B: Smart Fallback ──────────────────────────────────
    def test_smart_fallback_sufficient_uses_rag(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.smart_fallback,
            evidence_status=EvidenceStatus.sufficient,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=None,
        )
        assert decision == "rag"

    def test_smart_fallback_partial_uses_partial_rag(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.smart_fallback,
            evidence_status=EvidenceStatus.partial,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=None,
        )
        assert decision == "partial_rag"

    def test_smart_fallback_general_falls_back(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.smart_fallback,
            evidence_status=EvidenceStatus.insufficient,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=None,
        )
        assert decision == "general"

    def test_smart_fallback_doc_specific_refuses(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.smart_fallback,
            evidence_status=EvidenceStatus.insufficient,
            is_doc_specific=True,
            has_doc_filter=False,
            fallback_approved=None,
        )
        assert decision == "doc_specific_refuse"

    def test_smart_fallback_doc_filter_refuses(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.smart_fallback,
            evidence_status=EvidenceStatus.insufficient,
            is_doc_specific=False,
            has_doc_filter=True,
            fallback_approved=None,
        )
        assert decision == "doc_filter_refuse"

    # ── Mode C: Ask Before Fallback ─────────────────────────────
    def test_ask_before_fallback_prompts_user(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.ask_before_fallback,
            evidence_status=EvidenceStatus.insufficient,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=None,
        )
        assert decision == "ask_fallback"

    def test_ask_before_fallback_approved(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.ask_before_fallback,
            evidence_status=EvidenceStatus.insufficient,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=True,
        )
        assert decision == "general"

    def test_ask_before_fallback_rejected(self):
        decision = _route_answer_decision(
            answer_mode=AnswerMode.ask_before_fallback,
            evidence_status=EvidenceStatus.insufficient,
            is_doc_specific=False,
            has_doc_filter=False,
            fallback_approved=False,
        )
        assert decision == "strict_refuse"


class TestChatRequestSchema:
    def test_default_answer_mode(self):
        req = ChatRequest(query="What is RAG?")
        assert req.answer_mode == AnswerMode.smart_fallback
        assert req.fallback_approved is None

    def test_custom_answer_mode(self):
        req = ChatRequest(query="What is RAG?", answer_mode=AnswerMode.strict)
        assert req.answer_mode == AnswerMode.strict
