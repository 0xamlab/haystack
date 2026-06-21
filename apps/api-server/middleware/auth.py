"""FastAPI auth dependency — extracts and verifies API key on protected routes."""
import redis.asyncio as aioredis
import structlog
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.services.auth_service import AuthContext, verify_api_key

logger = structlog.get_logger(__name__)

# Security schemes for OpenAPI spec
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_redis(request: Request) -> aioredis.Redis:  # type: ignore[type-arg]
    """Extract Redis client from app state."""
    return request.app.state.redis


async def get_current_org(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),  # type: ignore[type-arg]
    api_key_value: str | None = Security(_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> AuthContext:
    """
    FastAPI dependency that authenticates every protected request.

    Accepts:
    - X-API-Key header
    - Authorization: Bearer <api_key> header

    Returns AuthContext with org_id, key_id, plan.
    Raises 401 if key is missing, invalid, or revoked.
    """
    # Extract raw key from whichever header was provided
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
                    "message": "API key required. Provide X-API-Key header or Authorization: Bearer <key>.",
                    "request_id": getattr(request.state, "request_id", None),
                    "docs_url": "https://docs.algenta.ai/errors/authentication_required",
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
                    "message": "The API key provided is invalid or has been revoked.",
                    "request_id": getattr(request.state, "request_id", None),
                    "docs_url": "https://docs.algenta.ai/errors/invalid_api_key",
                }
            },
        )

    # Attach org_id to request state for logging middleware
    request.state.org_id = ctx["org_id"]
    return ctx
