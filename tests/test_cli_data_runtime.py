"""Tests for CLI runtime commands.

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


def test_cmd_contract_prints_machine_readable_contract_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (200, _platform_contract_payload()),
    )

    output = _capture_stdout(cli.cmd_contract, "table")

    assert "Algenta contract: v1.5" in output
    assert "/v1/meta/contract" in output
    assert "get_contract() / get_contract()" in output
    assert "getContract() / getContract()" in output
    assert MANIFEST_BACKED_INTEGRATIONS_DISPLAY in output
    assert f"Read-only:       {MANIFEST_BACKED_READ_ONLY_DISPLAY}" in output
    assert "de contract" in output
    assert "get_contract" in output
    assert "record_predicates selectors=column, dimension_hint" in output
    assert "eq, gt, gte, lt, lte, in, is_null, is_not_null" in output


def test_cmd_contract_json_emits_manifest_backed_integration_inventory(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    expected_payload = _platform_contract_payload()
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (200, expected_payload),
    )

    output = _capture_stdout(cli.cmd_contract, "json")
    body = json.loads(output)
    assert_manifest_backed_integrations(body["integrations"])


def test_cmd_contract_falls_back_to_openapi_extension(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {
                        "contract_endpoint": "/v1/meta/contract",
                        "summary_endpoint": "/v1/data/{dataset_id}/summary",
                        "query_endpoint": "/v1/query",
                        "query_batch_endpoint": "/v1/query/batch",
                        "query_sql_report_endpoint": "/v1/query/sql-report",
                    },
                    "governed_filter_contract": {
                        "kind": "record_predicates",
                        "selector_fields": ["column", "dimension_hint"],
                        "operators": {
                            "scalar": ["eq", "gt", "gte", "lt", "lte"],
                            "list": ["in"],
                            "nullary": ["is_null", "is_not_null"],
                        },
                    },
                    "direct_sdk": {
                        "python": {"contract_method": "get_contract"},
                        "typescript": {"contract_method": "getContract"},
                    },
                    "runtime_sdk": {
                        "python": {"contract_method": "get_contract"},
                        "typescript": {"contract_method": "getContract"},
                    },
                    "cli": {"contract_command": "de contract"},
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    output = _capture_stdout(cli.cmd_contract, "table")

    assert "https://example.test/self-host" in output
    assert "/v1/meta/contract" in output
    assert MANIFEST_BACKED_INTEGRATIONS_DISPLAY in output
    assert f"Read-only:       {MANIFEST_BACKED_READ_ONLY_DISPLAY}" in output
    assert "de contract" in output
    assert "record_predicates selectors=column, dimension_hint" in output


def test_cmd_contract_json_falls_back_to_openapi_extension(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {
                        "contract_endpoint": "/v1/meta/contract",
                        "query_batch_endpoint": "/v1/query/batch",
                    },
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    output = _capture_stdout(cli.cmd_contract, "json")
    body = json.loads(output)

    assert body["api_base_url"] == "https://example.test/self-host"
    assert body["mcp_endpoint"] == "https://example.test/self-host/mcp"
    assert body["mcp_tools_endpoint"] == "https://example.test/self-host/mcp/tools"
    assert body["primary_data_query_contract"]["api"]["query_batch_endpoint"] == "/v1/query/batch"
    assert_manifest_backed_integrations(body["integrations"])


def test_cmd_contract_rejects_invalid_openapi_fallback(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
        if (method, path) == ("GET", "/v1/meta/contract"):
            return 404, {"error": {"code": "not_found"}}
        if (method, path) == ("GET", "/openapi.json"):
            return 200, {"openapi": "3.1.0"}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    with pytest.raises(
        RuntimeError,
        match="contract_extension_missing",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_contract_rejects_openapi_fallback_missing_api_section(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
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

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_contract_rejects_openapi_fallback_missing_contract_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
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

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_contract_rejects_openapi_fallback_invalid_nested_contract_override(
    monkeypatch,
) -> None:
    monkeypatch.setattr(cli, "_RICH", False)

    def _fake_api_request(method: str, path: str, body=None):
        assert body is None
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

    monkeypatch.setattr(cli, "api_request", _fake_api_request)
    monkeypatch.setattr(cli, "_get_base_url", lambda: "https://example.test/self-host")

    with pytest.raises(
        RuntimeError,
        match="invalid_contract_payload",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_contract_rejects_invalid_payload(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            {
                "contract_version": "v1.3",
                "brand": "Algenta",
                "api_base_url": "https://api.algenta.ai",
                "mcp_endpoint": "https://api.algenta.ai/mcp",
                "mcp_transport": "streamable_http",
                "mcp_protocol_version": "2025-11-25",
                "mcp_legacy_sse_endpoint": "https://api.algenta.ai/mcp/sse",
                "mcp_tools_endpoint": "https://api.algenta.ai/mcp/tools",
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
                    "plan_limits": {
                        "enterprise": {"simulations_per_month": "unlimited"},
                    },
                },
                "primary_data_query_contract": {
                    "api": {"contract_endpoint": "/v1/meta/contract"},
                    "mcp": {"contract_tool": "get_contract"},
                },
                "integrations": [],
            },
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=r"invalid payload: api_key_prefixes\.test",
    ):
        _capture_stdout(cli.cmd_contract, "table")


def test_cmd_runtime_manifest_prints_runtime_foundation_summary(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    monkeypatch.setattr(cli, "_RICH", False)
    manifest = get_runtime_manifest().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            manifest,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_manifest, "table")

    assert "Algenta runtime manifest:" in output
    assert "llm-core-v1" in output
    assert "22 shipping / 22 listed" in output
    assert "Functions:       209" in output
    assert "python_sdk, typescript_sdk, cli, mcp" in output
    assert "channel_covered=22" in output
    assert "manifest-listed" in output

    json_output = _capture_stdout(cli.cmd_runtime_manifest, "json")
    payload = json.loads(json_output)
    provider_routing_overhead = next(
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] == "B8"
    )
    assert provider_routing_overhead["description"] == "provider routing overhead"
    assert provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    checkpoint_overhead = next(
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] == "B6"
    )
    assert checkpoint_overhead["description"] == "checkpoint and replay overhead"
    assert checkpoint_overhead["evidence_paths"] == []


def test_cmd_runtime_manifest_rejects_invalid_signed_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    monkeypatch.setattr(cli, "_RICH", False)
    manifest = get_runtime_manifest().model_dump(mode="json")
    manifest["maturity"]["bpe_tokenizer"] = "legendary"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, manifest))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: maturity\.bpe_tokenizer",
    ):
        cli.cmd_runtime_manifest("table")


def test_cmd_runtime_validate_prints_release_verdict(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    monkeypatch.setattr(cli, "_RICH", False)
    validation = get_runtime_release_validation().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            validation,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_validate, "table")

    assert "Algenta runtime release validation:" in output
    assert "-> valid" in output
    assert "manifest-listed: pass" in output
    assert "deployment-mode validated: pass" in output


def test_cmd_runtime_validate_prefers_raw_deployment_mode_when_typed_mode_is_missing(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    monkeypatch.setattr(cli, "_RICH", False)
    validation = get_runtime_release_validation().model_dump(mode="json")
    validation["deployment_mode"] = None
    validation["deployment_mode_raw"] = "shadow_realm"
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            validation,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_validate, "table")

    assert "Deployment:      shadow_realm" in output


def test_cmd_runtime_validate_rejects_invalid_signed_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    monkeypatch.setattr(cli, "_RICH", False)
    validation = get_runtime_release_validation().model_dump(mode="json")
    validation["conditions"][0]["condition"] = "teleport-validated"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, validation))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: conditions\.0\.condition",
    ):
        cli.cmd_runtime_validate("table")


def test_cmd_runtime_validate_rejects_invalid_signed_model_instance(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_release_validation().model_copy(deep=True)
    payload.conditions[0].condition = "teleport-validated"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: conditions\.0\.condition",
    ):
        cli.cmd_runtime_validate("json")


def test_cmd_runtime_admin_modules_prints_signed_module_catalog(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_modules().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            payload,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_admin_modules, "table")

    assert "Algenta runtime module catalog:" in output
    assert "22 modules / 209 functions" in output
    assert "mojo_llm_runtime_core [channel_covered]" in output
    assert "bpe_tokenizer" in output


def test_cmd_runtime_admin_modules_rejects_invalid_signed_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["status"] = "unknown_status"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: proof_matrix\.0\.status",
    ):
        cli.cmd_runtime_admin_modules("table")


def test_cmd_runtime_admin_modules_rejects_invalid_signed_model_instance(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_modules().model_copy(deep=True)
    payload.modules[0].name = "wormhole_kernel"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: modules\.0\.name",
    ):
        cli.cmd_runtime_admin_modules("json")


def test_cmd_runtime_admin_benchmarks_prints_signed_benchmark_catalog(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            payload,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_admin_benchmarks, "table")

    assert "Algenta runtime benchmark catalog:" in output
    discovery = payload["benchmark_discovery_lane"]
    assert (
        f"{discovery['discovered_source_modules']} source modules / "
        f"{discovery['shipping_manifest_modules']} shipping modules"
    ) in output
    assert "runtime_manifest_load: p95 25.0 ms / ceiling 100.0 ms" in output
    assert "Evaluation:      10 dimensions / 8 methods / 6 release blockers" in output
    assert "Quality gates:   replay=on, tool_call=on, rag=on, decision=on" in output
    assert "Benchmark classes:" in output
    assert "B1: microkernel latency" in output
    assert "benchmarks/summary.json, tests/benchmark_mojo_vs_python.py" in output
    assert "Quality gate benchmark classes:" in output
    assert "B6: checkpoint and replay overhead [evidence: none]" in output
    assert "bpe_tokenizer" in output


def test_cmd_runtime_admin_benchmarks_json_keeps_benchmark_class_evidence_paths(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    monkeypatch.setattr(
        cli,
        "api_request",
        lambda method, path, body=None: (
            200,
            payload,
        ),
    )

    output = _capture_stdout(cli.cmd_runtime_admin_benchmarks, "json")
    parsed = json.loads(output)

    provider_routing_overhead = next(
        entry for entry in parsed["benchmarking"]["classes"] if entry["code"] == "B8"
    )
    assert provider_routing_overhead["description"] == "provider routing overhead"
    assert provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    checkpoint_overhead = next(
        entry
        for entry in parsed["quality_gate_benchmark_classes"]
        if entry["code"] == "B6"
    )
    assert checkpoint_overhead["description"] == "checkpoint and replay overhead"
    assert checkpoint_overhead["evidence_paths"] == []
    assert {entry["code"] for entry in parsed["quality_gate_benchmark_classes"]} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert [entry["name"] for entry in parsed["quality_gate_slo_budgets"]] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert parsed["evaluation_summary"]["replay_gate_enabled"] is True
    assert parsed["evaluation_summary"]["tool_call_quality_gate_enabled"] is True
    assert parsed["evaluation_summary"]["rag_quality_gate_enabled"] is True
    assert parsed["evaluation_summary"]["decision_quality_gate_enabled"] is True


def test_cmd_runtime_admin_benchmarks_rejects_invalid_signed_payload(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["name"] = "wormhole_kernel"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: module_benchmarks\.0\.name",
    ):
        cli.cmd_runtime_admin_benchmarks("table")


def test_cmd_runtime_admin_benchmarks_rejects_invalid_signed_model_instance(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    monkeypatch.setattr(cli, "_RICH", False)
    payload = get_runtime_admin_benchmarks().model_copy(deep=True)
    payload.module_benchmarks[0].name = "wormhole_kernel"
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    with pytest.raises(
        RuntimeError,
        match=r"invalid signed payload: module_benchmarks\.0\.name",
    ):
        cli.cmd_runtime_admin_benchmarks("json")


def test_cmd_deployments_regions_prints_provider_inventory(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "providers": [
            {
                "id": "algenta_shared",
                "name": "Algenta Managed",
                "regions": [
                    {"id": "algenta-shared", "label": "Algenta Shared", "location": "Global"}
                ],
            }
        ]
    }
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_deployments_regions, "table")

    assert "Deployment providers:" in output
    assert "algenta_shared: Algenta Managed" in output
    assert "Algenta Shared" in output


def test_cmd_deployments_get_prints_active_deployment(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "deployment_id": "dep_123",
        "provider": "algenta_shared",
        "region": "algenta-shared",
        "status": "requested",
        "endpoint_url": "https://example.test/runtime",
        "cost_usd_month": 12.5,
        "billable_cost_usd_month": 15.0,
        "billing_markup_pct": 20.0,
    }
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_deployments_get, "table")

    assert "Deployment ID:       dep_123" in output
    assert "Provider:            algenta_shared" in output
    assert "Status:              requested" in output


def test_cmd_deployments_create_posts_request_file_and_prints_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    request_path = tmp_path / "deployment_request.json"
    request_path.write_text(
        json.dumps(
            {
                "provider": "aws",
                "region": "us-east-1",
                "config": {"instance_size": "medium"},
                "billing_markup_pct": 25.0,
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def _fake_api_request(method: str, path: str, body=None):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        return (
            202,
            {
                "deployment_id": "dep_123",
                "provider": "aws",
                "region": "us-east-1",
                "status": "requested",
                "billing_markup_pct": 25.0,
            },
        )

    monkeypatch.setattr(cli, "api_request", _fake_api_request)

    output = _capture_stdout(cli.cmd_deployments_create, str(request_path), "table")

    assert captured == {
        "method": "POST",
        "path": "/v1/deployments",
        "body": {
            "provider": "aws",
            "region": "us-east-1",
            "config": {"instance_size": "medium"},
            "billing_markup_pct": 25.0,
        },
    }
    assert "Deployment ID:       dep_123" in output
    assert "Billing markup pct:  25.0" in output


def test_cmd_deployments_cost_prints_cost_summary(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {
        "deployment_id": "dep_123",
        "provider": "algenta_shared",
        "region": "algenta-shared",
        "year": 2026,
        "month": 5,
        "cost_usd_month": 12.5,
        "billable_cost_usd_month": 15.0,
        "billing_markup_pct": 20.0,
        "last_updated": "2026-05-24T12:30:00Z",
    }
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (200, payload))

    output = _capture_stdout(cli.cmd_deployments_cost, "dep_123", "table")

    assert "Deployment ID:       dep_123" in output
    assert "Month:               2026-05" in output
    assert "Cost USD/month:      12.5" in output


def test_cmd_deployments_delete_prints_transition(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_RICH", False)
    payload = {"status": "deprovisioning", "deployment_id": "dep_123"}
    monkeypatch.setattr(cli, "api_request", lambda method, path, body=None: (202, payload))

    output = _capture_stdout(cli.cmd_deployments_delete, "dep_123", "table")

    assert "Deployment ID: dep_123" in output
    assert "Status:        deprovisioning" in output


def test_main_dispatches_contract(monkeypatch) -> None:
    called: list[str] = []

    def _fake_cmd_contract(format: str = "table") -> None:
        called.append(format)

    monkeypatch.setattr(cli, "cmd_contract", _fake_cmd_contract)
    monkeypatch.setattr(cli.sys, "argv", ["de", "contract", "--format", "json"])

    cli.main()

    assert called == ["json"]


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["de", "deployments", "regions", "--format", "json"],
            "cmd_deployments_regions",
            {"format": "json"},
        ),
        (
            ["de", "deployments", "get"],
            "cmd_deployments_get",
            {"format": "table"},
        ),
        (
            ["de", "deployments", "create", "deployment.json", "--format", "json"],
            "cmd_deployments_create",
            {"request_path": "deployment.json", "format": "json"},
        ),
        (
            ["de", "deployments", "cost", "dep_123"],
            "cmd_deployments_cost",
            {"deployment_id": "dep_123", "format": "table"},
        ),
        (
            ["de", "deployments", "delete", "dep_123", "--format", "json"],
            "cmd_deployments_delete",
            {"deployment_id": "dep_123", "format": "json"},
        ),
    ],
)
def test_main_dispatches_deployment_commands(
    monkeypatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    called: dict[str, object] = {}

    if handler_name == "cmd_deployments_create":
        def _fake_cmd(request_path: str, format: str = "table") -> None:
            called["request_path"] = request_path
            called["format"] = format
    elif handler_name in {"cmd_deployments_cost", "cmd_deployments_delete"}:
        def _fake_cmd(deployment_id: str, format: str = "table") -> None:
            called["deployment_id"] = deployment_id
            called["format"] = format
    else:
        def _fake_cmd(format: str = "table") -> None:
            called["format"] = format

    monkeypatch.setattr(cli, handler_name, _fake_cmd)
    monkeypatch.setattr(cli.sys, "argv", argv)

    cli.main()

    assert called == expected


def test_cmd_runtime_history_prints_recent_events(monkeypatch, tmp_path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    ledger = runtime_dir / "history.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": 1_700_000_000,
                        "status": "started",
                        "target": "monte_carlo.run",
                        "engine_used": None,
                        "latency_ms": None,
                        "error": None,
                    }
                ),
                json.dumps(
                    {
                        "timestamp": 1_700_000_001,
                        "status": "completed",
                        "target": "monte_carlo.run",
                        "engine_used": "python-fallback",
                        "latency_ms": 12.34,
                        "error": None,
                    }
                ),
            ]
        )
    )
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir))
    output = _capture_stdout(cli.cmd_runtime_history, 10, "table")
    assert "Runtime history (2 events)" in output
    assert "monte_carlo.run" in output
    assert "python-fallback" in output


def test_main_dispatches_runtime_history(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_runtime_history(limit: int = 20, format: str = "table") -> None:
        called["limit"] = limit
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_runtime_history", _fake_cmd_runtime_history)
    monkeypatch.setattr(
        cli.sys, "argv", ["de", "runtime", "history", "--limit", "5", "--format", "json"]
    )

    cli.main()

    assert called == {"limit": 5, "format": "json"}


def test_main_dispatches_runtime_admin_modules(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_runtime_admin_modules(format: str = "table") -> None:
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_runtime_admin_modules", _fake_cmd_runtime_admin_modules)
    monkeypatch.setattr(
        cli.sys, "argv", ["de", "runtime", "admin-modules", "--format", "json"]
    )

    cli.main()

    assert called == {"format": "json"}


def test_main_dispatches_runtime_admin_benchmarks(monkeypatch) -> None:
    called: dict[str, object] = {}

    def _fake_cmd_runtime_admin_benchmarks(format: str = "table") -> None:
        called["format"] = format

    monkeypatch.setattr(cli, "cmd_runtime_admin_benchmarks", _fake_cmd_runtime_admin_benchmarks)
    monkeypatch.setattr(
        cli.sys, "argv", ["de", "runtime", "admin-benchmarks", "--format", "json"]
    )

    cli.main()

    assert called == {"format": "json"}
