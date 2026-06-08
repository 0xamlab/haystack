from __future__ import annotations

import warnings

import pytest

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.runtime_manifest import (
    RuntimeManifestBuildError,
    get_runtime_admin_benchmarks,
    get_runtime_admin_modules,
    get_runtime_manifest,
    get_runtime_release_validation,
    validate_runtime_admin_benchmarks_payload,
    validate_runtime_admin_modules_payload,
)
from tests._asgi_client import SyncASGIClient

PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]


async def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_runtime_admin",
        "key_id": "key_runtime_admin",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


@pytest.mark.anyio
async def test_runtime_admin_routes_require_authentication(client) -> None:
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        response = await client.get("/v1/admin/runtime/modules")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_runtime_admin_modules_route_matches_signed_manifest() -> None:
    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/admin/runtime/modules")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    manifest = get_runtime_manifest().model_dump(mode="json")

    assert payload["runtime_version"] == manifest["runtime_version"]
    assert payload["llm_core_manifest"] == "llm-core-v1"
    assert payload["summary"] == {
        "module_count": 22,
        "function_count": 209,
        "maturity_counts": {"channel_covered": 22},
        "layer_counts": {"mojo_llm_runtime_core": 22},
    }
    assert payload["shipping_contract"]["benchmark_discovery_rule"] == manifest[
        "shipping_contract"
    ]["benchmark_discovery_rule"]
    assert [entry["name"] for entry in payload["modules"]] == [
        module["name"] for module in manifest["modules"]
    ]
    assert payload["proof_matrix"] == manifest["proof_matrix"]


def test_runtime_admin_benchmarks_route_exposes_budgeted_runtime_catalog() -> None:
    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/admin/runtime/benchmarks")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    manifest = get_runtime_manifest().model_dump(mode="json")

    assert payload["runtime_version"] == "2026.05.0"
    assert payload["benchmark_discovery_lane"]["shipping_manifest_modules"] == 22
    assert payload["benchmark_discovery_lane"]["non_shipping_rule"] == manifest[
        "benchmark_discovery_lane"
    ]["non_shipping_rule"]
    assert len(payload["benchmark_discovery_lane"]["discovered_source_inventory"]) == payload[
        "benchmark_discovery_lane"
    ]["discovered_source_modules"]
    assert sum(
        entry["public_function_count"]
        for entry in payload["benchmark_discovery_lane"]["discovered_source_inventory"]
    ) == payload["benchmark_discovery_lane"]["discovered_public_functions"]
    assert payload["benchmarking"]["classes"][0] == {
        "code": "B1",
        "description": "microkernel latency",
        "evidence_paths": [
            "benchmarks/summary.json",
            "tests/benchmark_mojo_vs_python.py",
        ],
    }
    assert payload["slo_budgets"][0]["name"] == "runtime_manifest_load"
    assert payload["evaluation_science"]["dimensions"][0] == "answer correctness"
    assert payload["quality_gate_benchmark_classes"] == [
        {
            "code": "B6",
            "description": "checkpoint and replay overhead",
            "evidence_paths": [],
        },
        {
            "code": "B7",
            "description": "MCP tool latency",
            "evidence_paths": [],
        },
        {
            "code": "B9",
            "description": "RAG retrieval quality and latency",
            "evidence_paths": [],
        },
        {
            "code": "B10",
            "description": "decision workflow completion latency",
            "evidence_paths": [
                "build/repository_intelligence_benchmark.json",
                "benchmarks/repository_intelligence_benchmark.py",
                "tests/test_repository_intelligence_benchmark.py",
            ],
        },
    ]
    assert [entry["name"] for entry in payload["quality_gate_slo_budgets"]] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert payload["evaluation_summary"] == {
        "dimension_count": 10,
        "method_count": 8,
        "release_blocker_count": 6,
        "benchmark_class_count": 4,
        "slo_budget_count": 3,
        "replay_gate_enabled": True,
        "tool_call_quality_gate_enabled": True,
        "rag_quality_gate_enabled": True,
        "decision_quality_gate_enabled": True,
    }
    assert len(payload["module_benchmarks"]) == 22
    assert payload["module_benchmarks"][0]["function_count"] > 0
    assert payload["shipping_runtime_modules"][0] == "bpe_tokenizer"
    assert payload["shipping_runtime_function_counts"][0] == payload["module_benchmarks"][0][
        "function_count"
    ]
    assert payload["shipping_runtime_benchmark_speedups_x"][0] == payload["module_benchmarks"][0][
        "benchmark_speedup_x"
    ]
    assert payload["shipping_runtime_benchmark_artifacts"][0] == payload["module_benchmarks"][0][
        "benchmark_artifact"
    ]
    assert payload["shipping_runtime_compiled_artifacts"][0] == payload["module_benchmarks"][0][
        "compiled_artifact"
    ]
    assert payload["shipping_runtime_compiled_engines"][0] == payload["module_benchmarks"][0][
        "compiled_engine"
    ]
    assert payload["shipping_runtime_max_cold_ms"][0] == payload["module_benchmarks"][0][
        "max_cold_ms"
    ]
    assert payload["shipping_runtime_max_warm_ms"][0] == payload["module_benchmarks"][0][
        "max_warm_ms"
    ]
    assert payload["shipping_runtime_max_hot_ms"][0] == payload["module_benchmarks"][0][
        "max_hot_ms"
    ]
    assert all(entry["benchmark_speedup_x"] > 0 for entry in payload["module_benchmarks"])
    assert sum(entry["function_count"] for entry in payload["module_benchmarks"]) == payload[
        "benchmark_discovery_lane"
    ]["shipping_manifest_functions"]
    assert payload["shipping_runtime_modules"] == [
        entry["name"] for entry in payload["module_benchmarks"]
    ]
    assert payload["shipping_runtime_function_counts"] == [
        entry["function_count"] for entry in payload["module_benchmarks"]
    ]
    assert payload["shipping_runtime_benchmark_speedups_x"] == [
        entry["benchmark_speedup_x"] for entry in payload["module_benchmarks"]
    ]
    assert payload["shipping_runtime_benchmark_artifacts"] == [
        entry["benchmark_artifact"] for entry in payload["module_benchmarks"]
    ]
    assert payload["shipping_runtime_compiled_artifacts"] == [
        entry["compiled_artifact"] for entry in payload["module_benchmarks"]
    ]
    assert payload["shipping_runtime_compiled_engines"] == [
        entry["compiled_engine"] for entry in payload["module_benchmarks"]
    ]
    assert payload["shipping_runtime_max_cold_ms"] == [
        entry["max_cold_ms"] for entry in payload["module_benchmarks"]
    ]
    assert payload["shipping_runtime_max_warm_ms"] == [
        entry["max_warm_ms"] for entry in payload["module_benchmarks"]
    ]
    assert payload["shipping_runtime_max_hot_ms"] == [
        entry["max_hot_ms"] for entry in payload["module_benchmarks"]
    ]
    discovered_source_import_paths = {
        entry["import_path"]
        for entry in payload["benchmark_discovery_lane"]["discovered_source_inventory"]
    }
    assert {
        entry["name"] for entry in payload["module_benchmarks"]
    }.issubset(discovered_source_import_paths)


