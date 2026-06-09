"""Tests for test_api_key_expiry_contract: capped_key.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-1/tests/test_api_key_expiry_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_capped_key_requires_device_header_for_hosted_api(client, app) -> None:
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

        response = await client.get("/v1/me", headers={"X-API-Key": runtime_key})
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 401
    body = response.json()
    error = body.get("error") or body["detail"]["error"]
    assert error["code"] == "device_binding_required"
    assert error["required_header"] == "X-Algenta-Device-Id"


@pytest.mark.anyio
async def test_capped_key_requires_hostname_hash_for_hosted_api(client, app) -> None:
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

        response = await client.get(
            "/v1/me",
            headers={
                "X-API-Key": runtime_key,
                "X-Algenta-Device-Id": "hosted-device-000001",
                "X-Algenta-Platform": "linux",
                "X-Algenta-Platform-Version": "6.8",
                "X-Algenta-SDK-Version": "algenta-test/1.0.0",
            },
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 401
    body = response.json()
    error = body.get("error") or body["detail"]["error"]
    assert error["code"] == "device_fingerprint_required"
    assert error["required_header"] == "X-Algenta-Hostname-Hash"


@pytest.mark.anyio
async def test_capped_key_requires_platform_for_hosted_api(client, app) -> None:
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

        response = await client.get(
            "/v1/me",
            headers={
                "X-API-Key": runtime_key,
                "X-Algenta-Device-Id": "hosted-device-000001",
                "X-Algenta-Platform": "",
                "X-Algenta-Platform-Version": "6.8",
                "X-Algenta-Hostname-Hash": "deadbeef" * 8,
                "X-Algenta-SDK-Version": "algenta-test/1.0.0",
            },
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 401
    body = response.json()
    error = body.get("error") or body["detail"]["error"]
    assert error["code"] == "device_platform_required"
    assert error["required_header"] == "X-Algenta-Platform"


