"""Device-scope server-refusal: the per-node effective-vCPU ceiling for DESKTOP licenses.

Covers the full DARK-first chain end to end:
  Stripe SKU metadata `max_effective_vcpu`
    → stripe_catalog_compiler.CompiledSku.max_effective_vcpu
    → entitlement_snapshot.resolve_snapshot (device branch → tier override)
    → entitlement_service.to_license_claims (emits the claim for DEVICE scope)
    → runtime node_broker.assert_device_capacity (refuses server-class hardware, opt-in).

Safety invariants asserted: no ceiling / deployment scope → no-op; within grace → admit;
over ceiling → observe-only (logs, no raise) unless ALGENTA_ENFORCE_DEVICE_VCPU is set.
"""
from __future__ import annotations

import pytest

from apps.api_server.services import entitlement_snapshot as snap
from apps.api_server.services import stripe_catalog_compiler as cc
from apps.api_server.services.entitlement_service import resolve_entitlement, to_license_claims
from apps.runtime import capacity, node_broker


# ── runtime: node_broker.assert_device_capacity (desktop-on-server refusal) ───────


class _DesktopLicense:
    def __init__(self, *, scope="device", max_effective_vcpu=0, deployment_class="desktop"):
        self._scope = scope
        self.max_effective_vcpu = max_effective_vcpu
        self.deployment_class = deployment_class

    def is_deployment_scope(self) -> bool:
        return self._scope == "deployment"


def _set_effective_vcpu(monkeypatch, value: float) -> None:
    monkeypatch.setattr(
        capacity,
        "measure_effective_vcpu",
        lambda: capacity.CapacityMeasurement(effective_vcpu=value, source="test", constraints={}),
    )


def test_device_capacity_noop_without_ceiling(monkeypatch) -> None:
    # No ceiling set → the enforcement is dark for this license, whatever the hardware.
    _set_effective_vcpu(monkeypatch, 64.0)
    node_broker.assert_device_capacity(_DesktopLicense(max_effective_vcpu=0), enforcing=True)


def test_device_capacity_noop_for_deployment_scope(monkeypatch) -> None:
    # Servers license per Compute Unit (assert_deployment_capacity), never per-node vCPU.
    _set_effective_vcpu(monkeypatch, 64.0)
    node_broker.assert_device_capacity(
        _DesktopLicense(scope="deployment", max_effective_vcpu=8), enforcing=True
    )


def test_device_capacity_within_grace_admits(monkeypatch) -> None:
    # An 8-vCPU workstation on an "up to 8" desktop license is fine (inside the 1.25 grace).
    _set_effective_vcpu(monkeypatch, 8.0)
    node_broker.assert_device_capacity(_DesktopLicense(max_effective_vcpu=8), enforcing=True)


def test_device_capacity_refuses_server_class_when_enforcing(monkeypatch) -> None:
    _set_effective_vcpu(monkeypatch, 32.0)  # 4× the 8 ceiling → clearly server-class
    with pytest.raises(node_broker.NodeAdmissionError):
        node_broker.assert_device_capacity(_DesktopLicense(max_effective_vcpu=8), enforcing=True)


def test_device_capacity_dark_observes_but_never_raises(monkeypatch) -> None:
    # DARK (enforcing=False): being over the ceiling logs but MUST NOT raise — brick-safety.
    _set_effective_vcpu(monkeypatch, 32.0)
    node_broker.assert_device_capacity(_DesktopLicense(max_effective_vcpu=8), enforcing=False)


def test_device_vcpu_enforcing_env_gate(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_ENFORCE_DEVICE_VCPU", raising=False)
    assert node_broker.device_vcpu_enforcing() is False  # DARK by default
    monkeypatch.setenv("ALGENTA_ENFORCE_DEVICE_VCPU", "1")
    assert node_broker.device_vcpu_enforcing() is True


# ── engine: claim emission (device scope) ─────────────────────────────────────────


def test_to_license_claims_emits_ceiling_for_device_scope() -> None:
    record = resolve_entitlement("pro", overrides={"max_effective_vcpu": 8})
    claims = to_license_claims(record)
    assert record.license_scope == "device"
    assert claims["max_effective_vcpu"] == 8
    # A device token must NOT gain the deployment-only claims.
    assert "license_scope" not in claims and "max_concurrent_units" not in claims


def test_to_license_claims_omits_ceiling_when_unset() -> None:
    # Byte-identical to before for any plan whose SKU sets no ceiling.
    claims = to_license_claims(resolve_entitlement("pro"))
    assert "max_effective_vcpu" not in claims


# ── engine: compiler + snapshot chain ─────────────────────────────────────────────


def _device_price(*, product_meta=None):
    pm = {
        "lic_schema": "thyn_license_v1",
        "sku_key": "algenta.pro.workstation",
        "product_key": "algenta",
        "edition_key": "pro",
        "license_scope": "device",
        "license_mode": "workstation",
        "qty_metric": "device",
        "deploy_class": "workstation",
        "vcpu_per_unit": "4",
        "workers_per_unit": "0",
        "measure_policy": "cgroup-v1",
        "grace_policy": "community-floor-v1",
        "entitlement_features": "",
    }
    if product_meta:
        pm.update(product_meta)
    return {
        "id": "price_1",
        "unit_amount": 9900,
        "currency": "usd",
        "recurring": {"interval": "month"},
        "lookup_key": "algenta.pro.workstation",
        "livemode": False,
        "metadata": {"qty_min": "1", "qty_max": "100"},
        "product": {"id": "prod_1", "active": True, "metadata": pm},
    }


def test_compiler_reads_max_effective_vcpu_metadata() -> None:
    rel = cc.compile_catalog([_device_price(product_meta={"max_effective_vcpu": "8"})])
    sku = rel.sku("algenta.pro.workstation")
    assert sku.max_effective_vcpu == 8
    # Absent metadata → 0 (no ceiling), never an error.
    rel0 = cc.compile_catalog([_device_price()])
    assert rel0.sku("algenta.pro.workstation").max_effective_vcpu == 0


def test_compiler_rejects_out_of_range_ceiling() -> None:
    with pytest.raises(cc.CatalogCompileError):
        cc.compile_catalog([_device_price(product_meta={"max_effective_vcpu": "99999"})])


def test_snapshot_device_branch_carries_ceiling() -> None:
    sku = cc.compile_catalog([_device_price(product_meta={"max_effective_vcpu": "8"})]).sku(
        "algenta.pro.workstation"
    )
    s = snap.resolve_snapshot(
        source_type=snap.SOURCE_STRIPE,
        org_id="org-1",
        sku=sku,
        quantity=1,
        catalog_release="r1",
        policy_hash="h1",
        stripe_ids={"subscription": "sub_1", "price": "price_1"},
    )
    assert s.license_scope == "device"
    assert s.license_claims["max_effective_vcpu"] == 8
    assert "license_scope" not in s.license_claims  # device token stays device-shaped
