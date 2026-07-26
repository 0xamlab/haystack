"""Deployment (server) scope: Compute-Unit admission, strict-profile routing, and the
deployment-aware Community fallback.

Covers: node_broker.assert_deployment_capacity (local pinned-node unit ceiling), _parse_token
routing of strict-profile tokens through the hardened verifier (incl. cross-product rejection),
and that a lapsed deployment license carries deployment_id into the Community recovery floor.
"""
from __future__ import annotations

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.runtime import capacity, node_broker
from apps.runtime import license as L
from apps.runtime import license_verify as lv


class _FakeLicense:
    def __init__(self, *, scope="deployment", max_units=0, unit_size=4):
        self._scope = scope
        self.max_concurrent_units = max_units
        self._unit_size = unit_size

    def is_deployment_scope(self) -> bool:
        return self._scope == "deployment"

    def unit_size(self) -> int:
        return self._unit_size


def _set_effective_vcpu(monkeypatch, value: float) -> None:
    monkeypatch.setattr(
        capacity,
        "measure_effective_vcpu",
        lambda: capacity.CapacityMeasurement(effective_vcpu=value, source="test", constraints={}),
    )


# ── node_broker.assert_deployment_capacity ───────────────────────────────────────


def test_deployment_capacity_admits_node_within_pool(monkeypatch) -> None:
    _set_effective_vcpu(monkeypatch, 16.0)  # 16 vCPU / 4 = 4 units
    lic = _FakeLicense(max_units=128, unit_size=4)
    node_broker.assert_deployment_capacity(lic, enforcing=True)  # 4 <= 128 → no raise


def test_deployment_capacity_rejects_node_bigger_than_pool(monkeypatch) -> None:
    _set_effective_vcpu(monkeypatch, 96.0)  # 96 / 4 = 24 units
    lic = _FakeLicense(max_units=8, unit_size=4)  # pool only 8
    with pytest.raises(node_broker.NodeAdmissionError):
        node_broker.assert_deployment_capacity(lic, enforcing=True)


def test_deployment_capacity_noop_for_device_scope(monkeypatch) -> None:
    _set_effective_vcpu(monkeypatch, 96.0)
    lic = _FakeLicense(scope="device", max_units=0)
    node_broker.assert_deployment_capacity(lic, enforcing=True)  # never raises for device scope


def test_deployment_capacity_noop_when_dark(monkeypatch) -> None:
    _set_effective_vcpu(monkeypatch, 96.0)
    lic = _FakeLicense(max_units=1, unit_size=4)
    node_broker.assert_deployment_capacity(lic, enforcing=False)  # dark → no raise


def test_node_compute_units_uses_unit_size(monkeypatch) -> None:
    _set_effective_vcpu(monkeypatch, 12.0)
    assert node_broker.node_compute_units(_FakeLicense(unit_size=4)) == 3.0
    assert node_broker.node_compute_units(_FakeLicense(unit_size=6)) == 2.0


# ── strict-profile routing in _parse_token ───────────────────────────────────────


@pytest.fixture()
def strict_env(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    monkeypatch.setenv("ALGENTA_LICENSE_TRUST_BUNDLE", json.dumps({"kid1": pub}))
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "algenta")
    return priv


def _strict_token(priv: str, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://license.algenta.ai",
        "aud": "algenta-runtime",
        "sub": "device-license",
        "jti": "lic-1",
        "iat": now,
        "nbf": now - 5,
        "exp": now + 86400,
        "schema_version": 1,
        "ver": 2,
        "product": "algenta",
        "edition": "server",
        "license_scope": "deployment",
        "deployment_class": "server",
        "deployment_id": "production-us",
        "max_concurrent_units": 128,
        "vcpu_per_unit": 4,
    }
    claims.update(overrides)
    return jwt.encode(claims, priv, algorithm="RS256", headers={"typ": lv.LICENSE_TYP, "kid": "kid1"})


def test_parse_token_routes_strict_deployment_token(strict_env) -> None:
    lic = L._parse_token(_strict_token(strict_env))
    assert lic is not None and lic.valid
    assert lic.source == "strict"
    assert lic.is_deployment_scope()
    assert lic.deployment_id == "production-us"
    assert lic.max_concurrent_units == 128


