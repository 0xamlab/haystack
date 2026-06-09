"""Tests for test_algenta_runtime_connectors: runtime_connect.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-2/tests/test_algenta_runtime_connectors.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_connectors_helpers import *  # noqa: F401,F403


def test_runtime_connect_inline_connector_requires_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    monkeypatch.setattr(runtime, "_client", lambda: object())

    with pytest.raises(RuntimeValidationError, match="persist=True"):
        runtime.connect(
            connector={"type": "postgres", "host": "localhost", "database": "analytics"},
            dataset_name="orders_dataset",
        )


def test_runtime_connect_saved_connector_uses_data_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="self_hosted", api_key="de_live_test", base_url="http://localhost:8000")
    captured: dict[str, object] | None = None

    class _ConnectResult(SimpleNamespace):
        def model_dump(self) -> dict[str, object]:
            return dict(self.__dict__)

    class _FakeClient:
        def connect_data(self, payload):
            nonlocal captured
            captured = payload
            return _ConnectResult(
                status="ready",
                dataset_id="ds_ready",
                source_id="ds_ready",
                dataset_name="orders_dataset",
                schema={"fields": ["amount"]},
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    registration = runtime.connect(
        connector_id="conn_123",
        dataset_name="orders_dataset",
        selection={"table": "orders"},
    )

    assert isinstance(registration, SourceRegistration)
    assert registration.dataset_id == "ds_ready"
    assert captured == {
        "dataset_name": "orders_dataset",
        "description": None,
        "selection": {"table": "orders"},
        "visibility": None,
        "connection_id": "conn_123",
    }


def test_runtime_connect_inline_connector_with_persist_true_uses_connector_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    captured: dict[str, object] | None = None

    class _ConnectResult(SimpleNamespace):
        def model_dump(self) -> dict[str, object]:
            return dict(self.__dict__)

    class _FakeClient:
        def connect_data(self, payload):
            nonlocal captured
            captured = payload
            return _ConnectResult(
                status="ready",
                dataset_id="ds_ready",
                source_id="ds_ready",
                dataset_name="orders_dataset",
                schema={"fields": ["amount"]},
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    registration = runtime.connect(
        connector={"type": "postgres", "host": "localhost", "database": "analytics"},
        dataset_name="orders_dataset",
        persist=True,
    )

    assert isinstance(registration, SourceRegistration)
    assert registration.dataset_id == "ds_ready"
    assert captured == {
        "dataset_name": "orders_dataset",
        "description": None,
        "selection": {},
        "visibility": None,
        "connector": {"type": "postgres", "host": "localhost", "database": "analytics"},
    }


