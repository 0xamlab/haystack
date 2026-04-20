"""
Deployment management API — per-org cloud isolation.

Endpoints:
  GET    /v1/deployments/regions          — List available cloud providers + regions
  GET    /v1/deployments                  — Get current org deployment
  POST   /v1/deployments                  — Request a new deployment (provision)
  DELETE /v1/deployments/{deployment_id}  — Deprovision a deployment
  GET    /v1/deployments/{deployment_id}/cost — Get current month cloud cost
"""
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.middleware.rbac import require_role
from apps.api_server.models.deployment import Deployment, DeploymentStatus
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.provisioner_service import (
    get_available_regions,
    get_provisioner,
    provision_deployment,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Deployments"])

AsyncSessionDep = Annotated[AsyncSession, Depends(get_db)]


# ─── Schemas ──────────────────────────────────────────────────────────────────

class DeploymentCreate(BaseModel):
    provider: str = Field(
        description="Cloud provider: algenta_shared, aws, azure, gcp",
        default="algenta_shared",
    )
    region: str = Field(
        description="Cloud region identifier. Use /v1/deployments/regions to list options.",
        default="algenta-shared",
    )
    config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional provider-specific configuration. "
            "Supported keys: instance_size (e.g. 'small'|'medium'|'large'), "
            "storage_gb, max_concurrent_runs, auto_scale_max."
        ),
    )
    billing_markup_pct: float = Field(
        default=20.0,
        ge=0,
        le=200,
        description="Pass-through cost markup percentage. Default: 20%.",
    )


