from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.models import (
    APIKey,
    APIKeyStatus,
    Organization,
    OrgPlan,
    OrgStatus,
    User,
    UserRole,
    UserStatus,
)
from apps.api_server.models.device import DeviceRegistration
from apps.api_server.services.auth_service import hash_api_key


class _RedisStub:
    async def hgetall(self, *_args, **_kwargs) -> dict[bytes, bytes]:
        return {}

    async def delete(self, *_args, **_kwargs) -> int:
        return 0

    async def hset(self, *_args, **_kwargs) -> int:
        return 1

    async def expire(self, *_args, **_kwargs) -> bool:
        return True


class _SyntheticValidationPayload(BaseModel):
    count: int


async def _seed_api_key(
    *,
    label: str,
    expires_at: datetime | None,
    plan: OrgPlan = OrgPlan.PRO,
) -> tuple[str, str]:
    raw_key = f"de_live_{uuid4().hex}{uuid4().hex[:8]}"
    slug = f"pytest-api-key-{uuid4().hex[:12]}"
    email = f"{slug}@example.com"

    async with AsyncSessionLocal() as session:
        org = Organization(
            name=f"Pytest {label}",
            slug=slug,
            plan=plan,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.flush()

        user = User(
            org_id=org.id,
            email=email,
            password_hash="pytest-api-key-contract",
            name=f"Pytest {label}",
            role=UserRole.OWNER,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        session.add(user)
        await session.flush()

        api_key = APIKey(
            org_id=org.id,
            user_id=user.id,
            label=label,
            key_prefix=raw_key[:12],
            hashed_key=hash_api_key(raw_key),
            status=APIKeyStatus.ACTIVE,
            expires_at=expires_at,
        )
        session.add(api_key)
        await session.commit()
        return raw_key, str(api_key.id)


async def _device_registration_snapshot(
    *,
    api_key_id: str,
    device_id: str,
) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DeviceRegistration).where(
                DeviceRegistration.api_key_id == UUID(api_key_id),
                DeviceRegistration.device_id == device_id,
            )
        )
        row = result.scalar_one()
        return {
            "id": str(row.id),
            "heartbeat_count": row.heartbeat_count,
            "last_heartbeat_at": row.last_heartbeat_at,
            "status": getattr(row.status, "value", row.status),
        }


def _hosted_device_headers(
    raw_key: str,
    device_id: str,
    *,
    platform: str = "linux",
    platform_version: str = "6.8",
    hostname_hash: str = "deadbeef" * 8,
    sdk_version: str = "algenta-test/1.0.0",
    binding_token: str = "",
) -> dict[str, str]:
    headers = {
        "X-API-Key": raw_key,
        "X-Algenta-Device-Id": device_id,
        "X-Algenta-Platform": platform,
        "X-Algenta-Platform-Version": platform_version,
        "X-Algenta-Hostname-Hash": hostname_hash,
        "X-Algenta-SDK-Version": sdk_version,
    }
    if binding_token:
        headers["X-Algenta-Device-Binding-Token"] = binding_token
    return headers


@contextmanager
def _temporary_route(app, path: str, endpoint, *, methods: list[str]):
    app.router.add_api_route(path, endpoint, methods=methods)
    app.openapi_schema = None
    try:
        yield
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "endpoint", None) is not endpoint
        ]
        app.openapi_schema = None


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
async def test_capped_hosted_api_bootstraps_and_requires_binding_token(client, app) -> None:
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
            headers=_hosted_device_headers(runtime_key, "hosted-binding-route-0001"),
        )
        second_without_token = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(runtime_key, "hosted-binding-route-0001"),
        )
        token = first_response.headers.get("X-Algenta-Device-Binding-Token", "")
        second_with_token = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(
                runtime_key,
                "hosted-binding-route-0001",
                binding_token=token,
            ),
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 200
    assert token

    assert second_without_token.status_code == 401
    error = (
        second_without_token.json().get("error") or second_without_token.json()["detail"]["error"]
    )
    assert error["code"] == "device_binding_token_required"
    assert error["required_header"] == "X-Algenta-Device-Binding-Token"

    assert second_with_token.status_code == 200


@pytest.mark.anyio
async def test_capped_hosted_api_rejects_invalid_binding_token(client, app) -> None:
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
            headers=_hosted_device_headers(runtime_key, "hosted-binding-route-0002"),
        )
        assert first_response.status_code == 200
        bad_token_response = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(
                runtime_key,
                "hosted-binding-route-0002",
                binding_token="not-the-right-binding-token-000001",
            ),
        )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert bad_token_response.status_code == 403
    error = bad_token_response.json().get("error") or bad_token_response.json()["detail"]["error"]
    assert error["code"] == "invalid_device_binding_token"
    assert error["required_header"] == "X-Algenta-Device-Binding-Token"


