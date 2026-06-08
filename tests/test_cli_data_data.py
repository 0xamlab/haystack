"""Tests for CLI data commands.

Extracted from tests/test_cli_data.py during modularization.
"""
from __future__ import annotations

import json

import pytest

from apps.cli import main as cli
from tests._manifest_backed_integrations import (
    MANIFEST_BACKED_INTEGRATIONS_DISPLAY,
    MANIFEST_BACKED_READ_ONLY_DISPLAY,
    assert_manifest_backed_integrations,
)
from tests._cli_data_helpers import (
    _capture_stdout,
    _capture_stderr,
    _platform_contract_payload,
)


def test_cmd_data_connect_with_request_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "connect.json"
    request_path.write_text(
        json.dumps(
            {
                "connection_type": "file_upload",
                "dataset_name": "Sales",
                "csv": "amount\n10\n20\n",
            }
        )
    )

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
            "schema_summary": {
                "row_count": 2,
                "columns": 1,
                "roles_summary": {"derived_measure": 1},
            },
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
                    {
                        "dataset_id": "ds_1",
                        "dataset_name": "Orders",
                        "visibility": "private",
                        "row_count": 10,
                        "columns": 3,
                    },
                ]
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_list, "table")
    assert "Datasets (1 returned / 1 total)" in output
    assert "ds_1" in output


def test_cmd_data_list_supports_discovery_filters_and_compact(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert (
            path
            == "/v1/data?page=1&limit=5&search=otp&status=ready&source_name=ops_postgres&compact=1"
        )
        return 200, {
            "datasets": [
                {
                    "dataset_id": "ds_otp",
                    "name": "OTP Monthly",
                    "status": "ready",
                    "source_names": ["ops_postgres"],
                    "column_count": 42,
                    "registered_at": "2026-05-20T10:00:00Z",
                }
            ],
            "total": 12,
            "matched_total": 1,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_data_list,
        "table",
        search="otp",
        status_filter="ready",
        source_name="ops_postgres",
        page=1,
        limit=5,
        compact=True,
    )
    assert "1 matched / 12 total" in output
    assert "OTP Monthly" in output
    assert "ops_postgres" in output


def test_cmd_data_summary_prints_low_token_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "dataset_id": "ds_otp",
                "name": "OTP Monthly",
                "status": "ready",
                "source_names": ["ops_postgres"],
                "row_count": 1200,
                "column_count": 42,
                "registered_at": "2026-05-20T10:00:00Z",
                "query_hints": ["otp_rate", "flight_month"],
            },
        ),
    )
    output = _capture_stdout(cli.cmd_data_summary, "ds_otp", "table")
    assert "Dataset summary: OTP Monthly (ds_otp)" in output
    assert "otp_rate" in output
    assert "1200 / 42" in output


def test_cmd_data_inspect_prints_schema(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "dataset": {
                    "dataset_name": "Orders",
                    "dataset_id": "ds_1",
                    "visibility": "private",
                    "refreshable": True,
                },
                "schema": {
                    "row_count": 10,
                    "columns": [{"name": "amount", "role": "derived_measure"}],
                },
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


def test_cmd_data_query_batch_prints_ordered_result_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "batch.json"
    request_path.write_text(
        json.dumps(
            {
                "defaults": {"dataset_id": "otp_events"},
                "queries": [
                    {
                        "key": "overall_otp",
                        "request": {"metric": {"role": "metric", "hint": "otp_rate"}},
                    }
                ],
            }
        )
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/query/batch"
        assert body["defaults"]["dataset_id"] == "otp_events"
        return 200, {
            "request_id": "req_batch",
            "results": [
                {
                    "key": "overall_otp",
                    "data": {"resolved_column": "otp_rate_pct", "row_count": 1},
                    "metadata": {"latency_ms": 12.4},
                },
                {
                    "key": "avg_delay",
                    "error": {"code": "metric_not_found", "message": "missing"},
                },
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_data_query_batch, str(request_path), "table")
    assert "Query batch request: req_batch" in output
    assert "overall_otp" in output
    assert "metric_not_found" in output


def test_cmd_data_sql_report_prints_report_preview(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "report.json"
    request_path.write_text(
        json.dumps(
            {
                "sources": [{"dataset_id": "ds_otp", "alias": "otp"}],
                "sql": "select flight_month, otp_rate_pct from otp",
                "max_rows": 100,
            }
        )
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/query/sql-report"
        assert body["sources"][0]["alias"] == "otp"
        return 200, {
            "request_id": "req_sql",
            "columns": ["flight_month", "otp_rate_pct"],
            "rows": [{"flight_month": "2026-04-01", "otp_rate_pct": 92.4}],
            "row_count": 1,
            "truncated": False,
            "latency_ms": 24.1,
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_data_sql_report, str(request_path), "table")
    assert "SQL report request: req_sql" in output
    assert "flight_month, otp_rate_pct" in output
    assert "2026-04-01 | 92.4" in output


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


def test_cmd_data_disconnect_requires_yes_in_noninteractive_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_data_disconnect("ds_1", assume_yes=False, format="json")

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "--yes" in captured.err


def test_main_dispatches_data_list(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_data_list(format: str = "table", **kwargs) -> None:  # type: ignore[no-untyped-def]
        called["format"] = format
        called.update(kwargs)

    monkeypatch.setattr(cli, "cmd_data_list", _fake_cmd_data_list)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "de",
            "data",
            "list",
            "--format",
            "json",
            "--search",
            "otp",
            "--status",
            "ready",
            "--source-name",
            "ops_postgres",
            "--page",
            "2",
            "--limit",
            "5",
            "--compact",
        ],
    )

    cli.main()

    assert called == {
        "format": "json",
        "search": "otp",
        "status_filter": "ready",
        "source_name": "ops_postgres",
        "page": 2,
        "limit": 5,
        "compact": True,
    }


def test_main_dispatches_data_summary(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_data_summary(dataset_id: str, format: str = "table") -> None:
        called["dataset_id"] = dataset_id
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_data_summary", _fake_cmd_data_summary)
    monkeypatch.setattr(cli.sys, "argv", ["de", "data", "summary", "ds_otp", "--format", "json"])

    cli.main()

    assert called == {"dataset_id": "ds_otp", "format": "json"}


def test_main_dispatches_data_query_batch_and_sql_report(monkeypatch) -> None:
    called: list[tuple[str, str, str]] = []

    def _fake_cmd_data_query_batch(request_path: str, format: str = "table") -> None:
        called.append(("batch", request_path, format))

    def _fake_cmd_data_sql_report(request_path: str, format: str = "table") -> None:
        called.append(("sql", request_path, format))

    monkeypatch.setattr(cli, "cmd_data_query_batch", _fake_cmd_data_query_batch)
    monkeypatch.setattr(cli, "cmd_data_sql_report", _fake_cmd_data_sql_report)

    monkeypatch.setattr(
        cli.sys, "argv", ["de", "data", "query-batch", "batch.json", "--format", "json"]
    )
    cli.main()

    monkeypatch.setattr(cli.sys, "argv", ["de", "data", "sql-report", "report.json"])
    cli.main()

    assert called == [("batch", "batch.json", "json"), ("sql", "report.json", "table")]


