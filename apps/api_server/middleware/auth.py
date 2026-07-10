"""FastAPI auth dependency — extracts and verifies API key on protected routes."""

import uuid

import structlog
from fastapi import Depends, HTTPException, Request, Response, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.models.organization import OrgStatus
from apps.api_server.models.user import UserStatus
from apps.api_server.services import entra_auth
from apps.api_server.services.auth_service import (
    AuthContext,
    consume_auth_session_dirty,
    verify_api_key,
)
from apps.api_server.services.device_service import (
    HOSTED_DEVICE_BINDING_TOKEN_HEADER,
    DeviceBindingError,
    bind_hosted_api_device,
)
from apps.api_server.services.offline_token import verify_offline_token

logger = structlog.get_logger(__name__)

__all__ = ["AuthContext", "get_current_org", "get_redis", "require_verified_email"]

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_redis(request: Request) -> object:
    """Extract Redis client from app state."""
    return request.app.state.redis


# Entra failures that mean "you are who you say, but not allowed here" (403) vs bad token (401).
_ENTRA_FORBIDDEN_CODES = frozenset(
    {"principal_not_mapped", "tenant_not_allowed", "client_app_not_allowed", "wrong_resource_token"}
)


async def _verify_entra_bearer(raw_key: str, db: AsyncSession, request: Request) -> AuthContext:
    """Verify an Entra bearer and resolve it to an AuthContext, or raise the right HTTP error."""

    from apps.api_server.services.entra_org_resolver import resolve_entra_principal

    request_id = getattr(request.state, "request_id", None)
    try:
        principal = await entra_auth.verify_entra_token(raw_key)
        return await resolve_entra_principal(principal, db)
    except entra_auth.EntraAuthError as exc:
        if exc.code in entra_auth.SERVICE_ERROR_CODES:
            status = 503
        elif exc.code in _ENTRA_FORBIDDEN_CODES:
            status = 403
        else:
            status = 401
        logger.info("entra_auth_rejected", code=exc.code, status=status)
        raise HTTPException(
            status_code=status,
            detail={
                "error": {
                    "code": f"entra_{exc.code}",
                    "message": exc.message,
                    "request_id": request_id,
                }
            },
        ) from exc


