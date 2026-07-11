"""Algenta billing path — the pieces that make algenta_pro/algenta_team sellable end-to-end, product-scoped
and isolated from codna/telys: webhook price→plan reverse map, placeholder-safe price resolution, checkout
allowlists, the product-scoped billing gate (algenta ships DARK), and the license decouple (products.algenta
issued without the global v2 flag). Mirrors tests/unit/test_telys_billing.py.
"""

import base64
import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from apps.api_server.routers import billing
from apps.api_server.routers.website_billing import _CHECKOUT_PLANS
from apps.api_server.services import device_service
from apps.api_server.services.product_registry import product_flag, product_for_plan


def _decode_jwt_claims(token: str) -> dict:
    seg = token.split(".")[1]
    seg += "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg))


# ── webhook: algenta price_id → plan (else a paid algenta sub silently stays 'free') ──────────
class TestPlanFromSubscription:
    _settings = SimpleNamespace(
        stripe_price_developer="price_dev",
        stripe_price_pro="price_pro",
        stripe_price_team="price_team",
        stripe_price_telys_pro="price_telys_pro_real",
        stripe_price_telys_team="price_telys_team_real",
        stripe_price_algenta_pro="price_algenta_pro_real",
        stripe_price_algenta_team="price_algenta_team_real",
    )

    def _sub(self, price_id: str) -> dict:
        return {"items": {"data": [{"price": {"id": price_id}}]}}

    def test_algenta_pro_price_maps_to_algenta_pro(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_algenta_pro_real")) == "algenta_pro"

    def test_algenta_team_price_maps_to_algenta_team(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_algenta_team_real")) == "algenta_team"

    def test_isolation_other_brand_prices_never_map_to_algenta(self):
        # A codna/telys price_id must NEVER resolve to an algenta plan (and vice versa) — no name collision.
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_pro")) == "pro"
            assert billing._plan_from_subscription(self._sub("price_telys_pro_real")) == "telys_pro"
            for pid, plan in (
                ("price_algenta_pro_real", "algenta_pro"),
                ("price_algenta_team_real", "algenta_team"),
            ):
                got = billing._plan_from_subscription(self._sub(pid))
                assert got == plan and not got.startswith(("codna", "telys")), got

    def test_unknown_price_falls_back_to_free(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_unknown")) == "free"


# ── checkout allowlist permits algenta (self-serve website) ────────────────────────────────────
def test_website_checkout_allowlist_includes_algenta_pro_and_team():
    assert {"algenta_pro", "algenta_team"} <= _CHECKOUT_PLANS
    # regression: existing brands still sellable
    assert {"pro", "team", "telys_pro"} <= _CHECKOUT_PLANS


# ── CheckoutRequest carries the per-device / per-seat quantity (webhook syncs it) ────────────────
def test_checkout_request_quantity():
    from apps.api_server.routers.website_billing import CheckoutRequest

    assert CheckoutRequest(plan="algenta_team").quantity == 1  # default
    assert CheckoutRequest(plan="algenta_team", quantity=20).quantity == 20  # per-device count
    import pytest

    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError for < 1
        CheckoutRequest(plan="algenta_pro", quantity=0)


# ── checkout redirect URLs: trusted-host only (no open redirect) ─────────────────────────────────
def test_validated_return_url_allows_trusted_and_blocks_others(monkeypatch):
    from types import SimpleNamespace

    from apps.api_server.routers import website_billing as wb

    monkeypatch.setattr(
        wb, "_get_settings", lambda: SimpleNamespace(accounts_base_url="https://accounts.thyn.ai")
    )
    # accounts portal host → allowed
    assert wb._validated_return_url("https://accounts.thyn.ai/account?checkout=success") is not None
    assert wb._validated_return_url("http://localhost:3000/account") is not None  # dev
    # attacker / any other host → dropped (falls back to the derived default)
    assert wb._validated_return_url("https://evil.example.com/account") is None
    assert wb._validated_return_url("https://accounts.thyn.ai.evil.com/x") is None  # not exact host
    assert wb._validated_return_url(None) is None
    assert wb._validated_return_url("not-a-url") is None


# ── price-id resolution is placeholder-safe ─────────────────────────────────────────────────────
class TestAlgentaPriceResolution:
    def _patch(self, pro: str, team: str):
        s = SimpleNamespace(stripe_price_algenta_pro=pro, stripe_price_algenta_team=team)
        return patch("apps.api_server.services.stripe_service.get_settings", return_value=s)

    def test_real_ids_resolve(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        with self._patch("price_AP_real", "price_AT_real"):
            assert PLAN_PRICE_IDS["algenta_pro"] == "price_AP_real"
            assert PLAN_PRICE_IDS["algenta_team"] == "price_AT_real"

    def test_placeholder_resolves_to_none(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        with self._patch("price_algenta_pro_replace_me", "price_algenta_team_replace_me"):
            assert PLAN_PRICE_IDS["algenta_pro"] is None
            assert PLAN_PRICE_IDS["algenta_team"] is None

    def test_algenta_free_never_has_sku(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        assert PLAN_PRICE_IDS["algenta_free"] is None


# ── product-scoped billing gate: ALL brands billing-on; the credential gate is the real dark switch ─
class TestBillingGate:
    def test_algenta_billing_flag_is_on(self):
        # Algenta billing is now live at the product level (per-device Pro/Team are in Stripe). The
        # effective dark switch is credential-based: billing_configured() gates on a real Stripe key.
        assert product_flag(product_for_plan("algenta_pro"), "billing", default=True) is True
        assert product_flag(product_for_plan("algenta_team"), "billing", default=True) is True

    def test_codna_and_telys_billing_are_live(self):
        assert product_flag(product_for_plan("pro"), "billing", default=True) is True
        assert product_flag(product_for_plan("telys_pro"), "billing", default=True) is True


# ── license decouple: algenta plans emit products.algenta even with license_v2_issuance OFF ──────
class TestLicenseProductDecouple:
    def _issue(self, plan: str) -> dict:
        token = device_service._issue_license_jwt(
            device_id="dev-test",
            api_key_prefix="ak_test",
            plan=plan,
            device_limit=3,
            org_id=str(uuid.uuid4()),
        )
        return _decode_jwt_claims(token)

    def test_algenta_plan_emits_products_with_flag_off(self, monkeypatch):
        from apps.api_server import config

        monkeypatch.setattr(config.get_settings(), "license_v2_issuance", False, raising=False)
        claims = self._issue("algenta_pro")
        assert claims["ver"] == 2
        assert claims.get("products", {}).get("algenta", {}).get("tier") == "pro"
        assert "local_runtime" in claims["products"]["algenta"]["features"]
