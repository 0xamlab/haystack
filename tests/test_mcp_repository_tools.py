from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import repositories

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
                    "ranked_target_language_count": 200,
                    "progress_fraction": 3 / 200,
                    "progress_label": "3 / 200",
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
                "validated_inputs": {"simulation_id": "simulation_123"},
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

    assert capabilities["supported_languages"] == ["python", "typescript", "coq"]
    assert capabilities["support_progress"]["progress_label"] == "3 / 200"
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
    assert simulation["validated_inputs"]["simulation_id"] == "simulation_123"
    assert simulation["decision_plan"]["repository_analysis"]["planner_execution_mode"] == (
        "deterministic_local"
    )
    assert apply_result["branch_name"] == "algenta/repo-fix"
    assert apply_result["apply_gate"]["policy_snapshot_id"] == "policy_123"
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
