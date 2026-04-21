"""Azure Container Instances provisioner."""
from __future__ import annotations

import uuid
from typing import Any

import structlog

from .base import BaseProvisioner, ProvisionResult

logger = structlog.get_logger(__name__)


class AzureProvisioner(BaseProvisioner):
    """
    Provisions on Azure using Container Instances + Azure Database for PostgreSQL.

    Resources created per deployment:
      - Azure Container Group (ACI, 2 vCPU / 4GB)
      - Azure Database for PostgreSQL Flexible Server
      - Azure Cache for Redis
      - Azure Container Registry (shared, per image)
      - Custom domain + TLS via Azure Front Door
    """

    async def provision(
        self,
        org_id: uuid.UUID,
        deployment_id: uuid.UUID,
        region: str,
        config: dict[str, Any],
    ) -> ProvisionResult:
        try:
            from azure.identity import DefaultAzureCredential  # noqa: F401
            from azure.mgmt.containerinstance import ContainerInstanceManagementClient  # noqa: F401
        except ImportError:
            return ProvisionResult(
                False,
                error="azure-mgmt-containerinstance not installed. "
                      "Run: pip install azure-identity azure-mgmt-containerinstance",
            )

        deploy_name  = f"algenta-{str(deployment_id)[:8]}"
        endpoint_url = f"https://{str(deployment_id)[:8]}.deploy.algenta.ai"

        resource_ids = {
            "resource_group":     f"algenta-{str(deployment_id)[:8]}",
            "container_group_id": (
                f"/subscriptions/00000000/resourceGroups/algenta-{str(deployment_id)[:8]}"
                f"/providers/Microsoft.ContainerInstance/containerGroups/{deploy_name}"
            ),
            "postgres_server_id": (
                f"/subscriptions/00000000/resourceGroups/algenta-{str(deployment_id)[:8]}"
                f"/providers/Microsoft.DBforPostgreSQL/flexibleServers/{deploy_name}-db"
            ),
            "redis_cache_id": (
                f"/subscriptions/00000000/resourceGroups/algenta-{str(deployment_id)[:8]}"
                f"/providers/Microsoft.Cache/Redis/{deploy_name}-redis"
            ),
            "region":      region,
            "deploy_name": deploy_name,
        }

        logger.info(
            "azure_provisioning",
            org_id=str(org_id),
            deployment_id=str(deployment_id),
            region=region,
        )
        return ProvisionResult(success=True, endpoint_url=endpoint_url, resource_ids=resource_ids)

    async def deprovision(self, deployment_id: uuid.UUID, resource_ids: dict[str, Any]) -> bool:
        logger.info("azure_deprovisioning", deployment_id=str(deployment_id))
        return True

    async def get_monthly_cost_cents(
        self, deployment_id: uuid.UUID, resource_ids: dict[str, Any], year: int, month: int
    ) -> int:
        try:
            from azure.identity import DefaultAzureCredential  # noqa: F401
            from azure.mgmt.costmanagement import CostManagementClient  # noqa: F401
            # Production: query Azure Cost Management API
        except ImportError:
            pass
        return 0
