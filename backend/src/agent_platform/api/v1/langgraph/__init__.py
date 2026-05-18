"""LangGraph Platform-compatible API routes.

Provides endpoints compatible with:
- LangGraph Studio
- LangGraph Client SDK (langgraph-sdk)
- DeerFlow frontend

Routes mirror the LangGraph Platform API spec:
  /api/langgraph/threads/*
  /api/langgraph/runs/*
  /api/langgraph/assistants/*
"""

from agent_platform.api.v1.langgraph.threads import router as threads_router
from agent_platform.api.v1.langgraph.runs import router as runs_router
from agent_platform.api.v1.langgraph.assistants import router as assistants_router
from agent_platform.api.v1.langgraph.auth import router as auth_router

__all__ = ["threads_router", "runs_router", "assistants_router", "auth_router"]
