"""A plan Stripe sells must be a plan checkout can charge for.

Measured on the live host 2026-07-31: `GET https://api.algenta.ai/billing/plans` advertises
`algenta_server` at $600/mo and $6000/yr, and `api.telys.ai` advertises `telys_server` — publicly,
on an unauthenticated endpoint. Neither was in checkout's literal allow-list, and neither had a
`stripe_price_*` setting, so `POST /v1/billing/checkout` answered `invalid_plan`. The plans were
advertised and unbuyable.

The cause was that plan -> price was a HAND-MAINTAINED map. Adding a plan took four separate edits:
a `stripe_price_<plan>` config field, an entry in `PLAN_PRICE_IDS`, an entry in the checkout
allow-list, and the env var in production. `/billing/plans` needed none of them, because it reads
Stripe directly — so the pricing page moved ahead of checkout the moment a price was created, and
nothing failed loudly.

That map also held ONE price per plan with no interval, so every annual price in the catalogue was
unreachable through checkout even though the shared account portal already links
`/checkout?app=<brand>&plan=<plan>&interval=year`.

Both are the same defect, and the fix is to resolve the price from the SAME catalogue the pricing
page renders, keyed by `(plan, interval)`. These tests pin that a plan present in the catalogue is
chargeable at both intervals, that the legacy env-configured mapping still works, and that a plan
absent from the catalogue is refused rather than silently billed at the wrong price.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apps.api_server.services import stripe_catalog

# The shapes measured on the live host, plus the price id Stripe holds for each.
LIVE_ALGENTA: list[dict[str, Any]] = [
    {"id": "price_apro_m", "plan": "algenta_pro", "interval": "month", "price_usd": 99.0,
     "lookup_key": "algenta_pro_monthly", "source": "algenta"},
    {"id": "price_atea_m", "plan": "algenta_team", "interval": "month", "price_usd": 499.0,
     "lookup_key": "algenta_team_monthly", "source": "algenta"},
    {"id": "price_asrv_m", "plan": "algenta_server", "interval": "month", "price_usd": 600.0,
     "lookup_key": "algenta_server_monthly", "source": "algenta"},
    {"id": "price_apro_y", "plan": "algenta_pro", "interval": "year", "price_usd": 948.0,
     "lookup_key": "algenta_pro_annual", "source": "algenta"},
    {"id": "price_atea_y", "plan": "algenta_team", "interval": "year", "price_usd": 4788.0,
     "lookup_key": "algenta_team_annual", "source": "algenta"},
    # Note the suffix: `_yearly` here while pro/team use `_annual`. The resolver keys on the
    # `interval` field rather than on the lookup-key suffix precisely so that inconsistency in the
    # Stripe catalogue cannot lose a price.
    {"id": "price_asrv_y", "plan": "algenta_server", "interval": "year", "price_usd": 6000.0,
     "lookup_key": "algenta_server_yearly", "source": "algenta"},
]


@pytest.fixture(autouse=True)
def _catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the measured catalogue without touching Stripe."""

    async def _list_plans(app: str, *, use_cache: bool = True) -> list[dict[str, Any]]:
        return LIVE_ALGENTA if app == "algenta" else []

    monkeypatch.setattr(stripe_catalog, "list_plans", _list_plans)


def _resolve(plan: str, interval: str = "month", app: str = "algenta"):
    return asyncio.run(stripe_catalog.resolve_price(app, plan, interval))


def test_the_server_tier_is_chargeable_at_both_intervals():
    """THE REGRESSION. Advertised publicly at $600/mo and refused by checkout as `invalid_plan`."""
    monthly = _resolve("algenta_server", "month")
    yearly = _resolve("algenta_server", "year")
    assert monthly is not None, "algenta_server monthly is advertised; it must be chargeable"
    assert yearly is not None, "algenta_server yearly is advertised; it must be chargeable"
    assert (monthly["id"], monthly["price_usd"]) == ("price_asrv_m", 600.0)
    assert (yearly["id"], yearly["price_usd"]) == ("price_asrv_y", 6000.0)


