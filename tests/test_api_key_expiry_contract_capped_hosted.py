"""Tests for test_api_key_expiry_contract: capped_hosted.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-1/tests/test_api_key_expiry_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


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


