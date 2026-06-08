from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import repositories as repositories_router
from apps.api_server.schemas.repositories import (
    RepositoryApplyResponse,
    RepositoryDecisionPlanResponse,
    RepositoryGraphQueryResponse,
    RepositoryIntelligenceCapabilitiesResponse,
    RepositorySnapshotResponse,
    RepositoryTriageResponse,
)
from apps.api_server.schemas.response import DecisionEnvelope
from apps.api_server.services.repository_intelligence import (
    RepositoryIntelligenceError,
    get_repository_intelligence_capabilities,
)
from tests._asgi_client import SyncASGIClient

PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]
REPOSITORY_ID = "00000000-0000-0000-0000-000000000123"
ORG_ID = "00000000-0000-0000-0000-000000000456"
CREATED_AT = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)


async def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_repository_route",
        "key_id": "key_repository_route",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


def _visible_connector() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID(REPOSITORY_ID),
        org_id=uuid.UUID(ORG_ID),
        connector_type=SimpleNamespace(value="local_repo"),
    )


def _repository_artifact_payload(*, artifact_id: str, artifact_kind: str) -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "artifact_kind": artifact_kind,
        "content_hash": f"sha256-{artifact_id}",
        "storage_path": f"/tmp/{artifact_id}.parquet",
        "schema_revision": "runtime-internal-contracts-v1",
        "created_at": CREATED_AT,
    }


def _snapshot_response_payload() -> RepositorySnapshotResponse:
    return RepositorySnapshotResponse.model_validate(
        {
            "repository_id": REPOSITORY_ID,
            "snapshot_id": "snapshot_123",
            "connector_type": "local_repo",
            "ref": "main",
            "resolved_revision": "abc123",
            "content_hash": "content_hash_123",
            "status": "created",
            "created_at": CREATED_AT,
            "file_count": 2,
            "language_counts": {"python": 2},
            "raw_repo_token_estimate": 1200,
            "repository_snapshot_artifact": _repository_artifact_payload(
                artifact_id="artifact_snapshot_123",
                artifact_kind="RepositorySnapshot",
            ),
            "repository_graph_artifact": _repository_artifact_payload(
                artifact_id="artifact_graph_123",
                artifact_kind="RepositoryGraph",
            ),
            "symbol_graph_artifact": _repository_artifact_payload(
                artifact_id="artifact_symbol_123",
                artifact_kind="SymbolGraph",
            ),
            "dependency_graph_artifact": _repository_artifact_payload(
                artifact_id="artifact_dependency_123",
                artifact_kind="DependencyGraph",
            ),
        }
    )


def _capabilities_response_payload() -> dict[str, object]:
    return {
        "supported_languages": ["python", "typescript", "coq"],
        "support_progress": {
            "supported_real_language_count": 3,
            "ranked_target_language_count": 200,
            "progress_fraction": 3 / 200,
            "progress_label": "3 / 200",
        },
    }


def _triage_response_payload() -> RepositoryTriageResponse:
    return RepositoryTriageResponse.model_validate(
        {
            "repository_id": REPOSITORY_ID,
            "snapshot_id": "snapshot_123",
            "workspace_evidence_bundle_ref": "bundle_123",
            "created_at": CREATED_AT,
            "suspect_files": ["src/service.py"],
            "suspect_symbols": ["render_status"],
            "raw_repo_token_estimate": 1200,
            "evidence_bundle_token_count": 240,
            "reduction_ratio": 5.0,
            "evidence_items": [
                {
                    "evidence_id": "evidence_123",
                    "rank": 1,
                    "source_type": "diagnostic",
                    "source_ref": "diagnostic:return_literal",
                    "file_path": "src/service.py",
                    "symbol_name": "render_status",
                    "summary": "Return literal mismatches the failing test.",
                    "snippet": "return 'broken'",
                    "token_count": 12,
                    "score": 0.98,
                }
            ],
            "workspace_evidence_bundle_artifact": _repository_artifact_payload(
                artifact_id="artifact_bundle_123",
                artifact_kind="WorkspaceEvidenceBundle",
            ),
        }
    )


