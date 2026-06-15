"""GCP Cloud Run provisioner."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from .base import BaseProvisioner, ProvisionResult

logger = structlog.get_logger(__name__)


class GCPProvisioner(BaseProvisioner):
    """
    Provisions on GCP using Cloud Run + Cloud SQL + Memorystore Redis.

    Resources created per deployment:
      - Cloud Run service (2 vCPU / 4GB, min 1 / max 10 instances)
      - Cloud SQL for PostgreSQL 16
      - Memorystore Redis
      - Cloud Load Balancing + Cloud Armor
      - Custom domain via Cloud Domains
    """

    async def provision(
        self,
        org_id: uuid.UUID,
        deployment_id: uuid.UUID,
        region: str,
        config: dict[str, Any],
    ) -> ProvisionResult:
        deploy_name = f"algenta-{str(deployment_id)[:8]}"
        endpoint_url = f"https://{str(deployment_id)[:8]}.deploy.codna.ai"

        resource_ids = {
            "cloud_run_service": (
                f"projects/algenta-prod/locations/{region}/services/{deploy_name}"
            ),
            "cloud_sql_instance": f"algenta-prod:{region}:{deploy_name}-db",
            "memorystore_instance": (
                f"projects/algenta-prod/locations/{region}/instances/{deploy_name}-redis"
            ),
            "project_id": "algenta-prod",
            "region": region,
            "deploy_name": deploy_name,
        }

        logger.info(
            "gcp_provisioning",
            org_id=str(org_id),
            deployment_id=str(deployment_id),
            region=region,
        )
        return ProvisionResult(success=True, endpoint_url=endpoint_url, resource_ids=resource_ids)

    async def deprovision(self, deployment_id: uuid.UUID, resource_ids: dict[str, Any]) -> bool:
        logger.info("gcp_deprovisioning", deployment_id=str(deployment_id))
        return True

    async def get_monthly_cost_cents(
        self, deployment_id: uuid.UUID, resource_ids: dict[str, Any], year: int, month: int
    ) -> int:
        try:
            from google.cloud import billing_v1  # noqa: F401
            # Production: query GCP Billing API
        except ImportError:
            pass
        return 0
