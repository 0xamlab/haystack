"""FastAPI auth dependency — extracts and verifies API key on protected routes."""

import uuid

import structlog
from fastapi import Depends, HTTPException, Request, Response, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.models.organization import OrgStatus
from apps.api_server.models.user import UserStatus
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

logger = structlog.get_logger(__name__)

__all__ = ["AuthContext", "get_current_org", "get_redis", "require_verified_email"]

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_redis(request: Request) -> object:
    """Extract Redis client from app state."""
    return request.app.state.redis


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
                    "docs_url": "https://docs.codna.ai/errors/authentication_required",
                }
            },
        )

    ctx = await verify_api_key(raw_key, db, redis_client)
    if ctx is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "invalid_api_key",
                    "message": ("The API key provided is invalid, expired, or has been revoked."),
                    "request_id": getattr(request.state, "request_id", None),
                    "docs_url": "https://docs.codna.ai/errors/invalid_api_key",
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
                    "docs_url": "https://docs.codna.ai/errors/email_verification_required",
                }
            },
        )
    return ctx
