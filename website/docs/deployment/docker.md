# Docker Deployment

## Quick Start
```bash
docker-compose up -d
```

This starts:
- PostgreSQL 16 (port 5432)
- Redis 7 (port 6379)
- Forge backend (port 8000)

## Configuration
Set environment variables in `docker-compose.yml` or `.env`.

## Production Considerations
- Use persistent volumes for PostgreSQL and Redis
- Set `FORGE_SECRET_KEY` to a secure random value
- Configure CORS origins for your domain
- Enable rate limiting for production
