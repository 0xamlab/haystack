"""Telys billing path — the fixes that make telys_pro/telys_team actually sellable end-to-end
(checkout allowlist, webhook price→plan reverse map, placeholder-safe price resolution, and the
license decouple so a paid Telys customer's products.telys is issued without the global v2 flag).

These guard the six integration gaps found by the billing-path verification; without them the Telys
Stripe products exist but are unsellable / un-entitled, with green unit tests masking it."""

import base64
import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from apps.api_server.routers import billing
from apps.api_server.routers.website_billing import _CHECKOUT_PLANS
from apps.api_server.services import device_service


def _decode_jwt_claims(token: str) -> dict:
    """Read JWT claims without verifying (dev_hmac HS256 token)."""
    seg = token.split(".")[1]
    seg += "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg))


# ── webhook: telys price_id → plan (else a paid telys sub silently stays 'free') ──────────────
class TestPlanFromSubscription:
    _settings = SimpleNamespace(
        stripe_price_developer="price_dev",
        stripe_price_pro="price_pro",
        stripe_price_team="price_team",
        stripe_price_telys_pro="price_telys_pro_real",
        stripe_price_telys_team="price_telys_team_real",
    )

    def _sub(self, price_id: str) -> dict:
        return {"items": {"data": [{"price": {"id": price_id}}]}}

    def test_telys_pro_price_maps_to_telys_pro(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_telys_pro_real")) == "telys_pro"

    def test_telys_team_price_maps_to_telys_team(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_telys_team_real")) == "telys_team"

    def test_existing_codna_mappings_unchanged(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_pro")) == "pro"
            assert billing._plan_from_subscription(self._sub("price_team")) == "team"

    def test_unknown_price_falls_back_to_free(self):
        with patch.object(billing, "_get_settings", return_value=self._settings):
            assert billing._plan_from_subscription(self._sub("price_unknown")) == "free"


# ── checkout allowlists permit telys ──────────────────────────────────────────────────────────
def test_website_checkout_allowlist_includes_telys():
    assert "telys_pro" in _CHECKOUT_PLANS
    # telys_team is deliberately EXCLUDED from public self-serve (#287 dropped Team from the ladder;
    # it's retained for existing orgs + enforcement, not sold here). See website_billing._CHECKOUT_PLANS.
    assert "telys_team" not in _CHECKOUT_PLANS
    # Codna tiers still sellable (no regression)
    assert "pro" in _CHECKOUT_PLANS and "team" in _CHECKOUT_PLANS


# ── price-id resolution is placeholder-safe (placeholder → None → clean 400, not a Stripe 502) ──
class TestTelysPriceResolution:
    def _patch(self, pro: str, team: str):
        s = SimpleNamespace(stripe_price_telys_pro=pro, stripe_price_telys_team=team)
        return patch("apps.api_server.services.stripe_service.get_settings", return_value=s)

    def test_real_ids_resolve(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        with self._patch("price_TP_real", "price_TT_real"):
            assert PLAN_PRICE_IDS["telys_pro"] == "price_TP_real"
            assert PLAN_PRICE_IDS["telys_team"] == "price_TT_real"

    def test_placeholder_resolves_to_none(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        with self._patch("price_telys_pro_replace_me", "price_telys_team_replace_me"):
            assert PLAN_PRICE_IDS["telys_pro"] is None
            assert PLAN_PRICE_IDS["telys_team"] is None

    def test_telys_developer_never_has_sku(self):
        from apps.api_server.services.stripe_service import PLAN_PRICE_IDS

        assert PLAN_PRICE_IDS["telys_developer"] is None


# ── license decouple: telys plans emit products.telys even with license_v2_issuance OFF ─────────
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

    def test_telys_plan_emits_products_with_flag_off(self, monkeypatch):
        from apps.api_server import config

        monkeypatch.setattr(config.get_settings(), "license_v2_issuance", False, raising=False)
        claims = self._issue("telys_pro")
        assert claims["ver"] == 2
        assert claims.get("products", {}).get("telys", {}).get("tier") == "pro"
        assert "local_runtime" in claims["products"]["telys"]["features"]

    def test_codna_plan_no_products_map_with_flag_off(self, monkeypatch):
        """Zero blast radius: a Codna plan with the global flag OFF still emits NO products map."""
        from apps.api_server import config

        monkeypatch.setattr(config.get_settings(), "license_v2_issuance", False, raising=False)
        claims = self._issue("pro")
        assert "products" not in claims
