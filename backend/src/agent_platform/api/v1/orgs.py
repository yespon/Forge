"""Organization management endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.auth.rbac import require_permission
from agent_platform.database import get_db
from agent_platform.models.org import Org, Team
from agent_platform.models.user import User, UserRole

router = APIRouter(prefix="/orgs", tags=["organizations"])


# Schemas
class OrgBase(BaseModel):
    """Base organization schema."""

    name: str = Field(..., min_length=1, max_length=100)


class OrgCreate(OrgBase):
    """Create organization request."""

    slug: str | None = Field(None, pattern=r'^[\w-]+$', max_length=50)


class OrgUpdate(BaseModel):
    """Update organization request."""

    name: str | None = Field(None, min_length=1, max_length=100)
    settings: dict | None = None
    quota: dict | None = None
    status: str | None = Field(None, pattern=r'^(active|inactive|suspended)$')


class OrgResponse(BaseModel):
    """Organization response."""

    id: str
    name: str
    slug: str
    status: str
    settings: dict
    quota: dict
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class OrgListResponse(BaseModel):
    """Organization list response."""

    items: list[OrgResponse]
    total: int
    page: int
    page_size: int


class TeamBase(BaseModel):
    """Base team schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class TeamCreate(TeamBase):
    """Create team request."""

    slug: str | None = Field(None, pattern=r'^[\w-]+$', max_length=50)


