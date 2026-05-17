# Forge × DeerFlow — Architecture Document

## Overview

Forge is an **Enterprise Multi-User Agent Runtime Platform** combining a full enterprise control layer (HITL approval, audit logging, multi-tenant RBAC) with DeerFlow's Super Agent Harness (multi-provider models, 14 middleware layers, SKILL.md skills, MCP, sub-agents, memory, IM channels).

## Architecture Diagram

```
                         

```
┌──────────────────────────────────────────────────────────────────┐
│                     Clients (Web / IM / API)                      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                    FastAPI (main.py)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Auth (JWT)   │  │  RBAC        │  │  Rate Limit           │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    API Routes                               │  │
│  │  auth users sessions chat tasks approvals skills sandbox    │  │
│  │  orgs webhooks connectors artifacts integration             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬───────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────┐
│                   Service Layer                                  │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│  │  HITL Rules     │  │  ToolGateway   │  │  TaskRuntime      │   │
│  │  Engine         │  │  (unified      │  │  (orchestration)  │   │
│  │  18 rules       │  │   execution)   │  │                   │   │
│  └────────────────┘  └────────────────┘  └──────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Integration Layer (DeerFlow)                   │  │
│  │  ┌─────────┐ ┌────────┐ ┌──────────┐ ┌────────────────┐   │  │
│  │  │ Models  │ │Memory  │ │Sub-agents│ │   MCP Transport  │   │  │
│  │  │ Factory │ │Manager │ │Executor  │ │  stdio/SSE/OAuth │   │  │
│  │  └─────────┘ └────────┘ └──────────┘ └────────────────┘   │  │
│  │  ┌─────────┐ ┌────────┐ ┌──────────┐ ┌────────────────┐   │  │
│  │  │ Skills  │ │  IM    │ │Middleware│ │    Tools        │   │  │
│  │  │ Loader  │ │Channels│ │   Chain  │ │ file/bash/web   │   │  │
│  │  └─────────┘ └────────┘ └──────────┘ └────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬───────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────┐
│                  Middleware Chain (execution order)               │
│                                                                  │
│  1. SandboxMiddleware          Create workspace dirs             │
│  2. DanglingToolCallMiddleware Patch missing ToolMessages        │
│  3. ToolErrorHandlingMiddleware Catch → ToolMessage conversion   │
│  4. SummarizationMiddleware    LLM summary when token threshold  │
│  5. TodoMiddleware             Inject plan-mode prompts          │
│  6. TitleMiddleware           LLM title gen (first turn)         │
│  7. MemoryMiddleware           Inject + extract memory facts     facts        │
│  8. ForgeHITLMiddleware        HITL rule check + approval        │
│  9. ForgeAuditMiddleware       Log to AuditLog table             │
│ 10. SubagentLimitMiddleware    Cap concurrent task_tool calls    │
│ 11. LoopDetectionMiddleware    Sliding window + hash detection   │
│ 12. ClarificationMiddleware    Intercept ask_clarification       │
└──────────────────────────────────────┬───────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────┐
│               Data Layer                                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  PostgreSQL  │  │    Redis     │  │   Docker Sandbox      │   │
│  │  (14 models) │  │  (task queue)│  │   (isolated exec)    │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Project Layout

```
forge/
├── ARCHITECTURE.md           ← This file
├── ROADMAP.md                ← Development roadmap
├── config.yaml               ← Unified configuration
├── extensions_config.json    ← MCP server configs
├── docker-compose.yml        ← PostgreSQL + Redis + app
├── skills/public/            ← 21 SKILL.md community skills
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic/              ← Database migrations
│   ├── tests/
│   │   └── test_integration.py  ← Integration tests (9 tests)
│   └── src/agent_platform/
│       ├── main.py           ← FastAPI entry
│       ├── config.py         ← Pydantic settings
│       ├── database.py       ← SQLAlchemy async engine
│       │
│       ├── api/v1/           ← REST API (12 routers)
│       │   ├── auth.py sessions.py users.py orgs.py
│       │   ├── chat.py tasks.py approvals.py skills.py
│       │   ├── sandbox.py connectors.py webhooks.py
│       │   ├── health.py integration.py ws.py
│       │   └── admin/audit.py
│       │
│       ├── models/           ← 14 SQLAlchemy models
│       ├── auth/             ← JWT + RBAC
│       ├── services/         ← Enterprise services
│       ├── integration/      ← ★ DeerFlow integration (33 files)
│       │   ├── __init__.py
│       │   ├── config.py types.py models.py
│       │   ├── agent_factory.py memory.py skills.py
│       │   ├── subagent_executor.py channels.py
│       │   ├── mcp.py mcp_transport.py mcp_oauth.py
│       │   ├── middleware/        ← 14 middleware files
│       │   └── tools/             ← 7 tool files
│       ├── sandbox/           ← Docker sandbox
│       └── workers/           ← Background workers
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── pages/             ← 8 pages
│       ├── components/        ← UI components
│       ├── stores/            ← Zustand
│       ├── types/             ← TypeScript types
│       └── lib/api.ts        ← API client
│
└── scripts/
    ├── compare.py             ← Forge vs DeerFlow comparison
    └── audit_integration.py   ← Integration module audit
```

