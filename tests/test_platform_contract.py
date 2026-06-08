from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import ValidationError

from apps import platform_contract
from apps.api_server.main import app
from tests import _manifest_backed_integrations as manifest_helpers
from tests._manifest_backed_integrations import (
    MANIFEST_BACKED_INTEGRATIONS,
    NORMALIZED_MANIFEST_BACKED_INTEGRATIONS,
    assert_manifest_backed_integration_texts_equal,
    assert_manifest_backed_integrations,
    contract_integrations_match_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "apps" / "docs" / "integration_manifest.v1.json"
EXAMPLE_BASE_URL = "https://your-algenta-base-url.example"
EXAMPLE_MCP_ENDPOINT = f"{EXAMPLE_BASE_URL}/mcp/sse"


def test_manifest_declares_canonical_contract() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["brand"] == "Algenta"
    assert manifest["api_base_url"] == "https://api.algenta.ai"
    assert manifest["mcp_endpoint"] == "https://api.algenta.ai/mcp/sse"
    assert manifest["auth_scheme"] == "bearer_api_key"
    assert manifest["api_key_prefixes"] == {"live": "de_live_", "test": "de_test_"}
    assert manifest["compatibility"]["deprecation_window_days"] == 90
    assert manifest["privacy_registry"]["algenta_owned_hosts"][0] == "algenta.ai"
    assert manifest["privacy_registry"]["algenta_owned_suffixes"] == [
        ".algenta.ai",
        ".algenta.io",
        ".decisionengine.io",
    ]
    assert "api.stripe.com" in manifest["privacy_registry"]["vendor_telemetry_hosts"]
    assert ".home.arpa" in manifest["privacy_registry"]["private_host_suffixes"]
    assert_manifest_backed_integrations(manifest["integrations"])
    data_query = manifest["primary_data_query_contract"]
    assert data_query["api"]["contract_endpoint"] == "/v1/meta/contract"
    assert data_query["api"]["discovery_endpoint"] == "/v1/data"
    assert data_query["api"]["summary_endpoint"] == "/v1/data/{dataset_id}/summary"
    assert data_query["api"]["query_batch_endpoint"] == "/v1/query/batch"
    assert data_query["api"]["query_sql_report_endpoint"] == "/v1/query/sql-report"
    assert data_query["governed_filter_contract"]["kind"] == "record_predicates"
    assert data_query["governed_filter_contract"]["selector_fields"] == ["column", "dimension_hint"]
    assert data_query["governed_filter_contract"]["operators"]["scalar"] == [
        "eq",
        "gt",
        "gte",
        "lt",
        "lte",
    ]
    assert data_query["governed_filter_contract"]["operators"]["list"] == ["in"]
    assert data_query["governed_filter_contract"]["operators"]["nullary"] == [
        "is_null",
        "is_not_null",
    ]
    assert data_query["governed_filter_contract"]["type_behavior"]["boolean"] == ["eq"]
    assert data_query["governed_filter_contract"]["validation"]["requires_selector"] is True
    assert data_query["governed_filter_contract"]["supports_non_sql_backends"] is True
    assert data_query["direct_sdk"]["python"]["import_root"] == "decision_engine"
    assert data_query["direct_sdk"]["python"]["preferred_client_class"] == "AlgentaClient"
    assert (
        data_query["direct_sdk"]["python"]["preferred_async_client_class"] == "AsyncAlgentaClient"
    )
    assert data_query["direct_sdk"]["python"]["contract_method"] == "get_contract"
    assert data_query["direct_sdk"]["typescript"]["import_package"] == "algenta-sdk"
    assert data_query["direct_sdk"]["typescript"]["preferred_client_class"] == "AlgentaClient"
    assert data_query["direct_sdk"]["typescript"]["contract_method"] == "getContract"
    assert data_query["direct_sdk"]["python"]["query_with_metadata_method"] == "query_with_metadata"
    assert data_query["direct_sdk"]["typescript"]["query_batch_method"] == "queryBatch"
    assert data_query["runtime_sdk"]["python"]["import_root"] == "algenta"
    assert data_query["runtime_sdk"]["python"]["runtime_class"] == "Runtime"
    assert data_query["runtime_sdk"]["python"]["libraries_entrypoint"] == "libraries"
    assert data_query["runtime_sdk"]["python"]["contract_method"] == "get_contract"
    assert data_query["runtime_sdk"]["typescript"]["import_package"] == "algenta-sdk"
    assert data_query["runtime_sdk"]["typescript"]["runtime_class"] == "Runtime"
    assert data_query["runtime_sdk"]["typescript"]["libraries_entrypoint"] == "libraries"
    assert data_query["runtime_sdk"]["typescript"]["contract_method"] == "getContract"
    assert data_query["runtime_sdk"]["python"]["summary_method"] == "get_dataset_summary"
    assert data_query["runtime_sdk"]["typescript"]["query_sql_report_method"] == "querySqlReport"
    assert data_query["cli"]["contract_command"] == "de contract"
    assert data_query["cli"]["summary_command"] == "de data summary <dataset_id>"
    assert data_query["cli"]["runtime_modules_command"] == "de runtime modules"
    assert data_query["cli"]["runtime_functions_command"] == "de runtime functions <module>"
    assert (
        data_query["cli"]["runtime_execute_command"]
        == "de runtime execute <module> <function> --args-json '<json>'"
    )
    assert data_query["mcp"]["contract_tool"] == "get_contract"
    assert data_query["mcp"]["query_batch_tool"] == "query_batch"
    assert data_query["mcp"]["runtime_library_list_tool"] == "list_runtime_libraries"
    assert data_query["mcp"]["runtime_library_execute_tool"] == "execute_runtime_library"
    assert data_query["recommended_flows"]["machine_readable_contract"] == ["GET /v1/meta/contract"]
    assert data_query["recommended_flows"]["governed_query"] == [
        "GET /v1/data?search=...&compact=1",
        "GET /v1/data/{dataset_id}/summary",
        "POST /v1/resolve",
        "POST /v1/verify",
        "POST /v1/query",
    ]


def test_manifest_backed_integration_fixture_matches_canonical_manifest() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["integrations"] == list(MANIFEST_BACKED_INTEGRATIONS)


def test_contract_integrations_match_manifest_fails_closed_for_malformed_input() -> None:
    assert contract_integrations_match_manifest([object()]) is False


def test_contract_integrations_match_manifest_fails_closed_for_empty_sequences() -> None:
    assert contract_integrations_match_manifest([]) is False


def test_contract_integrations_match_manifest_accepts_attribute_backed_fixture_payload() -> None:
    integrations = [
        SimpleNamespace(
            **{
                **integration,
                "capabilities": tuple(integration["capabilities"]),
                "required_scopes": tuple(integration["required_scopes"]),
                "write_actions": tuple(integration["write_actions"]),
                "admin_controls": tuple(integration["admin_controls"]),
                "regions": tuple(integration["regions"]),
            }
        )
        for integration in MANIFEST_BACKED_INTEGRATIONS
    ]

    assert contract_integrations_match_manifest(integrations) is True


def test_contract_integrations_match_manifest_fails_closed_for_drifted_payload() -> None:
    drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    drifted_integrations[0] = {
        **drifted_integrations[0],
        "status": "deprecated",
    }

    assert contract_integrations_match_manifest(drifted_integrations) is False


def test_normalize_manifest_backed_integrations_supports_attribute_backed_sequences() -> None:
    integrations = [
        SimpleNamespace(
            **{
                **integration,
                "capabilities": tuple(integration["capabilities"]),
                "required_scopes": tuple(integration["required_scopes"]),
                "write_actions": tuple(integration["write_actions"]),
                "admin_controls": tuple(integration["admin_controls"]),
                "regions": tuple(integration["regions"]),
            }
        )
        for integration in MANIFEST_BACKED_INTEGRATIONS
    ]

    assert manifest_helpers.normalize_manifest_backed_integrations(integrations) == (
        NORMALIZED_MANIFEST_BACKED_INTEGRATIONS
    )


def test_normalize_manifest_backed_integrations_rejects_empty_sequences() -> None:
    with pytest.raises(AssertionError, match="expected manifest-backed integrations"):
        manifest_helpers.normalize_manifest_backed_integrations([])


def test_assert_manifest_backed_integrations_rejects_drifted_payload() -> None:
    drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    drifted_integrations[0] = {
        **drifted_integrations[0],
        "status": "deprecated",
    }

    with pytest.raises(AssertionError):
        assert_manifest_backed_integrations(drifted_integrations)


def test_assert_manifest_backed_integrations_equal_rejects_drifted_payloads() -> None:
    drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    drifted_integrations[0] = {
        **drifted_integrations[0],
        "status": "deprecated",
    }

    with pytest.raises(AssertionError):
        manifest_helpers.assert_manifest_backed_integrations_equal(
            list(MANIFEST_BACKED_INTEGRATIONS),
            drifted_integrations,
        )


def test_assert_manifest_backed_integrations_equal_accepts_matching_drifted_payloads() -> None:
    left_drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    left_drifted_integrations[0] = {
        **left_drifted_integrations[0],
        "status": "deprecated",
    }
    right_drifted_integrations = list(left_drifted_integrations)

    manifest_helpers.assert_manifest_backed_integrations_equal(
        left_drifted_integrations,
        right_drifted_integrations,
    )


def test_manifest_export_text_helper_accepts_matching_esm_and_commonjs_exports() -> None:
    payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))
    esm_text = f"export const INTEGRATIONS = {payload};"
    cjs_text = f"exports.INTEGRATIONS = {payload};"

    assert_manifest_backed_integration_texts_equal(esm_text, cjs_text)


def test_manifest_export_text_helper_accepts_identical_export_texts() -> None:
    payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))
    text = f"export const INTEGRATIONS = {payload};"

    assert_manifest_backed_integration_texts_equal(text, text)


def test_manifest_export_text_helper_rejects_identical_drifted_export_texts() -> None:
    drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    drifted_integrations[0] = {
        **drifted_integrations[0],
        "status": "deprecated",
    }
    text = f"export const INTEGRATIONS = {json.dumps(drifted_integrations)};"

    with pytest.raises(AssertionError):
        assert_manifest_backed_integration_texts_equal(text, text)


def test_manifest_export_text_helper_rejects_missing_integration_export() -> None:
    payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))

    with pytest.raises(AssertionError, match="missing exported INTEGRATIONS array"):
        assert_manifest_backed_integration_texts_equal(
            f"export const INTEGRATIONS = {payload};",
            "export const CONTRACT_VERSION = '2026.05.0';",
        )


def test_manifest_export_text_helper_rejects_missing_left_hand_integration_export() -> None:
    payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))

    with pytest.raises(AssertionError, match="missing exported INTEGRATIONS array"):
        assert_manifest_backed_integration_texts_equal(
            "export const CONTRACT_VERSION = '2026.05.0';",
            f"exports.INTEGRATIONS = {payload};",
        )


def test_manifest_export_text_helper_rejects_matching_drifted_payloads() -> None:
    left_drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    left_drifted_integrations[0] = {
        **left_drifted_integrations[0],
        "status": "deprecated",
    }
    right_drifted_integrations = list(left_drifted_integrations)

    with pytest.raises(AssertionError):
        assert_manifest_backed_integration_texts_equal(
            f"export const INTEGRATIONS = {json.dumps(left_drifted_integrations)};",
            f"exports.INTEGRATIONS = {json.dumps(right_drifted_integrations)};",
        )


