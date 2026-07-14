"""Cohenta billing path — the pieces that make cohenta_pro_runner/cohenta_team sellable end-to-end from
the website (accounts.thyn.ai) checkout, product-scoped and isolated from codna/telys/algenta: checkout
allowlist (which also gains codna's proplus/ultra solo tiers), webhook price→plan reverse map,
placeholder-safe price resolution, the product-scoped billing gate, and the license decouple
(products.cohenta issued without the global v2 flag). Mirrors tests/unit/test_algenta_billing.py.
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


# ── webhook: cohenta price_id → plan (else a paid cohenta sub silently stays 'free') ──────────
class TestPlanFromSubscription:
    _settings = SimpleNamespace(
        stripe_price_developer="price_dev",
        stripe_price_pro="price_pro",
        stripe_price_proplus="price_proplus_real",
        stripe_price_ultra="price_ultra_real",
        stripe_price_team="price_team",
        stripe_price_telys_pro="price_telys_pro_real",
        stripe_price_telys_team="price_telys_team_real",
        stripe_price_algenta_pro="price_algenta_pro_real",
        stripe_price_algenta_team="price_algenta_team_real",
        stripe_price_cohenta_pro_runner="price_cohenta_pro_runner_real",
        stripe_price_cohenta_team="price_cohenta_team_real",
    )

    def _sub(self, price_id: str) -> dict:
        return {"items": {"data": [{"price": {"id": price_id}}]}}

    def test_cohenta_pro_runner_price_maps_to_cohenta_pro_runner(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert (
                billing._plan_from_subscription(self._sub("price_cohenta_pro_runner_real"))
                == "cohenta_pro_runner"
            )

    def test_cohenta_team_price_maps_to_cohenta_team(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_cohenta_team_real")) == "cohenta_team"

    def test_codna_solo_tier_prices_map(self):
        # proplus/ultra joined the website checkout — their renewals must reverse-map too.
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_proplus_real")) == "proplus"
            assert billing._plan_from_subscription(self._sub("price_ultra_real")) == "ultra"

    def test_isolation_other_brand_prices_never_map_to_cohenta(self):
        # A codna/telys/algenta price_id must NEVER resolve to a cohenta plan (and vice versa).
        with patch.object(billing, "_get_settings", return_value=self._settings):
            for pid, plan in (
                ("price_pro", "pro"),
                ("price_telys_pro_real", "telys_pro"),
                ("price_algenta_pro_real", "algenta_pro"),
            ):
                got = billing._plan_from_subscription(self._sub(pid))
                assert got == plan and not got.startswith("cohenta"), got
            for pid, plan in (
                ("price_cohenta_pro_runner_real", "cohenta_pro_runner"),
                ("price_cohenta_team_real", "cohenta_team"),
            ):
                got = billing._plan_from_subscription(self._sub(pid))
                assert got == plan and got.startswith("cohenta"), got

    def test_unknown_price_falls_back_to_free(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_unknown")) == "free"


# ── checkout allowlist permits cohenta + the codna solo power tiers (self-serve website) ────────
def test_website_checkout_allowlist_includes_cohenta():
    assert {"cohenta_pro_runner", "cohenta_team"} <= _CHECKOUT_PLANS
    # cohenta_free is $0 — never sold through Checkout.
    assert "cohenta_free" not in _CHECKOUT_PLANS


def test_website_checkout_allowlist_includes_codna_proplus_and_ultra():
    # proplus/ultra have Stripe prices (STRIPE_PRICE_PROPLUS/ULTRA) — sellable from the website now.
    assert {"proplus", "ultra"} <= _CHECKOUT_PLANS
    # regression: existing brands still sellable, telys_team still deliberately excluded (#287)
    assert {"pro", "team", "telys_pro", "algenta_pro", "algenta_team"} <= _CHECKOUT_PLANS
    assert "telys_team" not in _CHECKOUT_PLANS


# ── price-id resolution is placeholder-safe ─────────────────────────────────────────────────────
class TestCohentaPriceResolution:
    def _patch(self, pro_runner: str, team: str):
        s = SimpleNamespace(
            stripe_price_cohenta_pro_runner=pro_runner, stripe_price_cohenta_team=team
        )
        return patch("apps.api_server.services.stripe_service.get_settings", return_value=s)

    def test_real_ids_resolve(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        with self._patch("price_CPR_real", "price_CT_real"):
            assert PLAN_PRICE_IDS["cohenta_pro_runner"] == "price_CPR_real"
            assert PLAN_PRICE_IDS["cohenta_team"] == "price_CT_real"

    def test_placeholder_resolves_to_none(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        with self._patch("price_cohenta_pro_runner_replace_me", "price_cohenta_team_replace_me"):
            assert PLAN_PRICE_IDS["cohenta_pro_runner"] is None
            assert PLAN_PRICE_IDS["cohenta_team"] is None

    def test_cohenta_free_never_has_sku(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        assert PLAN_PRICE_IDS["cohenta_free"] is None


# ── product-scoped billing gate: cohenta billing is ON (credential gate is the dark switch) ──────
class TestBillingGate:
    def test_cohenta_billing_flag_is_on(self):
        assert product_flag(product_for_plan("cohenta_pro_runner"), "billing", default=True) is True
        assert product_flag(product_for_plan("cohenta_team"), "billing", default=True) is True

    def test_other_brands_billing_still_live(self):
        assert product_flag(product_for_plan("pro"), "billing", default=True) is True
        assert product_flag(product_for_plan("telys_pro"), "billing", default=True) is True
        assert product_flag(product_for_plan("algenta_pro"), "billing", default=True) is True


# ── license decouple: cohenta plans emit products.cohenta even with license_v2_issuance OFF ──────
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

    def test_cohenta_plan_emits_products_with_flag_off(self, monkeypatch):
        from apps.api_server import config

        monkeypatch.setattr(config.get_settings(), "license_v2_issuance", False, raising=False)
        claims = self._issue("cohenta_pro_runner")
        assert claims["ver"] == 2
        assert claims.get("products", {}).get("cohenta", {}).get("tier") == "pro"
        assert "campaigns" in claims["products"]["cohenta"]["features"]

    def test_codna_plan_no_products_map_with_flag_off(self, monkeypatch):
        """Zero blast radius: a Codna plan with the global flag OFF still emits NO products map."""
        from apps.api_server import config

        monkeypatch.setattr(config.get_settings(), "license_v2_issuance", False, raising=False)
        claims = self._issue("pro")
        assert "products" not in claims
