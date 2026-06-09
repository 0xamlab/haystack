"""Tests for test_api_key_expiry_contract: enterprise_key.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-1/tests/test_api_key_expiry_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_enterprise_key_device_limit_blocks_third_hosted_request(client, app) -> None:
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

        first_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(runtime_key, "hosted-device-000001"),
        )
        second_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(runtime_key, "hosted-device-000002"),
        )
        third_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(runtime_key, "hosted-device-000003"),
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert third_response.status_code == 402
    third_body = third_response.json()
    error = third_body.get("error")
    if error is None:
        detail = third_body.get("detail", third_body)
        error = detail.get("error", detail)
    assert error["code"] == "device_limit_reached"
    assert error["device_limit"] == 2
    assert error["device_count"] == 2


@pytest.mark.anyio
async def test_enterprise_key_device_limit_blocks_third_registration(client, app) -> None:
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
        assert created["device_limit"] == 2
        runtime_key = created["raw_key"]

        def _register_payload(device_id: str) -> dict[str, object]:
            return {
                "device": {
                    "device_id": device_id,
                    "platform": "linux",
                    "platform_version": "6.8",
                    "hostname_hash": "deadbeef" * 8,
                    "sdk_version": "algenta-ts-live/1.0.0",
                }
            }

        first_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_register_payload("device-0000000001"),
        )
        second_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_register_payload("device-0000000002"),
        )
        third_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_register_payload("device-0000000003"),
        )

        assert first_response.status_code == 200
        assert first_response.json()["device_limit"] == 2
        assert second_response.status_code == 200
        assert second_response.json()["device_count"] == 2
        assert third_response.status_code == 402
        third_body = third_response.json()
        error = third_body.get("error")
        if error is None:
            detail = third_body.get("detail", third_body)
            error = detail.get("error", detail)
        assert error["code"] == "device_limit_reached"
        assert error["device_limit"] == 2
        assert error["device_count"] == 2
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_enterprise_key_without_device_limit_remains_unlimited(client, app) -> None:
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
                "label": "Mission Enterprise Unlimited Key",
                "expires_at": "2028-05-19T00:00:00Z",
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["device_limit"] == 0
        runtime_key = created["raw_key"]

        def _register_payload(device_id: str) -> dict[str, object]:
            return {
                "device": {
                    "device_id": device_id,
                    "platform": "linux",
                    "platform_version": "6.8",
                    "hostname_hash": "deadbeef" * 8,
                    "sdk_version": "algenta-ts-live/1.0.0",
                }
            }

        first_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_register_payload("device-unlimited-0001"),
        )
        second_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_register_payload("device-unlimited-0002"),
        )
        third_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_register_payload("device-unlimited-0003"),
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert third_response.status_code == 200
        assert first_response.json()["device_limit"] == 0
        assert second_response.json()["device_limit"] == 0
        assert third_response.json()["device_limit"] == 0
        assert third_response.json()["device_count"] == 3

        list_response = await client.get(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
        )
        assert list_response.status_code == 200
        listed = list_response.json()
        entry = next(item for item in listed if item["id"] == created["id"])
        assert entry["device_limit"] == 0
    finally:
        app.dependency_overrides.pop(get_redis, None)


