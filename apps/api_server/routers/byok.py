"""Top-level ``/byok`` endpoint for the codna website's Bring-Your-Own-Key card.

Distinct front door from ``/v1/provider-keys`` (which is codna-API-key authenticated, for the
SDK/CLI). This one is authenticated by a **Supabase access_token** (the website's GitHub-OAuth
session), maps the caller's GitHub identity to their engine org (personal install, or org-admin via
the App's installation token), and delegates to the SAME encrypted tenant-key store. Both doors
write ``tenant_provider_keys``; only the auth + org-resolution differ.

The site posts ``{"provider": "anthropic", "key": "sk-ant-…"}`` with ``Authorization: Bearer <jwt>``
from a Next.js server action (server→server, so CORS does not apply). The key is write-only: stored
encrypted, never returned. Inert until ``SUPABASE_URL`` + the GitHub App are configured (503).
"""
from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_redis
from apps.api_server.services import tenant_key_management as tk_mgmt
from apps.api_server.services import website_identity

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["BYOK"])


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


# The website BYOK card manages the caller's own LLM PROVIDER key (Anthropic today). The reserved
# engine key — the org's codna engine credential — is NOT manageable from this public surface; only
# the API-key-authenticated /v1/provider-keys (admin RBAC) may touch it. Reject it explicitly so a
# crafted request can't clobber the engine key via the Supabase-auth path.
_ENGINE_LABELS = frozenset({"engine", "algenta_engine"})


def _check_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized in _ENGINE_LABELS:
        raise HTTPException(
            status_code=400,
            detail=_err("unsupported_backend", "The engine key cannot be managed here."),
        )
    return normalized


class ByokRequest(BaseModel):
    """Mirrors the website's payload shape (``provider``/``key``), distinct from the SDK's
    ``backend``/``api_key``. The website only sends ``anthropic`` today; other supported backends
    are accepted for forward-compatibility and validated downstream by the key store."""

    provider: str = Field(default="anthropic", min_length=1, max_length=64)
    key: str = Field(min_length=1)


async def _verify_and_resolve(
    authorization: str | None, db: AsyncSession, redis: Any
) -> tuple[Any, dict[str, Any]]:
    """Verify the Supabase JWT + resolve the caller's engine org (shared website identity path).

    Note: an inherent (millisecond) TOCTOU window exists between this org-admin resolution and the
    key write below — a GitHub admin revoked mid-request would still complete this one call. The
    blast radius is one's-own-org BYOK key (re-addable, audited), so we accept it rather than take a
    distributed lock; the short Redis cache also bounds re-checks.
    """
    return await website_identity.verify_and_resolve_org(authorization, db, redis)


def _actor_email(identity: dict[str, Any]) -> str:
    return identity.get("email") or f"github:{identity['github_login']}"


@router.post(
    "/byok",
    status_code=204,
    response_model=None,  # 204 has no body; explicit (future annotations make -> None NoneType)
    summary="Set the caller's per-org BYOK key (website / Supabase-authenticated; write-only)",
)
async def set_byok(
    payload: ByokRequest,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> None:
    response.headers["Cache-Control"] = "no-store"  # never cache a key-management mutation
    provider = _check_provider(payload.provider)
    org, identity = await _verify_and_resolve(authorization, db, redis)
    try:
        await tk_mgmt.set_org_key(
            db,
            org_id=org.id,
            api_backend=provider,
            api_key=payload.key,
            actor_email=_actor_email(identity),
        )
    except tk_mgmt.TenantKeyError as exc:
        status_code = 409 if exc.code == "encryption_key_required" else 400
        raise HTTPException(status_code=status_code, detail=_err(exc.code, str(exc))) from exc


@router.delete(
    "/byok",
    status_code=204,
    response_model=None,  # 204 has no body; explicit (future annotations make -> None NoneType)
    summary="Remove the caller's per-org BYOK key (idempotent)",
)
async def delete_byok(
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    provider: str = "anthropic",
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> None:
    response.headers["Cache-Control"] = "no-store"  # never cache a key-management mutation
    provider = _check_provider(provider)
    org, identity = await _verify_and_resolve(authorization, db, redis)
    try:
        await tk_mgmt.delete_org_key(
            db, org_id=org.id, api_backend=provider, actor_email=_actor_email(identity)
        )
    except tk_mgmt.TenantKeyError as exc:
        raise HTTPException(status_code=400, detail=_err(exc.code, str(exc))) from exc
    # Idempotent: 204 whether or not a key existed (the site's "remove" need not 404).
