"""Tests for test_package_distribution_surface: misc_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-1/tests/test_package_distribution_surface.py during modularization.
"""
from __future__ import annotations

from tests._test_package_distribution_surface_helpers import *  # noqa: F401,F403


def test_python_package_readmes_exist_and_match_declared_metadata() -> None:
    for package_dir in ("packages/python-sdk", "packages/algenta"):
        project_root = ROOT / package_dir
        pyproject = tomllib.loads((project_root / "pyproject.toml").read_text())
        assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
        readme_name = pyproject["project"]["readme"]
        readme_path = project_root / readme_name
        assert readme_path.exists()
        text = readme_path.read_text()
        assert "PRIMARY_DATA_QUERY_CONTRACT" in text
        assert "contract_endpoint" in text
    assert "get_contract" in text
    assert "list_connectors" in text
    assert "connect_data" in text
    assert "get_dataset" in text
    assert "get_dataset_summary" in text
    assert "refresh_dataset" in text
    assert "delete_dataset" in text
    assert "query_batch" in text
    assert "query_sql_report" in text
    assert "/openapi.json" in text
    assert "x-primary-data-query-contract" in text


def test_typescript_sdk_types_lock_provider_catalog_and_trace_contract() -> None:
    # types.ts is now a barrel that re-exports sub-modules; concat the
    # barrel + every _types_*.ts to cover the same textual surface.
    src_dir = ROOT / "packages" / "ts-sdk" / "src"
    text = (src_dir / "types.ts").read_text() + "\n".join(
        p.read_text() for p in sorted(src_dir.glob("_types_*.ts"))
    )

    assert "provider_backend: string | null;" in text
    assert "provider_model_id: string | null;" in text
    assert "provider_attempts: ProviderAttemptResponse[];" in text
    assert "provider_auth_configured: boolean;" in text
    assert "chat_provider_auth_configured: boolean;" in text
    assert "embedding_provider_auth_configured: boolean;" in text
    assert "routing_targets: string[];" in text
    assert "resolved_routing_targets: string[];" in text
    assert "required_provider_headers: string[];" in text
    assert "chat_required_provider_headers: string[];" in text
    assert "embedding_required_provider_headers: string[];" in text
    assert "chat_provider_auth_env_vars: string[];" in text
    assert "embedding_provider_auth_env_vars: string[];" in text
    assert "provider_attempts?: ProviderAttemptResponse[];" not in text


