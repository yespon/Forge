"""Embedded Python client for Forge platform.

Provides direct in-process access to all Forge capabilities
without running the HTTP server. Mirrors the REST API interface
so consumer code works identically in HTTP and embedded modes.

Usage:
    from agent_platform.client import ForgeClient

    client = ForgeClient(db_url="postgresql+asyncpg://...")
    response = await client.chat("Summarize this week's progress", session_id="...")
    async for event in client.stream("Analyze the data", session_id="..."):
        print(event)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class ClientConfig:
    """Configuration for ForgeClient."""
    db_url: str = ""
    model_name: str = "claude-sonnet-4-20250514"
    enable_hitl: bool = False
    enable_audit: bool = True
    enable_memory: bool = True
    memory_storage_path: str = ".forge/memory"
    default_system_prompt: Optional[str] = None


@dataclass
class ChatResponse:
    """Response from a chat call."""
    content: str = ""
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)


@dataclass
class StreamEvent:
    """A streaming event from the agent."""
    type: str = ""  # content, tool_call, tool_result, error, done
    data: dict = field(default_factory=dict)
    content: Optional[str] = None


class ForgeClient:
    """Embedded Python client for the Forge platform.

    Provides direct in-process access to chat, task management,
    skills, memory, and other platform capabilities without HTTP.
    """

    def __init__(
        self,
        db_url: str = "",
        model_name: str = "claude-sonnet-4-20250514",
        enable_hitl: bool = False,
        enable_audit: bool = True,
        enable_memory: bool = True,
        config: Optional[ClientConfig] = None,
    ):
        self._config = config or ClientConfig(
            db_url=db_url,
            model_name=model_name,
            enable_hitl=enable_hitl,
            enable_audit=enable_audit,
            enable_memory=enable_memory,
        )
        self._db_engine = None
        self._db_session_factory = None
        self._initialized = False

    async def _ensure_init(self) -> None:
        """Lazy initialization of database and services."""
        if self._initialized:
            return

        if self._config.db_url:
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
            self._db_engine = create_async_engine(self._config.db_url, echo=False)
            self._db_session_factory = async_sessionmaker(
                self._db_engine, expire_on_commit=False,
            )

        self._initialized = True

    async def _get_db(self):
        """Get a database session."""
        await self._ensure_init()
        if self._db_session_factory:
            return self._db_session_factory()
        return None

    # ==================== Chat ====================

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> ChatResponse:
        """Send a message and get a complete response.

        Args:
            message: The user message
            session_id: Optional session ID (created if not provided)
            user_id: Optional user ID for multi-tenant use
            model_name: Override the default model

        Returns:
            ChatResponse with the assistant's reply
        """
        response = ChatResponse()
        async for event in self.stream(
            message,
            session_id=session_id,
            user_id=user_id,
            model_name=model_name,
            system_prompt=system_prompt,
        ):
            if event.type == "content" and event.content:
                response.content += event.content
            elif event.type == "tool_call":
                response.tool_calls.append(event.data)
            elif event.type == "done":
                response.usage = event.data.get("usage", {})
                response.task_id = event.data.get("task_id")
                response.session_id = event.data.get("session_id")

        return response

    async def stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat response with real-time events.

        Args:
            message: The user message
            session_id: Optional session ID
            user_id: Optional user ID
            model_name: Override the default model

        Yields:
            StreamEvent for each chunk of the response
        """
        db = await self._get_db()

        try:
            if db:
                async with db:
                    async for event in self._execute_with_db(
                        db, message, session_id, user_id, model_name, system_prompt,
                    ):
                        yield event
            else:
                async for event in self._execute_standalone(
                    message, model_name, system_prompt,
                ):
                    yield event
        except Exception as e:
            logger.exception("Stream error: %s", e)
            yield StreamEvent(type="error", data={"error": str(e)})
            yield StreamEvent(type="done", data={})

    async def _execute_with_db(
        self, db, message, session_id, user_id, model_name, system_prompt,
    ) -> AsyncIterator[StreamEvent]:
        """Execute chat using TaskRuntime with database."""
        from agent_platform.services.task_runtime import TaskRuntime

        runtime = TaskRuntime(db=db)

        # Create or get session
        if not session_id:
            from agent_platform.models.session import Session
            session = Session(
                user_id=user_id or str(uuid4()),
                name="embedded-client",
                model=model_name or self._config.model_name,
            )
            db.add(session)
            await db.commit()
            session_id = str(session.id)

        # Create task
        task = await runtime.create_task(
            session_id=session_id,
            user_id=user_id or "embedded",
            prompt=message,
        )

        # Execute task and stream events
        async for event in runtime.execute_task(str(task.id)):
            yield StreamEvent(
                type=event.type,
                content=getattr(event, "content", None),
                data={
                    "task_id": str(task.id),
                    "session_id": session_id,
                },
            )

    async def _execute_standalone(
        self, message, model_name, system_prompt,
    ) -> AsyncIterator[StreamEvent]:
        """Execute chat standalone without database (for quick tasks)."""
        from agent_platform.agent.factory import create_agent, stream_agent_response

        model = model_name or self._config.model_name
        agent, _ = await create_agent(
            model_name=model,
            system_prompt=system_prompt or self._config.default_system_prompt,
        )

        thread_id = f"embedded_{uuid4()}"
        async for chunk in stream_agent_response(agent, message, thread_id):
            chunk_type = chunk.get("type", "content")
            yield StreamEvent(
                type=chunk_type,
                content=chunk.get("content"),
                data=chunk,
            )

        yield StreamEvent(type="done", data={"thread_id": thread_id})

    # ==================== Tasks ====================

    async def create_task(
        self,
        intent: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """Create a task."""
        db = await self._get_db()
        if not db:
            raise RuntimeError("Database required for task creation")

        async with db:
            from agent_platform.services.task_runtime import TaskRuntime
            runtime = TaskRuntime(db=db)
            task = await runtime.create_task(
                session_id=session_id or str(uuid4()),
                user_id=user_id or "embedded",
                prompt=intent,
            )
            return {
                "id": str(task.id),
                "status": task.status.value if hasattr(task.status, "value") else str(task.status),
                "prompt": task.prompt,
            }

    async def get_task(self, task_id: str) -> Optional[dict]:
        """Get task details."""
        db = await self._get_db()
        if not db:
            return None

        async with db:
            from sqlalchemy import select
            from agent_platform.models.task import Task
            result = await db.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                return None
            return {
                "id": str(task.id),
                "status": task.status.value if hasattr(task.status, "value") else str(task.status),
                "prompt": task.prompt,
                "result": task.result,
            }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        db = await self._get_db()
        if not db:
            return False

        async with db:
            from agent_platform.services.task_runtime import TaskRuntime
            runtime = TaskRuntime(db=db)
            return await runtime.cancel_task(task_id)

    # ==================== Skills ====================

    async def list_skills(self) -> dict:
        """List available skills."""
        db = await self._get_db()
        if not db:
            return {"skills": []}

        async with db:
            from sqlalchemy import select
            from agent_platform.models.skill import Skill
            result = await db.execute(select(Skill))
            skills = result.scalars().all()
            return {
                "skills": [
                    {
                        "name": s.name,
                        "description": s.description,
                        "visibility": s.visibility.value if hasattr(s.visibility, "value") else str(s.visibility),
                        "is_restricted": s.is_restricted,
                    }
                    for s in skills
                ],
            }

    # ==================== Memory ====================

    def get_memory(self, user_id: str = "default") -> dict:
        """Get memory data for a user."""
        from agent_platform.integration.memory import get_memory_manager
        mm = get_memory_manager(user_id=user_id)
        return mm.get_status()

    def get_memory_context(self, query: str = "", user_id: str = "default") -> str:
        """Get memory context for injection."""
        from agent_platform.integration.memory import get_memory_manager
        mm = get_memory_manager(user_id=user_id)
        return mm.get_memory_context(query)

    def store_memory_fact(
        self, content: str, category: str = "general",
        confidence: float = 1.0, user_id: str = "default",
    ) -> bool:
        """Store a memory fact."""
        from agent_platform.integration.memory import get_memory_manager
        mm = get_memory_manager(user_id=user_id)
        return mm.store_fact(content, category, confidence)

    # ==================== Models ====================

    def list_models(self) -> dict:
        """List available models."""
        try:
            from agent_platform.integration import get_available_models
            return {"models": get_available_models()}
        except Exception:
            return {"models": []}

    # ==================== Lifecycle ====================

    async def close(self) -> None:
        """Close the client and release resources."""
        if self._db_engine:
            await self._db_engine.dispose()
            self._db_engine = None
        self._initialized = False

    async def __aenter__(self):
        await self._ensure_init()
        return self

    async def __aexit__(self, *args):
        await self.close()
