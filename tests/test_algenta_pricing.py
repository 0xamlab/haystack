"""Algenta pricing model — the LIVE pricing card (https://algenta.ai/pricing, already in Stripe).

Everything is self-hosted and licensed PER DEVICE (Stripe usage=licensed, quantity = # devices):

  * Community  algenta_free  $0            1 device  · 1 worker/device  · 1 seat   · non-commercial
  * Pro        algenta_pro   $99/device/mo             5 workers/device · 1 seat   · commercial
  * Team       algenta_team  $499/device/mo            20 workers/device · 15 seats · commercial
  * Enterprise enterprise    from $50k/yr  air-gapped · fleet · unlimited

There is NO separate self-host plan — the old `algenta_selfhost` ($199/node) tier was removed;
Pro/Team ARE the per-device self-host tiers.
"""

from __future__ import annotations

import pytest

from apps.api_server.models.organization import OrgPlan
from apps.api_server.routers.account import limits
from apps.api_server.services import plan_limits
from apps.api_server.services.dormant_accounts import PAID_PLANS
from apps.api_server.services.entitlement_service import resolve_entitlement
from apps.api_server.services.product_registry import product_for_plan
from apps.api_server.services.team_seats import seat_limit


# ── prices match the live pricing card + the Stripe monthly prices ──────────────────
def test_prices_match_the_card() -> None:
    assert plan_limits.get("algenta_free").price_usd_month == 0
    assert plan_limits.get("algenta_pro").price_usd_month == 99  # $99/device/mo
    assert plan_limits.get("algenta_team").price_usd_month == 499  # $499/device/mo


def test_one_unsynced_paid_unit_never_grants_multiple_devices() -> None:
    assert plan_limits.device_limit("algenta_free") == 1
    assert plan_limits.device_limit("algenta_pro") == 1
    assert plan_limits.device_limit("algenta_team") == 1


# ── per-device worker concurrency: Community 1 · Pro 5 · Team 20 ─────────────────────
def test_worker_caps_per_device() -> None:
    assert plan_limits.worker_limit("algenta_free") == 1
    assert plan_limits.worker_limit("algenta_pro") == 5
    assert plan_limits.worker_limit("algenta_team") == 20
    assert plan_limits.worker_limit("enterprise") == 0  # negotiated / unlimited


@pytest.mark.anyio
async def test_limits_endpoint_matches_algenta_enforcement() -> None:
    expected = {
        "algenta_free": (0, 0, 1_000_000, 100, 0),
        "algenta_pro": (0, 0, 1_000_000, 100, 0),
        "algenta_team": (0, 0, 1_000_000, 100, 0),
        "enterprise": (0, 0, 1_000_000, 100, 0),
    }
    for plan, values in expected.items():
        response = await limits({"plan": plan})  # type: ignore[arg-type]
        assert (
            response.max_simulations_per_month,
            response.rate_limit_per_minute,
            response.max_runs_per_simulation,
            response.max_batch_items,
            response.concurrent_jobs,
        ) == values


# ── seats: Community 1 · Pro 1 · Team 15 (fixed bundle; devices are the billing unit) ─
def test_seat_caps() -> None:
    assert seat_limit("algenta_free") == 1
    assert seat_limit("algenta_pro") == 1
    assert seat_limit("algenta_team") == 15
    assert resolve_entitlement("algenta_team").named_seat_limit == 15
    assert resolve_entitlement("algenta_free").named_seat_limit == 1
    assert resolve_entitlement("algenta_pro").named_seat_limit == 1


# ── Community: free forever, self-hosted, exactly one device, non-commercial ─────────
def test_community_is_one_device_forever_noncommercial() -> None:
    cfg = plan_limits.get("algenta_free")
    assert cfg.price_usd_month == 0
    assert cfg.local_runtime is True  # the full engine on your hardware
    assert cfg.devices == 1

    ent = resolve_entitlement("algenta_free")
    assert ent.active_node_limit == 1
    assert ent.named_seat_limit == 1
    assert ent.commercial_use is False
    assert ent.redistribution_allowed is False


# ── Pro / Team are commercial, self-hosted, and grant the algenta product edition ────
def test_paid_tiers_are_commercial_self_hosted() -> None:
    for plan in ("algenta_pro", "algenta_team"):
        cfg = plan_limits.get(plan)
        assert cfg.local_runtime is True  # self-hosted — runs on the customer's hardware
        ent = resolve_entitlement(plan)
        assert ent.commercial_use is True
        assert ent.redistribution_allowed is False
        assert "algenta" in ent.products
        # billing/product resolution routes paid tiers to the algenta product (billing gate applies).
        assert product_for_plan(plan) == "algenta"


# ── paid-plan bookkeeping: payers are never dormant-deleted; Community is ────────────
def test_paid_plan_bookkeeping() -> None:
    assert "algenta_pro" in PAID_PLANS
    assert "algenta_team" in PAID_PLANS
    assert "algenta_free" not in PAID_PLANS  # Community is dormant-deletable (not a payer)


# ── the paid tiers have a Stripe price slot (real ids set by the owner / already live) ─
def test_paid_tiers_have_stripe_price_slots() -> None:
    from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

    assert "algenta_pro" in list(PLAN_PRICE_IDS)
    assert "algenta_team" in list(PLAN_PRICE_IDS)


# ── the removed self-host tier must be gone end-to-end ──────────────────────────────
def test_algenta_selfhost_is_removed() -> None:
    # not a plan value anymore
    assert not hasattr(OrgPlan, "ALGENTA_SELFHOST")
    assert "algenta_selfhost" not in {p.value for p in OrgPlan}
    # not offered anywhere
    from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

    assert "algenta_selfhost" not in list(PLAN_PRICE_IDS)
    assert "algenta_selfhost" not in PAID_PLANS
    # falls back to Community-equivalent (empty/free) if ever referenced, never a paid grant
    assert resolve_entitlement("algenta_selfhost").products == {}
