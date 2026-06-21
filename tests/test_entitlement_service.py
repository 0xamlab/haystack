"""Entitlement resolution (P3a) — the authorized commercial-capacity record per org.

Covers tier→record mapping, per-org overrides, the self-service ceiling, v2 claim
emission, and a cross-layer round-trip: the claims this service emits must parse back
into a runtime DeviceLicense (apps/runtime/license.py, P0) with the same products/caps.
"""

from __future__ import annotations

from types import SimpleNamespace

from apps.api_server.services.entitlement_service import (
    CODNA_FEATURES_FULL,
    EntitlementRecord,
    ProductGrant,
    entitlement_for_org,
    resolve_entitlement,
    to_license_claims,
    within_self_service_ceiling,
)

# ── Tier → record ─────────────────────────────────────────────────────────────


def test_free_tier_has_no_local_engine_license() -> None:
    rec = resolve_entitlement("free")
    assert rec.products == {}  # cloud-API only — free download stays inert
    assert rec.commercial_use is False
    assert rec.concurrent_worker_limit == 0
    assert rec.deployment_class == ""


def test_pro_tier_grants_full_codna_within_ceiling() -> None:
    rec = resolve_entitlement("pro")
    assert rec.has_product("codna")
    assert rec.products["codna"].features == frozenset(CODNA_FEATURES_FULL)
    assert rec.products["codna"].tier == "pro"
    assert rec.deployment_class == "desktop"
    assert (rec.named_seat_limit, rec.active_node_limit, rec.concurrent_worker_limit) == (1, 1, 2)
    assert rec.commercial_use is True


def test_developer_and_pro_are_the_same_commercial_tier() -> None:
    dev = resolve_entitlement("developer")
    pro = resolve_entitlement("pro")
    assert (dev.named_seat_limit, dev.active_node_limit, dev.concurrent_worker_limit) == (
        pro.named_seat_limit,
        pro.active_node_limit,
        pro.concurrent_worker_limit,
    )
    assert dev.products["codna"].features == pro.products["codna"].features


def test_team_tier_sits_at_the_self_service_ceiling() -> None:
    rec = resolve_entitlement("team")
    assert (rec.named_seat_limit, rec.active_node_limit, rec.concurrent_worker_limit) == (5, 2, 4)
    assert rec.deployment_class == "server"
    assert within_self_service_ceiling(rec) is True


def test_enterprise_tier_is_negotiated_and_above_ceiling() -> None:
    rec = resolve_entitlement("enterprise")
    # 0 = unspecified/negotiated pools (control-plane reconciled); concrete via overrides.
    assert (rec.named_seat_limit, rec.active_node_limit, rec.concurrent_worker_limit) == (0, 0, 0)
    assert rec.offline_grace_days == 30  # paid offline right
    assert within_self_service_ceiling(rec) is False  # uncapped ⇒ requires a contract


def test_unknown_plan_falls_back_to_free() -> None:
    assert resolve_entitlement("bogus").plan == "free"
    assert resolve_entitlement("").products == {}


def test_plan_accepts_enum_like_value() -> None:
    enum_like = SimpleNamespace(value="team")
    assert resolve_entitlement(enum_like).named_seat_limit == 5


# ── Overrides (enterprise negotiated pools) ────────────────────────────────────


def test_overrides_apply_authoritatively() -> None:
    rec = resolve_entitlement(
        "enterprise",
        overrides={
            "named_seat_limit": 250,
            "active_node_limit": 12,
            "concurrent_worker_limit": 48,
            "redistribution_allowed": True,
            "entitlement_version": 7,
        },
    )
    assert rec.named_seat_limit == 250
    assert rec.active_node_limit == 12
    assert rec.concurrent_worker_limit == 48
    assert rec.redistribution_allowed is True
    assert rec.entitlement_version == 7
    # untouched fields keep the tier default
    assert rec.deployment_class == "server"


