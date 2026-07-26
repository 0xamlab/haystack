"""L3 connected-pool authority — POST /v1/deployment/node/heartbeat.

Server-side unit-weighted node admission against a deployment's pool: nodes are admitted while
their summed units fit the pool; the over-cap node is refused (never evicting peers); a node
re-heartbeating is idempotent; heartbeat against an un-activated deployment 404s.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.organization import OrgPlan
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.fixture(autouse=True)
def _redis_override(app):  # noqa: F811
    stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return stub

    app.dependency_overrides[get_redis] = _fake_redis
    yield
    app.dependency_overrides.pop(get_redis, None)


def _signing_key():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return k.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


async def _activate(client, key, dep_id, units):
    return await client.post(
        "/v1/deployment/activate",
        headers={"X-API-Key": key},
        json={"deployment_id": dep_id, "deployment_pubkey_thumbprint": "ed25519:D", "units": units},
    )


@pytest.mark.anyio
async def test_node_heartbeat_admits_within_pool_and_blocks_over(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="L3 Owner", expires_at=None, plan=OrgPlan.ALGENTA_SERVER
    )
    dep = f"prod-{uuid4().hex[:8]}"
    # activate the deployment with the whole pool (4 units for the default server tier)
    r = await _activate(client, owner_key, dep, 4)
    assert r.status_code == 200, r.text
    h = {"X-API-Key": owner_key}

    # node-a takes 3 units
    ra = await client.post("/v1/deployment/node/heartbeat", headers=h,
                           json={"deployment_id": dep, "node_thumbprint": "node-a", "units": 3})
    assert ra.status_code == 200, ra.text
    assert ra.json()["used_units"] == 3 and ra.json()["pool_units"] == 4

    # node-b asking 2 more → 5 > 4 → refused (peer not evicted)
    rb = await client.post("/v1/deployment/node/heartbeat", headers=h,
                           json={"deployment_id": dep, "node_thumbprint": "node-b", "units": 2})
    assert rb.status_code == 409, rb.text
    assert "pool_exhausted" in rb.text

    # node-b asking 1 → fits
    rb2 = await client.post("/v1/deployment/node/heartbeat", headers=h,
                            json={"deployment_id": dep, "node_thumbprint": "node-b", "units": 1})
    assert rb2.status_code == 200, rb2.text
    assert rb2.json()["used_units"] == 4


@pytest.mark.anyio
async def test_node_heartbeat_is_idempotent(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="L3 Owner 2", expires_at=None, plan=OrgPlan.ALGENTA_SERVER
    )
    dep = f"prod-{uuid4().hex[:8]}"
    assert (await _activate(client, owner_key, dep, 4)).status_code == 200
    h = {"X-API-Key": owner_key}
    for _ in range(3):
        r = await client.post("/v1/deployment/node/heartbeat", headers=h,
                              json={"deployment_id": dep, "node_thumbprint": "node-a", "units": 3})
        assert r.status_code == 200, r.text
        assert r.json()["used_units"] == 3  # never accumulates to 9


@pytest.mark.anyio
async def test_pool_advisory_lock_executes_on_backend() -> None:
    # The over-admission race fix relies on pg_advisory_xact_lock; confirm it actually runs on the
    # real (Postgres) test backend inside a transaction without error.
    from apps.api_server.db.session import AsyncSessionLocal  # noqa: F405
    from apps.api_server.services.deployment_service import acquire_pool_advisory_lock

    async with AsyncSessionLocal() as s:
        await acquire_pool_advisory_lock(s, "algenta_deployment_node", "some-key")
        await acquire_pool_advisory_lock(s, "algenta_org_deployment_alloc", "org-key")
        await s.rollback()  # releases the xact locks


@pytest.mark.anyio
async def test_node_heartbeat_unactivated_deployment_404(client, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_LICENSE_SIGNING_PRIVATE_KEY", _signing_key())
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="L3 Owner 3", expires_at=None, plan=OrgPlan.ALGENTA_SERVER
    )
    r = await client.post(
        "/v1/deployment/node/heartbeat",
        headers={"X-API-Key": owner_key},
        json={"deployment_id": f"never-{uuid4().hex[:8]}", "node_thumbprint": "n", "units": 1},
    )
    assert r.status_code == 404
    assert "deployment_not_active" in r.text