def test_manifest_export_text_helper_rejects_mismatched_integration_payloads() -> None:
    left_payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))
    mismatched_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    mismatched_integrations[0] = {
        **mismatched_integrations[0],
        "status": "deprecated",
    }
    right_payload = json.dumps(mismatched_integrations)

    with pytest.raises(AssertionError):
        assert_manifest_backed_integration_texts_equal(
            f"export const INTEGRATIONS = {left_payload};",
            f"exports.INTEGRATIONS = {right_payload};",
        )


def test_load_platform_contract_manifest_model_validates_full_primary_contract_shape() -> None:
    platform_contract.clear_platform_contract_caches()
    manifest = platform_contract.load_platform_contract_manifest_model()
    assert (
        manifest.primary_data_query_contract.runtime_sdk.typescript.libraries_entrypoint
        == "libraries"
    )
    assert manifest.primary_data_query_contract.cli.runtime_execute_command.startswith(
        "de runtime execute"
    )


def test_load_platform_contract_manifest_model_rejects_non_object_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "integration_manifest.invalid.json"
    manifest_path.write_text(json.dumps(["not-an-object"]))
    monkeypatch.setattr(platform_contract, "MANIFEST_PATH", manifest_path)
    platform_contract.clear_platform_contract_caches()

    with pytest.raises(
        platform_contract.PlatformContractManifestError,
        match="JSON object",
    ) as exc:
        platform_contract.load_platform_contract_manifest_model()
    assert exc.value.code == "invalid_platform_contract_manifest"


def test_load_platform_contract_manifest_model_rejects_invalid_nested_contract_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    manifest["primary_data_query_contract"]["runtime_sdk"]["typescript"].pop("runtime_class")
    manifest_path = tmp_path / "integration_manifest.invalid.json"
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(platform_contract, "MANIFEST_PATH", manifest_path)
    platform_contract.clear_platform_contract_caches()

    with pytest.raises(
        platform_contract.PlatformContractManifestError,
        match="canonical Algenta contract schema",
    ) as exc:
        platform_contract.load_platform_contract_manifest_model()
    assert exc.value.code == "invalid_platform_contract_manifest"


def test_validate_platform_contract_payload_rejects_invalid_signed_model_instance() -> None:
    payload = platform_contract.load_platform_contract_manifest_model().model_copy(
        update={"api_key_prefixes": {"live": "de_live_", "test": 7}}
    )

    with pytest.raises(
        platform_contract.PlatformContractManifestError,
        match="api_key_prefixes.test",
    ) as exc:
        platform_contract.validate_platform_contract_payload(payload)

    assert exc.value.code == "invalid_platform_contract_manifest"
    assert exc.value.details["cause"] == "api_key_prefixes.test"
    assert exc.value.details["validation_errors"][0]["path"] == "api_key_prefixes.test"


def test_platform_contract_models_reject_tuple_backed_list_fields() -> None:
    payload = json.loads(MANIFEST_PATH.read_text())
    payload["compatibility"]["legacy_headers"] = ("X-Deprecated-Key",)

    with pytest.raises(ValidationError) as exc_info:
        platform_contract.PlatformContractResponse.model_validate(payload)

    error_text = str(exc_info.value)
    assert "compatibility" in error_text
    assert "legacy_headers must be provided as a list" in error_text


def test_platform_contract_models_build_json_schema() -> None:
    schema = platform_contract.PlatformContractResponse.model_json_schema()
    assert schema["type"] == "object"
    assert schema["properties"]


def test_manifest_integrations_have_required_fields() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    required = {
        "name",
        "description",
        "icon",
        "capabilities",
        "auth_scheme",
        "required_scopes",
        "read_only_default",
        "write_actions",
        "admin_controls",
        "docs_url",
        "privacy_url",
        "terms_url",
        "support_url",
        "regions",
        "status",
    }
    integrations = manifest["integrations"]
    assert integrations
    for integration in integrations:
        assert required.issubset(integration)


def test_api_reference_documents_machine_readable_discovery_contract() -> None:
    api_reference = (ROOT / "apps" / "docs" / "docs" / "api-reference" / "index.md").read_text()
    assert "x-canonical-mcp-endpoint" in api_reference
    assert "x-primary-data-query-contract" in api_reference
    assert "governed_filter_contract" in api_reference
    assert "decision_engine.AlgentaClient" in api_reference
    assert "algenta.Runtime" in api_reference
    assert "algenta.libraries" in api_reference


def test_makefile_openapi_target_uses_repo_python_and_validates_generated_spec() -> None:
    makefile_text = (ROOT / "Makefile").read_text()
    assert "mkdir -p schemas/openapi" in makefile_text
    assert "curl -fsS http://localhost:8000/openapi.json" in makefile_text
    assert "yaml.safe_dump" in makefile_text
    assert "from openapi_spec_validator import validate_spec" in makefile_text
    assert "scripts/convert_openapi.py" not in makefile_text


def test_makefile_contract_target_runs_real_contract_inventory() -> None:
    makefile_text = (ROOT / "Makefile").read_text()
    requirements_text = (ROOT / "requirements-dev.txt").read_text()
    assert "CONTRACT_PYTEST_FILES" in makefile_text
    assert "CONTRACT_SCRIPT_FILES := tests/integration/test_openapi.py" in makefile_text
    assert "pytest $(CONTRACT_PYTEST_FILES) -v --tb=short" in makefile_text
    assert '"$$PY_BIN" $(CONTRACT_SCRIPT_FILES)' in makefile_text
    assert "pytest tests/contract/" not in makefile_text
    assert "openapi-spec-validator==0.9.0" in requirements_text


def test_direct_api_client_docs_cover_manifest_first_runtime_and_control_plane_helpers() -> None:
    direct_api = (ROOT / "apps" / "docs" / "docs" / "direct-api-client.md").read_text()

    assert "## Persisted runtime and control-plane helpers" in direct_api
    assert "`client.list_agent_runs(...)`" in direct_api
    assert "`client.list_agent_run_checkpoints(run_id)`" in direct_api
    assert "`client.query_agent_run_checkpoints(...)`" in direct_api
    assert "`client.list_agent_run_mission_events(run_id, limit=...)`" in direct_api
    assert "`client.query_agent_run_mission_events(...)`" in direct_api
    assert "`client.list_agent_run_telemetry(run_id, limit=...)`" in direct_api
    assert "`client.query_agent_run_telemetry(...)`" in direct_api
    assert "`client.replay_agent_run(run_id, checkpoint_id=...)`" in direct_api
    assert "`client.fork_agent_run(run_id, checkpoint_id=...)`" in direct_api
    assert "`client.get_audit_logs(...)`" in direct_api
    assert "`client.get_audit_log_artifacts(...)`" in direct_api
    assert "`client.list_execution_policy_snapshots()`" in direct_api
    assert "`client.listAgentRuns({ ... })`" in direct_api
    assert "`client.listAgentRunCheckpoints(runId)`" in direct_api
    assert "`client.queryAgentRunCheckpoints({ ... })`" in direct_api
    assert "`client.listAgentRunMissionEvents(runId, { limit })`" in direct_api
    assert "`client.queryAgentRunMissionEvents({ ... })`" in direct_api
    assert "`client.listAgentRunTelemetry(runId, { limit })`" in direct_api
    assert "`client.queryAgentRunTelemetry({ ... })`" in direct_api
    assert "`client.replayAgentRun(runId, { checkpoint_id })`" in direct_api
    assert "`client.forkAgentRun(runId, { checkpoint_id })`" in direct_api
    assert "`client.getAuditLogs({ ... })`" in direct_api
    assert "`client.getAuditLogArtifacts({ ... })`" in direct_api
    assert "`client.listExecutionPolicySnapshots()`" in direct_api


def test_openapi_uses_canonical_bearer_contract() -> None:
    schema = app.openapi()
    security = schema["components"]["securitySchemes"]
    assert schema["info"]["title"] == "Algenta API"
    assert "governed data discovery" in schema["info"]["description"]
    assert schema["servers"] == [{"url": "https://api.algenta.ai"}]
    assert schema["x-canonical-mcp-endpoint"] == "https://api.algenta.ai/mcp/sse"
    assert (
        schema["x-primary-data-query-contract"]["api"]["contract_endpoint"] == "/v1/meta/contract"
    )
    assert schema["x-primary-data-query-contract"]["api"]["discovery_endpoint"] == "/v1/data"
    assert (
        schema["x-primary-data-query-contract"]["governed_filter_contract"]["kind"]
        == "record_predicates"
    )
    assert schema["x-primary-data-query-contract"]["governed_filter_contract"]["operators"][
        "nullary"
    ] == ["is_null", "is_not_null"]
    assert (
        schema["x-primary-data-query-contract"]["direct_sdk"]["python"]["import_root"]
        == "decision_engine"
    )
    assert (
        schema["x-primary-data-query-contract"]["direct_sdk"]["python"]["preferred_client_class"]
        == "AlgentaClient"
    )
    assert (
        schema["x-primary-data-query-contract"]["direct_sdk"]["typescript"]["contract_method"]
        == "getContract"
    )
    assert (
        schema["x-primary-data-query-contract"]["runtime_sdk"]["python"]["runtime_class"]
        == "Runtime"
    )
    assert (
        schema["x-primary-data-query-contract"]["runtime_sdk"]["python"]["contract_method"]
        == "get_contract"
    )
    assert (
        schema["x-primary-data-query-contract"]["runtime_sdk"]["python"]["libraries_entrypoint"]
        == "libraries"
    )
    assert schema["x-primary-data-query-contract"]["cli"]["contract_command"] == "de contract"
    assert (
        schema["x-primary-data-query-contract"]["cli"]["query_batch_command"]
        == "de data query-batch <request.json>"
    )
    assert (
        schema["x-primary-data-query-contract"]["cli"]["runtime_modules_command"]
        == "de runtime modules"
    )
    assert (
        schema["x-primary-data-query-contract"]["cli"]["runtime_functions_command"]
        == "de runtime functions <module>"
    )
    assert (
        schema["x-primary-data-query-contract"]["cli"]["runtime_execute_command"]
        == "de runtime execute <module> <function> --args-json '<json>'"
    )
    assert schema["x-primary-data-query-contract"]["mcp"]["contract_tool"] == "get_contract"
    assert (
        schema["x-primary-data-query-contract"]["mcp"]["query_sql_report_tool"]
        == "query_sql_report"
    )
    assert (
        schema["x-primary-data-query-contract"]["mcp"]["runtime_library_list_tool"]
        == "list_runtime_libraries"
    )
    assert (
        schema["x-primary-data-query-contract"]["mcp"]["runtime_library_execute_tool"]
        == "execute_runtime_library"
    )
    assert "BearerAuth" in security
    assert security["BearerAuth"]["scheme"] == "bearer"
    assert "LegacyApiKey" in security
    protected = schema["paths"]["/v1/jobs"]["post"]["security"]
    assert protected == [{"BearerAuth": []}, {"LegacyApiKey": []}]
    decision_params = {
        param["name"] for param in schema["paths"]["/v1/decisions"]["get"]["parameters"]
    }
    assert "page" in decision_params
    assert "limit" in decision_params
    for path in [
        "/v1/data",
        "/v1/datasets",
        "/v1/sources",
        "/v1/triggers",
        "/v1/connectors",
        "/v1/team",
        "/v1/api-keys",
        "/v1/distributions",
        "/v1/templates",
        "/v1/device/list",
        "/v1/engines",
        "/v1/simulate/templates",
    ]:
        param_names = {param["name"] for param in schema["paths"][path]["get"]["parameters"]}
        assert "page" in param_names
        assert "limit" in param_names

    data_params = {param["name"] for param in schema["paths"]["/v1/data"]["get"]["parameters"]}
    datasets_params = {
        param["name"] for param in schema["paths"]["/v1/datasets"]["get"]["parameters"]
    }
    for param_name in {"search", "status", "source_name", "compact"}:
        assert param_name in data_params
        assert param_name in datasets_params

    assert "/v1/data/{dataset_id}/summary" in schema["paths"]
    assert "/v1/meta/contract" in schema["paths"]
    assert "/v1/query/batch" in schema["paths"]
    assert "/v1/query/sql-report" in schema["paths"]


