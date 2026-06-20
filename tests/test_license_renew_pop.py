"""Renewal proof-of-possession (P3b-C1) — /v1/license/challenge + /v1/license/renew.

End-to-end through the live router with real Ed25519 crypto: register a device bound to a
keypair, get a single-use nonce, sign it, renew → fresh license. Plus the adversarial cases
the design flagged: nonce replay, thumbprint mismatch, bad signature, missing challenge,
unbound legacy device, unregistered device.
"""

from __future__ import annotations

import base64

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from apps.runtime.device_keypair import thumbprint_for_public_pem
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403

_DEVICE = "renew-device-identity-0001"


def _keypair() -> tuple[Ed25519PrivateKey, str]:
    priv = Ed25519PrivateKey.generate()
    pub_pem = (
        priv.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv, pub_pem


async def _runtime_key(client) -> str:
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Renew Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    create = await client.post(
        "/v1/api-keys",
        headers={"X-API-Key": owner_key},
        json={"label": "Runtime", "expires_at": "2028-05-19T00:00:00Z", "device_limit": 3},
    )
    assert create.status_code == 201
    return create.json()["raw_key"]


async def _register(client, key: str, thumb: str, device_id: str = _DEVICE) -> None:
    resp = await client.post(
        "/v1/device/register",
        headers={"X-API-Key": key},
        json={
            "device": {
                "device_id": device_id,
                "platform": "linux",
                "platform_version": "6.8",
                "hostname_hash": "deadbeef" * 8,
                "sdk_version": "algenta/1.0.0",
                "device_pubkey_thumbprint": thumb,
            }
        },
    )
    assert resp.status_code == 200, resp.text


def _with_redis(app):
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405


@pytest.mark.anyio
async def test_renew_happy_path(client, app) -> None:
    _with_redis(app)
    try:
        key = await _runtime_key(client)
        priv, pub_pem = _keypair()
        await _register(client, key, thumbprint_for_public_pem(pub_pem))

        ch = await client.post(
            "/v1/license/challenge", headers={"X-API-Key": key}, json={"device_id": _DEVICE}
        )
        assert ch.status_code == 200, ch.text
        nonce_b64 = ch.json()["nonce"]
        sig = priv.sign(base64.b64decode(nonce_b64))

        rn = await client.post(
            "/v1/license/renew",
            headers={"X-API-Key": key},
            json={
                "device_id": _DEVICE,
                "public_key_pem": pub_pem,
                "signature": base64.b64encode(sig).decode(),
            },
        )
        assert rn.status_code == 200, rn.text
        token = rn.json()["license_token"]
        claims = jwt.decode(token, options={"verify_signature": False})
        assert claims["device_id"] == _DEVICE
        assert claims["activation_id"]  # carries the identity claims (A1)
        assert claims["device_pubkey_thumbprint"] == thumbprint_for_public_pem(pub_pem)
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_renew_nonce_is_single_use(client, app) -> None:
    _with_redis(app)
    try:
        key = await _runtime_key(client)
        priv, pub_pem = _keypair()
        await _register(client, key, thumbprint_for_public_pem(pub_pem))
        ch = await client.post(
            "/v1/license/challenge", headers={"X-API-Key": key}, json={"device_id": _DEVICE}
        )
        sig = base64.b64encode(priv.sign(base64.b64decode(ch.json()["nonce"]))).decode()
        body = {"device_id": _DEVICE, "public_key_pem": pub_pem, "signature": sig}
        first = await client.post("/v1/license/renew", headers={"X-API-Key": key}, json=body)
        replay = await client.post("/v1/license/renew", headers={"X-API-Key": key}, json=body)
        assert first.status_code == 200
        assert replay.status_code == 409  # nonce consumed → challenge_required
        assert replay.json()["error"]["code"] == "challenge_required"
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_renew_rejects_mismatched_key(client, app) -> None:
    _with_redis(app)
    try:
        key = await _runtime_key(client)
        priv, pub_pem = _keypair()
        await _register(client, key, thumbprint_for_public_pem(pub_pem))
        ch = await client.post(
            "/v1/license/challenge", headers={"X-API-Key": key}, json={"device_id": _DEVICE}
        )
        # A DIFFERENT keypair signs the nonce + presents its own (non-matching) pem.
        other_priv, other_pem = _keypair()
        sig = base64.b64encode(other_priv.sign(base64.b64decode(ch.json()["nonce"]))).decode()
        rn = await client.post(
            "/v1/license/renew",
            headers={"X-API-Key": key},
            json={"device_id": _DEVICE, "public_key_pem": other_pem, "signature": sig},
        )
        assert rn.status_code == 409
        assert rn.json()["error"]["code"] == "device_key_mismatch"
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_renew_rejects_bad_signature(client, app) -> None:
    _with_redis(app)
    try:
        key = await _runtime_key(client)
        priv, pub_pem = _keypair()
        await _register(client, key, thumbprint_for_public_pem(pub_pem))
        ch = await client.post(
            "/v1/license/challenge", headers={"X-API-Key": key}, json={"device_id": _DEVICE}
        )
        assert ch.status_code == 200
        # Correct (matching) pem, but a signature over the WRONG bytes.
        bad_sig = base64.b64encode(priv.sign(b"not-the-nonce")).decode()
        rn = await client.post(
            "/v1/license/renew",
            headers={"X-API-Key": key},
            json={"device_id": _DEVICE, "public_key_pem": pub_pem, "signature": bad_sig},
        )
        assert rn.status_code == 401
        assert rn.json()["error"]["code"] == "proof_of_possession_failed"
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_renew_without_challenge_is_rejected(client, app) -> None:
    _with_redis(app)
    try:
        key = await _runtime_key(client)
        priv, pub_pem = _keypair()
        await _register(client, key, thumbprint_for_public_pem(pub_pem))
        # No challenge issued → no nonce.
        sig = base64.b64encode(priv.sign(b"x" * 32)).decode()
        rn = await client.post(
            "/v1/license/renew",
            headers={"X-API-Key": key},
            json={"device_id": _DEVICE, "public_key_pem": pub_pem, "signature": sig},
        )
        assert rn.status_code == 409
        assert rn.json()["error"]["code"] == "challenge_required"
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_challenge_rejects_unbound_legacy_device(client, app) -> None:
    _with_redis(app)
    try:
        key = await _runtime_key(client)
        await _register(client, key, "")  # legacy: registered with NO thumbprint
        ch = await client.post(
            "/v1/license/challenge", headers={"X-API-Key": key}, json={"device_id": _DEVICE}
        )
        assert ch.status_code == 409
        assert ch.json()["error"]["code"] == "device_not_bound"
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_challenge_rejects_unregistered_device(client, app) -> None:
    _with_redis(app)
    try:
        key = await _runtime_key(client)
        ch = await client.post(
            "/v1/license/challenge",
            headers={"X-API-Key": key},
            json={"device_id": "never-registered-device-x"},
        )
        assert ch.status_code == 404
        assert ch.json()["error"]["code"] == "device_not_registered"
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_challenge_and_renew_reject_revoked_device(client, app) -> None:
    """A revoked device cannot renew (covers the REVOKED path + TOCTOU guard)."""
    _with_redis(app)
    try:
        key = await _runtime_key(client)
        priv, pub_pem = _keypair()
        await _register(client, key, thumbprint_for_public_pem(pub_pem))
        # Revoke the device directly in the (shared test) DB.
        from sqlalchemy import update as _sa_update

        from apps.api_server.db.session import AsyncSessionLocal
        from apps.api_server.models.device import DeviceRegistration, DeviceStatus

        async with AsyncSessionLocal() as s:
            await s.execute(
                _sa_update(DeviceRegistration)
                .where(DeviceRegistration.device_id == _DEVICE)
                .values(status=DeviceStatus.REVOKED)
            )
            await s.commit()

        ch = await client.post(
            "/v1/license/challenge", headers={"X-API-Key": key}, json={"device_id": _DEVICE}
        )
        assert ch.status_code == 403
        assert ch.json()["error"]["code"] == "device_revoked"
        rn = await client.post(
            "/v1/license/renew",
            headers={"X-API-Key": key},
            json={
                "device_id": _DEVICE,
                "public_key_pem": pub_pem,
                "signature": base64.b64encode(priv.sign(b"x" * 32)).decode(),
            },
        )
        assert rn.status_code == 403
        assert rn.json()["error"]["code"] == "device_revoked"
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


class _FakeRedis:
    """Minimal async Redis with ATOMIC getdel — exercises the production nonce path."""

    def __init__(self) -> None:
        self._kv: dict[str, object] = {}

    async def set(self, k, v, ex=None) -> None:
        self._kv[k] = v

    async def get(self, k):
        return self._kv.get(k)

    async def getdel(self, k):
        return self._kv.pop(k, None)

    async def delete(self, k) -> int:
        return 1 if self._kv.pop(k, None) is not None else 0

    async def incr(self, k) -> int:
        self._kv[k] = int(self._kv.get(k, 0)) + 1
        return self._kv[k]

    async def expire(self, k, t) -> bool:
        return True


@pytest.mark.anyio
async def test_renew_single_use_via_redis_path(client, app) -> None:
    """The Redis-backed nonce path (atomic getdel) is single-use — replay → 409."""
    _with_redis(app)
    prev = getattr(app.state, "redis", None)
    app.state.redis = _FakeRedis()  # drive the router's request.app.state.redis path
    try:
        key = await _runtime_key(client)
        priv, pub_pem = _keypair()
        await _register(client, key, thumbprint_for_public_pem(pub_pem))
        ch = await client.post(
            "/v1/license/challenge", headers={"X-API-Key": key}, json={"device_id": _DEVICE}
        )
        assert ch.status_code == 200
        sig = base64.b64encode(priv.sign(base64.b64decode(ch.json()["nonce"]))).decode()
        body = {"device_id": _DEVICE, "public_key_pem": pub_pem, "signature": sig}
        first = await client.post("/v1/license/renew", headers={"X-API-Key": key}, json=body)
        replay = await client.post("/v1/license/renew", headers={"X-API-Key": key}, json=body)
        assert first.status_code == 200, first.text
        assert replay.status_code == 409  # nonce consumed atomically via getdel
        assert replay.json()["error"]["code"] == "challenge_required"
    finally:
        app.state.redis = prev
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405
