from __future__ import annotations

from unittest.mock import AsyncMock

from apps.api_server.db.session import get_db
from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import execution_policy as execution_policy_router
from tests._asgi_client import SyncASGIClient

PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]


async def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_policy_router",
        "key_id": "key_policy_router",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


def test_execution_policy_routes_persist_and_list_snapshots(monkeypatch, tmp_path) -> None:
    db = AsyncMock()

    async def _fake_db():
        yield db

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    audit_writer = AsyncMock()
    monkeypatch.setattr(execution_policy_router, "write_audit_event", audit_writer)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    app.dependency_overrides[get_db] = _fake_db
    try:
        with SyncASGIClient(app) as client:
            current = client.get("/v1/execution/policy")
            assert current.status_code == 200, current.text
            current_payload = current.json()
            assert current_payload["revision"] == 1
            assert current_payload["snapshot_id"].startswith("execution-policy-v1-r1:")

            updated = client.request(
                "PATCH",
                "/v1/execution/policy",
                json={"min_confidence": 0.84, "allow_reexecution": True},
            )
            assert updated.status_code == 200, updated.text
            updated_payload = updated.json()
            assert updated_payload["revision"] == 2
            assert updated_payload["previous_snapshot_id"] == current_payload["snapshot_id"]

            snapshots = client.get("/v1/execution/policy/snapshots")
            assert snapshots.status_code == 200, snapshots.text
            snapshot_payload = snapshots.json()
            assert snapshot_payload["total_snapshots"] == 2
            assert snapshot_payload["data"][-1]["snapshot_id"] == updated_payload["snapshot_id"]
            assert snapshot_payload["data"][-1]["content_hash"]
            audit_writer.assert_awaited_once()
            metadata = audit_writer.await_args.kwargs["metadata"]
            assert metadata["policy_snapshot_id"] == updated_payload["snapshot_id"]
            assert metadata["changes"] == {"min_confidence": 0.84, "allow_reexecution": True}
    finally:
        app.dependency_overrides.clear()


def test_execution_policy_routes_require_auth_and_publish_openapi_security() -> None:
    async def _fake_db():
        yield object()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            unauthorized = client.get("/v1/execution/policy")
            assert unauthorized.status_code == 401
            openapi = client.get("/openapi.json")
    finally:
        app.dependency_overrides.clear()

    assert openapi.status_code == 200
    payload = openapi.json()
    assert payload["paths"]["/v1/execution/policy"]["get"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        payload["paths"]["/v1/execution/policy"]["patch"]["security"] == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        payload["paths"]["/v1/execution/policy/snapshots"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