## Key Capabilities

### Enterprise Layer (Forge Native)
| Capability | Description |
|-----------|-------------|
| HITL Approval | 18 security rules, 4 strategies (SINGLE/MULTI/ESCALATION/CONSENSUS) |
| Audit Logging | Full tool call audit trail (pre/post execution) |
| Multi-Tenant RBAC | 5 roles: platform_admin → org_admin → team_admin → developer → viewer |
| Async Task Queue | Redis Streams, 0-100% progress tracking, TaskEvent streaming |
| Feishu Cards | Interactive approval cards with actionable buttons |
| Rate Limiting | API-level rate limiting middleware |

### Agent Runtime Layer (DeerFlow Integration)
| Capability | Description |
|-----------|-------------|
| 14 Middleware | Sandbox → Clarification with runtime hooks |
| Multi-Provider Models | OpenAI / Anthropic / DeepSeek / Google / Ollama |
| 21 Skills | deep-research, data-analysis, image-generation, etc. |
| Memory | JSON persistence, keyword retrieval, context injection |
| Sub-Agents | Independent LLM agents, background exec, timeout/cancel |
| MCP | stdio subprocess + SSE, tool discovery/call, OAuth |
| IM Channels | Feishu, Slack, Telegram, DingTalk via MessageBus |
| Summarization | LLM-based context compression at token threshold |
| Loop Detection | Sliding window hash + tool frequency limits |
| Custom Agent | SOUL.md user-created agents |

## Data Flow: Agent Execution

```
1. User sends message → Session API
2. TaskRuntime creates Task (status: queued)
3. create_forge_agent():
   a. resolve_model() → create_chat_model() (5 providers)
   b. get_available_tools() → 7+ tools
   c. build_middleware_chain() → 14 middlewares
4. agent.astream(state):
   a. Sandbox: create workspace dir
   b. Memory: inject relevant facts
   c. DynamicContext: inject date/time
   d. LLM produces tool_calls
   e. LoopDetection: check sliding window
   f. HITL check → may pause for approval
   g. Execute tool (via ToolGateway)
   h. Audit log the call
   i. Memory: extract new facts
   j. Title gen (first turn)
   k. Check summarization threshold
5. Stream events back to client (SSE)
```

## Configuration

Two config sources merged at startup:

```yaml
# config.yaml (DeerFlow format)
models:
  - name: claude-sonnet-4-6
    use: langchain_anthropic:ChatAnthropic
    api_key: $ANTHROPIC_API_KEY

summarization:
  enabled: true
  trigger:
    - type: tokens
      value: 15000

loop_detection:
  enabled: true
  warn_threshold: 3
  hard_limit: 5

memory:
  enabled: true
```

```env
# .env (Forge format)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/forge
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=sk-ant-...
```

## Middleware Architecture

Each middleware implements one or more of these hooks:

```python
class AgentMiddleware:
    async def abefore_agent(self, state, runtime) -> dict | None: ...
    async def abefore_model(self, state, runtime) -> dict | None: ...
    async def aafter_model(self, state, runtime) -> dict | None: ...
    async def awrap_model_call(self, request, handler) -> ModelResponse: ...
    async def awrap_tool_call(self, request, handler) -> Any: ...
```

The `build_forge_middleware_chain()` function assembles them in order.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| FastAPI + LangGraph | Enterprise REST (auth/rbac/rate-limit) + agent graph |
| PostgreSQL only | Multi-tenancy + audit require proper SQL |
| Direct `mcp` library | Avoid langchain-mcp-adapters API churn |
| SKILL.md format | Markdown, no code deploy needed |
| JSON memory file | Simple dev; PostgreSQL-backed in production |
| Python 3.12 + poetry | Modern typing, reproducible builds |
