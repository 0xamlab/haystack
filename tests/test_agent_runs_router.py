from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import HTTPException

from apps.api_server.db.session import get_db
from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import agent_runs as agent_runs_router
from tests._asgi_client import SyncASGIClient

PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]


async def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_agent_runs",
        "key_id": "key_agent_runs",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


def test_agent_run_routes_require_authentication() -> None:
    async def _deny_auth() -> dict[str, str]:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "authentication_required",
                    "message": "API key required.",
                }
            },
        )

    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_org] = _deny_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post("/v1/agent/runs", json={"task": "search docs"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_agent_run_lifecycle_routes_persist_and_transition(monkeypatch, tmp_path) -> None:
    db = AsyncMock()

    async def _fake_db():
        yield db

    async def _noop_quota_check(*, auth: object, redis_client: object, request_state: object | None = None) -> None:
        del auth, redis_client, request_state

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(agent_runs_router, "_quota_check", _noop_quota_check)
    audit_writer = AsyncMock()
    monkeypatch.setattr(agent_runs_router, "write_audit_event", audit_writer)
    monkeypatch.setattr(agent_runs_router, "get_client_ip", lambda request: "203.0.113.10")
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    app.dependency_overrides[get_db] = _fake_db
    try:
        with SyncASGIClient(app) as client:
            create = client.post(
                "/v1/agent/runs",
                json={
                    "task": "Search the latest operating procedure",
                    "tools": ["search"],
                    "approval_mode": "manual",
                },
            )
            assert create.status_code == 200, create.text
            created = create.json()
            assert created["status"] == "requires_approval"
            run_id = created["run_id"]

            listed = client.get("/v1/agent/runs?page=1&limit=25&status=requires_approval")
            assert listed.status_code == 200, listed.text
            listed_payload = listed.json()
            assert listed_payload["total"] == 1
            assert listed_payload["data"][0]["run_id"] == run_id
            assert listed_payload["data"][0]["policy_snapshot_id"] == created["policy_snapshot_id"]

            get_run = client.get(f"/v1/agent/runs/{run_id}")
            assert get_run.status_code == 200, get_run.text
            assert get_run.json()["status"] == "requires_approval"

            approve = client.post(f"/v1/agent/runs/{run_id}/approve", json={})
            assert approve.status_code == 200, approve.text
            approved = approve.json()
            assert approved["status"] == "completed"
            assert approved["tools_used"] == ["search"]

            checkpoints = client.get(f"/v1/agent/runs/{run_id}/checkpoints")
            assert checkpoints.status_code == 200, checkpoints.text
            checkpoint_payload = checkpoints.json()
            assert checkpoint_payload["total_checkpoints"] == 3
            assert checkpoint_payload["data"][-1]["status"] == "completed"

            checkpoint_query = client.get(
                "/v1/agent/runs/checkpoints"
                f"?page=1&limit=25&status=completed&request_hash={approved['request_hash']}"
                f"&policy_snapshot_id={approved['policy_snapshot_id']}"
                f"&schema_snapshot_id={approved['schema_snapshot_id']}"
                f"&run_id={run_id}&checkpoint_id={checkpoint_payload['data'][-1]['checkpoint_id']}"
            )
            assert checkpoint_query.status_code == 200, checkpoint_query.text
            checkpoint_query_payload = checkpoint_query.json()
            assert checkpoint_query_payload["total"] == 1
            assert checkpoint_query_payload["data"][0]["run_id"] == run_id
            assert checkpoint_query_payload["data"][0]["run_status"] == "completed"
            assert (
                checkpoint_query_payload["data"][0]["checkpoint_id"]
                == checkpoint_payload["data"][-1]["checkpoint_id"]
            )

            replay = client.post(f"/v1/agent/runs/{run_id}/replay", json={})
            assert replay.status_code == 200, replay.text
            assert replay.json()["replay_status"] == "matched"

            fork = client.post(
                f"/v1/agent/runs/{run_id}/fork",
                json={"checkpoint_id": checkpoint_payload["data"][0]["checkpoint_id"]},
            )
            assert fork.status_code == 200, fork.text
            assert fork.json()["status"] == "paused"
            assert fork.json()["source_run_id"] == run_id

            events = client.get(f"/v1/agent/runs/{run_id}/events")
            assert events.status_code == 200, events.text
            event_payload = events.json()
            assert event_payload["run_id"] == run_id
            assert event_payload["total_events"] == 6
            assert [item["event_type"] for item in event_payload["data"]] == [
                "run_created",
                "tool_selected",
                "approval_required",
                "run_approved",
                "tool_executed",
                "run_completed",
            ]

            mission_events = client.get(f"/v1/agent/runs/{run_id}/mission-events?limit=25")
            assert mission_events.status_code == 200, mission_events.text
            mission_payload = mission_events.json()
            assert mission_payload["run_id"] == run_id
            assert mission_payload["total_events"] == 6
            assert mission_payload["data"][0]["event_type"] == "run_created"
            assert mission_payload["data"][-1]["event_type"] == "run_completed"
            assert mission_payload["data"][0]["details_json"] == '{"approval_mode":"manual","start_paused":false}'

            telemetry = client.get(f"/v1/agent/runs/{run_id}/telemetry?limit=25")
            assert telemetry.status_code == 200, telemetry.text
            telemetry_payload = telemetry.json()
            assert telemetry_payload["run_id"] == run_id
            assert telemetry_payload["total_batches"] == 1
            assert telemetry_payload["data"][0]["telemetry_kind"] == "agent_run_completion"

            mission_query = client.get(
                "/v1/agent/runs/mission-events"
                f"?page=1&limit=25&status=completed&request_hash={approved['request_hash']}"
                f"&policy_snapshot_id={approved['policy_snapshot_id']}"
                f"&schema_snapshot_id={approved['schema_snapshot_id']}"
                f"&run_id={run_id}&event_type=run_completed"
            )
            assert mission_query.status_code == 200, mission_query.text
            mission_query_payload = mission_query.json()
            assert mission_query_payload["total"] == 1
            assert mission_query_payload["data"][0]["run_id"] == run_id
            assert mission_query_payload["data"][0]["run_status"] == "completed"

            telemetry_query = client.get(
                "/v1/agent/runs/telemetry"
                f"?page=1&limit=25&status=completed&request_hash={approved['request_hash']}"
                f"&policy_snapshot_id={approved['policy_snapshot_id']}"
                f"&schema_snapshot_id={approved['schema_snapshot_id']}"
                f"&run_id={run_id}&telemetry_kind=agent_run_completion&module_name=agent_run_service"
            )
            assert telemetry_query.status_code == 200, telemetry_query.text
            telemetry_query_payload = telemetry_query.json()
            assert telemetry_query_payload["total"] == 1
            assert telemetry_query_payload["data"][0]["run_id"] == run_id
            assert telemetry_query_payload["data"][0]["telemetry_kind"] == "agent_run_completion"

            paused = client.post(
                "/v1/agent/runs",
                json={"task": "Calculate the next-step recommendation", "start_paused": True},
            )
            assert paused.status_code == 200, paused.text
            paused_run_id = paused.json()["run_id"]

            resumed = client.post(f"/v1/agent/runs/{paused_run_id}/resume", json={})
            assert resumed.status_code == 200, resumed.text
            assert resumed.json()["status"] == "completed"

            paused_again = client.post(
                "/v1/agent/runs",
                json={"task": "Calculate the next-step recommendation", "start_paused": True},
            )
            cancellable_run_id = paused_again.json()["run_id"]
            cancelled = client.post(f"/v1/agent/runs/{cancellable_run_id}/cancel", json={})
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"

            assert audit_writer.await_count == 8
            actions = [call.kwargs["action"] for call in audit_writer.await_args_list]
            assert actions == [
                "agent_run.create",
                "agent_run.approve",
                "agent_run.replay",
                "agent_run.fork",
                "agent_run.create",
                "agent_run.resume",
                "agent_run.create",
                "agent_run.cancel",
            ]
            replay_metadata = audit_writer.await_args_list[2].kwargs["metadata"]
            assert replay_metadata["replay_status"] == "matched"
            assert replay_metadata["failure_code"] is None
            create_metadata = audit_writer.await_args_list[0].kwargs["metadata"]
            assert create_metadata["policy_snapshot_id"]
            assert create_metadata["schema_snapshot_id"]
            assert create_metadata["manifest_version"]
    finally:
        app.dependency_overrides.clear()


def test_agent_run_routes_surface_conflict_and_openapi_security(monkeypatch, tmp_path) -> None:
    db = AsyncMock()

    async def _fake_db():
        yield db

    async def _noop_quota_check(*, auth: object, redis_client: object, request_state: object | None = None) -> None:
        del auth, redis_client, request_state

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(agent_runs_router, "_quota_check", _noop_quota_check)
    monkeypatch.setattr(agent_runs_router, "write_audit_event", AsyncMock())
    monkeypatch.setattr(agent_runs_router, "get_client_ip", lambda request: "203.0.113.10")
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    app.dependency_overrides[get_db] = _fake_db
    try:
        with SyncASGIClient(app) as client:
            create = client.post("/v1/agent/runs", json={"task": "Search the knowledge base"})
            run_id = create.json()["run_id"]

            conflict = client.post(f"/v1/agent/runs/{run_id}/cancel", json={})
            assert conflict.status_code == 409, conflict.text
            error = conflict.json()["error"]
            assert error["code"] == "agent_run_invalid_state"

            openapi = client.get("/openapi.json")
    finally:
        app.dependency_overrides.clear()

    assert openapi.status_code == 200
    payload = openapi.json()
    assert payload["paths"]["/v1/agent/runs"]["post"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert payload["paths"]["/v1/agent/runs"]["get"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/events"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/mission-events"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert payload["paths"]["/v1/agent/runs/mission-events"]["get"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/checkpoints"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert payload["paths"]["/v1/agent/runs/checkpoints"]["get"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/telemetry"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert payload["paths"]["/v1/agent/runs/telemetry"]["get"]["security"] == PROTECTED_OPENAPI_SECURITY
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/replay"]["post"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/fork"]["post"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        "text/event-stream"
        in payload["paths"]["/v1/agent/runs/{run_id}/events"]["get"]["responses"]["200"]["content"]
    )
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/resume"]["post"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/cancel"]["post"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        payload["paths"]["/v1/agent/runs/{run_id}/approve"]["post"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )


def test_agent_run_events_route_supports_sse_stream(monkeypatch, tmp_path) -> None:
    db = AsyncMock()

    async def _fake_db():
        yield db

    async def _noop_quota_check(*, auth: object, redis_client: object, request_state: object | None = None) -> None:
        del auth, redis_client, request_state

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(agent_runs_router, "_quota_check", _noop_quota_check)
    monkeypatch.setattr(agent_runs_router, "write_audit_event", AsyncMock())
    monkeypatch.setattr(agent_runs_router, "get_client_ip", lambda request: "203.0.113.10")
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    app.dependency_overrides[get_db] = _fake_db
    try:
        with SyncASGIClient(app) as client:
            create = client.post("/v1/agent/runs", json={"task": "Search the knowledge base"})
            assert create.status_code == 200, create.text
            run_id = create.json()["run_id"]

            stream_response = client.get(f"/v1/agent/runs/{run_id}/events?stream=true")
    finally:
        app.dependency_overrides.clear()

    assert stream_response.status_code == 200
    assert "text/event-stream" in stream_response.headers["content-type"]
    assert '"type":"agent.run.event"' in stream_response.text
    assert '"event_type":"run_created"' in stream_response.text
    assert '"type":"agent.run.completed"' in stream_response.text
    assert "data: [DONE]" in stream_response.text


def test_agent_run_list_rejects_invalid_status(monkeypatch, tmp_path) -> None:
    db = AsyncMock()

    async def _fake_db():
        yield db

    async def _noop_quota_check(*, auth: object, redis_client: object, request_state: object | None = None) -> None:
        del auth, redis_client, request_state

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(agent_runs_router, "_quota_check", _noop_quota_check)
    monkeypatch.setattr(agent_runs_router, "write_audit_event", AsyncMock())
    monkeypatch.setattr(agent_runs_router, "get_client_ip", lambda request: "203.0.113.10")
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    app.dependency_overrides[get_db] = _fake_db
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/agent/runs?status=invalid")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_agent_run_status"


def test_agent_run_trace_queries_reject_invalid_status(monkeypatch, tmp_path) -> None:
    db = AsyncMock()

    async def _fake_db():
        yield db

    async def _noop_quota_check(*, auth: object, redis_client: object, request_state: object | None = None) -> None:
        del auth, redis_client, request_state

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(agent_runs_router, "_quota_check", _noop_quota_check)
    monkeypatch.setattr(agent_runs_router, "write_audit_event", AsyncMock())
    monkeypatch.setattr(agent_runs_router, "get_client_ip", lambda request: "203.0.113.10")
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    app.dependency_overrides[get_db] = _fake_db
    try:
        with SyncASGIClient(app) as client:
            checkpoint_response = client.get("/v1/agent/runs/checkpoints?status=invalid")
            mission_response = client.get("/v1/agent/runs/mission-events?status=invalid")
            telemetry_response = client.get("/v1/agent/runs/telemetry?status=invalid")
    finally:
        app.dependency_overrides.clear()

    assert checkpoint_response.status_code == 422
    assert checkpoint_response.json()["error"]["code"] == "invalid_agent_run_status"
    assert mission_response.status_code == 422
    assert mission_response.json()["error"]["code"] == "invalid_agent_run_status"
    assert telemetry_response.status_code == 422
    assert telemetry_response.json()["error"]["code"] == "invalid_agent_run_status"
