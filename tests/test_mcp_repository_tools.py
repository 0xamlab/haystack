from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import repositories
from apps.api_server.services.repository_language_priority import (
    DEFAULT_REAL_LANGUAGE_RANK_TARGET,
)

pytestmark = pytest.mark.anyio


def test_repository_tool_specs_cover_repository_flow() -> None:
    assert (
        repositories.GET_REPOSITORY_INTELLIGENCE_CAPABILITIES_SPEC["name"]
        == "get_repository_intelligence_capabilities"
    )
    assert repositories.CREATE_REPOSITORY_SNAPSHOT_SPEC["name"] == "create_repository_snapshot"
    assert repositories.GET_REPOSITORY_SNAPSHOT_SPEC["name"] == "get_repository_snapshot"
    assert repositories.TRIAGE_REPOSITORY_SPEC["name"] == "triage_repository"
    assert (
        repositories.CREATE_REPOSITORY_DECISION_PLAN_SPEC["name"]
        == "create_repository_decision_plan"
    )
    assert repositories.QUERY_REPOSITORY_GRAPH_SPEC["name"] == "query_repository_graph"
    assert repositories.SIMULATE_REPOSITORY_SPEC["name"] == "simulate_repository"
    assert repositories.RUN_REPOSITORY_PIPELINE_SPEC["name"] == "run_repository_pipeline"
    assert repositories.SIMULATE_REPOSITORY_PATCH_SPEC["name"] == "simulate_repository_patch"
    assert repositories.RUN_REPOSITORY_FIX_SPEC["name"] == "run_repository_fix"
    assert repositories.APPLY_REPOSITORY_SPEC["name"] == "apply_repository"