def test_runtime_admin_validation_route_reports_release_theorem_status() -> None:
    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        with SyncASGIClient(app) as client:
            response = client.get("/v1/admin/runtime/validation")
            openapi = client.get("/openapi.json")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert payload["valid_release"] is True
    assert payload["theorem_statement"] == (
        "A release is valid iff every advertised capability is manifest-listed, proof-backed, "
        "policy-covered, replay-tested, and deployment-mode validated."
    )
    conditions = {entry["condition"]: entry for entry in payload["conditions"]}
    assert list(conditions) == [
        "manifest-listed",
        "proof-backed",
        "policy-covered",
        "replay-tested",
        "deployment-mode validated",
    ]
    assert all(entry["satisfied"] is True for entry in conditions.values())
    assert "/v1/runtime/manifest" in conditions["manifest-listed"]["evidence_paths"]
    assert conditions["proof-backed"]["evidence_paths"] == [
        "build/llm_rollout_proof_bundle.json",
        "build/llm_rollout_parity_benchmark.json",
        "build/llm_compiled_runtime_benchmark.json",
        "tests/test_llm_rollout_matrix.py",
    ]
    assert conditions["policy-covered"]["evidence_paths"] == [
        "apps/api_server/services/execution_policy_service.py",
        "/v1/runtime/manifest",
    ]
    assert conditions["replay-tested"]["evidence_paths"] == [
        "/v1/runtime/manifest",
        "apps/docs/integration_manifest.v1.json",
    ]
    assert conditions["deployment-mode validated"]["evidence_paths"] == ["/v1/runtime/manifest"]
    openapi_payload = openapi.json()
    assert "/v1/admin/runtime/modules" in openapi_payload["paths"]
    assert "/v1/admin/runtime/benchmarks" in openapi_payload["paths"]
    assert "/v1/admin/runtime/validation" in openapi_payload["paths"]
    assert "/mcp/tools" in openapi_payload["paths"]
    assert "/mcp/sse" in openapi_payload["paths"]
    assert "/mcp/messages" in openapi_payload["paths"]
    assert openapi_payload["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "APIKey",
        "description": "Canonical v1 authentication. Use Authorization: Bearer <api_key>.",
    }
    assert (
        openapi_payload["paths"]["/v1/admin/runtime/modules"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        openapi_payload["paths"]["/v1/admin/runtime/benchmarks"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert (
        openapi_payload["paths"]["/v1/admin/runtime/validation"]["get"]["security"]
        == PROTECTED_OPENAPI_SECURITY
    )
    assert openapi_payload["paths"]["/v1/runtime/manifest"]["get"].get("security") is None
    assert openapi_payload["paths"]["/mcp/tools"]["get"].get("security") is None
    assert openapi_payload["paths"]["/mcp/sse"]["get"].get("security") is None
    assert openapi_payload["paths"]["/mcp/messages"]["post"].get("security") is None
    assert "200" in openapi_payload["paths"]["/mcp/tools"]["get"]["responses"]
    assert "503" in openapi_payload["paths"]["/mcp/sse"]["get"]["responses"]
    assert "503" in openapi_payload["paths"]["/mcp/messages"]["post"]["responses"]
    assert "200" not in openapi_payload["paths"]["/mcp/sse"]["get"]["responses"]
    assert "200" not in openapi_payload["paths"]["/mcp/messages"]["post"]["responses"]


def test_runtime_manifest_route_rejects_invalid_signed_model_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apps.api_server.routers.meta as meta_router

    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.modules[0].name = "wormhole_kernel"
    monkeypatch.setattr(meta_router, "get_runtime_manifest", lambda: manifest)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with SyncASGIClient(app) as client:
            response = client.get("/v1/runtime/manifest")

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "invalid_runtime_manifest_payload"
    assert payload["error"]["details"]["cause"] == "modules.0.name"
    assert payload["error"]["details"]["validation_errors"][0]["path"] == "modules.0.name"
    assert caught == []


def test_runtime_admin_modules_route_rejects_invalid_signed_model_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apps.api_server.routers.meta as meta_router

    modules = get_runtime_admin_modules().model_copy(deep=True)
    modules.modules[0].name = "wormhole_kernel"
    monkeypatch.setattr(meta_router, "get_runtime_admin_modules", lambda: modules)

    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with SyncASGIClient(app) as client:
                response = client.get("/v1/admin/runtime/modules")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "invalid_runtime_admin_modules_payload"
    assert payload["error"]["details"]["cause"] == "modules.0.name"
    assert payload["error"]["details"]["validation_errors"][0]["path"] == "modules.0.name"
    assert caught == []


def test_runtime_admin_benchmarks_route_rejects_invalid_signed_model_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apps.api_server.routers.meta as meta_router

    benchmarks = get_runtime_admin_benchmarks().model_copy(deep=True)
    benchmarks.module_benchmarks[0].name = "wormhole_kernel"
    monkeypatch.setattr(meta_router, "get_runtime_admin_benchmarks", lambda: benchmarks)

    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with SyncASGIClient(app) as client:
                response = client.get("/v1/admin/runtime/benchmarks")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "invalid_runtime_admin_benchmarks_payload"
    assert payload["error"]["details"]["cause"] == "module_benchmarks.0.name"
    assert payload["error"]["details"]["validation_errors"][0]["path"] == "module_benchmarks.0.name"
    assert caught == []


def test_runtime_admin_validation_route_rejects_invalid_signed_model_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apps.api_server.routers.meta as meta_router

    validation = get_runtime_release_validation().model_copy(deep=True)
    validation.conditions[0].condition = "wormhole_condition"
    monkeypatch.setattr(meta_router, "get_runtime_release_validation", lambda: validation)

    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with SyncASGIClient(app) as client:
                response = client.get("/v1/admin/runtime/validation")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "invalid_runtime_release_validation_payload"
    assert payload["error"]["details"]["cause"] == "conditions.0.condition"
    assert payload["error"]["details"]["validation_errors"][0]["path"] == "conditions.0.condition"
    assert caught == []


def test_get_runtime_admin_modules_fails_closed_for_invalid_internal_manifest_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Patch the actual definition location: get_runtime_manifest lives in
    # apps.runtime_manifest._public_api after the modular split.
    import apps.runtime_manifest._public_api as runtime_manifest_module

    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.modules[0].name = "wormhole_kernel"
    monkeypatch.setattr(runtime_manifest_module, "get_runtime_manifest", lambda: manifest)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeManifestBuildError) as exc_info:
            get_runtime_admin_modules()

    assert exc_info.value.code == "invalid_runtime_admin_modules_payload"
    assert exc_info.value.details["cause"] == "modules.0.name"
    assert exc_info.value.details["validation_errors"][0]["path"] == "modules.0.name"
    assert caught == []


def test_get_runtime_admin_benchmarks_fails_closed_for_invalid_internal_manifest_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Patch the actual definition location.
    import apps.runtime_manifest._public_api as runtime_manifest_module

    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.modules[0].name = "wormhole_kernel"
    monkeypatch.setattr(runtime_manifest_module, "get_runtime_manifest", lambda: manifest)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeManifestBuildError) as exc_info:
            get_runtime_admin_benchmarks()

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_modules.0"
    assert exc_info.value.details["validation_errors"][0]["path"] == "shipping_runtime_modules.0"
    assert caught == []


def test_validate_runtime_admin_modules_payload_fails_closed_for_duplicate_proof_matrix_layers() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"].append(dict(payload["proof_matrix"][0]))

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_modules_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_modules_payload"
    assert exc_info.value.details["cause"] == "proof_matrix"
    assert exc_info.value.details["validation_errors"][0]["path"] == "proof_matrix"


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_duplicate_benchmark_classes() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmarking"]["classes"].append(dict(payload["benchmarking"]["classes"][0]))

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "benchmarking.classes"
    assert exc_info.value.details["validation_errors"][0]["path"] == "benchmarking.classes"


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_duplicate_benchmark_class_evidence_paths() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmarking"]["classes"][0]["evidence_paths"].append(
        payload["benchmarking"]["classes"][0]["evidence_paths"][0]
    )

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "evidence_paths"
    assert exc_info.value.details["validation_errors"][0]["path"] == "evidence_paths"


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_duplicate_quality_gate_benchmark_class_evidence_paths() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["quality_gate_benchmark_classes"][0]["evidence_paths"].append(
        "tests/test_runtime_admin_api.py"
    )
    payload["quality_gate_benchmark_classes"][0]["evidence_paths"].append(
        "tests/test_runtime_admin_api.py"
    )

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "evidence_paths"
    assert exc_info.value.details["validation_errors"][0]["path"] == "evidence_paths"


