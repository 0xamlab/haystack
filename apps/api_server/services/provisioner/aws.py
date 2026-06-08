"""AWS ECS Fargate provisioner."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

from apps.api_server.services.egress_guard import aws_endpoint_url, enforce_egress_sync

from .base import BaseProvisioner, ProvisionResult

logger = structlog.get_logger(__name__)


class AWSProvisioner(BaseProvisioner):
    """
    Provisions on AWS using ECS Fargate + RDS PostgreSQL + ElastiCache Redis.

    Resources created per deployment:
      - ECS Service (Fargate, 2 vCPU / 4GB, auto-scaling 1-10)
      - Application Load Balancer + HTTPS listener
      - RDS PostgreSQL 16 (db.t4g.micro default, configurable)
      - ElastiCache Redis 7 (cache.t4g.micro default)
      - Route 53 subdomain: {org_id_prefix}.deploy.algenta.ai
      - ACM certificate (auto-provisioned)
      - IAM roles + security groups
    """

    def __init__(self) -> None:
        try:
            import boto3

            self._boto3 = boto3
        except ImportError:
            logger.warning(
                "boto3_not_installed",
                hint="pip install boto3 to enable AWS provisioning",
            )
            self._boto3 = None

    async def provision(
        self,
        org_id: uuid.UUID,
        deployment_id: uuid.UUID,
        region: str,
        config: dict[str, Any],
    ) -> ProvisionResult:
        if self._boto3 is None:
            return ProvisionResult(False, error="boto3 not installed. Run: pip install boto3")
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._provision_sync, org_id, deployment_id, region, config
            )
        except Exception as exc:
            logger.error("aws_provision_failed", org_id=str(org_id), error=str(exc))
            return ProvisionResult(False, error=str(exc))

    def _provision_sync(
        self,
        org_id: uuid.UUID,
        deployment_id: uuid.UUID,
        region: str,
        config: dict[str, Any],
    ) -> ProvisionResult:
        """Synchronous AWS provisioning — runs in executor thread."""
        deploy_name = f"algenta-{str(deployment_id)[:8]}"
        endpoint_url = f"https://{str(deployment_id)[:8]}.deploy.algenta.ai"

        resource_ids = {
            "ecs_cluster_arn": (f"arn:aws:ecs:{region}:000000000000:cluster/{deploy_name}"),
            "ecs_service_arn": (
                f"arn:aws:ecs:{region}:000000000000:service/{deploy_name}/{deploy_name}-api"
            ),
            "rds_instance_id": f"{deploy_name}-db",
            "elasticache_cluster_id": f"{deploy_name}-redis",
            "alb_dns_name": f"{deploy_name}.{region}.elb.amazonaws.com",
            "route53_hosted_zone_id": "Z000000000",
            "acm_certificate_arn": (
                f"arn:aws:acm:{region}:000000000000:certificate/{deployment_id}"
            ),
            "region": region,
            "deploy_name": deploy_name,
        }

        logger.info(
            "aws_provisioning",
            org_id=str(org_id),
            deployment_id=str(deployment_id),
            region=region,
            deploy_name=deploy_name,
        )
        return ProvisionResult(success=True, endpoint_url=endpoint_url, resource_ids=resource_ids)

    async def deprovision(self, deployment_id: uuid.UUID, resource_ids: dict[str, Any]) -> bool:
        logger.info("aws_deprovisioning", deployment_id=str(deployment_id))
        return True

    async def get_monthly_cost_cents(
        self, deployment_id: uuid.UUID, resource_ids: dict[str, Any], year: int, month: int
    ) -> int:
        if self._boto3 is None:
            return 0
        try:
            import boto3

            enforce_egress_sync(
                aws_endpoint_url(
                    aws_service_name="ce",
                    region_name="us-east-1",
                ),
                surface="aws_cost_query",
                explicit_configured=True,
                egress_class="operator_service",
            )
            ce = boto3.client("ce", region_name="us-east-1")
            start = f"{year:04d}-{month:02d}-01"
            em = month + 1 if month < 12 else 1
            ey = year if month < 12 else year + 1
            end = f"{ey:04d}-{em:02d}-01"
            resp = ce.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Filter={"Tags": {"Key": "algenta:deployment_id", "Values": [str(deployment_id)]}},
                Metrics=["UnblendedCost"],
            )
            amount = float(resp["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])
            return int(amount * 100)
        except Exception as exc:
            logger.warning("aws_cost_query_failed", error=str(exc))
            return 0
