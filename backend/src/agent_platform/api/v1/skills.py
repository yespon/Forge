"""Skill management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.database import get_db
from agent_platform.models.skill import Skill, SkillGrant, SkillVisibility
from agent_platform.services.skill_registry import SkillRegistry

router = APIRouter(prefix="/skills", tags=["skills"])


# --- Schemas ---

class SkillResponse(BaseModel):
    name: str
    version: str
    description: str
    visibility: str
    is_active: bool
    is_restricted: bool
    tools: list[str]


class SkillListResponse(BaseModel):
    items: list[SkillResponse]


class SkillDetailResponse(BaseModel):
    name: str
    version: str
    description: str
    visibility: str
    is_active: bool
    is_restricted: bool
    manifest: dict
    tools: list[str]
    restrictions: dict


class InstallRequest(BaseModel):
    session_id: UUID | None = None


class ConfigRequest(BaseModel):
    config: dict = Field(default_factory=dict)


# --- Helpers ---

def _skill_to_response(skill: Skill) -> SkillResponse:
    tools = []
    if skill.manifest:
        for t in skill.manifest.get("tools", []):
            tools.append(t if isinstance(t, str) else t.get("name", str(t)))
    return SkillResponse(
        name=skill.name,
        version=skill.version,
        description=skill.description or "",
        visibility=skill.visibility or "builtin",
        is_active=skill.is_active,
        is_restricted=skill.is_restricted,
        tools=tools,
    )


# --- Endpoints ---

@router.get("", response_model=SkillListResponse)
async def list_skills(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    visibility: str | None = None,
) -> SkillListResponse:
    """List available skills."""
    registry = SkillRegistry(db=db)

    # Builtin skills always visible
    items: list[SkillResponse] = []
    for skill in registry._builtin_skills.values():
        if visibility and skill.visibility != visibility:
            continue
        items.append(_skill_to_response(skill))

    # Also list DB-persisted skills visible to the user's org
    result = await db.execute(
        select(Skill).where(Skill.is_active == True)  # noqa: E712
    )
    for skill in result.scalars().all():
        if visibility and skill.visibility != visibility:
            continue
        if skill.visibility == SkillVisibility.ORG and skill.org_id != current_user.org_id:
            continue
        if skill.visibility == SkillVisibility.PRIVATE and skill.owner_id != current_user.id:
            continue
        # Deduplicate with builtin
        if skill.name not in registry._builtin_skills:
            items.append(_skill_to_response(skill))

    return SkillListResponse(items=items)


@router.get("/{skill_name}", response_model=SkillDetailResponse)
async def get_skill(
    current_user: CurrentUser,
    skill_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SkillDetailResponse:
    """Get detailed skill information."""
    registry = SkillRegistry(db=db)

    skill = registry.get_builtin_skill(skill_name)
    if not skill:
        result = await db.execute(
            select(Skill).where(Skill.name == skill_name, Skill.is_active == True)  # noqa: E712
        )
        skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    tools = []
    if skill.manifest:
        for t in skill.manifest.get("tools", []):
            tools.append(t if isinstance(t, str) else t.get("name", str(t)))

    return SkillDetailResponse(
        name=skill.name,
        version=skill.version,
        description=skill.description or "",
        visibility=skill.visibility or "builtin",
        is_active=skill.is_active,
        is_restricted=skill.is_restricted,
        manifest=skill.manifest or {},
        tools=tools,
        restrictions=skill.restrictions or {},
    )


@router.post("/{skill_name}/install", status_code=status.HTTP_200_OK)
async def install_skill(
    current_user: CurrentUser,
    skill_name: str,
    request: InstallRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Install/grant a skill to the user or session."""
    registry = SkillRegistry(db=db)

    skill = registry.get_builtin_skill(skill_name)
    if not skill:
        result = await db.execute(
            select(Skill).where(Skill.name == skill_name)
        )
        skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    if skill.is_restricted:
        # Check if user has admin role
        if current_user.role not in ("admin", "owner"):
            raise HTTPException(
                status_code=403,
                detail="Only admins can install restricted skills",
            )

    if request.session_id:
        await registry.grant_skill_to_session(
            skill_name=skill_name,
            session_id=str(request.session_id),
            user_id=str(current_user.id),
        )

    return {
        "status": "installed",
        "skill": skill_name,
        "session_id": str(request.session_id) if request.session_id else None,
    }


@router.post("/{skill_name}/uninstall", status_code=status.HTTP_200_OK)
async def uninstall_skill(
    current_user: CurrentUser,
    skill_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    session_id: UUID | None = None,
) -> dict:
    """Remove a skill grant."""
    if session_id:
        result = await db.execute(
            select(SkillGrant).where(
                SkillGrant.skill_name == skill_name,
                SkillGrant.session_id == str(session_id),
                SkillGrant.user_id == str(current_user.id),
            )
        )
        grant = result.scalar_one_or_none()
        if grant:
            await db.delete(grant)
            await db.commit()

    return {"status": "uninstalled", "skill": skill_name}


@router.post("/{skill_name}/config", status_code=status.HTTP_200_OK)
async def configure_skill(
    current_user: CurrentUser,
    skill_name: str,
    request: ConfigRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Update skill configuration."""
    result = await db.execute(
        select(Skill).where(Skill.name == skill_name)
    )
    skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found in database")

    # Merge config into manifest
    manifest = dict(skill.manifest or {})
    manifest["config"] = request.config
    skill.manifest = manifest
    await db.commit()

    return {"status": "configured", "skill": skill_name, "config": request.config}