class DeploymentResponse(BaseModel):
    deployment_id: str
    org_id: str
    provider: str
    region: str
    status: str
    endpoint_url: str | None
    cost_usd_month: float
    billable_cost_usd_month: float
    billing_markup_pct: float
    created_at: str
    provisioned_at: str | None
    error_message: str | None

    @classmethod
    def from_model(cls, d: Deployment) -> "DeploymentResponse":
        return cls(
            deployment_id=str(d.id),
            org_id=str(d.org_id),
            provider=d.provider.value if hasattr(d.provider, "value") else str(d.provider),
            region=d.region,
            status=d.status.value if hasattr(d.status, "value") else str(d.status),
            endpoint_url=d.endpoint_url,
            cost_usd_month=d.cost_usd_month,
            billable_cost_usd_month=d.billable_cost_usd_month,
            billing_markup_pct=float(d.billing_markup_pct),
            created_at=d.created_at.isoformat() if d.created_at else "",
            provisioned_at=d.provisioned_at.isoformat() if d.provisioned_at else None,
            error_message=d.error_message,
        )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/v1/deployments/regions",
    summary="List available cloud providers and regions",
)
async def list_regions(
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> dict[str, Any]:
    """
    Returns all available cloud providers and their supported regions.
    Regions are fetched live from cloud SDKs when credentials are available,
    otherwise returns a comprehensive static fallback list.
    Use the region `id` field when creating a deployment.
    """
    live_regions = await get_available_regions()
    return {
        "providers": [
            {
                "id": "algenta_shared",
                "name": "Algenta Managed",
                "description": "Multi-tenant shared pool — default tier, no setup required.",
                "icon": "🌐",
                "regions": live_regions["algenta_shared"],
            },
            {
                "id": "aws",
                "name": "Amazon Web Services",
                "description": (
                    "Isolated deployment on AWS ECS Fargate + RDS + ElastiCache. "
                    "HIPAA-eligible. SOC2 Type II."
                ),
                "icon": "☁️",
                "regions": live_regions["aws"],
            },
            {
                "id": "azure",
                "name": "Microsoft Azure",
                "description": (
                    "Isolated deployment on Azure Container Instances + PostgreSQL "
                    "Flexible + Redis Cache."
                ),
                "icon": "☁️",
                "regions": live_regions["azure"],
            },
            {
                "id": "gcp",
                "name": "Google Cloud Platform",
                "description": "Isolated deployment on Cloud Run + Cloud SQL + Memorystore Redis.",
                "icon": "☁️",
                "regions": live_regions["gcp"],
            },
        ]
    }


@router.get(
    "/v1/deployments",
    response_model=DeploymentResponse | None,
    summary="Get current org deployment",
)
async def get_deployment(
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> DeploymentResponse | None:
    """Return the active deployment for this org, or None if using shared pool."""
    result = await db.execute(
        select(Deployment).where(
            Deployment.org_id == auth["org_id"],
            Deployment.status.in_([
                DeploymentStatus.ACTIVE,
                DeploymentStatus.PROVISIONING,
                DeploymentStatus.REQUESTED,
                DeploymentStatus.UPDATING,
            ]),
        ).order_by(Deployment.created_at.desc()).limit(1)
    )
    deployment = result.scalar_one_or_none()
    if deployment is None:
        return None
    return DeploymentResponse.from_model(deployment)


@router.post(
    "/v1/deployments",
    response_model=DeploymentResponse,
    status_code=202,
    summary="Request a new cloud deployment",
    description=(
        "Provision an isolated engine deployment on your chosen cloud provider and region. "
        "Returns 202 Accepted immediately — provisioning is async (typically 3-5 minutes). "
        "Poll GET /v1/deployments to check status. "
        "When status=active, all API calls are automatically routed to your isolated deployment. "
        "Requires owner role."
    ),
)
async def create_deployment(
    payload: DeploymentCreate,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(require_role("owner"))],
) -> DeploymentResponse:
    """Create a new deployment for this org."""
    # Check for existing active/in-progress deployment
    existing = await db.execute(
        select(Deployment).where(
            Deployment.org_id == auth["org_id"],
            Deployment.status.in_([
                DeploymentStatus.ACTIVE,
                DeploymentStatus.PROVISIONING,
                DeploymentStatus.REQUESTED,
            ]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "deployment_exists",
                    "message": (
                        "An active or in-progress deployment already exists for "
                        "this org. Deprovision it first."
                    ),
                }
            },
        )

    # Validate provider + region
    from apps.api_server.services.provisioner_service import REGIONS as ALL_REGIONS
    if payload.provider not in ALL_REGIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_provider",
                    "message": (
                        f"Unknown provider '{payload.provider}'. "
                        f"Valid: {list(ALL_REGIONS.keys())}"
                    ),
                }
            },
        )
    valid_regions = [r["id"] for r in ALL_REGIONS[payload.provider]]
    if payload.region not in valid_regions:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_region",
                    "message": (
                        f"Region '{payload.region}' not available for "
                        f"{payload.provider}. Valid: {valid_regions}"
                    ),
                }
            },
        )

    # Create deployment record
    deployment = Deployment(
        org_id=auth["org_id"],
        provider=payload.provider,
        region=payload.region,
        status=DeploymentStatus.REQUESTED,
        config=payload.config,
        billing_markup_pct=payload.billing_markup_pct,
        requested_by_user_id=auth.get("key_id"),
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    # Start async provisioning (fire-and-forget)
    import asyncio
    asyncio.create_task(_provision_async(
        deployment.id,
        auth["org_id"],
        payload.provider,
        payload.region,
        payload.config or {},
    ))

    logger.info(
        "deployment_requested",
        org_id=str(auth["org_id"]),
        deployment_id=str(deployment.id),
        provider=payload.provider,
        region=payload.region,
    )

    return DeploymentResponse.from_model(deployment)


@router.delete(
    "/v1/deployments/{deployment_id}",
    status_code=202,
    summary="Deprovision a deployment",
    description=(
        "Tear down cloud resources for a deployment. Org will revert to shared "
        "pool. Requires owner role."
    ),
)
async def delete_deployment(
    deployment_id: uuid.UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(require_role("owner"))],
) -> dict[str, str]:
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.org_id == auth["org_id"],
        )
    )
    deployment = result.scalar_one_or_none()
    if deployment is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Deployment not found."}},
        )

    if deployment.status == DeploymentStatus.DEPROVISIONED:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "already_deprovisioned",
                    "message": "This deployment is already deprovisioned.",
                }
            },
        )

    deployment.status = DeploymentStatus.DEPROVISIONING
    await db.commit()

    import asyncio
    asyncio.create_task(
        _deprovision_async(
            deployment_id,
            deployment.provider,
            deployment.cloud_resource_ids or {},
        )
    )

    return {"status": "deprovisioning", "deployment_id": str(deployment_id)}


