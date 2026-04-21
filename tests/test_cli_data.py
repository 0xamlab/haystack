from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from apps.cli import main as cli


def _capture_stdout(fn, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()


def test_cmd_data_connect_with_request_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "connect.json"
    request_path.write_text(json.dumps({
        "connection_type": "file_upload",
        "dataset_name": "Sales",
        "csv": "amount\n10\n20\n",
    }))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/data/connect"
        assert body["dataset_name"] == "Sales"
        return 200, {
            "status": "ready",
            "dataset_id": "ds_sales",
            "dataset_name": "Sales",
            "connection_type": "file_upload",
            "provider": "file",
            "visibility": "private",
            "schema_summary": {"row_count": 2, "columns": 1, "roles_summary": {"derived_measure": 1}},
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_data_connect, str(request_path), "table")
    assert "Dataset ID" in output
    assert "ds_sales" in output


def test_cmd_data_list_prints_datasets(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "datasets": [
                    {"dataset_id": "ds_1", "dataset_name": "Orders", "visibility": "private", "row_count": 10, "columns": 3},
                ]
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_list, "table")
    assert "Datasets (1)" in output
    assert "ds_1" in output


def test_cmd_data_inspect_prints_schema(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "dataset": {"dataset_name": "Orders", "dataset_id": "ds_1", "visibility": "private", "refreshable": True},
                "schema": {"row_count": 10, "columns": [{"name": "amount", "role": "derived_measure"}]},
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_inspect, "ds_1", "table")
    assert "Dataset: Orders (ds_1)" in output
    assert "amount [derived_measure]" in output


def test_cmd_data_refresh_prints_ready(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "status": "ready",
                "dataset_id": "ds_1",
                "dataset_name": "Orders",
                "connection_type": "database",
                "provider": "sqlite",
                "visibility": "private",
                "schema_summary": {"row_count": 10, "columns": 1, "roles_summary": {}},
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_refresh, "ds_1", "table")
    assert "Dataset ID" in output
    assert "sqlite" in output


def test_cmd_data_disconnect_prints_deleted(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {"dataset_id": "ds_1", "status": "deleted", "connection_deleted": True},
        ),
    )
    output = _capture_stdout(cli.cmd_data_disconnect, "ds_1", assume_yes=True, format="table")
    assert "Deleted dataset ds_1" in output


def test_main_dispatches_data_list(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_data_list(format: str = "table") -> None:
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_data_list", _fake_cmd_data_list)
    monkeypatch.setattr(cli.sys, "argv", ["de", "data", "list", "--format", "json"])

    cli.main()

    assert called == {"format": "json"}


def test_cmd_runtime_history_prints_recent_events(monkeypatch, tmp_path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    ledger = runtime_dir / "history.jsonl"
    ledger.write_text("\n".join([
        json.dumps({
            "timestamp": 1_700_000_000,
            "status": "started",
            "target": "monte_carlo.run",
            "engine_used": None,
            "latency_ms": None,
            "error": None,
        }),
        json.dumps({
            "timestamp": 1_700_000_001,
            "status": "completed",
            "target": "monte_carlo.run",
            "engine_used": "python-fallback",
            "latency_ms": 12.34,
            "error": None,
        }),
    ]))
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir))
    output = _capture_stdout(cli.cmd_runtime_history, 10, "table")
    assert "Runtime history (2 events)" in output
    assert "monte_carlo.run" in output
    assert "python-fallback" in output


def test_main_dispatches_runtime_history(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_runtime_history(limit: int = 20, format: str = "table") -> None:
        called["limit"] = limit
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_runtime_history", _fake_cmd_runtime_history)
    monkeypatch.setattr(cli.sys, "argv", ["de", "runtime", "history", "--limit", "5", "--format", "json"])

    cli.main()

    assert called == {"limit": 5, "format": "json"}