class TeamUpdate(BaseModel):
    """Update team request."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    settings: dict | None = None


class TeamResponse(BaseModel):
    """Team response."""

    id: str
    org_id: str
    name: str
    slug: str
    description: str | None
    settings: dict
    created_at: str

    class Config:
        from_attributes = True


class TeamListResponse(BaseModel):
    """Team list response."""

    items: list[TeamResponse]
    total: int
    page: int
    page_size: int


# Organization Endpoints
@router.get("", response_model=OrgListResponse)
@require_permission("org:read")
async def list_orgs(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrgListResponse:
    """List organizations.

    Non-platform admins can only see their own organization.
    """
    if current_user.role != UserRole.PLATFORM_ADMIN:
        # Return only user's org
        result = await db.execute(
            select(Org).where(
                Org.id == current_user.org_id,
                Org.deleted_at.is_(None),
            )
        )
        org = result.scalar_one_or_none()
        items = [OrgResponse.model_validate(org)] if org else []
        return OrgListResponse(
            items=items,
            total=len(items),
            page=1,
            page_size=page_size,
        )

    # Platform admins can see all orgs
    count_result = await db.execute(
        select(Org).where(Org.deleted_at.is_(None))
    )
    total = len(count_result.scalars().all())

    result = await db.execute(
        select(Org)
        .where(Org.deleted_at.is_(None))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orgs = result.scalars().all()

    return OrgListResponse(
        items=[OrgResponse.model_validate(o) for o in orgs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
@require_permission("org:manage")
async def create_org(
    current_user: CurrentUser,
    request: OrgCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgResponse:
    """Create a new organization."""
    import re

    # Generate slug if not provided
    slug = request.slug or re.sub(r'[^\w]+', '-', request.name.lower()).strip('-')

    # Check slug uniqueness
    result = await db.execute(select(Org).where(Org.slug == slug))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        )

    org = Org(
        name=request.name,
        slug=slug,
        status="active",
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    return OrgResponse.model_validate(org)


@router.get("/current", response_model=OrgResponse)
async def get_current_org(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgResponse:
    """Get current user's organization."""
    result = await db.execute(
        select(Org).where(
            Org.id == current_user.org_id,
            Org.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return OrgResponse.model_validate(org)


@router.get("/{org_id}", response_model=OrgResponse)
@require_permission("org:read")
async def get_org(
    current_user: CurrentUser,
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgResponse:
    """Get organization by ID."""
    result = await db.execute(
        select(Org).where(
            Org.id == org_id,
            Org.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Permission check
    if (
        current_user.role != UserRole.PLATFORM_ADMIN
        and org.id != current_user.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other organizations",
        )

    return OrgResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrgResponse)
@require_permission("org:update")
async def update_org(
    current_user: CurrentUser,
    org_id: UUID,
    request: OrgUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgResponse:
    """Update organization."""
    result = await db.execute(
        select(Org).where(
            Org.id == org_id,
            Org.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Permission check
    if (
        current_user.role != UserRole.PLATFORM_ADMIN
        and org.id != current_user.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify other organizations",
        )

    # Update fields
    if request.name:
        org.name = request.name

    if request.settings is not None:
        org.settings.update(request.settings)

    if request.quota is not None:
        org.quota.update(request.quota)

    if request.status:
        org.status = request.status

    await db.commit()
    await db.refresh(org)

    return OrgResponse.model_validate(org)


# Team Endpoints
@router.get("/{org_id}/teams", response_model=TeamListResponse)
@require_permission("team:read")
async def list_teams(
    current_user: CurrentUser,
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TeamListResponse:
    """List teams in an organization."""
    # Permission check
    if (
        current_user.role != UserRole.PLATFORM_ADMIN
        and org_id != current_user.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access teams from other organizations",
        )

    # Count teams
    count_result = await db.execute(
        select(Team).where(
            Team.org_id == org_id,
        )
    )
    total = len(count_result.scalars().all())

    # Get teams
    result = await db.execute(
        select(Team)
        .where(Team.org_id == org_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    teams = result.scalars().all()

    return TeamListResponse(
        items=[TeamResponse.model_validate(t) for t in teams],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{org_id}/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
@require_permission("team:create")
async def create_team(
    current_user: CurrentUser,
    org_id: UUID,
    request: TeamCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    """Create a new team."""
    import re

    # Permission check
    if (
        current_user.role != UserRole.PLATFORM_ADMIN
        and org_id != current_user.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create teams in other organizations",
        )

    # Generate slug if not provided
    slug = request.slug or re.sub(r'[^\w]+', '-', request.name.lower()).strip('-')

    # Check slug uniqueness within org
    result = await db.execute(
        select(Team).where(
            Team.org_id == org_id,
            Team.slug == slug,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Team slug already exists in this organization",
        )

    team = Team(
        org_id=org_id,
        name=request.name,
        slug=slug,
        description=request.description,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)

    return TeamResponse.model_validate(team)


@router.get("/{org_id}/teams/{team_id}", response_model=TeamResponse)
@require_permission("team:read")
async def get_team(
    current_user: CurrentUser,
    org_id: UUID,
    team_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    """Get team by ID."""
    result = await db.execute(
        select(Team).where(
            Team.id == team_id,
            Team.org_id == org_id,
        )
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Permission check
    if (
        current_user.role != UserRole.PLATFORM_ADMIN
        and team.org_id != current_user.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access teams from other organizations",
        )

    return TeamResponse.model_validate(team)


@router.patch("/{org_id}/teams/{team_id}", response_model=TeamResponse)
@require_permission("team:update")
async def update_team(
    current_user: CurrentUser,
    org_id: UUID,
    team_id: UUID,
    request: TeamUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    """Update team."""
    result = await db.execute(
        select(Team).where(
            Team.id == team_id,
            Team.org_id == org_id,
        )
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Permission check
    if (
        current_user.role != UserRole.PLATFORM_ADMIN
        and team.org_id != current_user.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify teams from other organizations",
        )

    # Update fields
    if request.name:
        team.name = request.name

    if request.description is not None:
        team.description = request.description

    if request.settings is not None:
        team.settings.update(request.settings)

    await db.commit()
    await db.refresh(team)

    return TeamResponse.model_validate(team)


@router.delete("/{org_id}/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("team:delete")
async def delete_team(
    current_user: CurrentUser,
    org_id: UUID,
    team_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a team."""
    result = await db.execute(
        select(Team).where(
            Team.id == team_id,
            Team.org_id == org_id,
        )
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Permission check
    if (
        current_user.role != UserRole.PLATFORM_ADMIN
        and team.org_id != current_user.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete teams from other organizations",
        )

    await db.delete(team)
    await db.commit()
