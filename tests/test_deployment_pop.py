"""Deployment-key proof-of-possession for the L3 node heartbeat.

A node must prove it holds the private key matching the node_thumbprint it claims (sign a server
nonce) — so an org API key alone can't spoof node identities. Default OFF (API-key-only, back-
compat); ALGENTA_REQUIRE_DEPLOYMENT_POP=1 makes it mandatory; supplied PoP is always verified.
"""
from __future__ import annotations

import base64
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.organization import OrgPlan
from apps.runtime.device_keypair import thumbprint_for_public_pem
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.fixture(autouse=True)
def _redis_override(app):  # noqa: F811
    stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return stub

    app.dependency_overrides[get_redis] = _fake_redis
    yield
    app.dependency_overrides.pop(get_redis, None)


def _signing_key() -> str:
    from cryptography.hazmat.primitives.asymmetric import rsa

    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return k.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


def _node_keypair() -> tuple[Ed25519PrivateKey, str, str]:
    priv = Ed25519PrivateKey.generate()
    pub_pem = (
        priv.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    thumb = thumbprint_for_public_pem(pub_pem)
    return priv, pub_pem, thumb


async def _activate(client, key, dep_id, units):
    return await client.post(
        "/v1/deployment/activate", headers={"X-API-Key": key},
        json={"deployment_id": dep_id, "deployment_pubkey_thumbprint": "ed25519:D", "units": units},
    )


@pytest.mark.anyio
async def test_full_pop_flow_admits(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    monkeypatch.setenv("ALGENTA_REQUIRE_DEPLOYMENT_POP", "1")
    owner_key, _ = await _seed_api_key(label="PoP Owner", expires_at=None, plan=OrgPlan.ALGENTA_SERVER)  # noqa: F405
    dep = f"prod-{uuid4().hex[:8]}"
    assert (await _activate(client, owner_key, dep, 4)).status_code == 200
    h = {"X-API-Key": owner_key}
    priv, pub_pem, thumb = _node_keypair()

    # 1. challenge → nonce
    ch = await client.post("/v1/deployment/node/challenge", headers=h,
                           json={"deployment_id": dep, "node_thumbprint": thumb})
    assert ch.status_code == 200, ch.text
    nonce_b64 = ch.json()["nonce"]

    # 2. sign the nonce with the node's deployment key
    sig = base64.b64encode(priv.sign(base64.b64decode(nonce_b64))).decode()

    # 3. heartbeat with PoP → admitted
    r = await client.post("/v1/deployment/node/heartbeat", headers=h, json={
        "deployment_id": dep, "node_thumbprint": thumb, "units": 2,
        "nonce": nonce_b64, "public_key_pem": pub_pem, "signature": sig,
    })
    assert r.status_code == 200, r.text
    assert r.json()["used_units"] == 2


@pytest.mark.anyio
async def test_required_pop_rejects_missing_proof(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    monkeypatch.setenv("ALGENTA_REQUIRE_DEPLOYMENT_POP", "1")
    owner_key, _ = await _seed_api_key(label="PoP Owner 2", expires_at=None, plan=OrgPlan.ALGENTA_SERVER)  # noqa: F405
    dep = f"prod-{uuid4().hex[:8]}"
    assert (await _activate(client, owner_key, dep, 4)).status_code == 200
    r = await client.post("/v1/deployment/node/heartbeat", headers={"X-API-Key": owner_key},
                          json={"deployment_id": dep, "node_thumbprint": "ed25519:X", "units": 2})
    assert r.status_code == 401
    assert "pop_required" in r.text


@pytest.mark.anyio
async def test_supplied_pop_with_thumbprint_mismatch_rejected(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    monkeypatch.delenv("ALGENTA_REQUIRE_DEPLOYMENT_POP", raising=False)  # not required, but supplied → verified
    owner_key, _ = await _seed_api_key(label="PoP Owner 3", expires_at=None, plan=OrgPlan.ALGENTA_SERVER)  # noqa: F405
    dep = f"prod-{uuid4().hex[:8]}"
    assert (await _activate(client, owner_key, dep, 4)).status_code == 200
    h = {"X-API-Key": owner_key}
    priv, pub_pem, thumb = _node_keypair()
    ch = await client.post("/v1/deployment/node/challenge", headers=h,
                           json={"deployment_id": dep, "node_thumbprint": "ed25519:CLAIMED-OTHER"})
    nonce_b64 = ch.json()["nonce"]
    sig = base64.b64encode(priv.sign(base64.b64decode(nonce_b64))).decode()
    # claims a thumbprint that does NOT match the presented public key → rejected
    r = await client.post("/v1/deployment/node/heartbeat", headers=h, json={
        "deployment_id": dep, "node_thumbprint": "ed25519:CLAIMED-OTHER", "units": 2,
        "nonce": nonce_b64, "public_key_pem": pub_pem, "signature": sig,
    })
    assert r.status_code == 401
    assert "pop_thumbprint_mismatch" in r.text


@pytest.mark.anyio
async def test_bad_signature_rejected(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    monkeypatch.setenv("ALGENTA_REQUIRE_DEPLOYMENT_POP", "1")
    owner_key, _ = await _seed_api_key(label="PoP Owner 4", expires_at=None, plan=OrgPlan.ALGENTA_SERVER)  # noqa: F405
    dep = f"prod-{uuid4().hex[:8]}"
    assert (await _activate(client, owner_key, dep, 4)).status_code == 200
    h = {"X-API-Key": owner_key}
    priv, pub_pem, thumb = _node_keypair()
    ch = await client.post("/v1/deployment/node/challenge", headers=h,
                           json={"deployment_id": dep, "node_thumbprint": thumb})
    nonce_b64 = ch.json()["nonce"]
    # sign GARBAGE instead of the nonce
    sig = base64.b64encode(priv.sign(b"not-the-nonce")).decode()
    r = await client.post("/v1/deployment/node/heartbeat", headers=h, json={
        "deployment_id": dep, "node_thumbprint": thumb, "units": 2,
        "nonce": nonce_b64, "public_key_pem": pub_pem, "signature": sig,
    })
    assert r.status_code == 401
    assert "pop_signature_invalid" in r.text


@pytest.mark.anyio
async def test_nonce_is_single_use(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    monkeypatch.setenv("ALGENTA_REQUIRE_DEPLOYMENT_POP", "1")
    owner_key, _ = await _seed_api_key(label="PoP Owner 5", expires_at=None, plan=OrgPlan.ALGENTA_SERVER)  # noqa: F405
    dep = f"prod-{uuid4().hex[:8]}"
    assert (await _activate(client, owner_key, dep, 4)).status_code == 200
    h = {"X-API-Key": owner_key}
    priv, pub_pem, thumb = _node_keypair()
    ch = await client.post("/v1/deployment/node/challenge", headers=h,
                           json={"deployment_id": dep, "node_thumbprint": thumb})
    nonce_b64 = ch.json()["nonce"]
    sig = base64.b64encode(priv.sign(base64.b64decode(nonce_b64))).decode()
    body = {"deployment_id": dep, "node_thumbprint": thumb, "units": 2,
            "nonce": nonce_b64, "public_key_pem": pub_pem, "signature": sig}
    assert (await client.post("/v1/deployment/node/heartbeat", headers=h, json=body)).status_code == 200
    # replay the same nonce → rejected (consumed)
    r2 = await client.post("/v1/deployment/node/heartbeat", headers=h, json=body)
    assert r2.status_code == 401
    assert "pop_nonce_invalid" in r2.text


@pytest.mark.anyio
async def test_pop_optional_when_flag_off(client, monkeypatch) -> None:
    # back-compat: with the flag off and no PoP supplied, heartbeat works on API key alone
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    monkeypatch.delenv("ALGENTA_REQUIRE_DEPLOYMENT_POP", raising=False)
    owner_key, _ = await _seed_api_key(label="PoP Owner 6", expires_at=None, plan=OrgPlan.ALGENTA_SERVER)  # noqa: F405
    dep = f"prod-{uuid4().hex[:8]}"
    assert (await _activate(client, owner_key, dep, 4)).status_code == 200
    r = await client.post("/v1/deployment/node/heartbeat", headers={"X-API-Key": owner_key},
                          json={"deployment_id": dep, "node_thumbprint": "ed25519:Z", "units": 2})
    assert r.status_code == 200, r.text
