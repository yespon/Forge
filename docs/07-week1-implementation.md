# Week 1 实现指南

## 目标

建立项目基础结构，完成数据库迁移，实现用户认证与会话管理基础 API。

---

## 项目结构

```
agent-runtime-platform/
├── Makefile
├── docker-compose.yml
├── docker-compose.override.yml
├── pyproject.toml
├── alembic.ini
├── .env.example
├── .gitignore
├── README.md
│
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── agent_platform/          # 主包
│   │   │   ├── __init__.py
│   │   │   ├── main.py              # FastAPI 入口
│   │   │   ├── config.py            # 配置管理
│   │   │   ├── database.py          # 数据库连接
│   │   │   ├── models/              # SQLAlchemy 模型
│   │   │   │   ├── __init__.py
│   │   │   │   ├── user.py
│   │   │   │   ├── org.py
│   │   │   │   ├── session.py
│   │   │   │   └── task.py
│   │   │   ├── api/                 # API 路由
│   │   │   │   ├── __init__.py
│   │   │   │   ├── deps.py          # 依赖注入
│   │   │   │   ├── v1/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── auth.py
│   │   │   │   │   ├── sessions.py
│   │   │   │   │   └── users.py
│   │   │   ├── services/            # 业务逻辑
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth_service.py
│   │   │   │   └── session_service.py
│   │   │   └── core/                # 核心工具
│   │   │       ├── __init__.py
│   │   │       ├── security.py      # 密码/JWT
│   │   │       └── exceptions.py    # 自定义异常
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── conftest.py
│   │       ├── test_auth.py
│   │       └── test_sessions.py
│   └── alembic/                     # 数据库迁移
│       ├── env.py
│       ├── README
│       └── versions/
│
├── frontend/                        # React 前端 (Week 8 开始)
│   └── ...
│
└── infra/                           # 基础设施配置
    └── docker/
        ├── Dockerfile.backend
        ├── Dockerfile.frontend
        └── init-scripts/
```

---

## 1. 项目初始化

### 1.1 根目录配置

**pyproject.toml** (根目录)

```toml
[tool.poetry]
name = "agent-runtime-platform"
version = "0.1.0"
description = "Enterprise Multi-User Agent Runtime Platform"
authors = ["Your Team <team@company.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.12"

[tool.poetry.group.backend.dependencies]
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.32.0"}
sqlalchemy = {extras = ["asyncpg"], version = "^2.0.36"}
alembic = "^1.14.0"
pydantic = "^2.10.0"
pydantic-settings = "^2.6.0"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-multipart = "^0.0.17"
httpx = "^0.27.0"
redis = {extras = ["hiredis"], version = "^5.2.0"}
structlog = "^24.4.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-asyncio = "^0.24.0"
pytest-cov = "^6.0.0"
black = "^24.10.0"
isort = "^5.13.0"
flake8 = "^7.1.0"
mypy = "^1.13.0"
pre-commit = "^4.0.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 100
target-version = ['py312']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["backend/src/tests"]
```

**docker-compose.yml**

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-platform}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-platform123}
      POSTGRES_DB: ${DB_NAME:-agent_platform}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/docker/init-scripts/postgres:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-platform}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: infra/docker/Dockerfile.backend
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-platform}:${DB_PASSWORD:-platform123}@postgres:5432/${DB_NAME:-agent_platform}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY:-change-me-in-production}
      ENV: ${ENV:-development}
    volumes:
      - ./backend/src:/app/src
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn agent_platform.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  postgres_data:
  redis_data:
```

**docker-compose.override.yml** (开发环境)

```yaml
version: "3.8"

services:
  backend:
    environment:
      - LOG_LEVEL=debug
      - DEBUG=true
    command: uvicorn agent_platform.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/src
```

**Makefile**

```makefile
.PHONY: install dev migrate test lint format clean

# 安装依赖
install:
	pip install poetry
	poetry install --with dev

# 启动开发环境
dev:
	docker-compose up -d

# 停止开发环境
down:
	docker-compose down

# 数据库迁移
migrate:
	cd backend && poetry run alembic upgrade head

migrate-create:
	@read -p "Migration message: " msg; \
	cd backend && poetry run alembic revision --autogenerate -m "$$msg"

# 测试
test:
	cd backend && poetry run pytest -v --cov=src/agent_platform --cov-report=term-missing

test-watch:
	cd backend && poetry run pytest -v -f

# 代码质量
lint:
	cd backend && poetry run flake8 src
	cd backend && poetry run mypy src

format:
	cd backend && poetry run black src
	cd backend && poetry run isort src

format-check:
	cd backend && poetry run black --check src
	cd backend && poetry run isort --check-only src

# 清理
clean:
	docker-compose down -v
	docker system prune -f

# 初始化（新项目）
init: install
	cp .env.example .env
	docker-compose up -d postgres redis
	sleep 5
	$(MAKE) migrate
```

---

### 1.2 后端核心代码

**backend/pyproject.toml**

```toml
[tool.poetry]
name = "agent-platform-backend"
version = "0.1.0"
package-mode = false

