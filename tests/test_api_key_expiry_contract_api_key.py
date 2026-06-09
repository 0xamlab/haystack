"""Tests for test_api_key_expiry_contract: api_key.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-1/tests/test_api_key_expiry_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_api_key_create_and_list_round_trip_expiry(client, app) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Owner Route Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )

    try:
        create_response = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={
                "label": "Mission Two Year Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 2,
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["key_prefix"]
        assert created["raw_key"].startswith(created["key_prefix"])
        assert created["expires_at"] == "2028-05-19T00:00:00Z"
        assert created["device_limit"] == 2

        list_response = await client.get(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
        )
        assert list_response.status_code == 200
        listed = list_response.json()
        entry = next(item for item in listed if item["id"] == created["id"])
        assert entry["key_prefix"] == created["key_prefix"]
        assert entry["expires_at"] == "2028-05-19T00:00:00Z"
        assert entry["device_limit"] == 2
        assert "raw_key" not in entry

        revoke_response = await client.delete(
            f"/v1/api-keys/{created['id']}",
            headers={"X-API-Key": owner_key},
        )
        assert revoke_response.status_code == 204
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_api_key_device_limit_cannot_exceed_plan_cap(client, app) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Owner Route Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.PRO,
    )

    try:
        response = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={
                "label": "Too Wide Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 6,
            },
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 400
    body = response.json()
    error = body.get("error") or body["detail"]["error"]
    assert error["code"] == "invalid_device_limit"


@pytest.mark.anyio
async def test_api_key_zero_device_limit_is_rejected_on_finite_plan(client, app) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Owner Route Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.PRO,
    )

    try:
        response = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={
                "label": "Unlimited On Pro Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 0,
            },
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 400
    body = response.json()
    error = body.get("error") or body["detail"]["error"]
    assert error["code"] == "invalid_device_limit"
    assert "does not support unlimited devices per key" in error["message"]


