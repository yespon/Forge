# Agent Runtime Platform

Enterprise Multi-User Agent Runtime Platform with sandbox isolation, skill management, and human-in-the-loop approval workflows.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Runtime Platform                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   User API  │  │  Admin API  │  │   Runtime API (DeepAgents)│  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         └─────────────────┼─────────────────────┘                │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              FastAPI Application Layer                   │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐  │    │
│  │  │  Auth   │ │  Orgs   │ │ Sessions│ │   Sandboxes   │  │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └───────────────┘  │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SQLAlchemy ORM (Async)                      │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            ▼                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  PostgreSQL │  │    Redis    │  │      Sandbox Runtime    │  │
│  │  (Models)   │  │  (Cache)    │  │    (Docker/K8s/Dind)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **Migrations**: Alembic
- **Testing**: pytest + pytest-asyncio
- **Deployment**: Docker Compose / Kubernetes

## Project Structure

```
forge/
├── Makefile                    # Build automation
├── docker-compose.yml          # Development services
├── pyproject.toml              # Root Poetry configuration
├── .env                        # Environment variables
├── README.md                   # This file
│
├── backend/
│   ├── pyproject.toml          # Backend dependencies
│   ├── alembic.ini             # Alembic configuration
│   ├── src/agent_platform/     # Main application
│   │   ├── main.py             # FastAPI entry point
│   │   ├── config.py           # Settings management
│   │   ├── database.py         # DB connection & session
│   │   ├── models/             # SQLAlchemy models
│   │   │   ├── user.py         # User model
│   │   │   └── org.py          # Org, Team, UserTeam models
│   │   └── api/v1/             # API routes
│   │       └── health.py       # Health check endpoints
│   ├── alembic/                # Database migrations
│   │   ├── env.py              # Alembic environment
│   │   └── versions/           # Migration files
│   └── tests/                  # Test suite
│       ├── conftest.py         # Pytest fixtures
│       └── test_health.py      # Health check tests
│
└── infra/
    └── docker/
        └── Dockerfile.backend  # Backend container image
```

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Poetry (`pip install poetry`)

### Setup

1. **Clone and install dependencies:**
```bash
git clone <repo-url>
cd forge
make install
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Start services:**
```bash
make dev
```

4. **Run database migrations:**
```bash
make migrate
```

5. **Verify setup:**
```bash
make test
curl http://localhost:8000/health
```

## Development Commands

| Command | Description |
|---------|-------------|
| `make install` | Install Poetry and dependencies |
| `make dev` | Start PostgreSQL and Redis containers |
| `make down` | Stop all containers |
| `make migrate` | Run database migrations |
| `make migrate-create` | Create new migration |
| `make test` | Run test suite |
| `make lint` | Run linting (flake8, mypy) |
| `make format` | Format code (black, isort) |
| `make clean` | Clean up containers and volumes |
| `make init` | Full setup (install + dev + migrate) |

## API Endpoints

### Health Checks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health status with database connectivity |
| `/api/v1/ready` | GET | Kubernetes readiness probe |
| `/api/v1/live` | GET | Kubernetes liveness probe |

### Example Response

```bash
$ curl http://localhost:8000/health
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development",
  "services": {
    "database": "healthy"
  }
}
```

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Models

### User
- Multi-tenant user with org association
- Role-based access control (platform_admin, org_admin, team_admin, developer, viewer)
- MFA and password hash support

### Org
- Organization with quota management
- Settings and billing info

### Team
- Teams within organizations
- Many-to-many with users via UserTeam

### UserTeam
- Association table for user-team membership
- Role within team context

## Testing

```bash
# Run all tests
cd backend
poetry run pytest -v

# Run with coverage
poetry run pytest --cov=src/agent_platform --cov-report=html

# Run specific test
poetry run pytest tests/test_health.py::test_health_check -v
```

## Database Migrations

```bash
cd backend

# Create new migration
poetry run alembic revision --autogenerate -m "add new feature"

# Run migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1

# View current version
poetry run alembic current
```

## Configuration

Configuration is managed via environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `REDIS_URL` | Redis connection string | - |
| `SECRET_KEY` | JWT signing key | - |
| `ENV` | Environment (development/production) | development |
| `DEBUG` | Enable debug mode | false |
| `LOG_LEVEL` | Logging level | INFO |
| `CORS_ORIGINS` | Allowed CORS origins | localhost:3000,5173 |

## Week 1 Deliverables

- [x] Project structure with FastAPI
- [x] PostgreSQL + SQLAlchemy async models
- [x] Alembic migrations
- [x] User/Org/Team models
- [x] Health check endpoints
- [x] Docker Compose setup
- [x] Test suite with pytest

## Week 2+ Roadmap

- [ ] JWT authentication (login/logout)
- [ ] Session management API
- [ ] User/Org management endpoints
- [ ] Sandbox runtime integration
- [ ] Skill management system
- [ ] HITL approval workflows
- [ ] Audit logging