async def test_repository_tool_handlers_forward_canonical_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, object]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path, kwargs.get("json")))
        if (method, path) == ("GET", "/v1/repositories/capabilities"):
            return {
                "supported_languages": ["python", "typescript", "coq"],
                "support_progress": {
                    "supported_real_language_count": 3,
                    "ranked_target_language_count": DEFAULT_REAL_LANGUAGE_RANK_TARGET,
                    "progress_fraction": 3 / DEFAULT_REAL_LANGUAGE_RANK_TARGET,
                    "progress_label": f"3 / {DEFAULT_REAL_LANGUAGE_RANK_TARGET}",
                },
            }
        if (method, path) == ("POST", "/v1/repositories/repo_123/snapshots"):
            return {"snapshot_id": "snapshot_123", "status": "created"}
        if (method, path) == ("GET", "/v1/repositories/repo_123/snapshots/snapshot_123"):
            return {"snapshot_id": "snapshot_123", "status": "existing"}
        if (method, path) == ("POST", "/v1/repositories/repo_123/triage"):
            return {"workspace_evidence_bundle_ref": "evidence_bundle_123"}
        if (method, path) == ("POST", "/v1/repositories/repo_123/decision-plans"):
            return {
                "decision_plan_id": "decision_plan_123",
                "decision_plan": {
                    "repository_analysis": {
                        "planner_model_id": "repository.deterministic_local_v1",
                        "planner_execution_mode": "deterministic_local",
                        "planner_provider_backend": None,
                        "generated_patch_ref": "patch_123",
                        "patch_impact_report_ref": "impact_123",
                    }
                },
            }
        if (method, path) == ("POST", "/v1/repositories/repo_123/graph-query"):
            return {
                "repository_id": "repo_123",
                "snapshot_id": "snapshot_123",
                "created_at": "2026-05-29T12:10:00Z",
                "seed_file_paths": ["src/service.py"],
                "seed_symbols": ["handle_request"],
                "direct_dependencies": ["src/helpers.py"],
                "direct_dependents": ["tests/test_service.py"],
                "impacted_files": ["src/service.py", "tests/test_service.py"],
                "impacted_symbols": ["handle_request"],
                "graph_nodes": [],
                "graph_edges": [],
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
        if (method, path) == ("POST", "/v1/repositories/repo_123/simulate"):
            return {
                "run_id": "simulation_123",
                "decision_plan": {
                    "repository_analysis": {
                        "planner_model_id": "repository.deterministic_local_v1",
                        "planner_execution_mode": "deterministic_local",
                        "planner_provider_backend": None,
                        "generated_patch_ref": "patch_123",
                        "patch_impact_report_ref": "impact_123",
                    }
                },
                "score_breakdown": {"apply_gate": {"passed": True}},
            }
        if (method, path) == ("POST", "/v1/repositories/repo_123/simulate-patch"):
            return {
                "run_id": "simulation_patch_123",
                "recommended_action": "apply_patch",
                "confidence": 0.84,
            }
        if (method, path) == ("POST", "/v1/repositories/repo_123/pipeline"):
            return {
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
                            "patch_impact_report_ref": "impact_123",
                        }
                    },
                },
                "simulation": {
                    "run_id": "simulation_123",
                    "recommended_action": "apply_patch",
                    "score_breakdown": {"apply_gate": {"passed": True}},
                },
            }
        if (method, path) == ("POST", "/v1/repositories/repo_123/apply"):
            return {
                "applied": True,
                "branch_name": "algenta/repo-fix",
                "apply_gate": {"passed": True, "policy_snapshot_id": "policy_123"},
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(repositories, "api", _fake_api)

    capabilities = json.loads(
        await repositories.get_repository_intelligence_capabilities_handler({})
    )
    snapshot = json.loads(
        await repositories.create_repository_snapshot_handler(
            {"repository_id": "repo_123", "ref": "main"}
        )
    )
    fetched = json.loads(
        await repositories.get_repository_snapshot_handler(
            {"repository_id": "repo_123", "snapshot_id": "snapshot_123"}
        )
    )
    triage = json.loads(
        await repositories.triage_repository_handler(
            {
                "repository_id": "repo_123",
                "snapshot_id": "snapshot_123",
                "signals": {"issue_text": "null dereference"},
            }
        )
    )
    plan = json.loads(
        await repositories.create_repository_decision_plan_handler(
            {
                "repository_id": "repo_123",
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
            }
        )
    )
    graph = json.loads(
        await repositories.query_repository_graph_handler(
            {
                "repository_id": "repo_123",
                "snapshot_id": "snapshot_123",
                "file_path": "src/service.py",
                "direction": "both",
            }
        )
    )
    simulation = json.loads(
        await repositories.simulate_repository_handler(
            {
                "repository_id": "repo_123",
                "decision_plan_id": "decision_plan_123",
            }
        )
    )
    apply_result = json.loads(
        await repositories.apply_repository_handler(
            {
                "repository_id": "repo_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "local_branch",
                "write_permission": True,
            }
        )
    )
    pipeline = json.loads(
        await repositories.run_repository_pipeline_handler({"repository_id": "repo_123"})
    )
    simulate_patch = json.loads(
        await repositories.simulate_repository_patch_handler(
            {
                "repository_id": "repo_123",
                "snapshot_id": "snapshot_123",
                "patch_diff": "diff --git a/x b/x",
            }
        )
    )
    fix = json.loads(
        await repositories.run_repository_fix_handler({"repository_id": "repo_123"})
    )

    assert capabilities["supported_languages"] == ["python", "typescript", "coq"]
    assert capabilities["support_progress"]["progress_label"] == (
        f"3 / {DEFAULT_REAL_LANGUAGE_RANK_TARGET}"
    )
    assert snapshot["snapshot_id"] == "snapshot_123"
    assert fetched["status"] == "existing"
    assert triage["workspace_evidence_bundle_ref"] == "evidence_bundle_123"
    assert plan["decision_plan_id"] == "decision_plan_123"
    assert plan["decision_plan"]["repository_analysis"]["planner_model_id"] == (
        "repository.deterministic_local_v1"
    )
    assert plan["decision_plan"]["repository_analysis"]["patch_impact_report_ref"] == (
        "impact_123"
    )
    assert graph["seed_file_paths"] == ["src/service.py"]
    assert graph["top_change_risk_files"][0]["risk_score"] == 72.5
    assert simulation["run_id"] == "simulation_123"
    assert simulation["decision_plan"]["repository_analysis"]["planner_execution_mode"] == (
        "deterministic_local"
    )
    assert apply_result["branch_name"] == "algenta/repo-fix"
    assert apply_result["apply_gate"]["policy_snapshot_id"] == "policy_123"
    assert pipeline["pipeline"]["plan_id"] == "decision_plan_123"
    assert pipeline["gate"]["decision"] == "apply_allowed"
    assert simulate_patch["pipeline"]["simulation_id"] == "simulation_patch_123"
    assert fix["pipeline"]["apply_id"] == "simulation_123"
    assert fix["gate"]["decision"] == "apply_allowed"
    assert calls == [
        ("GET", "/v1/repositories/capabilities", None),
        ("POST", "/v1/repositories/repo_123/snapshots", {"ref": "main"}),
        ("GET", "/v1/repositories/repo_123/snapshots/snapshot_123", None),
        (
            "POST",
            "/v1/repositories/repo_123/triage",
            {
                "snapshot_id": "snapshot_123",
                "signals": {"issue_text": "null dereference"},
            },
        ),
        (
            "POST",
            "/v1/repositories/repo_123/decision-plans",
            {
                "workspace_evidence_bundle_ref": "evidence_bundle_123",
            },
        ),
        (
            "POST",
            "/v1/repositories/repo_123/graph-query",
            {
                "snapshot_id": "snapshot_123",
                "file_path": "src/service.py",
                "direction": "both",
            },
        ),
        (
            "POST",
            "/v1/repositories/repo_123/simulate",
            {
                "decision_plan_id": "decision_plan_123",
            },
        ),
        (
            "POST",
            "/v1/repositories/repo_123/apply",
            {
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "local_branch",
                "write_permission": True,
            },
        ),
        ("POST", "/v1/repositories/repo_123/pipeline", {}),
        (
            "POST",
            "/v1/repositories/repo_123/simulate-patch",
            {
                "snapshot_id": "snapshot_123",
                "patch_diff": "diff --git a/x b/x",
            },
        ),
        ("POST", "/v1/repositories/repo_123/pipeline", {}),
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
    ("handler", "arguments", "error"),
    [
        (
            repositories.get_repository_intelligence_capabilities_handler,
            {"repository_id": "repo_123"},
            "get_repository_intelligence_capabilities does not accept arguments.",
        ),
        (
            repositories.create_repository_snapshot_handler,
            {},
            "repository_id is required.",
        ),
        (
            repositories.get_repository_snapshot_handler,
            {"repository_id": "repo_123"},
            "snapshot_id is required.",
        ),
        (
            repositories.triage_repository_handler,
            {"repository_id": "repo_123", "snapshot_id": "snapshot_123"},
            "signals is required.",
        ),
        (
            repositories.create_repository_decision_plan_handler,
            {"repository_id": "repo_123"},
            "workspace_evidence_bundle_ref is required.",
        ),
        (
            repositories.query_repository_graph_handler,
            {"repository_id": "repo_123"},
            "snapshot_id or workspace_evidence_bundle_ref is required.",
        ),
        (
            repositories.simulate_repository_handler,
            {"repository_id": "repo_123"},
            "decision_plan_id is required.",
        ),
        (
            repositories.run_repository_pipeline_handler,
            {},
            "repository_id is required.",
        ),
        (
            repositories.simulate_repository_patch_handler,
            {"repository_id": "repo_123", "snapshot_id": "snapshot_123"},
            "patch_diff is required.",
        ),
        (
            repositories.run_repository_fix_handler,
            {},
            "repository_id is required.",
        ),
        (
            repositories.apply_repository_handler,
            {"repository_id": "repo_123"},
            "decision_plan_id is required.",
        ),
    ],
)
async def test_repository_tool_handlers_validate_required_arguments(
    handler,
    arguments: dict[str, object],
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        await handler(arguments)
