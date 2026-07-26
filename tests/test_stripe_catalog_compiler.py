"""Stripe catalog compiler + EntitlementSnapshot (C0).

Fixture-driven (no live Stripe): compilation, the full validation matrix (duplicate sku_key,
bad enums, missing fields, out-of-range numbers, scope/metric mismatch, live/test mixing), the
deterministic policy_hash, and the three EntitlementSnapshot source types.
"""
from __future__ import annotations

import pytest

from apps.api_server.services import entitlement_snapshot as snap
from apps.api_server.services import stripe_catalog_compiler as cc


def _price(sku="algenta.server.pinned", *, product_meta=None, price_meta=None,
           unit_amount=22900, interval="year", lookup=None, livemode=False, pid="prod_1"):
    pm = {
        "lic_schema": "thyn_license_v1",
        "sku_key": sku,
        "product_key": "algenta",
        "edition_key": "server",
        "license_scope": "deployment",
        "license_mode": "pinned",
        "qty_metric": "compute_unit",
        "deploy_class": "production_server",
        "vcpu_per_unit": "4",
        "workers_per_unit": "5",
        "measure_policy": "cgroup-v1",
        "grace_policy": "community-floor-v1",
        "entitlement_features": "server_pinned,relay_access",
    }
    if product_meta:
        pm.update(product_meta)
    prm = {"qty_min": "4", "qty_max": "127"}
    if price_meta:
        prm.update(price_meta)
    return {
        "id": "price_1",
        "unit_amount": unit_amount,
        "currency": "usd",
        "recurring": {"interval": interval} if interval else None,
        "lookup_key": lookup or sku,
        "livemode": livemode,
        "metadata": prm,
        "product": {"id": pid, "active": True, "metadata": pm},
    }


# ── happy path ───────────────────────────────────────────────────────────────


def test_compile_valid_catalog() -> None:
    rel = cc.compile_catalog([_price()], release="2026.07.25.1")
    assert rel.release == "2026.07.25.1"
    s = rel.sku("algenta.server.pinned")
    assert s is not None
    assert s.license_scope == "deployment" and s.qty_metric == "compute_unit"
    assert s.vcpu_per_unit == 4 and s.workers_per_unit == 5
    assert s.qty_min == 4 and s.qty_max == 127
    assert s.price_amount_cents == 22900 and s.currency == "usd" and s.interval == "year"
    assert s.entitlement_features == ("server_pinned", "relay_access")
    assert len(rel.policy_hash) == 64  # sha256 hex


def test_non_licensing_prices_are_ignored() -> None:
    plain = {"id": "price_x", "unit_amount": 100, "currency": "usd", "product": {"id": "p", "metadata": {}}}
    rel = cc.compile_catalog([plain, _price()])
    assert set(rel.skus) == {"algenta.server.pinned"}  # the plain price is skipped, not an error


def test_policy_hash_is_deterministic_and_content_sensitive() -> None:
    h1 = cc.compile_catalog([_price()]).policy_hash
    h2 = cc.compile_catalog([_price()]).policy_hash
    h3 = cc.compile_catalog([_price(product_meta={"vcpu_per_unit": "8"})]).policy_hash
    assert h1 == h2 and h1 != h3


# ── validation matrix (all raise CatalogCompileError) ─────────────────────────


def test_duplicate_sku_key_rejected() -> None:
    with pytest.raises(cc.CatalogCompileError, match="duplicate sku_key"):
        cc.compile_catalog([_price(pid="a"), _price(pid="b")])


def test_unknown_product_rejected() -> None:
    with pytest.raises(cc.CatalogCompileError, match="unknown product_key"):
        cc.compile_catalog([_price(product_meta={"product_key": "acme"})])


def test_invalid_enum_rejected() -> None:
    with pytest.raises(cc.CatalogCompileError, match="invalid license_mode"):
        cc.compile_catalog([_price(product_meta={"license_mode": "bogus"})])


def test_scope_metric_mismatch_rejected() -> None:
    with pytest.raises(cc.CatalogCompileError, match="deployment scope must use qty_metric=compute_unit"):
        cc.compile_catalog([_price(product_meta={"qty_metric": "device"})])


def test_missing_sku_key_rejected() -> None:
    with pytest.raises(cc.CatalogCompileError, match="missing sku_key"):
        cc.compile_catalog([_price(product_meta={"sku_key": ""})])


def test_out_of_range_vcpu_rejected() -> None:
    with pytest.raises(cc.CatalogCompileError, match="vcpu_per_unit out of range"):
        cc.compile_catalog([_price(product_meta={"vcpu_per_unit": "9999"})])


def test_bad_qty_bounds_rejected() -> None:
    with pytest.raises(cc.CatalogCompileError, match="invalid qty_min/qty_max"):
        cc.compile_catalog([_price(price_meta={"qty_min": "50", "qty_max": "4"})])


