from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

import apps.cli.main as cli
import apps.cli.main.__main__ as cli_module_entry
import apps.cli.support as cli_support


def _capture_stdout(func, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        func(*args, **kwargs)
    return buffer.getvalue()


def test_cli_facade_keeps_support_request_bindings() -> None:
    assert cli.api_request is cli_support.api_request
    assert cli.api_stream_request is cli_support.api_stream_request


def test_cli_package_entrypoint_exports_facade_main() -> None:
    assert cli_module_entry.main is cli.main


def test_cmd_repositories_snapshot_posts_request_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "snapshot.json"
    request_path.write_text(json.dumps({"ref": "main"}), encoding="utf-8")

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/repositories/repo_123/snapshots"
        assert body == {"ref": "main"}
        return 200, {
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "status": "created",
            "resolved_revision": "abc123",
            "file_count": 2,
            "raw_repo_token_estimate": 1200,
            "language_counts": {"python": 2},
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_repositories_snapshot, "repo_123", str(request_path), "table")

    assert "Snapshot ID:     snapshot_123" in output
    assert "Status:          created" in output
    assert "Files:           2" in output
    assert "Raw tokens:      1200" in output


def test_cmd_repositories_capabilities_gets_global_surface_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert path == "/v1/repositories/capabilities"
        assert body is None
        return 200, {
            "supported_languages": ["python", "typescript", "coq"],
            "support_progress": {
                "supported_real_language_count": 3,
                "ranked_target_language_count": 200,
                "progress_fraction": 3 / 200,
                "progress_label": "3 / 200",
            },
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_repositories_capabilities, "table")

    assert "Supported:       3" in output
    assert "Progress:        3 / 200" in output
    assert "Languages:       python, typescript, coq" in output


def test_cmd_repositories_decision_plan_posts_request_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "decision-plan.json"
    request_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot_123",
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
            }
        ),
        encoding="utf-8",
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/repositories/repo_123/decision-plans"
        assert body == {
            "snapshot_id": "snapshot_123",
            "workspace_evidence_bundle_ref": "evidence_bundle_123",
        }
        return 200, {
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
            "decision_plan": {
                "recommended_action": "Add null guard in handle_request",
                "confidence": 0.91,
                "repository_analysis": {
                    "planner_model_id": "repo-fix-model",
                    "planner_execution_mode": "provider_backed_chat",
                    "planner_provider_backend": "openai",
                    "generated_patch_ref": "patch_123",
                    "patch_impact_report_ref": "patch_impact_123",
                    "root_cause": "handle_request dereferences user.name without a null guard.",
                    "candidate_fixes": ["Add a null guard before returning user.name."],
                },
            },
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_repositories_decision_plan,
        "repo_123",
        str(request_path),
        "table",
    )

    assert "Decision plan:   decision_plan_123" in output
    assert "Action:          Add null guard in handle_request" in output
    assert "Planner model:   repo-fix-model" in output
    assert "Planner mode:    provider_backed_chat" in output
    assert "Planner backend: openai" in output
    assert "Patch impact:    patch_impact_123" in output
    assert "Root cause:      handle_request dereferences user.name without a null guard." in output


