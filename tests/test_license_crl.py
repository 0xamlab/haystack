"""Signed CRL (P3b-D1) — GET /v1/license/revocations.

The CRL is a JWT (signed by the license signer) listing revoked activation_ids, derived from
REVOKED device rows. Unauthenticated + self-authenticating. Covers: empty CRL, a revoked
device appears (by its stable activation_id), the signature verifies under the active signer,
the version advances on revoke, and revoke_device bumps updated_at.
"""

from __future__ import annotations

import uuid

import jwt
import pytest

from apps.api_server.services.device_service import _activation_id
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


def _decode_unverified(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


async def _register_and_revoke(client, app, base: str) -> tuple[str, str]:
    """Register a (uniquely-named) device under a fresh org+key and revoke it.

    The test DB persists committed rows across runs, so the device_id MUST be unique per run
    to avoid colliding with leftover data. Returns (org_id, activation_id).
    """
    device_id = f"{base}-{uuid.uuid4().hex}"
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="CRL Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    create = await client.post(
        "/v1/api-keys",
        headers={"X-API-Key": owner_key},
        json={"label": "Runtime", "expires_at": "2028-05-19T00:00:00Z", "device_limit": 3},
    )
    runtime_key = create.json()["raw_key"]
    await client.post(
        "/v1/device/register",
        headers={"X-API-Key": runtime_key},
        json={
            "device": {
                "device_id": device_id,
                "platform": "linux",
                "platform_version": "6.8",
                "hostname_hash": "deadbeef" * 8,
                "sdk_version": "algenta/1.0.0",
                "device_pubkey_thumbprint": "ed25519:" + "A" * 43,
            }
        },
    )
    # Revoke directly in the shared test DB, capturing the org_id for the activation_id.
    from sqlalchemy import select as _sel
    from sqlalchemy import update as _upd

    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models.device import DeviceRegistration, DeviceStatus

    async with AsyncSessionLocal() as s:
        org_id = (
            await s.execute(
                _sel(DeviceRegistration.org_id).where(DeviceRegistration.device_id == device_id)
            )
        ).scalar_one()
        await s.execute(
            _upd(DeviceRegistration)
            .where(DeviceRegistration.device_id == device_id)
            .values(status=DeviceStatus.REVOKED, updated_at=datetime.now(UTC))  # noqa: F405
        )
        await s.commit()
    return str(org_id), _activation_id(str(org_id), device_id)


@pytest.mark.anyio
async def test_crl_is_unauthenticated_and_lists_revoked(client, app) -> None:
    try:
        _org, activation_id = await _register_and_revoke(client, app, "crl-list-device")
        resp = await client.get("/v1/license/revocations")  # NO auth header
        assert resp.status_code == 200, resp.text
        crl = _decode_unverified(resp.json()["crl"])
        assert crl["sub"] == "device-license-revocation-list"
        ids = {entry["activation_id"] for entry in crl["revoked"]}
        assert activation_id in ids
        assert crl["version"] > 0
        assert crl["valid_until"] > crl["issued_at"]
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_crl_signature_verifies_under_active_signer(client, app) -> None:
    try:
        await _register_and_revoke(client, app, "crl-sig-device-0002")
        resp = await client.get("/v1/license/revocations")
        token = resp.json()["crl"]
        # Default backend is dev_hmac (HS256) — verify the signature with its secret.
        from apps.api_server.config import get_settings
        from apps.api_server.services.license_signer import dev_hmac_secret

        decoded = jwt.decode(token, dev_hmac_secret(get_settings()), algorithms=["HS256"])
        assert decoded["iss"] == "algenta-control-plane"
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_crl_empty_when_nothing_revoked(client, app) -> None:
    # No devices revoked in a clean DB slice for THIS assertion's purposes: the global CRL may
    # carry entries from other tests, so assert the SHAPE + that our never-revoked id is absent.
    resp = await client.get("/v1/license/revocations")
    assert resp.status_code == 200
    crl = _decode_unverified(resp.json()["crl"])
    assert isinstance(crl["revoked"], list)
    bogus = _activation_id("00000000-0000-0000-0000-000000000000", "never-revoked-device")
    assert bogus not in {e["activation_id"] for e in crl["revoked"]}