def test_parse_token_rejects_cross_product_strict_token(strict_env) -> None:
    # A Telys strict license must not verify on an Algenta runtime.
    assert L._parse_token(_strict_token(strict_env, product="telys")) is None


def test_parse_token_rejects_strict_token_with_no_trust_bundle(monkeypatch) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    monkeypatch.delenv("ALGENTA_LICENSE_TRUST_BUNDLE", raising=False)
    monkeypatch.delenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("ALGENTA_LICENSE_PUBLIC_KEY", raising=False)
    assert L._parse_token(_strict_token(priv)) is None  # kid not resolvable → rejected, no fallthrough


# ── deployment-aware Community fallback ──────────────────────────────────────────


class _BoundLicense:
    """A deployment license: bound to a thumbprint but active_node_limit=0 (units are the metric)."""

    def __init__(self, thumbprint: str):
        self.device_pubkey_thumbprint = thumbprint
        self.source = "strict"

    def node_limit(self) -> int:
        return 0  # deployment scope: node cap is 0 (Compute Units, not nodes)


def test_bound_deployment_license_enforced_despite_zero_node_limit(monkeypatch) -> None:
    # THE fix: a bound deployment license (active_node_limit=0) must still be pinned to its node.
    # Copying the offline response to a different node (different key) must fail closed.
    lic = _BoundLicense("ed25519:NODE_A")
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:NODE_B")
    with pytest.raises(node_broker.NodeAdmissionError, match="not the licensed node"):
        node_broker.assert_node_binding(lic, enforcing=True)
    # On the bound node itself → admitted
    monkeypatch.setattr(node_broker, "resolve_node_identity", lambda: "ed25519:NODE_A")
    node_broker.assert_node_binding(lic, enforcing=True)  # no raise


def test_unbound_license_still_noop_binding() -> None:
    # An unbound token (no thumbprint) is still a binding no-op (L2 census handles it).
    lic = _BoundLicense("")
    node_broker.assert_node_binding(lic, enforcing=True)  # no raise


def test_community_floor_never_blocked_by_node_binding() -> None:
    """never-hard-cut: the Community fallback (unbound, no license_id, active_node_limit=1) must
    NOT be hard-blocked by node enforcement — even with enforcement ON."""
    community = L._make_community_license(reason="lapsed", deployment_id="prod")
    # would otherwise raise (unbound token with a finite node limit) — the exemption prevents it
    node_broker.assert_node_binding(community, enforcing=True)  # no raise


def test_community_floor_is_recognized() -> None:
    community = L._make_community_license(reason="lapsed")
    assert node_broker._is_community_floor(community) is True
    # a normal license is not exempt
    assert node_broker._is_community_floor(_FakeLicense()) is False


def test_community_fallback_carries_deployment_id() -> None:
    lic = L._make_community_license(reason="lapsed", deployment_id="production-us")
    assert lic.valid and lic.plan == "algenta_free"
    assert lic.license_scope == "device"  # recovers to personal-device floor, not deployment
    assert lic.deployment_id == "production-us"  # retained for once-per-deployment election
    assert lic.active_node_limit == 1 and lic.concurrent_worker_limit == 1
    assert lic.commercial_use is False


def test_runtime_product_default(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_RUNTIME_PRODUCT", raising=False)
    assert L._runtime_product() == "algenta"
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    assert L._runtime_product() == "codna"


def test_production_profile_rejects_dev_secret_hs256_forgery(monkeypatch) -> None:
    """Under the production/strict profile (require_local_license), a token forged with the
    source-visible HS256 dev secret is rejected — the anti-forgery guarantee (the critique's #1
    finding). This is the runtime half of the RS256-only artifact split."""
    import jwt

    monkeypatch.setenv("ALGENTA_REQUIRE_LOCAL_LICENSE", "1")
    forged = jwt.encode(
        {"ver": 2, "plan": "enterprise", "device_id": "x", "sub": "device-license"},
        L._DEV_SECRET,
        algorithm="HS256",
    )
    assert L._parse_token(forged) is None