[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.32.0"}
sqlalchemy = {extras = ["asyncpg"], version = "^2.0.36"}
alembic = "^1.14.0"
pydantic = "^2.10.0"
pydantic-settings = "^2.6.0"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-multipart = "^0.0.17"
httpx = "^0.27.0"
redis = {extras = ["hiredis"], version = "^5.2.0"}
structlog = "^24.4.0"
asyncpg = "^0.30.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-asyncio = "^0.24.0"
pytest-cov = "^6.0.0"
black = "^24.10.0"
isort = "^5.13.0"
flake8 = "^7.1.0"
mypy = "^1.13.0"
```

**backend/src/agent_platform/config.py**

```python
"""Application configuration."""

from functools import lru_cache
from typing import Optional

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # App
    APP_NAME: str = "Agent Runtime Platform"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"  # development, staging, production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: RedisDsn
    
    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW: int = 60
    
    @property
    def is_development(self) -> bool:
        return self.ENV == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**backend/src/agent_platform/database.py**

```python
"""Database connection and session management."""

from typing import AsyncGenerator

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

# Base class for models
Base = declarative_base()


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
        # In production, use Alembic migrations instead
        if settings.is_development:
            await conn.run_sync(Base.metadata.create_all)
```

**backend/src/agent_platform/models/user.py**

```python
"""User and organization models."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.session import Session
    from agent_platform.models.task import Task


class UserRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    ORG_ADMIN = "org_admin"
    TEAM_ADMIN = "team_admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Org(Base):
    """Organization model."""
    
    __tablename__ = "orgs"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    quota: Mapped[dict] = mapped_column(JSON, default=dict)
    billing_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="org")
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="org")


class Team(Base):
    """Team model."""
    
    __tablename__ = "teams"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="teams")
    members: Mapped[list["UserTeam"]] = relationship("UserTeam", back_populates="team")
    
    __table_args__ = (
        # Unique constraint for org + slug
        {"UniqueConstraint": ("org_id", "slug")},
    )


class User(Base):
    """User model."""
    
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    role: Mapped[str] = mapped_column(SQLEnum(UserRole), default=UserRole.DEVELOPER)
    status: Mapped[str] = mapped_column(SQLEnum(UserStatus), default=UserStatus.ACTIVE)
    
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    quota_override: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="users")
    teams: Mapped[list["UserTeam"]] = relationship("UserTeam", back_populates="user")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="user")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user")
    
    __table_args__ = (
        {"UniqueConstraint": ("org_id", "email")},
    )
    
    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and self.deleted_at is None
    
    @property
    def is_admin(self) -> bool:
        return self.role in (UserRole.PLATFORM_ADMIN, UserRole.ORG_ADMIN)


class UserTeam(Base):
    """User-Team association."""
    
    __tablename__ = "user_teams"
    
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    team_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # member, admin
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="teams")
    team: Mapped["Team"] = relationship("Team", back_populates="members")
```

**backend/src/agent_platform/models/session.py**

```python
"""Session and sandbox models."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Interval, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.user import User


class SessionStatus:
    CREATING = "creating"
    ACTIVE = "active"
    IDLE = "idle"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    ERROR = "error"


class Session(Base):
    """Agent session model."""
    
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False)
    
    sandbox_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thread_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.CREATING)
    channel: Mapped[str] = mapped_column(String(20), default="web")
    
    model_config: Mapped[dict] = mapped_column(JSON, default=dict)
    
    token_used: Mapped[int] = mapped_column(Integer, default=0)
    token_budget: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    
    idle_timeout: Mapped[timedelta] = mapped_column(Interval, default=timedelta(minutes=5))
    max_lifetime: Mapped[timedelta] = mapped_column(Interval, default=timedelta(hours=24))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now() + timedelta(hours=24)
    )
    
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
```

**backend/src/agent_platform/main.py**

```python
"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_platform.api.v1 import auth, sessions, users
from agent_platform.config import get_settings
from agent_platform.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    if settings.is_development:
        await init_db()
    yield
    # Shutdown


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Multi-User Agent Runtime Platform",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
```

---

### 1.3 Alembic 配置

**backend/alembic.ini**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
timezone = Asia/Shanghai

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**backend/alembic/env.py**

```python
"""Alembic environment configuration."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from agent_platform.config import get_settings
from agent_platform.database import Base
from agent_platform.models import org, session, task, user  # noqa

settings = get_settings()
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return str(settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## 2. 测试配置

**backend/src/tests/conftest.py**

```python
"""Pytest fixtures."""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_platform.database import Base
from agent_platform.main import app

# Test database
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test_agent_platform"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Set up test database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(setup_database) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

---

## Week 1 交付检查清单

- [ ] 项目目录结构初始化
- [ ] Poetry 依赖配置完成
- [ ] Docker Compose 开发环境可运行
- [ ] PostgreSQL + Redis 服务正常
- [ ] SQLAlchemy 模型定义完成
  - [ ] User/Org/Team 模型
  - [ ] Session 模型
- [ ] Alembic 迁移配置
- [ ] 首次迁移脚本生成并执行
- [ ] FastAPI 基础应用运行
- [ ] `/health` 接口返回正常
- [ ] pytest 基础配置完成

---

## 运行命令

```bash
# 1. 初始化项目
make init

# 2. 启动服务
docker-compose up -d

# 3. 验证数据库连接
docker-compose exec postgres psql -U platform -d agent_platform -c "\dt"

# 4. 运行测试
make test

# 5. 访问 API 文档
open http://localhost:8000/docs
```