def _graph_query_response_payload() -> RepositoryGraphQueryResponse:
    return RepositoryGraphQueryResponse.model_validate(
        {
            "repository_id": REPOSITORY_ID,
            "snapshot_id": "snapshot_123",
            "created_at": CREATED_AT,
            "seed_file_paths": ["src/service.py"],
            "seed_symbols": ["src/service.py:render_status"],
            "direct_dependencies": ["src/helpers.py"],
            "direct_dependents": ["tests/test_service.py"],
            "impacted_files": ["src/service.py", "src/helpers.py", "tests/test_service.py"],
            "impacted_symbols": ["render_status", "normalize_status"],
            "graph_nodes": [
                {
                    "file_path": "src/service.py",
                    "depth": 0,
                    "is_seed": True,
                    "inbound_count": 1,
                    "outbound_count": 1,
                    "risk_score": 44.5,
                    "contained_symbols": ["render_status"],
                    "parent_child_symbols": [],
                },
                {
                    "file_path": "src/helpers.py",
                    "depth": 1,
                    "is_seed": False,
                    "inbound_count": 1,
                    "outbound_count": 0,
                    "risk_score": 24.0,
                    "contained_symbols": ["normalize_status"],
                    "parent_child_symbols": [],
                },
            ],
            "graph_edges": [
                {
                    "source_file": "src/service.py",
                    "target_file": "src/helpers.py",
                    "edge_type": "imports",
                }
            ],
            "top_change_risk_files": [
                {
                    "file_path": "src/service.py",
                    "depth": 0,
                    "relationship": "seed",
                    "risk_score": 44.5,
                    "top_symbol": "render_status",
                }
            ],
        }
    )


def _decision_plan_payload() -> dict[str, object]:
    return {
        "recommended_action": "local_branch",
        "confidence": 0.93,
        "expected_value": 1.4,
        "risk": {
            "p5": -0.2,
            "p95": 2.6,
            "probability_of_loss": 0.08,
            "var_95": -0.3,
        },
        "options": [],
        "rationale": "Patch the Python return literal to align with the bounded evidence bundle.",
        "repository_analysis": {
            "root_cause": "src/service.py returns the wrong literal for the failing test.",
            "planner_model_id": "repository.deterministic_local_v1",
            "planner_execution_mode": "deterministic_local",
            "planner_provider_backend": None,
            "candidate_fixes": ["Update the return literal in src/service.py."],
            "impacted_services": ["service-api"],
            "impacted_symbols": ["render_status"],
            "likely_failing_tests": ["tests/test_service.py::test_render_status"],
            "rollback_complexity": "low",
            "blast_radius": "single-module",
            "workspace_evidence_refs": ["bundle_123"],
            "generated_patch_ref": "patch_123",
            "patch_impact_report_ref": "impact_123",
            "token_reduction_metrics": {
                "raw_repo_token_estimate": 1200,
                "evidence_bundle_token_count": 240,
                "reduction_ratio": 5.0,
            },
        },
    }


def _decision_plan_response_payload() -> RepositoryDecisionPlanResponse:
    return RepositoryDecisionPlanResponse.model_validate(
        {
            "repository_id": REPOSITORY_ID,
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "plan_123",
            "created_at": CREATED_AT,
            "decision_plan": _decision_plan_payload(),
        }
    )


def _simulation_response_payload() -> DecisionEnvelope:
    return DecisionEnvelope.model_validate(
        {
            "run_id": "10000000-0000-0000-0000-000000000123",
            "engine_version": "mojo-runtime/1",
            "recommended_action": "local_branch",
            "confidence": 0.93,
            "rationale": "Simulation cleared the apply gate for the bounded repository patch.",
            "metrics": {
                "expected_value": 1.4,
                "median": 1.3,
                "std_deviation": 0.2,
                "variance": 0.04,
                "probability_of_loss": 0.08,
                "var_95": -0.3,
                "cvar_95": -0.4,
            },
            "percentiles": {
                "p5": -0.2,
                "p25": 1.0,
                "p50": 1.3,
                "p75": 1.6,
                "p95": 2.0,
            },
            "scenarios_run": 5000,
            "execution_ms": 42,
            "metadata": {
                "mode": "expert",
                "seed": 42,
                "billing_units": 5,
                "engine_version": "mojo-runtime/1",
            },
            "validated_inputs": {"simulation_id": "sim_123"},
            "score_breakdown": {"apply_gate": {"passed": True, "policy_snapshot_id": "policy_123"}},
            "decision_plan": _decision_plan_payload(),
        }
    )


