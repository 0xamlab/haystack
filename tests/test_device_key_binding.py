"""Device-key binding (P3b-2) — server-side activation binding to a device keypair.

Unit-tests the binding rule and exercises the live /v1/device/register router path:
first keypair-aware register binds the device's public-key thumbprint; a later register
of the same device presenting a DIFFERENT thumbprint is rejected (clone); a legacy client
(no thumbprint) is unaffected and never re-binds.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.api_server.services.device_service import _check_device_key_binding
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403

_T1 = "ed25519:" + "A" * 43
_T2 = "ed25519:" + "B" * 43


# ── Unit: the binding rule ─────────────────────────────────────────────────────


def _row(thumb: str) -> SimpleNamespace:
    return SimpleNamespace(device_pubkey_thumbprint=thumb)


def test_binding_allows_matching_thumbprint() -> None:
    _check_device_key_binding(_row(_T1), _T1)  # no raise


def test_binding_rejects_mismatched_thumbprint() -> None:
    with pytest.raises(ValueError, match="device key"):
        _check_device_key_binding(_row(_T1), _T2)


def test_binding_allows_legacy_empty_incoming() -> None:
    # Bound device, legacy client sends nothing → allowed (does not re-bind here).
    _check_device_key_binding(_row(_T1), "")


def test_binding_allows_first_bind_when_unbound() -> None:
    _check_device_key_binding(_row(""), _T1)  # no raise — first bind


# ── Integration: the live register endpoint ────────────────────────────────────


@pytest.mark.anyio
async def test_device_register_binds_and_enforces_keypair(client, app) -> None:
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Binding Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        create = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={"label": "Runtime Key", "expires_at": "2028-05-19T00:00:00Z", "device_limit": 3},
        )
        assert create.status_code == 201
        runtime_key = create.json()["raw_key"]

        def _payload(thumb: str) -> dict[str, object]:
            return {
                "device": {
                    "device_id": "runtime-device-identity-0001",
                    "platform": "linux",
                    "platform_version": "6.8",
                    "hostname_hash": "deadbeef" * 8,
                    "sdk_version": "algenta-live/1.0.0",
                    "device_pubkey_thumbprint": thumb,
                }
            }

        # First register binds T1 and echoes it back.
        first = await client.post(
            "/v1/device/register", headers={"X-API-Key": runtime_key}, json=_payload(_T1)
        )
        assert first.status_code == 200
        assert first.json()["device_pubkey_thumbprint"] == _T1

        # Re-register with the SAME key → ok.
        same = await client.post(
            "/v1/device/register", headers={"X-API-Key": runtime_key}, json=_payload(_T1)
        )
        assert same.status_code == 200

        # Re-register with a DIFFERENT key (same fingerprint) → rejected as a clone.
        clone = await client.post(
            "/v1/device/register", headers={"X-API-Key": runtime_key}, json=_payload(_T2)
        )
        assert clone.status_code == 409
        body = clone.json()
        error = body.get("error") or body.get("detail", {}).get("error", body.get("detail", {}))
        assert error.get("code") == "device_key_mismatch"

        # Legacy client (no thumbprint) re-registering the bound device → still ok.
        legacy = await client.post(
            "/v1/device/register", headers={"X-API-Key": runtime_key}, json=_payload("")
        )
        assert legacy.status_code == 200
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_device_register_legacy_no_thumbprint_unbound(client, app) -> None:
    """A device that never sends a thumbprint stays unbound and re-registers freely."""
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Legacy Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        create = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={"label": "Legacy Key", "expires_at": "2028-05-19T00:00:00Z", "device_limit": 2},
        )
        runtime_key = create.json()["raw_key"]
        payload = {
            "device": {
                "device_id": "legacy-device-identity-0002",
                "platform": "linux",
                "platform_version": "6.8",
                "hostname_hash": "cafebabe" * 8,
                "sdk_version": "algenta-live/1.0.0",
            }
        }
        r1 = await client.post(
            "/v1/device/register", headers={"X-API-Key": runtime_key}, json=payload
        )
        r2 = await client.post(
            "/v1/device/register", headers={"X-API-Key": runtime_key}, json=payload
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["device_pubkey_thumbprint"] == ""
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405
