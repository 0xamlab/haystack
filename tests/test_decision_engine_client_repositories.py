from __future__ import annotations

import importlib
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

from apps.api_server.services.repository_language_priority import (
    DEFAULT_REAL_LANGUAGE_RANK_TARGET,
)

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

decision_engine = importlib.import_module("decision_engine")
AsyncDecisionEngineClient = decision_engine.AsyncDecisionEngineClient
DecisionEngineClient = decision_engine.DecisionEngineClient
DecisionEnvelope = decision_engine.DecisionEnvelope
RepositoryApplyResult = decision_engine.RepositoryApplyResult
RepositoryIntelligenceCapabilitiesResult = decision_engine.RepositoryIntelligenceCapabilitiesResult
RepositoryDecisionPlanRevisionResult = decision_engine.RepositoryDecisionPlanRevisionResult
RepositoryGraphQueryResult = decision_engine.RepositoryGraphQueryResult
RepositorySnapshotResult = decision_engine.RepositorySnapshotResult
RepositoryTriageResult = decision_engine.RepositoryTriageResult


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
        "run_id": str(uuid.UUID("11111111-1111-1111-1111-111111111111")),
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
        "score_breakdown": {"apply_gate": {"passed": True}},
        "decision_plan": _decision_plan_payload(),
    }


def _graph_query_payload(repository_id: str) -> dict[str, object]:
    return {
        "repository_id": repository_id,
        "snapshot_id": "snapshot_123",
        "created_at": "2026-05-29T12:01:30Z",
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
            "ranked_target_language_count": DEFAULT_REAL_LANGUAGE_RANK_TARGET,
            "progress_fraction": 3 / DEFAULT_REAL_LANGUAGE_RANK_TARGET,
            "progress_label": f"3 / {DEFAULT_REAL_LANGUAGE_RANK_TARGET}",
        },
    }


