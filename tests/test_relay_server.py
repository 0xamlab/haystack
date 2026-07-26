"""Algenta Relay HTTP heartbeat service (apps/runtime/relay_server.py).

DB-less TestClient tests: pool-ceiling enforcement over HTTP, signed leases that verify through
the delegation chain, heartbeat renewal, release, idempotency, and construction fail-closed when
the pool root doesn't bind this relay's key.
"""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from apps.runtime import relay_delegation as rd
from apps.runtime.relay_server import create_relay_app


def _kp():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
        k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
    )


@pytest.fixture()
def relay():
    root_priv, root_pub = _kp()
    relay_priv, relay_pub = _kp()
    trust = {"root-kid": root_pub}
    pool_root = rd.sign_pool_root(
        root_priv, customer_id="cust-1", relay_public_key_pem=relay_pub,
        permitted_products=["algenta"], max_concurrent_units=16, kid="root-kid",
        max_lease_ttl_seconds=600,
    )
    app = create_relay_app(
        pool_root_token=pool_root, relay_private_key_pem=relay_priv,
        relay_public_key_pem=relay_pub, vendor_trust_bundle=trust, relay_id="relay-1",
    )
    return {"client": TestClient(app), "trust": trust, "relay_pub": relay_pub,
            "pool_root": pool_root}


def test_status_reports_pool(relay) -> None:
    r = relay["client"].get("/v1/relay/status")
    assert r.status_code == 200
    assert r.json()["pool_units"] == 16
    assert r.json()["available_units"] == 16


def test_lease_grants_and_verifies_through_chain(relay) -> None:
    c = relay["client"]
    r = c.post("/v1/relay/lease", json={"node_public_key_thumbprint": "node-a",
               "deployment_id": "prod", "product": "algenta", "units": 8})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["granted_units"] == 8 and body["available_units"] == 8

    # the returned lease verifies through the full delegation chain
    pool = rd.verify_pool_root(relay["pool_root"], trust_bundle=relay["trust"])
    v = rd.verify_node_lease(body["lease_token"], pool_root=pool,
                             relay_public_key_pem=relay["relay_pub"], expected_product="algenta")
    assert v.granted_units == 8 and v.node_thumbprint == "node-a"


def test_pool_ceiling_enforced_over_http(relay) -> None:
    c = relay["client"]
    assert c.post("/v1/relay/lease", json={"node_public_key_thumbprint": "a",
                  "deployment_id": "d", "product": "algenta", "units": 10}).status_code == 200
    # 10 + 8 > 16 → refused
    r = c.post("/v1/relay/lease", json={"node_public_key_thumbprint": "b",
               "deployment_id": "d", "product": "algenta", "units": 8})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "pool_exhausted"


def test_lease_is_idempotent_over_http(relay) -> None:
    c = relay["client"]
    for _ in range(3):
        assert c.post("/v1/relay/lease", json={"node_public_key_thumbprint": "a",
                      "deployment_id": "d", "product": "algenta", "units": 8}).status_code == 200
    assert relay["client"].get("/v1/relay/status").json()["used_units"] == 8  # not 24


def test_heartbeat_then_release(relay) -> None:
    c = relay["client"]
    assert c.post("/v1/relay/lease", json={"node_public_key_thumbprint": "a",
                  "deployment_id": "d", "product": "algenta", "units": 8}).status_code == 200
    assert c.post("/v1/relay/heartbeat", json={"node_public_key_thumbprint": "a"}).status_code == 200
    assert c.post("/v1/relay/release", json={"node_public_key_thumbprint": "a"}).status_code == 200
    assert relay["client"].get("/v1/relay/status").json()["used_units"] == 0


def test_heartbeat_unknown_node_409(relay) -> None:
    r = relay["client"].post("/v1/relay/heartbeat", json={"node_public_key_thumbprint": "ghost"})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "no_active_lease"


def test_product_not_in_pool_refused(relay) -> None:
    r = relay["client"].post("/v1/relay/lease", json={"node_public_key_thumbprint": "a",
                             "deployment_id": "d", "product": "telys", "units": 4})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "product_not_in_pool"


def test_bad_product_request_does_not_clobber_existing_lease(relay) -> None:
    c = relay["client"]
    # node holds a valid 8-unit lease for the permitted product
    assert c.post("/v1/relay/lease", json={"node_public_key_thumbprint": "a",
                  "deployment_id": "d", "product": "algenta", "units": 8}).status_code == 200
    # a bad-product request for the SAME node is refused WITHOUT destroying the good lease
    r = c.post("/v1/relay/lease", json={"node_public_key_thumbprint": "a",
               "deployment_id": "d", "product": "telys", "units": 8})
    assert r.status_code == 403
    assert relay["client"].get("/v1/relay/status").json()["used_units"] == 8  # lease intact


def test_construction_fails_if_pool_root_binds_other_relay() -> None:
    root_priv, root_pub = _kp()
    relay_priv, relay_pub = _kp()
    other_priv, other_pub = _kp()
    pool_root = rd.sign_pool_root(
        root_priv, customer_id="c", relay_public_key_pem=other_pub,  # binds a DIFFERENT relay key
        permitted_products=["algenta"], max_concurrent_units=8, kid="root-kid",
    )
    with pytest.raises(ValueError, match="does not bind this relay"):
        create_relay_app(pool_root_token=pool_root, relay_private_key_pem=relay_priv,
                         relay_public_key_pem=relay_pub, vendor_trust_bundle={"root-kid": root_pub})
