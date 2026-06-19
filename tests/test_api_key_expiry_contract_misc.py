"""Tests for test_api_key_expiry_contract: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-1/tests/test_api_key_expiry_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_expired_api_key_is_rejected_by_route(client, app) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    expired_key, _key_id = await _seed_api_key(
        label="Expired Route Key",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    try:
        response = await client.get("/v1/me", headers={"X-API-Key": expired_key})
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 401
    body = response.json()
    error = body.get("error") or body["detail"]["error"]
    assert error["code"] == "invalid_api_key"
    assert "expired" in error["message"].lower()


@pytest.mark.anyio
async def test_revoked_api_key_is_rejected_immediately_after_cache_warm(client, app) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Owner Route Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )

    try:
        create_response = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={
                "label": "Revoked Route Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 2,
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        raw_key = created["raw_key"]

        warm_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(raw_key, "revoked-route-device-0001"),
        )
        assert warm_response.status_code == 200

        revoke_response = await client.delete(
            f"/v1/api-keys/{created['id']}",
            headers={"X-API-Key": owner_key},
        )
        assert revoke_response.status_code == 204

        rejected_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(raw_key, "revoked-route-device-0001"),
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert rejected_response.status_code == 401
    body = rejected_response.json()
    error = body.get("error") or body["detail"]["error"]
    assert error["code"] == "invalid_api_key"


@pytest.mark.anyio
async def test_inherited_plan_key_does_not_require_device_header_for_hosted_api(
    client, app
) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Pro Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.PRO,
    )

    try:
        response = await client.get("/v1/me", headers={"X-API-Key": owner_key})
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert response.status_code == 200


@pytest.mark.anyio
async def test_hosted_device_reuse_refreshes_activity_without_consuming_extra_slot(
    client, app
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

    device_one = "hosted-device-reuse-0001"
    device_two = "hosted-device-reuse-0002"
    device_three = "hosted-device-reuse-0003"

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
            headers=_hosted_device_headers(runtime_key, device_one),
        )
        binding_token = first_response.headers["X-Algenta-Device-Binding-Token"]
        first_snapshot = await _device_registration_snapshot(
            api_key_id=created["id"],
            device_id=device_one,
        )

        second_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(
                runtime_key,
                device_one,
                binding_token=binding_token,
            ),
        )
        second_snapshot = await _device_registration_snapshot(
            api_key_id=created["id"],
            device_id=device_one,
        )

        third_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(runtime_key, device_two),
        )
        fourth_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(runtime_key, device_three),
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert third_response.status_code == 200
    assert fourth_response.status_code == 402

    assert first_snapshot["heartbeat_count"] == 1
    assert second_snapshot["heartbeat_count"] == 2
    assert second_snapshot["last_heartbeat_at"] >= first_snapshot["last_heartbeat_at"]

    fourth_body = fourth_response.json()
    error = fourth_body.get("error")
    if error is None:
        detail = fourth_body.get("detail", fourth_body)
        error = detail.get("error", detail)
    assert error["code"] == "device_limit_reached"
    assert error["device_limit"] == 2
    assert error["device_count"] == 2


@pytest.mark.anyio
async def test_revoked_device_cannot_reactivate_on_hosted_api_or_device_register(
    client, app
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

    device_id = "hosted-device-revoked-01"

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
            headers=_hosted_device_headers(runtime_key, device_id),
        )
        assert first_response.status_code == 200

        registration = await _device_registration_snapshot(
            api_key_id=created["id"],
            device_id=device_id,
        )

        revoke_response = await client.delete(
            f"/v1/device/{registration['id']}",
            headers={"X-API-Key": owner_key},
        )
        hosted_reuse_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(runtime_key, device_id),
        )
        register_reuse_response = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json={
                "device": {
                    "device_id": device_id,
                    "platform": "linux",
                    "platform_version": "6.8",
                    "hostname_hash": "deadbeef" * 8,
                    "sdk_version": "algenta-ts-live/1.0.0",
                }
            },
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert revoke_response.status_code == 200
    assert hosted_reuse_response.status_code == 403
    assert register_reuse_response.status_code == 403

    hosted_body = hosted_reuse_response.json()
    hosted_error = hosted_body.get("error")
    if hosted_error is None:
        detail = hosted_body.get("detail", hosted_body)
        hosted_error = detail.get("error", detail)
    assert hosted_error["code"] == "device_revoked"
    assert hosted_error["device_id"] == device_id

    register_body = register_reuse_response.json()
    register_error = register_body.get("error")
    if register_error is None:
        detail = register_body.get("detail", register_body)
        register_error = detail.get("error", detail)
    assert register_error["code"] == "device_revoked"
    assert register_error["device_id"] == device_id


@pytest.mark.anyio
async def test_hosted_device_binding_rejects_reused_device_id_with_mismatched_hostname_hash(
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

        first_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(
                runtime_key,
                "hosted-device-identity-0001",
                hostname_hash="deadbeef" * 8,
            ),
        )
        binding_token = first_response.headers["X-Algenta-Device-Binding-Token"]
        mismatch_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(
                runtime_key,
                "hosted-device-identity-0001",
                hostname_hash="cafebabe" * 8,
                binding_token=binding_token,
            ),
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
    assert error["device_id"] == "hosted-device-identity-0001"
    assert error["mismatched_fields"] == ["hostname_hash"]


