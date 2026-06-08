from __future__ import annotations

import importlib
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")
DecisionEnvelopeOutput = algenta.DecisionEnvelopeOutput
RepositoryApplyOutput = algenta.RepositoryApplyOutput
RepositoryIntelligenceCapabilitiesOutput = algenta.RepositoryIntelligenceCapabilitiesOutput
RepositoryDecisionPlanRevisionOutput = algenta.RepositoryDecisionPlanRevisionOutput
RepositoryGraphQueryOutput = algenta.RepositoryGraphQueryOutput
RepositorySnapshotOutput = algenta.RepositorySnapshotOutput
RepositoryTriageOutput = algenta.RepositoryTriageOutput
Runtime = algenta.Runtime
RuntimeValidationError = algenta.RuntimeValidationError


def _artifact_payload(kind: str, artifact_id: str) -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "artifact_kind": kind,
        "content_hash": f"sha256-{artifact_id}",
        "storage_path": f"/tmp/{artifact_id}.parquet",
        "schema_revision": "runtime-internal-contracts-v1",
        "created_at": "2026-05-29T12:00:00Z",
    }


def _decision_plan_payload() -> dict[str, object]:
    return {
        "recommended_action": "Add null guard in handle_request",
        "confidence": 0.91,
        "expected_value": 82.5,
        "risk": {
            "p5": -12.0,
            "p95": 110.0,
            "probability_of_loss": 0.08,
            "var_95": 12.0,
        },
        "options": [
            {
                "name": "Add null guard in handle_request",
                "rank": 1,
                "expected_value": 82.5,
                "risk": {
                    "p5": -12.0,
                    "p95": 110.0,
                    "probability_of_loss": 0.08,
                    "var_95": 12.0,
                },
                "score": 0.91,
            }
        ],
        "rationale": "Bounded repository evidence isolates the fault to src/service.py.",
        "integrity": {
            "request_hash": "req_hash_123",
            "result_hash": "res_hash_123",
        },
        "calibration": None,
        "repository_analysis": {
            "root_cause": "handle_request dereferences user.name without a null guard.",
            "planner_model_id": "repo-fix-model",
            "planner_execution_mode": "provider_backed_chat",
            "planner_provider_backend": "openai",
            "candidate_fixes": ["Add a null guard before returning user.name."],
            "impacted_services": ["src/service.py"],
            "impacted_symbols": ["handle_request"],
            "likely_failing_tests": ["tests/test_service.py"],
            "rollback_complexity": "low",
            "blast_radius": "low",
            "workspace_evidence_refs": ["evidence_bundle_123"],
            "generated_patch_ref": "patch_123",
            "patch_impact_report_ref": "patch_impact_123",
            "token_reduction_metrics": {
                "raw_repo_token_estimate": 1200,
                "evidence_bundle_token_count": 180,
                "reduction_ratio": 6.67,
            },
        },
    }


def _simulation_payload() -> dict[str, object]:
    return {
        "run_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "status": "completed",
        "engine_version": "2026.05.0",
        "recommended_action": "apply_patch",
        "confidence": 0.93,
        "rationale": "Patch simulation satisfies current execution policy thresholds.",
        "metrics": {
            "expected_value": 84.0,
            "median": 82.0,
            "std_deviation": 9.0,
            "variance": 81.0,
            "probability_of_loss": 0.08,
            "var_95": 12.0,
            "cvar_95": 15.0,
        },
        "percentiles": {
            "p5": -12.0,
            "p25": 60.0,
            "p50": 82.0,
            "p75": 95.0,
            "p95": 110.0,
        },
        "scenarios_run": 5000,
        "execution_ms": 11,
        "metadata": {
            "mode": "expert",
            "seed": 42,
            "billing_units": 1,
            "engine_version": "2026.05.0",
        },
        "validated_inputs": {"simulation_id": "simulation_123"},
        "score_breakdown": {"apply_gate": {"passed": True, "policy_snapshot_id": "policy_123"}},
        "decision_plan": _decision_plan_payload(),
    }