def test_validate_runtime_admin_modules_payload_fails_closed_for_duplicate_proof_evidence_paths() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["evidence_paths"].append(payload["proof_matrix"][0]["evidence_paths"][0])

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_modules_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_modules_payload"
    assert exc_info.value.details["cause"] == "proof_matrix.0.evidence_paths"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "proof_matrix.0.evidence_paths"
    )


def test_validate_runtime_admin_modules_payload_fails_closed_for_summary_function_count_mismatch() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["function_count"] += 1

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_modules_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_modules_payload"
    assert exc_info.value.details["cause"] == "summary.function_count"
    assert exc_info.value.details["validation_errors"][0]["path"] == "summary.function_count"


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_duplicate_compiled_artifact_paths() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["compiled_artifacts"].append(dict(payload["compiled_artifacts"][0]))

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "compiled_artifacts"
    assert exc_info.value.details["validation_errors"][0]["path"] == "compiled_artifacts"


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_shipping_module_count_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_modules"] += 1

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == (
        "benchmark_discovery_lane.shipping_manifest_modules"
    )
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "benchmark_discovery_lane.shipping_manifest_modules"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_missing_discovered_shipping_module() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    discovery_index = next(
        index
        for index, entry in enumerate(payload["benchmark_discovery_lane"]["discovered_source_inventory"])
        if entry["import_path"] == payload["module_benchmarks"][0]["name"]
    )
    replacement_import_path = f"{payload['module_benchmarks'][0]['name']}_shadow"
    payload["benchmark_discovery_lane"]["discovered_source_inventory"][discovery_index][
        "import_path"
    ] = replacement_import_path

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert (
        exc_info.value.details["cause"] == "benchmark_discovery_lane.discovered_source_inventory"
    )
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "benchmark_discovery_lane.discovered_source_inventory"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_shipping_function_count_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_function_counts"][0] += 1

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_function_counts.0"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "shipping_runtime_function_counts.0"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_shipping_speedup_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_speedups_x"][0] += 1.0

    with pytest.raises(RuntimeManifestBuildError, match="shipping_runtime_benchmark_speedups_x") as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.details["cause"] == "shipping_runtime_benchmark_speedups_x.0"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "shipping_runtime_benchmark_speedups_x.0"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_shipping_module_identity_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_modules"][0], payload["shipping_runtime_modules"][1] = (
        payload["shipping_runtime_modules"][1],
        payload["shipping_runtime_modules"][0],
    )

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_modules.0"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "shipping_runtime_modules.0"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_shipping_benchmark_artifact_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_artifacts"][0], payload["shipping_runtime_benchmark_artifacts"][1] = (
        payload["shipping_runtime_benchmark_artifacts"][1],
        payload["shipping_runtime_benchmark_artifacts"][0],
    )

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_benchmark_artifacts.0"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "shipping_runtime_benchmark_artifacts.0"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_shipping_compiled_artifact_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_artifacts"][0] = "build/mismatched-runtime-compiled-artifact.json"

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_compiled_artifacts.0"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "shipping_runtime_compiled_artifacts.0"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_shipping_compiled_engine_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_engines"][0] = "python_fallback"

    with pytest.raises(RuntimeManifestBuildError, match="shipping_runtime_compiled_engines") as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.details["cause"] == "shipping_runtime_compiled_engines.0"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "shipping_runtime_compiled_engines.0"
    )