def test_api_key_openapi_contract_exposes_expiry_fields() -> None:
    schema = app.openapi()
    components = schema["components"]["schemas"]

    create_props = components["CreateAPIKeyRequest"]["properties"]
    assert "expires_at" in create_props
    assert "device_limit" in create_props
    expires_schema = create_props["expires_at"]
    assert any(
        entry.get("format") == "date-time"
        for entry in expires_schema.get("anyOf", [expires_schema])
    )

    info_props = components["APIKeyInfo"]["properties"]
    created_props = components["APIKeyCreated"]["properties"]
    assert "expires_at" in info_props
    assert "expires_at" in created_props
    assert "device_limit" in info_props
    assert "device_limit" in created_props

    auth_text = (
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "authentication.md"
    ).read_text()
    assert '"expires_at":"2028-05-19T00:00:00Z"' in auth_text
    assert '"device_limit":3' in auth_text
    assert "ordinary hosted API traffic" in auth_text
    assert "`X-Algenta-Device-Id`" in auth_text
    assert "`X-Algenta-Platform`" in auth_text
    assert "`X-Algenta-Hostname-Hash`" in auth_text
    assert "`X-Algenta-Device-Binding-Token`" in auth_text
    assert "device_binding_token_required" in auth_text


def test_sdk_and_quickstart_docs_cover_bounded_api_key_creation() -> None:
    quickstart = (ROOT / "apps" / "docs" / "docs" / "quickstart.md").read_text()
    python_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "python.md").read_text()
    ts_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "typescript.md").read_text()
    direct_api = (ROOT / "apps" / "docs" / "docs" / "direct-api-client.md").read_text()
    readme = (ROOT / "README.md").read_text()

    assert "POST http://localhost:8000/v1/api-keys" in quickstart
    assert '"expires_at":"2028-05-19T00:00:00Z"' in quickstart
    assert '"device_limit":3' in quickstart
    assert "returned `raw_key` value is shown only once" in quickstart
    assert "`key_prefix`" in quickstart
    assert "`device_limit`" in quickstart
    assert "ordinary hosted API traffic" in quickstart
    assert "`X-Algenta-Device-Id`" in quickstart
    assert "`X-Algenta-Platform`" in quickstart
    assert "`X-Algenta-Hostname-Hash`" in quickstart
    assert "`X-Algenta-Device-Binding-Token`" in quickstart
    assert "first governed dataset query" in quickstart
    assert "http://localhost:8000/v1/meta/contract" in quickstart
    assert "http://localhost:8000/openapi.json" in quickstart
    assert "x-primary-data-query-contract" in quickstart
    assert "http://localhost:8000/v1/data?search=orders&compact=1&limit=5" in quickstart
    assert "http://localhost:8000/v1/data/orders_summary/summary" in quickstart
    assert "http://localhost:8000/v1/query" in quickstart
    assert "POST /v1/query/batch" in quickstart
    assert "POST /v1/query/sql-report" in quickstart

    assert "client.create_api_key(" in python_sdk
    assert 'expires_at="2028-05-19T00:00:00Z"' in python_sdk
    assert "device_limit=3" in python_sdk
    assert 'created["raw_key"]' in python_sdk
    assert 'created["key_prefix"]' in python_sdk
    assert 'created["device_limit"]' in python_sdk
    assert "stable device headers" in python_sdk
    assert "binding token" in python_sdk
    assert "ALGENTA_DEVICE_ID" in python_sdk
    assert "DE_DEVICE_ID" in python_sdk
    assert "from decision_engine import DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT" in python_sdk
    assert "record-filter contract" in python_sdk
    assert "Redis and other non-SQL sources" in python_sdk
    assert (
        'PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["type_behavior"]["numeric"]'
        in python_sdk
    )

    assert "await client.createApiKey({" in ts_sdk
    assert 'expires_at: "2028-05-19T00:00:00Z"' in ts_sdk
    assert "device_limit: 3" in ts_sdk
    assert "created.raw_key" in ts_sdk
    assert "created.key_prefix" in ts_sdk
    assert "created.device_limit" in ts_sdk
    assert "stable device headers" in ts_sdk
    assert "binding token" in ts_sdk
    assert "ALGENTA_DEVICE_ID" in ts_sdk
    assert "DE_DEVICE_ID" in ts_sdk
    assert 'import { DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT } from "algenta-sdk";' in ts_sdk
    assert "record-filter contract" in ts_sdk
    assert "Redis and other non-SQL sources" in ts_sdk
    assert "PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract.type_behavior.numeric" in ts_sdk

    assert "created = client.create_api_key(" in direct_api
    assert "from decision_engine import DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT" in direct_api
    assert 'datasets = client.list_datasets(search="orders", compact=True)' in direct_api
    assert "const created = await client.createApiKey({" in direct_api
    assert (
        "import { DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT } from 'algenta-sdk'" in direct_api
    )
    assert "const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY" in direct_api
    assert "throw new Error('Set ALGENTA_API_KEY or DE_API_KEY before running this example.')" in direct_api
    assert "apiKey," in direct_api
    assert "QueryFilterCondition" in direct_api
    assert "QueryFilterSpec" in direct_api
    assert (
        "const datasets = await client.listDatasets({ search: 'orders', compact: true })"
        in direct_api
    )
    assert 'expires_at="2028-05-19T00:00:00Z"' in direct_api
    assert "expires_at: '2028-05-19T00:00:00Z'" in direct_api
    assert "device_limit=3" in direct_api
    assert "device_limit: 3" in direct_api
    assert "raw_key" in direct_api
    assert "ordinary hosted API traffic" in direct_api
    assert "`X-Algenta-Device-Id`" in direct_api
    assert "`X-Algenta-Platform`" in direct_api
    assert "`X-Algenta-Hostname-Hash`" in direct_api
    assert "`X-Algenta-Device-Binding-Token`" in direct_api
    assert "record-filter contract" in direct_api
    assert "Redis and other non-SQL sources" in direct_api
    assert (
        'PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["operators"]["scalar"]'
        in direct_api
    )
    assert "PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract.operators.scalar" in direct_api
    assert "DECISION_ENGINE_API_KEY" not in direct_api
    assert "ALGENTA_API_KEY" in direct_api
    assert 'api_key="de_live_...' not in direct_api
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in direct_api
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in direct_api

    assert "POST http://localhost:8000/v1/api-keys" in readme
    assert '"expires_at":"2028-05-19T00:00:00Z"' in readme
    assert '"device_limit":3' in readme
    assert "replacement key for steady-state" in readme
    assert "`key_prefix`" in readme
    assert "`device_limit`" in readme
    assert "ordinary hosted API traffic" in readme
    assert "`X-Algenta-Device-Id`" in readme
    assert "`X-Algenta-Platform`" in readme
    assert "`X-Algenta-Hostname-Hash`" in readme
    assert "`X-Algenta-Device-Binding-Token`" in readme
    assert "record-filter contract" in readme
    assert "PRIMARY_DATA_QUERY_CONTRACT.governed_filter_contract" in readme
    assert "Redis snapshots" in readme


def test_docs_use_canonical_urls_and_bearer_examples() -> None:
    doc_paths = [
        ROOT / "apps" / "docs" / "docs" / "index.md",
        ROOT / "apps" / "docs" / "docs" / "quickstart.md",
        ROOT / "apps" / "docs" / "docs" / "operations" / "index.md",
        ROOT / "apps" / "docs" / "docs" / "operations" / "tls-and-reverse-proxy.md",
        ROOT / "apps" / "docs" / "docs" / "operations" / "logs-and-metrics.md",
        ROOT / "apps" / "docs" / "docs" / "operations" / "upgrade-and-rollback.md",
        ROOT / "apps" / "docs" / "docs" / "operations-advanced" / "backup-and-recovery.md",
        ROOT / "apps" / "docs" / "docs" / "operations-advanced" / "troubleshooting.md",
        ROOT / "apps" / "docs" / "docs" / "operations-advanced" / "support-boundaries.md",
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "index.md",
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "authentication.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "chatgpt-actions.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "claude-codex.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "n8n.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "azure-ai-studio.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "overview.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "make.md",
        ROOT / "apps" / "mcp_server" / "README.md",
        ROOT / "apps" / "mcp_server" / "server.py",
        ROOT / "apps" / "mcp_server" / "config.py",
    ]
    for path in doc_paths:
        text = path.read_text()
        assert "api.decisionengine.io" not in text, path
        assert "api.algenta.io" not in text, path
    assert (
        "Authorization: Bearer" in (ROOT / "apps" / "docs" / "docs" / "quickstart.md").read_text()
    )
    api_reference_index = (ROOT / "apps" / "docs" / "docs" / "api-reference" / "index.md").read_text()
    assert "Authorization: Bearer <YOUR_ALGENTA_API_KEY>" in api_reference_index
    assert "X-API-Key: <YOUR_ALGENTA_API_KEY>" in api_reference_index
    assert "Authorization: Bearer de_live_..." not in api_reference_index
    assert "X-API-Key: de_live_..." not in api_reference_index


def test_public_docs_and_examples_have_no_stale_hosts_or_key_prefixes() -> None:
    targets = [
        ROOT / "apps" / "docs" / "docs",
        ROOT / "examples",
        ROOT / "apps" / "mcp_server",
    ]
    forbidden = ["api.decisionengine.io", "api.algenta.io", "docs.decisionengine.io", "alg_live_"]
    suffixes = {".md", ".json", ".yaml", ".yml", ".py", ".js", ".ts"}

    files: list[Path] = []
    for target in targets:
        if target.is_file():
            files.append(target)
            continue
        for path in target.rglob("*"):
            if path.is_file() and path.suffix in suffixes:
                files.append(path)

    offenders: list[str] = []
    for path in files:
        text = path.read_text()
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{path}: {needle}")
    assert not offenders, "\n".join(offenders)


def test_error_docs_cover_scope_and_idempotency_contract() -> None:
    auth_text = (
        ROOT / "apps" / "docs" / "docs" / "api-reference" / "authentication.md"
    ).read_text()
    errors_text = (ROOT / "apps" / "docs" / "docs" / "api-reference" / "errors.md").read_text()
    assert "access_scope_denied" in auth_text
    assert "access_scope_denied" in errors_text
    assert "resource_write_conflict" in errors_text
    assert "idempotency_key_conflict" in errors_text


