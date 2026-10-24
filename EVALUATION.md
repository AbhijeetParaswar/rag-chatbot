# Evaluation Framework & Benchmark (Phase 2 Stub)

This document is a placeholder for the forthcoming RAG benchmark and golden dataset evaluation harness.

## Objective
Measure retrieval accuracy, citation faithfulness, hallucination rate, and answer relevancy using a golden QA dataset paired with the ingested PDFs.

## Architecture & Integration
The backend endpoint `POST /chat` is intentionally designed to support direct evaluation integration. It synchronously returns the full JSON response containing:
- `answer`: generated text response
- `citations`: list of parsed and validated citation objects (`file_name`, `page_start`, `page_end`, `section_title`, `snippet`)
- `retrieved_chunks`: all candidate chunks returned by vector search/reranking with cosine similarity `score`
- `latency_ms`: end-to-end processing duration
- `not_answerable`: boolean flag identifying queries guarded by similarity threshold

## Planned Metrics
1. **Context Precision & Recall**: Percentage of golden chunk citations retrieved in the top-$K$.
2. **Citation Faithfulness**: Percentage of claims with valid `[n]` citations grounded in the source passage.
3. **Hallucination Rate**: Verification that unanswerable questions trigger `not_answerable=true` and yield no fabricated citations.
4. **End-to-End Latency**: Median and P95 latency distribution.

*Golden dataset creation and test automation script will be added in Phase 2.*
