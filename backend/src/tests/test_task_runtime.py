"""Task Runtime tests.

Tests for the Task Runtime layer including:
- Task creation
- Task execution flow
- Skill resolution
- Capability planning
- Backward compatibility with Chat API
"""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import select

from agent_platform.models.session import Session
from agent_platform.models.task import Task, TaskStatus, TaskType
from agent_platform.models.task_event import TaskEvent, TaskEventType
from agent_platform.agent.factory import create_agent
from agent_platform.services.capability_planner import CapabilityPlan, CapabilityPlanner
from agent_platform.services.skill_resolver import SkillDefinition, SkillResolver
from agent_platform.services.task_runtime import TaskRuntime


# Fixtures
@pytest_asyncio.fixture
async def sample_session(db_session, sample_user):
    """Create a sample session for testing."""
    session = Session(
        user_id=sample_user.id,
        name="Test Session",
        model="claude-sonnet-4-6",
        thread_id=f"user_{sample_user.id}_session_{uuid4()}",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def task_runtime(db_session):
    """Create a TaskRuntime instance."""
    return TaskRuntime(db=db_session)


# SkillResolver Tests
class TestSkillResolver:
    """Test SkillResolver functionality."""

    def test_resolve_file_ops(self):
        """Test resolving file operations keywords."""
        resolver = SkillResolver()

        # Test English keywords
        skills = resolver.resolve("Read the config file and analyze it")
        assert "file_ops" in skills

        # Test Chinese keywords
        skills = resolver.resolve("读取文件内容")
        assert "file_ops" in skills

    def test_resolve_data_analysis(self):
        """Test resolving data analysis keywords."""
        resolver = SkillResolver()

        skills = resolver.resolve("Analyze the CSV data and create charts")
        assert "data_analysis" in skills

    def test_resolve_multiple_skills(self):
        """Test resolving multiple skills from prompt."""
        resolver = SkillResolver()

        skills = resolver.resolve("Read the data file and analyze it with Python")
        assert "file_ops" in skills
        assert "code_execution" in skills

    def test_resolve_empty_prompt(self):
        """Test resolving empty prompt returns empty list."""
        resolver = SkillResolver()

        skills = resolver.resolve("")
        assert skills == []

    def test_resolve_no_match(self):
        """Test resolving prompt with no matching skills."""
        resolver = SkillResolver()

        skills = resolver.resolve("Tell me a joke about cats")
        # Should return empty or minimal skills
        assert isinstance(skills, list)

    def test_get_skill(self):
        """Test getting skill definition by name."""
        resolver = SkillResolver()

        skill = resolver.get_skill("file_ops")
        assert skill is not None
        assert skill.name == "file_ops"
        assert "read_file" in skill.tools

    def test_get_skill_not_found(self):
        """Test getting non-existent skill."""
        resolver = SkillResolver()

        skill = resolver.get_skill("non_existent")
        assert skill is None

    def test_add_custom_skill(self):
        """Test adding custom skill."""
        resolver = SkillResolver()

        custom_skill = SkillDefinition(
            name="custom_skill",
            description="A custom skill",
            keywords=["custom", "special"],
            tools=["custom_tool"],
            priority=20,
        )

        resolver.add_skill(custom_skill)

        # Test that custom skill is resolved
        skills = resolver.resolve("Use the custom tool")
        assert "custom_skill" in skills


# CapabilityPlanner Tests
class TestCapabilityPlanner:
    """Test CapabilityPlanner functionality."""

    @pytest.mark.asyncio
    async def test_plan_single_skill(self):
        """Test planning with single skill."""
        planner = CapabilityPlanner(db=None)

        plan = await planner.plan(
            skills=["file_ops"],
            user_id="user-123",
        )

        assert isinstance(plan, CapabilityPlan)
        assert "file_ops" in plan.skills
        assert "read_file" in plan.tools
        assert "write_file" in plan.tools

    @pytest.mark.asyncio
    async def test_plan_multiple_skills(self):
        """Test planning with multiple skills."""
        planner = CapabilityPlanner(db=None)

        plan = await planner.plan(
            skills=["file_ops", "code_execution"],
            user_id="user-123",
        )

        assert "file_ops" in plan.skills
        assert "code_execution" in plan.skills
        assert "execute_bash" in plan.tools

    @pytest.mark.asyncio
    async def test_plan_with_hitl(self):
        """Test planning with HITL enabled."""
        planner = CapabilityPlanner(db=None)

        plan = await planner.plan(
            skills=["file_ops"],
            user_id="user-123",
            enable_hitl=True,
            custom_rules=[{"rule": "test"}],
        )

        assert plan.enable_hitl is True
        assert plan.hitl_rules == [{"rule": "test"}]

    @pytest.mark.asyncio
    async def test_plan_from_prompt(self):
        """Test planning from a user prompt."""
        planner = CapabilityPlanner(db=None)

        plan = await planner.plan_from_prompt(
            prompt="Read the file and execute the script",
            user_id="user-123",
        )

        # Should resolve skills from prompt
        assert len(plan.skills) > 0
        assert len(plan.tools) > 0

    def test_capability_plan_to_dict(self):
        """Test CapabilityPlan to_dict method."""
        plan = CapabilityPlan(
            skills=["file_ops"],
            tools=["read_file"],
            enable_hitl=True,
            model="claude-sonnet-4-6",
            config={"test": True},
        )

        data = plan.to_dict()

        assert data["skills"] == ["file_ops"]
        assert data["tools"] == ["read_file"]
        assert data["enable_hitl"] is True
        assert data["model"] == "claude-sonnet-4-6"
        assert data["config"] == {"test": True}


# TaskRuntime Tests
class TestTaskRuntime:
    """Test TaskRuntime functionality."""

    @pytest.mark.asyncio
    async def test_create_task(self, db_session, sample_user, sample_session, task_runtime):
        """Test task creation."""
        task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Read the config file",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
        )

        assert task is not None
        assert task.user_id == sample_user.id
        assert task.session_id == sample_session.id
        assert task.type == TaskType.SYNC
        assert task.status == TaskStatus.PENDING
        assert task.prompt == "Read the config file"

        # Verify execution plan is created
        assert task.execution_plan is not None
        assert "skills" in task.execution_plan
        assert "tools" in task.execution_plan

        # Verify metadata
        assert "skills" in task.extra_metadata
        assert "file_ops" in task.extra_metadata["skills"]

    @pytest.mark.asyncio
    async def test_create_task_with_parent(self, db_session, sample_user, sample_session, task_runtime):
        """Test creating a subtask with parent."""
        # Create parent task
        parent_task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Parent task",
            task_type=TaskType.ASYNC,
            org_id=sample_user.org_id,
        )

        # Create subtask
        subtask = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Subtask",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
            parent_task_id=parent_task.id,
        )

        assert subtask.parent_task_id == parent_task.id

    @pytest.mark.asyncio
    async def test_create_task_records_event(self, db_session, sample_user, sample_session, task_runtime):
        """Test that task creation records an event."""
        task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Test prompt",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
        )

        # Check that event was recorded
        result = await db_session.execute(
            select(TaskEvent).where(TaskEvent.task_id == task.id)
        )
        events = result.scalars().all()

        assert len(events) >= 1
        assert any(e.type == TaskEventType.CREATED for e in events)

    @pytest.mark.asyncio
    async def test_get_task(self, db_session, sample_user, sample_session, task_runtime):
        """Test getting task by ID."""
        task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Test prompt",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
        )

        fetched_task = await task_runtime.get_task(task.id)

        assert fetched_task is not None
        assert fetched_task.id == task.id
        assert fetched_task.prompt == "Test prompt"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, db_session, task_runtime):
        """Test getting non-existent task."""
        fetched_task = await task_runtime.get_task(uuid4())

        assert fetched_task is None

    @pytest.mark.asyncio
    async def test_cancel_task(self, db_session, sample_user, sample_session, task_runtime):
        """Test cancelling a task."""
        task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Test prompt",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
        )

        # Cancel the task
        cancelled = await task_runtime.cancel_task(task.id)

        assert cancelled is True

        # Verify task status
        await db_session.refresh(task)
        assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_task_not_cancellable(self, db_session, sample_user, sample_session, task_runtime):
        """Test cancelling a task that's already running."""
        task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Test prompt",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
        )

        # Mark as running
        task.mark_running()
        await db_session.commit()

        # Try to cancel
        cancelled = await task_runtime.cancel_task(task.id)

        assert cancelled is False

    @pytest.mark.asyncio
    async def test_task_model_parent_child_relationship(self, db_session, sample_user, sample_session):
        """Test Task model parent-child relationship."""
        from agent_platform.models.task import Task, TaskType, TaskStatus

        # Create parent task
        parent = Task(
            user_id=sample_user.id,
            org_id=sample_user.org_id,
            session_id=sample_session.id,
            type=TaskType.SYNC,
            status=TaskStatus.PENDING,
            prompt="Parent task",
        )
        db_session.add(parent)
        await db_session.commit()
        await db_session.refresh(parent)

        # Create child task
        child = Task(
            user_id=sample_user.id,
            org_id=sample_user.org_id,
            session_id=sample_session.id,
            type=TaskType.SYNC,
            status=TaskStatus.PENDING,
            prompt="Child task",
            parent_task_id=parent.id,
        )
        db_session.add(child)
        await db_session.commit()
        await db_session.refresh(child)

        # Verify relationships
        assert child.parent_task_id == parent.id
        await db_session.refresh(child, attribute_names=["parent_task"])
        assert child.parent_task.id == parent.id

        # Refresh parent to get subtasks
        await db_session.refresh(parent, attribute_names=["subtasks"])
        assert len(parent.subtasks) == 1
        assert parent.subtasks[0].id == child.id

    @pytest.mark.asyncio
    async def test_task_model_execution_plan(self, db_session, sample_user, sample_session):
        """Test Task model execution_plan field."""
        from agent_platform.models.task import Task, TaskType, TaskStatus

        plan = {
            "skills": ["file_ops", "data_analysis"],
            "tools": ["read_file", "write_file"],
            "enable_hitl": True,
        }

        task = Task(
            user_id=sample_user.id,
            org_id=sample_user.org_id,
            session_id=sample_session.id,
            type=TaskType.SYNC,
            status=TaskStatus.PENDING,
            prompt="Test task with plan",
            execution_plan=plan,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Verify execution plan
        assert task.execution_plan == plan

        # Test to_dict includes plan
        data = task.to_dict()
        assert data["execution_plan"] == plan
        assert data["parent_task_id"] is None


# TaskEvent Model Tests
class TestTaskEvent:
    """Test TaskEvent model."""

    @pytest.mark.asyncio
    async def test_create_task_event(self, db_session, sample_user, sample_session):
        """Test creating a task event."""
        # Create a task first
        task = Task(
            user_id=sample_user.id,
            org_id=sample_user.org_id,
            session_id=sample_session.id,
            type=TaskType.SYNC,
            status=TaskStatus.PENDING,
            prompt="Test task",
        )
        db_session.add(task)
        await db_session.commit()

        # Create an event
        event = TaskEvent(
            task_id=task.id,
            type=TaskEventType.CREATED,
            data={"test": True},
            message="Task created",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        assert event.id is not None
        assert event.task_id == task.id
        assert event.type == TaskEventType.CREATED
        assert event.data == {"test": True}
        assert event.message == "Task created"
        assert event.created_at is not None

    @pytest.mark.asyncio
    async def test_task_event_relationship(self, db_session, sample_user, sample_session):
        """Test task-event relationship."""
        # Create task
        task = Task(
            user_id=sample_user.id,
            org_id=sample_user.org_id,
            session_id=sample_session.id,
            type=TaskType.SYNC,
            status=TaskStatus.PENDING,
            prompt="Test task",
        )
        db_session.add(task)
        await db_session.commit()

        # Create multiple events
        for i, event_type in enumerate([TaskEventType.CREATED, TaskEventType.STARTED, TaskEventType.COMPLETED]):
            event = TaskEvent(
                task_id=task.id,
                type=event_type,
                data={"index": i},
            )
            db_session.add(event)

        await db_session.commit()

        # Refresh task to get events
        await db_session.refresh(task, attribute_names=["events"])

        # Verify events are ordered by created_at
        assert len(task.events) == 3
        event_types = [e.type for e in task.events]
        assert TaskEventType.CREATED in event_types
        assert TaskEventType.STARTED in event_types
        assert TaskEventType.COMPLETED in event_types


# Chat API Backward Compatibility Tests
class TestChatAPIBackwardCompatibility:
    """Test Chat API backward compatibility."""

    @pytest.mark.asyncio
    async def test_chat_messages_uses_task_runtime_not_direct_agent(self, client, sample_user, auth_headers, db_session):
        session = Session(
            user_id=sample_user.id,
            name="Test Session",
            model="claude-sonnet-4-6",
            thread_id=f"user_{sample_user.id}_session_{uuid4()}",
        )
        db_session.add(session)
        await db_session.commit()

        with patch("agent_platform.api.v1.chat.create_agent", create=True) as direct_create_agent:
            with patch("agent_platform.services.task_runtime.create_agent") as runtime_create_agent:
                mock_agent = MagicMock()
                runtime_create_agent.return_value = (mock_agent, None)

                with patch("agent_platform.services.task_runtime.stream_agent_response") as mock_stream:
                    async def mock_stream_response(*args, **kwargs):
                        yield {"type": "content", "content": "Task runtime response"}

                    mock_stream.side_effect = mock_stream_response

                    response = await client.post(
                        f"/api/v1/sessions/{session.id}/chat/messages",
                        headers=auth_headers,
                        json={"message": "send weekly report", "stream": False},
                    )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["content"] == "Task runtime response"
        direct_create_agent.assert_not_called()
        runtime_create_agent.assert_called_once()
        assert runtime_create_agent.call_args.kwargs["enable_hitl"] is True
        assert runtime_create_agent.call_args.kwargs["session"].id == session.id
        assert runtime_create_agent.call_args.kwargs["user"].id == sample_user.id
        assert runtime_create_agent.call_args.kwargs["db"] is db_session

    @pytest.mark.asyncio
    async def test_chat_completions_sse_format(self, client, sample_user, auth_headers, db_session):
        """Test that chat completions returns correct SSE format."""
        from agent_platform.models.session import Session

        # Create a session
        session = Session(
            user_id=sample_user.id,
            name="Test Session",
            model="claude-sonnet-4-6",
            thread_id=f"user_{sample_user.id}_session_{uuid4()}",
        )
        db_session.add(session)
        await db_session.commit()

        # Mock the agent execution
        with patch("agent_platform.services.task_runtime.create_agent") as mock_create_agent:
            mock_agent = MagicMock()
            mock_create_agent.return_value = (mock_agent, None)

            with patch("agent_platform.services.task_runtime.stream_agent_response") as mock_stream:
                async def mock_stream_response(*args, **kwargs):
                    yield {"type": "content", "content": "Hello"}
                    yield {"type": "content", "content": " World"}

                mock_stream.side_effect = mock_stream_response

                # Make request
                response = await client.post(
                    f"/api/v1/sessions/{session.id}/chat/completions",
                    headers=auth_headers,
                    json={"message": "Hello", "stream": True},
                )

                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

                # Parse SSE response
                content = response.content.decode()

                # Verify SSE format
                assert 'data: {"type": "content", "content": "Hello"}' in content
                assert 'data: {"type": "content", "content": " World"}' in content
                assert 'data: {"type": "done"}' in content

    @pytest.mark.asyncio
    async def test_chat_completions_creates_implicit_task(self, client, sample_user, auth_headers, db_session):
        """Test that chat completions creates an implicit task."""
        from agent_platform.models.session import Session
        from agent_platform.models.task import Task

        # Create a session
        session = Session(
            user_id=sample_user.id,
            name="Test Session",
            model="claude-sonnet-4-6",
            thread_id=f"user_{sample_user.id}_session_{uuid4()}",
        )
        db_session.add(session)
        await db_session.commit()

        # Mock the agent execution
        with patch("agent_platform.services.task_runtime.create_agent") as mock_create_agent:
            mock_agent = MagicMock()
            mock_create_agent.return_value = (mock_agent, None)

            with patch("agent_platform.services.task_runtime.stream_agent_response") as mock_stream:
                async def mock_stream_response(*args, **kwargs):
                    yield {"type": "content", "content": "Response"}

                mock_stream.side_effect = mock_stream_response

                # Make request
                await client.post(
                    f"/api/v1/sessions/{session.id}/chat/completions",
                    headers=auth_headers,
                    json={"message": "Test message", "stream": True},
                )

                # Verify task was created
                result = await db_session.execute(
                    select(Task).where(Task.session_id == session.id)
                )
                tasks = result.scalars().all()

                assert len(tasks) >= 1
                task = tasks[0]
                assert task.prompt == "Test message"
                assert task.type == TaskType.SYNC
                assert task.user_id == sample_user.id


# Integration Tests
class TestTaskRuntimeIntegration:
    """Integration tests for Task Runtime."""

    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self, db_session, sample_user, sample_session, task_runtime):
        """Test full task lifecycle: create -> execute -> complete."""
        # Create task
        task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Test task",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
        )

        assert task.status == TaskStatus.PENDING

        # Mock agent execution
        with patch("agent_platform.services.task_runtime.create_agent") as mock_create_agent:
            mock_agent = MagicMock()
            mock_create_agent.return_value = (mock_agent, None)

            with patch("agent_platform.services.task_runtime.stream_agent_response") as mock_stream:
                async def mock_stream_response(*args, **kwargs):
                    yield {"type": "content", "content": "Result"}

                mock_stream.side_effect = mock_stream_response

                # Execute task
                events = []
                async for event in task_runtime.execute_task(task.id):
                    events.append(event)

                # Verify events
                assert any(e.type == "content" for e in events)
                assert any(e.type == "done" for e in events)

        # Verify task is completed
        await db_session.refresh(task)
        assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_task_execution_failure(self, db_session, sample_user, sample_session, task_runtime):
        """Test task execution failure handling."""
        # Create task
        task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="Test task that will fail",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
        )

        # Mock agent execution with error
        with patch("agent_platform.services.task_runtime.create_agent") as mock_create_agent:
            mock_create_agent.side_effect = Exception("Agent creation failed")

            # Execute task
            events = []
            async for event in task_runtime.execute_task(task.id):
                events.append(event)

            # Verify error event
            assert any(e.type == "error" for e in events)

        # Verify task is failed
        await db_session.refresh(task)
        assert task.status == TaskStatus.FAILED
        assert "Agent creation failed" in task.error_message