@router.get(
    "/v1/deployments/{deployment_id}/cost",
    summary="Get current month cloud cost for a deployment",
)
async def get_deployment_cost(
    deployment_id: uuid.UUID,
    db: AsyncSessionDep,
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
) -> dict[str, Any]:
    result = await db.execute(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.org_id == auth["org_id"],
        )
    )
    deployment = result.scalar_one_or_none()
    if deployment is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Deployment not found."}},
        )

    now = datetime.now(UTC)
    return {
        "deployment_id": str(deployment_id),
        "provider": deployment.provider,
        "region": deployment.region,
        "year": now.year,
        "month": now.month,
        "cost_usd_month": deployment.cost_usd_month,
        "billable_cost_usd_month": deployment.billable_cost_usd_month,
        "billing_markup_pct": float(deployment.billing_markup_pct),
        "last_updated": deployment.updated_at.isoformat() if deployment.updated_at else None,
    }


# ─── Async provisioning helpers ───────────────────────────────────────────────

async def _provision_async(
    deployment_id: uuid.UUID,
    org_id: uuid.UUID,
    provider: str,
    region: str,
    config: dict[str, Any],
) -> None:
    """Background task: provision cloud resources and update deployment record."""
    from apps.api_server.db.session import async_session_factory

    async with async_session_factory() as db:
        try:
            result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
            deployment = result.scalar_one_or_none()
            if deployment is None:
                return

            deployment.status = DeploymentStatus.PROVISIONING
            deployment.provisioning_started_at = datetime.now(UTC)
            await db.commit()

            provision_result = await provision_deployment(
                org_id,
                deployment_id,
                provider,
                region,
                config,
            )

            if provision_result.success:
                deployment.status = DeploymentStatus.ACTIVE
                deployment.endpoint_url = provision_result.endpoint_url
                deployment.cloud_resource_ids = provision_result.resource_ids
                deployment.provisioned_at = datetime.now(UTC)
                logger.info(
                    "deployment_provisioned",
                    deployment_id=str(deployment_id),
                    endpoint_url=provision_result.endpoint_url,
                )
            else:
                deployment.status = DeploymentStatus.FAILED
                deployment.error_message = provision_result.error
                logger.error(
                    "deployment_failed",
                    deployment_id=str(deployment_id),
                    error=provision_result.error,
                )

            await db.commit()

        except Exception as exc:
            logger.error(
                "deployment_provision_exception",
                deployment_id=str(deployment_id),
                error=str(exc),
            )
            try:
                result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
                d = result.scalar_one_or_none()
                if d:
                    d.status = DeploymentStatus.FAILED
                    d.error_message = str(exc)
                    await db.commit()
            except Exception as update_exc:
                logger.debug(
                    "deployment_failure_status_update_failed",
                    deployment_id=str(deployment_id),
                    error=str(update_exc),
                )


async def _deprovision_async(
    deployment_id: uuid.UUID,
    provider: Any,
    resource_ids: dict[str, Any],
) -> None:
    """Background task: tear down cloud resources."""
    from apps.api_server.db.session import async_session_factory

    provider_str = provider.value if hasattr(provider, "value") else str(provider)
    provisioner = get_provisioner(provider_str)

    async with async_session_factory() as db:
        success = True
        if provisioner:
            success = await provisioner.deprovision(deployment_id, resource_ids)

        result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        if deployment:
            deployment.status = (
                DeploymentStatus.DEPROVISIONED
                if success
                else DeploymentStatus.FAILED
            )
            deployment.endpoint_url = None
            await db.commit()