def test_python_sdk_readme_covers_direct_client_contract() -> None:
    text = (ROOT / "packages" / "python-sdk" / "README.md").read_text()
    assert "AlgentaClient" in text
    assert "de_live_" not in text
    assert 'api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")' in text
    assert 'raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")' in text
    assert "api_key=api_key," in text
    assert "QueryFilterCondition" in text
    assert "QueryFilterSpec" in text
    assert "client.get_contract()" in text
    assert "client.get_runtime_manifest()" in text
    assert "client.get_runtime_modules()" in text
    assert "client.get_runtime_benchmarks()" in text
    assert "client.get_runtime_release_validation()" in text
    assert "benchmark-class `evidence_paths`" in text
    assert "`B6`" in text
    assert "checkpoint and" in text
    assert "replay overhead" in text
    assert "`B7` MCP tool latency" in text
    assert "`B9`" in text
    assert "RAG retrieval" in text
    assert "quality and" in text
    assert "latency" in text
    assert "`B10` decision workflow completion latency" in text
    assert "`mcp_call_first_party`" in text
    assert "`decision_plan_creation`" in text
    assert "`replay`" in text
    assert "client.list_models()" in text
    assert "client.resolve_artifact_bridge(repo_id=..., filename=..., revision=..., local_files_only=True)" in text
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1" in text
    assert "repository_local_planner_unsupported" in text
    assert "planner_model_id" in text
    assert "planner_execution_mode" in text
    assert "planner_provider_backend" in text
    assert "ALGENTA_LLM_PROVIDER_MODELS_JSON" in text
    assert "openai_compatible" in text
    assert "openai" in text
    assert "anthropic" in text
    assert "ollama" in text
    assert "google_genai" in text
    assert "mistral" in text
    assert "cohere" in text
    assert "groq" in text
    assert "xai" in text
    assert "router" in text
    assert '"targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"]' in text
    assert '"fallback_policy": "retryable_only"' in text
    assert '"fallback_on": ["provider_rate_limited", "provider_timeout"]' in text
    assert '"timeout_seconds": 18.0' in text
    assert '"header_envs": {"OpenAI-Organization": "OPENAI_ORG_ID"}' in text
    assert '"max_attempts": 2' in text
    assert '"chat_targets": ["provider.groq-llama", "provider.openai-gpt-4o-mini"]' in text
    assert '"embedding_targets": ["provider.openai-gpt-4o-mini"]' in text
    assert '"chat_fallback_policy": "retryable_only"' in text
    assert '"chat_fallback_on": ["provider_rate_limited"]' in text
    assert '"embedding_fallback_policy": "disabled"' in text
    assert '"embedding_fallback_on": ["provider_backend_error"]' in text
    assert '"chat_timeout_seconds": 12.5' in text
    assert '"embedding_timeout_seconds": 9.0' in text
    assert "required_provider_headers" in text
    assert "chat_required_provider_headers" in text
    assert "embedding_required_provider_headers" in text
    assert "provider_auth_env_vars" in text
    assert "chat_provider_auth_env_vars" in text
    assert "embedding_provider_auth_env_vars" in text
    assert "provider_auth_configured" in text
    assert "chat_provider_auth_configured" in text
    assert "embedding_provider_auth_configured" in text
    assert "resolved_routing_targets" in text
    assert "resolved_chat_routing_targets" in text
    assert "resolved_embedding_routing_targets" in text
    assert '"chat_max_attempts": 2' in text
    assert '"embedding_max_attempts": 1' in text
    assert "Legacy `upstream_model`" in text
    assert "`capabilities` is optional" in text
    assert "optional `api_key_env`" in text
    assert "chat-completions only" in text
    assert 'client.tokenize(text, model="text.tokenizer")' in text
    assert "client.chat_completions(messages, model=\"text.tokenizer\")" in text
    assert "client.stream_chat_completions(messages, model=\"text.tokenizer\")" in text
    assert "client.stream_responses(input_value, model=\"text.tokenizer\", dimensions=64)" in text
    assert "client.plan_decision(request)" in text
    assert "client.log_decision(request)" in text
    assert "client.list_decisions(page=..., limit=..., with_outcome_only=...)" in text
    assert "client.get_decision(decision_id)" in text
    assert "client.record_outcome(decision_id, actual_outcome=..., outcome_notes=...)" in text
    assert "client.execute_decision(decision_id, webhook_url=..., timeout_seconds=...)" in text
    assert "client.delete_decision(decision_id)" in text
    assert "client.create_agent_run(task=..., approval_mode=..., ...)" in text
    assert "client.list_agent_runs(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=...)" in text
    assert "client.get_agent_run_events(run_id, limit=...)" in text
    assert "client.stream_agent_run_events(run_id, limit=...)" in text
    assert "client.list_agent_run_checkpoints(run_id)" in text
    assert "client.query_agent_run_checkpoints(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., checkpoint_id=...)" in text
    assert "client.list_agent_run_mission_events(run_id, limit=...)" in text
    assert "client.query_agent_run_mission_events(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., event_type=...)" in text
    assert "client.list_agent_run_telemetry(run_id, limit=...)" in text
    assert "client.query_agent_run_telemetry(page=..., limit=..., status_filter=..., request_hash=..., policy_snapshot_id=..., schema_snapshot_id=..., run_id=..., telemetry_kind=..., module_name=...)" in text
    assert "client.replay_agent_run(run_id, checkpoint_id=...)" in text
    assert "client.fork_agent_run(run_id, checkpoint_id=...)" in text
    assert "get_billing_info()" in text
    assert 'create_billing_checkout(plan="developer" | "pro")' in text
    assert "create_billing_portal()" in text
    assert 'refresh_credits(device_id=..., billing_period="YYYY-MM", credits_used=...)' in text
    assert "ingest_metering_events(device_id=..., events=[...])" in text
    assert "client.create_repository_snapshot(repository_id, request)" in text
    assert "client.get_repository_snapshot(repository_id, snapshot_id)" in text
    assert "client.triage_repository(repository_id, request)" in text
    assert "client.create_repository_decision_plan(repository_id, request)" in text
    assert "client.simulate_repository(repository_id, request)" in text
    assert "client.apply_repository(repository_id, request)" in text
    assert 'invite_team_member(email=..., role="member")' in text
    assert 'update_team_member_role(user_id, role="viewer")' in text
    assert "remove_team_member(user_id)" in text
    assert "get_audit_logs(page=..., limit=..., actor_email=..., action=..., resource_type=..., result=..., policy_snapshot_id=..., schema_snapshot_id=..., manifest_version=..., request_hash=...)" in text
    assert "get_audit_log_artifacts(page=..., limit=..., actor_email=..., action=..., resource_type=..., result=..., policy_snapshot_id=..., schema_snapshot_id=..., manifest_version=..., request_hash=..., content_hash=...)" in text
    assert "list_execution_policy_snapshots()" in text
    assert "distributions()" in text
    assert "templates()" in text
    assert "list_devices(page=..., limit=...)" in text
    assert "revoke_device(registration_id)" in text
    assert "register_trigger(name=..., condition=..., simulation_template=..., webhook_url=..., execution_webhook_url=..., auto_execute=..., description=...)" in text
    assert "list_triggers(status=\"all\", page=..., limit=...)" in text
    assert "fire_trigger(trigger_id, force=False)" in text
    assert "pause_trigger(trigger_id, paused=True | False)" in text
    assert "delete_trigger(trigger_id)" in text
    assert "connector = client.create_connector(" in text
    assert "detail = client.get_connector(connector.id)" in text
    assert "updated = client.update_connector(" in text
    assert "tested = client.test_connector(connector.id)" in text
    assert "browsed = client.browse_connector(connector.id)" in text
    assert "created = client.connect_data(" in text
    assert "dataset = client.get_dataset(created.dataset_id)" in text
    assert "refreshed = client.refresh_dataset(created.dataset_id)" in text
    assert "client.delete_dataset(created.dataset_id)" in text
    assert "client.delete_connector(connector.id)" in text
    assert "create_connector(name=..., connector_type=..., description=..., config={...})" in text
    assert "get_connector(connector_id)" in text
    assert "update_connector(connector_id, description=..., config={...})" in text
    assert "test_connector(connector_id)" in text
    assert "browse_connector(connector_id)" in text
    assert "delete_connector(connector_id)" in text
    assert "preview_test_connector(connector={...})" in text
    assert "preview_browse_connector(connector={...})" in text
    assert "connect_data(connection_type=..., provider=..., dataset_name=..., description=..., connection_config={...})" in text
    assert "get_dataset(dataset_id)" in text
    assert "refresh_dataset(dataset_id)" in text
    assert "delete_dataset(dataset_id)" in text
    assert 'client.list_datasets(search="orders", compact=True)' in text
    assert "client.get_dataset_summary" in text
    assert "client.query_with_metadata" in text
    assert "client.query_batch" in text
    assert "client.query_sql_report" in text
    assert "/openapi.json" in text
    assert "x-primary-data-query-contract" in text
    assert '"sources": [{"dataset_id": summary.dataset_id, "alias": "orders"}]' in text
    assert (
        '"sql": "SELECT order_month, gross_revenue FROM orders ORDER BY order_month DESC LIMIT 12"'
        in text
    )
    assert "`query()` remains available and unchanged" in text
    assert "ALGENTA_DEPLOYMENT_MODE=self_hosted" in text
    assert "ALGENTA_DEPLOYMENT_MODE=air_gapped" in text
    assert "must point `base_url` at your own" in text
    assert "fail closed instead of silently falling back to" in text


