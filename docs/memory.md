# Memory System

The memory system stores and retrieves facts from conversation context.

## Storage
- **Development**: JSON file (`~/.deer-flow/memory.json`)
- **Production**: PostgreSQL-backed (planned)

## API
- `GET /api/v1/integration/memory` - List memories
- `GET /api/v1/integration/memory?query=keyword` - Search memories

## How it works
1. **MemoryMiddleware** injects relevant facts before each model call
2. After each turn, new facts are extracted and stored
3. Facts are scored by keyword relevance for retrieval
