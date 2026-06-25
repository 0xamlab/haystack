"""Website/dashboard self-service device management — Supabase-authenticated.

The companion to ``/byok``: the subscription dashboard (codna-ai-site account page) lets a signed-in
user SEE the devices/seats on their plan and REVOKE one to free a seat — without an engine API key.
Authenticated by the user's Supabase access_token (the site's OAuth session), resolved to the
caller's engine org via the shared website-identity path; all queries are org-scoped, so a user can
only ever see and revoke their OWN org's devices.

Distinct from the SDK's ``/v1/device/*`` (codna-API-key + per-device binding, for runtime machines):
this surface is account management, not runtime, so it carries no device-binding requirement. Inert
until ``SUPABASE_URL`` (+ the GitHub App) is configured → 503.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_redis
from apps.api_server.services import website_identity
from apps.api_server.services.device_service import list_devices_with_activity, revoke_device

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["account"])


@router.get(
    "/account/devices",
    summary="List the signed-in user's devices + seat usage (website / Supabase auth)",
    description=(
        "Returns the caller's org devices, each marked `active` (heartbeating within the seat "
        "window) or idle, plus a seat summary. Powers the subscription dashboard's device list."
    ),
)
async def list_account_devices(
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"  # private account data — never cache
    org, _identity = await website_identity.verify_and_resolve_org(authorization, db, redis)
    return await list_devices_with_activity(org.id, db)


@router.delete(
    "/account/devices/{registration_id}",
    summary="Revoke one of the signed-in user's devices (frees a seat)",
    description=(
        "Self-service seat management: revoke a device you no longer use to free its seat. "
        "Org-scoped — you can only revoke devices on your own plan. The device loses access on its "
        "next license refresh."
    ),
)
async def revoke_account_device(
    registration_id: uuid.UUID,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    org, identity = await website_identity.verify_and_resolve_org(authorization, db, redis)
    found = await revoke_device(org.id, registration_id, db)
    if not found:
        # Org-scoped: a registration that isn't in the caller's org is indistinguishable from one
        # that doesn't exist — never confirm another tenant's device id.
        raise HTTPException(
            status_code=404,
            detail=website_identity.error_body(
                "device_not_found", "No such device on your account."
            ),
        )
    logger.info(
        "account_device_revoked",
        registration_id=str(registration_id),
        org_id=str(org.id),
        actor=identity.get("github_login"),
    )
    return {"revoked": True, "registration_id": str(registration_id)}
