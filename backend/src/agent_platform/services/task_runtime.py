"""Task runtime service.

This module provides the TaskRuntime class that orchestrates
task execution, including skill resolution, planning, and
agent invocation.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.models.session import Session
from agent_platform.models.task import Task, TaskStatus, TaskType
from agent_platform.models.task_event import TaskEvent, TaskEventType
from agent_platform.models.user import User
from agent_platform.runtime import RuntimeContext, get_runtime_registry
from agent_platform.runtime.events import RuntimeEvent
from agent_platform.runtime.kernel import DeerFlowKernel
from agent_platform.services.capability_planner import CapabilityPlan, get_capability_planner
from agent_platform.services.skill_resolver import get_skill_resolver

logger = logging.getLogger(__name__)


@dataclass
class TaskStreamEvent:
    """Task execution event for streaming."""

    type: str  # content, tool_call, tool_result, error, done
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_sse_format(self) -> str:
        """Convert event to SSE format."""
        data = {"type": self.type}

        if self.content is not None:
            data["content"] = self.content
        if self.tool_name is not None:
            data["tool_name"] = self.tool_name
        if self.tool_input is not None:
            data["tool_input"] = self.tool_input
        if self.tool_output is not None:
            data["tool_output"] = self.tool_output
        if self.error is not None:
            data["error"] = self.error
        if self.metadata:
            data["metadata"] = self.metadata

        return f"data: {json.dumps(data)}\n\n"


class TaskRuntime:
    """Task runtime for orchestrating task execution.

    The TaskRuntime is responsible for:
    1. Creating tasks
    2. Resolving skills from prompts
    3. Creating execution plans
    4. Executing tasks via agents
    5. Streaming results
    """

    def __init__(self, db: AsyncSession):
        """Initialize task runtime.

        Args:
            db: Database session
        """
        self.db = db
        self.skill_resolver = get_skill_resolver()
        self.capability_planner = get_capability_planner(db=db)
        self.runtime_registry = get_runtime_registry()
        try:
            self.runtime_registry.get("deerflow")
        except KeyError:
            self.runtime_registry.register(DeerFlowKernel())

    async def create_task(
        self,
        session_id: str | UUID,
        user_id: str | UUID,
        prompt: str,
        task_type: TaskType = TaskType.SYNC,
        org_id: Optional[str | UUID] = None,
        parent_task_id: Optional[str | UUID] = None,
        enable_hitl: bool = False,
        custom_rules: Optional[list[dict]] = None,
    ) -> Task:
        """Create a new task.

        Args:
            session_id: Session ID for the task
            user_id: User ID creating the task
            prompt: Task prompt/content
            task_type: Task type (sync/async)
            org_id: Optional organization ID
            parent_task_id: Optional parent task ID for subtasks
            enable_hitl: Whether to enable HITL
            custom_rules: Optional custom HITL rules

        Returns:
            Created Task instance
        """
        # Resolve skills from prompt
        skills = self.skill_resolver.resolve(prompt)

        # Create execution plan
        plan = await self.capability_planner.plan(
            skills=skills,
            user_id=str(user_id),
            enable_hitl=enable_hitl,
            custom_rules=custom_rules,
        )

        # Create task
        task = Task(
            user_id=str(user_id),
            org_id=str(org_id) if org_id else str(user_id),  # Default to user_id if no org
            session_id=str(session_id),
            type=task_type,
            status=TaskStatus.PENDING,
            prompt=prompt,
            execution_plan=plan.to_dict(),
            parent_task_id=str(parent_task_id) if parent_task_id else None,
            extra_metadata={
                "skills": skills,
                "enable_hitl": enable_hitl,
            },
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # Record task creation event
        await self._record_event(
            task_id=task.id,
            event_type=TaskEventType.CREATED,
            data={
                "skills": skills,
                "plan": plan.to_dict(),
            },
        )

        logger.info(f"Task created: {task.id} with skills: {skills}")

        return task

    async def execute_task(
        self,
        task_id: str | UUID,
    ) -> AsyncIterator[TaskStreamEvent]:
        """Execute a task and stream results.

        Args:
            task_id: Task ID to execute

        Yields:
            TaskStreamEvent instances during execution

        Raises:
            ValueError: If task not found
        """
        # Get task
        from sqlalchemy import select

        result = await self.db.execute(
            select(Task).where(Task.id == str(task_id))
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Mark task as running
        task.mark_running()
        await self.db.commit()

        # Record start event
        await self._record_event(
            task_id=task.id,
            event_type=TaskEventType.STARTED,
        )

        try:
            # Get execution plan
            plan_data = task.execution_plan or {}
            plan = CapabilityPlan(
                skills=plan_data.get("skills", []),
                tools=plan_data.get("tools", []),
                enable_hitl=plan_data.get("enable_hitl", False),
                hitl_rules=plan_data.get("hitl_rules", []),
                model=plan_data.get("model", "claude-sonnet-4-6"),
                config=plan_data.get("config", {}),
            )

            # Get session for thread_id and model
            result = await self.db.execute(
                select(Session).where(Session.id == task.session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                raise ValueError(f"Session not found: {task.session_id}")

            result = await self.db.execute(
                select(User).where(User.id == task.user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User not found: {task.user_id}")

            # Record agent/runtime creation event
            await self._record_event(
                task_id=task.id,
                event_type=TaskEventType.AGENT_CREATED,
                data={
                    "model": session.model,
                    "tools": plan.tools,
                    "enable_hitl": plan.enable_hitl,
                    "runtime_kind": (task.extra_metadata or {}).get("runtime_kind", "deerflow"),
                },
            )

            # Execute and stream through unified runtime kernel
            async for event in self._execute_plan(task, session, user, plan):
                yield event

            # Mark task as completed
            task.mark_completed()
            await self.db.commit()

            # Record completion event
            await self._record_event(
                task_id=task.id,
                event_type=TaskEventType.COMPLETED,
            )

            # Update session message count
            session.increment_message_count()
            await self.db.commit()

        except Exception as e:
            logger.exception(f"Task execution failed: {task_id}")

            # Mark task as failed
            task.mark_failed(str(e))
            await self.db.commit()

            # Record failure event
            await self._record_event(
                task_id=task.id,
                event_type=TaskEventType.FAILED,
                data={"error": str(e)},
            )

            # Yield error event
            yield TaskStreamEvent(
                type="error",
                error=str(e),
            )

    async def _execute_plan(
        self,
        task: Task,
        session: Session,
        user: User,
        plan: CapabilityPlan,
    ) -> AsyncIterator[TaskStreamEvent]:
        """Execute the plan through the unified runtime kernel and yield events."""
        thread_id = session.thread_id or str(session.id)
        runtime_kind = (task.extra_metadata or {}).get("runtime_kind", "deerflow")
        kernel = self.runtime_registry.get(runtime_kind)

        context = RuntimeContext(
            task_id=str(task.id),
            session_id=str(session.id),
            thread_id=thread_id,
            user_id=str(user.id),
            org_id=str(task.org_id) if task.org_id else None,
            runtime_kind=runtime_kind,
            model_name=session.model,
            system_prompt=session.system_prompt,
            input_message=task.prompt,
            skill_ids=plan.skills,
            tool_names=plan.tools,
            metadata={
                "session": session,
                "user": user,
                "db": self.db,
                "enable_hitl": plan.enable_hitl,
                "hitl_rules": plan.hitl_rules,
            },
        )

        run = await kernel.create_run(context)

        try:
            async for event in kernel.stream(run, input_message=task.prompt):
                async for mapped in self._map_runtime_event(task, event):
                    yield mapped
        except Exception as e:
            logger.exception(f"Plan execution failed for task: {task.id}")
            yield TaskStreamEvent(type="error", error=str(e))

    async def _map_runtime_event(
        self,
        task: Task,
        event: RuntimeEvent,
    ) -> AsyncIterator[TaskStreamEvent]:
        """Map unified runtime events to current streaming/task-event semantics."""
        if event.type == "run_started":
            return

        if event.type == "message_delta":
            content = event.data.get("content")
            if content is not None:
                await self._record_event(
                    task_id=task.id,
                    event_type=TaskEventType.CONTENT_CHUNK,
                    data={"content": content, "run_id": event.run_id},
                )
                yield TaskStreamEvent(type="content", content=content, metadata={"run_id": event.run_id})
            return

        if event.type == "approval_required":
            interrupt = event.data.get("interrupt", {})
            await self._record_event(
                task_id=task.id,
                event_type=TaskEventType.INTERRUPT,
                data={**interrupt, "run_id": event.run_id},
            )
            yield TaskStreamEvent(type="hitl_required", metadata={**interrupt, "run_id": event.run_id})
            return

        if event.type == "run_failed":
            error = event.data.get("error", "Runtime execution failed")
            await self._record_event(
                task_id=task.id,
                event_type=TaskEventType.FAILED,
                data={"error": error, "run_id": event.run_id},
            )
            yield TaskStreamEvent(type="error", error=error)
            return

        if event.type == "run_completed":
            yield TaskStreamEvent(type="done")
            return

    async def _record_event(
        self,
        task_id: str | UUID,
        event_type: TaskEventType,
        data: Optional[dict] = None,
        message: Optional[str] = None,
    ) -> None:
        """Record a task event.

        Args:
            task_id: Task ID
            event_type: Type of event
            data: Optional event data
            message: Optional message
        """
        try:
            event = TaskEvent(
                task_id=str(task_id),
                type=event_type.value,
                data=data or {},
                message=message,
            )
            self.db.add(event)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to record event: {e}")
            await self.db.rollback()

    async def get_task(self, task_id: str | UUID) -> Optional[Task]:
        """Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task instance or None
        """
        from sqlalchemy import select

        result = await self.db.execute(
            select(Task).where(Task.id == str(task_id))
        )
        return result.scalar_one_or_none()

    async def cancel_task(self, task_id: str | UUID) -> bool:
        """Cancel a task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False otherwise
        """
        task = await self.get_task(task_id)
        if not task:
            return False

        if not task.is_cancellable:
            return False

        task.mark_cancelled()
        await self.db.commit()

        # Record cancellation event
        await self._record_event(
            task_id=task.id,
            event_type=TaskEventType.CANCELLED,
        )

        return True


class TaskRuntimeFactory:
    """Factory for creating TaskRuntime instances."""

    @staticmethod
    async def create(db: AsyncSession) -> TaskRuntime:
        """Create a TaskRuntime instance.

        Args:
            db: Database session

        Returns:
            TaskRuntime instance
        """
        return TaskRuntime(db=db)
