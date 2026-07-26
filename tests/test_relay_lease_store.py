"""Relay HA — SqliteLeaseLedger shared/persistent ledger (apps/runtime/relay_lease_store.py).

Two ledger instances over the SAME file model two Relay replicas: they share pool state, so the
ceiling holds cluster-wide (no double-allocation) — the HA guarantee. Also verifies semantic
parity with the in-memory ledger (idempotent, borrow-with-expiry, release, node ceiling) and that
the relay app can be built on the shared ledger.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from apps.runtime import relay_delegation as rd
from apps.runtime.relay_lease import LeaseError
from apps.runtime.relay_lease_store import SqliteLeaseLedger
from apps.runtime.relay_server import create_relay_app


def test_shared_state_prevents_double_allocation(tmp_path: Path) -> None:
    db = tmp_path / "pool.db"
    # two "replicas" over the same shared file
    replica_a = SqliteLeaseLedger(db, max_units=10)
    replica_b = SqliteLeaseLedger(db, max_units=10)

    replica_a.acquire("node-a", 8, now=1000)
    # replica B sees replica A's 8 units and can only grant 2 more — the HA no-double-allocate guarantee
    assert replica_b.used_units(1000) == 8
    assert replica_b.available_units(1000) == 2
    with pytest.raises(LeaseError, match="pool exhausted"):
        replica_b.acquire("node-b", 8, now=1000)
    replica_b.acquire("node-b", 2, now=1000)  # fits
    assert replica_a.used_units(1000) == 10  # replica A also sees the full pool now


def test_idempotent_across_replicas(tmp_path: Path) -> None:
    db = tmp_path / "pool.db"
    a = SqliteLeaseLedger(db, max_units=10)
    b = SqliteLeaseLedger(db, max_units=10)
    a.acquire("node-a", 6, now=0)
    b.acquire("node-a", 6, now=1)  # same node re-acquiring on another replica — no double count
    assert a.used_units(2) == 6


def test_borrow_and_reclaim(tmp_path: Path) -> None:
    led = SqliteLeaseLedger(tmp_path / "p.db", max_units=8)
    led.acquire("a", 8, now=0, ttl=100, borrow=1000)
    assert led.used_units(200) == 8  # within borrow window → still reserved
    # past both TTL and borrow → reclaimed
    led.acquire("b", 8, now=2000)
    assert led.used_units(2000) == 8


def test_release_frees_across_replicas(tmp_path: Path) -> None:
    db = tmp_path / "p.db"
    a = SqliteLeaseLedger(db, max_units=8)
    b = SqliteLeaseLedger(db, max_units=8)
    a.acquire("a", 8, now=0, ttl=100, borrow=10_000)
    a.release("a", now=5)
    assert b.available_units(5) == 8  # the other replica immediately sees the freed units


def test_node_ceiling_shared(tmp_path: Path) -> None:
    led = SqliteLeaseLedger(tmp_path / "p.db", max_units=100, node_ceiling=2)
    led.acquire("a", 1, now=0)
    led.acquire("b", 1, now=0)
    with pytest.raises(LeaseError, match="node ceiling"):
        led.acquire("c", 1, now=0)


def test_renew_unknown_raises(tmp_path: Path) -> None:
    led = SqliteLeaseLedger(tmp_path / "p.db", max_units=8)
    with pytest.raises(LeaseError, match="re-acquire"):
        led.renew("ghost", now=0)


def test_relay_app_on_shared_ledger(tmp_path: Path) -> None:
    # The relay app builds on a shared ledger via ledger_factory (the HA wiring).
    def _kp():
        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        return (
            k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
            k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
        )
    root_priv, root_pub = _kp()
    relay_priv, relay_pub = _kp()
    pool_root = rd.sign_pool_root(root_priv, customer_id="c", relay_public_key_pem=relay_pub,
                                  permitted_products=["algenta"], max_concurrent_units=16, kid="root-kid")
    db = tmp_path / "relay.db"
    app = create_relay_app(
        pool_root_token=pool_root, relay_private_key_pem=relay_priv, relay_public_key_pem=relay_pub,
        vendor_trust_bundle={"root-kid": root_pub},
        ledger_factory=lambda max_units, node_ceiling: SqliteLeaseLedger(db, max_units, node_ceiling=node_ceiling),
    )
    c = TestClient(app)
    assert c.get("/v1/relay/status").json()["pool_units"] == 16
    r = c.post("/v1/relay/lease", json={"node_public_key_thumbprint": "n", "deployment_id": "d",
                                        "product": "algenta", "units": 8})
    assert r.status_code == 200, r.text
    # the lease persisted in the shared DB — a fresh ledger over the same file sees it
    assert SqliteLeaseLedger(db, max_units=16).used_units(r.json()["expires_at"] - 1) == 8
