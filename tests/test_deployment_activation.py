"""Deployment activation end-to-end (C): Stripe catalog → EntitlementSnapshot → signed
strict-profile deployment license → strict-verifier round-trip.

Proves the whole server chain: a purchased Compute-Unit quantity becomes a bound, strictly
verifiable deployment license that a cross-product runtime rejects.
"""
from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api_server.services import entitlement_snapshot as snap
from apps.api_server.services import stripe_catalog_compiler as cc
from apps.api_server.services.deployment_service import (
    DeploymentActivationError,
    build_deployment_license,
)
from apps.runtime import license as L
from apps.runtime import license_verify as lv


@pytest.fixture()
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv, pub


def _server_price(product="algenta"):
    return {
        "id": "price_srv",
        "unit_amount": 22900,
        "currency": "usd",
        "recurring": {"interval": "year"},
        "lookup_key": f"{product}.server.pinned",
        "metadata": {"qty_min": "4", "qty_max": "1024"},
        "product": {
            "id": f"prod_{product}",
            "active": True,
            "metadata": {
                "lic_schema": "thyn_license_v1",
                "sku_key": f"{product}.server.pinned",
                "product_key": product,
                "edition_key": "server",
                "license_scope": "deployment",
                "license_mode": "pinned",
                "qty_metric": "compute_unit",
                "deploy_class": "production_server",
                "vcpu_per_unit": "4",
                "workers_per_unit": "5",
                "measure_policy": "cgroup-v1",
                "grace_policy": "community-floor-v1",
            },
        },
    }


def _snapshot(product="algenta", quantity=64):
    sku = cc.compile_catalog([_server_price(product)]).sku(f"{product}.server.pinned")
    return snap.resolve_snapshot(
        source_type=snap.SOURCE_STRIPE, org_id="org-acme", sku=sku, quantity=quantity,
        catalog_release="r1", policy_hash="h1", stripe_ids={"subscription": "sub_1"},
    )


def test_activate_deployment_mints_verifiable_license(keypair, monkeypatch) -> None:
    priv, pub = keypair
    monkeypatch.setenv("ALGENTA_LICENSE_TRUST_BUNDLE", json.dumps({"kid1": pub}))
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "algenta")

    token = build_deployment_license(
        _snapshot(quantity=64),
        deployment_id="production-us",
        deployment_pubkey_thumbprint="ed25519:DEPLOYKEY",
        private_key_pem=priv,
        kid="kid1",
    )

    # It's a strict-profile token and the strict verifier accepts it.
    assert lv.is_strict_profile_token(token)
    verified = lv.verify_license_token(token, expected_product="algenta", trust_bundle={"kid1": pub})
    assert verified.payload["license_scope"] == "deployment"
    assert verified.payload["deployment_id"] == "production-us"
    assert verified.payload["max_concurrent_units"] == 64
    assert verified.payload["device_pubkey_thumbprint"] == "ed25519:DEPLOYKEY"

    # And the runtime loader parses it as a deployment-scope license.
    lic = L._parse_token(token)
    assert lic is not None and lic.valid and lic.is_deployment_scope()
    assert lic.max_concurrent_units == 64
    assert lic.deployment_id == "production-us"


def test_cross_product_deployment_license_rejected(keypair, monkeypatch) -> None:
    priv, pub = keypair
    # Mint a TELYS deployment license, present it to an ALGENTA runtime → rejected.
    token = build_deployment_license(
        _snapshot(product="telys", quantity=16),
        deployment_id="dep", deployment_pubkey_thumbprint="ed25519:K",
        private_key_pem=priv, kid="kid1",
    )
    _, reason = lv.try_verify_license_token(
        token, expected_product="algenta", trust_bundle={"kid1": pub}
    )
    assert reason == "wrong_product"


def test_activation_requires_deployment_scope() -> None:
    community = snap.resolve_community_snapshot(org_id="o", product="algenta")
    with pytest.raises(DeploymentActivationError, match="requires 'deployment'"):
        build_deployment_license(community, deployment_id="d", deployment_pubkey_thumbprint="k")


def test_activation_requires_binding() -> None:
    with pytest.raises(DeploymentActivationError, match="bound to the deployment key"):
        build_deployment_license(_snapshot(), deployment_id="d", deployment_pubkey_thumbprint="")


def test_all_five_editions_activate_and_verify(keypair, monkeypatch) -> None:
    priv, pub = keypair
    for ed in ["algenta", "codna", "telys", "sqai", "cohenta"]:
        token = build_deployment_license(
            _snapshot(product=ed, quantity=16),
            deployment_id=f"{ed}-prod", deployment_pubkey_thumbprint="ed25519:K",
            private_key_pem=priv, kid="kid1",
        )
        v = lv.verify_license_token(token, expected_product=ed, trust_bundle={"kid1": pub})
        assert v.payload["product"] == ed
        assert v.payload["license_scope"] == "deployment"
        assert v.payload["max_concurrent_units"] == 16
        assert ed in v.payload["products"]
        # cross-product isolation: this edition's license fails on any OTHER edition's runtime
        other = "codna" if ed != "codna" else "telys"
        _, reason = lv.try_verify_license_token(token, expected_product=other, trust_bundle={"kid1": pub})
        assert reason == "wrong_product"


def test_activation_refuses_uncapped(keypair) -> None:
    priv, _ = keypair
    # A snapshot whose claims somehow carry no unit ceiling must not mint.
    s = _snapshot()
    s.license_claims["max_concurrent_units"] = 0
    with pytest.raises(DeploymentActivationError, match="uncapped"):
        build_deployment_license(
            s, deployment_id="d", deployment_pubkey_thumbprint="k", private_key_pem=priv
        )
