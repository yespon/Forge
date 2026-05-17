from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from agent_platform.models.session import Session


@pytest.mark.asyncio
async def test_create_sandbox_reassigns_settings_for_json_tracking(
    client, sample_user, auth_headers, db_session
):
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

    with patch(
        "agent_platform.api.v1.sandbox.get_sandbox_provider",
        new=AsyncMock(return_value=provider),
    ):
        response = await client.post(
            f"/api/v1/sessions/{session.id}/sandbox/create",
            headers=auth_headers,
            json={},
        )

    assert response.status_code == status.HTTP_201_CREATED
    await db_session.refresh(session)
    assert session.settings == {"sandbox_id": "sb-test"}


@pytest.mark.asyncio
async def test_destroy_sandbox_reassigns_settings_for_json_tracking(
    client, sample_user, auth_headers, db_session
):
    session = Session(
        user_id=sample_user.id,
        name="Sandbox Session",
        settings={"sandbox_id": "sb-test", "other": True},
    )
    db_session.add(session)
    await db_session.commit()

    provider = MagicMock()
    provider.destroy = AsyncMock(return_value=None)

    with patch(
        "agent_platform.api.v1.sandbox.get_sandbox_provider",
        new=AsyncMock(return_value=provider),
    ):
        response = await client.post(
            f"/api/v1/sessions/{session.id}/sandbox/destroy",
            headers=auth_headers,
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    await db_session.refresh(session)
    assert session.settings == {"other": True}
