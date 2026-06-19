from __future__ import annotations

import json
from copy import deepcopy

import pytest

from apps.mcp_server.tools import meta
from apps.platform_contract import load_platform_contract_manifest
from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations,
)


def _platform_contract_payload() -> dict[str, object]:
    return deepcopy(load_platform_contract_manifest())


def test_get_contract_tool_spec_is_zero_argument() -> None:
    assert meta.GET_CONTRACT_SPEC["name"] == "get_contract"
    assert meta.GET_CONTRACT_SPEC["inputSchema"]["properties"] == {}
    assert meta.GET_CONTRACT_SPEC["inputSchema"]["additionalProperties"] is False


def test_get_runtime_manifest_tool_spec_is_zero_argument() -> None:
    assert meta.GET_RUNTIME_MANIFEST_SPEC["name"] == "get_runtime_manifest"
    assert meta.GET_RUNTIME_MANIFEST_SPEC["inputSchema"]["properties"] == {}
    assert meta.GET_RUNTIME_MANIFEST_SPEC["inputSchema"]["additionalProperties"] is False


def test_get_runtime_release_validation_tool_spec_is_zero_argument() -> None:
    assert meta.GET_RUNTIME_RELEASE_VALIDATION_SPEC["name"] == "get_runtime_release_validation"
    assert meta.GET_RUNTIME_RELEASE_VALIDATION_SPEC["inputSchema"]["properties"] == {}
    assert meta.GET_RUNTIME_RELEASE_VALIDATION_SPEC["inputSchema"]["additionalProperties"] is False


def test_get_runtime_modules_tool_spec_is_zero_argument() -> None:
    assert meta.GET_RUNTIME_MODULES_SPEC["name"] == "get_runtime_modules"
    assert meta.GET_RUNTIME_MODULES_SPEC["inputSchema"]["properties"] == {}
    assert meta.GET_RUNTIME_MODULES_SPEC["inputSchema"]["additionalProperties"] is False


def test_get_runtime_benchmarks_tool_spec_is_zero_argument() -> None:
    assert meta.GET_RUNTIME_BENCHMARKS_SPEC["name"] == "get_runtime_benchmarks"
    assert "benchmark evidence paths" in meta.GET_RUNTIME_BENCHMARKS_SPEC["description"]
    assert meta.GET_RUNTIME_BENCHMARKS_SPEC["inputSchema"]["properties"] == {}
    assert meta.GET_RUNTIME_BENCHMARKS_SPEC["inputSchema"]["additionalProperties"] is False


@pytest.mark.anyio
async def test_get_contract_tool_handler_forwards_contract_payload(monkeypatch) -> None:
    expected_payload = _platform_contract_payload()

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        return 200, expected_payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    raw = await meta.get_contract_handler({})
    body = json.loads(raw)

    assert body["brand"] == "Algenta"
    assert body["primary_data_query_contract"]["api"]["contract_endpoint"] == "/v1/meta/contract"
    assert body["primary_data_query_contract"]["mcp"]["contract_tool"] == "get_contract"
    assert body["capability_plane"]["api"]["list_providers_endpoint"] == "/v1/capability-providers"
    assert_manifest_backed_integrations(body["integrations"])


