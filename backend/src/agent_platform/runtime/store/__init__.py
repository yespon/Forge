"""LangGraph-compatible Store (BaseStore) backed by PostgreSQL.

Provides a key-value store for long-term agent memory and state
that persists across threads. Compatible with LangGraph's Store API.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class StoreItem:
    """A single item in the store."""

    __slots__ = ("namespace", "key", "value", "created_at", "updated_at")

    def __init__(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.namespace = namespace
        self.key = key
        self.value = value
        self.created_at = created_at
        self.updated_at = updated_at


class ForgeStore:
    """PostgreSQL-backed key-value store for LangGraph.

    Implements the LangGraph BaseStore protocol for use with
    `langgraph.store`. Data is stored in a JSONB column keyed
    by (namespace, key) tuples.

    Namespaces allow hierarchical organization:
      ("user", user_id, "preferences")
      ("thread", thread_id, "state")
    """

    def __init__(self, connection_string: Optional[str] = None):
        self._conn_string = connection_string
        self._table_created = False

    async def _ensure_table(self, conn) -> None:
        """Create the store table if it doesn't exist."""
        if self._table_created:
            return
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS langgraph_store (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                namespace TEXT[] NOT NULL,
                key TEXT NOT NULL,
                value JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(namespace, key)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_store_namespace ON langgraph_store USING GIN(namespace)
        """)
        self._table_created = True

    async def get(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> Optional[StoreItem]:
        """Get a single item by namespace and key."""
        from agent_platform.database import engine

        async with engine.begin() as conn:
            await self._ensure_table(conn)
            result = await conn.execute(
                """
                SELECT namespace, key, value, created_at, updated_at
                FROM langgraph_store
                WHERE namespace = :ns AND key = :key
                """,
                {"ns": list(namespace), "key": key},
            )
            row = result.first()
            if row:
                return StoreItem(
                    namespace=tuple(row.namespace),
                    key=row.key,
                    value=row.value,
                    created_at=str(row.created_at),
                    updated_at=str(row.updated_at),
                )
        return None

    async def put(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Put an item (upsert)."""
        from agent_platform.database import engine

        async with engine.begin() as conn:
            await self._ensure_table(conn)
            await conn.execute(
                """
                INSERT INTO langgraph_store (namespace, key, value)
                VALUES (:ns, :key, :value)
                ON CONFLICT (namespace, key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = NOW()
                """,
                {"ns": list(namespace), "key": key, "value": value},
            )

    async def delete(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> None:
        """Delete an item."""
        from agent_platform.database import engine

        async with engine.begin() as conn:
            await self._ensure_table(conn)
            await conn.execute(
                """
                DELETE FROM langgraph_store
                WHERE namespace = :ns AND key = :key
                """,
                {"ns": list(namespace), "key": key},
            )

    async def search(
        self,
        namespace_prefix: tuple[str, ...],
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[StoreItem]:
        """Search items by namespace prefix."""
        from agent_platform.database import engine

        async with engine.begin() as conn:
            await self._ensure_table(conn)
            result = await conn.execute(
                """
                SELECT namespace, key, value, created_at, updated_at
                FROM langgraph_store
                WHERE namespace[:ns_len] = :ns_prefix
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
                """,
                {
                    "ns_prefix": list(namespace_prefix),
                    "ns_len": len(namespace_prefix),
                    "limit": limit,
                    "offset": offset,
                },
            )
            return [
                StoreItem(
                    namespace=tuple(row.namespace),
                    key=row.key,
                    value=row.value,
                    created_at=str(row.created_at),
                    updated_at=str(row.updated_at),
                )
                for row in result
            ]

    async def list_namespaces(
        self,
        prefix: Optional[tuple[str, ...]] = None,
        limit: int = 100,
    ) -> Sequence[tuple[str, ...]]:
        """List distinct namespaces."""
        from agent_platform.database import engine

        async with engine.begin() as conn:
            await self._ensure_table(conn)
            if prefix:
                result = await conn.execute(
                    """
                    SELECT DISTINCT namespace FROM langgraph_store
                    WHERE namespace[:ns_len] = :prefix
                    LIMIT :limit
                    """,
                    {"prefix": list(prefix), "ns_len": len(prefix), "limit": limit},
                )
            else:
                result = await conn.execute(
                    "SELECT DISTINCT namespace FROM langgraph_store LIMIT :limit",
                    {"limit": limit},
                )
            return [tuple(row.namespace) for row in result]


# Singleton
_store_instance: Optional[ForgeStore] = None


def get_store() -> ForgeStore:
    """Get the global store singleton."""
    global _store_instance
    if _store_instance is None:
        _store_instance = ForgeStore()
    return _store_instance
