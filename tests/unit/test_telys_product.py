"""Telys product entitlements (additive) — telys_developer free tier + paid telys_pro/team, the engine's
ver:2 products.telys claim, and proof the existing Codna tiers are UNCHANGED (no bundling)."""
from apps.api_server.services import entitlement_service as ent
from apps.api_server.services.plan_limits import get as plan_get
from apps.api_server.services.stripe_service import PLAN_PRICE_IDS


def test_telys_developer_is_free_one_device_noncommercial():
    r = ent.resolve_entitlement("telys_developer")
    assert "telys" in r.products and "codna" not in r.products
    assert r.products["telys"].tier == "developer"
    assert "local_runtime" in r.products["telys"].features
    assert r.commercial_use is False
    assert r.named_seat_limit == 1 and r.device_allowance_per_seat == 1


def test_paid_telys_tiers_grant_telys_commercial():
    for plan, tier in (("telys_pro", "pro"), ("telys_team", "team")):
        r = ent.resolve_entitlement(plan)
        assert r.products["telys"].tier == tier and r.commercial_use is True


def test_to_license_claims_emits_v2_products_telys():
    claims = ent.to_license_claims(ent.resolve_entitlement("telys_developer"))
    assert claims["ver"] == 2
    assert claims["products"]["telys"]["tier"] == "developer"
    assert "local_runtime" in claims["products"]["telys"]["features"]


def test_codna_tiers_unchanged_no_telys_bundled():
    # zero blast radius: paid Codna tiers grant ONLY codna (Telys is sold separately)
    for plan in ("developer", "pro", "team", "enterprise"):
        r = ent.resolve_entitlement(plan)
        assert "codna" in r.products and "telys" not in r.products


def test_plan_limits_telys_developer_local_runtime_enabled():
    p = plan_get("telys_developer")
    assert p.local_runtime is True and p.price_usd_month == 0 and p.devices == 1


def test_stripe_price_mapping_for_telys():
    assert PLAN_PRICE_IDS["telys_developer"] is None          # free, no Stripe SKU
    assert "telys_pro" in PLAN_PRICE_IDS and "telys_team" in PLAN_PRICE_IDS
