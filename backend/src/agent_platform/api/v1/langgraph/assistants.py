"""LangGraph-compatible Assistants API.

Implements the LangGraph Platform assistants endpoints:
- GET  /assistants          — List available assistants (graphs)
- GET  /assistants/{id}     — Get assistant details
- GET  /assistants/search   — Search assistants
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from agent_platform.auth.dependencies import get_current_user

router = APIRouter(prefix="/assistants", tags=["langgraph-assistants"])


# --- Response schemas ---


class AssistantResponse(BaseModel):
    assistant_id: str
    graph_id: str
    name: str
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


# --- Built-in assistants registry ---


def _get_builtin_assistants() -> list[AssistantResponse]:
    """Return the list of built-in assistants."""
    return [
        AssistantResponse(
            assistant_id="lead_agent",
            graph_id="lead_agent",
            name="Forge Lead Agent",
            description="Primary multi-tool agent with full DeerFlow capabilities",
            metadata={"provider": "forge", "category": "general"},
            config={
                "recursion_limit": 100,
                "thinking_enabled": True,
                "subagent_enabled": False,
            },
        ),
        AssistantResponse(
            assistant_id="planner",
            graph_id="lead_agent",
            name="Forge Planner",
            description="Plan-mode agent for structured task decomposition",
            metadata={"provider": "forge", "category": "planning"},
            config={
                "recursion_limit": 100,
                "thinking_enabled": True,
                "is_plan_mode": True,
            },
        ),
        AssistantResponse(
            assistant_id="researcher",
            graph_id="lead_agent",
            name="Forge Researcher",
            description="Research-focused agent with web search and deep analysis",
            metadata={"provider": "forge", "category": "research"},
            config={
                "recursion_limit": 150,
                "thinking_enabled": True,
                "subagent_enabled": True,
            },
        ),
    ]


# --- Endpoints ---


@router.get("", response_model=list[AssistantResponse])
async def list_assistants(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
):
    """List available assistants."""
    assistants = _get_builtin_assistants()
    return assistants[offset : offset + limit]


@router.get("/search", response_model=list[AssistantResponse])
async def search_assistants(
    query: Optional[str] = None,
    metadata: Optional[str] = None,
    user=Depends(get_current_user),
):
    """Search assistants by name or metadata."""
    assistants = _get_builtin_assistants()
    if query:
        q = query.lower()
        assistants = [a for a in assistants if q in a.name.lower() or q in a.description.lower()]
    return assistants


@router.get("/{assistant_id}", response_model=AssistantResponse)
async def get_assistant(
    assistant_id: str,
    user=Depends(get_current_user),
):
    """Get a specific assistant."""
    for assistant in _get_builtin_assistants():
        if assistant.assistant_id == assistant_id:
            return assistant
    raise HTTPException(status_code=404, detail=f"Assistant '{assistant_id}' not found")
