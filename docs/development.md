# Development Guide

## Getting Started

### Prerequisites

- Python 3.12+
- Docker Desktop or Docker Engine
- Poetry (`pip install poetry`)
- Git

### Initial Setup

```bash
# Clone repository
git clone <repo-url>
cd forge

# Install dependencies
make install

# Copy environment file
cp .env.example .env

# Start services
make dev

# Run migrations
make migrate

# Verify setup
make test
```

## Project Structure

```
backend/
├── src/agent_platform/     # Application code
│   ├── main.py             # FastAPI entry
│   ├── config.py           # Settings
│   ├── database.py         # DB connection
│   ├── models/             # SQLAlchemy models
│   └── api/v1/             # API routes
├── tests/                  # Test files
└── alembic/                # Migrations
```

## Development Workflow

### 1. Start Development Environment

```bash
# Start PostgreSQL and Redis
make dev

# Verify services
docker-compose ps
```

### 2. Run Migrations

```bash
# Apply pending migrations
make migrate

# Create new migration after model changes
make migrate-create
# Enter migration message when prompted
```

### 3. Run Tests

```bash
# Run all tests
make test

# Run with coverage
poetry run pytest --cov=src/agent_platform --cov-report=html

# Run specific test
poetry run pytest tests/test_health.py::test_health_check -v

# Run with asyncio debug
poetry run pytest -v --asyncio-mode=auto
```

### 4. Code Quality

```bash
# Format code
make format

# Run linters
make lint
```

## Database Operations

### Connecting to PostgreSQL

```bash
# Using docker-compose
docker-compose exec postgres psql -U platform -d agent_platform

# Using docker directly
docker exec -it forge-postgres-1 psql -U platform -d agent_platform
```

### Common SQL Commands

```sql
-- List tables
\dt

-- Describe table
\d users

-- Check alembic version
SELECT * FROM alembic_version;

-- Count records
SELECT COUNT(*) FROM users;
```

### Creating Migrations

After modifying models:

```bash
cd backend

# Generate migration
poetry run alembic revision --autogenerate -m "add user preferences"

# Review generated migration
cat alembic/versions/*.py

# Apply migration
poetry run alembic upgrade head

# Rollback if needed
poetry run alembic downgrade -1
```

## Testing

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_health.py       # Health endpoint tests
└── test_models.py       # Model tests (to add)
```

### Writing Tests

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_example(client: AsyncClient):
    """Test example endpoint."""
    response = await client.get("/api/v1/example")
    assert response.status_code == 200
    data = response.json()
    assert "field" in data
```

### Fixtures

Available fixtures in `conftest.py`:

| Fixture | Description |
|---------|-------------|
| `event_loop` | Async event loop (session scope) |
| `setup_database` | Creates/drops test tables |
| `db_session` | Fresh database session per test |
| `client` | HTTP test client |

## API Development

### Adding New Endpoints

1. **Create router file** in `src/agent_platform/api/v1/`

```python
# src/agent_platform/api/v1/users.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.database import get_db

router = APIRouter()

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    """List all users."""
    return {"users": []}
```

2. **Register router** in `main.py`

```python
from agent_platform.api.v1 import users

app.include_router(users.router, prefix="/api/v1", tags=["users"])
```

3. **Add tests** in `tests/`

### Request/Response Models

Use Pydantic models for validation:

```python
from pydantic import BaseModel

class CreateUserRequest(BaseModel):
    email: str
    display_name: str | None = None

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection |
| `REDIS_URL` | Yes | - | Redis connection |
| `SECRET_KEY` | Yes | - | JWT signing key |
| `ENV` | No | development | Environment name |
| `DEBUG` | No | false | Debug mode |
| `LOG_LEVEL` | No | INFO | Logging level |

### Adding New Settings

Edit `src/agent_platform/config.py`:

```python
class Settings(BaseSettings):
    # ... existing fields
    NEW_SETTING: str = "default_value"
```

## Debugging

### Enable SQL Logging

Set in `.env`:
```
DEBUG=true
LOG_LEVEL=debug
```

### Debug Mode

```bash
# Run with auto-reload
poetry run uvicorn agent_platform.main:app --reload

# With debugger
poetry run python -m pdb -m uvicorn agent_platform.main:app
```

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'agent_platform'`
**Fix**: Set `PYTHONPATH=./src`

**Issue**: `asyncpg.exceptions.InvalidPasswordError`
**Fix**: Check `.env` database credentials match docker-compose

**Issue**: `alembic.util.exc.CommandError: Can't locate revision`
**Fix**: Run `poetry run alembic stamp head` to mark current state

## Docker Commands

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f postgres

# Restart service
docker-compose restart backend

# Clean start
docker-compose down -v
docker-compose up -d

# Rebuild image
docker-compose build backend
```

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push branch
git push -u origin feature/new-feature
```

### Commit Message Convention

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `chore:` Build/tooling changes

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
