from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _reload(module_name: str):
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def test_issue_and_store_requires_hosted_registration(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(Path.cwd() / ".tmp_runtime_contract_issue"))
    license_mod = _reload("apps.runtime.license")

    with patch.object(license_mod, "_exchange_api_key_for_license", return_value=None):
        lic = license_mod.issue_and_store("de_live_example")

    assert lic.valid is False
    assert "hosted license" in lic.message.lower()


def test_load_license_uses_dev_stub_only_when_explicit(monkeypatch) -> None:
    runtime_dir = Path.cwd() / ".tmp_runtime_contract_load"
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("ALGENTA_RUNTIME_DEV_MODE", "1")
    license_mod = _reload("apps.runtime.license")

    lic = license_mod.load_license("")

    assert lic.valid is True
    assert lic.source == "dev-stub"


def test_runtime_device_id_honors_documented_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEVICE_ID", "runtime-device-override-0001")
    monkeypatch.delenv("DE_DEVICE_ID", raising=False)

    device_mod = _reload("apps.runtime.device")

    assert device_mod.get_device_id() == "runtime-device-override-0001"
    assert device_mod.get_device_info()["device_id"] == "runtime-device-override-0001"


def test_runtime_device_id_legacy_override_and_validation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_DEVICE_ID", raising=False)
    monkeypatch.setenv("DE_DEVICE_ID", "legacy-runtime-device-0001")

    device_mod = _reload("apps.runtime.device")
    assert device_mod.get_device_id() == "legacy-runtime-device-0001"

    monkeypatch.setenv("ALGENTA_DEVICE_ID", "short")
    with pytest.raises(ValueError, match="ALGENTA_DEVICE_ID"):
        device_mod.get_device_id()