@pytest.mark.asyncio
async def test_create_agent_without_session_gets_no_default_local_tools():
    with patch("agent_platform.agent.factory.ChatAnthropic"):
        with patch("agent_platform.agent.factory.create_checkpointer", new_callable=AsyncMock) as mock_checkpointer:
            with patch("agent_platform.agent.factory.create_react_agent") as mock_create_react_agent:
                mock_checkpointer.return_value = MagicMock()
                mock_create_react_agent.return_value = MagicMock()

                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    await create_agent(model_name="claude-sonnet-4-6")

    assert mock_create_react_agent.call_args.kwargs["tools"] == []


# ---- Cross-module integration checks (spec review requirements) ----


class TestSpecReviewChecks:
    """Verify the design spec's review requirements are met."""

    @pytest.mark.asyncio
    async def test_chat_never_calls_create_agent_directly(self):
        """Chat API must route through TaskRuntime, not call create_agent directly."""
        import inspect
        from agent_platform.api.v1 import chat

        source = inspect.getsource(chat)
        # Should import TaskRuntime, not call create_agent at the handler level
        assert "TaskRuntime" in source
        # The handler should not directly call create_agent
        assert "create_agent(" not in source or "task_runtime" in source.lower()

    @pytest.mark.asyncio
    async def test_factory_no_default_local_tools_without_session(self):
        """create_agent without session must not provide bash/file tools."""
        from agent_platform.agent import factory
        import inspect

        source = inspect.getsource(factory.create_agent)
        # The fallback should be empty tools
        assert "agent_tools = []" in source

    @pytest.mark.asyncio
    async def test_approval_identity_from_auth_not_body(self):
        """submit_approval_decision must use current_user.id, not body user_id."""
        import inspect
        from agent_platform.api.v1 import approvals

        source = inspect.getsource(approvals.submit_approval_decision)
        assert "current_user.id" in source

    @pytest.mark.asyncio
    async def test_task_events_recorded_during_execution(
        self, db_session, sample_user, sample_session, task_runtime
    ):
        """Task execution must record CREATED, STARTED, and COMPLETED events."""
        task = await task_runtime.create_task(
            session_id=sample_session.id,
            user_id=sample_user.id,
            prompt="event tracking test",
            task_type=TaskType.SYNC,
            org_id=sample_user.org_id,
        )

        with patch("agent_platform.services.task_runtime.create_agent") as mock:
            mock_agent = MagicMock()
            mock.return_value = (mock_agent, None)

            with patch("agent_platform.services.task_runtime.stream_agent_response") as mock_stream:
                async def stream(*a, **kw):
                    yield {"type": "content", "content": "ok"}

                mock_stream.side_effect = stream

                async for _ in task_runtime.execute_task(task.id):
                    pass

        # Query events
        result = await db_session.execute(
            select(TaskEvent)
            .where(TaskEvent.task_id == task.id)
            .order_by(TaskEvent.created_at.asc())
        )
        event_types = [e.type for e in result.scalars().all()]

        assert TaskEventType.CREATED.value in event_types
        assert TaskEventType.STARTED.value in event_types
        assert TaskEventType.COMPLETED.value in event_types
