"""Dynamic plan catalog: list_plans filters by app (metadata.source) + shapes Stripe -> UI fields."""

from __future__ import annotations

import pytest

from apps.api_server.services import stripe_catalog


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


_PRICES = {
    "data": [
        {
            "unit_amount": 2000, "currency": "usd", "recurring": {"interval": "month"},
            "lookup_key": "codna_pro_monthly", "metadata": {"plan": "pro"},
            "product": {
                "active": True, "name": "Codna Pro", "description": "For solo devs",
                "marketing_features": [{"name": "Managed LLM"}, {"name": "GitHub App"}],
                "metadata": {"source": "codna", "plan": "pro"},
            },
        },
        {
            "unit_amount": 20000, "currency": "usd", "recurring": {"interval": "month"},
            "lookup_key": "codna_ultra_monthly", "metadata": {"plan": "ultra"},
            "product": {
                "active": True, "name": "Codna Ultra", "description": "Max solo",
                "marketing_features": [], "metadata": {"source": "codna", "plan": "ultra"},
            },
        },
        {
            "unit_amount": 2900, "currency": "usd", "recurring": {"interval": "month"},
            "lookup_key": "telys_pro_monthly", "metadata": {"plan": "telys_pro"},
            "product": {"active": True, "name": "Telys Pro", "metadata": {"source": "telys"}},
        },
        {
            "unit_amount": 4900, "currency": "usd", "metadata": {},
            "product": {"active": False, "name": "Algenta Developer (archived)", "metadata": {}},
        },
    ]
}


@pytest.fixture(autouse=True)
def _clear_cache():
    stripe_catalog._CACHE.clear()
    yield
    stripe_catalog._CACHE.clear()


async def test_list_plans_filters_by_app_and_shapes(monkeypatch):
    async def _req(**kwargs):
        return _Resp(_PRICES)

    monkeypatch.setattr(stripe_catalog, "stripe_api_request", _req)
    plans = await stripe_catalog.list_plans("codna", use_cache=False)
    # only active codna products, price-sorted (20 < 200); telys + archived excluded
    assert [p["name"] for p in plans] == ["Codna Pro", "Codna Ultra"]
    pro = plans[0]
    assert pro["price_usd"] == 20.0
    assert pro["interval"] == "month"
    assert pro["plan"] == "pro"
    assert pro["description"] == "For solo devs"
    assert pro["features"] == ["Managed LLM", "GitHub App"]


async def test_list_plans_scopes_to_telys(monkeypatch):
    async def _req(**kwargs):
        return _Resp(_PRICES)

    monkeypatch.setattr(stripe_catalog, "stripe_api_request", _req)
    plans = await stripe_catalog.list_plans("telys", use_cache=False)
    assert [p["name"] for p in plans] == ["Telys Pro"]


async def test_plan_rows_carry_entitlements_from_product_metadata(monkeypatch):
    """The billing card's entitlement chips render straight from product metadata."""
    async def _req(**kwargs):
        class _R:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "data": [
                        {
                            "id": "price_1", "unit_amount": 9900, "currency": "usd",
                            "lookup_key": "algenta_pro_monthly", "metadata": {},
                            "recurring": {"interval": "month"},
                            "product": {
                                "active": True, "name": "Algenta Pro", "description": "d",
                                "metadata": {
                                    "plan": "algenta_pro", "source": "algenta",
                                    "seats": "1", "workers": "5", "per": "device",
                                    "support": "email",  # non-entitlement key: must NOT pass through
                                },
                            },
                        }
                    ]
                }

        return _R()

    from apps.api_server.services import stripe_catalog as c

    monkeypatch.setattr(c, "stripe_api_request", _req)
    plans = await c.list_plans("algenta", use_cache=False)
    assert plans and plans[0]["entitlements"] == {"seats": "1", "workers": "5", "per": "device"}
