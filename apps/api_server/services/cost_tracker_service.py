"""
Cost tracker — pulls cloud provider costs nightly and creates Stripe pass-through billing records.

Runs as a scheduled task (cron via Celery/APScheduler or external scheduler).
Can also be triggered manually via API for on-demand cost refresh.

Flow:
  1. Query all active deployments
  2. For each deployment: call provider-specific Cost API
  3. Update deployments.cost_usd_month_cents
  4. Push to Stripe as metered usage (with markup)
  5. Emit audit event
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def refresh_deployment_costs(
    org_id: uuid.UUID | None = None,
    db: Any = None,
) -> dict[str, Any]:
    """
    Refresh cloud costs for all active deployments (or a single org's deployment).

    Args:
        org_id: If provided, only refresh costs for this org's deployment.
        db: AsyncSession to use (injected).

    Returns:
        Summary of refreshed deployments with cost data.
    """
    from sqlalchemy import select

    from apps.api_server.models.deployment import CloudProvider, Deployment, DeploymentStatus
    from apps.api_server.services.provisioner_service import get_provisioner

    now = datetime.now(UTC)
    year, month = now.year, now.month

    query = select(Deployment).where(Deployment.status == DeploymentStatus.ACTIVE)
    if org_id:
        query = query.where(Deployment.org_id == org_id)

    result = await db.execute(query)
    deployments = result.scalars().all()

    refreshed = []
    for deployment in deployments:
        provider_str = (
            deployment.provider.value
            if hasattr(deployment.provider, "value")
            else str(deployment.provider)
        )
        if provider_str == CloudProvider.ALGENTA_SHARED.value:
            continue  # Shared pool — no per-org cloud cost

        provisioner = get_provisioner(provider_str)
        if provisioner is None:
            continue

        try:
            cost_cents = await provisioner.get_monthly_cost_cents(
                deployment.id,
                deployment.cloud_resource_ids or {},
                year,
                month,
            )
            deployment.cost_usd_month_cents = cost_cents
            await db.commit()

            # Push to Stripe
            stripe_event_id = await _push_to_stripe(
                deployment=deployment,
                cost_cents=cost_cents,
                year=year,
                month=month,
            )
            if stripe_event_id:
                deployment.stripe_meter_event_id = stripe_event_id
                await db.commit()

            refreshed.append({
                "deployment_id": str(deployment.id),
                "org_id": str(deployment.org_id),
                "provider": provider_str,
                "region": deployment.region,
                "cost_usd_month": cost_cents / 100,
                "billable_usd_month": deployment.billable_cost_usd_month,
                "stripe_event_id": stripe_event_id,
            })

            logger.info(
                "cost_refreshed",
                deployment_id=str(deployment.id),
                org_id=str(deployment.org_id),
                cost_usd=cost_cents / 100,
            )

        except Exception as exc:
            logger.error(
                "cost_refresh_failed",
                deployment_id=str(deployment.id),
                error=str(exc),
            )

    return {
        "refreshed_count": len(refreshed),
        "year": year,
        "month": month,
        "deployments": refreshed,
    }


async def _push_to_stripe(
    deployment: Any,
    cost_cents: int,
    year: int,
    month: int,
) -> str | None:
    """
    Push deployment cost to Stripe as a metered usage record.

    Uses Stripe's `meter_events` API for pass-through billing.
    The customer is charged: cost_cents × (1 + markup / 100)

    Idempotency: uses deployment_id + year + month as idempotency key
    to prevent double-billing on retry.
    """
    try:
        import httpx

        from apps.api_server.config import get_settings

        settings = get_settings()
        if (
            not settings.stripe_secret_key
            or settings.stripe_secret_key.startswith("sk_test_replace")
        ):
            logger.debug("stripe_not_configured", deployment_id=str(deployment.id))
            return None

        billable_cents = int(deployment.billable_cost_usd_month * 100)
        if billable_cents <= 0:
            return None

        # Idempotency key: unique per deployment per billing month
        idempotency_key = f"algenta-cost-{deployment.id}-{year}-{month:02d}"

        # Stripe usage record for metered billing
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.stripe.com/v1/meter_events",
                auth=(settings.stripe_secret_key, ""),
                data={
                    "event_name": "algenta_cloud_cost",
                    # Set this to the actual Stripe customer ID.
                    "payload[stripe_customer_id]": deployment.org_id,
                    "payload[value]": str(billable_cents),
                    "identifier": idempotency_key,
                },
                headers={"Idempotency-Key": idempotency_key},
                timeout=10,
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                return data.get("identifier") or idempotency_key
            else:
                logger.warning(
                    "stripe_meter_event_failed",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                return None

    except Exception as exc:
        logger.error("stripe_push_failed", error=str(exc))
        return None


async def estimate_monthly_cost(
    provider: str,
    region: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Estimate monthly cloud cost before provisioning.
    Returns base cost + markup for the selected provider/region/config.

    Pricing is approximate and based on on-demand rates as of March 2026.
    Actual costs depend on usage patterns.
    """
    config = config or {}
    instance_size = config.get("instance_size", "small")

    # Approximate monthly costs (USD) by provider + size
    cost_table: dict[str, dict[str, float]] = {
        "aws": {
            "small":  150.0,   # ECS Fargate 2vCPU/4GB + RDS t4g.micro + ElastiCache t4g.micro
            "medium": 350.0,   # ECS 4vCPU/8GB + RDS t4g.small + ElastiCache t4g.small
            "large":  750.0,   # ECS 8vCPU/16GB + RDS t4g.medium + ElastiCache t4g.medium
        },
        "azure": {
            "small":  160.0,   # ACI 2vCPU/4GB + PostgreSQL B1ms + Redis C0
            "medium": 370.0,   # ACI 4vCPU/8GB + PostgreSQL B2s + Redis C1
            "large":  790.0,   # ACI 8vCPU/16GB + PostgreSQL B4ms + Redis C2
        },
        "gcp": {
            "small":  145.0,   # Cloud Run 2vCPU/4GB + Cloud SQL db-f1-micro + Memorystore M1
            "medium": 340.0,   # Cloud Run 4vCPU/8GB + Cloud SQL db-g1-small + Memorystore M2
            "large":  730.0,   # Cloud Run 8vCPU/16GB + Cloud SQL db-n1-standard-1 + Memorystore M3
        },
        "algenta_shared": {
            "small": 0.0,
            "medium": 0.0,
            "large": 0.0,
        },
    }

    base_cost = cost_table.get(provider, cost_table["aws"]).get(instance_size, 150.0)
    default_markup = 20.0
    markup_pct = config.get("billing_markup_pct", default_markup)
    billable = base_cost * (1 + markup_pct / 100)

    return {
        "provider": provider,
        "region": region,
        "instance_size": instance_size,
        "estimated_base_cost_usd_month": base_cost,
        "markup_pct": markup_pct,
        "estimated_billable_usd_month": billable,
        "note": (
            "Estimate based on on-demand pricing. "
            "Actual costs vary with usage. "
            "Billed monthly to your Stripe payment method."
        ),
    }