def test_overrides_can_narrow_products() -> None:
    rec = resolve_entitlement(
        "pro",
        overrides={"products": {"codna": {"tier": "pro", "features": ["repo_graph", "triage"]}}},
    )
    assert rec.products["codna"].features == frozenset({"repo_graph", "triage"})
    assert "apply" not in rec.products["codna"].features


def test_overrides_ignore_none_and_unknown_keys() -> None:
    base = resolve_entitlement("pro")
    rec = resolve_entitlement(
        "pro", overrides={"named_seat_limit": None, "totally_unknown": 999}
    )
    assert rec == base  # None and unknown keys are no-ops


# ── Self-service ceiling ───────────────────────────────────────────────────────


def test_ceiling_rejects_over_limit_and_redistribution() -> None:
    over_seats = EntitlementRecord(plan="x", named_seat_limit=6, active_node_limit=1, concurrent_worker_limit=1)
    assert within_self_service_ceiling(over_seats) is False
    redis = EntitlementRecord(
        plan="x",
        named_seat_limit=1,
        active_node_limit=1,
        concurrent_worker_limit=1,
        redistribution_allowed=True,
    )
    assert within_self_service_ceiling(redis) is False
    ok = EntitlementRecord(plan="x", named_seat_limit=5, active_node_limit=2, concurrent_worker_limit=4)
    assert within_self_service_ceiling(ok) is True


# ── entitlement_for_org ────────────────────────────────────────────────────────


def test_entitlement_for_org_reads_plan_and_overrides() -> None:
    org = SimpleNamespace(plan=SimpleNamespace(value="pro"), entitlement_overrides=None)
    assert entitlement_for_org(org).products["codna"].tier == "pro"

    org_ovr = SimpleNamespace(
        plan="enterprise",
        entitlement_overrides={"named_seat_limit": 100, "active_node_limit": 5},
    )
    rec = entitlement_for_org(org_ovr)
    assert rec.named_seat_limit == 100
    assert rec.active_node_limit == 5


# ── Claim emission + cross-layer round-trip with the P0 runtime parser ─────────


def test_to_license_claims_shape() -> None:
    claims = to_license_claims(resolve_entitlement("team"))
    assert claims["ver"] == 2
    assert claims["plan"] == "team"
    assert claims["products"]["codna"]["tier"] == "team"
    assert sorted(claims["products"]["codna"]["features"]) == sorted(CODNA_FEATURES_FULL)
    assert claims["concurrent_worker_limit"] == 4
    assert claims["offline_grace_days"] == 3


def test_claims_round_trip_into_runtime_device_license() -> None:
    """The claims P3a emits must parse back into a runtime DeviceLicense (P0) unchanged."""
    from apps.runtime.license import _device_license_from_payload

    rec = resolve_entitlement("team")
    claims = to_license_claims(rec)
    lic = _device_license_from_payload(
        claims, source="test", api_key="", default_plan="free"
    )

    assert lic.license_version == 2
    assert lic.has_product("codna") is True
    assert lic.product_features("codna") == frozenset(CODNA_FEATURES_FULL)
    assert lic.product_tier("codna") == "team"
    assert lic.worker_limit() == rec.concurrent_worker_limit == 4
    assert lic.named_seat_limit == rec.named_seat_limit == 5
    assert lic.active_node_limit == rec.active_node_limit == 2
    assert lic.commercial_use is True
    assert lic.offline_grace_days == 3


def test_narrowed_claims_round_trip_gate_features() -> None:
    rec = resolve_entitlement(
        "pro", overrides={"products": {"codna": {"tier": "pro", "features": ["repo_graph", "triage"]}}}
    )
    from apps.runtime.license import _device_license_from_payload

    lic = _device_license_from_payload(
        to_license_claims(rec), source="test", api_key="", default_plan="free"
    )
    assert lic.product_features("codna") == frozenset({"repo_graph", "triage"})


def test_grant_dataclass_is_hashable_frozen() -> None:
    g = ProductGrant(tier="pro", features=frozenset({"a"}))
    assert g.tier == "pro"
    # frozen → safe to use in sets / as defaults
    assert {g}  # hashable
