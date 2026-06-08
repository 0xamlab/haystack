from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from decision_engine import async_client_trigger_surface, client_trigger_surface


def _trigger_summary_payload() -> dict[str, object]:
    return {
        "trigger_id": "trigger_123",
        "org_id": "org_123",
        "name": "Revenue alert",
        "status": "active",
        "condition": {
            "source_id": "src_orders",
            "metric_hint": "revenue",
            "threshold": 200000.0,
            "direction": "above",
            "aggregation": "sum",
        },
        "description": "Watch for monthly revenue spikes.",
        "webhook_url": "https://example.com/hook",
        "execution_webhook_url": "https://example.com/execute",
        "auto_execute": True,
        "created_at": "2026-05-24T12:00:00Z",
        "last_checked_at": "2026-05-24T12:05:00Z",
        "last_fired_at": None,
        "last_result_summary": None,
    }


def test_register_trigger_posts_validated_payload() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return _trigger_summary_payload()

    client = SimpleNamespace(_request=_request)

    result = client_trigger_surface.register_trigger(
        client,
        name="Revenue alert",
        condition={
            "source_id": "src_orders",
            "metric_hint": "revenue",
            "threshold": 200000,
            "direction": "above",
        },
        simulation_template={"mode": "auto", "scenario": {"objective": "maximize_net_value"}},
        webhook_url="https://example.com/hook",
        execution_webhook_url="https://example.com/execute",
        auto_execute=True,
        description="Watch for monthly revenue spikes.",
    )

    assert result.trigger_id == "trigger_123"
    assert captured == {
        "method": "POST",
        "path": "/v1/triggers",
        "json": {
            "name": "Revenue alert",
            "condition": {
                "source_id": "src_orders",
                "metric_hint": "revenue",
                "threshold": 200000.0,
                "direction": "above",
                "aggregation": "sum",
            },
            "simulation_template": {"mode": "auto", "scenario": {"objective": "maximize_net_value"}},
            "auto_execute": True,
            "webhook_url": "https://example.com/hook",
            "execution_webhook_url": "https://example.com/execute",
            "description": "Watch for monthly revenue spikes.",
        },
    }


def test_list_triggers_builds_filtered_query() -> None:
    captured: dict[str, object] = {}

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured["method"] = method
        captured["path"] = path
        captured["params"] = kwargs["params"]
        return {
            "triggers": [_trigger_summary_payload()],
            "count": 1,
            "total": 1,
            "page": 2,
            "limit": 10,
            "pages": 1,
        }

    client = SimpleNamespace(_request=_request)

    result = client_trigger_surface.list_triggers(client, status="paused", page=2, limit=10)

    assert result.total == 1
    assert result.triggers[0].status == "active"
    assert captured == {
        "method": "GET",
        "path": "/v1/triggers",
        "params": {"page": 2, "limit": 10, "status": "paused"},
    }


def test_fire_pause_and_delete_trigger_target_canonical_routes() -> None:
    calls: list[tuple[str, str, object, object]] = []

    def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        calls.append((method, path, kwargs.get("json"), kwargs.get("params")))
        if (method, path) == ("POST", "/v1/triggers/trigger_123/fire"):
            return {
                "trigger_id": "trigger_123",
                "condition_met": True,
                "fired": True,
                "simulation_run_id": "run_123",
                "recommended_action": "proceed",
                "expected_value": 123000.0,
                "confidence": 0.82,
                "fired_at": "2026-05-24T12:05:00Z",
                "execution_status": "queued",
                "message": "Trigger fired.",
            }
        if (method, path) == ("PATCH", "/v1/triggers/trigger_123/pause"):
            return {"trigger_id": "trigger_123", "status": "paused"}
        if (method, path) == ("DELETE", "/v1/triggers/trigger_123"):
            return {}
        raise AssertionError(f"Unexpected call {(method, path)}")

    client = SimpleNamespace(_request=_request)

    fired = client_trigger_surface.fire_trigger(client, "trigger_123", force=True)
    paused = client_trigger_surface.pause_trigger(client, "trigger_123", paused=True)
    deleted = client_trigger_surface.delete_trigger(client, "trigger_123")

    assert fired.fired is True
    assert paused.status == "paused"
    assert deleted.deleted is True
    assert calls == [
        ("POST", "/v1/triggers/trigger_123/fire", {"force": True}, None),
        ("PATCH", "/v1/triggers/trigger_123/pause", None, {"paused": True}),
        ("DELETE", "/v1/triggers/trigger_123", None, None),
    ]


