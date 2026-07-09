"""Algenta pricing model — hosted per-seat + self-hosted per-node, and the free-forever-on-1-node guarantee.

Pins the business decision (research → docs/pricing-algenta.md):
  * algenta_pro   $29/mo   hosted, single seat
  * algenta_team  $39/seat hosted, per-seat (Stripe adjustable quantity)
  * algenta_selfhost $199/node  self-hosted, PER ACTIVE NODE (not per seat — fleet-abuse defense)
  * algenta_free  $0       always includes exactly ONE self-hosted node, non-commercial
"""
from __future__ import annotations

from apps.api_server.models.organization import OrgPlan
from apps.api_server.services import plan_limits
from apps.api_server.services.dormant_accounts import PAID_PLANS
from apps.api_server.services.entitlement_service import (
    resolve_entitlement,
    within_self_service_ceiling,
)
from apps.api_server.services.product_registry import product_for_plan


# ── prices are the ones the market research landed on ───────────────────────────────
def test_hosted_and_selfhost_prices() -> None:
    assert plan_limits.get("algenta_pro").price_usd_month == 29
    assert plan_limits.get("algenta_team").price_usd_month == 39      # per SEAT
    assert plan_limits.get("algenta_selfhost").price_usd_month == 199  # per NODE


# ── free forever on exactly one self-hosted node, non-commercial ────────────────────
def test_free_tier_is_one_node_forever_noncommercial() -> None:
    cfg = plan_limits.get("algenta_free")
    assert cfg.price_usd_month == 0
    assert cfg.local_runtime is True          # can run the local engine
    assert cfg.devices == 1                    # exactly one device/node

    ent = resolve_entitlement("algenta_free")
    assert ent.active_node_limit == 1          # one running node
    assert ent.named_seat_limit == 1
    assert ent.commercial_use is False         # free = non-commercial
    assert ent.redistribution_allowed is False


# ── self-host is per-node, commercial, finite-capped, and self-serve-sellable ────────
def test_selfhost_entitlement_is_per_node_and_within_ceiling() -> None:
    ent = resolve_entitlement("algenta_selfhost")
    assert ent.deployment_class == "server"
    assert ent.commercial_use is True
    assert ent.redistribution_allowed is False
    assert ent.active_node_limit >= 1          # a running-node ceiling exists (finite, not 0/uncapped)
    assert ent.concurrent_worker_limit > 0     # finite worker cap (the only offline-enforced unit)
    # A single self-serve self-host node stays sellable without a contract; bigger = enterprise site license.
    assert within_self_service_ceiling(ent) is True
    assert "algenta" in ent.products           # grants the algenta product edition


# ── wiring: enum, billing product resolution, paid-plan bookkeeping ─────────────────
def test_selfhost_plan_is_wired_end_to_end() -> None:
    assert OrgPlan.ALGENTA_SELFHOST.value == "algenta_selfhost"
    # billing/product resolution routes it to the algenta product (so the billing gate applies).
    assert product_for_plan("algenta_selfhost") == "algenta"
    # a paying self-host org must never be dormant-deleted...
    assert "algenta_selfhost" in PAID_PLANS
    # ...while the free tier remains dormant-deletable (not a payer).
    assert "algenta_free" not in PAID_PLANS


def test_selfhost_has_a_stripe_price_slot() -> None:
    from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

    # the key exists in the price map (value is None until the owner sets the real Stripe price id).
    assert "algenta_selfhost" in list(PLAN_PRICE_IDS)