def _graph_query_payload() -> dict[str, object]:
    return {
        "repository_id": "repo_123",
        "snapshot_id": "snapshot_123",
        "created_at": "2026-05-29T12:08:00Z",
        "seed_file_paths": ["src/service.py"],
        "seed_symbols": ["handle_request"],
        "direct_dependencies": ["src/helpers.py"],
        "direct_dependents": ["tests/test_service.py"],
        "impacted_files": ["src/service.py", "tests/test_service.py"],
        "impacted_symbols": ["handle_request"],
        "graph_nodes": [
            {
                "file_path": "src/service.py",
                "depth": 0,
                "is_seed": True,
                "inbound_count": 1,
                "outbound_count": 2,
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


def _capabilities_payload() -> dict[str, object]:
    return {
        "supported_languages": ["python", "typescript", "coq"],
        "support_progress": {
            "supported_real_language_count": 3,
            "ranked_target_language_count": 200,
            "progress_fraction": 3 / 200,
            "progress_label": "3 / 200",
        },
    }


def test_runtime_api_mode_repository_methods_return_typed_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")
    repository_id = "repo_123"
    calls: list[tuple[str, str | None, dict[str, Any] | None]] = []

    class _FakeClient:
        def get_repository_intelligence_capabilities(self) -> dict[str, object]:
            calls.append(("get_repository_intelligence_capabilities", None, None))
            return _capabilities_payload()

        def create_repository_snapshot(
            self,
            received_repository_id: str,
            request: dict[str, Any],
        ) -> dict[str, object]:
            calls.append(("create_repository_snapshot", received_repository_id, request))
            return {
                "repository_id": received_repository_id,
                "snapshot_id": "snapshot_123",
                "connector_type": "local_repo",
                "ref": "main",
                "resolved_revision": "abc123",
                "content_hash": "repo_hash_123",
                "status": "created",
                "created_at": "2026-05-29T12:00:00Z",
                "file_count": 14,
                "language_counts": {"python": 10, "markdown": 4},
                "raw_repo_token_estimate": 1200,
                "repository_snapshot_artifact": _artifact_payload(
                    "RepositorySnapshot",
                    "artifact_snapshot_123",
                ),
                "repository_graph_artifact": _artifact_payload(
                    "RepositoryGraph",
                    "artifact_graph_123",
                ),
                "symbol_graph_artifact": _artifact_payload("SymbolGraph", "artifact_symbol_123"),
                "dependency_graph_artifact": _artifact_payload(
                    "DependencyGraph",
                    "artifact_dependency_123",
                ),
            }

        def get_repository_snapshot(
            self,
            received_repository_id: str,
            snapshot_id: str,
        ) -> dict[str, object]:
            calls.append(
                (
                    "get_repository_snapshot",
                    received_repository_id,
                    {"snapshot_id": snapshot_id},
                )
            )
            return {
                "repository_id": received_repository_id,
                "snapshot_id": snapshot_id,
                "connector_type": "local_repo",
                "ref": "main",
                "resolved_revision": "abc123",
                "content_hash": "repo_hash_123",
                "status": "existing",
                "created_at": "2026-05-29T12:00:00Z",
                "file_count": 14,
                "language_counts": {"python": 10, "markdown": 4},
                "raw_repo_token_estimate": 1200,
                "repository_snapshot_artifact": _artifact_payload(
                    "RepositorySnapshot",
                    "artifact_snapshot_123",
                ),
                "repository_graph_artifact": _artifact_payload(
                    "RepositoryGraph",
                    "artifact_graph_123",
                ),
                "symbol_graph_artifact": _artifact_payload("SymbolGraph", "artifact_symbol_123"),
                "dependency_graph_artifact": _artifact_payload(
                    "DependencyGraph",
                    "artifact_dependency_123",
                ),
            }

        def triage_repository(
            self,
            received_repository_id: str,
            request: dict[str, Any],
        ) -> dict[str, object]:
            calls.append(("triage_repository", received_repository_id, request))
            return {
                "repository_id": received_repository_id,
                "snapshot_id": request["snapshot_id"],
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
                "created_at": "2026-05-29T12:05:00Z",
                "suspect_files": ["src/service.py"],
                "suspect_symbols": ["handle_request"],
                "raw_repo_token_estimate": 1200,
                "evidence_bundle_token_count": 180,
                "reduction_ratio": 6.67,
                "evidence_items": [
                    {
                        "evidence_id": "evidence_123",
                        "rank": 1,
                        "source_type": "diagnostic",
                        "source_ref": "src/service.py:14",
                        "file_path": "src/service.py",
                        "symbol_name": "handle_request",
                        "summary": "Null dereference when user is absent.",
                        "snippet": "return user.name",
                        "token_count": 24,
                        "score": 0.98,
                    }
                ],
                "workspace_evidence_bundle_artifact": _artifact_payload(
                    "WorkspaceEvidenceBundle",
                    "artifact_evidence_123",
                ),
            }

        def create_repository_decision_plan(
            self,
            received_repository_id: str,
            request: dict[str, Any],
        ) -> dict[str, object]:
            calls.append(("create_repository_decision_plan", received_repository_id, request))
            return {
                "repository_id": received_repository_id,
                "snapshot_id": request["snapshot_id"],
                "decision_plan_id": "decision_plan_123",
                "created_at": "2026-05-29T12:10:00Z",
                "decision_plan": _decision_plan_payload(),
            }

        def query_repository_graph(
            self,
            received_repository_id: str,
            request: dict[str, Any],
        ) -> dict[str, object]:
            calls.append(("query_repository_graph", received_repository_id, request))
            return _graph_query_payload()

        def simulate_repository(
            self,
            received_repository_id: str,
            request: dict[str, Any],
        ) -> dict[str, object]:
            calls.append(("simulate_repository", received_repository_id, request))
            return _simulation_payload()

        def apply_repository(
            self,
            received_repository_id: str,
            request: dict[str, Any],
        ) -> dict[str, object]:
            calls.append(("apply_repository", received_repository_id, request))
            return {
                "repository_id": received_repository_id,
                "snapshot_id": request["snapshot_id"],
                "decision_plan_id": request["decision_plan_id"],
                "simulation_id": request["simulation_id"],
                "mode": request["mode"],
                "applied": False,
                "created_at": "2026-05-29T12:15:00Z",
                "patch": "--- a/src/service.py\n+++ b/src/service.py\n@@\n-return user.name\n+return user.name if user else \"anonymous\"\n",
                "apply_gate": {"passed": True, "policy_snapshot_id": "policy_123"},
                "validation_summary": {"patch_files": ["src/service.py"]},
            }

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    capabilities = runtime.get_repository_intelligence_capabilities()
    snapshot = runtime.create_repository_snapshot(repository_id, {"ref": "main"})
    fetched_snapshot = runtime.get_repository_snapshot(repository_id, "snapshot_123")
    triage = runtime.triage_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "signals": {"issue_text": "Regression after latest deploy."},
        },
    )
    plan_revision = runtime.create_repository_decision_plan(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "workspace_evidence_bundle_ref": "evidence_bundle_123",
        },
    )
    graph = runtime.query_repository_graph(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "file_path": "src/service.py",
            "direction": "both",
        },
    )
    simulation = runtime.simulate_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
            "runs": 5000,
            "seed": 42,
        },
    )
    applied = runtime.apply_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
            "simulation_id": "simulation_123",
            "mode": "patch_only",
        },
    )

    assert isinstance(capabilities, RepositoryIntelligenceCapabilitiesOutput)
    assert isinstance(snapshot, RepositorySnapshotOutput)
    assert isinstance(fetched_snapshot, RepositorySnapshotOutput)
    assert isinstance(triage, RepositoryTriageOutput)
    assert isinstance(plan_revision, RepositoryDecisionPlanRevisionOutput)
    assert isinstance(graph, RepositoryGraphQueryOutput)
    assert isinstance(simulation, DecisionEnvelopeOutput)
    assert isinstance(applied, RepositoryApplyOutput)

    assert capabilities.supported_languages == ["python", "typescript", "coq"]
    assert capabilities.support_progress.progress_label == "3 / 200"
    assert snapshot.repository_snapshot_artifact.artifact_kind == "RepositorySnapshot"
    assert fetched_snapshot.status == "existing"
    assert triage.workspace_evidence_bundle_artifact.artifact_kind == "WorkspaceEvidenceBundle"
    assert triage.evidence_items[0].symbol_name == "handle_request"
    assert plan_revision.decision_plan.repository_analysis is not None
    assert plan_revision.decision_plan.repository_analysis.planner_model_id == "repo-fix-model"
    assert (
        plan_revision.decision_plan.repository_analysis.planner_execution_mode
        == "provider_backed_chat"
    )
    assert (
        plan_revision.decision_plan.repository_analysis.patch_impact_report_ref
        == "patch_impact_123"
    )
    assert graph.top_change_risk_files[0].top_symbol == "handle_request"
    assert graph.graph_nodes[0].parent_child_symbols == ["handle_request -> guard_user"]
    assert simulation.decision_plan is not None
    assert simulation.decision_plan.repository_analysis is not None
    assert simulation.decision_plan.repository_analysis.planner_provider_backend == "openai"
    assert simulation.decision_plan.repository_analysis.generated_patch_ref == "patch_123"
    assert simulation.score_breakdown == {
        "apply_gate": {"passed": True, "policy_snapshot_id": "policy_123"}
    }
    assert applied.validation_summary["patch_files"] == ["src/service.py"]

    assert calls == [
        ("get_repository_intelligence_capabilities", None, None),
        ("create_repository_snapshot", repository_id, {"ref": "main"}),
        ("get_repository_snapshot", repository_id, {"snapshot_id": "snapshot_123"}),
        (
            "triage_repository",
            repository_id,
            {
                "snapshot_id": "snapshot_123",
                "signals": {"issue_text": "Regression after latest deploy."},
            },
        ),
        (
            "create_repository_decision_plan",
            repository_id,
            {
                "snapshot_id": "snapshot_123",
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
            },
        ),
        (
            "query_repository_graph",
            repository_id,
            {
                "snapshot_id": "snapshot_123",
                "file_path": "src/service.py",
                "direction": "both",
            },
        ),
        (
            "simulate_repository",
            repository_id,
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "runs": 5000,
                "seed": 42,
            },
        ),
        (
            "apply_repository",
            repository_id,
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "patch_only",
            },
        ),
    ]