def test_integration_docs_cover_primary_surfaces() -> None:
    overview = (ROOT / "apps" / "docs" / "docs" / "integrations" / "overview.md").read_text()
    claude_codex = (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "claude-codex.md"
    ).read_text()
    langgraph = (ROOT / "apps" / "docs" / "docs" / "integrations" / "langgraph.md").read_text()
    mcp_readme = (ROOT / "apps" / "mcp_server" / "README.md").read_text()
    claude_desktop_readme = (ROOT / "examples" / "claude-desktop" / "README.md").read_text()
    langgraph_example = (ROOT / "examples" / "langgraph" / "decision_tool.py").read_text()

    required_paths = [
        ROOT / "apps" / "docs" / "docs" / "integrations" / "claude-codex.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "azure-ai-studio.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "langgraph.md",
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md",
        ROOT / "examples" / "chatgpt-actions" / "README.md",
        ROOT / "examples" / "n8n" / "README.md",
        ROOT / "examples" / "local-runtime" / "README.md",
    ]
    for path in required_paths:
        assert path.exists(), path

    assert "/integrations/claude-codex" in overview
    assert "/integrations/azure-ai-studio" in overview
    assert "/integrations/langgraph" in overview
    assert "/integrations/local-runtime" in overview
    assert "persisted runtime review" in overview
    assert "persisted runtime follow-up workflows" in overview
    assert "Add Algenta as a tool node" in langgraph
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in langgraph
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in langgraph
    assert 'api_key="de_live_...' not in langgraph
    assert "client.get_contract()" in langgraph
    assert "client.list_datasets(search=dataset_search, compact=True" in langgraph
    assert "client.get_dataset_summary(dataset_id)" in langgraph
    assert "client.query_with_metadata(" in langgraph
    assert "client.query_batch(" in langgraph
    assert "client.list_agent_runs(...)" in langgraph
    assert "client.query_agent_run_checkpoints(...)" in langgraph
    assert "client.query_agent_run_mission_events(...)" in langgraph
    assert "client.query_agent_run_telemetry(...)" in langgraph
    assert "client.replay_agent_run(run_id, checkpoint_id=...)" in langgraph
    assert "client.fork_agent_run(run_id, checkpoint_id=...)" in langgraph
    assert "client.get_audit_log_artifacts(...)" in langgraph
    assert "client.list_execution_policy_snapshots()" in langgraph
    assert "`query_sql_report(...)`" in langgraph
    assert "list_data" in mcp_readme
    assert "get_data_summary" in mcp_readme
    assert "query_data" in mcp_readme
    assert "query_batch" in mcp_readme
    assert "query_sql_report" in mcp_readme
    assert "list_models" in mcp_readme
    assert "tokenize" in mcp_readme
    assert "chat_completions" in mcp_readme
    assert "plan_decision" in mcp_readme
    assert "create_agent_run" in mcp_readme
    assert "approve_agent_run" in mcp_readme
    assert "compact=true" in mcp_readme
    assert "record-filter contract" in mcp_readme
    assert "governed_filter_contract" in mcp_readme
    assert "GET  /mcp/tools" in mcp_readme
    assert "always available" in mcp_readme
    assert "GET  /mcp/sse" in mcp_readme
    assert "POST /mcp/messages" in mcp_readme
    assert "mcp_transport_unavailable" in mcp_readme
    assert "Install requirements-mcp.txt to enable /mcp/sse and /mcp/messages." in mcp_readme
    assert "search='otp'" not in mcp_readme
    assert "query_batch(...)" in claude_codex
    assert "query_sql_report(...)" in claude_codex
    assert "list_data(search=" in claude_desktop_readme
    assert "query_batch" in claude_desktop_readme
    assert "query_sql_report" in claude_desktop_readme
    assert "list_agent_runs" in claude_desktop_readme
    assert "query_agent_run_checkpoints" in claude_desktop_readme
    assert "query_agent_run_mission_events" in claude_desktop_readme
    assert "query_agent_run_telemetry" in claude_desktop_readme
    assert "get_audit_log_artifacts" in claude_desktop_readme
    assert "list_execution_policy_snapshots" in claude_desktop_readme
    assert 'list_data(search="orders", compact=true)' in claude_desktop_readme
    assert "completed orders by month" in claude_desktop_readme
    assert "from decision_engine import AlgentaClient" in langgraph_example
    assert "inspect_algenta_contract" in langgraph_example
    assert "inspect_runtime_lineage" in langgraph_example
    assert "client.get_contract()" in langgraph_example
    assert "client.list_datasets(" in langgraph_example
    assert "client.get_dataset_summary(" in langgraph_example
    assert "client.query_with_metadata(" in langgraph_example
    assert "client.query_batch(" in langgraph_example
    assert "client.query_sql_report(" in langgraph_example
    assert "client.list_agent_runs(" in langgraph_example
    assert "client.query_agent_run_checkpoints(" in langgraph_example
    assert "client.query_agent_run_mission_events(" in langgraph_example
    assert "client.query_agent_run_telemetry(" in langgraph_example
    assert "client.get_audit_log_artifacts(" in langgraph_example
    assert "client.list_execution_policy_snapshots()" in langgraph_example
    assert "export ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY>" in langgraph_example
    assert "de_live_..." not in langgraph_example
    assert '"/v1/data?page=1"' not in langgraph_example
    assert "urllib.request" not in langgraph_example


def test_core_query_docs_cover_discovery_first_and_adjacent_surfaces() -> None:
    mcp_doc = (ROOT / "apps" / "docs" / "docs" / "mcp.md").read_text()
    resolve_doc = (ROOT / "apps" / "docs" / "docs" / "resolve.md").read_text()
    verify_doc = (ROOT / "apps" / "docs" / "docs" / "verify.md").read_text()
    query_doc = (ROOT / "apps" / "docs" / "docs" / "query.md").read_text()

    assert 'list_data(search="orders", compact=true)' in mcp_doc
    assert "get_data_summary(dataset_id)" in mcp_doc
    assert "Mission functionality mapping" in mcp_doc
    assert "query_sql_source" in mcp_doc
    assert "No one-to-one MCP tool today." in mcp_doc
    assert "get_sources_graph" in mcp_doc
    assert "map_data_sources" in mcp_doc
    assert "register_sql_source" in mcp_doc
    assert "get_algenta_library_health" in mcp_doc
    assert "query_batch(...)" in mcp_doc
    assert "governed_filter_contract" in mcp_doc
    assert "query_sql_report(...)" in mcp_doc
    assert "LLM utility and agent-run flow" in mcp_doc
    assert "list_models()" in mcp_doc
    assert "tokenize(...)" in mcp_doc
    assert "plan_decision(...)" in mcp_doc
    assert "create_agent_run(...)" in mcp_doc
    assert "get_agent_run(run_id)" in mcp_doc
    assert "approve_agent_run(run_id)" in mcp_doc
    assert "list_runtime_libraries" in mcp_doc
    assert "execute_runtime_library" in mcp_doc
    assert "text.tokenizer" in mcp_doc
    assert "vector_kernels.table" in mcp_doc
    assert "mission_functionality_surface_map.json" in mcp_doc
    assert "mcp_governed_exact_sequence.json" in mcp_doc
    assert "mcp_governed_sql_report_sequence.json" in mcp_doc
    assert "mcp_runtime_library_sequence.json" in mcp_doc
    assert "/v1/resolve" in mcp_doc
    assert "/v1/verify" in mcp_doc

    assert "GET /v1/meta/contract" in resolve_doc
    assert "/openapi.json" in resolve_doc
    assert "x-primary-data-query-contract" in resolve_doc
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in resolve_doc
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in resolve_doc
    assert 'api_key="de_live_...' not in resolve_doc
    assert 'rt.list_datasets(search="orders", compact=True)' in resolve_doc
    assert "rt.get_dataset_summary(datasets.datasets[0].dataset_id)" in resolve_doc
    assert "query_with_metadata()" in resolve_doc
    assert "query_batch()" in resolve_doc
    assert "query_sql_report()" in resolve_doc

    assert "GET /v1/meta/contract" in verify_doc
    assert "/openapi.json" in verify_doc
    assert "x-primary-data-query-contract" in verify_doc
    assert "list_datasets(search=..., compact=True)" in verify_doc
    assert "get_dataset_summary(dataset_id)" in verify_doc
    assert "queryWithMetadata()" in verify_doc

    assert "GET /v1/meta/contract" in query_doc
    assert "/openapi.json" in query_doc
    assert "x-primary-data-query-contract" in query_doc
    assert "list_datasets(search=..., compact=True)" in query_doc
    assert "query_with_metadata()" in query_doc
    assert "query_batch()" in query_doc
    assert "query_sql_report()" in query_doc
    assert "conditions[].op = eq" in query_doc
    assert "status = completed" in query_doc
    assert "record-filter contract" in query_doc
    assert "connector exposes deterministic records" in query_doc
    assert "Do not use `query()` as a planning shortcut" in query_doc


def test_overview_docs_cover_service_first_simulation_and_governed_query_paths() -> None:
    overview = (ROOT / "apps" / "docs" / "docs" / "index.md").read_text()
    how_it_works = (ROOT / "apps" / "docs" / "docs" / "how-algenta-works-today.md").read_text()
    secondary_modes = (ROOT / "apps" / "docs" / "docs" / "supported-secondary-modes.md").read_text()
    connect_docs = (ROOT / "apps" / "docs" / "docs" / "connect-register-sources.md").read_text()

    assert "GET /v1/meta/contract" in overview
    assert "POST /v1/simulate" in overview
    assert "GET /v1/data?search=...&compact=1" in overview
    assert "GET /v1/data/{dataset_id}/summary" in overview
    assert "POST /v1/query" in overview
    assert "/openapi.json" in overview
    assert "x-primary-data-query-contract" in overview

    assert "GET /v1/meta/contract" in how_it_works
    assert "GET /v1/data?search=...&compact=1" in how_it_works
    assert "POST /v1/query/batch" in how_it_works
    assert "POST /v1/query/sql-report" in how_it_works
    assert "list_agent_runs(...)" in how_it_works
    assert "query_agent_run_checkpoints(...)" in how_it_works
    assert "query_agent_run_mission_events(...)" in how_it_works
    assert "query_agent_run_telemetry(...)" in how_it_works
    assert "replay_agent_run(...)" in how_it_works
    assert "fork_agent_run(...)" in how_it_works
    assert "get_audit_log_artifacts(...)" in how_it_works
    assert "list_execution_policy_snapshots()" in how_it_works
    assert "listAgentRuns({ ... })" in how_it_works
    assert "queryAgentRunCheckpoints({ ... })" in how_it_works
    assert "queryAgentRunMissionEvents({ ... })" in how_it_works
    assert "queryAgentRunTelemetry({ ... })" in how_it_works
    assert "replayAgentRun(...)" in how_it_works
    assert "forkAgentRun(...)" in how_it_works
    assert "getAuditLogArtifacts({ ... })" in how_it_works
    assert "listExecutionPolicySnapshots()" in how_it_works
    assert "[Query](/query)" in how_it_works
    assert "[Direct API Client](/direct-api-client)" in how_it_works
    assert "[MCP](/mcp)" in how_it_works
    assert "/openapi.json" in how_it_works
    assert "x-primary-data-query-contract" in how_it_works

    assert "client.get_contract()" in secondary_modes
    assert "get_dataset_summary" in secondary_modes
    assert "query_with_metadata" in secondary_modes
    assert "query_batch" in secondary_modes
    assert "query_sql_report" in secondary_modes
    assert "list_agent_runs(...)" in secondary_modes
    assert "query_agent_run_checkpoints(...)" in secondary_modes
    assert "query_agent_run_mission_events(...)" in secondary_modes
    assert "query_agent_run_telemetry(...)" in secondary_modes
    assert "replay_agent_run(run_id, checkpoint_id=...)" in secondary_modes
    assert "fork_agent_run(run_id, checkpoint_id=...)" in secondary_modes
    assert "get_audit_log_artifacts(...)" in secondary_modes
    assert "list_execution_policy_snapshots()" in secondary_modes
    assert 'list_data(search="orders", compact=true)' in secondary_modes
    assert "list_agent_runs(...)" in secondary_modes
    assert "query_agent_run_checkpoints(...)" in secondary_modes
    assert "query_agent_run_mission_events(...)" in secondary_modes
    assert "query_agent_run_telemetry(...)" in secondary_modes
    assert "get_audit_log_artifacts()" in secondary_modes
    assert "list_execution_policy_snapshots()" in secondary_modes

    assert "GET /v1/meta/contract" in connect_docs
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in connect_docs
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in connect_docs
    assert 'api_key="de_live_...' not in connect_docs
    assert "list_datasets(search=..., compact=True)" in connect_docs
    assert "get_dataset_summary(dataset_id)" in connect_docs
    assert "query_with_metadata(...)" in connect_docs
    assert "query_batch(...)" in connect_docs
    assert "query_sql_report(...)" in connect_docs
    assert "/openapi.json" in connect_docs
    assert "x-primary-data-query-contract" in connect_docs