@pytest.mark.anyio
async def test_get_contract_tool_handler_rejects_invalid_payload(monkeypatch) -> None:
    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        return 200, {
            "contract_version": "v1.3",
            "brand": "Algenta",
            "api_base_url": "https://api.codna.ai",
            "mcp_endpoint": "https://api.codna.ai/mcp/sse",
            "mcp_tools_endpoint": "https://api.codna.ai/mcp/tools",
            "auth_scheme": "bearer_api_key",
            "api_key_prefixes": {"live": "de_live_"},
            "compatibility": {
                "legacy_headers": ["X-API-Key"],
                "legacy_env_vars": ["DE_API_KEY", "DE_BASE_URL", "ALGENTA_API_URL"],
                "legacy_domains": ["api.algenta.io"],
                "deprecation_window_days": 90,
            },
            "defaults": {
                "read_only_default": True,
                "write_confirmation_required": True,
                "plan_limits": {"enterprise": {"simulations_per_month": "unlimited"}},
            },
            "primary_data_query_contract": {
                "api": {"contract_endpoint": "/v1/meta/contract"},
                "mcp": {"contract_tool": "get_contract"},
            },
            "capability_plane": {
                "api": {"list_providers_endpoint": "/v1/capability-providers"},
                "enums": {"provider_types": ["mcp_provider"]},
                "direct_sdk": {
                    "typescript": {
                        "import_package": "algenta-sdk",
                        "preferred_client_class": "AlgentaClient",
                        "compatibility_client_class": "DecisionEngineClient",
                        "list_providers_method": "listCapabilityProviders",
                        "get_provider_method": "getCapabilityProvider",
                        "list_bindings_method": "listCapabilityBindings",
                        "create_binding_method": "createCapabilityBinding",
                        "get_binding_method": "getCapabilityBinding",
                        "update_binding_method": "updateCapabilityBinding",
                        "delete_binding_method": "deleteCapabilityBinding",
                        "preview_test_binding_method": "previewTestCapabilityBinding",
                        "test_binding_method": "testCapabilityBinding",
                        "preview_discover_binding_method": "previewDiscoverCapabilityBinding",
                        "discover_binding_method": "discoverCapabilityBinding",
                        "start_authorization_method": "startCapabilityAuthorization",
                        "complete_authorization_method": "completeCapabilityAuthorization",
                        "list_capabilities_method": "listCapabilities",
                        "get_capability_method": "getCapability",
                        "route_capabilities_method": "routeCapabilities",
                        "execute_capability_method": "executeCapability",
                        "record_outcome_method": "recordCapabilityOutcome",
                        "list_skills_method": "listSkills",
                        "enable_skill_method": "enableSkill",
                        "disable_skill_method": "disableSkill",
                        "list_mcp_providers_method": "listMcpProviders"
                    }
                },
                "runtime_sdk": {
                    "typescript": {
                        "import_package": "algenta-sdk",
                        "runtime_class": "Runtime",
                        "list_providers_method": "listCapabilityProviders",
                        "list_bindings_method": "listCapabilityBindings",
                        "list_capabilities_method": "listCapabilities",
                        "route_capabilities_method": "routeCapabilities",
                        "execute_capability_method": "executeCapability",
                        "register_adapter_method": "registerCapabilityAdapter"
                    }
                },
                "mcp": {
                    "list_providers_tool": "list_capability_providers",
                    "list_bindings_tool": "list_capability_bindings",
                    "create_binding_tool": "create_capability_binding",
                    "test_binding_tool": "test_capability_binding",
                    "discover_binding_tool": "discover_capability_binding",
                    "list_capabilities_tool": "list_capabilities",
                    "get_capability_tool": "get_capability",
                    "route_capabilities_tool": "route_capabilities",
                    "execute_capability_tool": "execute_capability",
                    "list_skills_tool": "list_skills",
                    "enable_skill_tool": "enable_skill",
                    "disable_skill_tool": "disable_skill",
                    "compatibility_aliases": ["list_data"]
                },
            },
            "integrations": [],
        }

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match=r"invalid payload: api_key_prefixes\.test",
    ):
        await meta.get_contract_handler({})


@pytest.mark.anyio
async def test_get_contract_tool_handler_falls_back_to_openapi_extension(monkeypatch) -> None:
    seen: list[tuple[str, str, dict[str, object]]] = []

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen.append((method, path, kwargs))
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"contract_endpoint": "/v1/meta/contract"},
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)
    monkeypatch.setattr(meta, "resolve_base_url", lambda: "https://example.test/self-host")

    raw = await meta.get_contract_handler({})
    body = json.loads(raw)

    assert body["api_base_url"] == "https://example.test/self-host"
    assert body["mcp_endpoint"] == "https://example.test/self-host/mcp/sse"
    assert body["primary_data_query_contract"]["mcp"]["contract_tool"] == "get_contract"
    assert_manifest_backed_integrations(body["integrations"])
    assert seen == [
        ("GET", "/v1/meta/contract", {}),
        ("GET", "/openapi.json", {}),
    ]