def test_cmd_repositories_graph_query_posts_request_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "graph-query.json"
    request_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot_123",
                "file_path": "src/service.py",
                "direction": "both",
                "max_depth": 2,
            }
        ),
        encoding="utf-8",
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/repositories/repo_123/graph-query"
        assert body == {
            "snapshot_id": "snapshot_123",
            "file_path": "src/service.py",
            "direction": "both",
            "max_depth": 2,
        }
        return 200, {
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "created_at": "2026-05-29T12:10:00Z",
            "seed_file_paths": ["src/service.py"],
            "seed_symbols": ["handle_request"],
            "direct_dependencies": ["src/helpers.py"],
            "direct_dependents": ["tests/test_service.py"],
            "impacted_files": ["src/service.py", "tests/test_service.py"],
            "impacted_symbols": ["handle_request", "test_handle_request"],
            "graph_nodes": [
                {
                    "file_path": "src/service.py",
                    "depth": 0,
                    "is_seed": True,
                    "inbound_count": 1,
                    "outbound_count": 1,
                    "risk_score": 72.5,
                    "contained_symbols": ["handle_request"],
                    "parent_child_symbols": ["handle_request -> guard_user"],
                }
            ],
            "graph_edges": [
                {
                    "source_file": "tests/test_service.py",
                    "target_file": "src/service.py",
                    "edge_type": "imports",
                }
            ],
            "top_change_risk_files": [
                {
                    "file_path": "src/service.py",
                    "depth": 0,
                    "relationship": "seed",
                    "risk_score": 72.5,
                    "top_symbol": "handle_request",
                }
            ],
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_repositories_graph_query, "repo_123", str(request_path), "table")

    assert "Snapshot ID:       snapshot_123" in output
    assert "Seed files:        1" in output
    assert "Direct deps:       1" in output
    assert "Graph nodes:       1" in output
    assert "src/service.py [seed] risk=72.5 symbol=handle_request" in output


def test_cmd_repositories_apply_posts_request_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "apply.json"
    request_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "local_branch",
                "write_permission": True,
            }
        ),
        encoding="utf-8",
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/repositories/repo_123/apply"
        assert body == {
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
            "simulation_id": "simulation_123",
            "mode": "local_branch",
            "write_permission": True,
        }
        return 200, {
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
            "simulation_id": "simulation_123",
            "mode": "local_branch",
            "applied": True,
            "branch_name": "algenta/test-null-guard",
            "commit_sha": "deadbeef",
            "local_checkout_path": "/tmp/repo",
            "pull_request_url": None,
            "apply_gate": {
                "passed": True,
                "policy_snapshot_id": "policy_123",
            },
            "validation_summary": {
                "patch_files": ["src/service.py"],
            },
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_repositories_apply, "repo_123", str(request_path), "table")

    assert "Mode:            local_branch" in output
    assert "Applied:         True" in output
    assert "Gate passed:     True" in output
    assert "Policy snapshot: policy_123" in output
    assert "Branch:          algenta/test-null-guard" in output
    assert "Commit:          deadbeef" in output
    assert "Checkout path:   /tmp/repo" in output
    assert "Patch files:     1" in output
    assert "  src/service.py" in output


def test_cmd_repositories_pipeline_prints_canonical_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "pipeline.json"
    request_path.write_text(
        json.dumps({"signals": {"issue_text": "null dereference"}}),
        encoding="utf-8",
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/repositories/repo_123/pipeline"
        assert body == {"signals": {"issue_text": "null dereference"}}
        return 200, {
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "snapshot": {"snapshot_id": "snapshot_123", "ref": "main"},
            "triage": {"workspace_evidence_bundle_ref": "bundle_123"},
            "decision_plan": {
                "decision_plan_id": "decision_plan_123",
                "decision_plan": {
                    "repository_analysis": {
                        "planner_model_id": "repository.deterministic_local_v1",
                        "planner_execution_mode": "deterministic_local",
                        "planner_provider_backend": None,
                    }
                },
            },
            "simulation": {
                "run_id": "simulation_123",
                "recommended_action": "apply_patch",
                "score_breakdown": {"apply_gate": {"passed": True}},
            },
        }

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_repositories_pipeline, "repo_123", str(request_path), "table")

    assert "Repository Channel Envelope" in output
    assert "Snapshot:        snapshot_123" in output
    assert "Plan:            decision_plan_123" in output
    assert "Simulation:      simulation_123" in output
    assert "Gate decision:   apply_allowed" in output


def test_cmd_repositories_simulate_patch_prints_canonical_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "simulate-patch.json"
    request_path.write_text(
        json.dumps({"snapshot_id": "snapshot_123", "patch_diff": "diff --git a/x b/x"}),
        encoding="utf-8",
    )

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/repositories/repo_123/simulate-patch"
        assert body == {"snapshot_id": "snapshot_123", "patch_diff": "diff --git a/x b/x"}
        return 200, {"run_id": "simulation_patch_123", "recommended_action": "apply_patch"}

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(
        cli.cmd_repositories_simulate_patch,
        "repo_123",
        str(request_path),
        "table",
    )

    assert "Simulation:      simulation_patch_123" in output
    assert "Gate decision:   apply_allowed" in output


