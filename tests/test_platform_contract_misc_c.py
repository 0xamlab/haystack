"""Tests for test_platform_contract: misc_c.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-4/tests/test_platform_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_platform_contract_helpers import *  # noqa: F401,F403


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