@pytest.mark.anyio
async def test_capped_hosted_api_http_exception_persists_binding_and_replays_header(
    client,
    app,
) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    async def _synthetic_http_exception_route(
        _auth=Depends(get_current_org),
    ) -> dict[str, object]:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "synthetic_route_failure",
                    "message": "Synthetic failure after auth.",
                }
            },
        )

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )
    path = "/__test/hosted-bind-http-exception"

    try:
        with _temporary_route(app, path, _synthetic_http_exception_route, methods=["GET"]):
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
                path,
                headers=_hosted_device_headers(runtime_key, "hosted-http-error-route-0001"),
            )
            token = first_response.headers.get("X-Algenta-Device-Binding-Token", "")
            snapshot = await _device_registration_snapshot(
                api_key_id=created["id"],
                device_id="hosted-http-error-route-0001",
            )
            second_without_token = await client.get(
                path,
                headers=_hosted_device_headers(runtime_key, "hosted-http-error-route-0001"),
            )
            second_with_token = await client.get(
                path,
                headers=_hosted_device_headers(
                    runtime_key,
                    "hosted-http-error-route-0001",
                    binding_token=token,
                ),
            )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 409
    assert token
    assert snapshot["heartbeat_count"] == 1

    first_error = first_response.json().get("error") or first_response.json()["detail"]["error"]
    assert first_error["code"] == "synthetic_route_failure"

    assert second_without_token.status_code == 401
    second_error = (
        second_without_token.json().get("error") or second_without_token.json()["detail"]["error"]
    )
    assert second_error["code"] == "device_binding_token_required"

    assert second_with_token.status_code == 409
    replayed_error = (
        second_with_token.json().get("error") or second_with_token.json()["detail"]["error"]
    )
    assert replayed_error["code"] == "synthetic_route_failure"


@pytest.mark.anyio
async def test_capped_hosted_api_validation_error_persists_binding_and_replays_header(
    client,
    app,
) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    async def _synthetic_validation_route(
        payload: _SyntheticValidationPayload,
        _auth=Depends(get_current_org),
    ) -> dict[str, object]:
        return {"count": payload.count}

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )
    path = "/__test/hosted-bind-validation-error"

    try:
        with _temporary_route(app, path, _synthetic_validation_route, methods=["POST"]):
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

            first_response = await client.post(
                path,
                headers=_hosted_device_headers(runtime_key, "hosted-validation-route-0001"),
                json={"count": "bad"},
            )
            token = first_response.headers.get("X-Algenta-Device-Binding-Token", "")
            snapshot = await _device_registration_snapshot(
                api_key_id=created["id"],
                device_id="hosted-validation-route-0001",
            )
            second_with_token = await client.post(
                path,
                headers=_hosted_device_headers(
                    runtime_key,
                    "hosted-validation-route-0001",
                    binding_token=token,
                ),
                json={"count": "bad"},
            )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 422
    assert token
    assert snapshot["heartbeat_count"] == 1
    first_error = first_response.json().get("error") or first_response.json()["detail"]["error"]
    assert first_error["code"] == "validation_error"

    assert second_with_token.status_code == 422
    second_error = (
        second_with_token.json().get("error") or second_with_token.json()["detail"]["error"]
    )
    assert second_error["code"] == "validation_error"


