"""CRUD helpers for the database models.

All functions accept an AsyncSession and return ORM objects or lists.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import Document, Memory, Message, Thread, User


# ──────────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────────

async def get_or_create_user(db: AsyncSession, user_id: str = "default") -> User:
    """Return existing user or create one."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=user_id, name=user_id)
        db.add(user)
        await db.flush()
    return user


# ──────────────────────────────────────────────────
# Threads
# ──────────────────────────────────────────────────

async def create_thread(
    db: AsyncSession,
    user_id: str = "default",
    title: Optional[str] = None,
) -> Thread:
    """Create a new conversation thread."""
    user = await get_or_create_user(db, user_id)
    thread = Thread(user_id=user.id, title=title)
    db.add(thread)
    await db.flush()
    return thread


async def list_threads(db: AsyncSession, user_id: str = "default") -> List[Thread]:
    """List all threads for a user, newest first."""
    result = await db.execute(
        select(Thread)
        .where(Thread.user_id == user_id)
        .options(selectinload(Thread.messages))
        .order_by(Thread.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_thread(db: AsyncSession, thread_id: str) -> Optional[Thread]:
    """Get a single thread with messages eagerly loaded."""
    result = await db.execute(
        select(Thread)
        .where(Thread.id == thread_id)
        .options(selectinload(Thread.messages))
    )
    return result.scalar_one_or_none()


async def update_thread(
    db: AsyncSession,
    thread_id: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
) -> Optional[Thread]:
    """Update thread title and/or summary."""
    values = {"updated_at": datetime.now(timezone.utc)}
    if title is not None:
        values["title"] = title
    if summary is not None:
        values["summary"] = summary
    await db.execute(
        update(Thread).where(Thread.id == thread_id).values(**values)
    )
    await db.flush()
    return await get_thread(db, thread_id)


async def delete_thread(db: AsyncSession, thread_id: str) -> bool:
    """Delete a thread and its messages (cascade)."""
    result = await db.execute(
        delete(Thread).where(Thread.id == thread_id)
    )
    return result.rowcount > 0


# ──────────────────────────────────────────────────
# Messages
# ──────────────────────────────────────────────────

async def add_message(
    db: AsyncSession,
    thread_id: str,
    role: str,
    content: str,
    citations_json: Optional[str] = None,
    retrieved_chunks_json: Optional[str] = None,
    latency_ms: Optional[float] = None,
    model: Optional[str] = None,
) -> Message:
    """Add a message to a thread."""
    msg = Message(
        thread_id=thread_id,
        role=role,
        content=content,
        citations_json=citations_json,
        retrieved_chunks_json=retrieved_chunks_json,
        latency_ms=latency_ms,
        model=model,
    )
    db.add(msg)
    await db.flush()
    # Update thread's updated_at
    await db.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    await db.flush()
    return msg


async def get_thread_messages(
    db: AsyncSession,
    thread_id: str,
    limit: Optional[int] = None,
) -> List[Message]:
    """Get messages for a thread, ordered by creation time."""
    stmt = (
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at.asc())
    )
    if limit:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ──────────────────────────────────────────────────
# Memories
# ──────────────────────────────────────────────────

async def add_memory(
    db: AsyncSession,
    user_id: str,
    text: str,
    source_thread_id: Optional[str] = None,
) -> Memory:
    """Add a long-term memory for a user."""
    mem = Memory(user_id=user_id, text=text, source_thread_id=source_thread_id)
    db.add(mem)
    await db.flush()
    return mem


async def list_memories(db: AsyncSession, user_id: str = "default") -> List[Memory]:
    """List all memories for a user."""
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_memory(db: AsyncSession, memory_id: str) -> bool:
    """Delete a specific memory."""
    result = await db.execute(
        delete(Memory).where(Memory.id == memory_id)
    )
    return result.rowcount > 0


# ──────────────────────────────────────────────────
# Documents
# ──────────────────────────────────────────────────

async def upsert_document(
    db: AsyncSession,
    file_name: str,
    file_hash: str,
    pages: int,
    chunk_count: int,
) -> Document:
    """Insert or update a document record."""
    result = await db.execute(
        select(Document).where(Document.file_name == file_name)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        doc = Document(
            file_name=file_name,
            hash=file_hash,
            pages=pages,
            chunk_count=chunk_count,
        )
        db.add(doc)
    else:
        doc.hash = file_hash
        doc.pages = pages
        doc.chunk_count = chunk_count
        doc.indexed_at = datetime.now(timezone.utc)
    await db.flush()
    return doc


async def get_document_by_name(db: AsyncSession, file_name: str) -> Optional[Document]:
    """Find a document by file name."""
    result = await db.execute(
        select(Document).where(Document.file_name == file_name)
    )
    return result.scalar_one_or_none()


async def get_document_by_hash(db: AsyncSession, file_hash: str) -> Optional[Document]:
    """Find a document by content hash."""
    result = await db.execute(
        select(Document).where(Document.hash == file_hash)
    )
    return result.scalar_one_or_none()


async def list_documents(db: AsyncSession) -> List[Document]:
    """List all indexed documents."""
    result = await db.execute(
        select(Document).order_by(Document.indexed_at.desc())
    )
    return list(result.scalars().all())