async def get_current_org(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: object = Depends(get_redis),
    api_key_value: str | None = Security(_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> AuthContext:
    """
    FastAPI dependency that authenticates every protected request.
    Accepts X-API-Key header or Authorization: Bearer <api_key>.
    Returns AuthContext or raises 401.
    """
    raw_key: str | None = None
    if api_key_value:
        raw_key = api_key_value
    elif bearer:
        raw_key = bearer.credentials

    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "authentication_required",
                    "message": (
                        "API key required. Use Authorization: Bearer <key> "
                        "header (X-API-Key also accepted for legacy clients)."
                    ),
                    "request_id": getattr(request.state, "request_id", None),
                    "docs_url": "https://docs.algenta.ai/errors/authentication_required",
                }
            },
        )

    # MICROSOFT ENTRA ID: when the gateway is Entra-configured AND the bearer's (unverified)
    # issuer is an Entra issuer, this is the ONLY verifier tried — an Entra-looking token that
    # fails verification is rejected outright, never fed to the api-key/license paths
    # (fail-closed; no downgrade). The workspace comes from the provisioned principal mapping,
    # never from headers (is_platform=False also blocks X-Workspace-Id).
    if entra_auth.entra_configured() and entra_auth.looks_like_entra_token(raw_key):
        ctx = await _verify_entra_bearer(raw_key, db, request)
        _enforce_account_status(ctx, request)
        _hdrs = getattr(request, "headers", None)
        if _hdrs is not None and (_hdrs.get("X-Workspace-Id") or "").strip():
            # The workspace is DERIVED from the principal mapping; an Entra caller may never
            # select one. Reject explicitly (same posture as tenant keys) — never ignore.
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "workspace_scope_not_permitted",
                        "message": (
                            "An Entra identity's workspace is derived from its provisioned "
                            "mapping; X-Workspace-Id is not permitted."
                        ),
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )
        request.state.org_id = ctx["org_id"]
        return ctx

    # OFFLINE-FIRST AUTH: verify a signed license JWT LOCALLY (signature + expiry) and map its
    # claims to an AuthContext — ZERO Postgres/Redis/network on the hot path (the per-request
    # apikey+organizations SELECT is skipped entirely; works on a device gone dark). Fall back to the
    # DB-backed api-key path only for non-JWT (legacy/hosted) credentials.
    ctx = verify_offline_token(raw_key)
    if ctx is None:
        ctx = await verify_api_key(raw_key, db, redis_client)
    if ctx is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "invalid_api_key",
                    "message": ("The API key provided is invalid, expired, or has been revoked."),
                    "request_id": getattr(request.state, "request_id", None),
                    "docs_url": "https://docs.algenta.ai/errors/invalid_api_key",
                }
            },
        )

    # Reject suspended/deleted orgs + suspended users on EVERY protected request (covers both the
    # DB and the Redis-cache auth path, since the statuses are carried on the AuthContext).
    _enforce_account_status(ctx, request)

    # Sub-tenancy: a PLATFORM key (e.g. Mission's company key) may act on behalf of
    # a specific workspace within its org via X-Workspace-Id. A tenant key may NOT
    # assume a workspace — reject to prevent cross-tenant access.
    _headers = getattr(request, "headers", None)
    workspace_header = _headers.get("X-Workspace-Id") if _headers is not None else None
    if workspace_header:
        workspace_header = workspace_header.strip()
    if workspace_header:
        if not ctx.get("is_platform"):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "workspace_scope_not_permitted",
                        "message": (
                            "Only a platform key may set X-Workspace-Id; this key may not "
                            "assume a workspace scope."
                        ),
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )
        try:
            ctx["workspace_id"] = uuid.UUID(workspace_header)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "invalid_workspace_id",
                        "message": "X-Workspace-Id must be a valid UUID.",
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )

    should_commit = consume_auth_session_dirty(db)

    try:
        binding = await bind_hosted_api_device(request, ctx, db)
    except DeviceBindingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **exc.details,
                }
            },
        ) from exc

    request.state.org_id = ctx["org_id"]
    if binding:
        should_commit = True
        request.state.device_id = binding["device_id"]
        if binding["binding_token"]:
            headers = dict(getattr(request.state, "extra_response_headers", {}))
            headers[HOSTED_DEVICE_BINDING_TOKEN_HEADER] = binding["binding_token"]
            request.state.extra_response_headers = headers
            response.headers[HOSTED_DEVICE_BINDING_TOKEN_HEADER] = binding["binding_token"]
    if should_commit:
        await db.commit()
    return ctx


def _enforce_account_status(ctx: AuthContext, request: Request) -> None:
    """Reject a request from a suspended/deleted organization or a suspended user (Wave 2).

    Runs on every protected request via get_current_org, so it covers both the database and the
    Redis-cache auth paths. (A freshly-suspended account stays active until its cached AuthContext
    expires — ≤ the auth cache TTL — or the suspend action busts the cache via
    invalidate_api_key_cache.)
    """
    request_id = getattr(request.state, "request_id", None)
    if ctx["org_status"] in (OrgStatus.SUSPENDED.value, OrgStatus.DELETED.value):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "organization_suspended",
                    "message": "This organization is suspended and cannot make API calls. Contact support.",
                    "request_id": request_id,
                }
            },
        )
    if ctx["user_status"] == UserStatus.SUSPENDED.value:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "account_suspended",
                    "message": "This account is suspended. Contact support.",
                    "request_id": request_id,
                }
            },
        )


async def require_verified_email(
    ctx: AuthContext = Depends(get_current_org),
) -> AuthContext:
    """Gate agentic/expensive endpoints on a verified email address (Wave 2).

    Applied as a router-level dependency on the agentic routers (simulate, agent_runs,
    repositories, jobs). Service keys are machine credentials with no human email, so they are
    exempt; key-only contexts resolve email_verified=True in verify_api_key. Account creation and
    read/account endpoints stay open so a new user can verify and manage their account.

    Reads via .get() so an incomplete ctx (e.g. a test that overrides get_current_org with a
    partial dict) is treated as permitted rather than crashing; the real auth path always supplies
    is_service + email_verified, so production enforcement is unaffected.
    """
    if not ctx.get("is_service") and not ctx.get("email_verified", True):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "email_verification_required",
                    "message": (
                        "Verify your email address before using this endpoint. "
                        "Check your inbox or request a new verification link via /auth/verify."
                    ),
                    "docs_url": "https://docs.algenta.ai/errors/email_verification_required",
                }
            },
        )
    return ctx