def test_ai_and_automation_examples_cover_governed_discovery_and_query_surfaces() -> None:
    chatgpt_doc = (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "chatgpt-actions.md"
    ).read_text()
    claude_doc = (ROOT / "apps" / "docs" / "docs" / "integrations" / "claude-codex.md").read_text()
    n8n_doc = (ROOT / "apps" / "docs" / "docs" / "integrations" / "n8n.md").read_text()
    make_doc = (ROOT / "apps" / "docs" / "docs" / "integrations" / "make.md").read_text()
    zapier_doc = (ROOT / "apps" / "docs" / "docs" / "integrations" / "zapier.md").read_text()
    power_doc = (ROOT / "apps" / "docs" / "docs" / "integrations" / "power-automate.md").read_text()
    power_readme = (ROOT / "examples" / "power-automate" / "README.md").read_text()
    azure_doc = (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "azure-ai-studio.md"
    ).read_text()
    chatgpt_example = yaml.safe_load(
        (ROOT / "examples" / "chatgpt-actions" / "openapi_actions.yaml").read_text()
    )
    power_connector = json.loads(
        (ROOT / "examples" / "power-automate" / "connector_definition.json").read_text()
    )
    power_contract_request = json.loads(
        (ROOT / "examples" / "power-automate" / "contract_request.json").read_text()
    )
    power_openapi_contract_request = json.loads(
        (ROOT / "examples" / "power-automate" / "openapi_contract_request.json").read_text()
    )
    power_query_batch_request = json.loads(
        (ROOT / "examples" / "power-automate" / "query_batch_request.json").read_text()
    )
    power_sql_report_request = json.loads(
        (ROOT / "examples" / "power-automate" / "sql_report_request.json").read_text()
    )
    azure_query_tool = json.loads(
        (ROOT / "examples" / "azure-ai-studio" / "algenta_query_tool_definition.json").read_text()
    )
    azure_sql_report_tool = json.loads(
        (
            ROOT / "examples" / "azure-ai-studio" / "algenta_sql_report_tool_definition.json"
        ).read_text()
    )
    azure_contract_tool = json.loads(
        (
            ROOT / "examples" / "azure-ai-studio" / "algenta_contract_tool_definition.json"
        ).read_text()
    )
    azure_readme = (ROOT / "examples" / "azure-ai-studio" / "README.md").read_text()
    chatgpt_readme = (ROOT / "examples" / "chatgpt-actions" / "README.md").read_text()
    claude_readme = (ROOT / "examples" / "claude-desktop" / "README.md").read_text()
    n8n_readme = (ROOT / "examples" / "n8n" / "README.md").read_text()
    make_readme = (ROOT / "examples" / "make" / "README.md").read_text()
    zapier_readme = (ROOT / "examples" / "zapier" / "README.md").read_text()
    n8n_contract_workflow = json.loads(
        (ROOT / "examples" / "n8n" / "workflow_contract.json").read_text()
    )
    n8n_query_batch_workflow = json.loads(
        (ROOT / "examples" / "n8n" / "workflow_query_batch.json").read_text()
    )
    n8n_sql_report_workflow = json.loads(
        (ROOT / "examples" / "n8n" / "workflow_sql_report.json").read_text()
    )
    make_contract_request = json.loads(
        (ROOT / "examples" / "make" / "contract_request.json").read_text()
    )
    make_openapi_contract_request = json.loads(
        (ROOT / "examples" / "make" / "openapi_contract_request.json").read_text()
    )
    make_query_batch = json.loads(
        (ROOT / "examples" / "make" / "query_batch_request.json").read_text()
    )
    make_sql_report = json.loads(
        (ROOT / "examples" / "make" / "sql_report_request.json").read_text()
    )
    zapier_contract_request = json.loads(
        (ROOT / "examples" / "zapier" / "contract_request.json").read_text()
    )
    zapier_openapi_contract_request = json.loads(
        (ROOT / "examples" / "zapier" / "openapi_contract_request.json").read_text()
    )
    zapier_query_batch = json.loads(
        (ROOT / "examples" / "zapier" / "query_batch_request.json").read_text()
    )
    zapier_sql_report = json.loads(
        (ROOT / "examples" / "zapier" / "sql_report_request.json").read_text()
    )
    colab_notebook = json.loads(
        (ROOT / "examples" / "google-colab" / "algenta_decision_engine.ipynb").read_text()
    )

    for needle in [
        "GET /v1/meta/contract",
        "GET /v1/data",
        "GET /v1/data/{dataset_id}/summary",
        "POST /v1/query",
        "POST /v1/query/batch",
        "POST /v1/query/sql-report",
        "GET /v1/agent/runs",
        "GET /v1/agent/runs/checkpoints",
        "GET /v1/agent/runs/mission-events",
        "GET /v1/agent/runs/telemetry",
        "GET /v1/audit-logs/artifacts",
        "GET /v1/execution/policy/snapshots",
    ]:
        assert needle in chatgpt_doc

    assert "Inspect the live contract" in chatgpt_readme
    assert "GET /v1/meta/contract" in chatgpt_readme
    assert "GET /v1/agent/runs" in chatgpt_readme
    assert "GET /v1/agent/runs/checkpoints" in chatgpt_readme
    assert "GET /v1/agent/runs/mission-events" in chatgpt_readme
    assert "GET /v1/agent/runs/telemetry" in chatgpt_readme
    assert "GET /v1/audit-logs/artifacts" in chatgpt_readme
    assert "GET /v1/execution/policy/snapshots" in chatgpt_readme
    assert "/openapi.json" in chatgpt_doc
    assert "x-primary-data-query-contract" in chatgpt_doc
    assert "/openapi.json" in chatgpt_readme
    assert "x-primary-data-query-contract" in chatgpt_readme
    assert "persisted runtime and control-plane review" in chatgpt_doc
    assert "persisted\nruntime review flow" in chatgpt_readme
    assert "control-plane review endpoints" in chatgpt_readme
    assert "get_contract()" in claude_doc
    assert 'list_data(search="orders", compact=true)' in claude_doc
    assert "completed orders by month" in claude_doc
    assert "get_contract" in claude_readme
    assert "Machine-readable Algenta contract" in claude_readme
    assert "get_contract → list_data → get_data_summary → query_data" in claude_readme

    shared_query_paths = {
        "/v1/meta/contract",
        "/v1/data",
        "/v1/data/{dataset_id}/summary",
        "/v1/query",
        "/v1/query/batch",
        "/v1/query/sql-report",
        "/v1/simulate",
    }
    chatgpt_expected_paths = shared_query_paths | {
        "/v1/agent/runs",
        "/v1/agent/runs/checkpoints",
        "/v1/agent/runs/mission-events",
        "/v1/agent/runs/telemetry",
        "/v1/audit-logs/artifacts",
        "/v1/execution/policy/snapshots",
    }
    assert chatgpt_expected_paths.issubset(chatgpt_example["paths"])
    assert shared_query_paths.issubset(power_connector["paths"])
    assert chatgpt_example["servers"][0]["url"] == EXAMPLE_BASE_URL
    assert chatgpt_example["x-canonical-mcp-endpoint"] == EXAMPLE_MCP_ENDPOINT
    assert power_connector["host"] == "your-algenta-base-url.example"
    assert power_connector["x-canonical-mcp-endpoint"] == EXAMPLE_MCP_ENDPOINT
    assert (
        chatgpt_example["x-primary-data-query-contract"]["api"]["contract_endpoint"]
        == "/v1/meta/contract"
    )
    assert (
        chatgpt_example["x-primary-data-query-contract"]["api"]["query_batch_endpoint"]
        == "/v1/query/batch"
    )
    assert (
        chatgpt_example["x-primary-data-query-contract"]["governed_filter_contract"]["kind"]
        == "record_predicates"
    )
    assert chatgpt_example["x-primary-data-query-contract"]["governed_filter_contract"][
        "operators"
    ]["nullary"] == ["is_null", "is_not_null"]
    assert (
        chatgpt_example["x-primary-data-query-contract"]["direct_sdk"]["python"]["contract_method"]
        == "get_contract"
    )
    assert (
        chatgpt_example["x-primary-data-query-contract"]["direct_sdk"]["python"][
            "preferred_client_class"
        ]
        == "AlgentaClient"
    )
    assert (
        chatgpt_example["x-primary-data-query-contract"]["runtime_sdk"]["python"]["runtime_class"]
        == "Runtime"
    )
    assert (
        power_connector["x-primary-data-query-contract"]["cli"]["contract_command"] == "de contract"
    )
    assert (
        power_connector["x-primary-data-query-contract"]["governed_filter_contract"]["kind"]
        == "record_predicates"
    )
    assert (
        power_connector["x-primary-data-query-contract"]["governed_filter_contract"][
            "supports_non_sql_backends"
        ]
        is True
    )
    assert (
        power_connector["x-primary-data-query-contract"]["cli"]["query_sql_report_command"]
        == "de data sql-report <request.json>"
    )
    assert (
        power_connector["x-primary-data-query-contract"]["runtime_sdk"]["typescript"][
            "contract_method"
        ]
        == "getContract"
    )
    assert (
        power_connector["x-primary-data-query-contract"]["runtime_sdk"]["typescript"][
            "runtime_class"
        ]
        == "Runtime"
    )
    assert (
        power_connector["x-primary-data-query-contract"]["runtime_sdk"]["typescript"][
            "libraries_entrypoint"
        ]
        == "libraries"
    )
    assert (
        chatgpt_example["x-primary-data-query-contract"]["mcp"]["contract_tool"] == "get_contract"
    )
    assert (
        chatgpt_example["x-primary-data-query-contract"]["mcp"]["query_sql_report_tool"]
        == "query_sql_report"
    )
    assert (
        chatgpt_example["paths"]["/v1/agent/runs"]["get"]["operationId"] == "listAgentRuns"
    )
    assert (
        chatgpt_example["paths"]["/v1/audit-logs/artifacts"]["get"]["operationId"]
        == "getAuditLogArtifacts"
    )
    assert (
        chatgpt_example["paths"]["/v1/execution/policy/snapshots"]["get"]["operationId"]
        == "listExecutionPolicySnapshots"
    )
    assert any(
        parameter["name"] == "policy_snapshot_id"
        for parameter in chatgpt_example["paths"]["/v1/agent/runs"]["get"]["parameters"]
    )
    assert any(
        parameter["name"] == "content_hash"
        for parameter in chatgpt_example["paths"]["/v1/audit-logs/artifacts"]["get"][
            "parameters"
        ]
    )
    assert "persisted runtime follow-up" in (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "overview.md"
    ).read_text()

    for text in [n8n_doc, make_doc, zapier_doc]:
        assert "/v1/meta/contract" in text
        assert "/openapi.json" in text
        assert "x-primary-data-query-contract" in text
        assert "/v1/data" in text
        assert "/v1/query" in text
        assert "/v1/query/batch" in text
        assert "/v1/query/sql-report" in text

    assert "Get Contract" in power_doc
    assert "governed_filter_contract" in power_doc
    assert "List Datasets" in power_doc
    assert "Get Dataset Summary" in power_doc
    assert "Query Dataset" in power_doc
    assert "Query Batch" in power_doc
    assert "Query SQL Report" in power_doc
    assert "GET /v1/meta/contract" in power_doc
    assert "/openapi.json" in power_doc
    assert "x-primary-data-query-contract" in power_doc
    assert "examples/power-automate/README.md" in power_doc
    assert "examples/power-automate/contract_request.json" in power_doc
    assert "examples/power-automate/openapi_contract_request.json" in power_doc
    assert "examples/power-automate/query_batch_request.json" in power_doc
    assert "examples/power-automate/sql_report_request.json" in power_doc
    assert "GET /v1/meta/contract" in power_readme
    assert "/openapi.json" in power_readme
    assert "x-primary-data-query-contract" in power_readme
    assert "GET /v1/data/{dataset_id}/summary" in power_readme
    assert "POST /v1/query/batch" in power_readme
    assert "POST /v1/query/sql-report" in power_readme
    assert "contract_request.json" in power_readme
    assert "openapi_contract_request.json" in power_readme
    assert "query_batch_request.json" in power_readme
    assert "sql_report_request.json" in power_readme
    assert power_contract_request["method"] == "GET"
    assert power_contract_request["url"] == f"{EXAMPLE_BASE_URL}/v1/meta/contract"
    assert power_contract_request["headers"]["Authorization"] == "Bearer <YOUR_ALGENTA_API_KEY>"
    assert power_openapi_contract_request["method"] == "GET"
    assert power_openapi_contract_request["url"] == f"{EXAMPLE_BASE_URL}/openapi.json"
    assert (
        power_openapi_contract_request["headers"]["Authorization"]
        == "Bearer <YOUR_ALGENTA_API_KEY>"
    )
    assert power_query_batch_request["defaults"]["dataset_id"] == "orders_facts"
    assert (
        power_query_batch_request["defaults"]["filter"]["conditions"][0]["dimension_hint"]
        == "status"
    )
    assert power_query_batch_request["queries"][1]["key"] == "monthly_completed_orders"
    assert power_sql_report_request["sources"][0]["alias"] == "orders"
    assert "select order_month" in power_sql_report_request["sql"]
    assert power_sql_report_request["max_rows"] == 100

    assert "algenta_query_tool_definition.json" in azure_doc
    assert "algenta_sql_report_tool_definition.json" in azure_doc
    assert "algenta_contract_tool_definition.json" in azure_doc
    assert "governed_filter_contract" in azure_doc
    assert "algenta_query_tool_definition.json" in azure_readme
    assert "algenta_sql_report_tool_definition.json" in azure_readme
    assert "algenta_contract_tool_definition.json" in azure_readme
    assert "Inspect the live Algenta contract" in azure_readme
    assert 'os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in azure_readme
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in azure_readme
    assert "Canonical key env var is `ALGENTA_API_KEY`. Legacy `DE_API_KEY` remains" in azure_readme
    assert "accepted for compatibility in the snippets above." in azure_readme
    assert "Canonical base URL env var is `ALGENTA_BASE_URL`. Legacy `DE_BASE_URL` and" in azure_readme
    assert "`ALGENTA_API_URL` remain accepted for compatibility in the snippets above." in azure_readme
    assert "/openapi.json" in azure_doc
    assert "x-primary-data-query-contract" in azure_doc
    assert "/openapi.json" in azure_readme
    assert "x-primary-data-query-contract" in azure_readme
    assert azure_query_tool["name"] == "algenta_query_dataset"
    assert "algenta_get_contract" in azure_query_tool["description"]
    assert (
        "completed_order_count"
        in azure_query_tool["parameters"]["properties"]["metric_hint"]["description"]
    )
    assert azure_sql_report_tool["name"] == "algenta_query_sql_report"
    assert "algenta_get_contract" in azure_sql_report_tool["description"]
    assert (
        "gross_revenue" in azure_sql_report_tool["parameters"]["properties"]["sql"]["description"]
    )
    assert azure_contract_tool["name"] == "algenta_get_contract"
    assert "governed filter rules" in azure_contract_tool["description"]
    tool_props = azure_query_tool["parameters"]["properties"]
    for field in ("dataset_search", "dataset_id", "metric_hint", "batch_queries"):
        assert field in tool_props
    sql_tool_props = azure_sql_report_tool["parameters"]["properties"]
    for field in ("dataset_search", "dataset_id", "sql", "alias", "max_rows"):
        assert field in sql_tool_props

    assert "GET /v1/data" in n8n_readme
    assert "GET /v1/data/{dataset_id}/summary" in n8n_readme
    assert "POST /v1/query" in n8n_readme
    assert "POST /v1/query/batch" in n8n_readme
    assert "POST /v1/query/sql-report" in n8n_readme
    assert "GET /v1/agent/runs" in n8n_readme
    assert "GET /v1/agent/runs/checkpoints" in n8n_readme
    assert "GET /v1/agent/runs/mission-events" in n8n_readme
    assert "GET /v1/agent/runs/telemetry" in n8n_readme
    assert "GET /v1/audit-logs/artifacts" in n8n_readme
    assert "GET /v1/execution/policy/snapshots" in n8n_readme
    assert "GET /v1/meta/contract" in n8n_readme
    assert "/openapi.json" in n8n_readme
    assert "x-primary-data-query-contract" in n8n_readme
    assert "workflow_contract.json" in n8n_readme
    assert "workflow_query_batch.json" in n8n_readme
    assert "workflow_sql_report.json" in n8n_readme
    assert "already do this by reading `/openapi.json`" in n8n_readme
    assert "persisted run inventory" in n8n_readme

    assert "GET /v1/agent/runs" in n8n_doc
    assert "GET /v1/agent/runs/checkpoints" in n8n_doc
    assert "GET /v1/agent/runs/mission-events" in n8n_doc
    assert "GET /v1/agent/runs/telemetry" in n8n_doc
    assert "GET /v1/audit-logs/artifacts" in n8n_doc
    assert "GET /v1/execution/policy/snapshots" in n8n_doc
    assert "persisted runtime follow-up" in n8n_doc

    assert "GET /v1/agent/runs" in make_doc
    assert "GET /v1/agent/runs/checkpoints" in make_doc
    assert "GET /v1/agent/runs/mission-events" in make_doc
    assert "GET /v1/agent/runs/telemetry" in make_doc
    assert "GET /v1/audit-logs/artifacts" in make_doc
    assert "GET /v1/execution/policy/snapshots" in make_doc
    assert "execution-policy lineage" in make_doc

    assert "GET /v1/agent/runs" in zapier_doc
    assert "GET /v1/agent/runs/checkpoints" in zapier_doc
    assert "GET /v1/agent/runs/mission-events" in zapier_doc
    assert "GET /v1/agent/runs/telemetry" in zapier_doc
    assert "GET /v1/audit-logs/artifacts" in zapier_doc
    assert "GET /v1/execution/policy/snapshots" in zapier_doc
    assert "policy lineage" in zapier_doc

    assert "GET /v1/agent/runs" in make_readme
    assert "GET /v1/agent/runs/checkpoints" in make_readme
    assert "GET /v1/agent/runs/mission-events" in make_readme
    assert "GET /v1/agent/runs/telemetry" in make_readme
    assert "GET /v1/audit-logs/artifacts" in make_readme
    assert "GET /v1/execution/policy/snapshots" in make_readme
    assert "persisted run inventory" in make_readme

    assert "GET /v1/agent/runs" in zapier_readme
    assert "GET /v1/agent/runs/checkpoints" in zapier_readme
    assert "GET /v1/agent/runs/mission-events" in zapier_readme
    assert "GET /v1/agent/runs/telemetry" in zapier_readme
    assert "GET /v1/audit-logs/artifacts" in zapier_readme
    assert "GET /v1/execution/policy/snapshots" in zapier_readme
    assert "persisted run inventory" in zapier_readme

    contract_node_names = {node["name"] for node in n8n_contract_workflow["nodes"]}
    assert n8n_contract_workflow["name"] == "Algenta — Inspect Live Contract"
    assert {"Get Contract", "Extract Contract"}.issubset(contract_node_names)
    contract_nodes = {node["name"]: node for node in n8n_contract_workflow["nodes"]}
    assert (
        contract_nodes["Get Contract"]["parameters"]["url"]
        == f"={EXAMPLE_BASE_URL}/openapi.json"
    )
    contract_values = {
        item["name"]: item["value"]
        for item in contract_nodes["Extract Contract"]["parameters"]["values"]["string"]
    }
    assert "x-primary-data-query-contract" in contract_values["contract_endpoint"]
    assert "x-primary-data-query-contract" in contract_values["discovery_endpoint"]
    assert "query_sql_report_endpoint" in contract_values

    batch_node_names = {node["name"] for node in n8n_query_batch_workflow["nodes"]}
    assert n8n_query_batch_workflow["name"] == "Algenta — Discover Dataset and Query Batch"
    assert {"Get Contract", "Discover Datasets", "Get Dataset Summary", "Query Batch"}.issubset(
        batch_node_names
    )
    batch_nodes = {node["name"]: node for node in n8n_query_batch_workflow["nodes"]}
    assert (
        batch_nodes["Get Contract"]["parameters"]["url"] == f"={EXAMPLE_BASE_URL}/openapi.json"
    )
    assert "x-primary-data-query-contract" in batch_nodes["Discover Datasets"]["parameters"]["url"]
    assert "query_batch_endpoint" in batch_nodes["Query Batch"]["parameters"]["url"]
    assert EXAMPLE_BASE_URL in batch_nodes["Discover Datasets"]["parameters"]["url"]
    assert EXAMPLE_BASE_URL in batch_nodes["Get Dataset Summary"]["parameters"]["url"]
    assert EXAMPLE_BASE_URL in batch_nodes["Query Batch"]["parameters"]["url"]
    assert "/openapi.json" in n8n_query_batch_workflow["_comment"]
    assert "x-primary-data-query-contract" in n8n_query_batch_workflow["_comment"]
    assert "Private profiles do not silently fall back to Algenta cloud." in n8n_query_batch_workflow[
        "_comment"
    ]

    sql_report_node_names = {node["name"] for node in n8n_sql_report_workflow["nodes"]}
    assert n8n_sql_report_workflow["name"] == "Algenta — Discover Dataset and SQL Report"
    assert {
        "Get Contract",
        "Discover Datasets",
        "Get Dataset Summary",
        "Query SQL Report",
    }.issubset(sql_report_node_names)
    sql_report_nodes = {node["name"]: node for node in n8n_sql_report_workflow["nodes"]}
    assert (
        sql_report_nodes["Get Contract"]["parameters"]["url"]
        == f"={EXAMPLE_BASE_URL}/openapi.json"
    )
    assert (
        "x-primary-data-query-contract"
        in sql_report_nodes["Discover Datasets"]["parameters"]["url"]
    )
    assert EXAMPLE_BASE_URL in sql_report_nodes["Discover Datasets"]["parameters"]["url"]
    assert EXAMPLE_BASE_URL in sql_report_nodes["Get Dataset Summary"]["parameters"]["url"]
    assert "search=orders" in sql_report_nodes["Discover Datasets"]["parameters"]["url"]
    assert EXAMPLE_BASE_URL in sql_report_nodes["Query SQL Report"]["parameters"]["url"]
    assert "query_sql_report_endpoint" in sql_report_nodes["Query SQL Report"]["parameters"]["url"]
    assert "/openapi.json" in n8n_sql_report_workflow["_comment"]
    assert "x-primary-data-query-contract" in n8n_sql_report_workflow["_comment"]
    assert "Private profiles do not silently fall back to Algenta cloud." in n8n_sql_report_workflow[
        "_comment"
    ]

    assert make_contract_request["method"] == "GET"
    assert make_contract_request["url"] == f"{EXAMPLE_BASE_URL}/v1/meta/contract"
    assert make_contract_request["headers"]["Authorization"] == "Bearer <YOUR_ALGENTA_API_KEY>"
    assert make_openapi_contract_request["method"] == "GET"
    assert make_openapi_contract_request["url"] == f"{EXAMPLE_BASE_URL}/openapi.json"
    assert (
        make_openapi_contract_request["headers"]["Authorization"]
        == "Bearer <YOUR_ALGENTA_API_KEY>"
    )
    make_readme = (ROOT / "examples" / "make" / "README.md").read_text()
    assert "/openapi.json" in make_readme
    assert "x-primary-data-query-contract" in make_readme
    assert "openapi_contract_request.json" in make_readme
    assert "openapi_contract_request.json" in make_doc
    assert make_query_batch["queries"][0]["key"] == "completed_orders"
    assert make_query_batch["defaults"]["dataset_id"] == "orders_facts"
    assert make_query_batch["defaults"]["filter"]["conditions"][0]["value"] == "completed"
    assert make_sql_report["sources"][0]["alias"] == "orders"
    assert "select order_month" in make_sql_report["sql"]
    assert make_sql_report["max_rows"] == 100

    assert zapier_contract_request["method"] == "GET"
    assert zapier_contract_request["url"] == f"{EXAMPLE_BASE_URL}/v1/meta/contract"
    assert (
        zapier_contract_request["headers"]["Authorization"]
        == "Bearer <YOUR_ALGENTA_API_KEY>"
    )
    assert zapier_openapi_contract_request["method"] == "GET"
    assert zapier_openapi_contract_request["url"] == f"{EXAMPLE_BASE_URL}/openapi.json"
    assert (
        zapier_openapi_contract_request["headers"]["Authorization"]
        == "Bearer <YOUR_ALGENTA_API_KEY>"
    )
    zapier_readme = (ROOT / "examples" / "zapier" / "README.md").read_text()
    assert "/openapi.json" in zapier_readme
    assert "x-primary-data-query-contract" in zapier_readme
    assert "openapi_contract_request.json" in zapier_readme
    assert "openapi_contract_request.json" in zapier_doc
    assert zapier_query_batch["queries"][1]["key"] == "monthly_completed_orders"
    assert zapier_query_batch["defaults"]["dataset_id"] == "orders_facts"
    assert zapier_query_batch["defaults"]["filter"]["conditions"][0]["op"] == "eq"
    assert zapier_sql_report["sources"][0]["dataset_id"] == "orders_facts"
    assert "select order_month" in zapier_sql_report["sql"]

    colab_text = "\n".join("".join(cell.get("source", [])) for cell in colab_notebook["cells"])
    assert "# Algenta — Google Colab" in colab_text
    assert "Algenta Decision Engine" not in colab_text
    assert "/v1/meta/contract" in colab_text
    assert "/openapi.json" in colab_text
    assert "x-primary-data-query-contract" in colab_text
    assert "def load_contract() -> dict:" in colab_text
    assert "/v1/data?search=orders&compact=1&limit=5" in colab_text
    assert "/v1/data/{dataset_id}/summary" in colab_text
    assert "/v1/query/batch" in colab_text
    assert "/v1/query/sql-report" in colab_text
    assert "/v1/simulate" in colab_text
    assert 'BASE_URL = "https://your-algenta-base-url.example"' in colab_text
    assert "Private profiles do not silently fall back to Algenta cloud." in colab_text


