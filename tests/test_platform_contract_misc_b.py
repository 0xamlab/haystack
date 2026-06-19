"""Tests for test_platform_contract: misc_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-4/tests/test_platform_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_platform_contract_helpers import *  # noqa: F401,F403


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
    assert "Private profiles do not silently fall back to Codna cloud." in n8n_query_batch_workflow[
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
    assert "Private profiles do not silently fall back to Codna cloud." in n8n_sql_report_workflow[
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
    assert "Private profiles do not silently fall back to Codna cloud." in colab_text


