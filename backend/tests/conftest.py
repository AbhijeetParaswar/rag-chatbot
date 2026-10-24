"""Pytest fixtures for unit and integration testing."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, List, Optional
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import Settings, get_settings
from backend.app.core.llm import LLMProvider
from backend.app.db.models import Base
from backend.app.db.session import get_db
from backend.app.main import app


# Test database engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


class MockLLMProvider(LLMProvider):
    """Mock LLM returning deterministic responses with citations."""

    def __init__(self, answer: str = "According to the syllabus [1], assignments are 30% and the final is 35% [2]."):
        self._answer = answer

    @property
    def model_name(self) -> str:
        return "mock-llm-v1"

    async def stream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        tokens = self._answer.split(" ")
        for i, token in enumerate(tokens):
            yield token + (" " if i < len(tokens) - 1 else "")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return self._answer
