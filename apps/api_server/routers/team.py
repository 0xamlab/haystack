"""Team management endpoints — /v1/team, /v1/audit-logs, /v1/audit-logs/artifacts."""

import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.params import Param
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.middleware.rbac import require_role
from apps.api_server.models.user import User, UserRole, UserStatus
from apps.api_server.pagination import paginate_sequence
from apps.api_server.services.auth_service import AuthContext, invalidate_user_api_key_caches
from apps.api_server.services.workspace_scope import workspace_scope_clauses

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
    result: str  # success | failure
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None


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
    now = datetime.now(UTC)
    return [
        AuditLogEntry(
            id=str(uuid4()),
            timestamp=now,
            actor_email="owner@codna.ai",
            action="simulate",
            resource_type="simulation_run",
            resource_id=str(org_id),
            ip_address="203.0.113.10",
            result="success",
            metadata={"source": "demo"},
        ),
        AuditLogEntry(
            id=str(uuid4()),
            timestamp=now,
            actor_email="admin@codna.ai",
            action="invite_member",
            resource_type="team_member",
            resource_id=str(uuid4()),
            ip_address="203.0.113.11",
            result="success",
            metadata={"source": "demo"},
        ),
        AuditLogEntry(
            id=str(uuid4()),
            timestamp=now,
            actor_email="viewer@codna.ai",
            action="access_denied",
            resource_type="audit_log",
            resource_id=str(org_id),
            ip_address="203.0.113.12",
            result="failure",
            metadata={"source": "demo"},
        ),
    ]


def _parse_audit_metadata(raw_metadata: str | None) -> dict[str, Any] | None:
    if raw_metadata is None:
        return None
    try:
        parsed = json.loads(raw_metadata)
    except json.JSONDecodeError:
        return {"raw_metadata": raw_metadata}
    if isinstance(parsed, dict):
        return parsed
    return {"raw_metadata": parsed}


def _matches_audit_log_filters(
    *,
    actor_email: str,
    action: str,
    resource_type: str | None,
    result: str,
    metadata: dict[str, Any] | None,
    actor_email_filter: str | None,
    action_filter: str | None,
    resource_type_filter: str | None,
    result_filter: str | None,
    policy_snapshot_id: str | None,
    schema_snapshot_id: str | None,
    manifest_version: str | None,
    request_hash: str | None,
) -> bool:
    if actor_email_filter is not None and actor_email != actor_email_filter:
        return False
    if action_filter is not None and action != action_filter:
        return False
    if resource_type_filter is not None and resource_type != resource_type_filter:
        return False
    if result_filter is not None and result != result_filter:
        return False
    metadata_lookup = metadata or {}
    lineage_filters = {
        "policy_snapshot_id": policy_snapshot_id,
        "schema_snapshot_id": schema_snapshot_id,
        "manifest_version": manifest_version,
        "request_hash": request_hash,
    }
    for key, expected in lineage_filters.items():
        if expected is None:
            continue
        if metadata_lookup.get(key) != expected:
            return False
    return True


def _normalize_optional_query_string(value: str | Param | None) -> str | None:
    if isinstance(value, str) or value is None:
        return value
    default = getattr(value, "default", None)
    return default if isinstance(default, str) or default is None else str(default)


def _to_audit_log_entry_from_artifact(record: Any) -> AuditLogEntry:
    return AuditLogEntry(
        id=record.event_id,
        timestamp=record.created_at,
        actor_email=record.actor_email,
        action=record.action,
        resource_type=record.resource_type or "—",
        resource_id=record.resource_id,
        ip_address=record.ip_address,
        result=record.result,
        content_hash=record.content_hash,
        metadata=_parse_audit_metadata(record.metadata_json),
    )


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
    result = await db.execute(select(User).where(User.org_id == auth["org_id"]))
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
) -> dict[str, Any]:
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


async def _count_active_owners(db: AsyncSessionDep, org_id: UUID) -> int:
    """Number of active owners in the org (used to prevent dropping the last owner)."""
    result = await db.execute(
        select(User).where(
            User.org_id == org_id,
            User.role == UserRole.OWNER,
            User.status == UserStatus.ACTIVE,
        )
    )
    return len(result.scalars().all())