@pytest.mark.anyio
async def test_get_contract_tool_handler_rejects_invalid_openapi_fallback(monkeypatch) -> None:
    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {}
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {"openapi": "3.1.0"}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match="contract_extension_missing",
    ):
        await meta.get_contract_handler({})


@pytest.mark.anyio
async def test_get_contract_tool_handler_rejects_openapi_fallback_missing_api_section(
    monkeypatch,
) -> None:
    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {}
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        await meta.get_contract_handler({})


@pytest.mark.anyio
async def test_get_contract_tool_handler_rejects_openapi_fallback_missing_contract_endpoint(
    monkeypatch,
) -> None:
    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {}
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"query_batch_endpoint": "/v1/query/batch"},
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        await meta.get_contract_handler({})


@pytest.mark.anyio
async def test_get_contract_tool_handler_rejects_openapi_fallback_invalid_nested_contract_override(
    monkeypatch,
) -> None:
    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs == {}
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"contract_endpoint": "/v1/meta/contract"},
                    "mcp": {"contract_tool": "get_contract"},
                    "runtime_sdk": {
                        "typescript": {"runtime_class": None},
                    },
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        await meta.get_contract_handler({})


@pytest.mark.anyio
async def test_get_runtime_manifest_tool_handler_forwards_manifest_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    expected = get_runtime_manifest().model_dump(mode="json")

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return 200, expected

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    raw = await meta.get_runtime_manifest_handler({})
    body = json.loads(raw)

    assert body["runtime_version"] == expected["runtime_version"]
    assert body["llm_core_manifest"] == "llm-core-v1"
    assert body["shipping_contract"]["module_count"] == 22
    provider_routing_overhead = next(
        entry for entry in body["benchmarking"]["classes"] if entry["code"] == "B8"
    )
    assert provider_routing_overhead == {
        "code": "B8",
        "description": "provider routing overhead",
        "evidence_paths": [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ],
    }
    checkpoint_overhead = next(
        entry for entry in body["benchmarking"]["classes"] if entry["code"] == "B6"
    )
    assert checkpoint_overhead == {
        "code": "B6",
        "description": "checkpoint and replay overhead",
        "evidence_paths": [],
    }
    decision_workflow_completion = next(
        entry for entry in body["benchmarking"]["classes"] if entry["code"] == "B10"
    )
    assert decision_workflow_completion == {
        "code": "B10",
        "description": "decision workflow completion latency",
        "evidence_paths": [
            "build/repository_intelligence_benchmark.json",
            "benchmarks/repository_intelligence_benchmark.py",
            "tests/test_repository_intelligence_benchmark.py",
        ],
    }
    assert body["formal_release_theorem"]["required_conditions"] == [
        "manifest-listed",
        "proof-backed",
        "policy-covered",
        "replay-tested",
        "deployment-mode validated",
    ]


@pytest.mark.anyio
async def test_get_runtime_manifest_tool_handler_rejects_invalid_signed_payload(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    payload = get_runtime_manifest().model_dump(mode="json")
    payload["maturity"]["bpe_tokenizer"] = "legendary"

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return 200, payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: maturity\.bpe_tokenizer",
    ):
        await meta.get_runtime_manifest_handler({})


