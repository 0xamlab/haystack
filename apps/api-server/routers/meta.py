"""Meta routes — health check, version, and system info."""
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api_server.config import get_settings

router = APIRouter(tags=["System"])
settings = get_settings()

ENGINE_VERSION = "0.1.0"
API_VERSION = "1.0.0"


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class VersionResponse(BaseModel):
    api_version: str
    engine_version: str
    environment: str


@router.get(
    "/v1/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service health status. No authentication required.",
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/v1/version",
    response_model=VersionResponse,
    summary="API and engine version",
    description="Returns current API version and Mojo engine version.",
)
async def version() -> VersionResponse:
    return VersionResponse(
        api_version=API_VERSION,
        engine_version=ENGINE_VERSION,
        environment=settings.api_env,
    )
