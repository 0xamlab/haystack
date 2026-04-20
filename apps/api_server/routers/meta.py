"""Meta routes — health check and version."""
from datetime import UTC, datetime

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


@router.get("/v1/health", response_model=HealthResponse, summary="Health check")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(UTC))


@router.get("/v1/version", response_model=VersionResponse, summary="API and engine version")
async def version() -> VersionResponse:
    return VersionResponse(
        api_version=API_VERSION,
        engine_version=ENGINE_VERSION,
        environment=settings.api_env,
    )
