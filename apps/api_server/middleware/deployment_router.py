"""
Deployment routing middleware — routes authenticated requests to the correct
org data plane endpoint when a dedicated cloud deployment is active.

Flow:
  1. Request arrives at control plane (api.algenta.ai)
  2. Auth middleware resolves org_id from API key
  3. This middleware checks if org has an active deployment with endpoint_url
  4. If yes: proxy the request to the data plane endpoint
  5. If no: fall through to local (shared pool) handler

Cache: Active deployment endpoint URLs are cached in Redis (5-minute TTL)
to avoid a DB lookup on every request.
"""
from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

# Paths that should NEVER be proxied — always handled by control plane
_CONTROL_PLANE_ONLY_PREFIXES = (
    "/v1/deployments",
    "/v1/billing",
    "/v1/team",
    "/v1/api-keys",
    "/v1/account",
    "/v1/auth",
    "/v1/simulate/templates",
    "/mcp",
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)

# Cache key prefix for deployment endpoint lookup
_CACHE_PREFIX = "deployment:endpoint:"
_CACHE_TTL = 300  # 5 minutes


class DeploymentRoutingMiddleware(BaseHTTPMiddleware):
    """
    Proxy requests to per-org data plane when org has an active dedicated deployment.

    Only activates for simulation paths: /v1/simulate, /v1/runs, /v1/jobs, /v1/analytics
    Control plane paths (billing, team, api-keys) are always handled locally.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        # Fast path: skip non-simulation paths entirely
        path = request.url.path
        if not self._should_proxy(path):
            return await call_next(request)  # type: ignore[operator]

        # Get org_id from request state (set by auth middleware)
        org_id = getattr(request.state, "org_id", None)
        if org_id is None:
            return await call_next(request)  # type: ignore[operator]

        # Look up active deployment endpoint
        endpoint_url = await self._get_deployment_endpoint(request, str(org_id))
        if endpoint_url is None:
            # No dedicated deployment — use shared pool (local handler)
            return await call_next(request)  # type: ignore[operator]

        # Proxy request to data plane
        try:
            return await self._proxy_request(request, endpoint_url)
        except Exception as exc:
            logger.error(
                "deployment_proxy_failed",
                org_id=str(org_id),
                endpoint=endpoint_url,
                error=str(exc),
            )
            # Fallback: route to shared pool on proxy failure
            return await call_next(request)  # type: ignore[operator]

    def _should_proxy(self, path: str) -> bool:
        """Return True if this path should be considered for data plane proxying."""
        # Never proxy control plane paths
        for prefix in _CONTROL_PLANE_ONLY_PREFIXES:
            if path.startswith(prefix):
                return False
        # Only proxy simulation/runs/jobs paths
        proxyable_prefixes = (
            "/v1/simulate",
            "/v1/runs",
            "/v1/jobs",
            "/v1/analytics",
            "/v1/recommend",
        )
        return any(path.startswith(p) for p in proxyable_prefixes)

    async def _get_deployment_endpoint(self, request: Request, org_id: str) -> str | None:
        """
        Look up the active deployment endpoint for this org.
        Cached in Redis for 5 minutes to avoid DB lookup per request.
        """
        cache_key = f"{_CACHE_PREFIX}{org_id}"

        # Try Redis cache first
        try:
            redis = getattr(request.app.state, "redis", None)
            if redis is not None:
                cached = await redis.get(cache_key)
                if cached is not None:
                    decoded = cached.decode() if isinstance(cached, bytes) else str(cached)
                    return decoded if decoded != "shared" else None
        except Exception as exc:
            logger.debug(
                "deployment_endpoint_cache_read_failed",
                org_id=org_id,
                cache_key=cache_key,
                error=str(exc),
            )

        # Cache miss — query DB
        try:
            import uuid

            from sqlalchemy import select

            from apps.api_server.db.session import AsyncSessionLocal
            from apps.api_server.models.deployment import Deployment, DeploymentStatus

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Deployment).where(
                        Deployment.org_id == uuid.UUID(org_id),
                        Deployment.status == DeploymentStatus.ACTIVE,
                        Deployment.endpoint_url.isnot(None),
                    ).limit(1)
                )
                deployment = result.scalar_one_or_none()
                endpoint_url = deployment.endpoint_url if deployment else None

            # Cache result
            try:
                redis = getattr(request.app.state, "redis", None)
                if redis is not None:
                    await redis.set(
                        cache_key,
                        endpoint_url or "shared",
                        ex=_CACHE_TTL,
                    )
            except Exception as exc:
                logger.debug(
                    "deployment_endpoint_cache_write_failed",
                    org_id=org_id,
                    cache_key=cache_key,
                    error=str(exc),
                )

            return endpoint_url

        except Exception as exc:
            logger.warning("deployment_endpoint_lookup_failed", org_id=org_id, error=str(exc))
            return None

    async def _proxy_request(self, request: Request, endpoint_url: str) -> Response:
        """
        Forward the request to the data plane endpoint, preserving headers + body.
        Strips the host header and adds X-Forwarded-For.
        """
        import httpx

        # Build target URL
        target_url = f"{endpoint_url.rstrip('/')}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        # Forward original headers (preserve auth, content-type, etc.)
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }
        headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
        headers["X-Algenta-Control-Plane"] = "true"

        body = await request.body()

        async with httpx.AsyncClient(timeout=60) as client:
            proxy_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

        logger.info(
            "request_proxied",
            org_id=str(getattr(request.state, "org_id", "unknown")),
            endpoint=endpoint_url,
            path=request.url.path,
            status=proxy_response.status_code,
        )

        return Response(
            content=proxy_response.content,
            status_code=proxy_response.status_code,
            headers=dict(proxy_response.headers),
            media_type=proxy_response.headers.get("content-type"),
        )


def invalidate_deployment_cache(org_id: str, redis_client: object) -> None:
    """Call this when a deployment status changes to clear the routing cache."""
    import asyncio
    try:
        import redis.asyncio as aioredis
        redis: aioredis.Redis = redis_client  # type: ignore
        cache_key = f"{_CACHE_PREFIX}{org_id}"
        asyncio.create_task(redis.delete(cache_key))
    except Exception as exc:
        logger.debug(
            "deployment_cache_invalidation_failed",
            org_id=org_id,
            error=str(exc),
        )
