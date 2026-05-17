# API Reference

## Base URL
All API endpoints are under `http://localhost:8000/api/v1`

## Authentication
Bearer JWT token required for all endpoints except `/auth/login` and `/auth/register`.

## Endpoints

### Auth
- `POST /auth/login` - Login with username/password
- `POST /auth/register` - Register new user
- `POST /auth/refresh` - Refresh access token
- `GET /auth/me` - Get current user

### Sessions
- `GET /sessions` - List sessions
- `POST /sessions` - Create session
- `GET /sessions/:id` - Get session
- `PATCH /sessions/:id` - Update session
- `DELETE /sessions/:id` - Delete session

### Chat
- `POST /sessions/:id/chat/completions` - Send message (streaming)
- `GET /sessions/:id/chat/history` - Get chat history

### Integration
- `GET /integration/status` - Integration health
- `GET /integration/models` - Available models
- `GET /integration/skills` - Available skills
- `GET /integration/memory` - Memory facts
- `GET /integration/mcp` - MCP server status