def test_runtime_api_mode_simulate_repository_rejects_invalid_nested_repository_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")

    class _FakeClient:
        def simulate_repository(
            self,
            repository_id: str,
            request: dict[str, Any],
        ) -> dict[str, object]:
            del repository_id, request
            payload = _simulation_payload()
            decision_plan = payload["decision_plan"]
            assert isinstance(decision_plan, dict)
            repository_analysis = decision_plan["repository_analysis"]
            assert isinstance(repository_analysis, dict)
            token_metrics = repository_analysis["token_reduction_metrics"]
            assert isinstance(token_metrics, dict)
            token_metrics["reduction_ratio"] = "not-a-number"
            return payload

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc_info:
        runtime.simulate_repository(
            "repo_123",
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
            },
        )

    assert exc_info.value.code == "invalid_runtime_api_payload"
    assert exc_info.value.validation_errors[0]["path"] == (
        "repository_analysis.token_reduction_metrics.reduction_ratio"
    )


def test_algenta_root_exports_repository_runtime_models() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "algenta" or module_name.startswith("algenta.")
    }
    for module_name in list(sys.modules):
        if module_name == "algenta" or module_name.startswith("algenta."):
            sys.modules.pop(module_name, None)

    try:
        root = importlib.import_module("algenta")

        assert "algenta.runtime_model_repository_intelligence" not in sys.modules
        assert "algenta.runtime_model_decision_envelope" not in sys.modules

        assert root.RepositorySnapshotOutput.__name__ == "RepositorySnapshotOutput"
        assert root.RepositoryApplyOutput.__name__ == "RepositoryApplyOutput"
        assert root.RepositoryGraphQueryOutput.__name__ == "RepositoryGraphQueryOutput"
        assert root.DecisionEnvelopeOutput.__name__ == "DecisionEnvelopeOutput"
        assert root.RepositoryAnalysisOutput.__name__ == "RepositoryAnalysisOutput"

        assert "algenta.runtime_model_repository_intelligence" in sys.modules
        assert "algenta.runtime_model_decision_envelope" in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "algenta" or module_name.startswith("algenta."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