def test_executor_appends_runtime_ledger(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    _reload("apps.runtime.ledger")
    credits = _reload("apps.runtime.credits")
    executor_mod = _reload("apps.runtime.executor")

    store = credits.CreditStore(tmp_path / "credits.json")
    store.initialize_sync(credits_granted=5, billing_period="2026-04")
    old_store = credits._store
    credits._store = store
    try:
        executor = executor_mod.Executor()
        with patch.object(executor, "_mojo_available", return_value=True):
            with patch("apps.runtime.executor._mojo_call", return_value={"result": {"value": 42}}):
                result = _run_async(
                    executor.execute_module(
                        "monte_carlo", "run", {"trials": 10}, request_id="req-ledger"
                    )
                )
    finally:
        credits._store = old_store

    assert result["success"] is True
    ledger_path = tmp_path / "history.jsonl"
    assert ledger_path.exists()
    events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    statuses = [event["status"] for event in events]
    assert statuses == ["started", "completed"]
    assert all(event["request_id"] == "req-ledger" for event in events)


def test_executor_execute_query_appends_ledger_and_returns_response_json(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    _reload("apps.runtime.ledger")
    credits = _reload("apps.runtime.credits")
    executor_mod = _reload("apps.runtime.executor")

    store = credits.CreditStore(tmp_path / "credits.json")
    store.initialize_sync(credits_granted=5, billing_period="2026-04")
    old_store = credits._store
    credits._store = store
    engine_response = {
        "result": {"columns": ["a"], "rows": [[1.0]]},
        "lineage": [{"op": "join", "detail": "1 joined rows"}],
        "plan_hash": "deadbeef",
        "ops": 1,
    }
    try:
        executor = executor_mod.Executor()
        with patch.object(executor, "_mojo_available", return_value=True):
            with patch(
                "apps.runtime.executor._mojo_call", return_value=engine_response
            ) as mock_call:
                result = _run_async(
                    executor.execute_query(
                        json.dumps({"type": "query_execute", "ops": []}),
                        request_id="req-query",
                    )
                )
    finally:
        credits._store = old_store

    assert result["success"] is True
    assert result["engine_used"] == "mojo"
    assert json.loads(result["response_json"]) == engine_response
    mock_call.assert_called_once()
    assert mock_call.call_args.args[0]["type"] == "query_execute"

    ledger_path = tmp_path / "history.jsonl"
    events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    statuses = [event["status"] for event in events]
    assert statuses == ["started", "completed"]
    assert all(event["request_id"] == "req-query" for event in events)


def test_executor_execute_query_forces_type_regardless_of_caller_input(
    monkeypatch, tmp_path
) -> None:
    """A caller's JSON is never trusted for `type` -- this RPC bypasses the
    function-spec validation `execute_module` goes through, so nothing else
    stands between an arbitrary `type` (e.g. "shutdown") and the shared worker."""
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    _reload("apps.runtime.ledger")
    credits = _reload("apps.runtime.credits")
    executor_mod = _reload("apps.runtime.executor")

    store = credits.CreditStore(tmp_path / "credits.json")
    store.initialize_sync(credits_granted=5, billing_period="2026-04")
    old_store = credits._store
    credits._store = store
    try:
        executor = executor_mod.Executor()
        with patch.object(executor, "_mojo_available", return_value=True):
            with patch(
                "apps.runtime.executor._mojo_call", return_value={"status": "ready"}
            ) as mock_call:
                _run_async(
                    executor.execute_query(json.dumps({"type": "shutdown"}))
                )
    finally:
        credits._store = old_store

    assert mock_call.call_args.args[0]["type"] == "query_execute"


def test_executor_execute_query_rejects_invalid_json_before_any_call(tmp_path) -> None:
    executor_mod = _reload("apps.runtime.executor")
    executor = executor_mod.Executor()
    with patch("apps.runtime.executor._mojo_call") as mock_call:
        result = _run_async(executor.execute_query("not json"))
    mock_call.assert_not_called()
    assert result["success"] is False
    assert "not valid JSON" in result["error"]


def test_executor_routes_runtime_library_calls_through_compiled_worker(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    _reload("apps.runtime.ledger")
    credits = _reload("apps.runtime.credits")
    executor_mod = _reload("apps.runtime.executor")

    store = credits.CreditStore(tmp_path / "credits.json")
    store.initialize_sync(credits_granted=5, billing_period="2026-04")
    old_store = credits._store
    credits._store = store
    try:
        executor = executor_mod.Executor()
        with patch.object(executor, "_mojo_available", return_value=True):
            with patch(
                "apps.runtime.executor.build_runtime_library_worker_request",
                return_value=(
                    object(),
                    {
                        "type": "library_execute",
                        "engine_type": "library_execute",
                        "module": "elevator",
                        "function": "annual_energy_consumption",
                        "args": [0.5, 0.5, 0.5, 0.5],
                    },
                ),
            ) as build_request:
                with patch(
                    "apps.runtime.executor._mojo_call",
                    return_value={"result": 0.123},
                ) as mojo_call:
                    with patch(
                        "apps.runtime.executor.parse_runtime_library_worker_response",
                        return_value=0.123,
                    ) as parse_response:
                        result = _run_async(
                            executor.execute_module(
                                "elevator",
                                "annual_energy_consumption",
                                [0.5, 0.5, 0.5, 0.5],
                                request_id="req-library",
                            )
                        )
    finally:
        credits._store = old_store

    build_request.assert_called_once_with(
        "elevator",
        "annual_energy_consumption",
        [0.5, 0.5, 0.5, 0.5],
    )
    mojo_call.assert_called_once_with(
        {
            "type": "library_execute",
            "engine_type": "library_execute",
            "module": "elevator",
            "function": "annual_energy_consumption",
            "args": [0.5, 0.5, 0.5, 0.5],
        },
        executor._mojo_sock,
    )
    parse_response.assert_called_once()
    assert result["success"] is True
    assert result["engine_used"] == "mojo"
    assert result["result_json"] == "0.123"


def _run_async(coro):
    import asyncio

    previous = None
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        if previous is None:
            asyncio.set_event_loop(asyncio.new_event_loop())
        else:
            asyncio.set_event_loop(previous)