def test_algenta_core_readme_covers_runtime_and_local_library_contracts() -> None:
    text = (ROOT / "packages" / "algenta" / "README.md").read_text()

    assert len(text.splitlines()) <= 260
    assert "Runtime" in text
    assert "de_live_" not in text
    assert 'pip install "algenta[cloud]"' in text
    assert 'Runtime(mode="api")' in text
    assert 'mode="self_hosted"' in text
    assert 'base_url="http://localhost:8000"' in text
    assert 'base_url="https://api.algenta.ai"' not in text
    assert "intentionally fails closed" in text
    assert "algenta-sdk" in text
    assert "Users do not install Mojo" in text
    assert "launch a daemon" in text
    assert "PRIMARY_DATA_QUERY_CONTRACT" in text
    assert "contract_endpoint" in text
    assert "/openapi.json" in text
    assert "x-primary-data-query-contract" in text
    assert "get_contract()" in text
    assert "list_connectors()" in text
    assert "connect_data()" in text
    assert "get_dataset()" in text
    assert "get_dataset_summary()" in text
    assert "refresh_dataset()" in text
    assert "delete_dataset()" in text
    assert "query_batch()" in text
    assert "query_sql_report()" in text
    assert "get_runtime_manifest()" in text
    assert "get_runtime_modules()" in text
    assert "get_runtime_benchmarks()" in text
    assert "get_runtime_release_validation()" in text
    assert "list_runtime_libraries" in text
    assert "execute_runtime_library" in text
    assert "https://docs.algenta.ai/sdk/python" in text


