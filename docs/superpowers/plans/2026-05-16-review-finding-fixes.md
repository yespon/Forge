# Review Finding Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the P0/P1 review findings so chat execution, HITL approvals, sandbox persistence, and task scheduling match the enterprise Task Runtime design.

**Architecture:** Chat endpoints must create/bind Tasks and execute through `TaskRuntime`. Agent tools must be loaded from session skills and gateway/HITL controls, not from default local bash/file tools. Approval and sandbox endpoints remain small FastAPI routers with focused regression tests.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, pytest-asyncio, LangGraph agent factory, existing `TaskRuntime`, existing sandbox provider abstraction.

---

## File Structure

- Modify `backend/src/agent_platform/api/v1/chat.py`: remove direct non-streaming agent invocation and route `/messages` through `TaskRuntime` with HITL enabled.
- Modify `backend/src/agent_platform/services/task_runtime.py`: default chat-created tasks to HITL enabled and pass `session`, `user`, and `db` to `create_agent`.
- Modify `backend/src/agent_platform/agent/factory.py`: make secure skill/session loading the only default when a session is provided, and make the no-session fallback tool-less.
- Modify `backend/src/agent_platform/api/v1/approvals.py`: move static routes above dynamic routes and use `current_user.id` as decision identity.
- Modify `backend/src/agent_platform/api/v1/sandbox.py`: replace in-place JSON mutation with reassignment.
- Create `backend/src/agent_platform/services/task_queue.py`: minimal Redis Streams-compatible queue abstraction with injectable Redis client for tests.
- Create `backend/src/agent_platform/api/v1/tasks.py`: task create/get/cancel/stream/artifacts endpoints backed by `TaskRuntime`.
- Modify `backend/src/agent_platform/main.py`: include task router.
- Add or modify tests in `backend/src/tests/test_task_runtime.py`, `backend/src/tests/test_approvals.py`, `backend/src/tests/test_sandbox.py`, and `backend/src/tests/test_tasks.py`.

---

### Task 1: Chat Uses Task Runtime, HITL, and Session Skills

**Files:**
- Modify: `backend/src/agent_platform/api/v1/chat.py`
- Modify: `backend/src/agent_platform/services/task_runtime.py`
- Modify: `backend/src/agent_platform/agent/factory.py`
- Test: `backend/src/tests/test_task_runtime.py`

- [x] **Step 1: Write failing tests for chat `/messages` and agent creation**

Add these tests to `backend/src/tests/test_task_runtime.py`:

```python
@pytest.mark.asyncio
async def test_chat_messages_uses_task_runtime_not_direct_agent(client, sample_user, auth_headers, db_session):
    session = Session(
        user_id=sample_user.id,
        name="Test Session",
        model="claude-sonnet-4-6",
        thread_id=f"user_{sample_user.id}_session_{uuid4()}",
    )
    db_session.add(session)
    await db_session.commit()

    with patch("agent_platform.api.v1.chat.create_agent") as direct_create_agent:
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
```

Add this unit test near existing agent factory tests if present, or at the bottom of `test_task_runtime.py`:

```python
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
```

- [x] **Step 2: Run tests to verify RED**

Run: `cd backend && poetry run pytest src/tests/test_task_runtime.py::TestChatAPIBackwardCompatibility::test_chat_messages_uses_task_runtime_not_direct_agent src/tests/test_task_runtime.py::test_create_agent_without_session_gets_no_default_local_tools -q`

Expected: FAIL because `/messages` still calls direct `create_agent`, `TaskRuntime` does not pass session/user/db, and `create_agent` still falls back to local tools.

- [x] **Step 3: Implement chat and agent changes**

In `chat.py`, import only `TaskRuntime` for execution. Replace `/messages` direct agent invocation with:

```python
task_runtime = TaskRuntime(db=db)
task = await task_runtime.create_task(
    session_id=session.id,
    user_id=current_user.id,
    prompt=request.message,
    task_type=TaskType.SYNC,
    org_id=current_user.org_id,
    enable_hitl=True,
)

content_parts: list[str] = []
async for event in task_runtime.execute_task(task.id):
    if event.type == "content" and event.content:
        content_parts.append(event.content)
    elif event.type == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {event.error}",
        )

session.increment_message_count()
await db.commit()

return ChatMessageResponse(
    id=str(task.id),
    role="assistant",
    content="".join(content_parts),
    tool_calls=None,
    created_at=str(session.last_activity_at),
)
```