def test_cmd_repositories_fix_runs_pipeline_then_apply(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "fix.json"
    request_path.write_text(
        json.dumps({"pipeline": {"signals": {"issue_text": "null dereference"}}}),
        encoding="utf-8",
    )
    calls: list[tuple[str, str, object]] = []

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        calls.append((method, path, body))
        if (method, path) == ("POST", "/v1/repositories/repo_123/pipeline"):
            return 200, {
                "repository_id": "repo_123",
                "snapshot_id": "snapshot_123",
                "snapshot": {"snapshot_id": "snapshot_123"},
                "triage": {"workspace_evidence_bundle_ref": "bundle_123"},
                "decision_plan": {"decision_plan_id": "decision_plan_123", "decision_plan": {}},
                "simulation": {
                    "run_id": "simulation_123",
                    "recommended_action": "apply_patch",
                    "score_breakdown": {"apply_gate": {"passed": True}},
                },
            }
        if (method, path) == ("POST", "/v1/repositories/repo_123/apply"):
            return 200, {
                "applied": True,
                "simulation_id": "simulation_123",
                "local_checkout_path": "/tmp/repo",
                "patch": "diff --git a/src/service.py b/src/service.py",
                "apply_gate": {"passed": True},
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    output = _capture_stdout(cli.cmd_repositories_fix, "repo_123", str(request_path), "table")

    assert "Apply:           simulation_123" in output
    assert "Gate decision:   apply_allowed" in output
    assert calls == [
        ("POST", "/v1/repositories/repo_123/pipeline", {"signals": {"issue_text": "null dereference"}}),
        (
            "POST",
            "/v1/repositories/repo_123/apply",
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "patch_only",
            },
        ),
    ]


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "repositories", "capabilities", "--format", "json"],
            "cmd_repositories_capabilities",
            ("json",),
        ),
        (
            ["de", "repositories", "snapshot", "repo_123", "snapshot.json", "--format", "json"],
            "cmd_repositories_snapshot",
            ("repo_123", "snapshot.json", "json"),
        ),
        (
            ["de", "repositories", "get-snapshot", "repo_123", "snapshot_123"],
            "cmd_repositories_get_snapshot",
            ("repo_123", "snapshot_123", "table"),
        ),
        (
            ["de", "repositories", "decision-plan", "repo_123", "decision-plan.json"],
            "cmd_repositories_decision_plan",
            ("repo_123", "decision-plan.json", "table"),
        ),
        (
            ["de", "repositories", "graph-query", "repo_123", "graph-query.json"],
            "cmd_repositories_graph_query",
            ("repo_123", "graph-query.json", "table"),
        ),
        (
            ["de", "repositories", "pipeline", "repo_123", "pipeline.json"],
            "cmd_repositories_pipeline",
            ("repo_123", "pipeline.json", "table"),
        ),
        (
            ["de", "repositories", "simulate-patch", "repo_123", "simulate-patch.json"],
            "cmd_repositories_simulate_patch",
            ("repo_123", "simulate-patch.json", "table"),
        ),
        (
            ["de", "repositories", "fix", "repo_123", "fix.json"],
            "cmd_repositories_fix",
            ("repo_123", "fix.json", "table"),
        ),
        (
            ["de", "repositories", "apply", "repo_123", "apply.json"],
            "cmd_repositories_apply",
            ("repo_123", "apply.json", "table"),
        ),
    ],
)
def test_main_dispatches_repository_commands(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    handler_name: str,
    expected: tuple[str, ...],
) -> None:
    called: dict[str, tuple[str, ...]] = {}

    def _fake_handler(*handler_args: str) -> None:
        called["args"] = handler_args

    monkeypatch.setattr(cli, handler_name, _fake_handler)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called["args"] == expected
