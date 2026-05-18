"""Checkpointer provider factory.

Provides LangGraph-compatible checkpointer backed by PostgreSQL (production)
or SQLite (development). This enables conversation state persistence, run resume,
and full compatibility with LangGraph Platform API.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


@lru_cache(maxsize=1)
def _get_connection_string() -> str:
    """Resolve database connection string for checkpointer."""
    from agent_platform.config import get_settings

    settings = get_settings()
    db_url = str(settings.DATABASE_URL)
    # langgraph-checkpoint-postgres expects a psycopg (sync-style) URI
    # but works async internally. Convert asyncpg URI if needed.
    if "asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")
    return db_url


def get_checkpointer() -> "BaseCheckpointSaver":
    """Get a configured LangGraph checkpointer instance.

    Uses PostgreSQL in production (when DATABASE_URL is set),
    falls back to in-memory for testing.
    """
    db_url = os.environ.get("DATABASE_URL", "")

    if db_url and "postgresql" in db_url:
        return _make_postgres_checkpointer(db_url)
    else:
        return _make_memory_checkpointer()


def make_checkpointer() -> "BaseCheckpointSaver":
    """Entry point referenced by langgraph.json.

    Returns an async-compatible PostgreSQL checkpointer.
    """
    return get_checkpointer()


def _make_postgres_checkpointer(db_url: str) -> "BaseCheckpointSaver":
    """Create PostgreSQL-backed checkpointer."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    # Normalize URI scheme
    if "asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")

    return AsyncPostgresSaver.from_conn_string(db_url)


def _make_memory_checkpointer() -> "BaseCheckpointSaver":
    """Create in-memory checkpointer for testing/development."""
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