def test_trigger_validation_fails_closed_for_invalid_inputs() -> None:
    client = SimpleNamespace(_request=lambda *args, **kwargs: {})  # type: ignore[return-value]

    with pytest.raises(ValueError, match="name must be a non-empty string"):
        client_trigger_surface.register_trigger(
            client,
            name="",
            condition={},
            simulation_template={"mode": "auto"},
        )
    with pytest.raises(ValueError, match="condition.source_id must be a non-empty string"):
        client_trigger_surface.register_trigger(
            client,
            name="Revenue alert",
            condition={"source_id": "", "metric_hint": "revenue", "threshold": 1, "direction": "above"},
            simulation_template={"mode": "auto"},
        )
    with pytest.raises(ValueError, match="status must be one of: active, paused, all"):
        client_trigger_surface.list_triggers(client, status="disabled")
    with pytest.raises(ValueError, match="trigger_id must be a non-empty string"):
        client_trigger_surface.fire_trigger(client, " ")


@pytest.mark.anyio
async def test_async_trigger_methods_forward_canonical_routes() -> None:
    calls: list[tuple[str, str, object, object]] = []

    async def _request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        calls.append((method, path, kwargs.get("json"), kwargs.get("params")))
        if (method, path) == ("POST", "/v1/triggers"):
            return _trigger_summary_payload()
        if (method, path) == ("GET", "/v1/triggers"):
            return {
                "triggers": [_trigger_summary_payload()],
                "count": 1,
                "total": 1,
            "page": 1,
            "limit": 25,
            "pages": 1,
        }
        if (method, path) == ("POST", "/v1/triggers/trigger_123/fire"):
            return {
                "trigger_id": "trigger_123",
                "condition_met": True,
                "fired": True,
                "simulation_run_id": "run_async_123",
                "recommended_action": "proceed",
                "expected_value": 99000.0,
                "confidence": 0.74,
                "fired_at": "2026-05-24T12:06:00Z",
                "execution_status": "queued",
                "message": "Trigger fired.",
            }
        if (method, path) == ("PATCH", "/v1/triggers/trigger_123/pause"):
            return {"trigger_id": "trigger_123", "status": "active"}
        if (method, path) == ("DELETE", "/v1/triggers/trigger_123"):
            return {}
        raise AssertionError(f"Unexpected call {(method, path)}")

    client = SimpleNamespace(_request=_request)

    created = await async_client_trigger_surface.register_trigger(
        client,
        name="Revenue alert",
        condition={
            "source_id": "src_orders",
            "metric_hint": "revenue",
            "threshold": 200000,
            "direction": "above",
        },
        simulation_template={"mode": "auto"},
    )
    listed = await async_client_trigger_surface.list_triggers(client)
    fired = await async_client_trigger_surface.fire_trigger(client, "trigger_123", force=True)
    resumed = await async_client_trigger_surface.pause_trigger(client, "trigger_123", paused=False)
    deleted = await async_client_trigger_surface.delete_trigger(client, "trigger_123")

    assert created.trigger_id == "trigger_123"
    assert listed.count == 1
    assert fired.simulation_run_id == "run_async_123"
    assert resumed.status == "active"
    assert deleted.deleted is True
    assert calls == [
        (
            "POST",
            "/v1/triggers",
            {
                "name": "Revenue alert",
                "condition": {
                    "source_id": "src_orders",
                    "metric_hint": "revenue",
                    "threshold": 200000.0,
                    "direction": "above",
                    "aggregation": "sum",
                },
                "simulation_template": {"mode": "auto"},
                "auto_execute": False,
            },
            None,
        ),
        ("GET", "/v1/triggers", None, None),
        ("POST", "/v1/triggers/trigger_123/fire", {"force": True}, None),
        ("PATCH", "/v1/triggers/trigger_123/pause", None, {"paused": False}),
        ("DELETE", "/v1/triggers/trigger_123", None, None),
    ]


@pytest.mark.anyio
async def test_async_trigger_validation_fails_closed_for_invalid_inputs() -> None:
    client = SimpleNamespace(_request=lambda *args, **kwargs: {})  # type: ignore[return-value]

    with pytest.raises(ValueError, match="simulation_template must be a non-empty JSON object"):
        await async_client_trigger_surface.register_trigger(
            client,
            name="Revenue alert",
            condition={
                "source_id": "src_orders",
                "metric_hint": "revenue",
                "threshold": 1,
                "direction": "above",
            },
            simulation_template={},
        )
    with pytest.raises(ValueError, match="status must be one of: active, paused, all"):
        await async_client_trigger_surface.list_triggers(client, status="disabled")
    with pytest.raises(ValueError, match="trigger_id must be a non-empty string"):
        await async_client_trigger_surface.fire_trigger(client, " ")