In `TaskRuntime.execute_task`, load the task owner and pass runtime context into `create_agent`:

```python
user_result = await self.db.execute(select(User).where(User.id == task.user_id))
user = user_result.scalar_one_or_none()
if not user:
    raise ValueError(f"User not found: {task.user_id}")

agent, _ = await create_agent(
    model_name=session.model,
    system_prompt=session.system_prompt,
    thread_id=session.thread_id,
    enable_hitl=plan.enable_hitl,
    session_id=str(session.id),
    task_id=str(task.id),
    custom_hitl_rules=plan.hitl_rules,
    session=session,
    user=user,
    db=self.db,
)
```

In `create_agent`, replace the final fallback with no tools:

```python
else:
    agent_tools = []
```

Update the default system prompt to avoid claiming file/bash access unless tools are present.

- [x] **Step 4: Run tests to verify GREEN**

Run: `cd backend && poetry run pytest src/tests/test_task_runtime.py -q`

Expected: PASS for task runtime tests.

---

### Task 2: Approval Identity and Static Route Order

**Files:**
- Modify: `backend/src/agent_platform/api/v1/approvals.py`
- Test: `backend/src/tests/test_approvals.py`

- [x] **Step 1: Write failing approval security and route tests**

Add these tests to `TestApprovalsAPI`:

```python
@pytest.mark.asyncio
async def test_submit_approval_uses_authenticated_user_not_body_user_id(
    self,
    client: AsyncClient,
    pending_approval: ApprovalRequest,
    test_user: User,
):
    forged_user_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/approvals/{pending_approval.id}",
        json={
            "decision": "approved",
            "reason": "body user_id should be ignored",
            "user_id": forged_user_id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decisions"][0]["user_id"] == str(test_user.id)
    assert data["decisions"][0]["user_id"] != forged_user_id
```

Add route regression tests:

```python
@pytest.mark.asyncio
async def test_approval_history_route_is_not_captured_by_approval_id(self, client: AsyncClient):
    response = await client.get("/api/v1/approvals/history")
    assert response.status_code != 422


@pytest.mark.asyncio
async def test_approval_rules_route_is_not_captured_by_approval_id(self, client: AsyncClient):
    response = await client.get("/api/v1/approvals/rules")
    assert response.status_code != 422
```

- [x] **Step 2: Run tests to verify RED**

Run: `cd backend && poetry run pytest src/tests/test_approvals.py::TestApprovalsAPI::test_submit_approval_uses_authenticated_user_not_body_user_id src/tests/test_approvals.py::TestApprovalsAPI::test_approval_history_route_is_not_captured_by_approval_id src/tests/test_approvals.py::TestApprovalsAPI::test_approval_rules_route_is_not_captured_by_approval_id -q`

Expected: FAIL because the body `user_id` is trusted and static routes are registered after `/{approval_id}`.

- [x] **Step 3: Implement approval fixes**

In `ApprovalDecisionRequest`, make `user_id` optional for backward compatibility:

```python
user_id: Optional[str] = Field(
    None,
    description="Deprecated. Decision identity comes from authenticated user.",
)
```

In `submit_approval_decision`, derive the decision maker once:

```python
decision_user_id = str(current_user.id)

if not can_decide_approval(approval, decision_user_id):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to submit decision for this approval request",
    )

approval.add_decision(
    user_id=decision_user_id,
    decision=decision_request.decision,
    reason=decision_request.reason,
)
```

Move `@router.get("/rules")` and `@router.get("/history")` above `@router.get("/{approval_id}")` and `@router.post("/{approval_id}")`.

- [x] **Step 4: Run tests to verify GREEN**

Run: `cd backend && poetry run pytest src/tests/test_approvals.py -q`

Expected: PASS for approval tests.

---

### Task 3: Sandbox Settings JSON Persistence

**Files:**
- Modify: `backend/src/agent_platform/api/v1/sandbox.py`
- Test: `backend/src/tests/test_sandbox.py`

- [x] **Step 1: Write failing sandbox JSON reassignment tests**

