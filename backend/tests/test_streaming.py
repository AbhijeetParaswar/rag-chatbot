"""Integration tests for Server-Sent Events (SSE) streaming chat."""

import json
from unittest.mock import patch
import pytest
from httpx import AsyncClient

from backend.tests.conftest import MockLLMProvider


@pytest.mark.asyncio
async def test_chat_sse_stream_events(async_client: AsyncClient):
    mock_llm = MockLLMProvider(
        answer="According to the syllabus [1], assignments are 30% and final exam is 35%."
    )

    with patch("backend.app.api.chat.get_llm_provider", return_value=mock_llm):
        async with async_client.stream(
            "POST",
            "/chat/stream",
            json={"query": "What is the weight of assignments in CS101?", "user_id": "test_user"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            events = []
            current_event = None
            current_data = []

            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                elif line.startswith("data:"):
                    current_data.append(line.replace("data:", "").strip())
                elif line == "" and current_event:
                    events.append({
                        "event": current_event,
                        "data": "\n".join(current_data),
                    })
                    current_event = None
                    current_data = []

            # Verify typed events sequence
            event_types = [e["event"] for e in events]
            assert "sources_start" in event_types
            assert "token" in event_types
            assert "sources_end" in event_types
            assert "done" in event_types

            # Verify sources_start data
            sources_start = next(e for e in events if e["event"] == "sources_start")
            s_data = json.loads(sources_start["data"])
            assert "sources" in s_data
            assert len(s_data["sources"]) > 0

            # Verify sources_end data
            sources_end = next(e for e in events if e["event"] == "sources_end")
            e_data = json.loads(sources_end["data"])
            assert "sources" in e_data
            # Model cited [1] so at least 1 verified citation should be returned
            assert len(e_data["sources"]) >= 1
            assert e_data["sources"][0]["index"] == 1

            # Verify done event metadata
            done_ev = next(e for e in events if e["event"] == "done")
            d_data = json.loads(done_ev["data"])
            assert "message_id" in d_data
            assert "thread_id" in d_data
            assert "latency_ms" in d_data
            assert d_data["not_answerable"] is False