def test_decision_engine_client_repository_methods_return_typed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    repository_id = "repo_123"
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def _fake_request(method: str, path: str, **kwargs: Any) -> dict[str, object]:
        calls.append((method, path, kwargs.get("json")))
        if (method, path) == ("GET", "/v1/repositories/capabilities"):
            return _capabilities_payload()
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/snapshots"):
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "connector_type": "local_repo",
                "ref": "main",
                "resolved_revision": "abc123",
                "content_hash": "content_hash_123",
                "status": "created",
                "created_at": "2026-05-29T12:00:00Z",
                "file_count": 2,
                "language_counts": {"python": 2},
                "raw_repo_token_estimate": 1200,
                "repository_snapshot_artifact": _artifact_payload(
                    "RepositorySnapshot", "artifact_snapshot_123"
                ),
                "repository_graph_artifact": _artifact_payload(
                    "RepositoryGraph", "artifact_graph_123"
                ),
                "symbol_graph_artifact": _artifact_payload(
                    "SymbolGraph", "artifact_symbol_123"
                ),
                "dependency_graph_artifact": _artifact_payload(
                    "DependencyGraph", "artifact_dependency_123"
                ),
            }
        if (method, path) == (
            "GET",
            f"/v1/repositories/{repository_id}/snapshots/snapshot_123",
        ):
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "connector_type": "local_repo",
                "ref": "main",
                "resolved_revision": "abc123",
                "content_hash": "content_hash_123",
                "status": "existing",
                "created_at": "2026-05-29T12:00:00Z",
                "file_count": 2,
                "language_counts": {"python": 2},
                "raw_repo_token_estimate": 1200,
                "repository_snapshot_artifact": _artifact_payload(
                    "RepositorySnapshot", "artifact_snapshot_123"
                ),
                "repository_graph_artifact": _artifact_payload(
                    "RepositoryGraph", "artifact_graph_123"
                ),
                "symbol_graph_artifact": _artifact_payload(
                    "SymbolGraph", "artifact_symbol_123"
                ),
                "dependency_graph_artifact": _artifact_payload(
                    "DependencyGraph", "artifact_dependency_123"
                ),
            }
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/triage"):
            assert kwargs["json"] == {
                "snapshot_id": "snapshot_123",
                "signals": {"issue_text": "null dereference in handle_request"},
            }
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
                "created_at": "2026-05-29T12:01:00Z",
                "suspect_files": ["src/service.py"],
                "suspect_symbols": ["handle_request"],
                "raw_repo_token_estimate": 1200,
                "evidence_bundle_token_count": 180,
                "reduction_ratio": 6.67,
                "evidence_items": [
                    {
                        "evidence_id": "evidence_123",
                        "rank": 1,
                        "source_type": "repository_file",
                        "source_ref": "src/service.py",
                        "file_path": "src/service.py",
                        "symbol_name": "handle_request",
                        "summary": "AttributeError in handle_request",
                        "snippet": "1: def handle_request(user):",
                        "token_count": 42,
                        "score": 12.5,
                    }
                ],
                "workspace_evidence_bundle_artifact": _artifact_payload(
                    "WorkspaceEvidenceBundle", "artifact_evidence_123"
                ),
            }
        if (method, path) == (
            "POST",
            f"/v1/repositories/{repository_id}/decision-plans",
        ):
            assert kwargs["json"] == {
                "snapshot_id": "snapshot_123",
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
            }
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "created_at": "2026-05-29T12:02:00Z",
                "decision_plan": _decision_plan_payload(),
            }
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/graph-query"):
            assert kwargs["json"] == {
                "snapshot_id": "snapshot_123",
                "file_path": "src/service.py",
                "direction": "both",
            }
            return _graph_query_payload(repository_id)
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/simulate"):
            assert kwargs["json"] == {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
            }
            return _simulation_payload()
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/apply"):
            assert kwargs["json"] == {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "patch_only",
            }
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "patch_only",
                "applied": False,
                "created_at": "2026-05-29T12:03:00Z",
                "patch": "--- a/src/service.py\n+++ b/src/service.py\n",
                "apply_gate": {"passed": True},
                "validation_summary": {"patch_files": ["src/service.py"]},
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    capabilities = client.get_repository_intelligence_capabilities()
    snapshot = client.create_repository_snapshot(repository_id, {"ref": "main"})
    fetched = client.get_repository_snapshot(repository_id, "snapshot_123")
    triage = client.triage_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "signals": {"issue_text": "null dereference in handle_request"},
        },
    )
    plan = client.create_repository_decision_plan(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "workspace_evidence_bundle_ref": "evidence_bundle_123",
        },
    )
    graph = client.query_repository_graph(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "file_path": "src/service.py",
            "direction": "both",
        },
    )
    simulation = client.simulate_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
        },
    )
    apply_result = client.apply_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
            "simulation_id": "simulation_123",
            "mode": "patch_only",
        },
    )

    assert isinstance(capabilities, RepositoryIntelligenceCapabilitiesResult)
    assert isinstance(snapshot, RepositorySnapshotResult)
    assert isinstance(fetched, RepositorySnapshotResult)
    assert isinstance(triage, RepositoryTriageResult)
    assert isinstance(plan, RepositoryDecisionPlanRevisionResult)
    assert isinstance(graph, RepositoryGraphQueryResult)
    assert isinstance(simulation, DecisionEnvelope)
    assert isinstance(apply_result, RepositoryApplyResult)
    assert capabilities.supported_languages == ["python", "typescript", "coq"]
    assert capabilities.support_progress.progress_label == f"3 / {DEFAULT_REAL_LANGUAGE_RANK_TARGET}"
    assert triage.workspace_evidence_bundle_artifact.artifact_kind == "WorkspaceEvidenceBundle"
    assert plan.decision_plan.repository_analysis is not None
    assert plan.decision_plan.repository_analysis.planner_model_id == "repo-fix-model"
    assert plan.decision_plan.repository_analysis.planner_execution_mode == "provider_backed_chat"
    assert plan.decision_plan.repository_analysis.patch_impact_report_ref == "patch_impact_123"
    assert graph.seed_file_paths == ["src/service.py"]
    assert graph.top_change_risk_files[0].top_symbol == "handle_request"
    assert simulation.decision_plan is not None
    assert simulation.decision_plan.repository_analysis is not None
    assert simulation.decision_plan.repository_analysis.planner_provider_backend == "openai"
    assert simulation.decision_plan.repository_analysis.generated_patch_ref == "patch_123"
    assert apply_result.validation_summary["patch_files"] == ["src/service.py"]
    assert calls == [
        ("GET", "/v1/repositories/capabilities", None),
        ("POST", f"/v1/repositories/{repository_id}/snapshots", {"ref": "main"}),
        ("GET", f"/v1/repositories/{repository_id}/snapshots/snapshot_123", None),
        (
            "POST",
            f"/v1/repositories/{repository_id}/triage",
            {
                "snapshot_id": "snapshot_123",
                "signals": {"issue_text": "null dereference in handle_request"},
            },
        ),
        (
            "POST",
            f"/v1/repositories/{repository_id}/decision-plans",
            {
                "snapshot_id": "snapshot_123",
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
            },
        ),
        (
            "POST",
            f"/v1/repositories/{repository_id}/graph-query",
            {
                "snapshot_id": "snapshot_123",
                "file_path": "src/service.py",
                "direction": "both",
            },
        ),
        (
            "POST",
            f"/v1/repositories/{repository_id}/simulate",
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
            },
        ),
        (
            "POST",
            f"/v1/repositories/{repository_id}/apply",
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "patch_only",
            },
        ),
    ]