def test_service_first_docs_keep_runtime_and_sdk_surfaces_distinct() -> None:
    ts_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "typescript.md").read_text()
    python_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "python.md").read_text()
    competitor = (ROOT / "apps" / "docs" / "docs" / "competitor-compatibility.md").read_text()
    readme = (ROOT / "README.md").read_text()
    cli_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "cli.md").read_text()
    connect_docs = (ROOT / "apps" / "docs" / "docs" / "connect-register-sources.md").read_text()
    local_runtime = (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md"
    ).read_text()
    trust_model = (ROOT / "apps" / "docs" / "docs" / "trust-model.md").read_text()
    local_runtime_example = (ROOT / "examples" / "local-runtime" / "README.md").read_text()

    assert 'import { AlgentaClient } from "algenta-sdk";' in ts_sdk
    assert 'import { DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT } from "algenta-sdk";' in ts_sdk
    assert "await client.simulate({" in ts_sdk
    assert "await client.submitJob({" in ts_sdk
    assert 'import { libraries } from "algenta-sdk";' in ts_sdk
    assert "await catalog.ab_testing.sample_size_proportion({" in ts_sdk
    assert "Local consumer sync checklist" in ts_sdk
    assert "pnpm --dir packages/ts-sdk build" in ts_sdk
    assert "pagination-only `listDatasets(...)` shape" in ts_sdk
    assert "`listDatasets({ page?, limit? })`" not in ts_sdk
    assert "stale `algenta-sdk` build" in ts_sdk
    assert "new Runtime({" not in ts_sdk
    assert 'import { Runtime } from "algenta-sdk";' not in ts_sdk
    assert "Use the TypeScript SDK after the service is already running." in ts_sdk
    assert "const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;" in ts_sdk
    assert 'throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");' in ts_sdk
    assert 'apiKey: "de_live_xxxxxxxxxxxxxxxxxxxxxxxx"' not in ts_sdk
    assert 'apiKey: "de_test_xxxxxxxxxxxxxxxxxxxxxxxx"' not in ts_sdk

    assert "from decision_engine import AlgentaClient" in python_sdk
    assert "from decision_engine import DEFAULT_BASE_URL, PRIMARY_DATA_QUERY_CONTRACT" in python_sdk
    assert "client.simulate(" in python_sdk
    assert "client.submit_job(" in python_sdk
    assert "from algenta import Runtime" not in python_sdk
    assert "Use the Python SDK after the service is already running." in python_sdk
    assert 'pip install "algenta-core[cloud]"' in python_sdk
    assert 'Runtime(mode="api")' in python_sdk
    assert "fail closed" in python_sdk
    assert "artifacts together" in python_sdk
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in python_sdk
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in python_sdk
    assert 'api_key="de_live_xxxxxxxxxxxxxxxxxxxxxxxx"' not in python_sdk
    assert 'api_key="de_test_xxxxxxxxxxxxxxxxxxxxxxxx"' not in python_sdk

    assert "Vanna" in competitor
    assert "Cube" in competitor
    assert "LlamaIndex" in competitor
    assert "Python and TypeScript both expose runtime and direct-client parity" in competitor
    assert "persisted replay, audit-artifact, and policy-snapshot operator surfaces" in competitor
    assert "higher-level example and operator-story symmetry" in competitor
    assert "listAgentRuns" in competitor
    assert "artifacts" in competitor
    assert "Competitor Compatibility" in readme
    assert '"host": "db.example.com"' in readme
    assert '"database": "orders"' in readme
    assert '"user": "analytics"' in readme
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in readme
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in readme
    assert "const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;" in readme
    assert 'throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");' in readme
    assert "### Mission local API + MCP stack" in readme
    assert "ALGENTA_ENV_FILE=/absolute/path/to/.env.local ./scripts/start-local.sh" in readme
    assert "ALGENTA_API_PORT=8010 ALGENTA_MCP_PORT=8011 ./scripts/start-local.sh" in readme
    assert "./scripts/stop-local.sh" in readme
    assert "ALGENTA_API_PORT=8060 ALGENTA_MCP_PORT=8061 ./scripts/stop-local.sh" in readme
    assert "./scripts/status-local.sh" in readme
    assert "active, stale, missing a lease, or missing a listener" in readme
    assert "./scripts/status-local.sh --format json" in readme
    assert "structured JSON instead" in readme
    assert "`scripts/start-local.sh` loads `ALGENTA_ENV_FILE` (or `DE_ENV_FILE`)" in readme
    assert "`provider.router` on `/v1/models`" in readme
    assert "The launcher now fail-closes if" in readme
    assert "`ALGENTA_LLM_PROVIDER_MODELS_JSON` is malformed" in readme
    assert "it only reports" in readme
    assert "`provider.router enabled`" in readme
    assert "Explicit startup env overrides such as `ALGENTA_API_PORT=...`," in readme
    assert "`ALGENTA_MCP_PORT=...`, and `ALGENTA_LLM_PROVIDER_MODELS_JSON=...` win over" in readme
    assert "`scripts/detach_process.py` so they survive the startup shell itself" in readme
    assert "isolated `uv run`" in readme
    assert "`requirements-mcp.txt`" in readme
    assert "`/mcp/sse`" in readme
    assert "fails closed if either the API `/v1/health`" in readme
    assert "Same-port reruns retire the previous API and MCP" in readme
    assert "`build/start-local/*.lease`" in readme
    assert "The launcher also prunes orphaned" in readme
    assert "`build/start-local/*.pid` files when the matching lease is gone" in readme
    assert "standalone MCP `/mcp/tools` endpoint never becomes ready" in readme
    assert "refuses to clobber it" in readme
    assert "only stops prior launcher-managed" in readme
    assert "`build/start-local/*.pid`" in readme
    assert "/openapi.json" in readme
    assert "x-primary-data-query-contract" in readme
    assert "algenta import" in cli_sdk
    assert "does **not** persist" in cli_sdk
    assert "de data list --search orders --compact --limit 5" in cli_sdk
    assert "de data summary orders_facts" in cli_sdk
    assert "de data query-batch batch_request.json" in cli_sdk
    assert "de data sql-report sql_report_request.json" in cli_sdk
    assert '"completed_order_count"' in cli_sdk
    assert "select order_month, gross_revenue from orders" in cli_sdk
    assert "algenta import" in connect_docs
    assert '"host": "db.example.com"' in connect_docs
    assert '"database": "orders"' in connect_docs
    assert '"user": "analytics"' in connect_docs
    assert "from algenta import Runtime" in local_runtime
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in local_runtime
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in local_runtime
    assert 'rt = Runtime(api_key=api_key)' in local_runtime
    assert "plan = rt.resolve" in local_runtime
    assert "result = rt.query(plan)" in local_runtime
    assert "get_contract()" in local_runtime
    assert "get_dataset_summary" in local_runtime
    assert "query_with_metadata()" in local_runtime
    assert "query_batch()" in local_runtime
    assert "query_sql_report()" in local_runtime
    assert "GET /v1/meta/contract" in local_runtime
    assert "/openapi.json" in local_runtime
    assert "x-primary-data-query-contract" in local_runtime
    assert "POST /v1/query/sql-report" in local_runtime
    assert "bounded-lifetime replacement key" in local_runtime
    assert "ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY> python3 scripts/verify_local_api_key_runtime.py" in local_runtime
    assert 'pip install "algenta-core[cloud]"' in local_runtime
    assert 'Runtime(mode="api")' in local_runtime
    assert "algenta-sdk" in local_runtime
    assert "artifacts together" in local_runtime
    assert "artifacts together" in local_runtime
    assert "const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;" in local_runtime
    assert 'throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");' in local_runtime
    assert "const rt = new Runtime({ apiKey });" in local_runtime
    assert "This hosted local-execution example is the Cloud Managed path." in local_runtime
    assert "pass an explicit self-hosted `base_url`" in local_runtime
    assert "pass an explicit self-hosted `baseUrl`" in local_runtime
    assert "Canonical env vars on this hosted-local path are `ALGENTA_API_KEY` and" in local_runtime
    assert "`ALGENTA_BASE_URL`. Legacy `DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL`" in local_runtime
    assert "remain accepted for compatibility." in local_runtime
    assert "fail closed" in local_runtime
    assert "silently falling back to Algenta cloud." in local_runtime
    assert 'new Runtime({ apiKey: "<YOUR_ALGENTA_API_KEY>" })' in trust_model
    assert 'Runtime(api_key="<YOUR_ALGENTA_API_KEY>")' in trust_model
    assert "immutable audit-log artifacts" in trust_model
    assert "execution-policy snapshots" in trust_model
    assert 'de_live_...' not in trust_model
    assert "Algenta — Local Runtime" in local_runtime_example
    assert 'pip install "algenta-core[cloud]"' in local_runtime_example
    assert 'Runtime(mode="api")' in local_runtime_example
    assert "algenta-sdk" in local_runtime_example
    assert "artifacts together" in local_runtime_example
    assert "artifacts together" in local_runtime_example
    assert "rt.get_contract()" in local_runtime_example
    assert 'runs = rt.list_agent_runs(status="requires_approval", limit=10)' in local_runtime_example
    assert 'checkpoints = rt.query_agent_run_checkpoints(run_id="run_agent_123", limit=10)' in local_runtime_example
    assert 'mission_events = rt.query_agent_run_mission_events(run_id="run_agent_123", limit=25)' in local_runtime_example
    assert 'telemetry = rt.query_agent_run_telemetry(run_id="run_agent_123", limit=25)' in local_runtime_example
    assert 'replayed = rt.replay_agent_run("run_agent_123", checkpoint_id="cp_2")' in local_runtime_example
    assert 'forked = rt.fork_agent_run("run_agent_123", checkpoint_id="cp_1")' in local_runtime_example
    assert "audit_artifacts = rt.get_audit_log_artifacts(limit=20)" in local_runtime_example
    assert "policy_snapshots = rt.list_execution_policy_snapshots()" in local_runtime_example
    assert "ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY> python3 scripts/verify_local_api_key_runtime.py" in local_runtime_example
    assert "de login <YOUR_ALGENTA_API_KEY>" in local_runtime_example
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in local_runtime_example
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in local_runtime_example
    assert 'rt = Runtime(api_key=api_key)' in local_runtime_example
    assert 'rt.list_datasets(search="orders", compact=True, limit=5)' in local_runtime_example
    assert "rt.get_dataset_summary" in local_runtime_example
    assert "rt.query_with_metadata(" in local_runtime_example
    assert "rt.query_batch(" in local_runtime_example
    assert "rt.query_sql_report(" in local_runtime_example
    assert "await rt.getContract()" in local_runtime_example
    assert 'const runs = await rt.listAgentRuns({ status: "requires_approval", limit: 10 });' in local_runtime_example
    assert 'const checkpoints = await rt.queryAgentRunCheckpoints({ run_id: "run_agent_123", limit: 10 });' in local_runtime_example
    assert 'const missionEvents = await rt.queryAgentRunMissionEvents({ run_id: "run_agent_123", limit: 25 });' in local_runtime_example
    assert 'const telemetry = await rt.queryAgentRunTelemetry({ run_id: "run_agent_123", limit: 25 });' in local_runtime_example
    assert 'const replayed = await rt.replayAgentRun("run_agent_123", { checkpoint_id: "cp_2" });' in local_runtime_example
    assert 'const forked = await rt.forkAgentRun("run_agent_123", { checkpoint_id: "cp_1" });' in local_runtime_example
    assert "const auditArtifacts = await rt.getAuditLogArtifacts({ limit: 20 });" in local_runtime_example
    assert "const policySnapshots = await rt.listExecutionPolicySnapshots();" in local_runtime_example
    assert '"completed_order_count"' in local_runtime_example
    assert '"order_month"' in local_runtime_example
    assert "gross_revenue" in local_runtime_example
    assert (
        'await rt.listDatasets({ search: "orders", compact: true, limit: 5 })'
        in local_runtime_example
    )
    assert "await rt.getDatasetSummary" in local_runtime_example
    assert "await rt.queryWithMetadata({" in local_runtime_example
    assert "await rt.queryBatch({" in local_runtime_example
    assert "await rt.querySqlReport({" in local_runtime_example
    assert "const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;" in local_runtime_example
    assert 'throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");' in local_runtime_example
    assert "const rt = new Runtime({ apiKey });" in local_runtime_example
    assert "These hosted local-execution examples are the Cloud Managed path." in local_runtime_example
    assert "pass an explicit self-hosted `base_url` /" in local_runtime_example
    assert "`baseUrl`" in local_runtime_example
    assert "Canonical env vars on this hosted-local path are `ALGENTA_API_KEY` and" in local_runtime_example
    assert (
        "`ALGENTA_BASE_URL`. Legacy `DE_API_KEY`, `DE_BASE_URL`, and `ALGENTA_API_URL`"
        in local_runtime_example
    )
    assert "remain accepted for compatibility." in local_runtime_example
    multi_hop_readme = (ROOT / "examples" / "multi-hop" / "README.md").read_text()
    assert 'Authorization: Bearer <YOUR_ALGENTA_API_KEY>' in multi_hop_readme
    assert "de_live_YOUR_KEY" not in multi_hop_readme
    assert "fail closed" in local_runtime_example
    assert "silently falling back to Algenta cloud." in local_runtime_example
    assert "GET /v1/meta/contract" in local_runtime_example
    assert "/openapi.json" in local_runtime_example
    assert "x-primary-data-query-contract" in local_runtime_example
    assert "POST /v1/query/batch" in local_runtime_example


