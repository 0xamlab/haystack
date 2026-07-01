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

from apps.api_server.services.stripe_service import _is_placeholder, stripe_api_request

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
        "plan": (price.get("metadata") or {}).get("plan") or pmeta.get("plan"),
        "name": prod.get("name"),
        "description": prod.get("description"),
        "features": features,
        "price_usd": round((price.get("unit_amount") or 0) / 100, 2),
        "currency": (price.get("currency") or "usd").upper(),
        "interval": (price.get("recurring") or {}).get("interval"),
        "lookup_key": price.get("lookup_key"),
        "source": pmeta.get("source"),
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
