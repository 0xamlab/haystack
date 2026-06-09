"""Tests for test_api_key_expiry_contract: device_register.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-1/tests/test_api_key_expiry_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_device_register_rejects_reused_device_id_with_mismatched_hostname_hash(
    client,
    app,
) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )

    try:
        create_response = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={
                "label": "Mission Enterprise Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 2,
            },
        )
        assert create_response.status_code == 201
        runtime_key = create_response.json()["raw_key"]

        def _payload(hostname_hash: str) -> dict[str, object]:
            return {
                "device": {
                    "device_id": "runtime-device-identity-0001",
                    "platform": "linux",
                    "platform_version": "6.8",
                    "hostname_hash": hostname_hash,
                    "sdk_version": "algenta-ts-live/1.0.0",
                }
            }

        first_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_payload("deadbeef" * 8),
        )
        mismatch_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_payload("cafebabe" * 8),
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 200
    assert mismatch_response.status_code == 403
    body = mismatch_response.json()
    error = body.get("error")
    if error is None:
        detail = body.get("detail", body)
        error = detail.get("error", detail)
    assert error["code"] == "device_identity_mismatch"
    assert error["device_id"] == "runtime-device-identity-0001"
    assert error["mismatched_fields"] == ["hostname_hash"]


@pytest.mark.anyio
async def test_device_register_requires_hostname_hash_for_capped_key(client, app) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )

    try:
        create_response = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={
                "label": "Mission Enterprise Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 2,
            },
        )
        assert create_response.status_code == 201
        runtime_key = create_response.json()["raw_key"]

        response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json={
                "device": {
                    "device_id": "runtime-device-missing-hostname-0001",
                    "platform": "linux",
                    "platform_version": "6.8",
                    "hostname_hash": "",
                    "sdk_version": "algenta-ts-live/1.0.0",
                }
            },
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 400
    body = response.json()
    error = body.get("error")
    if error is None:
        detail = body.get("detail", body)
        error = detail.get("error", detail)
    assert error["code"] == "device_fingerprint_required"
    assert error["required_field"] == "hostname_hash"


@pytest.mark.anyio
async def test_device_register_requires_platform_for_capped_key(client, app) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )

    try:
        create_response = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={
                "label": "Mission Enterprise Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 2,
            },
        )
        assert create_response.status_code == 201
        runtime_key = create_response.json()["raw_key"]

        response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json={
                "device": {
                    "device_id": "runtime-device-missing-platform-0001",
                    "platform": "",
                    "platform_version": "6.8",
                    "hostname_hash": "deadbeef" * 8,
                    "sdk_version": "algenta-ts-live/1.0.0",
                }
            },
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 400
    body = response.json()
    error = body.get("error")
    if error is None:
        detail = body.get("detail", body)
        error = detail.get("error", detail)
    assert error["code"] == "device_platform_required"
    assert error["required_field"] == "platform"


@pytest.mark.anyio
async def test_device_register_rejects_overlong_runtime_metadata(client, app) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )

    try:
        create_response = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={
                "label": "Mission Enterprise Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 2,
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        runtime_key = created["raw_key"]

        response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json={
                "device": {
                    "device_id": "device-overlong-0001",
                    "platform": "linux",
                    "platform_version": "6.8",
                    "hostname_hash": "deadbeef" * 9,
                    "sdk_version": "a" * 129,
                }
            },
        )

        assert response.status_code == 422
        body_text = json.dumps(response.json())
        assert "hostname_hash" in body_text or "sdk_version" in body_text
    finally:
        app.dependency_overrides.pop(get_redis, None)