def _apply_response_payload() -> RepositoryApplyResponse:
    return RepositoryApplyResponse.model_validate(
        {
            "repository_id": REPOSITORY_ID,
            "snapshot_id": "snapshot_123",
            "decision_plan_id": "plan_123",
            "simulation_id": "sim_123",
            "mode": "local_branch",
            "applied": True,
            "created_at": CREATED_AT,
            "patch": "--- a/src/service.py\n+++ b/src/service.py\n@@\n-return 'broken'\n+return 'fixed'\n",
            "branch_name": "algenta/live-repository-fix",
            "commit_sha": "abc123",
            "local_checkout_path": "/tmp/repository-checkout",
            "apply_gate": {"passed": True, "policy_snapshot_id": "policy_123"},
            "validation_summary": {"tests_selected": ["tests/test_service.py::test_render_status"]},
        }
    )


def _configure_repository_route_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_get_visible_connector(_db, _repository_id, _auth):
        return _visible_connector()

    monkeypatch.setattr(repositories_router, "get_visible_connector", _fake_get_visible_connector)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()


def test_repository_snapshot_route_requires_authentication() -> None:
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/snapshots",
                json={},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_repository_capabilities_route_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_get_capabilities():
        return _capabilities_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(
        repositories_router,
        "get_repository_intelligence_capabilities",
        _fake_get_capabilities,
    )
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/repositories/capabilities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["supported_languages"] == ["python", "typescript", "coq"]
    assert response.json()["support_progress"]["progress_label"] == "3 / 200"


def test_repository_capabilities_service_uses_live_priority_surface() -> None:
    capabilities = get_repository_intelligence_capabilities()

    assert isinstance(capabilities, RepositoryIntelligenceCapabilitiesResponse)
    assert capabilities.supported_languages
    assert capabilities.support_progress.supported_real_language_count == len(
        capabilities.supported_languages
    )
    assert (
        capabilities.support_progress.progress_label
        == f"{len(capabilities.supported_languages)} / "
        f"{capabilities.support_progress.ranked_target_language_count}"
    )