def test_annual_prices_are_reachable_at_all():
    """The old map held one price per plan with no interval, so annual could not be selected.

    The account portal already links `?interval=year`, so this was a live mismatch between what the
    portal offers and what the engine can charge.
    """
    assert _resolve("algenta_pro", "year")["price_usd"] == 948.0
    assert _resolve("algenta_pro", "month")["price_usd"] == 99.0
    assert _resolve("algenta_team", "year")["price_usd"] == 4788.0


def test_every_advertised_plan_and_interval_resolves():
    """Exhaustive over the catalogue, so a newly added price cannot be advertised-but-unbuyable.

    This is the invariant the four-edit mapping could not hold: `/billing/plans` reads Stripe, so it
    gains a plan the moment a price exists, while checkout gained one only when somebody remembered
    four files.
    """
    for entry in LIVE_ALGENTA:
        got = _resolve(entry["plan"], entry["interval"])
        assert got is not None, f"{entry['plan']}:{entry['interval']} is advertised but unresolvable"
        assert got["id"] == entry["id"]
        assert got["price_usd"] == entry["price_usd"]


def test_an_unknown_interval_is_refused_not_substituted():
    """Billing a customer monthly when they asked annually is worse than refusing.

    An UNKNOWN interval resolves to nothing — it is never silently served as monthly, which would
    charge a different amount than the caller asked for.
    """
    assert _resolve("algenta_pro", "week") is None
    assert _resolve("algenta_pro", "quarter") is None


def test_an_unspecified_interval_defaults_to_monthly_and_the_route_validates():
    """An EMPTY interval means unspecified, and matches the signature default of `month`.

    Validation of the caller-supplied value belongs at the route, not here: `/v1/billing/checkout`
    rejects anything outside {month, year} with `invalid_plan` before this is reached, so the
    resolver never sees a bad value over the wire. Asserted rather than left implicit, because the
    two behaviours look alike and only one of them may be reachable from a request.
    """
    assert _resolve("algenta_pro", "")["interval"] == "month"
    assert asyncio.run(stripe_catalog.resolve_price("algenta", "algenta_pro"))["interval"] == "month"

    import inspect

    from apps.api_server.routers import billing

    body = inspect.getsource(billing.checkout)
    assert '"month", "year"' in body, "the route must be the place a bad interval is refused"


def test_a_plan_absent_from_the_catalogue_is_refused():
    assert _resolve("algenta_ghost", "month") is None
    assert _resolve("", "month") is None


def test_a_brand_with_no_catalogue_resolves_nothing():
    """A brand whose prices are not in Stripe must not borrow another brand's price."""
    assert _resolve("algenta_pro", "month", app="telys") is None
    assert _resolve("telys_pro", "month", app="telys") is None


def test_matching_is_case_and_space_insensitive():
    assert _resolve("  ALGENTA_SERVER  ", "MONTH")["id"] == "price_asrv_m"


def test_a_catalogue_entry_without_a_price_id_is_not_offered():
    """A shaped entry missing its Stripe id cannot be charged, so it must not resolve.

    `_shape` reads `price["id"]`; if Stripe ever omits it the entry is still renderable on a pricing
    page but not chargeable, and returning it here would produce a checkout session with no price.
    """
    broken = [dict(LIVE_ALGENTA[0])]
    broken[0]["id"] = None

    async def _list_plans(app: str, *, use_cache: bool = True):
        return broken

    stripe_catalog.list_plans = _list_plans  # type: ignore[assignment]
    assert _resolve("algenta_pro", "month") is None


def test_the_public_payload_does_not_leak_the_price_id():
    """The catalogue carries the id for checkout; the public pricing payload keeps its old shape."""
    from apps.api_server.routers import billing

    src = billing.public_plans.__doc__ or ""
    assert src, "public_plans should stay documented"
    # The route strips `id` before returning; assert the stripping is present rather than trusting it.
    import inspect

    body = inspect.getsource(billing.public_plans)
    assert 'k != "id"' in body, "public_plans must drop the internal price id"