Create `backend/src/tests/test_sandbox.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status

from agent_platform.models.session import Session


@pytest.mark.asyncio
async def test_create_sandbox_reassigns_settings_for_json_tracking(client, sample_user, auth_headers, db_session):
    session = Session(user_id=sample_user.id, name="Sandbox Session", settings={})
    db_session.add(session)
    await db_session.commit()

    info = MagicMock()
    info.id = "sb-test"
    info.status.value = "running"
    info.container_id = "container-test"
    info.created_at.isoformat.return_value = "2026-05-16T00:00:00"
    info.started_at = None
    info.last_activity_at.isoformat.return_value = "2026-05-16T00:00:00"
    info.config.image = "python:3.12-slim"
    info.config.memory_limit = "512m"
    info.config.cpu_limit = 0.5
    info.config.network_mode = "none"
    info.memory_usage_mb = None
    info.cpu_usage_percent = None

    provider = MagicMock()
    provider.create = AsyncMock(return_value=info)

    with patch("agent_platform.api.v1.sandbox.get_sandbox_provider", new=AsyncMock(return_value=provider)):
        response = await client.post(
            f"/api/v1/sessions/{session.id}/sandbox/create",
            headers=auth_headers,
            json={},
        )

    assert response.status_code == status.HTTP_201_CREATED
    await db_session.refresh(session)
    assert session.settings == {"sandbox_id": "sb-test"}
```

Add destroy regression:

```python
@pytest.mark.asyncio
async def test_destroy_sandbox_reassigns_settings_for_json_tracking(client, sample_user, auth_headers, db_session):
    session = Session(
        user_id=sample_user.id,
        name="Sandbox Session",
        settings={"sandbox_id": "sb-test", "other": True},
    )
    db_session.add(session)
    await db_session.commit()

    provider = MagicMock()
    provider.destroy = AsyncMock(return_value=None)

    with patch("agent_platform.api.v1.sandbox.get_sandbox_provider", new=AsyncMock(return_value=provider)):
        response = await client.post(
            f"/api/v1/sessions/{session.id}/sandbox/destroy",
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    await db_session.refresh(session)
    assert session.settings == {"other": True}
```

- [x] **Step 2: Run tests to verify RED**

Run: `cd backend && poetry run pytest src/tests/test_sandbox.py -q`

Expected: FAIL because `session.settings["sandbox_id"] = ...` and `pop()` mutate JSON in place.

- [x] **Step 3: Implement JSON reassignment**

In `create_sandbox`, replace in-place mutation with:

```python
settings = dict(session.settings or {})
settings["sandbox_id"] = info.id
session.settings = settings
```

In `destroy_sandbox`, replace `pop()` with:

```python
settings = dict(session.settings or {})
settings.pop("sandbox_id", None)
session.settings = settings
```

- [x] **Step 4: Run tests to verify GREEN**

Run: `cd backend && poetry run pytest src/tests/test_sandbox.py -q`

Expected: PASS.

---

### Task 4: Task Queue and Task API Surface

**Files:**
- Create: `backend/src/agent_platform/services/task_queue.py`
- Create: `backend/src/agent_platform/api/v1/tasks.py`
- Modify: `backend/src/agent_platform/main.py`
- Test: `backend/src/tests/test_tasks.py`

- [x] **Step 1: Write failing TaskQueue and API tests**

Create `backend/src/tests/test_tasks.py`:

```python
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import status

from agent_platform.models.session import Session
from agent_platform.models.task import Task, TaskStatus, TaskType
from agent_platform.services.task_queue import TaskQueue


class FakeRedis:
    def __init__(self):
        self.messages = []

    async def xadd(self, stream, fields, maxlen=None, approximate=True):
        self.messages.append((stream, fields, maxlen, approximate))
        return "1-0"

    async def xreadgroup(self, group, consumer, streams, count=1, block=1000):
        return []

    async def xack(self, stream, group, message_id):
        return 1


@pytest.mark.asyncio
async def test_task_queue_enqueue_updates_task_message_id(db_session, sample_user, sample_session):
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.PENDING,
        prompt="queued work",
    )
    db_session.add(task)
    await db_session.commit()

    queue = TaskQueue(redis=FakeRedis(), db=db_session)
    message_id = await queue.enqueue(task)

    await db_session.refresh(task)
    assert message_id == "1-0"
    assert task.redis_message_id == "1-0"
    assert task.status == TaskStatus.QUEUED
```

Add API tests:

