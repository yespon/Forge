"""Health check tests."""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "environment" in data
    assert "services" in data
    assert "database" in data["services"]


@pytest.mark.asyncio
async def test_readiness_check(client):
    """Test readiness check endpoint."""
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True


@pytest.mark.asyncio
async def test_liveness_check(client):
    """Test liveness check endpoint."""
    response = await client.get("/api/v1/live")
    assert response.status_code == 200
    data = response.json()
    assert data["alive"] is True