def test_live_test_mixing_rejected() -> None:
    with pytest.raises(cc.CatalogCompileError, match="live/test mode mixing"):
        cc.compile_catalog([_price(sku="a.server.pinned", pid="a", livemode=True),
                            _price(sku="b.server.pinned", pid="b", livemode=False,
                                   product_meta={"product_key": "codna", "sku_key": "b.server.pinned"})])


def test_all_violations_reported_at_once() -> None:
    bad = _price(product_meta={"product_key": "acme", "license_mode": "bogus"})
    try:
        cc.compile_catalog([bad])
        raise AssertionError("should have raised")
    except cc.CatalogCompileError as exc:
        assert len(exc.violations) >= 2  # both product and mode flagged in one pass


# ── device-scope SKU ─────────────────────────────────────────────────────────


def test_device_scope_sku_compiles() -> None:
    dev = _price(
        sku="algenta.pro.workstation",
        product_meta={
            "sku_key": "algenta.pro.workstation", "license_scope": "device",
            "license_mode": "workstation", "qty_metric": "device", "deploy_class": "workstation",
        },
        price_meta={"qty_min": "1", "qty_max": "100"},
        unit_amount=9900,
    )
    rel = cc.compile_catalog([dev])
    s = rel.sku("algenta.pro.workstation")
    assert s.license_scope == "device" and s.qty_metric == "device"


# ── EntitlementSnapshot: three source types ───────────────────────────────────


def test_community_snapshot_needs_no_stripe() -> None:
    s = snap.resolve_community_snapshot(org_id="org-1", product="algenta")
    assert s.source_type == snap.SOURCE_COMMUNITY
    assert s.license_scope == "device" and s.quantity == 1
    assert s.stripe_subscription_id == ""
    # Community floor claims: non-commercial, no deployment units.
    assert s.license_claims.get("commercial_use") is False
    assert "max_concurrent_units" not in s.license_claims  # device scope emits no server claims


def test_stripe_subscription_snapshot_deployment_quantity_is_units() -> None:
    sku = cc.compile_catalog([_price()]).sku("algenta.server.pinned")
    s = snap.resolve_snapshot(
        source_type=snap.SOURCE_STRIPE, org_id="org-1", sku=sku, quantity=32,
        catalog_release="r1", policy_hash="h1",
        stripe_ids={"subscription": "sub_1", "price": "price_1"},
    )
    assert s.source_type == snap.SOURCE_STRIPE
    assert s.license_scope == "deployment" and s.quantity == 32
    assert s.license_claims["license_scope"] == "deployment"
    assert s.license_claims["max_concurrent_units"] == 32  # quantity → unit ceiling
    assert s.license_claims["vcpu_per_unit"] == 4
    assert s.stripe_subscription_id == "sub_1"


def test_enterprise_snapshot_applies_overrides() -> None:
    sku = cc.compile_catalog([_price(price_meta={"qty_min": "1", "qty_max": "100000"})]).sku("algenta.server.pinned")
    s = snap.resolve_snapshot(
        source_type=snap.SOURCE_ENTERPRISE, org_id="org-ent", sku=sku, quantity=256,
        overrides={"redistribution_allowed": False},
    )
    assert s.source_type == snap.SOURCE_ENTERPRISE
    assert s.license_claims["max_concurrent_units"] == 256


def test_snapshot_rejects_quantity_below_sku_minimum() -> None:
    sku = cc.compile_catalog([_price()]).sku("algenta.server.pinned")  # qty_min=4
    with pytest.raises(ValueError, match="outside SKU"):
        snap.resolve_snapshot(source_type=snap.SOURCE_STRIPE, org_id="o", sku=sku, quantity=2)


def test_snapshot_rejects_wrong_source_type() -> None:
    sku = cc.compile_catalog([_price()]).sku("algenta.server.pinned")
    with pytest.raises(ValueError, match="paid/enterprise"):
        snap.resolve_snapshot(source_type=snap.SOURCE_COMMUNITY, org_id="o", sku=sku, quantity=8)


def test_all_five_editions_compile_and_snapshot() -> None:
    prices = []
    for ed in ["algenta", "codna", "telys", "sqai", "cohenta"]:
        prices.append(_price(
            sku=f"{ed}.server.pinned", pid=f"prod_{ed}",
            product_meta={"sku_key": f"{ed}.server.pinned", "product_key": ed},
        ))
    rel = cc.compile_catalog(prices)
    assert len(rel.skus) == 5
    for ed in ["algenta", "codna", "telys", "sqai", "cohenta"]:
        s = snap.resolve_snapshot(
            source_type=snap.SOURCE_STRIPE, org_id="o", sku=rel.sku(f"{ed}.server.pinned"), quantity=16
        )
        assert s.license_claims["max_concurrent_units"] == 16
        assert ed in s.license_claims["products"]
