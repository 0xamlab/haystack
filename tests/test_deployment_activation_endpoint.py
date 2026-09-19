"""Integration test for POST /v1/deployment/activate (the connected server-license path).

Verifies the wiring: auth → org entitlement → mint bound strict-profile deployment license →
persist a DeploymentLicenseRegistration; a non-server org is refused; the minted token verifies.
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.deployment_license import DeploymentLicenseRegistration
from apps.api_server.models.organization import OrgPlan
from apps.runtime import license_verify as lv
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.fixture(autouse=True)
def _redis_override(app):  # noqa: F811
    """The auth middleware resolves a Redis client; stub it (no real Redis in tests)."""
    stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return stub

    app.dependency_overrides[get_redis] = _fake_redis
    yield
    app.dependency_overrides.pop(get_redis, None)


def _keypair():
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


@pytest.mark.anyio
async def test_activate_deployment_endpoint_mints_and_persists(client, monkeypatch) -> None:
    priv, pub = _keypair()
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", priv)
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_KID", "kid1")

    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Server Owner", expires_at=None, plan=OrgPlan.ALGENTA_SERVER
    )
    dep_id = f"production-{uuid4().hex[:8]}"  # unique — the test DB is shared across runs

    resp = await client.post(
        "/v1/deployment/activate",
        headers={"X-API-Key": owner_key},
        json={"deployment_id": dep_id, "deployment_pubkey_thumbprint": "ed25519:DEPLOY"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["deployment_id"] == dep_id
    assert data["product"] == "algenta"
    assert data["max_concurrent_units"] >= 1
    assert data["license_jti"]

    # the minted token is a strict-profile, bound, verifiable deployment license
    token = data["license_token"]
    assert lv.is_strict_profile_token(token)
    verified = lv.verify_license_token(token, expected_product="algenta", trust_bundle={"kid1": pub})
    assert verified.payload["license_scope"] == "deployment"
    assert verified.payload["deployment_id"] == dep_id
    assert verified.payload["device_pubkey_thumbprint"] == "ed25519:DEPLOY"
    # The jti the endpoint reports (and persists for revocation) IS the jti inside the SIGNED
    # token — established by choosing it before minting, not by decoding the token unverified.
    assert verified.payload["jti"] == data["license_jti"]
    assert verified.payload["license_id"] == data["license_jti"]

    # a registration row was persisted (scope the query to this run's unique deployment id)
    from apps.api_server.db.session import AsyncSessionLocal  # noqa: F405

    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(DeploymentLicenseRegistration).where(
                    DeploymentLicenseRegistration.deployment_id == dep_id
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].product == "algenta"
    assert rows[0].deployment_pubkey_thumbprint == "ed25519:DEPLOY"


@pytest.mark.anyio
async def test_activate_is_idempotent_updates_row(client, monkeypatch) -> None:
    priv, _ = _keypair()
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", priv)
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Server Owner 2", expires_at=None, plan=OrgPlan.ALGENTA_SERVER
    )
    dep_id = f"dep-{uuid4().hex[:8]}"
    body = {"deployment_id": dep_id, "deployment_pubkey_thumbprint": "ed25519:K1"}
    r1 = await client.post("/v1/deployment/activate", headers={"X-API-Key": owner_key}, json=body)
    assert r1.status_code == 200, r1.text
    # re-activate same deployment with a rotated key → updates the single row, not a second one
    body2 = {"deployment_id": dep_id, "deployment_pubkey_thumbprint": "ed25519:K2"}
    r2 = await client.post("/v1/deployment/activate", headers={"X-API-Key": owner_key}, json=body2)
    assert r2.status_code == 200, r2.text

    from apps.api_server.db.session import AsyncSessionLocal  # noqa: F405

    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(DeploymentLicenseRegistration).where(
                    DeploymentLicenseRegistration.deployment_id == dep_id
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].deployment_pubkey_thumbprint == "ed25519:K2"


@pytest.mark.anyio
async def test_pool_is_shared_across_deployments_not_multiplied(client, monkeypatch) -> None:
    """The over-provisioning fix: an org's purchased pool (default 4 units for *_server) is split
    across its deployments — the SUM can never exceed the pool, so N units stay N total, not N×K."""
    priv, _ = _keypair()
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", priv)
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Pool Owner", expires_at=None, plan=OrgPlan.ALGENTA_SERVER
    )
    h = {"X-API-Key": owner_key}
    a = f"dep-a-{uuid4().hex[:8]}"
    b = f"dep-b-{uuid4().hex[:8]}"

    # dep-a takes 3 of the pool of 4
    r1 = await client.post("/v1/deployment/activate", headers=h,
                           json={"deployment_id": a, "deployment_pubkey_thumbprint": "k1", "units": 3})
    assert r1.status_code == 200, r1.text
    assert r1.json()["max_concurrent_units"] == 3
    assert r1.json()["pool_units"] == 4
    assert r1.json()["pool_allocated_units"] == 3

    # dep-b asking for 2 more would total 5 > 4 → refused
    r2 = await client.post("/v1/deployment/activate", headers=h,
                           json={"deployment_id": b, "deployment_pubkey_thumbprint": "k2", "units": 2})
    assert r2.status_code == 409, r2.text
    assert "pool_exceeded" in r2.text

    # dep-b asking for the remaining 1 → allowed, pool now fully allocated
    r3 = await client.post("/v1/deployment/activate", headers=h,
                           json={"deployment_id": b, "deployment_pubkey_thumbprint": "k2", "units": 1})
    assert r3.status_code == 200, r3.text
    assert r3.json()["pool_allocated_units"] == 4

    # a third deployment gets nothing left → refused (exhausted)
    c = f"dep-c-{uuid4().hex[:8]}"
    r4 = await client.post("/v1/deployment/activate", headers=h,
                           json={"deployment_id": c, "deployment_pubkey_thumbprint": "k3"})
    assert r4.status_code == 409, r4.text
    assert "pool_exhausted" in r4.text


@pytest.mark.anyio
async def test_non_server_plan_is_refused(client, monkeypatch) -> None:
    priv, _ = _keypair()
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", priv)
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Pro Owner", expires_at=None, plan=OrgPlan.ALGENTA_PRO
    )
    resp = await client.post(
        "/v1/deployment/activate",
        headers={"X-API-Key": owner_key},
        json={"deployment_id": "d", "deployment_pubkey_thumbprint": "ed25519:K"},
    )
    assert resp.status_code == 403
    assert "no_deployment_entitlement" in resp.text  # envelope shape is app-defined


@pytest.mark.anyio
async def test_missing_binding_is_rejected(client, monkeypatch) -> None:
    priv, _ = _keypair()
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", priv)
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Server Owner 3", expires_at=None, plan=OrgPlan.ALGENTA_SERVER
    )
    resp = await client.post(
        "/v1/deployment/activate",
        headers={"X-API-Key": owner_key},
        json={"deployment_id": "d", "deployment_pubkey_thumbprint": ""},
    )
    assert resp.status_code == 422  # pydantic min_length or activation guard