@pytest.mark.anyio
async def test_capped_hosted_api_generic_error_persists_binding_and_replays_header(
    client,
    app,
) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    async def _synthetic_generic_error_route(
        _auth=Depends(get_current_org),
    ) -> dict[str, object]:
        raise RuntimeError("synthetic crash after auth")

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )
    path = "/__test/hosted-bind-generic-error"

    try:
        with _temporary_route(app, path, _synthetic_generic_error_route, methods=["GET"]):
            async with AsyncClient(
                transport=ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://testserver",
            ) as non_raising_client:
                create_response = await non_raising_client.post(
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

                first_response = await non_raising_client.get(
                    path,
                    headers=_hosted_device_headers(runtime_key, "hosted-generic-route-0001"),
                )
                token = first_response.headers.get("X-Algenta-Device-Binding-Token", "")
                snapshot = await _device_registration_snapshot(
                    api_key_id=created["id"],
                    device_id="hosted-generic-route-0001",
                )
                second_without_token = await non_raising_client.get(
                    path,
                    headers=_hosted_device_headers(runtime_key, "hosted-generic-route-0001"),
                )
                second_with_token = await non_raising_client.get(
                    path,
                    headers=_hosted_device_headers(
                        runtime_key,
                        "hosted-generic-route-0001",
                        binding_token=token,
                    ),
                )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 500
    assert token
    assert snapshot["heartbeat_count"] == 1
    first_error = first_response.json().get("error") or first_response.json()["detail"]["error"]
    assert first_error["code"] == "internal_error"

    assert second_without_token.status_code == 401
    second_error = (
        second_without_token.json().get("error") or second_without_token.json()["detail"]["error"]
    )
    assert second_error["code"] == "device_binding_token_required"

    assert second_with_token.status_code == 500
    replayed_error = (
        second_with_token.json().get("error") or second_with_token.json()["detail"]["error"]
    )
    assert replayed_error["code"] == "internal_error"


@pytest.mark.anyio
async def test_capped_hosted_api_success_with_explicit_response_replays_binding_header(
    client,
    app,
) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    async def _synthetic_explicit_response_route(
        _auth=Depends(get_current_org),
    ) -> JSONResponse:
        return JSONResponse({"ok": True, "surface": "explicit_response"})

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )
    path = "/__test/hosted-bind-explicit-response"

    try:
        with _temporary_route(app, path, _synthetic_explicit_response_route, methods=["GET"]):
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
                path,
                headers=_hosted_device_headers(runtime_key, "hosted-explicit-response-0001"),
            )
            token = first_response.headers.get("X-Algenta-Device-Binding-Token", "")
            snapshot = await _device_registration_snapshot(
                api_key_id=created["id"],
                device_id="hosted-explicit-response-0001",
            )
            second_without_token = await client.get(
                path,
                headers=_hosted_device_headers(runtime_key, "hosted-explicit-response-0001"),
            )
            second_with_token = await client.get(
                path,
                headers=_hosted_device_headers(
                    runtime_key,
                    "hosted-explicit-response-0001",
                    binding_token=token,
                ),
            )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 200
    assert first_response.json() == {"ok": True, "surface": "explicit_response"}
    assert token
    assert snapshot["heartbeat_count"] == 1

    assert second_without_token.status_code == 401
    second_error = (
        second_without_token.json().get("error") or second_without_token.json()["detail"]["error"]
    )
    assert second_error["code"] == "device_binding_token_required"

    assert second_with_token.status_code == 200
    assert second_with_token.json() == {"ok": True, "surface": "explicit_response"}


@pytest.mark.anyio
async def test_capped_hosted_api_success_with_streaming_response_replays_binding_header(
    client,
    app,
) -> None:
    redis_stub = _RedisStub()

    async def _fake_redis() -> _RedisStub:
        return redis_stub

    async def _synthetic_streaming_response_route(
        _auth=Depends(get_current_org),
    ) -> StreamingResponse:
        return StreamingResponse(iter((b"stream-ok",)), media_type="text/plain")

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _key_id = await _seed_api_key(
        label="Enterprise Owner Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ENTERPRISE,
    )
    path = "/__test/hosted-bind-streaming-response"

    try:
        with _temporary_route(app, path, _synthetic_streaming_response_route, methods=["GET"]):
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
                path,
                headers=_hosted_device_headers(runtime_key, "hosted-streaming-response-0001"),
            )
            token = first_response.headers.get("X-Algenta-Device-Binding-Token", "")
            snapshot = await _device_registration_snapshot(
                api_key_id=created["id"],
                device_id="hosted-streaming-response-0001",
            )
            second_without_token = await client.get(
                path,
                headers=_hosted_device_headers(runtime_key, "hosted-streaming-response-0001"),
            )
            second_with_token = await client.get(
                path,
                headers=_hosted_device_headers(
                    runtime_key,
                    "hosted-streaming-response-0001",
                    binding_token=token,
                ),
            )
    finally:
        app.dependency_overrides.pop(get_redis, None)

    assert first_response.status_code == 200
    assert first_response.text == "stream-ok"
    assert token
    assert snapshot["heartbeat_count"] == 1

    assert second_without_token.status_code == 401
    second_error = (
        second_without_token.json().get("error") or second_without_token.json()["detail"]["error"]
    )
    assert second_error["code"] == "device_binding_token_required"

    assert second_with_token.status_code == 200
    assert second_with_token.text == "stream-ok"


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