def test_public_package_and_export_surfaces_use_algenta_branding() -> None:
    python_sdk_pyproject = (ROOT / "packages" / "python-sdk" / "pyproject.toml").read_text()
    ts_sdk_package = (ROOT / "packages" / "ts-sdk" / "package.json").read_text()
    export_router = (ROOT / "apps" / "api_server" / "routers" / "export.py").read_text()
    simulation_templates = (ROOT / "apps" / "api_server" / "simulation_templates.py").read_text()
    python_sdk_exceptions = (
        ROOT / "packages" / "python-sdk" / "decision_engine" / "exceptions.py"
    ).read_text()
    python_sdk_models = (
        ROOT / "packages" / "python-sdk" / "decision_engine" / "models.py"
    ).read_text()
    mcp_init = (ROOT / "apps" / "mcp_server" / "__init__.py").read_text()
    email_service = (ROOT / "apps" / "api_server" / "services" / "email_service.py").read_text()
    jobs_router = (ROOT / "apps" / "api_server" / "routers" / "jobs.py").read_text()
    products_router = (ROOT / "apps" / "api_server" / "routers" / "products.py").read_text()
    legacy_api_main = (ROOT / "apps" / "api-server" / "main.py").read_text()
    readme = (ROOT / "README.md").read_text()

    assert "Python SDK for Algenta" in python_sdk_pyproject
    assert "Algenta Decision Engine" not in python_sdk_pyproject
    assert "SDK for Algenta public data, query, and simulation APIs" in ts_sdk_package
    assert '"algenta"' in ts_sdk_package
    assert "Algenta SDK errors" in python_sdk_exceptions
    assert "Decision Engine SDK errors" not in python_sdk_exceptions
    assert "Algenta Python SDK" in python_sdk_models
    assert "Decision Engine SDK" not in python_sdk_models
    assert "Algenta API and runtime" in mcp_init
    assert "decision engine" not in mcp_init.lower()
    assert "Quota exhausted — Algenta" in email_service
    assert "80% quota used — Algenta" in email_service
    assert "Decision Engine (" not in email_service
    assert "test webhook from the Algenta API" in jobs_router
    assert "test webhook from the Decision Engine" not in jobs_router
    assert "wraps Algenta decision analysis" in products_router
    assert "API — no statistics or simulation expertise required." in products_router
    assert "wraps Decision Engine" not in products_router
    assert 'title="Algenta API"' in legacy_api_main
    assert "Universal Decision Engine" not in legacy_api_main
    assert "cold `AlgentaClient(api_key=...)` construction" in readme
    assert "cold `AsyncAlgentaClient(api_key=...)` construction" in readme
    assert "cold `DecisionEngineClient(api_key=...)` construction" not in readme
    assert "That constructor is the local/runtime-first surface." in readme
    assert "For Cloud Managed API usage," in readme
    assert "private profiles fail closed and do not" in readme

    assert "# Algenta — Simulation Run Export" in export_router
    assert 'pdf.cell(0, 12, "Algenta"' in export_router
    assert "Algenta Decision Engine" not in export_router

    assert "Universal Domain Template Library for Algenta." in simulation_templates
    assert "Algenta Decision Engine" not in simulation_templates