def test_package_readmes_cover_unified_capability_plane_surface() -> None:
    python_readme = (ROOT / "packages" / "python-sdk" / "README.md").read_text()
    ts_readme = (ROOT / "packages" / "ts-sdk" / "README.md").read_text()
    core_readme = (ROOT / "packages" / "algenta" / "README.md").read_text()
    text = core_readme

    assert "## Unified Capability Plane" in python_readme
    assert "client.route_capabilities(" in python_readme
    assert "client.get_capability(route.selected_capability_id, include_instruction=True)" in python_readme
    assert "client.execute_capability(" in python_readme
    assert "client.list_capability_providers()" in python_readme
    assert "client.list_skills()" in python_readme
    assert "client.list_mcp_providers()" in python_readme
    assert "Execution ownership remains authoritative" in python_readme
    assert "`algenta_managed` capabilities must" in python_readme
    assert "`client_managed` capabilities and fail closed otherwise" in python_readme
    assert "examples/capability-plane/" in python_readme
    assert "examples/langgraph/capability_router.py" in python_readme

    assert "## Unified Capability Plane" in ts_readme
    assert "client.routeCapabilities({" in ts_readme
    assert "client.getCapability(route.selected_capability_id" in ts_readme
    assert "client.executeCapability({" in ts_readme
    assert "client.listCapabilityProviders()" in ts_readme
    assert "client.listSkills()" in ts_readme
    assert "client.listMcpProviders()" in ts_readme
    assert "Execution ownership remains authoritative" in ts_readme
    assert "`algenta_managed` capabilities must" in ts_readme
    assert "`client_managed` capabilities and fail closed otherwise" in ts_readme
    assert "examples/capability-plane/" in ts_readme
    assert "examples/langgraph/capability_router.py" in ts_readme

    assert "## Unified Capability Plane" in core_readme
    assert "runtime.route_capabilities(" in core_readme
    assert "runtime.get_capability(" in core_readme
    assert "runtime.execute_capability(" in core_readme
    assert "runtime.list_capability_providers()" in core_readme
    assert "runtime.list_skills()" in core_readme
    assert "runtime.list_mcp_providers()" in core_readme
    assert "runtime.register_capability_adapter(adapter)" in core_readme
    assert "Local runtime execution fails closed for `algenta_managed`" in core_readme
    assert "`Runtime(mode=\"api\")` or `Runtime(mode=\"self_hosted\")`" in core_readme
    assert "only `client_managed` capabilities" in core_readme
    assert "examples/capability-plane/" in core_readme
    assert "examples/langgraph/capability_router.py" in core_readme
