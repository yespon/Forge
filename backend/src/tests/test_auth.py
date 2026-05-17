"""Authentication tests."""

import uuid

import pytest
from httpx import AsyncClient

# Test password - bcrypt has 72 byte limit
TEST_PASSWORD = "TestPass123!"


def unique_email(prefix: str = "test") -> str:
    """Generate unique email address."""
    return f"{prefix}.{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient) -> None:
    """Test user registration."""
    response = await client.post(
        "/auth/register",
        json={
            "email": unique_email("register"),
            "password": TEST_PASSWORD,
            "display_name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "user" in data
    assert "tokens" in data
    assert data["user"]["display_name"] == "Test User"
    assert "access_token" in data["tokens"]
    assert "refresh_token" in data["tokens"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    """Test registration with duplicate email fails."""
    email = unique_email("duplicate")

    # Register first user
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    # Try to register again with same email
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    """Test successful login."""
    email = unique_email("login")

    # Register user first
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    # Login
    response = await client.post(
        "/auth/login",
        data={
            "username": email,
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "tokens" in data
    assert data["user"]["email"] == email
    assert "access_token" in data["tokens"]


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    """Test login with invalid password fails."""
    email = unique_email("badpass")

    # Register user first
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    # Try login with wrong password
    response = await client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "WrongPass123!",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    """Test login with non-existent user fails."""
    response = await client.post(
        "/auth/login",
        data={
            "username": unique_email("nonexistent"),
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient) -> None:
    """Test getting current user info with valid token."""
    email = unique_email("me")

    # Register and login
    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )
    tokens = register_response.json()["tokens"]

    # Get current user info
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email


@pytest.mark.asyncio
async def test_get_me_no_token(client: AsyncClient) -> None:
    """Test getting current user without token fails."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient) -> None:
    """Test token refresh."""
    email = unique_email("refresh")

    # Register and login
    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )
    refresh_token = register_response.json()["tokens"]["refresh_token"]

    # Refresh token
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient) -> None:
    """Test refresh with invalid token fails."""
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid_token_here"},
    )
    assert response.status_code == 401
