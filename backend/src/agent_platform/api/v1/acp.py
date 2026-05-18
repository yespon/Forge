"""ACP (Agent Communication Protocol) API endpoints.

Exposes ACP agent management and invocation via REST API.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agent_platform.auth.dependencies import get_current_user
from agent_platform.integration.acp_agent import (
    ACPAgentConfig,
    get_acp_manager,
    invoke_acp_agent,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/acp", tags=["acp"])


class ACPAgentResponse(BaseModel):
    name: str
    has_api: bool
    has_command: bool
    timeout: int


class ACPInvokeRequest(BaseModel):
    agent: str = Field(..., description="Name of the ACP agent to invoke")
    prompt: str = Field(..., min_length=1, max_length=50000, description="Task prompt")
    work_dir: Optional[str] = Field(None, description="Working directory")
    timeout: Optional[int] = Field(None, ge=1, le=3600, description="Timeout in seconds")


class ACPInvokeResponse(BaseModel):
    agent: str
    result: str
    success: bool


class ACPRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    timeout: int = Field(600, ge=1, le=7200)
    api_url: str = ""
    api_key: str = ""


@router.get("/agents", response_model=list[ACPAgentResponse])
async def list_acp_agents(user=Depends(get_current_user)):
    """List all registered ACP agents."""
    mgr = get_acp_manager()
    agents = []
    for name in mgr.list_agents():
        cfg = mgr.get(name)
        if cfg:
            agents.append(ACPAgentResponse(
                name=cfg.name,
                has_api=bool(cfg.api_url),
                has_command=bool(cfg.command),
                timeout=cfg.timeout,
            ))
    return agents


@router.post("/invoke", response_model=ACPInvokeResponse)
async def invoke_agent(req: ACPInvokeRequest, user=Depends(get_current_user)):
    """Invoke an ACP agent with a task prompt."""
    mgr = get_acp_manager()
    if not mgr.get(req.agent):
        raise HTTPException(status_code=404, detail=f"ACP agent '{req.agent}' not found")

    try:
        result = await invoke_acp_agent(
            agent_name=req.agent,
            prompt=req.prompt,
            work_dir=req.work_dir,
            timeout=req.timeout,
        )
        return ACPInvokeResponse(agent=req.agent, result=result, success=True)
    except Exception as e:
        logger.exception("ACP invoke failed for agent '%s'", req.agent)
        return ACPInvokeResponse(agent=req.agent, result=str(e), success=False)


@router.post("/agents", response_model=ACPAgentResponse, status_code=201)
async def register_acp_agent(req: ACPRegisterRequest, user=Depends(get_current_user)):
    """Register a new ACP agent."""
    if not req.command and not req.api_url:
        raise HTTPException(
            status_code=400,
            detail="Either 'command' or 'api_url' must be provided",
        )

    mgr = get_acp_manager()
    config = ACPAgentConfig(
        name=req.name,
        command=req.command,
        args=req.args,
        env=req.env,
        timeout=req.timeout,
        api_url=req.api_url,
        api_key=req.api_key,
    )
    mgr.register(config)

    return ACPAgentResponse(
        name=config.name,
        has_api=bool(config.api_url),
        has_command=bool(config.command),
        timeout=config.timeout,
    )
