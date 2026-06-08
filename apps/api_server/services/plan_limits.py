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
