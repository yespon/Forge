"""Tests for connectors, artifacts, and skills API endpoints."""

from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import status

from agent_platform.models.artifact import Artifact
from agent_platform.models.connector import (
    AuthType,
    ConnectionStatus,
    Connector,
    ConnectorConnection,
    ConnectorStatus,
)
from agent_platform.models.session import Session
from agent_platform.models.skill import Skill, SkillVisibility
from agent_platform.models.task import Task, TaskStatus, TaskType


# ---------- Connector API ----------


@pytest.mark.asyncio
async def test_list_connectors(client, sample_user, auth_headers, db_session):
    """GET /connectors should return active connectors."""
    c = Connector(
        name=f"feishu-{uuid4().hex[:6]}",
        display_name="飞书",
        auth_type=AuthType.OAUTH2,
        supported_scopes=["im:message"],
        status=ConnectorStatus.ACTIVE,
    )
    db_session.add(c)
    await db_session.commit()

    response = await client.get("/api/v1/connectors", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert any(i["name"] == c.name for i in items)


@pytest.mark.asyncio
async def test_connector_authorize_and_status(client, sample_user, auth_headers, db_session):
    """POST /connectors/{id}/authorize then GET /connectors/{id}/status."""
    c = Connector(
        name=f"test-conn-{uuid4().hex[:6]}",
        display_name="Test Connector",
        auth_type=AuthType.API_KEY,
        status=ConnectorStatus.ACTIVE,
    )
    db_session.add(c)
    await db_session.commit()

    # Authorize
    response = await client.post(
        f"/api/v1/connectors/{c.id}/authorize",
        headers=auth_headers,
        json={"scopes": ["read"], "vault_ref": "vault://test/key"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    # Check status
    response = await client.get(
        f"/api/v1/connectors/{c.id}/status",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] in ("active", "pending")


# ---------- Skills API ----------


@pytest.mark.asyncio
async def test_list_skills(client, sample_user, auth_headers, db_session):
    """GET /skills should return builtin and DB skills."""
    response = await client.get("/api/v1/skills", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_get_skill_not_found(client, sample_user, auth_headers):
    """GET /skills/{name} for a nonexistent skill should 404."""
    response = await client.get("/api/v1/skills/nonexistent-xyz", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_install_and_uninstall_skill(client, sample_user, auth_headers, db_session):
    """POST /skills/{name}/install and /uninstall lifecycle."""
    skill = Skill(
        name=f"test-skill-{uuid4().hex[:6]}",
        description="A test skill",
        visibility=SkillVisibility.PUBLIC,
        is_active=True,
        manifest={"tools": []},
    )
    db_session.add(skill)
    await db_session.commit()

    # Install
    response = await client.post(
        f"/api/v1/skills/{skill.name}/install",
        headers=auth_headers,
        json={},
    )
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    # Uninstall
    response = await client.post(
        f"/api/v1/skills/{skill.name}/uninstall",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK


# ---------- Artifacts API ----------


@pytest_asyncio.fixture
async def sample_session(db_session, sample_user):
    """Create a sample session for artifact tests."""
    s = Session(user_id=sample_user.id, name="Artifact Session")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest.mark.asyncio
async def test_list_task_artifacts(client, sample_user, auth_headers, db_session, sample_session):
    """GET /tasks/{id}/artifacts should return artifacts from DB."""
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.COMPLETED,
        prompt="generate report",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    artifact = Artifact(
        task_id=task.id,
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        name="report.pdf",
        mime_type="application/pdf",
        size=1024,
        storage_path="/tmp/test/report.pdf",
        artifact_type="file",
    )
    db_session.add(artifact)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/tasks/{task.id}/artifacts",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "report.pdf"
    assert items[0]["mime_type"] == "application/pdf"
    assert items[0]["size"] == 1024
    assert "/artifacts/" in items[0]["url"]


@pytest.mark.asyncio
async def test_list_task_artifacts_empty(client, sample_user, auth_headers, db_session, sample_session):
    """GET /tasks/{id}/artifacts with no artifacts returns empty list."""
    task = Task(
        user_id=sample_user.id,
        org_id=sample_user.org_id,
        session_id=sample_session.id,
        type=TaskType.ASYNC,
        status=TaskStatus.COMPLETED,
        prompt="no output",
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/tasks/{task.id}/artifacts",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["items"] == []
