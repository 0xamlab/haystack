"""Dynamic plan catalog from Stripe — so pricing pages + the account billing card render plan
TITLES, PRICES, DESCRIPTIONS, and FEATURE bullets straight from Stripe (never hardcoded).

Lists active prices (with their expanded product), filtered to one app by product.metadata.source
(codna|telys|…), and shapes them for the UI. Cached in-process with a short TTL so the page is
dynamic but cheap; the Stripe product.updated/price.updated webhooks can bust it later. Free +
Enterprise have no Stripe price, so callers add those bookends themselves.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from apps.api_server.services.stripe_service import _is_placeholder, _stripe_headers, stripe_api_request

log = structlog.get_logger(__name__)

_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_TTL_S = 300.0


def _shape(price: dict[str, Any]) -> dict[str, Any] | None:
    prod = price.get("product")
    if not isinstance(prod, dict) or not prod.get("active"):
        return None
    pmeta = prod.get("metadata") or {}
    features = [f.get("name") for f in (prod.get("marketing_features") or []) if f.get("name")]
    return {
        # The Stripe price id, kept so checkout can resolve a plan from the SAME catalog the pricing
        # page renders. `list_plans` strips it before returning, so the public payload is unchanged.
        # Without it, plan -> price was a hand-maintained map (one `stripe_price_<plan>` setting plus
        # an allow-list entry per plan), and any plan added to Stripe was ADVERTISED by this catalog
        # while checkout refused it as `invalid_plan` — which is exactly what happened to the
        # `*_server` tiers.
        "id": price.get("id"),
        "plan": (price.get("metadata") or {}).get("plan") or pmeta.get("plan"),
        "name": prod.get("name"),
        "description": prod.get("description"),
        "features": features,
        "price_usd": round((price.get("unit_amount") or 0) / 100, 2),
        "currency": (price.get("currency") or "usd").upper(),
        "interval": (price.get("recurring") or {}).get("interval"),
        "lookup_key": price.get("lookup_key"),
        "source": pmeta.get("source"),
        # The user-facing fix allowance ("150" | "unlimited" | absent) — the
        # unit customers are billed/limited by (simulations etc. are internal).
        "cloud_fix_prs": pmeta.get("cloud_fix_prs"),
    }


async def list_plans(app: str, *, use_cache: bool = True) -> list[dict[str, Any]]:
    """Active Stripe plans for `app` (by product.metadata.source), price-sorted, shaped for the UI."""
    now = time.monotonic()
    if use_cache and app in _CACHE and now - _CACHE[app][0] < _TTL_S:
        return _CACHE[app][1]

    resp = await stripe_api_request(
        method="GET",
        path="/v1/prices?active=true&limit=100&expand[]=data.product",
        surface="billing_catalog",
        # stripe_api_request does NOT auto-attach auth — each caller passes it (like checkout/portal).
        # Without this the catalog call hit Stripe unauthenticated → 401 → empty plans.
        headers=_stripe_headers(),
    )
    data = resp.json().get("data", []) if resp.status_code < 400 else []
    plans: list[dict[str, Any]] = []
    for price in data:
        if price.get("lookup_key") and _is_placeholder(price.get("lookup_key")):
            continue
        shaped = _shape(price)
        if shaped and shaped["source"] == app:
            plans.append(shaped)
    plans.sort(key=lambda p: p["price_usd"])
    _CACHE[app] = (now, plans)
    return plans


async def resolve_price(app: str, plan: str, interval: str = "month") -> dict[str, Any] | None:
    """The Stripe price for `(app, plan, interval)` straight from the catalogue, or ``None``.

    This is the mapping that was missing. Checkout resolved a plan through `PLAN_PRICE_IDS`, a
    hand-maintained dict of `plan -> settings.stripe_price_<plan>`, so adding a plan to Stripe took
    four separate edits (a config field, a mapping entry, an allow-list entry, and the env var in
    production). Skip any one and the plan is listed on the pricing page and refused at checkout.
    Measured on the live host: `/billing/plans` advertises `algenta_server` at $600/mo and
    `telys_server`, and neither is in the allow-list or the mapping, so both were unbuyable.

    That map also had no INTERVAL, holding one price id per plan — so the annual prices in the
    catalogue (`algenta_pro_annual`, $948) were unreachable through checkout even though the account
    portal already links `/checkout?app=...&plan=...&interval=year`.

    Resolving from the catalogue fixes the class rather than the two instances: a plan that Stripe
    sells is a plan this engine can charge for, with no code change and nothing to keep in sync.
    `interval` is matched exactly rather than defaulted at the Stripe end, because silently billing
    a customer monthly when they asked for annual is worse than refusing.
    """
    wanted_plan = (plan or "").strip().lower()
    wanted_interval = (interval or "month").strip().lower()
    if not wanted_plan:
        return None
    for candidate in await list_plans(app):
        if (candidate.get("plan") or "").strip().lower() != wanted_plan:
            continue
        if (candidate.get("interval") or "").strip().lower() != wanted_interval:
            continue
        if candidate.get("id"):
            return candidate
    return None
