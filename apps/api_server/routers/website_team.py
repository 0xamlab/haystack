"""Website/dashboard team management — Supabase-authenticated (companion to /account/devices).

A signed-in org admin lists members + seat usage, invites teammates by email+role, changes a
member's role, and removes members — from the accounts portal, without an engine API key. Authed
by the Supabase access_token → resolved to the caller's org via the shared website-identity path,
which only ever resolves an org the caller ADMINS, so these are admin-gated by construction and
strictly org-scoped. Seat-enforced per plan (solo plans can't add members; team caps at purchased
seats). Inert until SUPABASE_URL (+ GitHub App) is configured → 503.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.team_invite import InviteStatus, TeamInvite
from apps.api_server.models.user import User, UserRole, UserStatus
from apps.api_server.routers.team import INVITE_ACCEPT_BASE, INVITE_TTL_DAYS, _seats_used
from apps.api_server.services import resend_email, website_identity
from apps.api_server.services.team_seats import can_add_member, is_multi_seat, seat_limit

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["account"])
_ROLES = {"owner", "admin", "member", "viewer"}


class InviteBody(BaseModel):
    email: EmailStr
    role: str = "member"


class RoleBody(BaseModel):
    role: str


def _plan(org: Any) -> str:
    return org.plan.value if hasattr(org.plan, "value") else str(org.plan)


def _member(u: User) -> dict[str, str]:
    return {
        "user_id": str(u.id),
        "email": u.email,
        "name": u.name,
        "role": u.role.value if hasattr(u.role, "value") else str(u.role),
        "status": u.status.value if hasattr(u.status, "value") else str(u.status),
    }


async def _active_owner_count(db: AsyncSession, org_id: uuid.UUID) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(User).where(
                User.org_id == org_id, User.role == UserRole.OWNER, User.status == UserStatus.ACTIVE
            )
        )
        or 0
    )


@router.get("/account/orgs", summary="List every org the caller may act in (for the org picker)")
async def list_account_orgs(
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, object]:
    """Return the caller's eligible orgs (0, 1, or many). Someone who admins several picks one and
    sends it back as ``X-Org-Id`` on subsequent account calls. Never a 409 — an empty/single list is
    a valid answer here."""
    response.headers["Cache-Control"] = "no-store"
    orgs, _identity = await website_identity.list_eligible_orgs(authorization, db, redis)
    return {"orgs": orgs, "multiple": len(orgs) > 1}


@router.get("/account/team", summary="List team members + seat usage (website / Supabase auth)")
async def list_account_team(
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    org, _identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    result = await db.execute(select(User).where(User.org_id == org.id).order_by(User.created_at))
    members = [_member(u) for u in result.scalars().all()]
    used = await _seats_used(db, org.id)
    plan = _plan(org)
    return {
        "members": members,
        "plan": plan,
        "seats_used": used,
        "seat_limit": seat_limit(plan, org.seats),  # 0 = unlimited
        "can_invite": is_multi_seat(plan),
    }


@router.post("/account/team/invite", status_code=201, summary="Invite a team member (website / Supabase auth)")
async def invite_account_member(
    body: InviteBody,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    org, _identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    plan = _plan(org)
    if body.role not in _ROLES:
        raise HTTPException(status_code=422, detail=website_identity.error_body("invalid_role", f"Role must be one of {sorted(_ROLES)}."))
    if not is_multi_seat(plan):
        raise HTTPException(status_code=403, detail=website_identity.error_body("seats_not_available", "Your plan is single-seat. Upgrade to Team to invite members."))
    email = body.email.lower()
    if await db.scalar(select(User).where(User.org_id == org.id, func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail=website_identity.error_body("already_member", f"{email} is already on this team."))
    used = await _seats_used(db, org.id)
    if not can_add_member(plan, used, org.seats):
        raise HTTPException(status_code=403, detail=website_identity.error_body("seat_limit_reached", f"All {seat_limit(plan, org.seats)} seats are in use. Add seats or remove a member first."))

    invite = TeamInvite(
        org_id=org.id, email=email, role=body.role, token=secrets.token_urlsafe(32),
        status=InviteStatus.PENDING.value, expires_at=datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    await resend_email.send_team_invite_email(
        to=email, org_name=org.name, role=body.role, accept_url=f"{INVITE_ACCEPT_BASE}?token={invite.token}"
    )
    logger.info("account_team_invited", org_id=str(org.id), email=email, role=body.role)
    return {
        "invite_id": str(invite.id), "email": email, "role": body.role,
        "seats_used": used + 1, "seat_limit": seat_limit(plan, org.seats),
    }


@router.patch("/account/team/{user_id}/role", summary="Change a member's role (website / Supabase auth)")
async def update_account_member_role(
    user_id: uuid.UUID,
    body: RoleBody,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    org, _identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    if body.role not in _ROLES:
        raise HTTPException(status_code=422, detail=website_identity.error_body("invalid_role", f"Role must be one of {sorted(_ROLES)}."))
    u = await db.scalar(select(User).where(User.id == user_id, User.org_id == org.id))
    if u is None:
        raise HTTPException(status_code=404, detail=website_identity.error_body("member_not_found", "No such member on your team."))
    if u.role == UserRole.OWNER and body.role != "owner" and await _active_owner_count(db, org.id) <= 1:
        raise HTTPException(status_code=409, detail=website_identity.error_body("last_owner", "Cannot demote the last owner."))
    u.role = UserRole(body.role)
    await db.commit()
    return {"user_id": str(user_id), "role": body.role}


@router.delete("/account/team/{user_id}", status_code=204, summary="Remove a member (website / Supabase auth)")
async def remove_account_member(
    user_id: uuid.UUID,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> Response:
    org, _identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    u = await db.scalar(select(User).where(User.id == user_id, User.org_id == org.id))
    if u is None:
        raise HTTPException(status_code=404, detail=website_identity.error_body("member_not_found", "No such member on your team."))
    if u.role == UserRole.OWNER and await _active_owner_count(db, org.id) <= 1:
        raise HTTPException(status_code=409, detail=website_identity.error_body("last_owner", "Cannot remove the last owner."))
    await db.delete(u)
    await db.commit()
    logger.info("account_team_member_removed", org_id=str(org.id), user_id=str(user_id))
    return Response(status_code=204)
