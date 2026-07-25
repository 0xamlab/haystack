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
    rate_per_minute: int  # 0 = unlimited
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
    # Cohenta (campaign orchestration) — mirrors the telys developer/pro/team ladder: a free, no-card,
    # 1-device tier plus paid Pro Runner (solo) and Team (per-seat) tiers. Numbers track telys until
    # cohenta earns its own pricing page.
    "cohenta_free": PlanConfig(
        display_name="COHENTA FREE",
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
    "cohenta_pro_runner": PlanConfig(
        display_name="COHENTA PRO RUNNER", price_usd_month=25, executions_month=500_000,
        devices=3, local_runtime=True, rate_per_minute=300, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=False,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=4, storage_gb=10,
        llm_spend_cap_usd_month=0,
    ),
    "cohenta_team": PlanConfig(
        display_name="COHENTA TEAM", price_usd_month=99, executions_month=500_000,
        devices=10, local_runtime=True, rate_per_minute=1000, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=True,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=8, storage_gb=10,
        llm_spend_cap_usd_month=0,
    ),
    # Algenta (the engine as a product). Execution is unmetered at every tier: no monthly decision
    # quota, plan request-rate cap, or async-job cap. Tiers differ only by licensed devices, seats,
    # workers, and governance/support. Request-shape bounds remain uniform safety constraints.
    # local_runtime is ON at every tier; price_usd_month is display-only (Stripe is authoritative).
    # One paid unit licenses one device. Stripe quantity raises the org ceiling; before that quantity
    # is synchronized, every Algenta plan fails safely to one device rather than granting a fleet.
    "algenta_free": PlanConfig(
        display_name="ALGENTA FREE",
        price_usd_month=0,
        executions_month=0,
        devices=1,
        local_runtime=True,
        rate_per_minute=0,
        async_jobs=True,
        webhooks=True,
        max_runs_per_call=1_000_000,
        max_batch=100,
        audit_trail=False,
        rbac=False,
        permitted_modules=["*"],
        credit_batch_size=1_000,
        concurrent_jobs=0,
        storage_gb=0,
        llm_spend_cap_usd_month=0,
    ),
    # Pro — self-hosted, billed PER DEVICE ($99/device/mo, $948/device/yr; Stripe usage=licensed,
    # quantity = number of licensed devices). 5 workers/device, 1 seat. price_usd_month is the per-device
    # monthly price; the bill = $99 × devices.
    "algenta_pro": PlanConfig(
        display_name="ALGENTA PRO", price_usd_month=99, executions_month=0,
        devices=1, local_runtime=True, rate_per_minute=0, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=False,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=0, storage_gb=0,
        llm_spend_cap_usd_month=0,
    ),
    # Team — self-hosted, billed PER DEVICE ($499/device/mo, $4788/device/yr; Stripe usage=licensed,
    # quantity = number of licensed devices). 20 workers/device, 15 seats. price_usd_month is the
    # per-device monthly price; the bill = $499 × devices.
    "algenta_team": PlanConfig(
        display_name="ALGENTA TEAM", price_usd_month=499, executions_month=0,
        devices=1, local_runtime=True, rate_per_minute=0, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=True,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=0, storage_gb=0,
        llm_spend_cap_usd_month=0,
    ),
    # SQAI (on-device structured-query runtime) — mirrors the telys tier capacities initially.
    # sqai_developer: local runtime ENABLED (can register 1 device), no card, non-commercial.
    "sqai_developer": PlanConfig(
        display_name="SQAI DEVELOPER",
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
    "sqai_pro": PlanConfig(
        display_name="SQAI PRO", price_usd_month=25, executions_month=500_000,
        devices=3, local_runtime=True, rate_per_minute=300, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=False,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=4, storage_gb=10,
        llm_spend_cap_usd_month=0,
    ),
    "sqai_team": PlanConfig(
        display_name="SQAI TEAM", price_usd_month=99, executions_month=500_000,
        devices=10, local_runtime=True, rate_per_minute=1000, async_jobs=True, webhooks=True,
        max_runs_per_call=1_000_000, max_batch=100, audit_trail=True, rbac=True,
        permitted_modules=["*"], credit_batch_size=10_000, concurrent_jobs=8, storage_gb=10,
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
        rate_per_minute=0,
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


# Plans billed PER DEVICE: the Stripe subscription quantity IS the licensed device count (stored on
# ``Organization.licensed_devices``), so the org ceiling — not the static PlanConfig.devices — bounds
# how many devices they can register. Per-seat plans (codna ``team`` / ``telys_team``) are NOT here.
PER_DEVICE_PLANS = frozenset({"algenta_pro", "algenta_team"})
UNMETERED_EXECUTION_PLANS = frozenset(
    {"algenta_free", "algenta_pro", "algenta_team", "enterprise"}
)


def is_per_device_plan(plan: str) -> bool:
    """True if the plan is billed per device (Stripe quantity = licensed device count)."""
    return (plan or "").strip().lower() in PER_DEVICE_PLANS


def is_unmetered_execution_plan(plan: str) -> bool:
    """True when execution volume must never be billed or quota-enforced."""
    return (plan or "").strip().lower() in UNMETERED_EXECUTION_PLANS


def effective_device_limit(
    plan: str, api_key_device_limit: int | None, org_ceiling: int | None = None
) -> int:
    """
    Resolve the enforced per-key device limit under the current plan.

    The OUTER ceiling is the org's licensed device count (``org_ceiling``, from the Stripe quantity)
    for per-device plans when set (>0); otherwise the static plan cap. A key may narrow that ceiling
    further. ``0`` always means unlimited, but only plans with unlimited devices may honor it. A
    missing/zero ``org_ceiling`` falls back to the plan cap — never a lockout.
    """
    if not local_runtime_allowed(plan):
        return 0

    outer = org_ceiling if (org_ceiling is not None and org_ceiling > 0) else device_limit(plan)
    if api_key_device_limit is None:
        return outer
    if api_key_device_limit < 0:
        raise ValueError("api_key_device_limit must be greater than or equal to 0.")
    if outer == 0:
        return api_key_device_limit
    if api_key_device_limit == 0:
        return outer
    return min(api_key_device_limit, outer)


def validate_api_key_device_limit(
    plan: str, requested_device_limit: int | None, org_ceiling: int | None = None
) -> int | None:
    """
    Validate a configured per-key device cap against the current plan / org ceiling.

    For per-device plans the ceiling is the org's licensed device count (``org_ceiling``) when set;
    otherwise the static plan cap. A per-key override is a WITHIN-org sub-allocation, so it may be up
    to the ceiling. Returns the stored override value. ``None`` means inherit the ceiling default.
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

    cap = org_ceiling if (org_ceiling is not None and org_ceiling > 0) else device_limit(plan)
    if cap == 0:
        return requested_device_limit
    if requested_device_limit == 0:
        raise ValueError(
            f"Plan '{plan}' does not support unlimited devices per key. Maximum is {cap}."
        )
    if requested_device_limit > cap:
        raise ValueError(f"Plan '{plan}' allows at most {cap} device(s) per key.")
    return requested_device_limit


def local_runtime_allowed(plan: str) -> bool:
    """True if this plan permits device registration and local runtime use."""
    return get(plan).local_runtime


def permitted_modules(plan: str) -> list[str]:
    return get(plan).permitted_modules


def credit_batch_size(plan: str) -> int:
    """Credits issued per /v1/credits/refresh call."""
    return get(plan).credit_batch_size


# Per-device concurrent worker cap — the "N workers per device" on the pricing page. This is the
# SINGLE SOURCE OF TRUTH for that number: it flows into the signed license claims
# (entitlement_service.to_license_claims) and is enforced offline by the runtime WorkerBroker
# (apps/runtime/worker_broker.py). Adjust a value here and both the signer and every node follow on
# the next license renewal — no other edit needed. 0 = unlimited (enterprise/negotiated).
#
# Kept as a dedicated map (not per-PlanConfig) so the commercial worker ladder is legible + trivial
# to retune. Pricing (algenta.ai/pricing): Community 1 · Pro 5 · Team 20 · Enterprise unlimited.
_WORKER_LIMITS: dict[str, int] = {
    "free": 1,
    "telys_developer": 1,
    "algenta_free": 1,
    "cohenta_free": 1,
    "telys_pro": 5,
    "algenta_pro": 5,
    "cohenta_pro_runner": 5,
    "developer": 5,
    "pro": 5,
    "proplus": 10,
    "telys_team": 20,
    "algenta_team": 20,
    "cohenta_team": 20,
    "sqai_developer": 1,
    "sqai_pro": 5,
    "sqai_team": 20,
    "team": 20,
    "ultra": 20,
    "enterprise": 0,  # negotiated / unlimited
}


def worker_limit(plan: str) -> int:
    """Per-device concurrent worker cap for a plan. 0 = unlimited.

    Single source of truth consumed by entitlement_service (license claims) and the runtime
    WorkerBroker. Unknown plans fall back to the free cap (fail-closed to the smallest cap).
    """
    return _WORKER_LIMITS.get(plan, _WORKER_LIMITS["free"])