@router.patch("/v1/team/{user_id}/role", summary="Update a team member's role")
async def update_member_role(
    user_id: UUID,
    payload: RoleUpdateRequest,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> dict[str, Any]:
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
    # Block changing your own role (an admin must not self-escalate or self-demote).
    if auth["user_id"] is not None and auth["user_id"] == user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "self_role_change_forbidden",
                    "message": "You cannot change your own role.",
                }
            },
        )
    # Only an existing owner may grant the 'owner' role (prevents admin privilege escalation).
    if payload.role == UserRole.OWNER.value and auth["role"] != UserRole.OWNER.value:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "owner_grant_forbidden",
                    "message": "Only an owner can grant the 'owner' role.",
                }
            },
        )
    result = await db.execute(select(User).where(User.id == user_id, User.org_id == auth["org_id"]))
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

    # Refuse to demote the last active owner (zero-owner guard).
    demoting_owner = (
        user.role == UserRole.OWNER
        and user.status == UserStatus.ACTIVE
        and payload.role != UserRole.OWNER.value
    )
    if demoting_owner and await _count_active_owners(db, auth["org_id"]) <= 1:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "last_owner",
                    "message": "Cannot change the role of the last owner.",
                }
            },
        )

    user.role = UserRole(payload.role)
    await db.commit()
    return {"message": f"Role updated to '{payload.role}'.", "user_id": str(user_id)}


