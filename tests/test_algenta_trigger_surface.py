from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")
sdk_triggers = importlib.import_module("decision_engine.models_triggers")

CodnaClient = algenta.CodnaClient
Runtime = algenta.Runtime
RuntimeValidationError = algenta.RuntimeValidationError
SDKTriggerDeleteResult = sdk_triggers.TriggerDeleteResult
TriggerDeleteOutput = algenta.TriggerDeleteOutput
TriggerFireOutput = algenta.TriggerFireOutput
TriggerListOutput = algenta.TriggerListOutput
TriggerPauseOutput = algenta.TriggerPauseOutput
TriggerSummaryOutput = algenta.TriggerSummaryOutput


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


class _FakeDecisionEngineClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(self, method_name: str, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append((method_name, args, kwargs))
        return {"name": method_name, "args": list(args), "kwargs": kwargs}

    def register_trigger(
        self,
        *,
        name: str,
        condition: dict[str, object],
        simulation_template: dict[str, object],
        webhook_url=None,
        execution_webhook_url=None,
        auto_execute=False,
        description=None,
    ):
        return self._record(
            "register_trigger",
            name=name,
            condition=condition,
            simulation_template=simulation_template,
            webhook_url=webhook_url,
            execution_webhook_url=execution_webhook_url,
            auto_execute=auto_execute,
            description=description,
        )

    def list_triggers(self, *, status="all", page=None, limit=None):
        return self._record("list_triggers", status=status, page=page, limit=limit)

    def fire_trigger(self, trigger_id: str, *, force=False):
        return self._record("fire_trigger", trigger_id, force=force)

    def pause_trigger(self, trigger_id: str, *, paused=True):
        return self._record("pause_trigger", trigger_id, paused=paused)

    def delete_trigger(self, trigger_id: str):
        return self._record("delete_trigger", trigger_id)


class _FakeRuntimeApiClient:
    def register_trigger(
        self,
        *,
        name: str,
        condition: dict[str, object],
        simulation_template: dict[str, object],
        webhook_url=None,
        execution_webhook_url=None,
        auto_execute=False,
        description=None,
    ):
        assert name == "Revenue alert"
        assert condition["metric_hint"] == "revenue"
        assert simulation_template["mode"] == "auto"
        assert webhook_url == "https://example.com/hook"
        assert execution_webhook_url == "https://example.com/execute"
        assert auto_execute is True
        assert description == "Watch for monthly revenue spikes."
        return _trigger_summary_payload()

    def list_triggers(self, *, status="all", page=None, limit=None):
        assert status == "paused"
        assert page == 2
        assert limit == 10
        return {
            "triggers": [{**_trigger_summary_payload(), "status": "paused"}],
            "count": 1,
            "total": 1,
            "page": 2,
            "limit": 10,
            "pages": 1,
        }

    def fire_trigger(self, trigger_id: str, *, force=False):
        assert trigger_id == "trigger_123"
        assert force is True
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

    def pause_trigger(self, trigger_id: str, *, paused=True):
        assert trigger_id == "trigger_123"
        return {"trigger_id": trigger_id, "status": "paused" if paused else "active"}

    def delete_trigger(self, trigger_id: str):
        assert trigger_id == "trigger_123"
        return {}


def test_algenta_client_trigger_methods_delegate_to_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = type("FakeDecisionEngineModule", (), {"DecisionEngineClient": _FakeDecisionEngineClient})
    client_module = importlib.import_module("algenta.client")
    monkeypatch.setattr(client_module, "import_module", lambda name: fake_module)

    client = CodnaClient(api_key="de_test", base_url="http://localhost:8000")

    created = client.register_trigger(
        name="Revenue alert",
        condition={
            "source_id": "src_orders",
            "metric_hint": "revenue",
            "threshold": 200000,
            "direction": "above",
        },
        simulation_template={"mode": "auto"},
        webhook_url="https://example.com/hook",
        execution_webhook_url="https://example.com/execute",
        auto_execute=True,
        description="Watch for monthly revenue spikes.",
    )
    listed = client.list_triggers(status="paused", page=2, limit=10)
    fired = client.fire_trigger("trigger_123", force=True)
    paused = client.pause_trigger("trigger_123", paused=False)
    deleted = client.delete_trigger("trigger_123")

    assert created["name"] == "register_trigger"
    assert listed["name"] == "list_triggers"
    assert fired["name"] == "fire_trigger"
    assert paused["name"] == "pause_trigger"
    assert deleted["name"] == "delete_trigger"
    assert client._sdk_client().calls == [
        (
            "register_trigger",
            (),
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
            },
        ),
        ("list_triggers", (), {"status": "paused", "page": 2, "limit": 10}),
        ("fire_trigger", ("trigger_123",), {"force": True}),
        ("pause_trigger", ("trigger_123",), {"paused": False}),
        ("delete_trigger", ("trigger_123",), {}),
    ]


def test_algenta_runtime_trigger_methods_return_typed_outputs() -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")
    runtime._api_client = _FakeRuntimeApiClient()

    created = runtime.register_trigger(
        name="Revenue alert",
        condition={
            "source_id": "src_orders",
            "metric_hint": "revenue",
            "threshold": 200000,
            "direction": "above",
        },
        simulation_template={"mode": "auto"},
        webhook_url="https://example.com/hook",
        execution_webhook_url="https://example.com/execute",
        auto_execute=True,
        description="Watch for monthly revenue spikes.",
    )
    listed = runtime.list_triggers(status="paused", page=2, limit=10)
    fired = runtime.fire_trigger("trigger_123", force=True)
    paused = runtime.pause_trigger("trigger_123", paused=True)
    deleted = runtime.delete_trigger("trigger_123")

    assert isinstance(created, TriggerSummaryOutput)
    assert created.execution_webhook_url == "https://example.com/execute"
    assert isinstance(listed, TriggerListOutput)
    assert listed.page == 2
    assert listed.triggers[0].status == "paused"
    assert isinstance(fired, TriggerFireOutput)
    assert fired.simulation_run_id == "run_123"
    assert isinstance(paused, TriggerPauseOutput)
    assert paused.status == "paused"
    assert isinstance(deleted, TriggerDeleteOutput)
    assert deleted.deleted is True


def test_algenta_runtime_trigger_methods_fail_closed_on_invalid_payload() -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")

    class _BrokenClient:
        def list_triggers(self, *, status="all", page=None, limit=None):
            return {"triggers": "bad"}

    runtime._api_client = _BrokenClient()

    with pytest.raises(RuntimeValidationError) as exc_info:
        runtime.list_triggers()
    assert exc_info.value.code == "invalid_runtime_api_payload"


def test_algenta_runtime_delete_trigger_accepts_typed_sdk_result() -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")

    class _TypedDeleteClient:
        def delete_trigger(self, trigger_id: str):
            assert trigger_id == "trigger_123"
            return SDKTriggerDeleteResult(trigger_id=trigger_id, deleted=True)

    runtime._api_client = _TypedDeleteClient()

    deleted = runtime.delete_trigger("trigger_123")

    assert isinstance(deleted, TriggerDeleteOutput)
    assert deleted.trigger_id == "trigger_123"
    assert deleted.deleted is True
