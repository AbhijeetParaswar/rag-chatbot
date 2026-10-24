"""SQLAlchemy ORM models for the RAG chatbot.

Tables
------
- users       – simple user tracking (default user for single-user mode)
- threads     – conversation threads with optional title & summary
- messages    – individual messages within a thread (role, content, citations)
- memories    – long-term per-user memories extracted from conversations
- documents   – metadata for ingested PDF files (hash, page count, etc.)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """Shared base for all ORM models."""


class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=_new_id)
    name = Column(String(128), nullable=False, default="default")
    created_at = Column(DateTime, default=_utcnow)

    threads = relationship("Thread", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")


class Thread(Base):
    __tablename__ = "threads"

    id = Column(String(32), primary_key=True, default=_new_id)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False)
    title = Column(String(256), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="threads")
    messages = relationship(
        "Message", back_populates="thread", cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(32), primary_key=True, default=_new_id)
    thread_id = Column(String(32), ForeignKey("threads.id"), nullable=False)
    role = Column(String(16), nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    citations_json = Column(Text, nullable=True)        # JSON array of citation objects
    retrieved_chunks_json = Column(Text, nullable=True)  # JSON array of chunk metadata
    latency_ms = Column(Float, nullable=True)
    model = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    thread = relationship("Thread", back_populates="messages")


class Memory(Base):
    __tablename__ = "memories"

    id = Column(String(32), primary_key=True, default=_new_id)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    source_thread_id = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="memories")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(32), primary_key=True, default=_new_id)
    file_name = Column(String(512), nullable=False, unique=True)
    hash = Column(String(64), nullable=False)
    pages = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    indexed_at = Column(DateTime, default=_utcnow)