```python
@pytest.mark.asyncio
async def test_create_task_endpoint_creates_task(client, sample_user, auth_headers, db_session):
    session = Session(user_id=sample_user.id, name="Task Session")
    db_session.add(session)
    await db_session.commit()

    response = await client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "prompt": "summarize project status",
            "session_id": str(session.id),
            "type": "async",
            "priority": 1,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["prompt"] == "summarize project status"
    assert data["status"] in {"pending", "queued"}
    assert data["stream_url"] == f"/api/v1/tasks/{data['id']}/stream"


@pytest.mark.asyncio
async def test_cancel_task_endpoint(client, sample_user, auth_headers, db_session):
    session = Session(user_id=sample_user.id, name="Task Session")
    db_session.add(session)
    await db_session.commit()

    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.PENDING,
        prompt="cancel me",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.post(f"/api/v1/tasks/{task.id}/cancel", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == TaskStatus.CANCELLED
```

- [x] **Step 2: Run tests to verify RED**

Run: `cd backend && poetry run pytest src/tests/test_tasks.py -q`

Expected: FAIL because `services.task_queue` and `api.v1.tasks` do not exist.

- [x] **Step 3: Implement minimal TaskQueue**

Create `services/task_queue.py`:

```python
import json
from typing import Any, Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.models.task import Task


class TaskQueue:
    def __init__(
        self,
        redis: Redis,
        db: AsyncSession,
        stream_name: str = "agent_platform:tasks",
        group_name: str = "task-workers",
    ):
        self.redis = redis
        self.db = db
        self.stream_name = stream_name
        self.group_name = group_name

    async def enqueue(self, task: Task) -> str:
        message_id = await self.redis.xadd(
            self.stream_name,
            {
                "task_id": str(task.id),
                "user_id": str(task.user_id),
                "session_id": str(task.session_id),
                "type": str(task.type),
                "payload": json.dumps({"prompt": task.prompt}),
            },
            maxlen=10000,
            approximate=True,
        )
        task.mark_queued()
        task.redis_message_id = message_id.decode() if isinstance(message_id, bytes) else message_id
        await self.db.commit()
        return task.redis_message_id

    async def ack(self, message_id: str) -> int:
        return await self.redis.xack(self.stream_name, self.group_name, message_id)
```

- [x] **Step 4: Implement minimal Task API**

Create `api/v1/tasks.py` with `POST /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/cancel`, `GET /tasks/{id}/stream`, and `GET /tasks/{id}/artifacts`. Use `TaskRuntime` for create/cancel and ownership checks against `current_user.id`.

In `main.py`, add:

```python
from agent_platform.api.v1 import tasks
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
```

- [x] **Step 5: Run tests to verify GREEN**

Run: `cd backend && poetry run pytest src/tests/test_tasks.py -q`

Expected: PASS.

---

### Task 5: Final Regression and Review

**Files:**
- Read-only verification across all touched backend files and docs.

- [x] **Step 1: Run targeted regression suite**

Run: `cd backend && poetry run pytest src/tests/test_task_runtime.py src/tests/test_approvals.py src/tests/test_sandbox.py src/tests/test_tasks.py -q`

Expected: PASS.

- [x] **Step 2: Run import smoke test**

Run: `cd backend && poetry run python -m compileall src/agent_platform`

Expected: exit code 0.

- [x] **Step 3: Review diff for original six findings**

Check:

```bash
git diff -- backend/src/agent_platform/agent/factory.py backend/src/agent_platform/api/v1/chat.py backend/src/agent_platform/api/v1/approvals.py backend/src/agent_platform/api/v1/sandbox.py backend/src/agent_platform/services/task_queue.py backend/src/agent_platform/api/v1/tasks.py backend/src/tests
```

Expected: every original P0/P1 finding has a targeted test and implementation change.

- [x] **Step 4: Commit only relevant files**

Run:

```bash
git add backend/src/agent_platform/agent/factory.py backend/src/agent_platform/api/v1/chat.py backend/src/agent_platform/api/v1/approvals.py backend/src/agent_platform/api/v1/sandbox.py backend/src/agent_platform/services/task_runtime.py backend/src/agent_platform/services/task_queue.py backend/src/agent_platform/api/v1/tasks.py backend/src/agent_platform/main.py backend/src/tests/test_task_runtime.py backend/src/tests/test_approvals.py backend/src/tests/test_sandbox.py backend/src/tests/test_tasks.py docs/superpowers/plans/2026-05-16-review-finding-fixes.md docs/03-architecture-design.md
git commit -m "fix: align task runtime review findings"
```

Expected: commit succeeds without staging unrelated frontend or worktree files.
