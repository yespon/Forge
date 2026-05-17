"""Pytest fixtures."""

import asyncio
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from agent_platform.auth.jwt import create_access_token
from agent_platform.database import Base, get_db
from agent_platform.main import app
from agent_platform.models.org import Org
from agent_platform.models.user import User, UserRole

# Test database - use same credentials as main app but different database name
TEST_DATABASE_URL = "postgresql+asyncpg://platform:platform123@localhost:5432/test_agent_platform"

engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def setup_database():
    """Set up test database once per session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with TestingSessionLocal() as session:
        yield session
        await session.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client with the test database session."""
    from httpx import ASGITransport

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def sample_user(db_session) -> User:
    """Create a sample user for testing."""
    # Create an org with a unique slug to avoid conflicts
    unique_suffix = uuid4().hex[:8]
    org = Org(
        name="Test Org",
        slug=f"test-org-{unique_suffix}",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # Create user
    user = User(
        email=f"test_{uuid4()}@example.com",
        password_hash="hashed_password",
        display_name="Test User",
        role=UserRole.DEVELOPER,
        org_id=org.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Attach org to user for convenience
    user.org = org

    return user


@pytest.fixture
def auth_headers(sample_user) -> dict:
    """Create authentication headers for the sample user."""
    token = create_access_token({"sub": str(sample_user.id)})
    return {"Authorization": f"Bearer {token}"}
