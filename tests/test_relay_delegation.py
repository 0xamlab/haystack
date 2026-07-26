"""Relay delegation chain (apps/runtime/relay_delegation.py).

Vendor root → pool root (binds relay key) → relay-signed node lease. Verifies the chain holds,
and that a lease signed by a DIFFERENT relay key than the pool root binds is rejected (the
theft-of-pool-root-file-without-relay-key defense).
"""
from __future__ import annotations

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.runtime import relay_delegation as rd


def _kp():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = k.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub = (
        k.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv, pub


@pytest.fixture(scope="module")
def keys():
    root_priv, root_pub = _kp()
    relay_priv, relay_pub = _kp()
    evil_priv, evil_pub = _kp()
    return {
        "root_priv": root_priv, "trust": {"root-kid": root_pub},
        "relay_priv": relay_priv, "relay_pub": relay_pub,
        "evil_priv": evil_priv, "evil_pub": evil_pub,
    }


def _pool_root(keys, *, units=64, products=("algenta",), relay_pub=None):
    return rd.sign_pool_root(
        keys["root_priv"], customer_id="cust-1",
        relay_public_key_pem=relay_pub or keys["relay_pub"],
        permitted_products=list(products), max_concurrent_units=units, kid="root-kid",
    )


def test_pool_root_verifies_and_binds_relay(keys) -> None:
    pr = rd.verify_pool_root(_pool_root(keys), trust_bundle=keys["trust"])
    assert pr.max_concurrent_units == 64
    assert pr.relay_thumbprint == rd.key_thumbprint(keys["relay_pub"])
    assert pr.permitted_products == ("algenta",)


def test_pool_root_unknown_kid_rejected(keys) -> None:
    with pytest.raises(rd.RelayVerificationError) as e:
        rd.verify_pool_root(_pool_root(keys), trust_bundle={"other": keys["trust"]["root-kid"]})
    assert e.value.reason == "kid_unknown"


def test_pool_root_wrong_root_key_rejected(keys) -> None:
    forged = rd.sign_pool_root(
        keys["evil_priv"], customer_id="c", relay_public_key_pem=keys["relay_pub"],
        permitted_products=["algenta"], max_concurrent_units=64, kid="root-kid",
    )
    with pytest.raises(rd.RelayVerificationError) as e:
        rd.verify_pool_root(forged, trust_bundle=keys["trust"])
    assert e.value.reason == "invalid_token"


def test_node_lease_chain_verifies(keys) -> None:
    pr = rd.verify_pool_root(_pool_root(keys), trust_bundle=keys["trust"])
    lease = rd.sign_node_lease(
        keys["relay_priv"], pool_license_id="pool-1", relay_id="relay-1",
        node_public_key_thumbprint="ed25519:NODE", deployment_id="prod",
        product="algenta", granted_units=8, ttl_seconds=300,
    )
    v = rd.verify_node_lease(lease, pool_root=pr, relay_public_key_pem=keys["relay_pub"],
                             expected_product="algenta")
    assert v.granted_units == 8
    assert v.node_thumbprint == "ed25519:NODE"
    assert v.deployment_id == "prod"


def test_lease_signed_by_wrong_relay_key_rejected(keys) -> None:
    # Pool root binds the real relay key; a lease signed by the EVIL key (whose pub we present)
    # is rejected because that key's thumbprint != the bound thumbprint (stolen-file defense).
    pr = rd.verify_pool_root(_pool_root(keys), trust_bundle=keys["trust"])
    forged = rd.sign_node_lease(
        keys["evil_priv"], pool_license_id="pool-1", relay_id="relay-1",
        node_public_key_thumbprint="ed25519:NODE", deployment_id="prod",
        product="algenta", granted_units=8, ttl_seconds=300,
    )
    with pytest.raises(rd.RelayVerificationError) as e:
        rd.verify_node_lease(forged, pool_root=pr, relay_public_key_pem=keys["evil_pub"])
    assert e.value.reason == "relay_key_mismatch"


def test_lease_tampered_signature_rejected(keys) -> None:
    # A lease that claims to be from the bound relay but is actually signed by evil key with the
    # REAL relay pub presented → signature verification fails.
    pr = rd.verify_pool_root(_pool_root(keys), trust_bundle=keys["trust"])
    forged = rd.sign_node_lease(
        keys["evil_priv"], pool_license_id="p", relay_id="r",
        node_public_key_thumbprint="n", deployment_id="d", product="algenta",
        granted_units=8, ttl_seconds=300,
    )
    with pytest.raises(rd.RelayVerificationError) as e:
        rd.verify_node_lease(forged, pool_root=pr, relay_public_key_pem=keys["relay_pub"])
    assert e.value.reason == "invalid_token"  # bad signature under the real relay pub


def test_expired_lease_rejected(keys) -> None:
    pr = rd.verify_pool_root(_pool_root(keys), trust_bundle=keys["trust"])
    old = int(time.time()) - 10_000
    lease = rd.sign_node_lease(
        keys["relay_priv"], pool_license_id="p", relay_id="r",
        node_public_key_thumbprint="n", deployment_id="d", product="algenta",
        granted_units=8, ttl_seconds=300, now=old,
    )
    with pytest.raises(rd.RelayVerificationError) as e:
        rd.verify_node_lease(lease, pool_root=pr, relay_public_key_pem=keys["relay_pub"])
    assert e.value.reason == "expired"


def test_product_not_in_pool_rejected(keys) -> None:
    pr = rd.verify_pool_root(_pool_root(keys, products=("algenta",)), trust_bundle=keys["trust"])
    lease = rd.sign_node_lease(
        keys["relay_priv"], pool_license_id="p", relay_id="r",
        node_public_key_thumbprint="n", deployment_id="d", product="telys",
        granted_units=8, ttl_seconds=300,
    )
    with pytest.raises(rd.RelayVerificationError) as e:
        rd.verify_node_lease(lease, pool_root=pr, relay_public_key_pem=keys["relay_pub"],
                             expected_product="telys")
    assert e.value.reason == "product_not_in_pool"


def test_thumbprint_is_stable_and_key_specific(keys) -> None:
    assert rd.key_thumbprint(keys["relay_pub"]) == rd.key_thumbprint(keys["relay_pub"])
    assert rd.key_thumbprint(keys["relay_pub"]) != rd.key_thumbprint(keys["evil_pub"])
