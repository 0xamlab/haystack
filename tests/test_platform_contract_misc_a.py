"""Tests for test_platform_contract: misc_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-4/tests/test_platform_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_platform_contract_helpers import *  # noqa: F401,F403


def test_manifest_declares_canonical_contract() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["brand"] == "Codna"
    assert manifest["api_base_url"] == "https://api.codna.ai"
    assert manifest["mcp_endpoint"] == "https://api.codna.ai/mcp/sse"
    assert manifest["auth_scheme"] == "bearer_api_key"
    assert manifest["api_key_prefixes"] == {"live": "de_live_", "test": "de_test_"}
    assert manifest["compatibility"]["deprecation_window_days"] == 90
    assert manifest["privacy_registry"]["algenta_owned_hosts"][0] == "codna.ai"
    assert manifest["privacy_registry"]["algenta_owned_suffixes"] == [
        ".codna.ai",
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
    assert data_query["direct_sdk"]["python"]["preferred_client_class"] == "CodnaClient"
    assert (
        data_query["direct_sdk"]["python"]["preferred_async_client_class"] == "AsyncCodnaClient"
    )
    assert data_query["direct_sdk"]["python"]["contract_method"] == "get_contract"
    assert data_query["direct_sdk"]["typescript"]["import_package"] == "algenta-sdk"
    assert data_query["direct_sdk"]["typescript"]["preferred_client_class"] == "CodnaClient"
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
    assert "decision_engine.CodnaClient" in api_reference
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
    assert schema["info"]["title"] == "Codna API"
    assert "governed data discovery" in schema["info"]["description"]
    assert schema["servers"] == [{"url": "https://api.codna.ai"}]
    assert schema["x-canonical-mcp-endpoint"] == "https://api.codna.ai/mcp/sse"
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
        == "CodnaClient"
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
    assert "`X-Codna-Device-Id`" in auth_text
    assert "`X-Codna-Platform`" in auth_text
    assert "`X-Codna-Hostname-Hash`" in auth_text
    assert "`X-Codna-Device-Binding-Token`" in auth_text
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
    assert "`X-Codna-Device-Id`" in quickstart
    assert "`X-Codna-Platform`" in quickstart
    assert "`X-Codna-Hostname-Hash`" in quickstart
    assert "`X-Codna-Device-Binding-Token`" in quickstart
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
    assert "`X-Codna-Device-Id`" in direct_api
    assert "`X-Codna-Platform`" in direct_api
    assert "`X-Codna-Hostname-Hash`" in direct_api
    assert "`X-Codna-Device-Binding-Token`" in direct_api
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
    assert "`X-Codna-Device-Id`" in readme
    assert "`X-Codna-Platform`" in readme
    assert "`X-Codna-Hostname-Hash`" in readme
    assert "`X-Codna-Device-Binding-Token`" in readme
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
    assert "Add Codna as a tool node" in langgraph
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
    assert "from decision_engine import CodnaClient" in langgraph_example
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


