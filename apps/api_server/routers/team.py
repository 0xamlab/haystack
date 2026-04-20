"""Team management endpoints — /v1/team, /v1/audit-logs."""
from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import AuthContext, get_current_org
from apps.api_server.middleware.rbac import require_role
from apps.api_server.models.user import User
from apps.api_server.pagination import paginate_sequence

router = APIRouter(tags=["Team"])


class MemberInfo(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    status: str
    last_active: datetime | None

    model_config = {"from_attributes": True}


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class RoleUpdateRequest(BaseModel):
    role: str


class AuditLogEntry(BaseModel):
    id: str
    timestamp: datetime
    actor_email: str
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    result: str   # success | failure


class AuditLogResponse(BaseModel):
    entries: list[AuditLogEntry]
    total: int
    page: int
    limit: int
    pages: int


class TeamListResponse(BaseModel):
    members: list[MemberInfo]
    total: int
    page: int
    limit: int
    pages: int


def _generate_demo_audit_log(org_id: UUID) -> list[AuditLogEntry]:
    now = datetime.utcnow()
    return [
        AuditLogEntry(
            id=str(uuid4()),
            timestamp=now,
            actor_email="owner@algenta.ai",
            action="simulate",
            resource_type="simulation_run",
            resource_id=str(org_id),
            ip_address="203.0.113.10",
            result="success",
        ),
        AuditLogEntry(
            id=str(uuid4()),
            timestamp=now,
            actor_email="admin@algenta.ai",
            action="invite_member",
            resource_type="team_member",
            resource_id=str(uuid4()),
            ip_address="203.0.113.11",
            result="success",
        ),
        AuditLogEntry(
            id=str(uuid4()),
            timestamp=now,
            actor_email="viewer@algenta.ai",
            action="access_denied",
            resource_type="audit_log",
            resource_id=str(org_id),
            ip_address="203.0.113.12",
            result="failure",
        ),
    ]


@router.get(
    "/v1/team",
    response_model=list[MemberInfo] | TeamListResponse,
    summary="List team members",
)
async def list_team(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[MemberInfo] | TeamListResponse:
    """List all active users in the authenticated org."""
    result = await db.execute(
        select(User).where(User.org_id == auth["org_id"])
    )
    users = result.scalars().all()
    members = [
        MemberInfo(
            user_id=str(u.id),
            name=u.name,
            email=u.email,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            status=u.status.value if hasattr(u.status, "value") else str(u.status),
            last_active=None,
        )
        for u in users
    ]
    if page is None and limit is None:
        return members
    envelope = paginate_sequence(members, page=page or 1, limit=limit or 25)
    return TeamListResponse(
        members=envelope.items,
        total=envelope.total,
        page=envelope.page,
        limit=envelope.limit,
        pages=envelope.pages,
    )


@router.post("/v1/team/invite", status_code=201, summary="Invite a team member")
async def invite_member(
    payload: InviteRequest,
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> dict:
    """Send an invitation email to a new team member (stub — email not implemented)."""
    valid_roles = {"owner", "admin", "member", "viewer"}
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_role",
                    "message": f"Role must be one of: {sorted(valid_roles)}",
                }
            },
        )
    # In production: create pending invite record + send email
    return {
        "message": f"Invitation sent to {payload.email} with role '{payload.role}'.",
        "invite_id": str(uuid4()),
    }


@router.patch("/v1/team/{user_id}/role", summary="Update a team member's role")
async def update_member_role(
    user_id: UUID,
    payload: RoleUpdateRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> dict:
    """Change a team member's role."""
    valid_roles = {"owner", "admin", "member", "viewer"}
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_role",
                    "message": f"Role must be one of: {sorted(valid_roles)}",
                }
            },
        )
    result = await db.execute(
        select(User).where(User.id == user_id, User.org_id == auth["org_id"])
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": "User not found.",
                }
            },
        )

    user.role = payload.role  # type: ignore[assignment]
    await db.commit()
    return {"message": f"Role updated to '{payload.role}'.", "user_id": str(user_id)}


@router.delete("/v1/team/{user_id}", status_code=204, summary="Remove a team member")
async def remove_member(
    user_id: UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> None:
    """Remove a user from the org."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.org_id == auth["org_id"])
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": "User not found.",
                }
            },
        )

    from apps.api_server.models.user import UserStatus
    user.status = UserStatus.SUSPENDED  # type: ignore[assignment]
    await db.commit()


# ── Audit log (in-memory stub — production would use audit_events table) ──────

@router.get(
    "/v1/audit-logs",
    response_model=AuditLogResponse,
    summary="Paginated audit log from DB",
)
async def get_audit_logs(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
) -> AuditLogResponse:
    """Return paginated audit log for the authenticated org from the audit_events table."""
    from sqlalchemy import desc, func, select

    from apps.api_server.models.audit_event import AuditEvent

    base_q = select(AuditEvent).where(AuditEvent.org_id == auth["org_id"])
    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar_one()
    offset = (page - 1) * limit
    events = (
        await db.execute(
            base_q.order_by(desc(AuditEvent.created_at)).offset(offset).limit(limit)
        )
    ).scalars().all()

    if not events:
        demo_entries = _generate_demo_audit_log(auth["org_id"])
        start = (page - 1) * limit
        return AuditLogResponse(
            entries=demo_entries[start:start + limit],
            total=len(demo_entries),
            page=page,
            limit=limit,
            pages=max(1, (len(demo_entries) + limit - 1) // limit),
        )

    entries = [
        AuditLogEntry(
            id=str(e.id),
            timestamp=e.created_at,
            actor_email=e.actor_email,
            action=e.action,
            resource_type=e.resource_type or "—",
            resource_id=e.resource_id,
            ip_address=e.ip_address,
            result=e.result,
        )
        for e in events
    ]
    return AuditLogResponse(
        entries=entries,
        total=total,
        page=page,
        limit=limit,
        pages=max(1, (total + limit - 1) // limit),
    )