def test_repository_snapshot_route_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_create_snapshot(*, connector, request):
        assert str(connector.id) == REPOSITORY_ID
        assert request.ref == "main"
        return _snapshot_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "create_repository_snapshot", _fake_create_snapshot)
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/snapshots",
                json={"ref": "main"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["snapshot_id"] == "snapshot_123"
    assert response.json()["repository_snapshot_artifact"]["artifact_kind"] == "RepositorySnapshot"


def test_repository_snapshot_route_translates_repository_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_create_snapshot(*, connector, request):
        del connector, request
        raise RepositoryIntelligenceError(
            code="repository_source_not_found",
            message="Repository source path was not found.",
            status_code=404,
            details={"path": "/tmp/missing"},
        )

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "create_repository_snapshot", _fake_create_snapshot)
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/snapshots",
                json={"ref": "main"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "repository_source_not_found"
    assert response.json()["error"]["details"]["path"] == "/tmp/missing"


def test_repository_get_snapshot_route_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_get_snapshot(*, connector, snapshot_id):
        assert str(connector.id) == REPOSITORY_ID
        assert snapshot_id == "snapshot_123"
        return _snapshot_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "get_repository_snapshot", _fake_get_snapshot)
    try:
        with SyncASGIClient(app) as client:
            response = client.get(
                f"/v1/repositories/{REPOSITORY_ID}/snapshots/snapshot_123"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["resolved_revision"] == "abc123"
    assert response.json()["dependency_graph_artifact"]["artifact_kind"] == "DependencyGraph"


def test_repository_triage_route_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_triage(*, connector, request):
        assert str(connector.id) == REPOSITORY_ID
        assert request.snapshot_id == "snapshot_123"
        assert request.token_budget == 6000
        return _triage_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "triage_repository", _fake_triage)
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/triage",
                json={
                    "snapshot_id": "snapshot_123",
                    "signals": {
                        "diagnostics": [{"message": "return literal mismatch"}],
                        "failing_tests": ["tests/test_service.py::test_render_status"],
                    },
                    "token_budget": 6000,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["workspace_evidence_bundle_ref"] == "bundle_123"
    assert response.json()["evidence_items"][0]["source_type"] == "diagnostic"


def test_repository_graph_query_route_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_graph_query(*, connector, request):
        assert str(connector.id) == REPOSITORY_ID
        assert request.snapshot_id == "snapshot_123"
        assert request.file_path == "src/service.py"
        assert request.max_depth == 2
        return _graph_query_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "query_repository_graph", _fake_graph_query)
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/graph-query",
                json={
                    "snapshot_id": "snapshot_123",
                    "file_path": "src/service.py",
                    "max_depth": 2,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["seed_file_paths"] == ["src/service.py"]
    assert response.json()["direct_dependencies"] == ["src/helpers.py"]
    assert response.json()["top_change_risk_files"][0]["top_symbol"] == "render_status"


def test_repository_decision_plan_route_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_create_decision_plan(*, connector, request):
        assert str(connector.id) == REPOSITORY_ID
        assert request.snapshot_id == "snapshot_123"
        assert request.workspace_evidence_bundle_ref == "bundle_123"
        return _decision_plan_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "create_repository_decision_plan", _fake_create_decision_plan)
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/decision-plans",
                json={
                    "snapshot_id": "snapshot_123",
                    "workspace_evidence_bundle_ref": "bundle_123",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["decision_plan_id"] == "plan_123"
    repository_analysis = response.json()["decision_plan"]["repository_analysis"]
    assert repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"
    assert repository_analysis["patch_impact_report_ref"] == "impact_123"


def test_repository_decision_plan_route_accepts_workspace_evidence_bundle_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_create_decision_plan(*, connector, request):
        assert str(connector.id) == REPOSITORY_ID
        assert request.snapshot_id is None
        assert request.workspace_evidence_bundle_ref == "bundle_123"
        return _decision_plan_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "create_repository_decision_plan", _fake_create_decision_plan)
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/decision-plans",
                json={"workspace_evidence_bundle_ref": "bundle_123"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["decision_plan_id"] == "plan_123"


def test_repository_simulate_route_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_simulate(*, connector, request):
        assert str(connector.id) == REPOSITORY_ID
        assert request.snapshot_id is None
        assert request.decision_plan_id == "plan_123"
        assert request.runs == 5000
        return _simulation_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "simulate_repository_decision", _fake_simulate)
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/simulate",
                json={
                    "decision_plan_id": "plan_123",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["validated_inputs"]["simulation_id"] == "sim_123"
    assert response.json()["score_breakdown"]["apply_gate"]["policy_snapshot_id"] == "policy_123"
    assert response.json()["decision_plan"]["repository_analysis"]["planner_execution_mode"] == (
        "deterministic_local"
    )


def test_repository_apply_route_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_apply(*, connector, request):
        assert str(connector.id) == REPOSITORY_ID
        assert request.snapshot_id is None
        assert request.simulation_id == "sim_123"
        assert request.mode.value == "local_branch"
        return _apply_response_payload()

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(repositories_router, "apply_repository_decision", _fake_apply)
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                f"/v1/repositories/{REPOSITORY_ID}/apply",
                json={
                    "decision_plan_id": "plan_123",
                    "simulation_id": "sim_123",
                    "mode": "local_branch",
                    "write_permission": True,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["mode"] == "local_branch"
    assert response.json()["branch_name"] == "algenta/live-repository-fix"
    assert response.json()["apply_gate"]["passed"] is True


@pytest.mark.parametrize(
    ("path", "payload", "service_attr", "is_async"),
    [
        (
            f"/v1/repositories/{REPOSITORY_ID}/triage",
            {"snapshot_id": "snapshot_123", "signals": {"diagnostics": [{"message": "x"}]}},
            "triage_repository",
            False,
        ),
        (
            f"/v1/repositories/{REPOSITORY_ID}/decision-plans",
            {"snapshot_id": "snapshot_123", "workspace_evidence_bundle_ref": "bundle_123"},
            "create_repository_decision_plan",
            True,
        ),
        (
            f"/v1/repositories/{REPOSITORY_ID}/graph-query",
            {"snapshot_id": "snapshot_123", "file_path": "src/service.py"},
            "query_repository_graph",
            False,
        ),
        (
            f"/v1/repositories/{REPOSITORY_ID}/simulate",
            {"snapshot_id": "snapshot_123", "decision_plan_id": "plan_123"},
            "simulate_repository_decision",
            True,
        ),
        (
            f"/v1/repositories/{REPOSITORY_ID}/apply",
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "plan_123",
                "simulation_id": "sim_123",
                "mode": "patch_only",
            },
            "apply_repository_decision",
            True,
        ),
    ],
)
def test_repository_analysis_routes_translate_repository_errors(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    payload: dict[str, object],
    service_attr: str,
    is_async: bool,
) -> None:
    def _raise_repository_error(*args, **kwargs):
        del args, kwargs
        raise RepositoryIntelligenceError(
            code="repository_route_test_failure",
            message="Repository route propagated a service-layer failure.",
            status_code=409,
            details={"marker": service_attr},
        )

    async def _raise_repository_error_async(*args, **kwargs):
        _raise_repository_error(*args, **kwargs)

    _configure_repository_route_dependencies(monkeypatch)
    monkeypatch.setattr(
        repositories_router,
        service_attr,
        _raise_repository_error_async if is_async else _raise_repository_error,
    )
    try:
        with SyncASGIClient(app) as client:
            response = client.post(path, json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "repository_route_test_failure"
    assert response.json()["error"]["details"]["marker"] == service_attr


def test_openapi_declares_repository_routes_with_protected_security_and_response_models() -> None:
    with SyncASGIClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    expected_route_refs = {
        ("/v1/repositories/capabilities", "get"): (
            "#/components/schemas/RepositoryIntelligenceCapabilitiesResponse"
        ),
        ("/v1/repositories/{repository_id}/snapshots", "post"): (
            "#/components/schemas/RepositorySnapshotResponse"
        ),
        ("/v1/repositories/{repository_id}/snapshots/{snapshot_id}", "get"): (
            "#/components/schemas/RepositorySnapshotResponse"
        ),
        ("/v1/repositories/{repository_id}/triage", "post"): (
            "#/components/schemas/RepositoryTriageResponse"
        ),
        ("/v1/repositories/{repository_id}/graph-query", "post"): (
            "#/components/schemas/RepositoryGraphQueryResponse"
        ),
        ("/v1/repositories/{repository_id}/decision-plans", "post"): (
            "#/components/schemas/RepositoryDecisionPlanResponse"
        ),
        ("/v1/repositories/{repository_id}/simulate", "post"): (
            "#/components/schemas/DecisionEnvelope"
        ),
        ("/v1/repositories/{repository_id}/apply", "post"): (
            "#/components/schemas/RepositoryApplyResponse"
        ),
    }

    for (path, method), ref in expected_route_refs.items():
        operation = payload["paths"][path][method]
        assert operation["security"] == PROTECTED_OPENAPI_SECURITY
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": ref
        }


def test_openapi_repository_schemas_pin_planner_provenance_and_apply_gate_contract() -> None:
    with SyncASGIClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    repository_analysis = payload["components"]["schemas"]["RepositoryAnalysis"]
    decision_plan = payload["components"]["schemas"]["DecisionPlan"]
    apply_response = payload["components"]["schemas"]["RepositoryApplyResponse"]
    triage_response = payload["components"]["schemas"]["RepositoryTriageResponse"]
    decision_plan_response = payload["components"]["schemas"]["RepositoryDecisionPlanResponse"]
    decision_plan_request = payload["components"]["schemas"]["RepositoryDecisionPlanCreateRequest"]

    assert {
        "root_cause",
        "planner_model_id",
        "planner_execution_mode",
        "rollback_complexity",
        "blast_radius",
        "token_reduction_metrics",
    }.issubset(set(repository_analysis["required"]))
    assert repository_analysis["properties"]["planner_provider_backend"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert repository_analysis["properties"]["patch_impact_report_ref"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert decision_plan["properties"]["repository_analysis"]["anyOf"] == [
        {"$ref": "#/components/schemas/RepositoryAnalysis"},
        {"type": "null"},
    ]
    assert {"apply_gate", "validation_summary"}.issubset(set(apply_response["properties"]))
    assert {
        "workspace_evidence_bundle_ref",
        "raw_repo_token_estimate",
        "evidence_bundle_token_count",
        "reduction_ratio",
    }.issubset(set(triage_response["required"]))
    assert {"decision_plan_id", "decision_plan"}.issubset(
        set(decision_plan_response["required"])
    )
    assert "workspace_evidence_bundle_ref" in decision_plan_request["required"]
    assert "snapshot_id" not in decision_plan_request.get("required", [])
    simulation_request = payload["components"]["schemas"]["RepositorySimulationRequest"]
    apply_request = payload["components"]["schemas"]["RepositoryApplyRequest"]
    assert "decision_plan_id" in simulation_request["required"]
    assert "snapshot_id" not in simulation_request.get("required", [])
    assert {"decision_plan_id", "simulation_id", "mode"}.issubset(set(apply_request["required"]))
    assert "snapshot_id" not in apply_request.get("required", [])
