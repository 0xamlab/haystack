"""Tests for test_runtime_surface_compatibility: misc_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-4/tests/test_runtime_surface_compatibility.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_surface_compatibility_helpers import *  # noqa: F401,F403


def test_competitor_compatibility_docs_lock_match_and_non_match_decisions() -> None:
    competitor = (ROOT / "apps" / "docs" / "docs" / "competitor-compatibility.md").read_text(
        encoding="utf-8"
    )
    trust_model = (ROOT / "apps" / "docs" / "docs" / "trust-model.md").read_text(
        encoding="utf-8"
    )
    local_runtime = (
        ROOT / "apps" / "docs" / "docs" / "integrations" / "local-runtime.md"
    ).read_text(encoding="utf-8")
    python_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "python.md").read_text(
        encoding="utf-8"
    )
    ts_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "typescript.md").read_text(
        encoding="utf-8"
    )

    assert "Vanna" in competitor
    assert "Cube" in competitor
    assert "LlamaIndex" in competitor
    assert "Must match:" in competitor
    assert "Should match:" in competitor
    assert "Intentional non-match:" in competitor
    assert "Python and TypeScript both expose runtime and direct-client parity" in competitor
    assert "persisted replay, audit-artifact, and policy-snapshot operator surfaces" in competitor
    assert "higher-level example and operator-story symmetry" in competitor
    assert "listAgentRuns" in competitor
    assert "LLM-to-SQL as the primary execution path" in competitor
    assert "semantic-model-first product core" in competitor
    assert "probabilistic agent-centric execution" in competitor
    assert "from algenta import Runtime" in local_runtime
    assert "plan = rt.resolve" in local_runtime
    assert "result = rt.query(plan)" in local_runtime
    assert "de runtime admin-modules --format json" in local_runtime
    assert "de runtime admin-benchmarks --format json" in local_runtime
    assert "benchmark-class `evidence_paths`" in local_runtime
    assert "get_runtime_modules" in local_runtime
    assert "get_runtime_benchmarks" in local_runtime
    assert "rt.get_audit_logs(...)" in local_runtime
    assert "rt.get_audit_log_artifacts(...)" in local_runtime
    assert "rt.list_execution_policy_snapshots()" in local_runtime
    assert "rt.list_agent_runs(...)" in local_runtime
    assert "rt.list_agent_run_checkpoints(run_id)" in local_runtime
    assert "rt.query_agent_run_checkpoints(...)" in local_runtime
    assert "rt.list_agent_run_mission_events(run_id, limit=...)" in local_runtime
    assert "rt.query_agent_run_mission_events(...)" in local_runtime
    assert "rt.list_agent_run_telemetry(run_id, limit=...)" in local_runtime
    assert "rt.query_agent_run_telemetry(...)" in local_runtime
    assert "rt.replay_agent_run(run_id, checkpoint_id=...)" in local_runtime
    assert "rt.fork_agent_run(run_id, checkpoint_id=...)" in local_runtime
    assert "await rt.getAuditLogArtifacts({ ... })" in local_runtime
    assert "await rt.listExecutionPolicySnapshots()" in local_runtime
    assert "await rt.listAgentRuns({ ... })" in local_runtime
    assert "await rt.replayAgentRun(runId, { checkpoint_id })" in local_runtime
    assert "await rt.forkAgentRun(runId, { checkpoint_id })" in local_runtime
    assert "list_connectors(page=..., limit=...)" in local_runtime
    assert "create_connector(...)" in local_runtime
    assert "get_connector(...)" in local_runtime
    assert "update_connector(...)" in local_runtime
    assert "test_connector(...)" in local_runtime
    assert "browse_connector(...)" in local_runtime
    assert "delete_connector(...)" in local_runtime
    assert "connect_data(...)" in local_runtime
    assert "get_dataset(dataset_id)" in local_runtime
    assert "refresh_dataset(dataset_id)" in local_runtime
    assert "delete_dataset(dataset_id)" in local_runtime
    assert "create_repository_snapshot(repository_id, request)" in local_runtime
    assert "get_repository_snapshot(repository_id, snapshot_id)" in local_runtime
    assert "triage_repository(repository_id, request)" in local_runtime
    assert "create_repository_decision_plan(repository_id, request)" in local_runtime
    assert "simulate_repository(repository_id, request)" in local_runtime
    assert "apply_repository(repository_id, request)" in local_runtime
    assert "listConnectors({ page, limit })" in local_runtime
    assert "createConnector(...)" in local_runtime
    assert "getConnector(...)" in local_runtime
    assert "updateConnector(...)" in local_runtime
    assert "testConnector(...)" in local_runtime
    assert "browseConnector(...)" in local_runtime
    assert "deleteConnector(...)" in local_runtime
    assert "connect(source?, { name?, description?, connectorId?, connector?, selection?, datasetName?, persist?, visibility?, connectionName? })" in local_runtime
    assert "getDataset(datasetId)" in local_runtime
    assert "refreshDataset(datasetId)" in local_runtime
    assert "deleteDataset(datasetId)" in local_runtime
    assert "GET /v1/connectors" in local_runtime
    assert "POST /v1/connectors/{connector_id}/test" in local_runtime
    assert "POST /v1/data/connect" in local_runtime
    assert "POST /v1/data/{dataset_id}/refresh" in local_runtime
    assert "POST /v1/repositories/{repository_id}/snapshots" in local_runtime
    assert "POST /v1/repositories/{repository_id}/decision-plans" in local_runtime
    assert "POST /v1/repositories/{repository_id}/simulate" in local_runtime
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1" in (
        local_runtime
    )
    assert "ALGENTA_RUNTIME_REPOSITORY_INTELLIGENCE_BACKEND" in local_runtime
    assert 'repository_intelligence_backend="my_repo_backend.module:build_backend"' in (
        local_runtime
    )
    assert "register_repository_intelligence_backend" in local_runtime
    assert "local_repository_intelligence_backend_required" in local_runtime
    assert "repository_local_planner_unsupported" in local_runtime
    assert "planner_model_id" in local_runtime
    assert "planner_execution_mode" in local_runtime
    assert "planner_provider_backend" in local_runtime
    assert "const previewTest = await client.previewTestConnector({" in ts_sdk
    assert "const previewBrowse = await client.previewBrowseConnector({" in ts_sdk
    assert "ALGENTA_LLM_PROVIDER_MODELS_JSON" in ts_sdk
    assert "openai_compatible" in ts_sdk
    assert "openai" in ts_sdk
    assert "anthropic" in ts_sdk
    assert "ollama" in ts_sdk
    assert "google_genai" in ts_sdk
    assert "mistral" in ts_sdk
    assert "cohere" in ts_sdk
    assert "groq" in ts_sdk
    assert "xai" in ts_sdk
    assert "router" in ts_sdk
    assert '"targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"]' in ts_sdk
    assert '"fallback_policy": "retryable_only"' in ts_sdk
    assert '"fallback_on": ["provider_rate_limited", "provider_timeout"]' in ts_sdk
    assert '"timeout_seconds": 18.0' in ts_sdk
    assert '"header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"}' in ts_sdk
    assert '"max_attempts": 2' in ts_sdk
    assert '"chat_targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"]' in ts_sdk
    assert '"embedding_targets": ["provider.openai-gpt-4o-mini"]' in ts_sdk
    assert '"chat_fallback_policy": "retryable_only"' in ts_sdk
    assert '"chat_fallback_on": ["provider_rate_limited"]' in ts_sdk
    assert '"embedding_fallback_policy": "disabled"' in ts_sdk
    assert '"embedding_fallback_on": ["provider_backend_error"]' in ts_sdk
    assert '"chat_timeout_seconds": 12.5' in ts_sdk
    assert '"embedding_timeout_seconds": 9.0' in ts_sdk
    assert "required_provider_headers" in ts_sdk
    assert "chat_required_provider_headers" in ts_sdk
    assert "embedding_required_provider_headers" in ts_sdk
    assert "provider_auth_env_vars" in ts_sdk
    assert "chat_provider_auth_env_vars" in ts_sdk
    assert "embedding_provider_auth_env_vars" in ts_sdk
    assert "provider_auth_configured" in ts_sdk
    assert "chat_provider_auth_configured" in ts_sdk
    assert "embedding_provider_auth_configured" in ts_sdk
    assert "resolved_routing_targets" in ts_sdk
    assert "resolved_chat_routing_targets" in ts_sdk
    assert "resolved_embedding_routing_targets" in ts_sdk
    assert '"chat_max_attempts": 2' in ts_sdk
    assert '"embedding_max_attempts": 1' in ts_sdk
    assert "Legacy `upstream_model`" in ts_sdk
    assert "`capabilities` is optional" in ts_sdk
    assert "optional `api_key_env`" in ts_sdk
    assert "chat-completions only" in ts_sdk
    assert "client.resolveArtifactBridge({ repo_id, filename, revision, local_files_only })" in ts_sdk
    assert "const savedConnector = await client.createConnector({" in ts_sdk
    assert "const testedConnector = await client.testConnector(savedConnector.id);" in ts_sdk
    assert "const browsedConnector = await client.browseConnector(savedConnector.id);" in ts_sdk
    assert "const updatedConnector = await client.updateConnector(savedConnector.id, {" in ts_sdk
    assert "const created = await client.connectData({" in ts_sdk
    assert "const refreshed = await client.refreshDataset(created.dataset_id);" in ts_sdk
    assert "const detail = await client.getDataset(created.dataset_id);" in ts_sdk
    assert "createConnector(...)" in ts_sdk
    assert "getConnector(...)" in ts_sdk
    assert "updateConnector(...)" in ts_sdk
    assert "testConnector(...)" in ts_sdk
    assert "browseConnector(...)" in ts_sdk
    assert "deleteConnector(...)" in ts_sdk
    assert "previewTestConnector({ connector })" in ts_sdk
    assert "previewBrowseConnector({ connector })" in ts_sdk
    assert "connectData(...)" in ts_sdk
    assert "getDataset(...)" in ts_sdk
    assert "refreshDataset(...)" in ts_sdk
    assert "deleteDataset(...)" in ts_sdk
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1" in ts_sdk
    assert "repository_local_planner_unsupported" in ts_sdk
    assert "planner_model_id" in ts_sdk
    assert "planner_execution_mode" in ts_sdk
    assert "planner_provider_backend" in ts_sdk
    assert "immutable audit-log artifacts" in trust_model
    assert "execution-policy snapshots" in trust_model
    assert "from decision_engine import AlgentaClient" in python_sdk
    assert "ALGENTA_LLM_PROVIDER_MODELS_JSON" in python_sdk
    assert "openai_compatible" in python_sdk
    assert "openai" in python_sdk
    assert "anthropic" in python_sdk
    assert "ollama" in python_sdk
    assert "google_genai" in python_sdk
    assert "mistral" in python_sdk
    assert "cohere" in python_sdk
    assert "groq" in python_sdk
    assert "xai" in python_sdk
    assert "router" in python_sdk
    assert '"targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"]' in python_sdk
    assert '"fallback_policy": "retryable_only"' in python_sdk
    assert '"fallback_on": ["provider_rate_limited", "provider_timeout"]' in python_sdk
    assert '"timeout_seconds": 18.0' in python_sdk
    assert '"header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"}' in python_sdk
    assert '"max_attempts": 2' in python_sdk
    assert '"chat_targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"]' in python_sdk
    assert '"embedding_targets": ["provider.openai-gpt-4o-mini"]' in python_sdk
    assert '"chat_fallback_policy": "retryable_only"' in python_sdk
    assert '"chat_fallback_on": ["provider_rate_limited"]' in python_sdk
    assert '"embedding_fallback_policy": "disabled"' in python_sdk
    assert '"embedding_fallback_on": ["provider_backend_error"]' in python_sdk
    assert '"chat_timeout_seconds": 12.5' in python_sdk
    assert '"embedding_timeout_seconds": 9.0' in python_sdk
    assert "required_provider_headers" in python_sdk
    assert "chat_required_provider_headers" in python_sdk
    assert "embedding_required_provider_headers" in python_sdk
    assert "provider_auth_env_vars" in python_sdk
    assert "chat_provider_auth_env_vars" in python_sdk
    assert "embedding_provider_auth_env_vars" in python_sdk
    assert "provider_auth_configured" in python_sdk
    assert "chat_provider_auth_configured" in python_sdk
    assert "embedding_provider_auth_configured" in python_sdk
    assert "resolved_routing_targets" in python_sdk
    assert "resolved_chat_routing_targets" in python_sdk
    assert "resolved_embedding_routing_targets" in python_sdk
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1" in (
        python_sdk
    )
    assert "repository_local_planner_unsupported" in python_sdk
    assert "planner_model_id" in python_sdk
    assert "planner_execution_mode" in python_sdk
    assert "planner_provider_backend" in python_sdk
    cli_docs = (ROOT / "apps" / "docs" / "docs" / "sdks" / "cli.md").read_text(encoding="utf-8")
    assert "de llm models --format json" in cli_docs
    assert "capability-specific chat/embedding auth-header readiness" in cli_docs
    assert '"chat_max_attempts": 2' in python_sdk
    assert '"embedding_max_attempts": 1' in python_sdk
    assert "Legacy `upstream_model`" in python_sdk
    assert "`capabilities` is optional" in python_sdk
    assert "optional `api_key_env`" in python_sdk
    assert "chat-completions only" in python_sdk
    assert "get_runtime_modules()" in python_sdk
    assert "get_runtime_benchmarks()" in python_sdk
    assert "benchmark-class `evidence_paths`" in python_sdk
    assert "list_agent_runs(...)" in python_sdk
    assert "list_agent_run_checkpoints(run_id)" in python_sdk
    assert "query_agent_run_checkpoints(...)" in python_sdk
    assert "list_agent_run_mission_events(run_id, limit=...)" in python_sdk
    assert "query_agent_run_mission_events(...)" in python_sdk
    assert "list_agent_run_telemetry(run_id, limit=...)" in python_sdk
    assert "query_agent_run_telemetry(...)" in python_sdk
    assert "replay_agent_run(run_id, checkpoint_id=...)" in python_sdk
    assert "fork_agent_run(run_id, checkpoint_id=...)" in python_sdk
    assert "get_audit_logs(...)" in python_sdk
    assert "get_audit_log_artifacts(...)" in python_sdk
    assert "list_execution_policy_snapshots()" in python_sdk
    assert "result = client.simulate(" in python_sdk
    assert "job = client.submit_job(" in python_sdk
    assert "status = client.get_job(job.job_id)" in python_sdk
    assert "result = client.get_job_result(job.job_id)" in python_sdk
    assert 'result = client.poll_job(job.job_id, timeout=60.0, poll_interval=2.0)' in python_sdk
    assert "client.cancel_job(job.job_id)" in python_sdk
    assert 'webhook = client.test_webhook_delivery("https://example.test/webhook")' in python_sdk
    assert "preview_test = client.preview_test_connector(" in python_sdk
    assert "preview_browse = client.preview_browse_connector(" in python_sdk
    assert "connector = client.create_connector(" in python_sdk
    assert "tested = client.test_connector(connector.id)" in python_sdk
    assert "browsed = client.browse_connector(connector.id)" in python_sdk
    assert "updated = client.update_connector(" in python_sdk
    assert "created = client.connect_data(" in python_sdk
    assert "refreshed = client.refresh_dataset(created.dataset_id)" in python_sdk
    assert "detail = client.get_dataset(created.dataset_id)" in python_sdk
    assert "`algenta.Runtime(mode=\"api\")` and `Runtime(mode=\"self_hosted\")`" in python_sdk
    assert "`create_repository_snapshot(...)`, `get_repository_snapshot(...)`" in python_sdk
    assert "`simulate_repository(...)`, and `apply_repository(...)`." in python_sdk
    assert "create_connector(...)" in python_sdk
    assert "get_connector(...)" in python_sdk
    assert "update_connector(...)" in python_sdk
    assert "test_connector(...)" in python_sdk
    assert "browse_connector(...)" in python_sdk
    assert "delete_connector(...)" in python_sdk
    assert "preview_test_connector(connector={...})" in python_sdk
    assert "preview_browse_connector(connector={...})" in python_sdk
    assert "connect_data(...)" in python_sdk
    assert "get_dataset(...)" in python_sdk
    assert "refresh_dataset(...)" in python_sdk
    assert "delete_dataset(...)" in python_sdk
    assert 'import { AlgentaClient } from "algenta-sdk";' in ts_sdk
    assert "getRuntimeModules()" in ts_sdk
    assert "getRuntimeBenchmarks()" in ts_sdk
    assert "listAgentRuns({ ... })" in ts_sdk
    assert "listAgentRunCheckpoints(runId)" in ts_sdk
    assert "queryAgentRunCheckpoints({ ... })" in ts_sdk
    assert "listAgentRunMissionEvents(runId, { limit })" in ts_sdk
    assert "queryAgentRunMissionEvents({ ... })" in ts_sdk
    assert "listAgentRunTelemetry(runId, { limit })" in ts_sdk
    assert "queryAgentRunTelemetry({ ... })" in ts_sdk
    assert "replayAgentRun(runId, { checkpoint_id })" in ts_sdk
    assert "forkAgentRun(runId, { checkpoint_id })" in ts_sdk
    assert "getAuditLogs({ ... })" in ts_sdk
    assert "getAuditLogArtifacts({ ... })" in ts_sdk
    assert "listExecutionPolicySnapshots()" in ts_sdk
    assert "const result = await client.simulate({" in ts_sdk
    assert "const job = await client.submitJob({" in ts_sdk
    assert "const status = await client.getJob(job.job_id);" in ts_sdk
    assert "const result = await client.getJobResult(job.job_id);" in ts_sdk
    assert "const result = await client.pollJob(job.job_id, {" in ts_sdk
    assert "await client.cancelJob(job.job_id);" in ts_sdk
    assert 'const webhook = await client.testWebhookDelivery("https://example.test/webhook");' in ts_sdk
    assert 'tcpAddress: process.env.ALGENTA_DAEMON_TCP ?? "127.0.0.1:50099"' in ts_sdk
    assert "local/runtime-backed in this rollout" in ts_sdk
    assert "/v1/libraries" not in ts_sdk


def test_typescript_runtime_live_script_covers_api_helper_surface() -> None:
    typescript_runtime_live = (
        ROOT / "tests" / "integration" / "test_typescript_runtime_live.py"
    ).read_text(encoding="utf-8")
    ts_readme = (ROOT / "packages" / "ts-sdk" / "README.md").read_text(
        encoding="utf-8"
    )

    assert "TypeScript Runtime(mode='api') LLM helper surface" in typescript_runtime_live
    assert "TypeScript Runtime(mode='api') decision runtime helpers" in typescript_runtime_live
    assert "TypeScript Runtime(mode='api') plan + agent-run helpers" in typescript_runtime_live
    assert "TypeScript Runtime(mode='api') account helpers" in typescript_runtime_live
    assert "TypeScript Runtime(mode='api') team/credits/metering/audit/execution-policy helpers" in typescript_runtime_live
    assert "TypeScript Runtime(mode='api') deployment lifecycle" in typescript_runtime_live
    assert '_node_api_helper_probe("llm")' in typescript_runtime_live
    assert '_node_api_helper_probe("decision")' in typescript_runtime_live
    assert '_node_api_helper_probe("plan_agent")' in typescript_runtime_live
    assert '_node_api_helper_probe("account")' in typescript_runtime_live
    assert '_node_api_helper_probe("control_plane", webhook_url=callback_url)' in typescript_runtime_live
    assert '_node_api_helper_probe("deployment")' in typescript_runtime_live
    assert '("/v1/webhooks/test", "post")' in typescript_runtime_live
    assert '("/v1/credits/refresh", "post")' in typescript_runtime_live
    assert "classify_simulation_capacity_blocker" in typescript_runtime_live
    assert "_ISOLATED_API_SERVER_ACTIVE = False" in typescript_runtime_live
    assert "if _ISOLATED_API_SERVER_ACTIVE:" in typescript_runtime_live
    assert "_endpoint_serves_canonical_runtime_surface(" in typescript_runtime_live
    assert "_endpoint_supports_loopback_dataset_preview(BASE_URL)" in typescript_runtime_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in typescript_runtime_live
    assert '_emit(f"  ... {name}")' in typescript_runtime_live
    assert '_emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")' in (
        typescript_runtime_live
    )
    assert 'const rt = new Runtime({' in ts_readme
    assert 'const models = await rt.listModels();' in ts_readme
    assert 'const tokenized = await rt.tokenize({ input: "alpha beta" });' in ts_readme
    assert "const usage = await rt.usage();" in ts_readme
    assert 'const recommendation = await rt.recommend(' in ts_readme
    assert "Runtime forwards the governed helper groups" in ts_readme
    assert "models and vector utilities" in ts_readme
    assert "account and team controls" in ts_readme
    assert "connectors, datasets" in ts_readme
    assert "repository intelligence, agent runs" in ts_readme
    assert "deployment" in ts_readme
    assert "lifecycle, and decision helpers" in ts_readme


def test_typescript_sdk_readme_mentions_unified_capability_plane_examples() -> None:
    ts_readme = (ROOT / "packages" / "ts-sdk" / "README.md").read_text(encoding="utf-8")

    assert "## Unified Capability Plane" in ts_readme
    assert "client.routeCapabilities({" in ts_readme
    assert "client.executeCapability({" in ts_readme
    assert "client.listCapabilityProviders()" in ts_readme
    assert "client.listSkills()" in ts_readme
    assert "client.listMcpProviders()" in ts_readme
    assert "examples/capability-plane/" in ts_readme
    assert "examples/langgraph/capability_router.py" in ts_readme


def test_sdk_docs_call_out_local_runtime_capability_ownership_boundaries() -> None:
    python_sdk_doc = (ROOT / "apps" / "docs" / "docs" / "sdks" / "python.md").read_text(
        encoding="utf-8"
    )
    typescript_sdk_doc = (ROOT / "apps" / "docs" / "docs" / "sdks" / "typescript.md").read_text(
        encoding="utf-8"
    )

    assert '`client_managed` capabilities' in python_sdk_doc
    assert '`algenta_managed` capabilities remain' in python_sdk_doc
    assert '`Runtime(mode="api")` or `Runtime(mode="self_hosted")`' in python_sdk_doc

    assert '`client_managed` capabilities' in typescript_sdk_doc
    assert '`algenta_managed` capabilities remain' in typescript_sdk_doc
    assert "switch back to the running Algenta service" in typescript_sdk_doc


def test_live_mcp_integration_script_tracks_runtime_proof_catalog() -> None:
    mcp_integration = (ROOT / "tests" / "integration" / "test_mcp_server.py").read_text(
        encoding="utf-8"
    )

    assert "ROOT = Path(__file__).resolve().parents[2]" in mcp_integration
    assert "sys.path.insert(0, str(ROOT))" in mcp_integration
    assert "def _resolve_base_url() -> str:" in mcp_integration
    assert "def _endpoint_serves_canonical_mcp_contract(base_url: str) -> bool:" in mcp_integration
    assert '"apps.api_server.main:app"' in mcp_integration
    assert "atexit.register(_cleanup_runtime)" in mcp_integration
    assert '"list_models"' in mcp_integration
    assert '"create_agent_run"' in mcp_integration
    assert '"list_team_members"' in mcp_integration
    assert '"get_me"' in mcp_integration
    assert '"get_limits"' in mcp_integration
    assert '"list_distributions"' in mcp_integration
    assert '"list_templates"' in mcp_integration
    assert '"list_api_keys"' in mcp_integration
    assert '"create_connector"' in mcp_integration
    assert '"get_connector"' in mcp_integration
    assert '"update_connector"' in mcp_integration
    assert '"test_connector"' in mcp_integration
    assert '"preview_test_connector"' in mcp_integration
    assert '"browse_connector"' in mcp_integration
    assert '"preview_browse_connector"' in mcp_integration
    assert '"delete_connector"' in mcp_integration
    assert '"invite_team_member"' in mcp_integration
    assert '"update_team_member_role"' in mcp_integration
    assert '"remove_team_member"' in mcp_integration
    assert '"get_audit_logs"' in mcp_integration
    assert '"get_audit_log_artifacts"' in mcp_integration
    assert '"get_execution_policy"' in mcp_integration
    assert '"list_execution_policy_snapshots"' in mcp_integration
    assert '"list_agent_runs"' in mcp_integration
    assert '"get_agent_run_checkpoints"' in mcp_integration
    assert '"query_agent_run_checkpoints"' in mcp_integration
    assert '"get_agent_run_mission_events"' in mcp_integration
    assert '"query_agent_run_mission_events"' in mcp_integration
    assert '"get_agent_run_telemetry"' in mcp_integration
    assert '"query_agent_run_telemetry"' in mcp_integration
    assert "test_control_plane_tools" in mcp_integration
    assert "listed_distributions" in mcp_integration
    assert "listed_templates" in mcp_integration
    assert '"list_deployment_regions"' in mcp_integration
    assert '"get_deployment"' in mcp_integration
    assert '"get_deployment_cost"' in mcp_integration
    assert "test_deployment_tools" in mcp_integration
    assert "test_tool_connector_saved_lifecycle" in mcp_integration
    assert "test_tool_llm_provider_trace_is_explicit_for_utility_outputs" in mcp_integration
    assert '"provider_attempts"' in mcp_integration
    assert 'call_tool("get_runtime_manifest", {})' in mcp_integration
    assert 'call_tool("get_runtime_modules", {})' in mcp_integration
    assert 'call_tool("get_runtime_benchmarks", {})' in mcp_integration
    assert 'call_tool("get_runtime_release_validation", {})' in mcp_integration
    assert 'SUITE_NAME = "mcp_server_integration"' in mcp_integration
    assert "write_live_integration_summary_from_results(" in mcp_integration
    assert "Summary artifact:" in mcp_integration
    assert 'print(f"  ... {name}", flush=True)' in mcp_integration
    assert "PlatformContractResponse.model_validate(contract)" in mcp_integration
    assert "from tests._manifest_backed_integrations import (" in mcp_integration
    assert "contract_integrations_match_manifest" in mcp_integration
    assert 'contract_integrations_match_manifest(contract_body["integrations"])' in (
        mcp_integration
    )
    assert "resolve_local_live_base_url" not in mcp_integration
