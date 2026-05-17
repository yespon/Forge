"""Task queue and API tests."""

from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import status

from agent_platform.models.session import Session
from agent_platform.models.task import Task, TaskStatus, TaskType
from agent_platform.models.task_event import TaskEvent, TaskEventType
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


@pytest_asyncio.fixture
async def sample_session(db_session, sample_user):
    session = Session(user_id=sample_user.id, name="Task Session")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


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


@pytest.mark.asyncio
async def test_create_task_endpoint_creates_task(client, auth_headers, sample_session):
    response = await client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={
            "prompt": "summarize project status",
            "session_id": str(sample_session.id),
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
async def test_get_task_endpoint_returns_task(client, sample_user, auth_headers, db_session, sample_session):
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.PENDING,
        prompt="look me up",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.get(f"/api/v1/tasks/{task.id}", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(task.id)


@pytest.mark.asyncio
async def test_cancel_task_endpoint(client, sample_user, auth_headers, db_session, sample_session):
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.PENDING,
        prompt="cancel me",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.post(f"/api/v1/tasks/{task.id}/cancel", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == TaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_stream_task_endpoint_returns_sse(client, sample_user, auth_headers, db_session, sample_session):
    # Use a COMPLETED task so SSE replays events instead of trying to execute
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.COMPLETED,
        prompt="stream me",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.get(f"/api/v1/tasks/{task.id}/stream", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in response.text


@pytest.mark.asyncio
async def test_task_artifacts_endpoint_returns_list(client, sample_user, auth_headers, db_session, sample_session):
    from agent_platform.models.artifact import Artifact

    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.COMPLETED,
        prompt="artifacts please",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    artifact = Artifact(
        task_id=task.id,
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        name="report.md",
        mime_type="text/markdown",
        size=512,
        storage_path="/tmp/report.md",
    )
    db_session.add(artifact)
    await db_session.commit()

    response = await client.get(f"/api/v1/tasks/{task.id}/artifacts", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "report.md"


@pytest.mark.asyncio
async def test_delete_task_endpoint(client, sample_user, auth_headers, db_session, sample_session):
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.COMPLETED,
        prompt="delete me",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.delete(f"/api/v1/tasks/{task.id}", headers=auth_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify deleted
    response = await client.get(f"/api/v1/tasks/{task.id}", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_active_task_fails(client, sample_user, auth_headers, db_session, sample_session):
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.RUNNING,
        prompt="running task",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.delete(f"/api/v1/tasks/{task.id}", headers=auth_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_create_scheduled_task(client, auth_headers, sample_session):
    response = await client.post(
        "/api/v1/tasks/scheduled",
        headers=auth_headers,
        json={
            "prompt": "daily report",
            "session_id": str(sample_session.id),
            "cron": "0 9 * * 1-5",
            "timezone": "Asia/Shanghai",
            "enabled": True,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["prompt"] == "daily report"
    assert data["type"] in {"scheduled", "recurring"}


# ---- resume / events / list-filter tests ----


@pytest.mark.asyncio
async def test_resume_waiting_hitl_task(client, sample_user, auth_headers, db_session, sample_session):
    """POST /{task_id}/resume should re-queue an approved WAITING_HITL task."""
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.WAITING_HITL,
        prompt="needs approval",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/tasks/{task.id}/resume",
        headers=auth_headers,
        json={"decision": "approved", "reason": "looks good"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == TaskStatus.QUEUED


@pytest.mark.asyncio
async def test_resume_rejected_task_gets_cancelled(client, sample_user, auth_headers, db_session, sample_session):
    """POST /{task_id}/resume with rejected decision should cancel."""
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.WAITING_HITL,
        prompt="reject me",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/tasks/{task.id}/resume",
        headers=auth_headers,
        json={"decision": "rejected"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == TaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_resume_non_hitl_task_fails(client, sample_user, auth_headers, db_session, sample_session):
    """POST /{task_id}/resume on non-WAITING_HITL task should 400."""
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.RUNNING,
        prompt="running",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/tasks/{task.id}/resume",
        headers=auth_headers,
        json={"decision": "approved"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_get_task_events(client, sample_user, auth_headers, db_session, sample_session):
    """GET /{task_id}/events should return task event history."""
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.PENDING,
        prompt="events please",
    )
    db_session.add(task)
    await db_session.commit()

    # Add some events
    for etype in [TaskEventType.CREATED, TaskEventType.STARTED]:
        ev = TaskEvent(task_id=task.id, type=etype, data={"info": "test"})
        db_session.add(ev)
    await db_session.commit()

    response = await client.get(f"/api/v1/tasks/{task.id}/events", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_get_task_events_empty(client, sample_user, auth_headers, db_session, sample_session):
    """GET /{task_id}/events returns empty list for task with no events."""
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.PENDING,
        prompt="no events",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.get(f"/api/v1/tasks/{task.id}/events", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_tasks_filter_by_status(client, sample_user, auth_headers, db_session, sample_session):
    """GET /tasks?status=completed should filter correctly."""
    for s in [TaskStatus.PENDING, TaskStatus.COMPLETED, TaskStatus.COMPLETED]:
        t = Task(
            user_id=sample_user.id,
            org_id=sample_user.org_id,
            session_id=sample_session.id,
            type=TaskType.ASYNC,
            status=s,
            prompt=f"task-{s}",
        )
        db_session.add(t)
    await db_session.commit()

    response = await client.get(
        "/api/v1/tasks?status=completed",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert all(i["status"] == TaskStatus.COMPLETED.value for i in items)


# ---- Scheduler unit tests ----

try:
    import croniter as _croniter  # noqa: F401
    _has_croniter = True
except ImportError:
    _has_croniter = False


@pytest.mark.skipif(not _has_croniter, reason="croniter not installed")
class TestTaskScheduler:
    """Tests for the cron scheduler logic."""

    @pytest.mark.asyncio
    async def test_find_due_tasks_detects_pending_cron(self, db_session, sample_user, sample_session):
        """Scheduler should find PENDING scheduled tasks with valid cron."""
        from datetime import datetime, timezone
        from agent_platform.workers.scheduler import TaskScheduler

        task = Task(
            user_id=sample_user.id,
            org_id=sample_user.org_id,
            session_id=sample_session.id,
            type=TaskType.SCHEDULED,
            status=TaskStatus.PENDING,
            prompt="cron job",
            extra_metadata={
                "schedule": {
                    "cron": "* * * * *",  # every minute — always due
                    "timezone": "UTC",
                    "enabled": True,
                }
            },
        )
        db_session.add(task)
        await db_session.commit()

        scheduler = TaskScheduler()
        due = await scheduler._find_due_tasks(db_session, datetime.now(timezone.utc))
        assert any(str(t.id) == str(task.id) for t in due)

    @pytest.mark.asyncio
    async def test_disabled_task_not_found(self, db_session, sample_user, sample_session):
        """Disabled scheduled tasks should NOT be returned."""
        from datetime import datetime, timezone
        from agent_platform.workers.scheduler import TaskScheduler

        task = Task(
            user_id=sample_user.id,
            org_id=sample_user.org_id,
            session_id=sample_session.id,
            type=TaskType.SCHEDULED,
            status=TaskStatus.PENDING,
            prompt="disabled job",
            extra_metadata={
                "schedule": {
                    "cron": "* * * * *",
                    "timezone": "UTC",
                    "enabled": False,
                }
            },
        )
        db_session.add(task)
        await db_session.commit()

        scheduler = TaskScheduler()
        due = await scheduler._find_due_tasks(db_session, datetime.now(timezone.utc))
        assert not any(str(t.id) == str(task.id) for t in due)