@pytest.mark.parametrize(
    ("shipping_field", "benchmark_field"),
    [
        ("shipping_runtime_max_cold_ms", "max_cold_ms"),
        ("shipping_runtime_max_warm_ms", "max_warm_ms"),
        ("shipping_runtime_max_hot_ms", "max_hot_ms"),
    ],
)
def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_shipping_latency_mismatch(
    shipping_field: str,
    benchmark_field: str,
) -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload[shipping_field][0] = payload["module_benchmarks"][0][benchmark_field] + 1.0

    with pytest.raises(RuntimeManifestBuildError, match=shipping_field) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.details["cause"] == f"{shipping_field}.0"
    assert exc_info.value.details["validation_errors"][0]["path"] == f"{shipping_field}.0"


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("benchmark_speedup_x", 0.0),
        ("max_cold_ms", 0.0),
        ("max_warm_ms", -1.0),
        ("max_hot_ms", 0.0),
    ],
)
def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_non_positive_benchmark_metrics(
    field_name: str,
    bad_value: float,
) -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0][field_name] = bad_value
    if field_name == "benchmark_speedup_x":
        payload["shipping_runtime_benchmark_speedups_x"][0] = bad_value
    if field_name == "max_cold_ms":
        payload["shipping_runtime_max_cold_ms"][0] = bad_value
    if field_name == "max_warm_ms":
        payload["shipping_runtime_max_warm_ms"][0] = bad_value
    if field_name == "max_hot_ms":
        payload["shipping_runtime_max_hot_ms"][0] = bad_value

    with pytest.raises(RuntimeManifestBuildError, match=field_name) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.details["cause"] == f"module_benchmarks.0.{field_name}"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        f"module_benchmarks.0.{field_name}"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_missing_compiled_artifact_reference() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_artifact"] = "build/missing-runtime-benchmark.json"
    payload["shipping_runtime_compiled_artifacts"][0] = "build/missing-runtime-benchmark.json"

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "module_benchmarks.0.compiled_artifact"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "module_benchmarks.0.compiled_artifact"
    )


def test_validate_runtime_admin_benchmarks_payload_fails_closed_for_duplicate_benchmark_artifact_paths() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][1]["benchmark_artifact"] = payload["module_benchmarks"][0][
        "benchmark_artifact"
    ]
    payload["shipping_runtime_benchmark_artifacts"][1] = payload["module_benchmarks"][1][
        "benchmark_artifact"
    ]

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_admin_benchmarks_payload(payload)

    assert exc_info.value.code == "invalid_runtime_admin_benchmarks_payload"
    assert exc_info.value.details["cause"] == "module_benchmarks.1.benchmark_artifact"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "module_benchmarks.1.benchmark_artifact"
    )
