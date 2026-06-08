"""Tests for test_decision_engine_query_surface: async_decision_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-1/tests/test_decision_engine_query_surface.py during modularization.
"""
from __future__ import annotations

from tests._test_decision_engine_query_surface_helpers import *  # noqa: F401,F403


async def test_async_decision_engine_client_get_runtime_modules_rejects_invalid_benchmark_discovery_rule(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_modules()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_contract.benchmark_discovery_rule"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_duplicate_benchmark_classes(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmarking"]["classes"].append(dict(payload["benchmarking"]["classes"][0]))

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "benchmarking.classes"
    assert exc_info.value.validation_errors[0]["path"] == "benchmarking.classes"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_duplicate_compiled_artifacts(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["compiled_artifacts"].append(dict(payload["compiled_artifacts"][0]))

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "compiled_artifacts"
    assert exc_info.value.validation_errors[0]["path"] == "compiled_artifacts"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_function_count_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_function_counts"][0] += 1

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_function_counts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_function_counts.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_module_identity_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_modules"][0], payload["shipping_runtime_modules"][1] = (
        payload["shipping_runtime_modules"][1],
        payload["shipping_runtime_modules"][0],
    )

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_modules.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_modules.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_missing_discovered_shipping_module(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
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

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.details["cause"] == "benchmark_discovery_lane.discovered_source_inventory"
    )
    assert exc_info.value.validation_errors[0]["path"] == (
        "benchmark_discovery_lane.discovered_source_inventory"
    )

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_benchmark_artifact_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_artifacts"][0], payload["shipping_runtime_benchmark_artifacts"][1] = (
        payload["shipping_runtime_benchmark_artifacts"][1],
        payload["shipping_runtime_benchmark_artifacts"][0],
    )

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_benchmark_artifacts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_benchmark_artifacts.0"


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_compiled_artifact_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_artifacts"][0] = "build/mismatched-runtime-compiled-artifact.json"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_compiled_artifacts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_artifacts.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_compiled_engine_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_engines"][0] = "python_fallback"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_compiled_engines.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_engines.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_invalid_slo_budget_applies_to(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["slo_budgets"][0]["applies_to"] = "shadow_realm_lane"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "slo_budgets.0.applies_to"
    assert exc_info.value.validation_errors[0]["path"] == "slo_budgets.0.applies_to"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_invalid_non_shipping_rule(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "benchmark_discovery_lane.non_shipping_rule"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "benchmark_discovery_lane.non_shipping_rule"
    )

    await client.aclose()


@pytest.mark.parametrize(
    ("shipping_field", "benchmark_field"),
    [
        ("shipping_runtime_max_cold_ms", "max_cold_ms"),
        ("shipping_runtime_max_warm_ms", "max_warm_ms"),
        ("shipping_runtime_max_hot_ms", "max_hot_ms"),
    ],
)
async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_latency_mismatch(
    monkeypatch,
    shipping_field: str,
    benchmark_field: str,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload[shipping_field][0] = payload["module_benchmarks"][0][benchmark_field] + 1.0

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == f"{shipping_field}.0"
    assert exc_info.value.validation_errors[0]["path"] == f"{shipping_field}.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_missing_compiled_artifact_reference(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_artifact"] = "build/missing-runtime-benchmark.json"
    payload["shipping_runtime_compiled_artifacts"][0] = "build/missing-runtime-benchmark.json"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "module_benchmarks.0.compiled_artifact"
    assert exc_info.value.validation_errors[0]["path"] == "module_benchmarks.0.compiled_artifact"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_release_validation_rejects_duplicate_condition_evidence_paths(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["evidence_paths"].append(payload["conditions"][0]["evidence_paths"][0])

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_release_validation()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "conditions.0.evidence_paths"
    assert exc_info.value.validation_errors[0]["path"] == "conditions.0.evidence_paths"

    await client.aclose()


async def test_async_decision_engine_client_runtime_proof_surfaces_fail_closed_on_invalid_payloads(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import (
        get_runtime_admin_benchmarks,
        get_runtime_admin_modules,
        get_runtime_manifest,
        get_runtime_release_validation,
    )

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payloads = {
        "/v1/runtime/manifest": get_runtime_manifest().model_dump(mode="json"),
        "/v1/admin/runtime/modules": get_runtime_admin_modules().model_dump(mode="json"),
        "/v1/admin/runtime/benchmarks": get_runtime_admin_benchmarks().model_dump(mode="json"),
        "/v1/admin/runtime/validation": get_runtime_release_validation().model_dump(mode="json"),
    }
    payloads["/v1/runtime/manifest"]["maturity"]["bpe_tokenizer"] = "legendary"
    payloads["/v1/admin/runtime/modules"]["proof_matrix"][0]["status"] = "unknown_status"
    payloads["/v1/admin/runtime/benchmarks"]["module_benchmarks"][0]["compiled_engine"] = (
        "warp_core"
    )
    payloads["/v1/admin/runtime/validation"]["conditions"][0]["condition"] = (
        "teleport-validated"
    )

    async def _fake_request(method: str, path: str, **kwargs):
        assert method == "GET"
        assert kwargs == {}
        return payloads[path]

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as manifest_exc:
        await client.get_runtime_manifest()
    assert manifest_exc.value.error_code == "invalid_runtime_contract_payload"
    assert manifest_exc.value.details["cause"] == "maturity.bpe_tokenizer"
    assert manifest_exc.value.validation_errors[0]["path"] == "maturity.bpe_tokenizer"
    assert manifest_exc.value.field_errors[0]["path"] == "maturity.bpe_tokenizer"

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as modules_exc:
        await client.get_runtime_modules()
    assert modules_exc.value.error_code == "invalid_runtime_contract_payload"
    assert modules_exc.value.details["cause"] == "proof_matrix.0.status"
    assert modules_exc.value.validation_errors[0]["path"] == "proof_matrix.0.status"

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as benchmarks_exc:
        await client.get_runtime_benchmarks()
    assert benchmarks_exc.value.error_code == "invalid_runtime_contract_payload"
    assert benchmarks_exc.value.details["cause"] == "module_benchmarks.0.compiled_engine"
    assert benchmarks_exc.value.validation_errors[0]["path"] == (
        "module_benchmarks.0.compiled_engine"
    )

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as validation_exc:
        await client.get_runtime_release_validation()
    assert validation_exc.value.error_code == "invalid_runtime_contract_payload"
    assert validation_exc.value.details["cause"] == "conditions.0.condition"
    assert validation_exc.value.validation_errors[0]["path"] == "conditions.0.condition"

    await client.aclose()


@pytest.mark.parametrize(
    "method_name,path",
    [
        ("get_runtime_modules", "/v1/admin/runtime/modules"),
        ("get_runtime_benchmarks", "/v1/admin/runtime/benchmarks"),
        ("get_runtime_release_validation", "/v1/admin/runtime/validation"),
    ],
)
async def test_async_decision_engine_client_runtime_admin_routes_propagate_missing_route(
    monkeypatch,
    method_name: str,
    path: str,
) -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    async def _fake_request(method: str, request_path: str, **kwargs):
        assert (method, request_path) == ("GET", path)
        raise NotFoundError(
            "missing",
            status_code=404,
            response_body={"error": {"code": "not_found"}},
        )

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(NotFoundError):
        await getattr(client, method_name)()

    await client.aclose()