def test_readme_documents_self_hosted_saved_connector_and_runtime_library_surfaces() -> None:
    readme = (ROOT / "README.md").read_text()

    assert "GET /v1/data?search=...&compact=1" in readme
    assert "GET /v1/data/{dataset_id}/summary" in readme
    assert "POST /v1/query" in readme
    assert (
        "governed discovery/query and simulation workflows share the same backend/runtime core"
        in readme
    )
    assert "Local helper APIs" in readme
    assert "list_datasets" in readme
    assert "get_dataset_summary" in readme
    assert "query_with_metadata" in readme
    assert "query_batch" in readme
    assert "query_sql_report" in readme
    assert 'rt = Runtime(mode="self_hosted", api_key=api_key, base_url="http://localhost:8000")' in readme
    assert "connector = rt.create_connector(" in readme
    assert "rt.test_connector(connector.id)" in readme
    assert "rt.browse_connector(connector.id)" in readme
    assert "rt.list_datasets()" in readme
    assert "rt.get_dataset_summary(" in readme
    assert "rt.refresh_dataset(" in readme
    assert "de data list --search orders --compact --limit 5" in readme
    assert "de data summary orders_facts" in readme
    assert "de data query-batch batch_request.json" in readme
    assert "de data sql-report sql_report_request.json" in readme
    assert "de contract" in readme
    assert "de runtime modules --format json" in readme
    assert "de runtime functions text.tokenizer --format json" in readme
    assert "de runtime execute rerank_eval hit_rate_at_k" in readme
    assert "list_runtime_libraries" in readme
    assert "execute_runtime_library" in readme
    assert 'import { Runtime } from "algenta-sdk";' in readme
    assert 'mode: "self_hosted"' in readme
    assert "apiKey," in readme
    assert "await rt.createConnector(" in readme
    assert "await rt.testConnector(connector.id)" in readme
    assert "await rt.browseConnector(connector.id)" in readme
    assert "connectorId: connector.id" in readme
    assert "await rt.listDatasets()" in readme
    assert "await rt.getDatasetSummary(dataset.dataset_id!)" in readme
    assert "await rt.refreshDataset(dataset.dataset_id!)" in readme
    assert "query_with_metadata" in readme
    assert "get_contract" in readme
    assert "query_batch" in readme
    assert "query_sql_report" in readme
    assert "getContract" in readme
    assert "queryWithMetadata" in readme
    assert "queryBatch" in readme
    assert "querySqlReport" in readme
    assert "from algenta import libraries" in readme
    assert 'catalog = libraries(mode="local"' in readme
    assert "catalog.list_modules()" in readme
    assert "catalog.ab_testing" in readme
    assert (
        "Python `libraries()` and `MojoRuntime` stay local/runtime-backed, accept local `api_key` and `base_url` for licensed local execution, and still reject non-local modes"
        in readme
    )
    assert (
        "TypeScript `libraries()` and `MojoRuntime` stay local/runtime-backed in this rollout"
        in readme
    )
    assert "hosted or self-hosted generic Mojo dispatch is not part of this surface" in readme
    assert 'tcpAddress: process.env.ALGENTA_DAEMON_TCP ?? "127.0.0.1:50099"' in readme
    assert "/v1/libraries" not in readme
