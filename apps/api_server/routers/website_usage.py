"""Website/dashboard usage read — Supabase-authenticated.

The read half of metering: the account portal's Billing card shows how many
GITHUB FIXES of the plan's monthly allowance the org has used. Fixes are the
unit customers are billed/limited by — internal pipeline steps (triage,
snapshot, graph, simulate…) are components of a fix, never charged separately,
so they are deliberately NOT counted here. Everything returned is MEASURED or
plan CONFIG — nothing invented:

  * ``used``  — count of fix-completing usage_records this billing period
                (tool_name ∈ {apply_repository, run_repository_pipeline}; each
                is its own HTTP entry point recorded exactly once per fix).
  * ``quota`` — the plan's monthly fix allowance: the Stripe product's
                ``cloud_fix_prs`` metadata for paid plans ("unlimited" ⇒ None),
                or FREE_FIXES_PER_MONTH (env, default 20) for free orgs.
  * ``billing_period`` / ``plan`` / ``unit`` — the scope of those numbers.

Authenticated by the user's Supabase access_token like its ``/account/*``
siblings, org-scoped via the shared website-identity path. Inert until
``SUPABASE_URL`` is configured → 503.
"""

from __future__ import annotations

import os
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.usage_record import UsageEndpoint, UsageRecord
from apps.api_server.services import website_identity
from apps.api_server.services.quota_service import _current_billing_period

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["account"])

# The fix-COMPLETING tools. Each is a distinct HTTP entry point whose usage row
# is written once per successful fix (apply directly, or the full pipeline);
# internal steps carry other tool_names and never count toward the allowance.
_FIX_TOOLS = ("apply_repository", "run_repository_pipeline")

# Free-plan monthly fix allowance — same product config the portal shows.
_FREE_FIXES = int(os.getenv("CODNA_FREE_FIXES_PER_MONTH", "20") or "20")


async def _plan_fix_allowance(plan: str, source: str) -> int | None:
    """The plan's monthly fix allowance. Paid plans: the Stripe product's
    ``cloud_fix_prs`` metadata via the cached catalog ("unlimited" ⇒ None).
    Free (or a plan without a Stripe product): the FREE allowance."""
    if plan in ("free", "developer"):
        return _FREE_FIXES
    from apps.api_server.services.stripe_catalog import list_plans

    try:
        for entry in await list_plans(source):
            if entry.get("plan") == plan:
                raw = entry.get("cloud_fix_prs")
                if raw is None or str(raw).lower() == "unlimited":
                    return None
                try:
                    return int(str(raw))
                except ValueError:
                    return None
    except Exception:  # noqa: BLE001 — catalog down ⇒ report usage without a quota
        logger.warning("account_usage_allowance_lookup_failed", plan=plan)
    return None


@router.get(
    "/account/usage",
    summary="Current-period GitHub fixes used vs plan allowance (website / Supabase auth)",
    description=(
        "Returns the caller's org fix count for the current billing period — only "
        "fix-completing events count (pipeline runs / applies); internal steps like "
        "simulations never do — plus the plan's fix allowance (Stripe product "
        "metadata, or the free allowance). Powers the dashboard's usage meter."
    ),
)
async def account_usage(
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"  # private account data — never cache
    org, _identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )

    period = _current_billing_period()
    used = (
        await db.execute(
            select(func.count(UsageRecord.id)).where(
                UsageRecord.org_id == org.id,
                UsageRecord.billing_period == period,
                UsageRecord.endpoint == UsageEndpoint.REPOSITORY,
                UsageRecord.tool_name.in_(_FIX_TOOLS),
            )
        )
    ).scalar_one()

    plan = org.plan.value if hasattr(org.plan, "value") else str(org.plan)
    # Sibling products' plans carry their prefix (telys_pro → source "telys");
    # codna plans are bare (pro/team/…) → source "codna".
    source = plan.split("_", 1)[0] if "_" in plan else "codna"
    quota = await _plan_fix_allowance(plan, source)
    unlimited = quota is None

    return {
        "billing_period": period,
        "plan": plan,
        "unit": "fixes",
        "used": int(used),
        "quota": quota,
        "unlimited": unlimited,
        "remaining": (None if quota is None else max(0, quota - int(used))),
    }
