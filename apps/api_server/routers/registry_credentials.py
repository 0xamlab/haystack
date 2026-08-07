"""Registry pull credentials for the self-hosted installer.

The one-line installer (``curl -fsSL https://algenta.ai/install.sh | bash``) authenticates
through the SAME device-login path as the SDKs (RFC 8628 device grant against the accounts
portal, ``client_id=algenta-cli``) and exchanges the resulting Supabase access token for
read-only container-registry credentials here, so self-hosters can pull the private runtime
images without ever touching a GitHub token.

Security posture: the caller must present a valid Supabase JWT (verified exactly like
product onboarding); the served credential is a read-only packages token; the control plane
answers 503 unless ``ALGENTA_REGISTRY_READ_TOKEN`` is configured (a self-hosted control
plane does not distribute images). The token value never reaches the logs, and the route is
rate-limited per client IP like the rest of the login path.
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from apps.api_server.middleware.auth import get_redis
from apps.api_server.services.quota_service import check_named_rate_limit
from apps.api_server.services.supabase_auth import (
    SERVICE_ERROR_CODES,
    SupabaseAuthError,
    verify_supabase_jwt,
)
from apps.api_server.services.website_identity import bearer_token, error_body

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Registry"])


class RegistryCredentials(BaseModel):
    registry: str
    username: str
    password: str


def _client_ip(request: Request) -> str:
    fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "unknown")


async def _rate_limit(key: str, redis: Any, *, prefix: str, per_minute: int) -> None:
    """Same fail-open posture as the device-login path: a real 429 surfaces, a limiter
    outage must not take the login path down."""
    try:
        await check_named_rate_limit(
            key, redis, key_prefix=prefix, limit_per_minute=per_minute, error_code="slow_down"
        )
    except HTTPException as exc:
        if exc.status_code == 429:
            raise
        return
    except Exception:  # noqa: BLE001
        return


@router.post(
    "/v1/registry/credentials",
    response_model=RegistryCredentials,
    summary="Exchange a device-login token for read-only registry credentials (installer)",
    description=(
        "Called by install.sh after the device-login flow. Verifies the Supabase access "
        "token and returns read-only credentials for the container registry hosting the "
        "runtime images. Answers 503 when this deployment does not distribute images "
        "(ALGENTA_REGISTRY_READ_TOKEN unset)."
    ),
)
async def registry_credentials(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    redis: Any = Depends(get_redis),
) -> RegistryCredentials:
    from apps.api_server.config import get_settings

    await _rate_limit(_client_ip(request), redis, prefix="registry_creds_req", per_minute=10)

    token = bearer_token(authorization)  # raises 401 if absent
    try:
        await verify_supabase_jwt(token)
    except SupabaseAuthError as exc:
        # Mirror product onboarding: 503 for a service misconfig, 401 for a genuine bad token.
        status = 503 if exc.code in SERVICE_ERROR_CODES else 401
        raise HTTPException(status_code=status, detail=error_body(exc.code, str(exc))) from exc

    settings = get_settings()
    username = settings.algenta_registry_username
    read_token = settings.algenta_registry_read_token
    if not username or not read_token:
        raise HTTPException(
            status_code=503,
            detail=error_body(
                "registry_distribution_disabled",
                "this control plane does not distribute container images",
            ),
        )
    # Deliberately no token value in the log line — only that a credential was served.
    logger.info("registry_credentials.served", registry=settings.algenta_registry_url)
    return RegistryCredentials(
        registry=settings.algenta_registry_url, username=username, password=read_token
    )
