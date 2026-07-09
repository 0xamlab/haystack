"""
Plan limits — single source of truth for all tier enforcement.

Pricing tiers used by the current API/test contract:
  STARTER    $0          cloud API only · 500 executions/mo
  PRO        $99/dev/mo  full runtime · 10k/100k executions/mo legacy tiers
  TEAM       $499/mo     shared runtime · 1M executions/mo
  ENTERPRISE custom      private runtime · unlimited devices · unlimited executions

Internal plan names map to display tiers:
  free       → STARTER
  developer  → PRO   (legacy name, same limits)
  pro        → PRO
  team       → TEAM
  enterprise → ENTERPRISE

This module is imported by:
  - quota_service.py   (execution quota enforcement)
  - device_service.py  (device count enforcement)
  - devices.py router  (cloud-only guard on /v1/device/register)
  - license.py         (permitted_modules in JWT)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanConfig:
    display_name: str
    price_usd_month: int | None  # None = custom/sales
    executions_month: int  # 0 = unlimited
    devices: int  # 0 = unlimited
    local_runtime: bool  # can register devices / use local daemon
    rate_per_minute: int
    async_jobs: bool
    webhooks: bool
    max_runs_per_call: int
    max_batch: int
    audit_trail: bool
    rbac: bool
    permitted_modules: list[str]  # ["*"] = all, list of names = restricted
    credit_batch_size: int  # executions issued per /v1/credits/refresh call
    # Free-tier cost caps (Wave 2). 0 = unlimited. concurrent_jobs is ENFORCED on async job submit
    # (job_service.enforce_concurrent_jobs). storage_gb + llm_spend_cap_usd_month are DEFINED here and
    # surfaced via /v1/limits, but their ENFORCEMENT lands with their accounting backends — storage
    # needs per-org object-store accounting (not built); llm_spend is the managed-LLM meter (D3/PR-5).
    concurrent_jobs: int = 0
    storage_gb: int = 0
    llm_spend_cap_usd_month: int = 0


_PLANS: dict[str, PlanConfig] = {
    "free": PlanConfig(
        display_name="STARTER",
        price_usd_month=0,
        executions_month=10_000,
        devices=0,  # cloud API only — no local runtime
        local_runtime=False,
        rate_per_minute=60,
        async_jobs=False,
        webhooks=False,
        max_runs_per_call=10_000,
        max_batch=10,
        audit_trail=False,
        rbac=False,
        permitted_modules=["*"],  # all modules via cloud API
        credit_batch_size=1_000,
        concurrent_jobs=1,
        storage_gb=1,
        llm_spend_cap_usd_month=5,
    ),
    # Telys free developer plan — local runtime ENABLED (can register 1 device), no card, non-commercial.
    "telys_developer": PlanConfig(
        display_name="TELYS DEVELOPER",
        price_usd_month=0,
        executions_month=10_000,
        devices=1,
        local_runtime=True,
        rate_per_minute=60,
        async_jobs=False,
        webhooks=False,
        max_runs_per_call=10_000,
        max_batch=10,
        audit_trail=False,
        rbac=False,
        permitted_modules=["*"],
        credit_batch_size=1_000,
        concurrent_jobs=1,
        storage_gb=1,
        llm_spend_cap_usd_month=0,
    ),
    "telys_pro": PlanConfig(
        display_name="TELYS PRO", price_usd_month=25, executions_month=500_000,
        devices=3, local_runtime=True, rate_per_minute=300, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=False,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=4, storage_gb=10,
        llm_spend_cap_usd_month=0,
    ),
    "telys_team": PlanConfig(
        display_name="TELYS TEAM", price_usd_month=99, executions_month=500_000,
        devices=10, local_runtime=True, rate_per_minute=1000, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=True,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=8, storage_gb=10,
        llm_spend_cap_usd_month=0,
    ),
    # Algenta (the engine as a product). local_runtime is ON at every tier (the bundled in-process runtime
    # is the whole point). price_usd_month is a display value; the real charge is the Stripe price.
    # Two priced axes (see docs/pricing-algenta.md): HOSTED is per-SEAT (control plane counts seats);
    # SELF-HOSTED is per-NODE (once the customer holds the binary, seats are unenforceable — the only
    # enforceable unit is the running engine, capped by the active-node-cap). algenta_free is the free-
    # FOREVER, no-card baseline: it always includes exactly ONE self-hosted node, non-commercial.
    "algenta_free": PlanConfig(
        display_name="ALGENTA FREE",
        price_usd_month=0,
        executions_month=10_000,
        devices=1,
        local_runtime=True,
        rate_per_minute=60,
        async_jobs=False,
        webhooks=False,
        max_runs_per_call=10_000,
        max_batch=10,
        audit_trail=False,
        rbac=False,
        permitted_modules=["*"],
        credit_batch_size=1_000,
        concurrent_jobs=1,
        storage_gb=1,
        llm_spend_cap_usd_month=0,
    ),
    # Hosted, single commercial seat. Anchored to the repo-intelligence band (CodeRabbit/Greptile/Qodo
    # $24–30); $29 is the top charm point of that band, below Codna proplus $60.
    "algenta_pro": PlanConfig(
        display_name="ALGENTA PRO", price_usd_month=29, executions_month=500_000,
        devices=3, local_runtime=True, rate_per_minute=300, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=False,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=4, storage_gb=10,
        llm_spend_cap_usd_month=0,
    ),
    # Hosted, PER-SEAT. price_usd_month is the per-seat price; the bill = price × seats (Stripe adjustable
    # quantity, see stripe_service.create_checkout_session). Market Team band is $30–40/seat (Cursor/
    # Graphite $40, Greptile $30); $39 lands at center. Was a $99 flat plan (~$20 effective/seat).
    "algenta_team": PlanConfig(
        display_name="ALGENTA TEAM", price_usd_month=39, executions_month=500_000,
        devices=10, local_runtime=True, rate_per_minute=1000, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=True,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=8, storage_gb=10,
        llm_spend_cap_usd_month=0,
    ),
    # SELF-HOSTED, PER ACTIVE NODE. price_usd_month is the price per running engine node ($199/node/mo).
    # The enforceable unit self-hosted is the node (device), NOT the seat — otherwise one cheap license
    # runs across an entire fleet. Enforced by the active-node-cap (device_service.node_admission_block_count,
    # ALGENTA_ENFORCE_ACTIVE_NODE_CAP=1) for connected deployments; multi-node / air-gapped / >2-node self-
    # host is minted as an OFFLINE per-node license (scripts/issue_offline_license.py --paid-selfhost, which
    # requires finite caps + non-OEM via scripts/license_mint_guard), NEVER an OEM license. seats within a
    # node are not separately charged. anthropic/openai/google are BYOK (llm_spend_cap=0).
    "algenta_selfhost": PlanConfig(
        display_name="ALGENTA SELF-HOSTED", price_usd_month=199, executions_month=2_000_000,
        devices=1, local_runtime=True, rate_per_minute=2000, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=True,
        permitted_modules=["*"], credit_batch_size=25_000, concurrent_jobs=20, storage_gb=100,
        llm_spend_cap_usd_month=0,
    ),
    "developer": PlanConfig(
        display_name="PRO",
        price_usd_month=99,
        executions_month=500_000,
        devices=5,
        local_runtime=True,
        rate_per_minute=300,
        async_jobs=True,
        webhooks=True,
        max_runs_per_call=1_000_000,
        max_batch=100,
        audit_trail=True,
        rbac=False,
        permitted_modules=["*"],
        credit_batch_size=10_000,
        concurrent_jobs=5,
        storage_gb=10,
        llm_spend_cap_usd_month=50,
    ),
    "pro": PlanConfig(
        display_name="PRO",
        price_usd_month=99,
        executions_month=500_000,
        devices=5,
        local_runtime=True,
        rate_per_minute=1_000,
        async_jobs=True,
        webhooks=True,
        max_runs_per_call=1_000_000,
        max_batch=100,
        audit_trail=True,
        rbac=False,
        permitted_modules=["*"],
        credit_batch_size=10_000,
        concurrent_jobs=20,
        storage_gb=100,
        llm_spend_cap_usd_month=200,
    ),
    # Power-solo ($60) and max-solo ($200) — single seat, escalating managed-usage headroom
    # (Codna's Cursor Pro+/Ultra analogues). Not multi-seat (see team_seats).
    "proplus": PlanConfig(
        display_name="PRO+", price_usd_month=60, executions_month=2_000_000,
        devices=5, local_runtime=True, rate_per_minute=2_000, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=False,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=40, storage_gb=200,
        llm_spend_cap_usd_month=500,
    ),
    "ultra": PlanConfig(
        display_name="ULTRA", price_usd_month=200, executions_month=10_000_000,
        devices=10, local_runtime=True, rate_per_minute=5_000, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=False,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=100, storage_gb=500,
        llm_spend_cap_usd_month=2_000,
    ),
    "team": PlanConfig(
        display_name="TEAM",
        price_usd_month=499,
        executions_month=1_000_000,
        devices=25,
        local_runtime=True,
        rate_per_minute=5_000,
        async_jobs=True,
        webhooks=True,
        max_runs_per_call=1_000_000,
        max_batch=100,
        audit_trail=True,
        rbac=True,
        permitted_modules=["*"],
        credit_batch_size=25_000,
        concurrent_jobs=50,
        storage_gb=1_000,
        llm_spend_cap_usd_month=1_000,
    ),
    "enterprise": PlanConfig(
        display_name="ENTERPRISE",
        price_usd_month=None,
        executions_month=0,  # unlimited
        devices=0,  # unlimited
        local_runtime=True,
        rate_per_minute=10_000,
        async_jobs=True,
        webhooks=True,
        max_runs_per_call=1_000_000,
        max_batch=100,
        audit_trail=True,
        rbac=True,
        permitted_modules=["*"],
        credit_batch_size=100_000,
        concurrent_jobs=0,
        storage_gb=0,
        llm_spend_cap_usd_month=0,
    ),
}

_DEFAULT = _PLANS["free"]


def get(plan: str) -> PlanConfig:
    """Return PlanConfig for the given plan name. Falls back to free."""
    return _PLANS.get(plan, _DEFAULT)


def execution_quota(plan: str) -> int:
    """Monthly execution limit. 0 = unlimited."""
    return get(plan).executions_month


def device_limit(plan: str) -> int:
    """Max registered devices. 0 = unlimited."""
    return get(plan).devices


def effective_device_limit(plan: str, api_key_device_limit: int | None) -> int:
    """
    Resolve the enforced per-key device limit under the current plan.

    The plan remains the outer ceiling. A key may narrow that ceiling further.
    `0` always means unlimited, but only plans with unlimited devices may honor it.
    """
    if not local_runtime_allowed(plan):
        return 0

    plan_cap = device_limit(plan)
    if api_key_device_limit is None:
        return plan_cap
    if api_key_device_limit < 0:
        raise ValueError("api_key_device_limit must be greater than or equal to 0.")
    if plan_cap == 0:
        return api_key_device_limit
    if api_key_device_limit == 0:
        return plan_cap
    return min(api_key_device_limit, plan_cap)


def validate_api_key_device_limit(plan: str, requested_device_limit: int | None) -> int | None:
    """
    Validate a configured per-key device cap against the current plan.

    Returns the stored override value. `None` means inherit the plan default.
    """
    if requested_device_limit is None:
        return None
    if requested_device_limit < 0:
        raise ValueError("device_limit must be greater than or equal to 0.")
    if not local_runtime_allowed(plan):
        raise ValueError(
            f"Plan '{plan}' does not include local runtime access, "
            "so it cannot set a per-key device limit."
        )

    plan_cap = device_limit(plan)
    if plan_cap == 0:
        return requested_device_limit
    if requested_device_limit == 0:
        raise ValueError(
            f"Plan '{plan}' does not support unlimited devices per key. Maximum is {plan_cap}."
        )
    if requested_device_limit > plan_cap:
        raise ValueError(f"Plan '{plan}' allows at most {plan_cap} device(s) per key.")
    return requested_device_limit


def local_runtime_allowed(plan: str) -> bool:
    """True if this plan permits device registration and local runtime use."""
    return get(plan).local_runtime


def permitted_modules(plan: str) -> list[str]:
    return get(plan).permitted_modules


def credit_batch_size(plan: str) -> int:
    """Credits issued per /v1/credits/refresh call."""
    return get(plan).credit_batch_size
