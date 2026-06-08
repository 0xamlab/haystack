"""Tests for CLI decision commands.

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


def test_cmd_decision_plan_posts_request_and_prints_plan_summary(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "plan.json"
    payload = {
        "simulation_type": "monte_carlo",
        "parameters": {"trials": 500},
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/decisions/plan"
        assert body == payload
        return 200, {
            "recommended_action": "expand_capacity",
            "confidence": 0.83,
            "expected_value": 125000.0,
            "risk": {"p5": -1000.0, "p95": 220000.0, "probability_of_loss": 0.12},
            "rationale": "Expected upside dominates downside risk.",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decision_plan, str(request_path), "table")

    assert "Recommended:    expand_capacity" in output
    assert "Confidence:     0.83" in output
    assert "Expected value: 125000.0" in output
    assert "Risk:           p5=-1000.0 p95=220000.0 pol=0.12" in output


def test_cmd_decisions_log_posts_request_and_prints_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "decision-log.json"
    payload = {
        "chosen_action": "expand",
        "context": "Launch planning",
        "expected_value": 128000.0,
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/decisions"
        assert body == payload
        return 201, {
            "id": "decision_123",
            "chosen_action": "expand",
            "confidence": 0.82,
            "expected_value": 128000.0,
            "policy_snapshot_id": "policy-v1",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
            "created_at": "2026-05-24T12:00:00Z",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_log, str(request_path), "table")

    assert "Decision ID:     decision_123" in output
    assert "Chosen action:   expand" in output
    assert "Confidence:      0.82" in output
    assert "Policy snapshot: policy-v1" in output
    assert "Schema snapshot: schema-v1" in output
    assert "Manifest:        runtime-manifest-v1" in output


def test_cmd_decisions_list_gets_paginated_results_and_prints_rows(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/decisions?page=1&limit=20&with_outcome_only=true"
        assert body is None
        return 200, {
            "page": 1,
            "pages": 1,
            "total": 1,
            "limit": 20,
            "decisions": [
                {
                    "id": "decision_123",
                    "chosen_action": "expand",
                    "expected_value": 128000.0,
                    "actual_outcome": 141000.0,
                    "outcome_delta": 13000.0,
                    "policy_snapshot_id": "policy-v1",
                    "schema_snapshot_id": "schema-v1",
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_decisions_list,
        page=1,
        limit=20,
        with_outcome_only=True,
        format="table",
    )

    assert "Page: 1 / 1  Total: 1  Limit: 20" in output
    assert (
        "decision_123 action=expand expected=128000.0 actual=141000.0 delta=13000.0 "
        "policy=policy-v1 schema=schema-v1"
    ) in output


def test_cmd_decisions_get_fetches_record_and_prints_detail(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/decisions/decision_123"
        assert body is None
        return 200, {
            "id": "decision_123",
            "chosen_action": "expand",
            "context": "Launch planning",
            "expected_value": 128000.0,
            "actual_outcome": 141000.0,
            "outcome_delta": 13000.0,
            "execution_status": "delivered",
            "policy_snapshot_id": "policy-v1",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_get, "decision_123", "table")

    assert "Decision ID:     decision_123" in output
    assert "Context:         Launch planning" in output
    assert "Execution:       delivered" in output
    assert "Policy snapshot: policy-v1" in output
    assert "Schema snapshot: schema-v1" in output
    assert "Manifest:        runtime-manifest-v1" in output


def test_cmd_decisions_outcome_patches_payload_and_prints_delta(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "decision-outcome.json"
    payload = {"actual_outcome": 141000.0, "outcome_notes": "Launch outperformed baseline"}
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "PATCH"
        assert path == "/v1/decisions/decision_123/outcome"
        assert body == payload
        return 200, {
            "id": "decision_123",
            "actual_outcome": 141000.0,
            "outcome_delta": 13000.0,
            "policy_snapshot_id": "policy-v1",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
            "outcome_recorded_at": "2026-05-24T12:30:00Z",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_outcome, "decision_123", str(request_path), "table")

    assert "Actual outcome:  141000.0" in output
    assert "Outcome delta:   13000.0" in output
    assert "Policy snapshot: policy-v1" in output
    assert "Schema snapshot: schema-v1" in output
    assert "Manifest:        runtime-manifest-v1" in output


def test_cmd_decisions_execute_posts_payload_and_prints_receipt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "decision-execute.json"
    payload = {"webhook_url": "https://hooks.example.test/decision", "timeout_seconds": 15}
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/decisions/decision_123/execute"
        assert body == payload
        return 200, {
            "decision_id": "decision_123",
            "webhook_url": "https://hooks.example.test/decision",
            "execution_status": "delivered",
            "response_code": 202,
            "executed_at": "2026-05-24T12:05:00Z",
            "policy_snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
            "schema_snapshot_id": "schema-v1",
            "manifest_version": "runtime-manifest-v1",
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_execute, "decision_123", str(request_path), "table")

    assert "Decision ID:     decision_123" in output
    assert "Status:          delivered" in output
    assert "Response code:   202" in output
    assert "Policy snapshot: execution-policy-v1-r2:abcd1234abcd1234" in output
    assert "Schema snapshot: schema-v1" in output
    assert "Manifest:        runtime-manifest-v1" in output


def test_cmd_decisions_delete_uses_delete_and_prints_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "DELETE"
        assert path == "/v1/decisions/decision_123"
        assert body is None
        return 204, {}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decisions_delete, "decision_123", "table")

    assert "Decision deleted: decision_123" in output


def test_cmd_decision_score_posts_request_and_prints_score_summary(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "score.json"
    payload = {
        "request": {
            "mode": "expert",
            "simulation": {
                "variables": [
                    {"name": "outcome", "distribution": "fixed", "params": {"value": 100}}
                ],
                "objective_function": "outcome",
            },
        },
        "scoring_weights": {"expected_value": 0.7, "downside_risk": 0.3},
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/score"
        assert body == payload
        return 200, {
            "envelope": {
                "recommended_action": "expand_capacity",
                "expected_value": 125000.0,
                "probability_of_loss": 0.12,
            },
            "score": 0.87,
            "score_breakdown": {
                "expected_value_component": 0.61,
                "downside_risk_component": 0.26,
            },
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decision_score, str(request_path), "table")

    assert "Recommended:    expand_capacity" in output
    assert "Score:          0.87" in output
    assert "Expected value: 125000.0" in output
    assert "Probability of loss: 0.12" in output


def test_cmd_decision_batch_posts_request_and_prints_batch_summary(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "batch.json"
    payload = {
        "items": [
            {
                "mode": "expert",
                "simulation": {
                    "variables": [
                        {"name": "outcome", "distribution": "fixed", "params": {"value": 100}}
                    ],
                    "objective_function": "outcome",
                },
            },
            {
                "mode": "expert",
                "simulation": {
                    "variables": [
                        {"name": "outcome", "distribution": "fixed", "params": {"value": 120}}
                    ],
                    "objective_function": "outcome",
                },
            },
        ]
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/batch"
        assert body == payload
        return 200, {
            "total": 2,
            "succeeded": 1,
            "failed": 1,
            "results": [
                {
                    "index": 0,
                    "success": True,
                    "envelope": {
                        "recommended_action": "proceed",
                        "expected_value": 125000.0,
                    },
                },
                {"index": 1, "success": False, "error": "bad payload"},
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decision_batch, str(request_path), "table")

    assert "Total:          2" in output
    assert "Succeeded:      1" in output
    assert "Failed:         1" in output
    assert "#0 success action=proceed expected_value=125000.0" in output
    assert "#1 failed error=bad payload" in output


def test_cmd_decision_compare_posts_request_and_prints_compare_summary(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "compare.json"
    payload = {
        "scenarios": [
            {
                "name": "base",
                "request": {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {"name": "outcome", "distribution": "fixed", "params": {"value": 100}}
                        ],
                        "objective_function": "outcome",
                    },
                },
            },
            {
                "name": "stretch",
                "request": {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {"name": "outcome", "distribution": "fixed", "params": {"value": 120}}
                        ],
                        "objective_function": "outcome",
                    },
                },
            },
        ]
    }
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/compare"
        assert body == payload
        return 200, {
            "winner": "stretch",
            "margin": {
                "expected_value_delta": 20.0,
                "probability_of_loss_delta": -0.05,
                "score_delta": 0.11,
            },
            "scenarios": [
                {
                    "name": "base",
                    "envelope": {
                        "recommended_action": "hold",
                        "expected_value": 100.0,
                        "probability_of_loss": 0.2,
                    },
                    "delta_vs_best": {"score_delta": -0.11},
                },
                {
                    "name": "stretch",
                    "envelope": {
                        "recommended_action": "proceed",
                        "expected_value": 120.0,
                        "probability_of_loss": 0.15,
                    },
                    "delta_vs_best": {"score_delta": 0.0},
                },
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_decision_compare, str(request_path), "table")

    assert "Winner:         stretch" in output
    assert "Margin:         ev=20.0 pol=-0.05 score=0.11" in output
    assert "base: action=hold expected_value=100.0 pol=0.2 delta_score=-0.11" in output
    assert "stretch: action=proceed expected_value=120.0 pol=0.15 delta_score=0.0" in output


@pytest.mark.parametrize(
    ("func_name", "path", "payload", "response", "expected_lines"),
    [
        (
            "cmd_product_decision",
            "/v1/decision",
            {"inputs": [{"name": "revenue", "value": 125000.0}]},
            {
                "decision_id": "decision_product_123",
                "action": "proceed",
                "confidence": 0.82,
                "expected_outcome": 125000.0,
                "probability_of_loss": 0.14,
                "reasoning": "Expected value remains attractive within risk tolerance.",
            },
            ["Decision ID:       decision_product_123", "Action:            proceed"],
        ),
        (
            "cmd_product_agent_run",
            "/v1/agent/run",
            {"task": "Summarize launch blockers"},
            {
                "run_id": "agent_product_123",
                "status": "completed",
                "tools_used": ["search", "simulate"],
                "steps": [{"step": 1, "action": "search"}],
                "latency_ms": 88.4,
            },
            ["Run ID:            agent_product_123", "Tools used:        search, simulate"],
        ),
        (
            "cmd_product_optimize",
            "/v1/optimize",
            {"objective": "maximize_margin", "variables": [{"name": "price", "min": 95, "max": 140}]},
            {
                "optimization_id": "opt_123",
                "status": "completed",
                "objective_value": 183000.0,
                "optimal_values": {"price": 119.0},
                "iterations_run": 1200,
            },
            ["Optimization ID:   opt_123", "Objective value:   183000.0"],
        ),
        (
            "cmd_product_retrieve",
            "/v1/retrieve",
            {"query": "launch checklist", "documents": [{"content": "Launch checklist"}]},
            {
                "retrieval_id": "ret_123",
                "query": "launch checklist",
                "results": [{"rank": 1, "document_id": "doc_1", "relevance_score": 0.93}],
            },
            ["Retrieval ID:      ret_123", "#1 doc_1 score=0.93"],
        ),
        (
            "cmd_product_forecast",
            "/v1/forecast",
            {"metric": "monthly_revenue", "history": [118000.0, 121000.0, 125000.0]},
            {
                "forecast_id": "forecast_123",
                "metric": "monthly_revenue",
                "forecast_mean": 149000.0,
                "total_change_pct": 19.2,
                "periods": [{"period": 1, "forecast": 129000.0}],
            },
            ["Forecast ID:       forecast_123", "Total change pct:  19.2"],
        ),
    ],
)
def test_product_commands_post_request_and_print_summary(
    monkeypatch,
    tmp_path,
    func_name: str,
    path: str,
    payload: dict[str, object],
    response: dict[str, object],
    expected_lines: list[str],
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / f"{func_name}.json"
    request_path.write_text(json.dumps(payload))

    def _fake_api_request(method: str, requested_path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert requested_path == path
        assert body == payload
        return 200, response

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(getattr(cli, func_name), str(request_path), "table")

    for line in expected_lines:
        assert line in output


def test_main_dispatches_decision_plan(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_decision_plan(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_decision_plan", _fake_cmd_decision_plan)
    monkeypatch.setattr(cli.sys, "argv", ["de", "decision", "plan", "plan.json"])

    cli.main()

    assert called == {"request_path": "plan.json", "format": "table"}


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "decisions", "log", "decision.json", "--format", "json"],
            "cmd_decisions_log",
            {"request_path": "decision.json", "format": "json"},
        ),
        (
            ["de", "decisions", "list", "--limit", "20", "--with-outcome-only"],
            "cmd_decisions_list",
            {
                "page": 1,
                "limit": 20,
                "page_size": None,
                "with_outcome_only": True,
                "format": "table",
            },
        ),
        (
            ["de", "decisions", "get", "decision_123"],
            "cmd_decisions_get",
            {"decision_id": "decision_123", "format": "table"},
        ),
        (
            ["de", "decisions", "outcome", "decision_123", "outcome.json", "--format", "json"],
            "cmd_decisions_outcome",
            {
                "decision_id": "decision_123",
                "request_path": "outcome.json",
                "format": "json",
            },
        ),
        (
            ["de", "decisions", "execute", "decision_123", "execute.json"],
            "cmd_decisions_execute",
            {
                "decision_id": "decision_123",
                "request_path": "execute.json",
                "format": "table",
            },
        ),
        (
            ["de", "decisions", "delete", "decision_123", "--format", "json"],
            "cmd_decisions_delete",
            {"decision_id": "decision_123", "format": "json"},
        ),
    ],
)
def test_main_dispatches_decision_memory_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_decisions_list":
        def _fake_cmd(
            *,
            page: int = 1,
            limit: int | None = None,
            page_size: int | None = None,
            with_outcome_only: bool = False,
            format: str = "table",
        ) -> None:
            called["page"] = page
            called["limit"] = limit
            called["page_size"] = page_size
            called["with_outcome_only"] = with_outcome_only
            called["format"] = format
    elif handler_name in {"cmd_decisions_get", "cmd_decisions_delete"}:
        def _fake_cmd(decision_id: str, format: str = "table") -> None:
            called["decision_id"] = decision_id
            called["format"] = format
    elif handler_name in {"cmd_decisions_outcome", "cmd_decisions_execute"}:
        def _fake_cmd(decision_id: str, request_path: str, format: str = "table") -> None:
            called["decision_id"] = decision_id
            called["request_path"] = request_path
            called["format"] = format
    else:
        def _fake_cmd(request_path: str, format: str = "table") -> None:
            called["request_path"] = request_path
            called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "decision", "score", "score.json", "--format", "json"],
            "cmd_decision_score",
            {"request_path": "score.json", "format": "json"},
        ),
        (
            ["de", "decision", "batch", "batch.json"],
            "cmd_decision_batch",
            {"request_path": "batch.json", "format": "table"},
        ),
        (
            ["de", "decision", "compare", "compare.json"],
            "cmd_decision_compare",
            {"request_path": "compare.json", "format": "table"},
        ),
    ],
)
def test_main_dispatches_decision_runtime_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "product", "decision", "decision.json", "--format", "json"],
            "cmd_product_decision",
            {"request_path": "decision.json", "format": "json"},
        ),
        (
            ["de", "product", "agent-run", "agent-run.json"],
            "cmd_product_agent_run",
            {"request_path": "agent-run.json", "format": "table"},
        ),
        (
            ["de", "product", "optimize", "optimize.json"],
            "cmd_product_optimize",
            {"request_path": "optimize.json", "format": "table"},
        ),
        (
            ["de", "product", "retrieve", "retrieve.json"],
            "cmd_product_retrieve",
            {"request_path": "retrieve.json", "format": "table"},
        ),
        (
            ["de", "product", "forecast", "forecast.json", "--format", "json"],
            "cmd_product_forecast",
            {"request_path": "forecast.json", "format": "json"},
        ),
    ],
)
def test_main_dispatches_product_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    def _fake_cmd(request_path: str, format: str = "table") -> None:
        called["request_path"] = request_path
        called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


