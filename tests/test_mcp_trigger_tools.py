from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import triggers


def test_trigger_tool_specs_cover_full_lifecycle_surface() -> None:
    assert triggers.REGISTER_TRIGGER_SPEC["name"] == "register_trigger"
    assert triggers.LIST_TRIGGERS_SPEC["name"] == "list_triggers"
    assert triggers.FIRE_TRIGGER_SPEC["name"] == "fire_trigger"
    assert triggers.PAUSE_TRIGGER_SPEC["name"] == "pause_trigger"
    assert triggers.DELETE_TRIGGER_SPEC["name"] == "delete_trigger"
    register_props = triggers.REGISTER_TRIGGER_SPEC["inputSchema"]["properties"]
    assert "execution_webhook_url" in register_props
    assert "auto_execute" in register_props


@pytest.mark.anyio
async def test_trigger_handlers_forward_canonical_api_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, object]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path, kwargs.get("json") if "json" in kwargs else kwargs.get("params")))
        if (method, path) == ("POST", "/v1/triggers"):
            return {
                "trigger_id": "trigger_123",
                "name": "Revenue alert",
                "status": "active",
                "condition": {"metric_hint": "revenue", "direction": "above", "threshold": 200000},
                "created_at": "2026-05-24T12:00:00Z",
            }
        if (method, path) == ("GET", "/v1/triggers"):
            return {
                "triggers": [
                    {
                        "trigger_id": "trigger_123",
                        "name": "Revenue alert",
                        "status": "paused",
                        "condition": {"metric_hint": "revenue", "direction": "above", "threshold": 200000},
                        "last_checked_at": "2026-05-24T12:05:00Z",
                        "last_fired_at": None,
                        "last_result_summary": None,
                    }
                ],
                "count": 1,
                "total": 1,
                "page": 2,
                "limit": 10,
                "pages": 1,
            }
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
            }
        if (method, path) == ("PATCH", "/v1/triggers/trigger_123/pause?paused=true"):
            return {"trigger_id": "trigger_123", "status": "paused"}
        if (method, path) == ("DELETE", "/v1/triggers/trigger_123"):
            return {}
        raise AssertionError(f"Unexpected call {(method, path)}")

    monkeypatch.setattr(triggers, "api", _fake_api)

    created = json.loads(
        await triggers.register_trigger_handler(
            {
                "name": "Revenue alert",
                "condition": {
                    "source_id": "src_orders",
                    "metric_hint": "revenue",
                    "threshold": 200000,
                    "direction": "above",
                },
                "simulation_template": {"mode": "auto"},
                "webhook_url": "https://example.com/hook",
                "execution_webhook_url": "https://example.com/execute",
                "auto_execute": True,
                "description": "Watch for monthly revenue spikes.",
            }
        )
    )
    listed = json.loads(await triggers.list_triggers_handler({"status": "paused", "page": 2, "limit": 10}))
    fired = json.loads(await triggers.fire_trigger_handler({"trigger_id": "trigger_123", "force": True}))
    paused = json.loads(await triggers.pause_trigger_handler({"trigger_id": "trigger_123", "paused": True}))
    deleted = json.loads(await triggers.delete_trigger_handler({"trigger_id": "trigger_123"}))

    assert created["trigger_id"] == "trigger_123"
    assert listed["triggers"][0]["status"] == "paused"
    assert fired["fired"] is True
    assert fired["simulation_run_id"] == "run_123"
    assert paused["status"] == "paused"
    assert deleted == {"trigger_id": "trigger_123", "deleted": True}
    assert calls == [
        (
            "POST",
            "/v1/triggers",
            {
                "name": "Revenue alert",
                "condition": {
                    "source_id": "src_orders",
                    "metric_hint": "revenue",
                    "threshold": 200000,
                    "direction": "above",
                },
                "simulation_template": {"mode": "auto"},
                "webhook_url": "https://example.com/hook",
                "execution_webhook_url": "https://example.com/execute",
                "description": "Watch for monthly revenue spikes.",
                "auto_execute": True,
            },
        ),
        ("GET", "/v1/triggers", {"status": "paused", "page": 2, "limit": 10}),
        ("POST", "/v1/triggers/trigger_123/fire", {"force": True}),
        ("PATCH", "/v1/triggers/trigger_123/pause?paused=true", None),
        ("DELETE", "/v1/triggers/trigger_123", None),
    ]


@pytest.mark.anyio
async def test_trigger_handlers_fail_closed_on_missing_required_fields() -> None:
    assert json.loads(await triggers.register_trigger_handler({"name": "Incomplete"})) == {
        "error": "condition is required"
    }
    assert json.loads(await triggers.fire_trigger_handler({})) == {"error": "trigger_id is required"}
    assert json.loads(await triggers.pause_trigger_handler({})) == {"error": "trigger_id is required"}
    assert json.loads(await triggers.delete_trigger_handler({})) == {"error": "trigger_id is required"}