@router.delete("/v1/team/{user_id}", status_code=204, summary="Remove a team member")
async def remove_member(
    user_id: UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
    redis: Annotated[object, Depends(get_redis)],
) -> None:
    """Remove a user from the org."""
    result = await db.execute(select(User).where(User.id == user_id, User.org_id == auth["org_id"]))
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

    # Refuse to remove the last active owner (zero-owner guard).
    if (
        user.role == UserRole.OWNER
        and user.status == UserStatus.ACTIVE
        and await _count_active_owners(db, auth["org_id"]) <= 1
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "last_owner",
                    "message": "Cannot remove the last owner.",
                }
            },
        )

    user.status = UserStatus.SUSPENDED
    await db.commit()
    # Bust cached AuthContexts so the suspension takes effect immediately (the auth gate reads
    # status off the cached context) instead of after the auth cache TTL.
    await invalidate_user_api_key_caches(db, user_id, redis)


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
    actor_email: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    result: str | None = Query(default=None),
    policy_snapshot_id: str | None = Query(default=None),
    schema_snapshot_id: str | None = Query(default=None),
    manifest_version: str | None = Query(default=None),
    request_hash: str | None = Query(default=None),
) -> AuditLogResponse:
    """Return paginated audit log for the authenticated org from the audit_events table."""
    from sqlalchemy import desc, select

    from apps.api_server.models.audit_event import AuditEvent

    actor_email = _normalize_optional_query_string(actor_email)
    action = _normalize_optional_query_string(action)
    resource_type = _normalize_optional_query_string(resource_type)
    result = _normalize_optional_query_string(result)
    policy_snapshot_id = _normalize_optional_query_string(policy_snapshot_id)
    schema_snapshot_id = _normalize_optional_query_string(schema_snapshot_id)
    manifest_version = _normalize_optional_query_string(manifest_version)
    request_hash = _normalize_optional_query_string(request_hash)

    base_q = select(AuditEvent).where(*workspace_scope_clauses(AuditEvent, auth))
    all_events = ((await db.execute(base_q.order_by(desc(AuditEvent.created_at)))).scalars().all())

    if not all_events:
        demo_entries = _generate_demo_audit_log(auth["org_id"])
        filtered_demo_entries = [
            entry
            for entry in demo_entries
            if _matches_audit_log_filters(
                actor_email=entry.actor_email,
                action=entry.action,
                resource_type=entry.resource_type,
                result=entry.result,
                metadata=entry.metadata,
                actor_email_filter=actor_email,
                action_filter=action,
                resource_type_filter=resource_type,
                result_filter=result,
                policy_snapshot_id=policy_snapshot_id,
                schema_snapshot_id=schema_snapshot_id,
                manifest_version=manifest_version,
                request_hash=request_hash,
            )
        ]
        total = len(filtered_demo_entries)
        offset = (page - 1) * limit
        return AuditLogResponse(
            entries=filtered_demo_entries[offset : offset + limit],
            total=total,
            page=page,
            limit=limit,
            pages=max(1, (total + limit - 1) // limit),
        )

    filtered_entries = [
        AuditLogEntry(
            id=str(e.id),
            timestamp=e.created_at,
            actor_email=e.actor_email,
            action=e.action,
            resource_type=e.resource_type or "—",
            resource_id=e.resource_id,
            ip_address=e.ip_address,
            result=e.result,
            content_hash=None,
            metadata=_parse_audit_metadata(e.metadata_json),
        )
        for e in all_events
        if _matches_audit_log_filters(
            actor_email=e.actor_email,
            action=e.action,
            resource_type=e.resource_type,
            result=e.result,
            metadata=_parse_audit_metadata(e.metadata_json),
            actor_email_filter=actor_email,
            action_filter=action,
            resource_type_filter=resource_type,
            result_filter=result,
            policy_snapshot_id=policy_snapshot_id,
            schema_snapshot_id=schema_snapshot_id,
            manifest_version=manifest_version,
            request_hash=request_hash,
        )
    ]
    total = len(filtered_entries)
    offset = (page - 1) * limit
    return AuditLogResponse(
        entries=filtered_entries[offset : offset + limit],
        total=total,
        page=page,
        limit=limit,
        pages=max(1, (total + limit - 1) // limit),
    )


@router.get(
    "/v1/audit-logs/artifacts",
    response_model=AuditLogResponse,
    summary="Paginated audit log artifacts from Parquet runtime storage",
)
async def get_audit_log_artifacts(
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    actor_email: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    result: str | None = Query(default=None),
    policy_snapshot_id: str | None = Query(default=None),
    schema_snapshot_id: str | None = Query(default=None),
    manifest_version: str | None = Query(default=None),
    request_hash: str | None = Query(default=None),
    content_hash: str | None = Query(default=None),
) -> AuditLogResponse:
    from apps.api_server.services.audit_service import query_audit_event_artifacts

    # SECURITY (#7): the Parquet audit artifacts now carry workspace_id. A workspace-scoped
    # caller sees ONLY its own workspace's events; an unscoped (org-wide) platform call sees
    # all (incl. pre-#7 legacy records, which are workspace_id=None / org-wide).
    _ws = auth.get("workspace_id")
    workspace_id = str(_ws) if _ws else None

    actor_email = _normalize_optional_query_string(actor_email)
    action = _normalize_optional_query_string(action)
    resource_type = _normalize_optional_query_string(resource_type)
    result = _normalize_optional_query_string(result)
    policy_snapshot_id = _normalize_optional_query_string(policy_snapshot_id)
    schema_snapshot_id = _normalize_optional_query_string(schema_snapshot_id)
    manifest_version = _normalize_optional_query_string(manifest_version)
    request_hash = _normalize_optional_query_string(request_hash)
    content_hash = _normalize_optional_query_string(content_hash)

    records = query_audit_event_artifacts(
        org_id=str(auth["org_id"]),
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        result=result,
        policy_snapshot_id=policy_snapshot_id,
        schema_snapshot_id=schema_snapshot_id,
        manifest_version=manifest_version,
        request_hash=request_hash,
        content_hash=content_hash,
        workspace_id=workspace_id,
    )
    total = len(records)
    offset = (page - 1) * limit
    entries = [_to_audit_log_entry_from_artifact(record) for record in records[offset : offset + limit]]
    return AuditLogResponse(
        entries=entries,
        total=total,
        page=page,
        limit=limit,
        pages=max(1, (total + limit - 1) // limit),
    )