@pytest.mark.anyio
async def test_async_decision_engine_client_repository_methods_return_typed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="http://localhost:8000")
    repository_id = "repo_123"

    async def _fake_request(method: str, path: str, **kwargs: Any) -> dict[str, object]:
        if (method, path) == ("GET", "/v1/repositories/capabilities"):
            return _capabilities_payload()
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/snapshots"):
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "connector_type": "local_repo",
                "ref": None,
                "resolved_revision": "abc123",
                "content_hash": "content_hash_123",
                "status": "created",
                "created_at": "2026-05-29T12:00:00Z",
                "file_count": 2,
                "language_counts": {"python": 2},
                "raw_repo_token_estimate": 1200,
                "repository_snapshot_artifact": _artifact_payload(
                    "RepositorySnapshot", "artifact_snapshot_123"
                ),
                "repository_graph_artifact": _artifact_payload(
                    "RepositoryGraph", "artifact_graph_123"
                ),
                "symbol_graph_artifact": _artifact_payload(
                    "SymbolGraph", "artifact_symbol_123"
                ),
                "dependency_graph_artifact": _artifact_payload(
                    "DependencyGraph", "artifact_dependency_123"
                ),
            }
        if (method, path) == (
            "GET",
            f"/v1/repositories/{repository_id}/snapshots/snapshot_123",
        ):
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "connector_type": "local_repo",
                "ref": None,
                "resolved_revision": "abc123",
                "content_hash": "content_hash_123",
                "status": "existing",
                "created_at": "2026-05-29T12:00:00Z",
                "file_count": 2,
                "language_counts": {"python": 2},
                "raw_repo_token_estimate": 1200,
                "repository_snapshot_artifact": _artifact_payload(
                    "RepositorySnapshot", "artifact_snapshot_123"
                ),
                "repository_graph_artifact": _artifact_payload(
                    "RepositoryGraph", "artifact_graph_123"
                ),
                "symbol_graph_artifact": _artifact_payload(
                    "SymbolGraph", "artifact_symbol_123"
                ),
                "dependency_graph_artifact": _artifact_payload(
                    "DependencyGraph", "artifact_dependency_123"
                ),
            }
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/triage"):
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
                "created_at": "2026-05-29T12:01:00Z",
                "suspect_files": ["src/service.py"],
                "suspect_symbols": ["handle_request"],
                "raw_repo_token_estimate": 1200,
                "evidence_bundle_token_count": 180,
                "reduction_ratio": 6.67,
                "evidence_items": [],
                "workspace_evidence_bundle_artifact": _artifact_payload(
                    "WorkspaceEvidenceBundle", "artifact_evidence_123"
                ),
            }
        if (method, path) == (
            "POST",
            f"/v1/repositories/{repository_id}/decision-plans",
        ):
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "created_at": "2026-05-29T12:02:00Z",
                "decision_plan": _decision_plan_payload(),
            }
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/graph-query"):
            return _graph_query_payload(repository_id)
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/simulate"):
            return _simulation_payload()
        if (method, path) == ("POST", f"/v1/repositories/{repository_id}/apply"):
            return {
                "repository_id": repository_id,
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "patch_only",
                "applied": False,
                "created_at": "2026-05-29T12:03:00Z",
                "patch": "--- a/src/service.py\n+++ b/src/service.py\n",
                "apply_gate": {"passed": True},
                "validation_summary": {"patch_files": ["src/service.py"]},
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    capabilities = await client.get_repository_intelligence_capabilities()
    snapshot = await client.create_repository_snapshot(repository_id, {"ref": "main"})
    fetched = await client.get_repository_snapshot(repository_id, "snapshot_123")
    triage = await client.triage_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "signals": {"issue_text": "null dereference in handle_request"},
        },
    )
    plan = await client.create_repository_decision_plan(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "workspace_evidence_bundle_ref": "evidence_bundle_123",
        },
    )
    graph = await client.query_repository_graph(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "file_path": "src/service.py",
            "direction": "both",
        },
    )
    simulation = await client.simulate_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
        },
    )
    apply_result = await client.apply_repository(
        repository_id,
        {
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "decision_plan_123",
            "simulation_id": "simulation_123",
            "mode": "patch_only",
        },
    )

    assert isinstance(capabilities, RepositoryIntelligenceCapabilitiesResult)
    assert isinstance(snapshot, RepositorySnapshotResult)
    assert isinstance(fetched, RepositorySnapshotResult)
    assert isinstance(triage, RepositoryTriageResult)
    assert isinstance(plan, RepositoryDecisionPlanRevisionResult)
    assert isinstance(graph, RepositoryGraphQueryResult)
    assert isinstance(simulation, DecisionEnvelope)
    assert isinstance(apply_result, RepositoryApplyResult)
    assert capabilities.supported_languages == ["python", "typescript", "coq"]
    assert capabilities.support_progress.progress_label == f"3 / {DEFAULT_REAL_LANGUAGE_RANK_TARGET}"
    assert graph.graph_edges[0].edge_type == "imports"
