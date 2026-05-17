"""Database connection and session management."""

from typing import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from agent_platform.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Alias for external consumers (workers, scripts)
AsyncSessionFactory = AsyncSessionLocal

# Base class for models
Base = declarative_base()

# Redis singleton
_redis_instance: Redis | None = None


async def get_redis() -> Redis:
    """Get or create a shared Redis connection."""
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = Redis.from_url(
            str(settings.REDIS_URL),
            decode_responses=False,
        )
    return _redis_instance


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        if settings.is_development:
            await conn.run_sync(Base.metadata.create_all)
