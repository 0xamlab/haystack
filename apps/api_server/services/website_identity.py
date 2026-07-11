"""Shared website/dashboard identity: verify a Supabase JWT and resolve the caller's engine org.

The app-agnostic half of the "one Supabase login for all thyn-ai apps" design: every website /
dashboard surface (BYOK, self-service device & subscription management) authenticates the same way —
a Supabase access_token (the site's OAuth session) → the caller's GitHub identity → their engine org
(personal install, or org-admin via the App installation). Surfaces differ only in what they then do
with ``(org, identity)``; the verify+resolve path is identical, so it lives here once.

Inert until ``SUPABASE_URL`` (+ the GitHub App) is configured → 503, never a silent allow.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.services import byok_org_resolver, supabase_auth


def _auto_provision_enabled() -> bool:
    """DARK by default: only when flipped on does a brand-new non-GitHub identity (google/apple/
    microsoft) get an ``sb-user-{uid}`` personal org auto-created on first resolve. Off ⇒ they get a
    ``no_org`` 403 (the link table + resolver still land first, additively)."""
    return os.environ.get("ALGENTA_AUTO_PROVISION_SUPABASE_ORG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def bearer_token(authorization: str | None) -> str:
    """Extract the bearer token, or raise 401 (never leak why beyond 'missing')."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail=error_body("missing_bearer", "Authorization: Bearer <token> required."),
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=401, detail=error_body("missing_bearer", "Empty bearer token.")
        )
    return token


async def verify_identity(authorization: str | None) -> dict[str, Any]:
    """Verify the Supabase JWT and return the caller's PROVIDER-AGNOSTIC identity (no org resolution).

    Returns ``{supabase_uid, email, provider, github_user_id|None, github_login|None}`` — the
    ``supabase_uid`` (top-level ``sub``) is the stable identity key across GitHub / Google / Apple /
    Microsoft. 503 when website identity isn't configured or the verifier is unreachable; 401 for an
    invalid/expired token. Shared by both the resolve-one and list-all paths below.
    """
    if not supabase_auth.supabase_configured():
        raise HTTPException(
            status_code=503,
            detail=error_body("supabase_not_configured", "Website identity is not configured."),
        )
    token = bearer_token(authorization)
    try:
        claims = await supabase_auth.verify_supabase_jwt(token)
        return supabase_auth.extract_identity(claims)
    except supabase_auth.SupabaseAuthError as exc:
        status_code = 503 if exc.code in supabase_auth.SERVICE_ERROR_CODES else 401
        raise HTTPException(status_code=status_code, detail=error_body(exc.code, str(exc))) from exc


def parse_org_id(raw: str | None) -> uuid.UUID | None:
    """Parse an ``X-Org-Id`` header value; ignore blanks/garbage (fall back to auto-resolution)."""
    if not raw or not raw.strip():
        return None
    try:
        return uuid.UUID(raw.strip())
    except ValueError:
        return None


async def verify_and_resolve_org(
    authorization: str | None,
    db: AsyncSession,
    redis: Any,
    *,
    selected_org_id: uuid.UUID | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Verify the Supabase JWT + resolve the caller's engine org, or raise an HTTPException.

    503 when the website identity is not configured or the verifier's backing service is unreachable
    (not the user's fault); 401 for an invalid/expired token; the resolver's own ``http_status`` if
    the identity maps to no single eligible org (403/404/409/…). When the caller administers several
    orgs, pass ``selected_org_id`` (from the ``X-Org-Id`` header) to pick one; without it a 409
    carrying the eligible orgs is raised so the UI can prompt for a choice.
    """
    identity = await verify_identity(authorization)
    try:
        org = await byok_org_resolver.resolve_org_for_supabase_user(
            db,
            supabase_uid=identity["supabase_uid"],
            email=identity.get("email"),
            github_user_id=identity.get("github_user_id"),
            github_login=identity.get("github_login"),
            redis=redis,
            selected_org_id=selected_org_id,
            auto_provision=_auto_provision_enabled(),
        )
    except byok_org_resolver.OrgResolutionError as exc:
        detail = error_body(exc.code, str(exc))
        if exc.orgs:
            detail["error"]["orgs"] = exc.orgs
        raise HTTPException(status_code=exc.http_status, detail=detail) from exc
    return org, identity


async def list_eligible_orgs(
    authorization: str | None, db: AsyncSession, redis: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify the JWT and return every org the caller may act in (0, 1, or many), plus identity.

    Backs the org-picker: a single org resolves normally; multiple orgs come back via the resolver's
    ``multiple_orgs`` options instead of a 409; no org yields an empty list (not an error here).
    """
    identity = await verify_identity(authorization)
    try:
        org = await byok_org_resolver.resolve_org_for_supabase_user(
            db,
            supabase_uid=identity["supabase_uid"],
            email=identity.get("email"),
            github_user_id=identity.get("github_user_id"),
            github_login=identity.get("github_login"),
            redis=redis,
            auto_provision=_auto_provision_enabled(),
        )
        return [{"id": str(org.id), "name": org.name}], identity
    except byok_org_resolver.OrgResolutionError as exc:
        if exc.code == "multiple_orgs":
            return exc.orgs, identity
        if exc.code == "no_org":
            return [], identity
        # A real service failure (App unconfigured / GitHub unreachable) — surface it.
        raise HTTPException(
            status_code=exc.http_status, detail=error_body(exc.code, str(exc))
        ) from exc