@pytest.mark.anyio
async def test_get_runtime_release_validation_tool_handler_forwards_validation_payload(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    expected = get_runtime_release_validation().model_dump(mode="json")

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return 200, expected

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    raw = await meta.get_runtime_release_validation_handler({})
    body = json.loads(raw)

    assert body["valid_release"] is True
    assert [entry["condition"] for entry in body["conditions"]] == [
        "manifest-listed",
        "proof-backed",
        "policy-covered",
        "replay-tested",
        "deployment-mode validated",
    ]


@pytest.mark.anyio
async def test_get_runtime_release_validation_tool_handler_rejects_invalid_signed_payload(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["condition"] = "teleport-validated"

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return 200, payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: conditions\.0\.condition",
    ):
        await meta.get_runtime_release_validation_handler({})


@pytest.mark.anyio
async def test_get_runtime_release_validation_tool_handler_rejects_invalid_signed_model_instance(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    payload = get_runtime_release_validation().model_copy(deep=True)
    payload.conditions[0].condition = "teleport-validated"

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return 200, payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: conditions\.0\.condition",
    ):
        await meta.get_runtime_release_validation_handler({})


@pytest.mark.anyio
async def test_get_runtime_modules_tool_handler_forwards_module_catalog(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    expected = get_runtime_admin_modules().model_dump(mode="json")

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return 200, expected

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    raw = await meta.get_runtime_modules_handler({})
    body = json.loads(raw)

    assert body["summary"]["module_count"] == 22
    assert body["modules"][0]["name"] == "bpe_tokenizer"
    assert body["proof_matrix"][0]["layer"] == "mojo_llm_runtime_core"


@pytest.mark.anyio
async def test_get_runtime_modules_tool_handler_rejects_invalid_signed_payload(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["status"] = "unknown_status"

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return 200, payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: proof_matrix\.0\.status",
    ):
        await meta.get_runtime_modules_handler({})


@pytest.mark.anyio
async def test_get_runtime_modules_tool_handler_rejects_invalid_signed_model_instance(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    payload = get_runtime_admin_modules().model_copy(deep=True)
    payload.modules[0].name = "wormhole_kernel"

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return 200, payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: modules\.0\.name",
    ):
        await meta.get_runtime_modules_handler({})


@pytest.mark.anyio
async def test_get_runtime_benchmarks_tool_handler_forwards_benchmark_catalog(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    expected = get_runtime_admin_benchmarks().model_dump(mode="json")

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return 200, expected

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    raw = await meta.get_runtime_benchmarks_handler({})
    body = json.loads(raw)

    assert body["module_benchmarks"][0]["name"] == "bpe_tokenizer"
    assert body["benchmarking"]["classes"][0] == {
        "code": "B1",
        "description": "microkernel latency",
        "evidence_paths": [
            "benchmarks/summary.json",
            "tests/benchmark_mojo_vs_python.py",
        ],
    }
    assert body["slo_budgets"][0]["name"] == "runtime_manifest_load"
    assert body["quality_gate_benchmark_classes"][0] == {
        "code": "B6",
        "description": "checkpoint and replay overhead",
        "evidence_paths": [],
    }
    decision_workflow_completion = next(
        entry for entry in body["quality_gate_benchmark_classes"] if entry["code"] == "B10"
    )
    assert decision_workflow_completion == {
        "code": "B10",
        "description": "decision workflow completion latency",
        "evidence_paths": [
            "build/repository_intelligence_benchmark.json",
            "benchmarks/repository_intelligence_benchmark.py",
            "tests/test_repository_intelligence_benchmark.py",
        ],
    }
    assert {entry["code"] for entry in body["quality_gate_benchmark_classes"]} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert [entry["name"] for entry in body["quality_gate_slo_budgets"]] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert body["evaluation_summary"]["replay_gate_enabled"] is True
    assert body["evaluation_summary"]["tool_call_quality_gate_enabled"] is True
    assert body["evaluation_summary"]["rag_quality_gate_enabled"] is True
    assert body["evaluation_summary"]["decision_quality_gate_enabled"] is True


@pytest.mark.anyio
async def test_get_runtime_benchmarks_tool_handler_rejects_invalid_signed_payload(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["name"] = "wormhole_kernel"

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return 200, payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: module_benchmarks\.0\.name",
    ):
        await meta.get_runtime_benchmarks_handler({})


@pytest.mark.anyio
async def test_get_runtime_benchmarks_tool_handler_rejects_invalid_signed_model_instance(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    payload = get_runtime_admin_benchmarks().model_copy(deep=True)
    payload.module_benchmarks[0].name = "wormhole_kernel"

    async def _fake_api_with_status(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return 200, payload

    monkeypatch.setattr(meta, "api_with_status", _fake_api_with_status)

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: module_benchmarks\.0\.name",
    ):
        await meta.get_runtime_benchmarks_handler({})
