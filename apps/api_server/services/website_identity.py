"""Shared website/dashboard identity: verify a Supabase JWT and resolve the caller's engine org.

The app-agnostic half of the "one Supabase login for all thyn-ai apps" design: every website /
dashboard surface (BYOK, self-service device & subscription management) authenticates the same way —
a Supabase access_token (the site's OAuth session) → the caller's GitHub identity → their engine org
(personal install, or org-admin via the App installation). Surfaces differ only in what they then do
with ``(org, identity)``; the verify+resolve path is identical, so it lives here once.

Inert until ``SUPABASE_URL`` (+ the GitHub App) is configured → 503, never a silent allow.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.services import byok_org_resolver, supabase_auth


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


async def verify_and_resolve_org(
    authorization: str | None, db: AsyncSession, redis: Any
) -> tuple[Any, dict[str, Any]]:
    """Verify the Supabase JWT + resolve the caller's engine org, or raise an HTTPException.

    503 when the website identity is not configured or the verifier's backing service is unreachable
    (not the user's fault); 401 for an invalid/expired token; the resolver's own ``http_status`` if
    the identity maps to no single eligible org (403/404/409/…).
    """
    if not supabase_auth.supabase_configured():
        raise HTTPException(
            status_code=503,
            detail=error_body("supabase_not_configured", "Website identity is not configured."),
        )
    token = bearer_token(authorization)
    try:
        claims = await supabase_auth.verify_supabase_jwt(token)
        identity = supabase_auth.extract_github_identity(claims)
    except supabase_auth.SupabaseAuthError as exc:
        status_code = 503 if exc.code in supabase_auth.SERVICE_ERROR_CODES else 401
        raise HTTPException(status_code=status_code, detail=error_body(exc.code, str(exc))) from exc
    try:
        org = await byok_org_resolver.resolve_org_for_github_user(
            db,
            github_user_id=identity["github_user_id"],
            github_login=identity["github_login"],
            redis=redis,
        )
    except byok_org_resolver.OrgResolutionError as exc:
        raise HTTPException(
            status_code=exc.http_status, detail=error_body(exc.code, str(exc))
        ) from exc
    return org, identity
