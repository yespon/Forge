"""API routes for Forge × DeerFlow integration features.

Exposes new capabilities:
- GET /api/v1/integration/models - Available LLM models
- GET /api/v1/integration/skills - Available skills
- GET /api/v1/integration/memory - Memory facts
- GET /api/v1/integration/mcp - MCP server status
- GET /api/v1/integration/status - Integration status overview
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import get_current_user
from agent_platform.database import get_db
from agent_platform.integration import (
    get_integration_config,
    get_mcp_manager,
    get_memory_manager,
    get_skill_manager,
    get_available_models,
)
from agent_platform.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integration", tags=["integration"])


@router.get("/models")
async def list_models(
    current_user: User = Depends(get_current_user),
):
    """List all available LLM models with their capabilities."""
    models = get_available_models()
    return {
        "models": models,
        "total": len(models),
    }


@router.get("/skills")
async def list_skills(
    current_user: User = Depends(get_current_user),
):
    """List all available skills."""
    try:
        sm = get_skill_manager()
        skills = [
            {
                "name": s.name,
                "description": s.description,
                "is_active": s.is_active,
                "has_instructions": bool(s.instructions),
            }
            for s in sm.all_skills
        ]
        return {
            "skills": skills,
            "total": len(skills),
            "enabled": [s.name for s in sm.enabled_skills],
        }
    except Exception as e:
        logger.warning(f"Failed to list skills: {e}")
        return {"skills": [], "total": 0, "error": str(e)}


@router.get("/memory")
async def get_memory(
    query: Optional[str] = Query(None, description="Search query for relevant facts"),
    current_user: User = Depends(get_current_user),
):
    """Get stored memory facts."""
    mm = get_memory_manager()
    if query:
        facts = mm.store.get_relevant_facts(query)
    else:
        facts = mm.store.get_all_facts()

    return {
        "facts": [
            {
                "content": f.content,
                "category": f.category,
                "confidence": f.confidence,
                "timestamp": f.timestamp,
            }
            for f in facts
        ],
        "total": len(facts),
    }


@router.get("/mcp")
async def get_mcp_status(
    current_user: User = Depends(get_current_user),
):
    """Get MCP server status."""
    mcp = get_mcp_manager()
    servers = [
        {
            "name": s.name,
            "enabled": s.enabled,
            "type": s.type,
        }
        for s in mcp.get_enabled_servers()
    ]
    return {
        "servers": servers,
        "total": len(servers),
    }


@router.get("/status")
async def get_integration_status(
    current_user: User = Depends(get_current_user),
):
    """Get overall integration status overview."""
    cfg = get_integration_config()

    return {
        "version": "0.1.0",
        "models": {
            "available": len(cfg.models),
            "default": cfg.default_model_name,
        },
        "features": {
            "summarization": cfg.summarization.enabled,
            "memory": cfg.memory.enabled,
            "loop_detection": cfg.loop_detection.enabled,
            "tool_search": cfg.tool_search.enabled,
            "title_generation": cfg.title.enabled,
            "token_usage": cfg.token_usage.enabled,
        },
        "database": {
            "backend": cfg.database.backend,
        },
        "skills_path": cfg.skills.path,
    }