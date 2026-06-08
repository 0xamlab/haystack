from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

# ruff: noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from algenta import Runtime

from apps.mcp_server.registry import TOOLS, get_tool_specs


def test_python_runtime_primary_surface_is_runtime_first() -> None:
    runtime = Runtime()

    for method_name in (
        "connect",
        "create_connector",
        "test_connector",
        "browse_connector",
        "get_dataset_summary",
        "get_contract",
        "get_runtime_manifest",
        "resolve",
        "verify",
        "query",
        "query_with_metadata",
        "query_batch",
        "query_sql_report",
        "import_preview",
        "import_bundle_preview",
        "list_connectors",
        "list_datasets",
        "refresh_dataset",
        "create_repository_snapshot",
        "get_repository_snapshot",
        "triage_repository",
        "create_repository_decision_plan",
        "simulate_repository",
        "apply_repository",
    ):
        method = getattr(runtime, method_name, None)
        assert callable(method), method_name


def test_python_algenta_package_exports_runtime_library_surface() -> None:
    algenta = importlib.import_module("algenta")
    algenta_runtime = importlib.import_module("algenta.runtime")
    decision_engine = importlib.import_module("decision_engine")
    decision_engine_client = importlib.import_module("decision_engine.client")
    decision_engine_async_client = importlib.import_module("decision_engine.async_client")

    assert callable(algenta.Runtime)
    assert callable(algenta.libraries)
    assert callable(algenta.MojoRuntime)
    assert hasattr(algenta, "QueryFilterCondition")
    assert hasattr(algenta, "QueryFilterSpec")
    assert hasattr(algenta_runtime, "QueryFilterCondition")
    assert hasattr(algenta_runtime, "QueryFilterSpec")
    assert hasattr(decision_engine, "QueryFilterCondition")
    assert hasattr(decision_engine, "QueryFilterSpec")
    assert hasattr(decision_engine_client, "QueryFilterCondition")
    assert hasattr(decision_engine_client, "QueryFilterSpec")
    assert hasattr(decision_engine_async_client, "QueryFilterCondition")
    assert hasattr(decision_engine_async_client, "QueryFilterSpec")
    assert hasattr(algenta, "ConnectorMetadata")
    assert hasattr(algenta, "ConnectorTestOutput")
    assert hasattr(algenta, "ConnectorBrowseOutput")
    assert hasattr(algenta, "DatasetList")
    assert hasattr(algenta, "DatasetSelectionSummary")
    assert hasattr(algenta, "DatasetSummary")
    assert hasattr(algenta, "QueryExecutionMetadata")
    assert hasattr(algenta, "QueryWithMetadataOutput")
    assert hasattr(algenta, "QueryBatchOutput")
    assert hasattr(algenta, "QuerySqlReportOutput")
    assert hasattr(algenta, "RepositorySnapshotOutput")
    assert hasattr(algenta, "RepositoryTriageOutput")
    assert hasattr(algenta, "RepositoryAnalysisOutput")
    assert hasattr(algenta, "DecisionEnvelopeOutput")
    assert hasattr(algenta, "RuntimeManifestOutput")
    assert hasattr(algenta, "RuntimeSupportedChannel")
    assert hasattr(algenta, "RuntimeAuxiliaryChannel")
    assert hasattr(algenta, "RuntimeFeatureFlagChannel")
    assert hasattr(algenta, "RuntimeBenchmarkBaseline")
    assert hasattr(algenta, "RuntimeBenchmarkClassCode")
    assert hasattr(algenta, "RuntimeBenchmarkMetric")
    assert hasattr(algenta, "RuntimeDeploymentMode")
    assert hasattr(algenta, "RuntimeEvaluationDimension")
    assert hasattr(algenta, "RuntimeEvaluationMethod")
    assert hasattr(algenta, "RuntimeExecutionStateField")
    assert hasattr(algenta, "RuntimeExecutionValidityRule")
    assert hasattr(algenta, "RuntimeExternalNondeterminismSource")
    assert hasattr(algenta, "RuntimeFailureCode")
    assert hasattr(algenta, "RuntimeInvariantName")
    assert hasattr(algenta, "RuntimeArtifactLineageStep")
    assert hasattr(algenta, "RuntimeCapabilityField")
    assert hasattr(algenta, "RuntimeCapabilityRule")
    assert hasattr(algenta, "RuntimeLayer")
    assert hasattr(algenta, "RuntimeModuleId")
    assert hasattr(algenta, "RuntimePublicEndpoint")
    assert hasattr(algenta, "RuntimeAdminEndpoint")
    assert hasattr(algenta, "RuntimeFeatureFlagEndpoint")
    assert hasattr(algenta, "RuntimeLineageNodeField")
    assert hasattr(algenta, "RuntimeNondeterminismArtifact")
    assert hasattr(algenta, "RuntimeMemoryRegion")
    assert hasattr(algenta, "RuntimeMemoryRule")
    assert hasattr(algenta, "RuntimeProofObligation")
    assert hasattr(algenta, "RuntimeReleaseArtifact")
    assert hasattr(algenta, "RuntimeReleaseBlocker")
    assert hasattr(algenta, "RuntimeReleaseGateId")
    assert hasattr(algenta, "RuntimeMaturity")
    assert hasattr(algenta, "RuntimeSchedulerInvariant")
    assert hasattr(algenta, "RuntimeSchedulerMaximizeObjective")
    assert hasattr(algenta, "RuntimeSchedulerMinimizeObjective")
    assert hasattr(algenta, "RuntimeSchedulerPolicy")
    assert hasattr(algenta, "RuntimeSLOBudgetName")
    assert hasattr(algenta, "RuntimeThreatClass")
    assert hasattr(algenta, "RuntimeThreatControl")
    assert hasattr(algenta, "RuntimeThreatRule")
    assert hasattr(algenta_runtime, "RuntimeMaturity")
    assert hasattr(algenta_runtime, "RuntimeSupportedChannel")
    assert hasattr(algenta_runtime, "RuntimeAuxiliaryChannel")
    assert hasattr(algenta_runtime, "RuntimeFeatureFlagChannel")
    assert hasattr(algenta_runtime, "RuntimeBenchmarkBaseline")
    assert hasattr(algenta_runtime, "RuntimeBenchmarkClassCode")
    assert hasattr(algenta_runtime, "RuntimeBenchmarkMetric")
    assert hasattr(algenta_runtime, "RuntimeDeploymentMode")
    assert hasattr(algenta_runtime, "RuntimeEvaluationDimension")
    assert hasattr(algenta_runtime, "RuntimeEvaluationMethod")
    assert hasattr(algenta_runtime, "RuntimeExecutionStateField")
    assert hasattr(algenta_runtime, "RuntimeExecutionValidityRule")
    assert hasattr(algenta_runtime, "RuntimeExternalNondeterminismSource")
    assert hasattr(algenta_runtime, "RuntimeFailureCode")
    assert hasattr(algenta_runtime, "RuntimeInvariantName")
    assert hasattr(algenta_runtime, "RuntimeArtifactLineageStep")
    assert hasattr(algenta_runtime, "RuntimeCapabilityField")
    assert hasattr(algenta_runtime, "RuntimeCapabilityRule")
    assert hasattr(algenta_runtime, "RuntimeLayer")
    assert hasattr(algenta_runtime, "RuntimeModuleId")
    assert hasattr(algenta_runtime, "RuntimePublicEndpoint")
    assert hasattr(algenta_runtime, "RuntimeAdminEndpoint")
    assert hasattr(algenta_runtime, "RuntimeFeatureFlagEndpoint")
    assert hasattr(algenta_runtime, "RuntimeLineageNodeField")
    assert hasattr(algenta_runtime, "RuntimeNondeterminismArtifact")
    assert hasattr(algenta_runtime, "RuntimeMemoryRegion")
    assert hasattr(algenta_runtime, "RuntimeMemoryRule")
    assert hasattr(algenta_runtime, "RuntimeProofObligation")
    assert hasattr(algenta_runtime, "RuntimeReleaseArtifact")
    assert hasattr(algenta_runtime, "RuntimeReleaseBlocker")
    assert hasattr(algenta_runtime, "RuntimeReleaseGateId")
    assert hasattr(algenta_runtime, "RuntimeSchedulerInvariant")
    assert hasattr(algenta_runtime, "RuntimeSchedulerMaximizeObjective")
    assert hasattr(algenta_runtime, "RuntimeSchedulerMinimizeObjective")
    assert hasattr(algenta_runtime, "RuntimeSchedulerPolicy")
    assert hasattr(algenta_runtime, "RuntimeSLOBudgetName")
    assert hasattr(algenta_runtime, "RuntimeThreatClass")
    assert hasattr(algenta_runtime, "RuntimeThreatControl")
    assert hasattr(algenta_runtime, "RuntimeThreatRule")
    assert hasattr(decision_engine, "RuntimeManifestResult")
    assert hasattr(decision_engine, "RuntimeSupportedChannelResult")
    assert hasattr(decision_engine, "RuntimeAuxiliaryChannelResult")
    assert hasattr(decision_engine, "RuntimeFeatureFlagChannelResult")
    assert hasattr(decision_engine, "RuntimeBenchmarkBaselineResult")
    assert hasattr(decision_engine, "RuntimeBenchmarkClassCodeResult")
    assert hasattr(decision_engine, "RuntimeBenchmarkMetricResult")
    assert hasattr(decision_engine, "RuntimeDeploymentModeResult")
    assert hasattr(decision_engine, "RuntimeEvaluationDimensionResult")
    assert hasattr(decision_engine, "RuntimeEvaluationMethodResult")
    assert hasattr(decision_engine, "RuntimeExecutionStateFieldResult")
    assert hasattr(decision_engine, "RuntimeExecutionValidityRuleResult")
    assert hasattr(decision_engine, "RuntimeExternalNondeterminismSourceResult")
    assert hasattr(decision_engine, "RuntimeFailureCodeResult")
    assert hasattr(decision_engine, "RuntimeInvariantNameResult")
    assert hasattr(decision_engine, "RuntimeArtifactLineageStepResult")
    assert hasattr(decision_engine, "RuntimeCapabilityFieldResult")
    assert hasattr(decision_engine, "RuntimeCapabilityRuleResult")
    assert hasattr(decision_engine, "RuntimeLayerResult")
    assert hasattr(decision_engine, "RuntimeModuleIdResult")
    assert hasattr(decision_engine, "RuntimePublicEndpointResult")
    assert hasattr(decision_engine, "RuntimeAdminEndpointResult")
    assert hasattr(decision_engine, "RuntimeFeatureFlagEndpointResult")
    assert hasattr(decision_engine, "RuntimeLineageNodeFieldResult")
    assert hasattr(decision_engine, "RuntimeNondeterminismArtifactResult")
    assert hasattr(decision_engine, "RuntimeMemoryRegionResult")
    assert hasattr(decision_engine, "RuntimeMemoryRuleResult")
    assert hasattr(decision_engine, "RuntimeProofObligationResult")
    assert hasattr(decision_engine, "RuntimeReleaseArtifactResult")
    assert hasattr(decision_engine, "RuntimeReleaseBlockerResult")
    assert hasattr(decision_engine, "RuntimeMaturityResult")
    assert hasattr(decision_engine, "RuntimeReleaseGateIdResult")
    assert hasattr(decision_engine, "RuntimeSchedulerInvariantResult")
    assert hasattr(decision_engine, "RuntimeSchedulerMaximizeObjectiveResult")
    assert hasattr(decision_engine, "RuntimeSchedulerMinimizeObjectiveResult")
    assert hasattr(decision_engine, "RuntimeSchedulerPolicyResult")
    assert hasattr(decision_engine, "RuntimeSLOBudgetNameResult")
    assert hasattr(decision_engine, "RuntimeThreatClassResult")
    assert hasattr(decision_engine, "RuntimeThreatControlResult")
    assert hasattr(decision_engine, "RuntimeThreatRuleResult")
    assert algenta.DEFAULT_BASE_URL == "https://api.algenta.ai"
    assert algenta.AUTH_SCHEME == "bearer_api_key"
    assert (
        algenta.PRIMARY_DATA_QUERY_CONTRACT["api"]["query_sql_report_endpoint"]
        == "/v1/query/sql-report"
    )
    assert algenta.PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"] == "/v1/meta/contract"


def test_algenta_libraries_exposes_llm_rollout_canonical_module_names() -> None:
    import algenta

    catalog = algenta.libraries(mode="local", auto_start_daemon=False)
    module_names = set(catalog.names())

    assert {
        "bpe_tokenizer",
        "text.tokenizer",
        "embeddings",
        "flash_attention",
        "sparse_attention",
        "transformer_attention",
        "transformer_blocks",
        "llm_sampling",
        "vector_similarity",
        "vector_search",
        "vector_kernels.ranker",
        "vector_kernels.table",
        "sparse_vector",
        "rlhf_dpo",
        "rerank_eval",
        "inference_cost_latency",
        "kv_cache",
        "paged_kv_cache",
        "continuous_batching",
        "inference_engine",
        "speculative_decoding",
        "generation_loop",
    }.issubset(module_names)

    assert set(catalog.list_functions("text.tokenizer")) == {
        "is_stopword",
        "word_tokenize",
        "sentence_tokenize",
        "char_ngrams",
        "word_ngrams",
        "remove_stopwords",
        "stem_simple",
        "vocabulary_size",
        "token_frequency",
        "pad_sequence",
    }
    assert set(catalog.list_functions("vector_kernels.ranker")) == {"run_column_rank_v2"}
    assert set(catalog.list_functions("vector_kernels.table")) == {
        "build_query",
        "source_id_of",
        "role_id_of",
        "build_table_json",
    }
    assert set(catalog.list_functions("kv_cache")) == {
        "kv_cache_memory_per_layer",
        "kv_cache_total_memory",
        "kv_cache_utilization",
        "paged_attention_block_count",
        "prefix_cache_hit_bytes",
        "kv_eviction_score_lru",
        "kv_eviction_score_h2o",
        "incremental_decode_kv_append",
        "radix_cache_shared_prefix_len",
        "kv_quantization_error",
    }
    assert set(catalog.list_functions("generation_loop")) == {
        "temperature_logit_scale",
        "top_k_accept",
        "top_p_cumulative_accept",
        "min_p_accept",
        "repetition_penalty_logit",
        "presence_penalty_logit",
        "frequency_penalty_logit",
        "eos_stop_score",
        "eta_sampling_accept",
        "typical_sampling_accept",
    }


def test_typescript_runtime_primary_surface_is_runtime_first() -> None:
    ts_runtime = (ROOT / "packages" / "ts-sdk" / "src" / "runtime.ts").read_text(encoding="utf-8")
    ts_index = (ROOT / "packages" / "ts-sdk" / "src" / "index.ts").read_text(encoding="utf-8")

    assert "export class Runtime" in ts_runtime
    assert "connect(" in ts_runtime
    assert "resolve(" in ts_runtime
    assert "verify(" in ts_runtime
    assert "getRuntimeManifest(" in ts_runtime
    assert "getRuntimeModules(" in ts_runtime
    assert "getRuntimeBenchmarks(" in ts_runtime
    assert "getRuntimeReleaseValidation(" in ts_runtime
    assert "query(" in ts_runtime
    assert "importPreview(" in ts_runtime
    assert "importBundlePreview(" in ts_runtime
    assert "createRepositorySnapshot(" in ts_runtime
    assert "getRepositorySnapshot(" in ts_runtime
    assert "triageRepository(" in ts_runtime
    assert "createRepositoryDecisionPlan(" in ts_runtime
    assert "simulateRepository(" in ts_runtime
    assert "applyRepository(" in ts_runtime
    assert "export {" in ts_index
    assert "Runtime," in ts_index
    assert "PRIMARY_DATA_QUERY_CONTRACT" in ts_index
    assert "DEFAULT_BASE_URL" in ts_index


def test_mcp_registry_keeps_primary_and_secondary_surfaces_available() -> None:
    specs = get_tool_specs()
    spec_names = {spec["name"] for spec in specs}

    assert len(TOOLS) == 137
    assert len(specs) == 137
    assert spec_names == set(TOOLS)
    assert {
        "get_contract",
        "get_runtime_manifest",
        "get_runtime_modules",
        "get_runtime_benchmarks",
        "get_runtime_release_validation",
        "connect_data",
        "get_data_summary",
        "get_data_schema",
        "query_data",
        "query_batch",
        "query_sql_report",
        "list_models",
        "resolve_artifact_bridge",
        "tokenize",
        "count_tokens",
        "chat_completions",
        "responses",
        "embeddings",
        "embedding_similarity",
        "rerank",
        "plan_decision",
        "product_decision",
        "product_agent_run",
        "product_optimize",
        "product_retrieve",
        "product_forecast",
        "create_agent_run",
        "get_agent_run",
        "get_agent_run_events",
        "resume_agent_run",
        "cancel_agent_run",
        "approve_agent_run",
        "list_deployment_regions",
        "get_deployment",
        "create_deployment",
        "get_deployment_cost",
        "delete_deployment",
        "list_team_members",
        "invite_team_member",
        "update_team_member_role",
        "remove_team_member",
        "list_distributions",
        "list_templates",
        "list_devices",
        "revoke_device",
        "get_audit_logs",
        "get_execution_policy",
        "get_billing_info",
        "create_billing_checkout",
        "create_billing_portal",
        "refresh_credits",
        "ingest_metering_events",
        "update_execution_policy",
        "list_runtime_libraries",
        "execute_runtime_library",
        "simulate",
        "recommend",
        "score",
        "batch",
        "compare",
        "submit_job",
        "list_jobs",
        "get_job_status",
        "poll_job",
        "get_job_result",
        "cancel_job",
        "test_webhook_delivery",
        "list_runs",
        "log_decision",
        "list_decisions",
        "get_decision",
        "record_outcome",
        "execute_decision",
        "delete_decision",
        "register_trigger",
        "list_triggers",
        "fire_trigger",
        "pause_trigger",
        "delete_trigger",
        "create_connector",
        "get_connector",
        "update_connector",
        "test_connector",
        "preview_test_connector",
        "browse_connector",
        "preview_browse_connector",
        "delete_connector",
        "create_repository_snapshot",
        "get_repository_snapshot",
        "triage_repository",
        "create_repository_decision_plan",
        "query_repository_graph",
        "simulate_repository",
        "apply_repository",
    }.issubset(spec_names)


def test_cli_and_mcp_docs_cover_decision_runtime_helpers() -> None:
    cli_docs = (ROOT / "apps" / "docs" / "docs" / "sdks" / "cli.md").read_text()
    mcp_docs = (ROOT / "apps" / "docs" / "docs" / "mcp.md").read_text()
    mcp_readme = (ROOT / "apps" / "mcp_server" / "README.md").read_text()
    ts_docs = (ROOT / "apps" / "docs" / "docs" / "sdks" / "typescript.md").read_text()

    assert "de recommend recommend_request.json --format json" in cli_docs
    assert "de decision score score_request.json --format json" in cli_docs
    assert "de decision batch batch_request.json --format json" in cli_docs
    assert "de decision compare compare_request.json --format json" in cli_docs
    assert "de product decision product_decision_request.json --format json" in cli_docs
    assert "de product agent-run product_agent_run_request.json --format json" in cli_docs
    assert "de product optimize product_optimize_request.json --format json" in cli_docs
    assert "de product retrieve product_retrieve_request.json --format json" in cli_docs
    assert "de product forecast product_forecast_request.json --format json" in cli_docs
    assert "de decisions log decision_log_request.json --format json" in cli_docs
    assert "de decisions list --with-outcome-only --format json" in cli_docs
    assert "de decisions get <decision_id> --format json" in cli_docs
    assert "de decisions outcome <decision_id> decision_outcome_request.json --format json" in cli_docs
    assert "de decisions execute <decision_id> decision_execute_request.json --format json" in cli_docs
    assert "de decisions delete <decision_id> --format json" in cli_docs
    assert "de connectors create connector_request.json --format json" in cli_docs
    assert "de connectors preview-test connector_preview_request.json --format json" in cli_docs
    assert "de connectors browse <connector_id> --format json" in cli_docs
    assert "de connectors preview-browse connector_preview_request.json --format json" in cli_docs
    assert "de repositories snapshot <repository_id> repository_snapshot_request.json --format json" in cli_docs
    assert "de repositories get-snapshot <repository_id> <snapshot_id> --format json" in cli_docs
    assert "de repositories triage <repository_id> repository_triage_request.json --format json" in cli_docs
    assert "de repositories decision-plan <repository_id> repository_decision_plan_request.json --format json" in cli_docs
    assert "de repositories simulate <repository_id> repository_simulation_request.json --format json" in cli_docs
    assert "de repositories apply <repository_id> repository_apply_request.json --format json" in cli_docs
    assert "de team list --format json" in cli_docs
    assert "de account distributions --format json" in cli_docs
    assert "de account templates --format json" in cli_docs
    assert "de team invite new.user@example.com member --format json" in cli_docs
    assert "aggregate provider-auth metadata, and capability-specific chat/embedding auth-header readiness" in mcp_docs
    assert "aggregate provider-auth metadata, and capability-specific chat/embedding auth-header readiness" in mcp_readme
    assert "de team update-role user_123 viewer --format json" in cli_docs
    assert "de team remove user_123 --format json" in cli_docs
    assert "de team audit-logs --format json" in cli_docs
    assert "de team audit-artifacts --format json" in cli_docs
    assert "de devices list --format json" in cli_docs
    assert "de devices revoke <registration_id> --format json" in cli_docs
    assert "de billing info --format json" in cli_docs
    assert "de credits refresh credits_refresh_request.json --format json" in cli_docs
    assert "de execution-policy snapshots --format json" in cli_docs
    assert "de execution-policy get --format json" in cli_docs
    assert "de deployments regions --format json" in cli_docs
    assert "de deployments get --format json" in cli_docs
    assert "de deployments cost <deployment_id> --format json" in cli_docs
    assert "de job status <job_id> --format json" in cli_docs
    assert "de job result <job_id> --format json" in cli_docs
    assert "de job cancel <job_id> --format json" in cli_docs
    assert "de agent-runs list --status completed --format json" in cli_docs
    assert "de agent-runs checkpoints <run_id> --format json" in cli_docs
    assert "de agent-runs query-checkpoints --status completed --format json" in cli_docs
    assert "de agent-runs mission-events <run_id> --limit 25 --format json" in cli_docs
    assert "de agent-runs query-mission-events --status completed --format json" in cli_docs
    assert "de agent-runs telemetry <run_id> --limit 25 --format json" in cli_docs
    assert "de agent-runs query-telemetry --status completed --format json" in cli_docs
    assert "de job wait <job_id> --timeout 30 --format json" in cli_docs
    assert "de webhook test https://example.com/webhook --format json" in cli_docs
    assert "de triggers register trigger_request.json --format json" in cli_docs
    assert "de triggers list --status active --page 1 --limit 10 --format json" in cli_docs
    assert "de triggers fire <trigger_id> --force --format json" in cli_docs
    assert "de triggers pause <trigger_id> --format json" in cli_docs
    assert "de triggers resume <trigger_id> --format json" in cli_docs
    assert "de triggers delete <trigger_id> --format json" in cli_docs

    assert "`recommend(...)`, `score(...)`, `batch(...)`, or `compare(...)`" in mcp_docs
    assert (
        "`submit_job(...)`, `list_jobs(...)`, `get_job_status(...)`, "
        "`poll_job(...)`, `get_job_result(...)`, `cancel_job(...)`, and `test_webhook_delivery(...)`"
    ) in mcp_docs
    assert "`product_decision(...)`, `product_agent_run(...)`, `product_optimize(...)`, `product_retrieve(...)`, and `product_forecast(...)`" in mcp_docs
    assert "`recommend`, `score`, `batch`, and `compare`" in mcp_docs
    assert "`log_decision(...)`, `list_decisions(...)`, `get_decision(...)`, `record_outcome(...)`, `execute_decision(...)`, and `delete_decision(...)`" in mcp_docs
    assert "`list_team_members()`" in mcp_docs
    assert "`invite_team_member(email=..., role=...)`" in mcp_docs
    assert "`update_team_member_role(user_id=..., role=...)`" in mcp_docs
    assert "`remove_team_member(user_id=...)`" in mcp_docs
    assert "`list_distributions()`" in mcp_docs
    assert "`list_templates()`" in mcp_docs
    assert "`get_billing_info()`" in mcp_docs
    assert "`create_billing_checkout(plan=...)`" in mcp_docs
    assert "`create_billing_portal()`" in mcp_docs
    assert "`refresh_credits(device_id=..., billing_period=..., credits_used=...)`" in mcp_docs
    assert "`ingest_metering_events(device_id=..., events=[...])`" in mcp_docs
    assert "`register_trigger(...)`, `list_triggers(...)`, `fire_trigger(...)`, `pause_trigger(...)`, and `delete_trigger(...)`" in mcp_docs
    assert "`list_agent_runs(...)`" in mcp_docs
    assert "`get_agent_run_checkpoints(run_id)`" in mcp_docs
    assert "`query_agent_run_checkpoints(...)`" in mcp_docs
    assert "`get_agent_run_mission_events(run_id)`" in mcp_docs
    assert "`query_agent_run_mission_events(...)`" in mcp_docs
    assert "`get_agent_run_telemetry(run_id)`" in mcp_docs
    assert "`query_agent_run_telemetry(...)`" in mcp_docs
    assert "`list_devices()`" in mcp_docs
    assert "`revoke_device(registration_id=...)`" in mcp_docs
    assert "`get_audit_logs()`" in mcp_docs
    assert "`get_audit_log_artifacts()`" in mcp_docs
    assert "`get_execution_policy()`" in mcp_docs
    assert "`list_execution_policy_snapshots()`" in mcp_docs
    assert "`update_execution_policy(...)`" in mcp_docs
    assert (
        "`list_connectors`, `create_connector`, `get_connector`, `update_connector`, "
        "`test_connector`, `preview_test_connector`, `browse_connector`, "
        "`preview_browse_connector`, and `delete_connector`"
    ) in mcp_docs
    assert (
        "`create_repository_snapshot`, `get_repository_snapshot`, `triage_repository`, "
        "`create_repository_decision_plan`, `simulate_repository`, and `apply_repository`"
    ) in mcp_docs
    assert "`decision_plan_id`" in mcp_docs
    assert "`generated_patch_ref`" in mcp_docs
    assert "`patch_impact_report_ref`" in mcp_docs
    assert "`repository_analysis.planner_model_id`" in mcp_docs
    assert "`repository_analysis.planner_execution_mode`" in mcp_docs
    assert "`repository_analysis.planner_provider_backend`" in mcp_docs
    assert "`repository.deterministic_local_v1`" in mcp_docs
    assert "`repository_local_planner_unsupported`" in mcp_docs
    assert "`list_deployment_regions()`" in mcp_docs
    assert "`get_deployment()`" in mcp_docs
    assert "`get_deployment_cost(deployment_id)`" in mcp_docs
    assert "`create_deployment(...)` / `delete_deployment(...)`" in mcp_docs

    assert "| `recommend` | Compare actions and return a ranked recommendation. |" in mcp_readme
    assert "| `register_trigger` | Register a threshold trigger with a simulation template and optional webhook automation. |" in mcp_readme
    assert "| `list_triggers` | List registered triggers with current status and latest evaluation summary. |" in mcp_readme
    assert "| `fire_trigger` | Manually evaluate and fire one trigger, optionally forcing execution. |" in mcp_readme
    assert "| `pause_trigger` | Pause or resume one trigger without deleting it. |" in mcp_readme
    assert "| `delete_trigger` | Delete one trigger so it no longer fires automatically. |" in mcp_readme
    assert "| `product_decision` | Run the simple product decision helper and return the chosen action plus risk summary. |" in mcp_readme
    assert "| `product_agent_run` | Run the simple product task-execution helper and return a compact task result. |" in mcp_readme
    assert "| `product_optimize` | Run the simple product optimization helper and return the best variable values. |" in mcp_readme
    assert "| `product_retrieve` | Run the simple product retrieval helper over caller-supplied documents or a collection id. |" in mcp_readme
    assert "| `product_forecast` | Run the simple product forecast helper over a historical metric series. |" in mcp_readme
    assert "| `log_decision` | Persist one decision-memory record for later outcome review. |" in mcp_readme
    assert "| `list_decisions` | List persisted decision-memory records with optional outcome-only filtering. |" in mcp_readme
    assert "| `get_decision` | Fetch one persisted decision-memory record by id. |" in mcp_readme
    assert "| `record_outcome` | Record the actual outcome for one persisted decision-memory record. |" in mcp_readme
    assert "| `execute_decision` | Dispatch one persisted decision-memory record to a webhook and persist the receipt. |" in mcp_readme
    assert "| `delete_decision` | Delete one persisted decision-memory record by id. |" in mcp_readme
    assert "| `list_agent_runs` | List persisted agent runs with lineage-aware filters and pagination. |" in mcp_readme
    assert "| `get_agent_run_checkpoints` | Fetch persisted checkpoints for one agent run. |" in mcp_readme
    assert "| `query_agent_run_checkpoints` | Query persisted checkpoints across runs with lineage-aware filters. |" in mcp_readme
    assert "| `get_agent_run_mission_events` | Fetch canonical mission-event records for one agent run. |" in mcp_readme
    assert "| `query_agent_run_mission_events` | Query mission-event records across runs with lineage-aware filters. |" in mcp_readme
    assert "| `get_agent_run_telemetry` | Fetch persisted runtime telemetry batches for one agent run. |" in mcp_readme
    assert "| `query_agent_run_telemetry` | Query telemetry batches across runs with lineage-aware filters. |" in mcp_readme
    assert "| `score` | Score one simulation request with weighted decision criteria. |" in mcp_readme
    assert "| `batch` | Run multiple simulation requests in one decision-runtime call. |" in mcp_readme
    assert "| `compare` | Compare named scenarios and return the winner plus deltas. |" in mcp_readme
    assert "| `list_jobs` | List async simulation jobs with pagination and optional status filtering. |" in mcp_readme
    assert "| `poll_job` | Wait for a terminal async job state and return the final result or timeout summary. |" in mcp_readme
    assert "| `get_job_result` | Fetch the completed result payload for an async simulation job by id. |" in mcp_readme
    assert "| `cancel_job` | Cancel a queued or running async simulation job by id. |" in mcp_readme
    assert "| `test_webhook_delivery` | Send a test webhook payload to one callback URL and return the delivery result. |" in mcp_readme
    assert "| `create_connector` | Create and save one reusable connector definition. |" in mcp_readme
    assert "| `preview_test_connector` | Run a real health check for one inline connector definition without saving it. |" in mcp_readme
    assert "| `browse_connector` | Browse one saved live connector for tables, files, or items. |" in mcp_readme
    assert "| `preview_browse_connector` | Browse one inline connector definition without saving it. |" in mcp_readme
    assert "| `create_repository_snapshot` | Create or reuse one immutable repository snapshot for a saved repository connector. |" in mcp_readme
    assert "| `get_repository_snapshot` | Fetch one immutable repository snapshot by repository_id and snapshot_id. |" in mcp_readme
    assert "| `triage_repository` | Triage one repository snapshot into a bounded workspace evidence bundle. |" in mcp_readme
    assert "| `create_repository_decision_plan` | Create one immutable repository DecisionPlan revision from a snapshot and workspace evidence bundle. |" in mcp_readme
    assert "| `simulate_repository` | Simulate repository patch risk and return the gated DecisionEnvelope. |" in mcp_readme
    assert "| `apply_repository` | Apply a simulated repository decision as patch_only, local_branch, or remote_pr. |" in mcp_readme
    assert "`decision_plan_id`" in mcp_readme
    assert "`generated_patch_ref`" in mcp_readme
    assert "`patch_impact_report_ref`" in mcp_readme
    assert "`repository_analysis.planner_model_id`" in mcp_readme
    assert "`repository_analysis.planner_execution_mode`" in mcp_readme
    assert "`repository_analysis.planner_provider_backend`" in mcp_readme
    assert "`repository.deterministic_local_v1`" in mcp_readme
    assert "`repository_local_planner_unsupported`" in mcp_readme
    assert "| `list_deployment_regions` | List available deployment providers and regions for the current organization. |" in mcp_readme
    assert "| `get_deployment` | Fetch the current deployment for the active organization, if one exists. |" in mcp_readme
    assert "| `get_deployment_cost` | Get current-month cost details for one deployment by id. |" in mcp_readme
    assert "| `create_deployment` | Request a new isolated deployment for the active organization. |" in mcp_readme
    assert "| `delete_deployment` | Request deprovisioning for one deployment by id. |" in mcp_readme
    assert "| `list_team_members` | List team members for the current organization. |" in mcp_readme
    assert "| `invite_team_member` | Invite a team member to the current organization. |" in mcp_readme
    assert "| `update_team_member_role` | Update one current organization team member role by user id. |" in mcp_readme
    assert "| `remove_team_member` | Remove one team member from the current organization by user id. |" in mcp_readme
    assert "| `list_distributions` | List the simulation distribution catalog available to the current organization. |" in mcp_readme
    assert "| `list_templates` | List scenario templates available to the current organization. |" in mcp_readme
    assert "| `get_billing_info` | Get current billing plan and subscription info for the active organization. |" in mcp_readme
    assert "| `create_billing_checkout` | Create a Stripe Checkout session for the active organization. |" in mcp_readme
    assert "| `create_billing_portal` | Create a Stripe Billing Portal session for the active organization. |" in mcp_readme
    assert "| `refresh_credits` | Issue one execution credit batch for a local runtime device. |" in mcp_readme
    assert "| `ingest_metering_events` | Ingest one local metering event batch for the active organization. |" in mcp_readme
    assert "| `list_devices` | List registered devices for the current organization. |" in mcp_readme
    assert "| `revoke_device` | Revoke one registered device by registration id for the current organization. |" in mcp_readme
    assert "| `get_audit_logs` | Get paginated audit logs for the current organization. |" in mcp_readme
    assert "| `get_audit_log_artifacts` | Get immutable audit-log artifacts for the current organization, including content hashes. |" in mcp_readme
    assert "| `get_execution_policy` | Get the current autonomous execution policy for the active organization. |" in mcp_readme
    assert "| `list_execution_policy_snapshots` | List stored execution-policy snapshots for the active organization. |" in mcp_readme
    assert "| `update_execution_policy` | Update one or more execution-policy thresholds for the active organization. |" in mcp_readme

    assert "const recommendation = await client.recommend(" in ts_docs
    assert "client.distributions()" in ts_docs
    assert "client.templates()" in ts_docs
    assert "const score = await client.score(" in ts_docs
    assert "const batch = await client.batch([" in ts_docs
    assert "const compared = await client.compare([" in ts_docs
    assert "client.getBillingInfo()" in ts_docs
    assert "client.createRepositorySnapshot(" in ts_docs
    assert "client.triageRepository(" in ts_docs
    assert "client.createRepositoryDecisionPlan(" in ts_docs
    assert "client.simulateRepository(" in ts_docs
    assert "client.applyRepository(" in ts_docs
    assert "client.updateMe({ name, org_name })" in ts_docs
    assert "client.inviteTeamMember({ email, role })" in ts_docs
    assert "client.updateTeamMemberRole(userId, role)" in ts_docs
    assert "client.removeTeamMember(userId)" in ts_docs


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


def test_go_live_suite_keeps_live_typescript_runtime_gate() -> None:
    go_live = (ROOT / "tests" / "integration" / "test_go_live_full_real.py").read_text(
        encoding="utf-8"
    )

    assert "Live AlgentaClient integration" in go_live
    assert "tests/integration/test_algenta_client_live.py" in go_live
    assert "Live Python Mojo library integration" in go_live
    assert "tests/integration/test_algenta_mojo_library_live.py" in go_live
    assert "Live TypeScript Runtime integration" in go_live
    assert "tests/integration/test_typescript_runtime_live.py" in go_live
    assert "Live TypeScript SDK client integration" in go_live
    assert "tests/integration/test_typescript_sdk_client_live.py" in go_live
    assert "Live HTTP runtime library integration" in go_live
    assert "tests/integration/test_runtime_libraries_http_live.py" in go_live
    assert "LLM rollout parity benchmark" in go_live
    assert "benchmarks/llm_rollout_parity_benchmark.py" in go_live
    assert "LLM rollout compiled runtime benchmark" in go_live
    assert "benchmarks/llm_compiled_runtime_benchmark.py" in go_live
    assert "LLM rollout proof bundle" in go_live
    assert "build_proof_bundle(" in go_live


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
    assert "if _endpoint_serves_canonical_runtime_surface(BASE_URL):" in typescript_runtime_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in typescript_runtime_live
    assert '_emit(f"  ... {name}")' in typescript_runtime_live
    assert '_emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")' in (
        typescript_runtime_live
    )
    assert 'const rt = new Runtime({' in ts_readme
    assert 'const models = await rt.listModels();' in ts_readme
    assert '`rt.resolveArtifactBridge({ repo_id, filename, revision, local_files_only })`' in ts_readme
    assert 'const tokenized = await rt.tokenize({ input: "alpha beta" });' in ts_readme
    assert "const usage = await rt.usage();" in ts_readme
    assert 'const recommendation = await rt.recommend(' in ts_readme
    assert "- `rt.me()`" in ts_readme
    assert '- `rt.updateMe({ name: "Mission Ops", org_name: "Mission Control" })`' in ts_readme
    assert "- `rt.limits()`" in ts_readme
    assert "- `rt.inviteTeamMember({ email, role })`" in ts_readme
    assert "- `rt.updateTeamMemberRole(userId, role)`" in ts_readme
    assert "- `rt.removeTeamMember(userId)`" in ts_readme
    assert "- `rt.getAuditLogs({ page, limit })`" in ts_readme
    assert "- `rt.getAuditLogArtifacts({ page, limit, actor_email, action, resource_type, result, policy_snapshot_id, schema_snapshot_id, manifest_version, request_hash, content_hash })`" in ts_readme
    assert "- `rt.getExecutionPolicy()`" in ts_readme
    assert "- `rt.listExecutionPolicySnapshots()`" in ts_readme
    assert "- `rt.listAgentRuns({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id })`" in ts_readme
    assert "- `rt.listAgentRunCheckpoints(runId)`" in ts_readme
    assert "- `rt.queryAgentRunCheckpoints({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, checkpoint_id })`" in ts_readme
    assert "- `rt.listAgentRunMissionEvents(runId, { limit })`" in ts_readme
    assert "- `rt.queryAgentRunMissionEvents({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, event_type })`" in ts_readme
    assert "- `rt.listAgentRunTelemetry(runId, { limit })`" in ts_readme
    assert "- `rt.queryAgentRunTelemetry({ page, limit, status, request_hash, policy_snapshot_id, schema_snapshot_id, run_id, telemetry_kind, module_name })`" in ts_readme
    assert "- `rt.replayAgentRun(runId, { checkpoint_id })`" in ts_readme
    assert "- `rt.forkAgentRun(runId, { checkpoint_id })`" in ts_readme
    assert "- `rt.listConnectors({ page, limit })`" in ts_readme
    assert "- `rt.createConnector({ name, connector_type, description, config })`" in ts_readme
    assert "- `rt.getConnector(connectorId)`" in ts_readme
    assert "- `rt.updateConnector(connectorId, { description, config })`" in ts_readme
    assert "- `rt.testConnector(connectorId | { type, url, data_path })`" in ts_readme
    assert "- `rt.browseConnector(connectorId | { type, url, data_path })`" in ts_readme
    assert "- `rt.deleteConnector(connectorId)`" in ts_readme
    assert "- `previewTestConnector({ connector })`" in ts_readme
    assert "- `previewBrowseConnector({ connector })`" in ts_readme
    assert "- `rt.connect(source?, { name?, description?, connectorId?, connector?, selection?, datasetName?, persist?, visibility?, connectionName? })`" in ts_readme
    assert "- `rt.getDataset(datasetId)`" in ts_readme
    assert "- `rt.getDatasetSummary(datasetId)`" in ts_readme
    assert "- `rt.refreshDataset(datasetId)`" in ts_readme
    assert "- `rt.deleteDataset(datasetId)`" in ts_readme


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
    assert "write_live_integration_summary(" in mcp_integration
    assert "Summary artifact:" in mcp_integration
    assert 'print(f"  ... {name}", flush=True)' in mcp_integration
    assert "PlatformContractResponse.model_validate(contract)" in mcp_integration
    assert "from tests._manifest_backed_integrations import (" in mcp_integration
    assert "contract_integrations_match_manifest" in mcp_integration
    assert 'contract_integrations_match_manifest(contract_body["integrations"])' in (
        mcp_integration
    )
    assert "resolve_local_live_base_url" not in mcp_integration


def test_runtime_benchmark_surfaces_lock_provider_routing_overhead_class() -> None:
    runtime_manifest_tests = (ROOT / "tests" / "test_runtime_manifest.py").read_text(
        encoding="utf-8"
    )
    algenta_runtime_tests = (ROOT / "tests" / "test_algenta_runtime.py").read_text(
        encoding="utf-8"
    )
    decision_engine_query_tests = (
        ROOT / "tests" / "test_decision_engine_query_surface.py"
    ).read_text(encoding="utf-8")
    package_surface_tests = (
        ROOT / "tests" / "test_package_distribution_surface.py"
    ).read_text(encoding="utf-8")
    runtime_manifest_model_validation = (
        ROOT / "tests" / "test_runtime_manifest_model_validation.py"
    ).read_text(encoding="utf-8")
    mcp_integration = (ROOT / "tests" / "integration" / "test_mcp_server.py").read_text(
        encoding="utf-8"
    )
    runtime_admin_api = (ROOT / "tests" / "test_runtime_admin_api.py").read_text(
        encoding="utf-8"
    )
    mcp_meta_tools = (ROOT / "tests" / "test_mcp_meta_tools.py").read_text(
        encoding="utf-8"
    )
    algenta_client_live = (
        ROOT / "tests" / "integration" / "test_algenta_client_live.py"
    ).read_text(encoding="utf-8")
    python_sdk_live = (ROOT / "tests" / "integration" / "test_python_sdk.py").read_text(
        encoding="utf-8"
    )
    algenta_runtime_live = (
        ROOT / "tests" / "integration" / "test_algenta_runtime_live.py"
    ).read_text(encoding="utf-8")
    typescript_client_live = (
        ROOT / "tests" / "integration" / "test_typescript_sdk_client_live.py"
    ).read_text(encoding="utf-8")
    ts_runtime_live = (
        ROOT / "tests" / "integration" / "test_typescript_runtime_live.py"
    ).read_text(encoding="utf-8")
    ts_client_tests = (ROOT / "packages" / "ts-sdk" / "src" / "client.test.ts").read_text(
        encoding="utf-8"
    )
    ts_runtime_tests = (ROOT / "packages" / "ts-sdk" / "src" / "runtime.test.ts").read_text(
        encoding="utf-8"
    )
    cli_integration = (ROOT / "tests" / "integration" / "test_cli.py").read_text(
        encoding="utf-8"
    )
    openapi_integration = (ROOT / "tests" / "integration" / "test_openapi.py").read_text(
        encoding="utf-8"
    )

    assert "RuntimeBenchmarkClassCode.provider_routing_overhead" in runtime_manifest_tests
    assert 'entry.description == "provider routing overhead"' in runtime_manifest_tests
    assert '"build/provider_routing_overhead_benchmark.json"' in runtime_manifest_tests
    assert "RuntimeBenchmarkClassCode.checkpoint_replay_overhead" in runtime_manifest_tests
    assert 'entry.description == "checkpoint and replay overhead"' in runtime_manifest_tests
    assert "entry.evidence_paths == []" in runtime_manifest_tests
    assert (
        '"build/repository_intelligence_benchmark.json"' in runtime_manifest_tests
    )
    assert "RuntimeBenchmarkClassCode.provider_routing_overhead" in algenta_runtime_tests
    assert 'entry.description == "provider routing overhead"' in algenta_runtime_tests
    assert '"build/provider_routing_overhead_benchmark.json"' in algenta_runtime_tests
    assert "RuntimeBenchmarkClassCode.checkpoint_replay_overhead" in algenta_runtime_tests
    assert 'entry.description == "checkpoint and replay overhead"' in algenta_runtime_tests
    assert "entry.evidence_paths == []" in algenta_runtime_tests
    assert '"build/repository_intelligence_benchmark.json"' in algenta_runtime_tests
    assert (
        "RuntimeBenchmarkClassCodeResult.provider_routing_overhead"
        in decision_engine_query_tests
    )
    assert 'entry.description == "provider routing overhead"' in decision_engine_query_tests
    assert '"build/provider_routing_overhead_benchmark.json"' in decision_engine_query_tests
    assert (
        "RuntimeBenchmarkClassCodeResult.checkpoint_replay_overhead"
        in decision_engine_query_tests
    )
    assert 'entry.description == "checkpoint and replay overhead"' in decision_engine_query_tests
    assert "entry.evidence_paths == []" in decision_engine_query_tests
    assert '"build/repository_intelligence_benchmark.json"' in decision_engine_query_tests
    assert '"B6"' in package_surface_tests
    assert '"B8"' in package_surface_tests
    assert 'checkpoint_replay_overhead = "B6"' in package_surface_tests
    assert 'provider_routing_overhead = "B8"' in package_surface_tests
    assert "evidence_paths: string[];" in package_surface_tests
    assert (
        "test_runtime_admin_benchmark_models_reject_quality_gate_class_missing_from_benchmarking_classes"
        in runtime_manifest_model_validation
    )
    assert (
        "test_runtime_admin_benchmark_models_reject_quality_gate_benchmark_count_mismatch"
        in runtime_manifest_model_validation
    )
    assert (
        "test_runtime_admin_benchmark_models_reject_replay_gate_summary_mismatch"
        in runtime_manifest_model_validation
    )
    assert (
        "test_runtime_admin_benchmark_models_reject_non_replay_quality_gate_summary_mismatches"
        in runtime_manifest_model_validation
    )
    assert (
        "test_algenta_runtime_admin_benchmark_model_rejects_non_replay_quality_gate_summary_mismatches"
        in runtime_manifest_model_validation
    )
    assert "quality_gate_benchmark_classes must be declared in benchmarking.classes." in (
        runtime_manifest_model_validation
    )
    assert "evaluation_summary.benchmark_class_count" in runtime_manifest_model_validation
    assert "evaluation_summary.replay_gate_enabled" in runtime_manifest_model_validation
    assert "evaluation_summary.tool_call_quality_gate_enabled" in runtime_manifest_model_validation
    assert "evaluation_summary.rag_quality_gate_enabled" in runtime_manifest_model_validation
    assert "evaluation_summary.decision_quality_gate_enabled" in runtime_manifest_model_validation
    assert 'entry["code"] == "B8"' in mcp_integration
    assert "ensure_bootstrapped_local_live_api_key" in mcp_integration
    assert "if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):" in (
        mcp_integration
    )
    assert 'entry["description"] == "provider routing overhead"' in mcp_integration
    assert '"build/provider_routing_overhead_benchmark.json"' in mcp_integration
    assert 'entry["code"] == "B6"' in mcp_integration
    assert 'entry["description"] == "checkpoint and replay overhead"' in mcp_integration
    assert 'entry["evidence_paths"] == []' in mcp_integration
    assert 'entry["code"] == "B10"' in mcp_integration
    assert 'entry["description"] == "decision workflow completion latency"' in mcp_integration
    assert '"build/repository_intelligence_benchmark.json"' in mcp_integration
    assert '{entry["code"] for entry in data["quality_gate_benchmark_classes"]}' in mcp_integration
    assert '[entry["name"] for entry in data["quality_gate_slo_budgets"]]' in mcp_integration
    assert 'data["evaluation_summary"]["tool_call_quality_gate_enabled"] is True' in mcp_integration
    assert 'data["evaluation_summary"]["rag_quality_gate_enabled"] is True' in mcp_integration
    assert 'data["evaluation_summary"]["decision_quality_gate_enabled"] is True' in (
        mcp_integration
    )
    assert 'call_tool("get_runtime_manifest", {})' in mcp_integration
    assert 'data["benchmarking"]["classes"]' in mcp_integration
    assert '"benchmarks/summary.json"' in runtime_admin_api
    assert '"tests/benchmark_mojo_vs_python.py"' in runtime_admin_api
    assert '"quality_gate_benchmark_classes"][0]["evidence_paths"]' in runtime_admin_api
    assert '"tool_call_quality_gate_enabled"' in runtime_admin_api
    assert '"rag_quality_gate_enabled"' in runtime_admin_api
    assert '"decision_quality_gate_enabled"' in runtime_admin_api
    assert '"benchmark evidence paths"' in mcp_meta_tools
    assert 'body["benchmarking"]["classes"]' in mcp_meta_tools
    assert '"tests/benchmark_mojo_vs_python.py"' in mcp_meta_tools
    assert '{entry["code"] for entry in body["quality_gate_benchmark_classes"]}' in mcp_meta_tools
    assert '[entry["name"] for entry in body["quality_gate_slo_budgets"]]' in mcp_meta_tools
    assert 'body["evaluation_summary"]["tool_call_quality_gate_enabled"] is True' in mcp_meta_tools
    assert 'body["evaluation_summary"]["rag_quality_gate_enabled"] is True' in mcp_meta_tools
    assert 'body["evaluation_summary"]["decision_quality_gate_enabled"] is True' in (
        mcp_meta_tools
    )
    assert '"/v1/admin/runtime/benchmarks"' in openapi_integration
    assert "ensure_bootstrapped_local_live_api_key" in openapi_integration
    assert "if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):" in (
        openapi_integration
    )
    assert 'body["benchmarking"]["classes"][0]["evidence_paths"]' in openapi_integration
    assert 'entry["code"] == "B10"' in openapi_integration
    assert '"build/repository_intelligence_benchmark.json"' in openapi_integration
    assert 'evaluation_summary_schema["properties"]["tool_call_quality_gate_enabled"]["type"]' in (
        openapi_integration
    )
    assert 'evaluation_summary_schema["properties"]["rag_quality_gate_enabled"]["type"]' in (
        openapi_integration
    )
    assert 'evaluation_summary_schema["properties"]["decision_quality_gate_enabled"]["type"]' in (
        openapi_integration
    )
    assert 'body["evaluation_summary"]["tool_call_quality_gate_enabled"] is True' in (
        openapi_integration
    )
    assert 'body["evaluation_summary"]["rag_quality_gate_enabled"] is True' in (
        openapi_integration
    )
    assert 'body["evaluation_summary"]["decision_quality_gate_enabled"] is True' in (
        openapi_integration
    )
    assert 'benchmarks.quality_gate_benchmark_classes' in algenta_client_live
    assert "ensure_bootstrapped_local_live_api_key" in algenta_client_live
    assert "if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):" in (
        algenta_client_live
    )
    assert 'entry.code.value == "B6"' in algenta_client_live
    assert '{entry.code.value for entry in benchmarks.quality_gate_benchmark_classes}' in (
        algenta_client_live
    )
    assert '[entry.name.value for entry in benchmarks.quality_gate_slo_budgets]' in (
        algenta_client_live
    )
    assert 'checkpoint and replay overhead' in algenta_client_live
    assert 'checkpoint_replay_overhead.evidence_paths == []' in algenta_client_live
    assert 'benchmarks.evaluation_summary.tool_call_quality_gate_enabled is True' in (
        algenta_client_live
    )
    assert 'benchmarks.evaluation_summary.rag_quality_gate_enabled is True' in (
        algenta_client_live
    )
    assert 'benchmarks.evaluation_summary.decision_quality_gate_enabled is True' in (
        algenta_client_live
    )
    assert 'manifest.benchmarking.classes' in algenta_client_live
    assert 'manifest_checkpoint_replay_overhead.description == "checkpoint and replay overhead"' in (
        algenta_client_live
    )
    assert 'manifest_checkpoint_replay_overhead.evidence_paths == []' in algenta_client_live
    assert 'entry.code.value == "B10"' in algenta_client_live
    assert "manifest_decision_workflow_completion.description" in algenta_client_live
    assert '"decision workflow completion latency"' in algenta_client_live
    assert '"build/repository_intelligence_benchmark.json"' in algenta_client_live
    assert "client.get_runtime_benchmarks()" in python_sdk_live
    assert "ensure_bootstrapped_local_live_api_key" in python_sdk_live
    assert "if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):" in python_sdk_live
    assert "client.get_runtime_manifest()" in python_sdk_live
    assert 'entry.code.value == "B8"' in python_sdk_live
    assert 'entry.code.value == "B6"' in python_sdk_live
    assert '{entry.code.value for entry in benchmarks.quality_gate_benchmark_classes}' in (
        python_sdk_live
    )
    assert '[entry.name.value for entry in benchmarks.quality_gate_slo_budgets]' in python_sdk_live
    assert 'checkpoint_replay_overhead.evidence_paths == []' in python_sdk_live
    assert 'benchmarks.evaluation_summary.tool_call_quality_gate_enabled is True' in (
        python_sdk_live
    )
    assert 'benchmarks.evaluation_summary.rag_quality_gate_enabled is True' in python_sdk_live
    assert 'benchmarks.evaluation_summary.decision_quality_gate_enabled is True' in (
        python_sdk_live
    )
    assert 'manifest.benchmarking.classes' in python_sdk_live
    assert 'manifest_checkpoint_replay_overhead.description == "checkpoint and replay overhead"' in (
        python_sdk_live
    )
    assert 'manifest_checkpoint_replay_overhead.evidence_paths == []' in python_sdk_live
    assert 'entry.code.value == "B10"' in python_sdk_live
    assert "manifest_decision_workflow_completion.description" in python_sdk_live
    assert '"decision workflow completion latency"' in python_sdk_live
    assert '"build/repository_intelligence_benchmark.json"' in python_sdk_live
    assert "runtime.get_runtime_benchmarks()" in algenta_runtime_live
    assert "ensure_bootstrapped_local_live_api_key" in algenta_runtime_live
    assert "if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):" in (
        algenta_runtime_live
    )
    assert "runtime.get_runtime_manifest()" in algenta_runtime_live
    assert 'entry.code.value == "B8"' in algenta_runtime_live
    assert 'entry.code.value == "B6"' in algenta_runtime_live
    assert '{entry.code.value for entry in benchmarks.quality_gate_benchmark_classes}' in (
        algenta_runtime_live
    )
    assert '[entry.name.value for entry in benchmarks.quality_gate_slo_budgets]' in (
        algenta_runtime_live
    )
    assert 'checkpoint_replay_overhead.evidence_paths == []' in algenta_runtime_live
    assert 'benchmarks.evaluation_summary.tool_call_quality_gate_enabled is True' in (
        algenta_runtime_live
    )
    assert 'benchmarks.evaluation_summary.rag_quality_gate_enabled is True' in (
        algenta_runtime_live
    )
    assert 'benchmarks.evaluation_summary.decision_quality_gate_enabled is True' in (
        algenta_runtime_live
    )
    assert 'manifest.benchmarking.classes' in algenta_runtime_live
    assert 'manifest_checkpoint_replay_overhead.description == "checkpoint and replay overhead"' in (
        algenta_runtime_live
    )
    assert 'manifest_checkpoint_replay_overhead.evidence_paths == []' in algenta_runtime_live
    assert 'entry.code.value == "B10"' in algenta_runtime_live
    assert "manifest_decision_workflow_completion.description" in algenta_runtime_live
    assert '"decision workflow completion latency"' in algenta_runtime_live
    assert '"build/repository_intelligence_benchmark.json"' in algenta_runtime_live
    assert 'benchmarks["quality_gate_benchmark_classes"]' in typescript_client_live
    assert "ensure_bootstrapped_local_live_api_key" in typescript_client_live
    assert "if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):" in (
        typescript_client_live
    )
    assert 'entry["code"] == "B6"' in typescript_client_live
    assert 'checkpoint_replay_overhead["evidence_paths"] == []' in typescript_client_live
    assert 'entry["code"] == "B10"' in typescript_client_live
    assert 'decision_workflow_completion["description"] == "decision workflow completion latency"' in (
        typescript_client_live
    )
    assert '"build/repository_intelligence_benchmark.json"' in typescript_client_live
    assert 'manifest["benchmarking"]["classes"]' in typescript_client_live
    assert 'manifest_provider_routing_overhead["description"] == "provider routing overhead"' in (
        typescript_client_live
    )
    assert 'manifest_checkpoint_replay_overhead["description"] == "checkpoint and replay overhead"' in (
        typescript_client_live
    )
    assert 'code: "B8"' in ts_client_tests
    assert 'description: "provider routing overhead"' in ts_client_tests
    assert '"build/provider_routing_overhead_benchmark.json"' in ts_client_tests
    assert 'code: "B6"' in ts_client_tests
    assert 'description: "checkpoint and replay overhead"' in ts_client_tests
    assert 'manifestProviderRoutingOverhead?.description' in ts_client_tests
    assert 'manifestCheckpointReplayOverhead?.description' in ts_client_tests
    assert 'quality_gate_benchmark_classes: [' in ts_client_tests
    assert 'quality_gate_slo_budgets: [' in ts_client_tests
    assert 'replay_gate_enabled: true' in ts_client_tests
    assert 'code: "B7"' in ts_client_tests
    assert 'description: "MCP tool latency"' in ts_client_tests
    assert 'code: "B9"' in ts_client_tests
    assert 'description: "RAG retrieval quality and latency"' in ts_client_tests
    assert 'code: "B10"' in ts_client_tests
    assert 'description: "decision workflow completion latency"' in ts_client_tests
    assert '"build/repository_intelligence_benchmark.json"' in ts_client_tests
    assert 'name: "mcp_call_first_party"' in ts_client_tests
    assert 'name: "decision_plan_creation"' in ts_client_tests
    assert "tool_call_quality_gate_enabled: true" in ts_client_tests
    assert "rag_quality_gate_enabled: true" in ts_client_tests
    assert "decision_quality_gate_enabled: true" in ts_client_tests
    assert '_node_api_helper_probe("proof")' in ts_runtime_live
    assert "ensure_bootstrapped_local_live_api_key" in ts_runtime_live
    assert "INITIAL_API_KEY_CONFIGURED = has_configured_local_live_api_key()" in ts_runtime_live
    assert "return not CONFIGURED_BASE_URL and not INITIAL_API_KEY_CONFIGURED" in ts_runtime_live
    assert "if not INITIAL_API_KEY_CONFIGURED:" in ts_runtime_live
    assert 'manifest["benchmarking"]["classes"]' in ts_runtime_live
    assert 'manifest_provider_routing_overhead["description"] == "provider routing overhead"' in (
        ts_runtime_live
    )
    assert 'manifest_checkpoint_replay_overhead["description"] == "checkpoint and replay overhead"' in (
        ts_runtime_live
    )
    assert 'benchmarks["benchmarking"]["classes"]' in ts_runtime_live
    assert 'benchmarks["quality_gate_benchmark_classes"]' in ts_runtime_live
    assert 'entry["code"] == "B8"' in ts_runtime_live
    assert 'entry["code"] == "B6"' in ts_runtime_live
    assert 'checkpoint_replay_overhead["evidence_paths"] == []' in ts_runtime_live
    assert 'entry["code"] == "B10"' in ts_runtime_live
    assert 'decision_workflow_completion["description"] == "decision workflow completion latency"' in (
        ts_runtime_live
    )
    assert '"build/repository_intelligence_benchmark.json"' in ts_runtime_live
    assert '{entry["code"] for entry in benchmarks["quality_gate_benchmark_classes"]}' in (
        ts_runtime_live
    )
    assert 'entry["name"] for entry in benchmarks["quality_gate_slo_budgets"]' in ts_runtime_live
    assert 'benchmarks["evaluation_summary"]["tool_call_quality_gate_enabled"] is True' in (
        ts_runtime_live
    )
    assert 'benchmarks["evaluation_summary"]["rag_quality_gate_enabled"] is True' in (
        ts_runtime_live
    )
    assert 'benchmarks["evaluation_summary"]["decision_quality_gate_enabled"] is True' in (
        ts_runtime_live
    )
    assert 'code: "B8"' in ts_runtime_tests
    assert 'description: "provider routing overhead"' in ts_runtime_tests
    assert '"build/provider_routing_overhead_benchmark.json"' in ts_runtime_tests
    assert 'code: "B6"' in ts_runtime_tests
    assert 'description: "checkpoint and replay overhead"' in ts_runtime_tests
    assert 'manifestProviderRoutingOverhead?.description' in ts_runtime_tests
    assert 'manifestCheckpointReplayOverhead?.description' in ts_runtime_tests
    assert 'quality_gate_benchmark_classes: [' in ts_runtime_tests
    assert 'quality_gate_slo_budgets: [' in ts_runtime_tests
    assert 'replay_gate_enabled: true' in ts_runtime_tests
    assert 'code: "B7"' in ts_runtime_tests
    assert 'description: "MCP tool latency"' in ts_runtime_tests
    assert 'code: "B9"' in ts_runtime_tests
    assert 'description: "RAG retrieval quality and latency"' in ts_runtime_tests
    assert 'code: "B10"' in ts_runtime_tests
    assert 'description: "decision workflow completion latency"' in ts_runtime_tests
    assert '"build/repository_intelligence_benchmark.json"' in ts_runtime_tests
    assert 'name: "mcp_call_first_party"' in ts_runtime_tests
    assert 'name: "decision_plan_creation"' in ts_runtime_tests
    assert "tool_call_quality_gate_enabled: true" in ts_runtime_tests
    assert "rag_quality_gate_enabled: true" in ts_runtime_tests
    assert "decision_quality_gate_enabled: true" in ts_runtime_tests
    assert 'run_cli("runtime", "admin-benchmarks", "--format", "json")' in cli_integration
    assert "ensure_bootstrapped_local_live_api_key" in cli_integration
    assert "if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):" in cli_integration
    assert 'run_cli("runtime", "manifest", "--format", "json")' in cli_integration
    assert 'payload["benchmarking"]["classes"]' in cli_integration
    assert '"build/provider_routing_overhead_benchmark.json"' in cli_integration
    assert 'entry["code"] == "B10"' in cli_integration
    assert '"build/repository_intelligence_benchmark.json"' in cli_integration
    assert 'payload["evaluation_summary"]["tool_call_quality_gate_enabled"] is True' in (
        cli_integration
    )
    assert 'payload["evaluation_summary"]["rag_quality_gate_enabled"] is True' in (
        cli_integration
    )
    assert 'payload["evaluation_summary"]["decision_quality_gate_enabled"] is True' in (
        cli_integration
    )
    assert '{entry["code"] for entry in payload["quality_gate_benchmark_classes"]}' in (
        cli_integration
    )
    assert '[entry["name"] for entry in payload["quality_gate_slo_budgets"]]' in cli_integration


def test_live_openapi_integration_script_writes_summary_artifact() -> None:
    openapi_integration = (ROOT / "tests" / "integration" / "test_openapi.py").read_text(
        encoding="utf-8"
    )

    assert "ROOT = Path(__file__).resolve().parents[2]" in openapi_integration
    assert "sys.path.insert(0, str(ROOT))" in openapi_integration
    assert 'SUITE_NAME = "openapi_integration"' in openapi_integration
    assert '("/v1/webhooks/test", "post")' in openapi_integration
    assert '("/v1/data/connect", "post")' in openapi_integration
    assert '("/v1/connectors", "post")' in openapi_integration
    assert '("/v1/connectors/test", "post")' in openapi_integration
    assert '("/v1/connectors/browse", "post")' in openapi_integration
    assert '("/v1/connectors/{connector_id}", "get")' in openapi_integration
    assert '("/v1/connectors/{connector_id}", "patch")' in openapi_integration
    assert '("/v1/connectors/{connector_id}/test", "post")' in openapi_integration
    assert '("/v1/connectors/{connector_id}/browse", "get")' in openapi_integration
    assert '("/v1/connectors/{connector_id}", "delete")' in openapi_integration
    assert '("/v1/data", "get")' in openapi_integration
    assert '("/v1/data/{dataset_id}", "get")' in openapi_integration
    assert '("/v1/data/{dataset_id}/summary", "get")' in openapi_integration
    assert '("/v1/data/{dataset_id}/refresh", "post")' in openapi_integration
    assert '("/v1/repositories/{repository_id}/snapshots", "post")' in openapi_integration
    assert '("/v1/repositories/{repository_id}/snapshots/{snapshot_id}", "get")' in (
        openapi_integration
    )
    assert '("/v1/repositories/{repository_id}/triage", "post")' in openapi_integration
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in (
        openapi_integration
    )
    assert '("/v1/repositories/{repository_id}/simulate", "post")' in openapi_integration
    assert '("/v1/repositories/{repository_id}/apply", "post")' in openapi_integration
    assert (
        '"High-level /v1/data connect/list/refresh/summary/detail/delete responses are valid JSON"'
        in openapi_integration
    )
    assert "live_repository_fixture" in openapi_integration
    assert "local_repository_live_support_reason" in openapi_integration
    assert (
        '"Saved connector create/get/update/test/browse/delete responses are valid JSON"'
        in openapi_integration
    )
    assert '"Inline connector preview test/browse responses are valid JSON"' in openapi_integration
    assert (
        '"Repository intelligence snapshot/triage/decision-plan/simulate/apply responses are valid JSON"'
        in openapi_integration
    )
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in openapi_integration
    assert "repository.deterministic_local_v1" in openapi_integration
    assert 'repository_analysis.get("planner_model_id") == "repository.deterministic_local_v1"' in (
        openapi_integration
    )
    assert 'repository_analysis.get("planner_execution_mode") == "deterministic_local"' in (
        openapi_integration
    )
    assert 'repository_analysis.get("planner_provider_backend") is None' in openapi_integration
    assert "repository_model_unavailable" in openapi_integration
    assert "repository_apply_gate_failed" in openapi_integration
    assert "GET /v1/models response exposes routed provider catalog metadata" in openapi_integration
    assert "POST /v1/chat/completions response exposes explicit provider trace" in openapi_integration
    assert "POST /v1/responses response exposes explicit provider trace" in openapi_integration
    assert "POST /v1/embeddings response exposes explicit provider trace" in openapi_integration
    assert "resolved_chat_routing_targets" in openapi_integration
    assert "provider_auth_env_vars" in openapi_integration
    assert "chat_provider_auth_env_vars" in openapi_integration
    assert "embedding_provider_auth_env_vars" in openapi_integration
    assert "routing_fallback_on" in openapi_integration
    assert "routing_max_attempts" in openapi_integration
    assert "timeout_seconds" in openapi_integration
    assert "provider_attempts" in openapi_integration
    assert "write_live_integration_summary(" in openapi_integration
    assert "Summary artifact:" in openapi_integration
    assert 'print(f"  ... {name}", flush=True)' in openapi_integration


def test_go_live_full_real_script_writes_summary_artifact() -> None:
    full_real = (ROOT / "tests" / "integration" / "test_go_live_full_real.py").read_text(
        encoding="utf-8"
    )

    assert "python3 tests/integration/test_go_live_full_real.py" in full_real
    assert "PYTHONPATH=. python3 tests/integration/test_go_live_full_real.py" not in full_real
    assert "ROOT = Path(__file__).resolve().parents[2]" in full_real
    assert "sys.path.insert(0, str(ROOT))" in full_real
    assert 'SUITE_NAME = "go_live_full_real"' in full_real
    assert '"go_live_connectivity_local_only"' in full_real
    assert '"--summary-name"' in full_real
    assert "write_live_integration_summary(" in full_real
    assert "Summary artifact:" in full_real
    assert '("Live CLI integration", [sys.executable, "tests/integration/test_cli.py"], 300)' in full_real
    assert "test_cli_full.py" not in full_real


def test_cli_legacy_harness_and_status_doc_mark_canonical_cli_path_truthfully() -> None:
    cli_full = (ROOT / "tests" / "integration" / "test_cli_full.py").read_text(encoding="utf-8")
    status_doc = (ROOT / "platform_contract_v1_2_status.md").read_text(encoding="utf-8")

    assert "Legacy supplemental CLI harness" in cli_full
    assert "The canonical live CLI proof path is test_cli.py." in cli_full
    assert "Complements test_cli.py which covers: health, version, simulate, keys list." not in cli_full
    assert "historical at that time: `DE_SKIP_API=1 python3 tests/integration/test_cli_full.py`" in status_doc
    assert "current canonical live CLI proof: `python3 tests/integration/test_cli.py`" in status_doc


def test_go_live_connectivity_script_writes_summary_artifact() -> None:
    connectivity = (
        ROOT / "tests" / "integration" / "test_go_live_connectivity_real.py"
    ).read_text(encoding="utf-8")

    assert "python3 tests/integration/test_go_live_connectivity_real.py" in connectivity
    assert "PYTHONPATH=. python3 tests/integration/test_go_live_connectivity_real.py" not in connectivity
    assert 'SUITE_NAME = "go_live_connectivity_real"' in connectivity
    assert '"--summary-name"' in connectivity
    assert "write_live_integration_summary(" in connectivity
    assert "Summary artifact:" in connectivity
    assert '_emit(f"  ... {name}")' in connectivity


def test_remaining_live_integration_scripts_write_summary_artifacts() -> None:
    auth_security_live = (
        ROOT / "tests" / "integration" / "test_auth_security.py"
    ).read_text(encoding="utf-8")
    api_live = (ROOT / "tests" / "integration" / "test_api_live.py").read_text(
        encoding="utf-8"
    )
    billing_team_live = (
        ROOT / "tests" / "integration" / "test_billing_team.py"
    ).read_text(encoding="utf-8")
    connectors_live = (ROOT / "tests" / "integration" / "test_connectors.py").read_text(
        encoding="utf-8"
    )
    middleware_live = (ROOT / "tests" / "integration" / "test_middleware.py").read_text(
        encoding="utf-8"
    )
    mojo_pool_live = (ROOT / "tests" / "integration" / "test_mojo_pool.py").read_text(
        encoding="utf-8"
    )
    mojo_engines_realdata_live = (
        ROOT / "tests" / "integration" / "test_mojo_engines_realdata.py"
    ).read_text(encoding="utf-8")
    templates_live = (ROOT / "tests" / "integration" / "test_templates.py").read_text(
        encoding="utf-8"
    )
    all_engines_live = (ROOT / "tests" / "integration" / "test_all_engines.py").read_text(
        encoding="utf-8"
    )
    benchmarks_live = (ROOT / "tests" / "integration" / "test_benchmarks.py").read_text(
        encoding="utf-8"
    )
    e2e_complete_live = (ROOT / "tests" / "integration" / "test_e2e_complete.py").read_text(
        encoding="utf-8"
    )
    database_live = (ROOT / "tests" / "integration" / "test_database.py").read_text(
        encoding="utf-8"
    )
    jobs_live = (ROOT / "tests" / "integration" / "test_jobs.py").read_text(
        encoding="utf-8"
    )
    mcp_runtime_live = (
        ROOT / "tests" / "integration" / "test_mcp_runtime_live.py"
    ).read_text(encoding="utf-8")
    algenta_client_live = (
        ROOT / "tests" / "integration" / "test_algenta_client_live.py"
    ).read_text(encoding="utf-8")
    algenta_runtime_live = (
        ROOT / "tests" / "integration" / "test_algenta_runtime_live.py"
    ).read_text(encoding="utf-8")
    python_sdk_live = (ROOT / "tests" / "integration" / "test_python_sdk.py").read_text(
        encoding="utf-8"
    )
    typescript_sdk_live = (
        ROOT / "tests" / "integration" / "test_typescript_sdk_client_live.py"
    ).read_text(encoding="utf-8")
    typescript_runtime_live = (
        ROOT / "tests" / "integration" / "test_typescript_runtime_live.py"
    ).read_text(encoding="utf-8")
    local_runtime_real = (
        ROOT / "tests" / "integration" / "test_local_runtime_real.py"
    ).read_text(encoding="utf-8")
    cli_live = (ROOT / "tests" / "integration" / "test_cli.py").read_text(encoding="utf-8")
    services_live = (ROOT / "tests" / "integration" / "test_services.py").read_text(
        encoding="utf-8"
    )

    assert "python3 tests/integration/test_auth_security.py" in auth_security_live
    assert "PYTHONPATH=. python3 tests/integration/test_auth_security.py" not in auth_security_live
    assert "PROJECT_ROOT = os.path.normpath" in auth_security_live
    assert 'SUITE_NAME = "auth_security_integration"' in auth_security_live
    assert "write_live_integration_summary(" in auth_security_live
    assert "Summary artifact:" in auth_security_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in auth_security_live
    assert '_emit(f"  ... {name}")' in auth_security_live

    assert "python tests/integration/test_api_live.py" in api_live
    assert "PYTHONPATH=. python tests/integration/test_api_live.py" not in api_live
    assert "_PROJECT_ROOT = os.path.abspath" in api_live
    assert 'SUITE_NAME = "api_live_integration"' in api_live
    assert "write_live_integration_summary(" in api_live
    assert "Summary artifact:" in api_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in api_live
    assert '_emit(f"  ... {name}")' in api_live

    assert "python3 tests/integration/test_billing_team.py" in billing_team_live
    assert "PYTHONPATH=. python3 tests/integration/test_billing_team.py" not in billing_team_live
    assert '_ROOT = Path(__file__).resolve().parents[2]' in billing_team_live
    assert 'SUITE_NAME = "billing_team_integration"' in billing_team_live
    assert "write_live_integration_summary(" in billing_team_live
    assert "Summary artifact:" in billing_team_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in billing_team_live
    assert '_emit(f"  ... {name}")' in billing_team_live

    assert "python3 tests/integration/test_connectors.py" in connectors_live
    assert "PYTHONPATH=. python3 tests/integration/test_connectors.py" not in connectors_live
    assert "PROJECT_ROOT = os.path.normpath" in connectors_live
    assert 'SUITE_NAME = "connectors_integration"' in connectors_live
    assert "write_live_integration_summary(" in connectors_live
    assert "Summary artifact:" in connectors_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in connectors_live
    assert '_emit(f"  ... {name}")' in connectors_live

    assert "python tests/integration/test_middleware.py" in middleware_live
    assert "PYTHONPATH=. python tests/integration/test_middleware.py" not in middleware_live
    assert "_PROJECT_ROOT = os.path.abspath" in middleware_live
    assert 'SUITE_NAME = "middleware_integration"' in middleware_live
    assert "write_live_integration_summary(" in middleware_live
    assert "Summary artifact:" in middleware_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in middleware_live
    assert '_emit(f"  ... {name}")' in middleware_live

    assert "python tests/integration/test_mojo_pool.py" in mojo_pool_live
    assert "PYTHONPATH=. python tests/integration/test_mojo_pool.py" not in mojo_pool_live
    assert "Path(__file__).parents[2]" in mojo_pool_live
    assert 'SUITE_NAME = "mojo_pool_integration"' in mojo_pool_live
    assert "write_live_integration_summary(" in mojo_pool_live
    assert "Summary artifact:" in mojo_pool_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in mojo_pool_live
    assert '_emit(f"  ... {name}")' in mojo_pool_live

    assert "python3 tests/integration/test_mojo_engines_realdata.py" in mojo_engines_realdata_live
    assert (
        "PYTHONPATH=. python3 tests/integration/test_mojo_engines_realdata.py"
        not in mojo_engines_realdata_live
    )
    assert "_PROJECT_ROOT = Path(__file__).resolve().parents[2]" in mojo_engines_realdata_live
    assert 'SUITE_NAME = "mojo_engines_realdata_integration"' in mojo_engines_realdata_live
    assert "write_live_integration_summary(" in mojo_engines_realdata_live
    assert "Summary artifact:" in mojo_engines_realdata_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in mojo_engines_realdata_live
    assert '_emit(f"  ... {name}")' in mojo_engines_realdata_live

    assert "python tests/integration/test_templates.py" in templates_live
    assert "PYTHONPATH=. python tests/integration/test_templates.py" not in templates_live
    assert "_PROJECT_ROOT = os.path.abspath" in templates_live
    assert 'SUITE_NAME = "templates_integration"' in templates_live
    assert "write_live_integration_summary(" in templates_live
    assert "Summary artifact:" in templates_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in templates_live
    assert '_emit(f"  ... {name}")' in templates_live

    assert "python tests/integration/test_all_engines.py" in all_engines_live
    assert "PYTHONPATH=. python tests/integration/test_all_engines.py" not in all_engines_live
    assert "PROJECT_ROOT = os.path.normpath" in all_engines_live
    assert 'SUITE_NAME = "all_engines_integration"' in all_engines_live
    assert "write_live_integration_summary(" in all_engines_live
    assert "Summary artifact:" in all_engines_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in all_engines_live
    assert '_emit(f"  ... {name}")' in all_engines_live

    assert "python tests/integration/test_benchmarks.py" in benchmarks_live
    assert "PYTHONPATH=. python tests/integration/test_benchmarks.py" not in benchmarks_live
    assert "PROJECT_ROOT = os.path.normpath" in benchmarks_live
    assert 'SUITE_NAME = "benchmarks_integration"' in benchmarks_live
    assert "write_live_integration_summary(" in benchmarks_live
    assert "Summary artifact:" in benchmarks_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in benchmarks_live
    assert '_emit(f"  ... {name}")' in benchmarks_live

    assert "python tests/integration/test_e2e_complete.py" in e2e_complete_live
    assert "PYTHONPATH=. python tests/integration/test_e2e_complete.py" not in e2e_complete_live
    assert "_PROJECT_ROOT = os.path.normpath" in e2e_complete_live
    assert 'SUITE_NAME = "e2e_complete_integration"' in e2e_complete_live
    assert "write_live_integration_summary(" in e2e_complete_live
    assert "Summary artifact:" in e2e_complete_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in e2e_complete_live
    assert '_emit(f"  ... {name}")' in e2e_complete_live

    assert "python tests/integration/test_database.py" in database_live
    assert "PYTHONPATH=. python tests/integration/test_database.py" not in database_live
    assert "\nROOT = Path(__file__).resolve().parents[2]\n" not in database_live
    assert "PROJECT_ROOT = Path(__file__).resolve().parents[2]" in database_live
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in database_live
    assert 'SUITE_NAME = "database_integration"' in database_live
    assert "write_live_integration_summary(" in database_live
    assert "Summary artifact:" in database_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in database_live
    assert '_emit(f"  ... {name}")' in database_live

    assert "python tests/integration/test_jobs.py" in jobs_live
    assert "PYTHONPATH=. python tests/integration/test_jobs.py" not in jobs_live
    assert 'SUITE_NAME = "jobs_integration"' in jobs_live
    assert "write_live_integration_summary(" in jobs_live
    assert "Summary artifact:" in jobs_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in jobs_live
    assert '_emit(f"  ... {name}")' in jobs_live

    assert "python3 tests/integration/test_mcp_runtime_live.py" in mcp_runtime_live
    assert "PYTHONPATH=. python3 tests/integration/test_mcp_runtime_live.py" not in mcp_runtime_live
    assert 'SUITE_NAME = "mcp_runtime_live"' in mcp_runtime_live
    assert "write_live_integration_summary(" in mcp_runtime_live
    assert "Summary artifact:" in mcp_runtime_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in mcp_runtime_live
    assert '_emit(f"  ... {name}")' in mcp_runtime_live
    assert "_missing_live_api_key_reason()" in mcp_runtime_live
    assert 'results.append((SKIP, name, str(exc)))' in mcp_runtime_live

    assert "python3 tests/integration/test_algenta_client_live.py" in algenta_client_live
    assert "PYTHONPATH=. python3 tests/integration/test_algenta_client_live.py" not in algenta_client_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in algenta_client_live
    assert "sys.path.insert(0, path)" in algenta_client_live
    assert 'SUITE_NAME = "algenta_client_live"' in algenta_client_live
    assert "write_live_integration_summary(" in algenta_client_live
    assert "Summary artifact:" in algenta_client_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in algenta_client_live
    assert '_emit(f"  ... {name}")' in algenta_client_live
    assert '_emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")' in (
        algenta_client_live
    )
    assert "resolve_local_live_base_url" not in algenta_client_live

    assert "python3 tests/integration/test_algenta_runtime_live.py" in algenta_runtime_live
    assert (
        "PYTHONPATH=. python3 tests/integration/test_algenta_runtime_live.py"
        not in algenta_runtime_live
    )
    assert 'SUITE_NAME = "algenta_runtime_live"' in algenta_runtime_live
    assert "write_live_integration_summary(" in algenta_runtime_live
    assert "Summary artifact:" in algenta_runtime_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in algenta_runtime_live
    assert '_emit(f"  ... {name}")' in algenta_runtime_live
    assert '_emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")' in (
        algenta_runtime_live
    )
    assert "resolve_local_live_base_url" not in algenta_runtime_live

    assert "python3 tests/integration/test_python_sdk.py" in python_sdk_live
    assert "PYTHONPATH=. python3 tests/integration/test_python_sdk.py" not in python_sdk_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in python_sdk_live
    assert "sys.path.insert(0, path)" in python_sdk_live
    assert 'SUITE_NAME = "python_sdk_integration"' in python_sdk_live
    assert "PlatformContractResponse.model_validate(contract)" in python_sdk_live
    assert "from tests._manifest_backed_integrations import (" in python_sdk_live
    assert "contract_integrations_match_manifest" in python_sdk_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        python_sdk_live
    )
    assert "RuntimeAdminBenchmarksResponse.model_validate(" in python_sdk_live
    assert '("/v1/me", "get")' in python_sdk_live
    assert '("/v1/me", "patch")' in python_sdk_live
    assert '("/v1/billing/info", "get")' in python_sdk_live
    assert '("/v1/distributions", "get")' in python_sdk_live
    assert '("/v1/templates", "get")' in python_sdk_live
    assert '("/v1/webhooks/test", "post")' in python_sdk_live
    assert '("/v1/execution/policy/snapshots", "get")' in python_sdk_live
    assert '("/v1/connectors", "get")' in python_sdk_live
    assert '("/v1/connectors", "post")' in python_sdk_live
    assert '("/v1/connectors/test", "post")' in python_sdk_live
    assert '("/v1/connectors/browse", "post")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}", "get")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}", "patch")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in python_sdk_live
    assert '("/v1/connectors/{connector_id}", "delete")' in python_sdk_live
    assert '("/v1/data/connect", "post")' in python_sdk_live
    assert '("/v1/data", "get")' in python_sdk_live
    assert '("/v1/data/{dataset_id}", "get")' in python_sdk_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in python_sdk_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in python_sdk_live
    assert '("/v1/data/{dataset_id}", "delete")' in python_sdk_live
    assert '("/v1/team/invite", "post")' in python_sdk_live
    assert '("/v1/api-keys", "post")' in python_sdk_live
    assert '("/v1/credits/refresh", "post")' in python_sdk_live
    assert "Sync client account/API-key surface" in python_sdk_live
    assert "preview_test_connector(" in python_sdk_live
    assert "preview_browse_connector(" in python_sdk_live
    assert "Sync client saved connector + dataset lifecycle" in python_sdk_live
    assert "Sync client team/credits/metering/audit/execution-policy helpers" in python_sdk_live
    assert "Sync client deployment create/delete lifecycle" in python_sdk_live
    assert "_assert_model_catalog_provider_metadata(models)" in python_sdk_live
    assert "resolved_chat_routing_targets" in python_sdk_live
    assert "routing_fallback_on" in python_sdk_live
    assert "routing_max_attempts" in python_sdk_live
    assert "timeout_seconds" in python_sdk_live
    assert "provider_auth_configured" in python_sdk_live
    assert "chat_provider_auth_configured" in python_sdk_live
    assert "embedding_provider_auth_configured" in python_sdk_live
    assert "_assert_empty_provider_trace(response, output_items=True)" in python_sdk_live
    assert "_assert_empty_provider_trace(embedded)" in python_sdk_live
    assert "AsyncClient account/API-key surface" in python_sdk_live
    assert "AsyncClient saved connector + dataset lifecycle" in python_sdk_live
    assert "AsyncClient team/credits/metering/audit/execution-policy helpers" in python_sdk_live
    assert "AsyncClient deployment create/delete lifecycle" in python_sdk_live
    assert "await client.chat_completions(" in python_sdk_live
    assert "await client.responses(" in python_sdk_live
    assert "write_live_integration_summary(" in python_sdk_live
    assert "Summary artifact:" in python_sdk_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in python_sdk_live
    assert '_emit(f"  ... {name}")' in python_sdk_live
    assert "resolve_local_live_base_url" not in python_sdk_live

    assert (
        "python3 tests/integration/test_typescript_sdk_client_live.py" in typescript_sdk_live
    )
    assert (
        "PYTHONPATH=. python3 tests/integration/test_typescript_sdk_client_live.py"
        not in typescript_sdk_live
    )
    assert "ROOT = Path(__file__).resolve().parents[2]" in typescript_sdk_live
    assert "node" in typescript_sdk_live
    assert 'SUITE_NAME = "typescript_sdk_client_live"' in typescript_sdk_live
    assert "PlatformContractResponse.model_validate(contract)" in typescript_sdk_live
    assert "from tests._manifest_backed_integrations import (" in typescript_sdk_live
    assert "contract_integrations_match_manifest" in typescript_sdk_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        typescript_sdk_live
    )
    assert "RuntimeAdminBenchmarksResponse.model_validate(" in typescript_sdk_live
    assert "write_live_integration_summary(" in typescript_sdk_live
    assert "Summary artifact:" in typescript_sdk_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in typescript_sdk_live
    assert '_emit(f"  ... {name}")' in typescript_sdk_live
    assert '_emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")' in (
        typescript_sdk_live
    )
    assert "resolve_local_live_base_url" not in typescript_sdk_live
    assert "test_client_decision_runtime_surface" in typescript_sdk_live
    assert "test_client_account_surface" in typescript_sdk_live
    assert "test_client_dataset_surface" in typescript_sdk_live
    assert "test_client_control_plane_surface" in typescript_sdk_live
    assert "test_client_deployment_lifecycle_surface" in typescript_sdk_live
    assert 'case \'decision\':' in typescript_sdk_live
    assert "case 'account':" in typescript_sdk_live
    assert "case 'datasets':" in typescript_sdk_live
    assert "case 'control_plane':" in typescript_sdk_live
    assert "case 'deployment_lifecycle':" in typescript_sdk_live
    assert '("/v1/me", "get")' in typescript_sdk_live
    assert '("/v1/me", "patch")' in typescript_sdk_live
    assert '("/v1/connectors", "get")' in typescript_sdk_live
    assert '("/v1/connectors", "post")' in typescript_sdk_live
    assert '("/v1/connectors/test", "post")' in typescript_sdk_live
    assert '("/v1/connectors/browse", "post")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}", "get")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}", "patch")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in typescript_sdk_live
    assert '("/v1/connectors/{connector_id}", "delete")' in typescript_sdk_live
    assert '("/v1/data/connect", "post")' in typescript_sdk_live
    assert '("/v1/data", "get")' in typescript_sdk_live
    assert '("/v1/data/{dataset_id}", "get")' in typescript_sdk_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in typescript_sdk_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in typescript_sdk_live
    assert '("/v1/data/{dataset_id}", "delete")' in typescript_sdk_live
    assert '("/v1/billing/info", "get")' in typescript_sdk_live
    assert "previewTestConnector" in typescript_sdk_live
    assert "previewBrowseConnector" in typescript_sdk_live
    assert '("/v1/distributions", "get")' in typescript_sdk_live
    assert '("/v1/templates", "get")' in typescript_sdk_live
    assert '("/v1/webhooks/test", "post")' in typescript_sdk_live
    assert '("/v1/credits/refresh", "post")' in typescript_sdk_live
    assert '("/v1/execution/policy/snapshots", "get")' in typescript_sdk_live
    assert '("/v1/team", "get")' in typescript_sdk_live
    assert '("/v1/team/invite", "post")' in typescript_sdk_live
    assert '"resolved_chat_routing_targets"' in typescript_sdk_live
    assert '"routing_fallback_on"' in typescript_sdk_live
    assert '"routing_max_attempts"' in typescript_sdk_live
    assert '"timeout_seconds"' in typescript_sdk_live
    assert '"provider_auth_env_vars"' in typescript_sdk_live
    assert '"provider_auth_configured"' in typescript_sdk_live
    assert '"chat_provider_auth_configured"' in typescript_sdk_live
    assert '"embedding_provider_auth_configured"' in typescript_sdk_live
    assert '"provider_attempts"' in typescript_sdk_live

    assert "test_client_control_plane_surface" in algenta_client_live
    assert "test_client_saved_connector_surface" in algenta_client_live
    assert "test_client_dataset_surface" in algenta_client_live
    assert "test_client_deployment_lifecycle_surface" in algenta_client_live
    assert (
        "from tests._manifest_backed_integrations import (\n"
        "    contract_integrations_match_manifest,\n"
        ")"
    ) in algenta_client_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        algenta_client_live
    )
    assert "assert contract_integrations_match_manifest(contract.integrations)" in (
        algenta_client_live
    )
    assert "get_billing_info" in algenta_client_live
    assert '("/v1/connectors", "get")' in algenta_client_live
    assert '("/v1/connectors", "post")' in algenta_client_live
    assert '("/v1/connectors/test", "post")' in algenta_client_live
    assert '("/v1/connectors/browse", "post")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}", "get")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}", "patch")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in algenta_client_live
    assert '("/v1/connectors/{connector_id}", "delete")' in algenta_client_live
    assert '("/v1/data/connect", "post")' in algenta_client_live
    assert '("/v1/data", "get")' in algenta_client_live
    assert '("/v1/data/{dataset_id}", "get")' in algenta_client_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in algenta_client_live
    assert "preview_test_connector(" in algenta_client_live
    assert "preview_browse_connector(" in algenta_client_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in algenta_client_live
    assert '("/v1/data/{dataset_id}", "delete")' in algenta_client_live
    assert '("/v1/distributions", "get")' in algenta_client_live
    assert '("/v1/templates", "get")' in algenta_client_live
    assert '("/v1/webhooks/test", "post")' in algenta_client_live
    assert '("/v1/credits/refresh", "post")' in algenta_client_live
    assert '("/v1/execution/policy/snapshots", "get")' in algenta_client_live
    assert '("/v1/team", "get")' in algenta_client_live
    assert '("/v1/me", "patch")' in algenta_client_live
    assert '("/v1/team/invite", "post")' in algenta_client_live
    assert "_assert_model_catalog_provider_metadata(models)" in algenta_client_live
    assert "resolved_chat_routing_targets" in algenta_client_live
    assert "routing_fallback_on" in algenta_client_live
    assert "routing_max_attempts" in algenta_client_live
    assert "timeout_seconds" in algenta_client_live
    assert "provider_auth_configured" in algenta_client_live
    assert "chat_provider_auth_configured" in algenta_client_live
    assert "embedding_provider_auth_configured" in algenta_client_live
    assert "_assert_empty_provider_trace(response, output_items=True)" in algenta_client_live

    assert "run_api_runtime_control_plane_surface" in algenta_runtime_live
    assert "run_api_runtime_dataset_surface" in algenta_runtime_live
    assert "run_api_runtime_deployment_lifecycle_surface" in algenta_runtime_live
    assert "PlatformContractResponse.model_validate(contract)" in algenta_runtime_live
    assert "from tests._manifest_backed_integrations import (" in algenta_runtime_live
    assert "contract_integrations_match_manifest" in algenta_runtime_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        algenta_runtime_live
    )
    assert "RuntimeAdminBenchmarksResponse.model_validate(" in algenta_runtime_live
    assert '("/v1/meta/contract", "get")' in algenta_runtime_live
    assert '("/v1/admin/runtime/benchmarks", "get")' in algenta_runtime_live
    assert '("/v1/models", "get")' in algenta_runtime_live
    assert '("/v1/connectors", "get")' in algenta_runtime_live
    assert '("/v1/connectors", "post")' in algenta_runtime_live
    assert '("/v1/connectors/test", "post")' in algenta_runtime_live
    assert '("/v1/connectors/browse", "post")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}", "get")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}", "patch")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in algenta_runtime_live
    assert '("/v1/connectors/{connector_id}", "delete")' in algenta_runtime_live
    assert '("/v1/data/connect", "post")' in algenta_runtime_live
    assert '("/v1/data", "get")' in algenta_runtime_live
    assert '("/v1/data/{dataset_id}", "get")' in algenta_runtime_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in algenta_runtime_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in algenta_runtime_live
    assert '("/v1/data/{dataset_id}", "delete")' in algenta_runtime_live
    assert '("/v1/distributions", "get")' in algenta_runtime_live
    assert '("/v1/templates", "get")' in algenta_runtime_live
    assert '("/v1/webhooks/test", "post")' in algenta_runtime_live
    assert "_assert_model_catalog_provider_metadata(models)" in algenta_runtime_live
    assert "resolved_chat_routing_targets" in algenta_runtime_live
    assert "routing_fallback_on" in algenta_runtime_live
    assert "routing_max_attempts" in algenta_runtime_live
    assert "timeout_seconds" in algenta_runtime_live
    assert "provider_auth_configured" in algenta_runtime_live
    assert "chat_provider_auth_configured" in algenta_runtime_live
    assert "embedding_provider_auth_configured" in algenta_runtime_live
    assert "_assert_empty_provider_trace(response, output_items=True)" in algenta_runtime_live
    assert '("/v1/credits/refresh", "post")' in algenta_runtime_live
    assert '("/v1/execution/policy/snapshots", "get")' in algenta_runtime_live
    assert '("/v1/me", "patch")' in algenta_runtime_live
    assert "get_billing_info" in algenta_runtime_live
    assert "preview_tested_connector = runtime.test_connector(" in algenta_runtime_live
    assert "preview_browsed_connector = runtime.browse_connector(" in algenta_runtime_live
    assert "API Runtime connectors + dataset lifecycle surface" in algenta_runtime_live
    assert '("/v1/team", "get")' in algenta_runtime_live
    assert '("/v1/team/invite", "post")' in algenta_runtime_live
    assert "from tests._manifest_backed_integrations import (" in typescript_runtime_live
    assert "contract_integrations_match_manifest" in typescript_runtime_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        typescript_runtime_live
    )
    assert "resolve_local_live_base_url" not in typescript_runtime_live
    assert 'case "datasets":' in typescript_runtime_live
    assert "run_typescript_runtime_dataset_surface" in typescript_runtime_live
    assert '("/v1/connectors", "get")' in typescript_runtime_live
    assert '("/v1/connectors", "post")' in typescript_runtime_live
    assert '("/v1/connectors/test", "post")' in typescript_runtime_live
    assert '("/v1/connectors/browse", "post")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}", "get")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}", "patch")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in typescript_runtime_live
    assert '("/v1/connectors/{connector_id}", "delete")' in typescript_runtime_live
    assert '("/v1/data/connect", "post")' in typescript_runtime_live
    assert '("/v1/data", "get")' in typescript_runtime_live
    assert '("/v1/data/{dataset_id}", "get")' in typescript_runtime_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in typescript_runtime_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in typescript_runtime_live
    assert '("/v1/data/{dataset_id}", "delete")' in typescript_runtime_live
    assert "TypeScript Runtime(mode='api') connectors + dataset lifecycle helpers" in (
        typescript_runtime_live
    )
    assert "previewTestedConnector = await runtime.testConnector({" in typescript_runtime_live
    assert "previewBrowsedConnector = await runtime.browseConnector({" in typescript_runtime_live
    assert '"routing_fallback_on"' in typescript_runtime_live
    assert '"routing_max_attempts"' in typescript_runtime_live
    assert '"timeout_seconds"' in typescript_runtime_live
    assert '"provider_attempts"' in typescript_runtime_live
    assert '("/v1/usage", "get")' in typescript_sdk_live
    assert '("/v1/limits", "get")' in typescript_sdk_live
    assert '("/v1/api-keys", "post")' in typescript_sdk_live
    assert '("/v1/recommend", "post")' in typescript_sdk_live
    assert '("/v1/score", "post")' in typescript_sdk_live
    assert '("/v1/batch", "post")' in typescript_sdk_live
    assert '("/v1/compare", "post")' in typescript_sdk_live

    assert 'SUITE_NAME = "local_runtime_real"' in local_runtime_real
    assert "write_live_integration_summary(" in local_runtime_real
    assert "Summary artifact:" in local_runtime_real
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in local_runtime_real
    assert '_emit(f"  ... {name}")' in local_runtime_real

    assert "python3 tests/integration/test_cli.py" in cli_live
    assert "PYTHONPATH=. python3 tests/integration/test_cli.py" not in cli_live
    assert 'SUITE_NAME = "cli_integration"' in cli_live
    assert "write_live_integration_summary(" in cli_live
    assert "Summary artifact:" in cli_live
    assert '_emit(f"  ... {name}")' in cli_live
    assert "PlatformContractResponse.model_validate(contract)" in cli_live
    assert "from tests._manifest_backed_integrations import (" in cli_live
    assert "contract_integrations_match_manifest" in cli_live
    assert 'if not contract_integrations_match_manifest(contract["integrations"]):' in (
        cli_live
    )
    assert "resolve_local_live_base_url" not in cli_live
    assert "test_cli_team_surface" in cli_live
    assert "test_cli_webhook_test_surface" in cli_live
    assert "test_cli_audit_logs_surface" in cli_live
    assert "test_cli_execution_policy_surface" in cli_live
    assert "test_cli_data_surface" in cli_live
    assert "test_cli_connector_surface" in cli_live
    assert "test_cli_credit_refresh_surface" in cli_live
    assert '("/v1/connectors", "post")' in cli_live
    assert '("/v1/connectors/test", "post")' in cli_live
    assert '("/v1/connectors/browse", "post")' in cli_live
    assert '("/v1/connectors/{connector_id}", "get")' in cli_live
    assert '("/v1/connectors/{connector_id}", "patch")' in cli_live
    assert '("/v1/connectors/{connector_id}/test", "post")' in cli_live
    assert '("/v1/connectors/{connector_id}/browse", "get")' in cli_live
    assert '("/v1/connectors/{connector_id}", "delete")' in cli_live
    assert '("/v1/data/connect", "post")' in cli_live
    assert '("/v1/data", "get")' in cli_live
    assert '("/v1/data/{dataset_id}/refresh", "post")' in cli_live
    assert '("/v1/data/{dataset_id}/summary", "get")' in cli_live
    assert '("/v1/data/{dataset_id}", "get")' in cli_live
    assert '("/v1/data/{dataset_id}", "delete")' in cli_live
    assert 'run_cli("connectors", "preview-test"' in cli_live
    assert 'run_cli("connectors", "preview-browse"' in cli_live
    assert '("/v1/execution/policy/snapshots", "get")' in cli_live
    assert '("/v1/credits/refresh", "post")' in cli_live
    assert "billing" in cli_live
    assert '("/v1/team", "get")' in cli_live
    assert '("/v1/me", "patch")' in cli_live
    assert '("/v1/distributions", "get")' in cli_live
    assert '("/v1/templates", "get")' in cli_live
    assert '("/v1/team/invite", "post")' in cli_live
    assert '("/v1/billing/info", "get")' in cli_live
    assert '("/v1/webhooks/test", "post")' in cli_live
    assert '("/v1/audit-logs", "get")' in cli_live
    assert '("/v1/audit-logs/artifacts", "get")' in cli_live
    assert '("/v1/agent/runs", "get")' in cli_live
    assert '("/v1/agent/runs/{run_id}/checkpoints", "get")' in cli_live
    assert '("/v1/agent/runs/checkpoints", "get")' in cli_live
    assert '("/v1/agent/runs/{run_id}/mission-events", "get")' in cli_live
    assert '("/v1/agent/runs/mission-events", "get")' in cli_live
    assert '("/v1/agent/runs/{run_id}/telemetry", "get")' in cli_live
    assert '("/v1/agent/runs/telemetry", "get")' in cli_live
    assert '("/v1/execution/policy", "patch")' in cli_live
    assert "test_cli_deployment_surface" in cli_live
    assert '("/v1/deployments/regions", "get")' in cli_live
    assert '("/v1/deployments/{deployment_id}/cost", "get")' in cli_live
    assert 'response_events[-1]["response"]["provider_attempts"] == []' in cli_live
    assert 'chat_data["provider_attempts"] == []' in cli_live
    assert 'tokenizer["chat_required_provider_headers"] == []' in cli_live
    assert 'tokenizer["embedding_required_provider_headers"] == []' in cli_live
    assert 'tokenizer["chat_provider_auth_env_vars"] == []' in cli_live
    assert 'tokenizer["embedding_provider_auth_env_vars"] == []' in cli_live
    assert 'tokenizer["chat_provider_auth_configured"] is False' in cli_live
    assert 'tokenizer["embedding_provider_auth_configured"] is False' in cli_live

    assert "python3 tests/integration/test_services.py" in services_live
    assert "PYTHONPATH=. python tests/integration/test_services.py" not in services_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in services_live
    assert "sys.path.insert(0, str(ROOT))" in services_live
    assert 'SUITE_NAME = "services_integration"' in services_live
    assert "write_live_integration_summary(" in services_live
    assert "Summary artifact:" in services_live
    assert '_emit(f"  ... {name}")' in services_live


def test_repository_intelligence_live_scripts_cover_public_surfaces() -> None:
    repository_fixture = (
        ROOT / "tests" / "integration" / "live_repository_fixture.py"
    ).read_text(encoding="utf-8")
    python_sdk_live = (ROOT / "tests" / "integration" / "test_python_sdk.py").read_text(
        encoding="utf-8"
    )
    algenta_client_live = (
        ROOT / "tests" / "integration" / "test_algenta_client_live.py"
    ).read_text(encoding="utf-8")
    algenta_runtime_live = (
        ROOT / "tests" / "integration" / "test_algenta_runtime_live.py"
    ).read_text(encoding="utf-8")
    cli_live = (ROOT / "tests" / "integration" / "test_cli.py").read_text(encoding="utf-8")
    mcp_server_live = (
        ROOT / "tests" / "integration" / "test_mcp_server.py"
    ).read_text(encoding="utf-8")
    typescript_sdk_live = (
        ROOT / "tests" / "integration" / "test_typescript_sdk_client_live.py"
    ).read_text(encoding="utf-8")
    typescript_runtime_live = (
        ROOT / "tests" / "integration" / "test_typescript_runtime_live.py"
    ).read_text(encoding="utf-8")

    assert "class LiveRepositoryFixture:" in repository_fixture
    assert "def local_repository_live_support_reason(base_url: str) -> str | None:" in (
        repository_fixture
    )
    assert "connector_type\": \"local_repo\"" in repository_fixture
    assert "decision_plan_id" in repository_fixture
    assert "mode\": \"patch_only\"" in repository_fixture
    assert "def apply_local_branch_request(" in repository_fixture
    assert "mode\": \"local_branch\"" in repository_fixture
    assert "\"write_permission\": True" in repository_fixture
    assert "def assert_local_branch_applied(" in repository_fixture

    assert "test_sync_repository_surface" in python_sdk_live
    assert "test_async_repository_surface" in python_sdk_live
    assert 'check("Sync client repository intelligence surface → typed live results"' in (
        python_sdk_live
    )
    assert 'check("AsyncClient repository intelligence surface → typed live results"' in (
        python_sdk_live
    )
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in python_sdk_live
    assert "local_repository_live_support_reason(BASE_URL)" in python_sdk_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in python_sdk_live
    assert 'repository_analysis.planner_model_id == "repository.deterministic_local_v1"' in (
        python_sdk_live
    )
    assert 'repository_analysis.planner_execution_mode == "deterministic_local"' in (
        python_sdk_live
    )
    assert "repository_analysis.planner_provider_backend is None" in python_sdk_live

    assert "test_client_repository_surface" in algenta_client_live
    assert 'check("AlgentaClient repository intelligence surface"' in algenta_client_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in algenta_client_live
    assert "local_repository_live_support_reason(BASE_URL)" in algenta_client_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in algenta_client_live
    assert '_value(repository_analysis, "planner_model_id") == "repository.deterministic_local_v1"' in (
        algenta_client_live
    )
    assert '_value(repository_analysis, "planner_execution_mode") == "deterministic_local"' in (
        algenta_client_live
    )
    assert '_value(repository_analysis, "planner_provider_backend") is None' in (
        algenta_client_live
    )

    assert "run_api_runtime_repository_surface" in algenta_runtime_live
    assert 'check("API Runtime repository intelligence surface"' in algenta_runtime_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in algenta_runtime_live
    assert "local_repository_live_support_reason(BASE_URL)" in algenta_runtime_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in algenta_runtime_live
    assert 'planner_model_id == "repository.deterministic_local_v1"' in algenta_runtime_live
    assert 'planner_execution_mode == "deterministic_local"' in algenta_runtime_live
    assert "planner_provider_backend is None" in algenta_runtime_live

    assert "test_cli_repository_surface" in cli_live
    assert (
        'check("CLI repository intelligence surface → snapshot/triage/plan/simulate/apply"'
        in cli_live
    )
    assert '"decision-plan"' in cli_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in cli_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in cli_live
    assert 'repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"' in (
        cli_live
    )
    assert 'repository_analysis["planner_execution_mode"] == "deterministic_local"' in cli_live
    assert 'repository_analysis["planner_provider_backend"] is None' in cli_live

    assert "test_tool_repository_intelligence_lifecycle" in mcp_server_live
    assert '"create_repository_snapshot"' in mcp_server_live
    assert '"apply_repository"' in mcp_server_live
    assert "local_repository_live_support_reason(BASE_URL)" in mcp_server_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in mcp_server_live
    assert 'repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"' in (
        mcp_server_live
    )
    assert 'repository_analysis["planner_execution_mode"] == "deterministic_local"' in (
        mcp_server_live
    )
    assert 'repository_analysis["planner_provider_backend"] is None' in mcp_server_live

    assert "test_client_repository_surface" in typescript_sdk_live
    assert 'check("TypeScript SDK client repository intelligence surface"' in typescript_sdk_live
    assert "case 'repositories':" in typescript_sdk_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in (
        typescript_sdk_live
    )
    assert '"DE_LOCAL_REPOSITORY_PATH": repository_path or ""' in typescript_sdk_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in typescript_sdk_live
    assert 'repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"' in (
        typescript_sdk_live
    )
    assert 'repository_analysis["planner_execution_mode"] == "deterministic_local"' in (
        typescript_sdk_live
    )
    assert 'repository_analysis["planner_provider_backend"] is None' in typescript_sdk_live

    assert "run_typescript_runtime_repository_surface" in typescript_runtime_live
    assert (
        'check(\n            "TypeScript Runtime(mode=\'api\') repository intelligence helpers",'
        in typescript_runtime_live
    )
    assert 'case "repositories":' in typescript_runtime_live
    assert '("/v1/repositories/{repository_id}/decision-plans", "post")' in (
        typescript_runtime_live
    )
    assert '"DE_LOCAL_REPOSITORY_PATH": repository_path or ""' in typescript_runtime_live
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL" in typescript_runtime_live
    assert 'repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"' in (
        typescript_runtime_live
    )
    assert 'repository_analysis["planner_execution_mode"] == "deterministic_local"' in (
        typescript_runtime_live
    )
    assert 'repository_analysis["planner_provider_backend"] is None' in (
        typescript_runtime_live
    )


def test_all_standalone_integration_scripts_emit_summary_artifacts() -> None:
    integration_root = ROOT / "tests" / "integration"
    missing_suite_name: list[str] = []
    missing_write: list[str] = []
    missing_print: list[str] = []
    missing_progress: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue
        if "SUITE_NAME =" not in text:
            missing_suite_name.append(path.name)
        if "write_live_integration_summary(" not in text and "write_live_summary_artifact(" not in text:
            missing_write.append(path.name)
        if "Summary artifact:" not in text:
            missing_print.append(path.name)
        if '_emit(f"  ... {name}")' not in text and 'print(f"  ... {name}", flush=True)' not in text:
            missing_progress.append(path.name)

    assert not missing_suite_name, f"Standalone integration scripts missing suite names: {missing_suite_name}"
    assert not missing_write, f"Standalone integration scripts missing summary writers: {missing_write}"
    assert not missing_print, f"Standalone integration scripts missing summary artifact output: {missing_print}"
    assert not missing_progress, (
        f"Standalone integration scripts missing visible per-check progress output: {missing_progress}"
    )


def test_all_standalone_integration_scripts_register_suite_names_in_the_correct_artifact_registry() -> None:
    integration_root = ROOT / "tests" / "integration"
    integration_registry = (integration_root / "live_integration_artifacts.py").read_text(
        encoding="utf-8"
    )
    rollout_registry = (ROOT / "benchmarks" / "llm_rollout_live_artifacts.py").read_text(
        encoding="utf-8"
    )
    missing_registration: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue
        match = re.search(r'^SUITE_NAME\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match is None:
            missing_registration.append(f"{path.name}: missing SUITE_NAME")
            continue

        suite_name = match.group(1)
        registry_text = (
            rollout_registry if "write_live_summary_artifact(" in text else integration_registry
        )
        registry_name = (
            "benchmarks/llm_rollout_live_artifacts.py"
            if "write_live_summary_artifact(" in text
            else "tests/integration/live_integration_artifacts.py"
        )
        if f'"{suite_name}"' not in registry_text:
            missing_registration.append(f"{path.name}: {suite_name} missing from {registry_name}")

    assert not missing_registration, (
        "Standalone integration scripts missing artifact registry entries: "
        f"{missing_registration}"
    )


def test_live_integration_artifact_paths_follow_suite_name_summary_suffix() -> None:
    registry_path = ROOT / "tests" / "integration" / "live_integration_artifacts.py"
    spec = importlib.util.spec_from_file_location("live_integration_artifacts", registry_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    artifact_paths = module.LIVE_INTEGRATION_SUMMARY_ARTIFACTS

    assert {
        name: path.name for name, path in artifact_paths.items()
    } == {name: f"{name}_summary.json" for name in artifact_paths}


def test_live_integration_summary_script_registry_matches_suite_names() -> None:
    registry_path = ROOT / "tests" / "integration" / "live_integration_artifacts.py"
    spec = importlib.util.spec_from_file_location("live_integration_artifacts", registry_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    artifact_names = set(module.LIVE_INTEGRATION_SUMMARY_ARTIFACTS)
    script_names = set(module.LIVE_INTEGRATION_SUMMARY_SCRIPTS)

    assert script_names == artifact_names
    assert all(
        script == "tests/integration/test_go_live_connectivity_real.py"
        for name, script in module.LIVE_INTEGRATION_SUMMARY_SCRIPTS.items()
        if name in {"go_live_connectivity_local_only", "go_live_connectivity_real"}
    )
    assert all(
        script.startswith("tests/integration/test_") and script.endswith(".py")
        for script in module.LIVE_INTEGRATION_SUMMARY_SCRIPTS.values()
    )


def test_live_summary_helper_modules_keep_fail_closed_metadata_and_parser_guards() -> None:
    integration_helper = (ROOT / "tests" / "integration" / "live_integration_artifacts.py").read_text(
        encoding="utf-8"
    )
    rollout_helper = (ROOT / "benchmarks" / "llm_rollout_live_artifacts.py").read_text(
        encoding="utf-8"
    )

    assert 'if not isinstance(payload, dict):' in integration_helper
    assert 'if not isinstance(payload, dict):' in rollout_helper
    assert 'raise ValueError(f"{path} must contain a JSON object")' in integration_helper
    assert 'raise ValueError(f"{path} must contain a JSON object")' in rollout_helper
    assert 'details must use only string keys' in integration_helper
    assert 'details must not contain tuples' in integration_helper
    assert 'extra must use only string keys' in rollout_helper
    assert 'extra must not contain tuples' in rollout_helper
    assert 'channels must be a list or tuple of channel names' in rollout_helper
    assert 'channels must be a sequence of channel names, not a single string' in rollout_helper
    assert 'must be an integer, not boolean' in integration_helper
    assert 'must be an integer, not boolean' in rollout_helper
    assert 'must be an integer' in integration_helper
    assert 'must be an integer' in rollout_helper
    assert 'generated_at must be a UTC ISO-8601 string ending with Z' in integration_helper
    assert 'generated_at must be a UTC ISO-8601 string ending with Z' in rollout_helper
    assert 'sort_keys=True' in integration_helper
    assert 'sort_keys=True' in rollout_helper
    assert '+ "\\n"' in integration_helper
    assert '+ "\\n"' in rollout_helper


def test_all_standalone_integration_scripts_bind_summary_writers_to_suite_name() -> None:
    integration_root = ROOT / "tests" / "integration"
    missing_suite_binding: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue

        uses_integration_writer = "write_live_integration_summary(" in text
        uses_rollout_writer = "write_live_summary_artifact(" in text

        if uses_integration_writer and (
            re.search(r"write_live_integration_summary\(\s*SUITE_NAME\s*,", text) is None
            and "name=SUITE_NAME" not in text
        ):
            missing_suite_binding.append(
                f"{path.name}: write_live_integration_summary not bound to SUITE_NAME"
            )

        if uses_rollout_writer and "suite_name=SUITE_NAME" not in text:
            missing_suite_binding.append(
                f"{path.name}: write_live_summary_artifact not bound to SUITE_NAME"
            )

    assert not missing_suite_binding, (
        "Standalone integration scripts missing SUITE_NAME summary-writer bindings: "
        f"{missing_suite_binding}"
    )


def test_all_standalone_integration_scripts_bind_summary_writers_to_own_script_path() -> None:
    integration_root = ROOT / "tests" / "integration"
    missing_script_binding: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue

        expected_script = f"tests/integration/{path.name}"

        if "write_live_integration_summary(" in text:
            match = re.search(
                r'write_live_integration_summary\(.*?script="([^"]+)"',
                text,
                re.DOTALL,
            )
            if match is None or match.group(1) != expected_script:
                missing_script_binding.append(
                    f"{path.name}: write_live_integration_summary script != {expected_script}"
                )

        if "write_live_summary_artifact(" in text:
            match = re.search(
                r'write_live_summary_artifact\(.*?script="([^"]+)"',
                text,
                re.DOTALL,
            )
            if match is None or match.group(1) != expected_script:
                missing_script_binding.append(
                    f"{path.name}: write_live_summary_artifact script != {expected_script}"
                )

    assert not missing_script_binding, (
        "Standalone integration scripts missing exact script-path summary bindings: "
        f"{missing_script_binding}"
    )


def test_all_standalone_integration_scripts_with_skip_lanes_write_skipped_counts_to_summary() -> None:
    integration_root = ROOT / "tests" / "integration"
    missing_skipped_binding: list[str] = []

    for path in sorted(integration_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "Standalone integration script; run via python" not in text:
            continue
        if "write_live_integration_summary(" not in text:
            continue
        if "SKIP" not in text:
            continue
        if re.search(r"write_live_integration_summary\(.*?skipped=", text, re.DOTALL) is None:
            missing_skipped_binding.append(
                f"{path.name}: write_live_integration_summary missing skipped= binding"
            )

    assert not missing_skipped_binding, (
        "Standalone integration scripts with skip lanes missing skipped summary bindings: "
        f"{missing_skipped_binding}"
    )


def test_live_runtime_library_scripts_self_bootstrap_repo_imports() -> None:
    http_live = (ROOT / "tests" / "integration" / "test_runtime_libraries_http_live.py").read_text(
        encoding="utf-8"
    )
    python_live = (ROOT / "tests" / "integration" / "test_algenta_mojo_library_live.py").read_text(
        encoding="utf-8"
    )
    cli_mcp_live = (
        ROOT / "tests" / "integration" / "test_cli_mcp_runtime_libraries_live.py"
    ).read_text(encoding="utf-8")

    assert "python3 tests/integration/test_runtime_libraries_http_live.py" in http_live
    assert "PYTHONPATH=. python3 tests/integration/test_runtime_libraries_http_live.py" not in http_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in http_live
    assert "sys.path.insert(0, str(ROOT))" in http_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in http_live
    assert '_emit(f"  ... {name}")' in http_live

    assert "python3 tests/integration/test_algenta_mojo_library_live.py" in python_live
    assert "PYTHONPATH=. python3 tests/integration/test_algenta_mojo_library_live.py" not in python_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in python_live
    assert "sys.path.insert(0, path)" in python_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in python_live
    assert '_emit(f"  ... {name}")' in python_live

    assert "python3 tests/integration/test_cli_mcp_runtime_libraries_live.py" in cli_mcp_live
    assert "PYTHONPATH=. python3 tests/integration/test_cli_mcp_runtime_libraries_live.py" not in cli_mcp_live
    assert "ROOT = Path(__file__).resolve().parents[2]" in cli_mcp_live
    assert "sys.path.insert(0, str(ROOT))" in cli_mcp_live
    assert 'def _format_elapsed_seconds(started_at: float) -> str:' in cli_mcp_live
    assert '_emit(f"  ... {name}")' in cli_mcp_live
    assert "def _resolve_base_url() -> str:" in cli_mcp_live
    assert "def _endpoint_serves_canonical_runtime_contract(base_url: str) -> bool:" in cli_mcp_live
    assert "async def _wait_for_runtime_entitlement_ready(timeout_seconds: float = 10.0)" in cli_mcp_live
    assert "runtime daemon entitlement did not become ready" in cli_mcp_live
    assert '"apps.api_server.main:app"' in cli_mcp_live
    assert "atexit.register(_cleanup_runtime)" in cli_mcp_live


def test_go_live_verify_script_self_bootstraps_repo_imports() -> None:
    go_live_verify = (ROOT / "tests" / "go_live_verify.py").read_text(encoding="utf-8")

    assert "python3 tests/go_live_verify.py" not in go_live_verify
    assert "ROOT = Path(__file__).resolve().parents[1]" in go_live_verify
    assert "sys.path.insert(0, str(ROOT))" in go_live_verify
    assert "from tests.go_live_matrix_status import (" in go_live_verify


def test_typescript_sdk_package_exports_point_to_real_build_outputs() -> None:
    package_json = (ROOT / "packages" / "ts-sdk" / "package.json").read_text(encoding="utf-8")

    assert '"main": "dist/index.js"' in package_json
    assert '"module": "dist/index.js"' in package_json
    assert '"import": "./dist/index.js"' in package_json


def test_typescript_contract_helper_uses_shared_manifest_fixture() -> None:
    helper = (ROOT / "packages" / "ts-sdk" / "src" / "test_contract_helpers.ts").read_text(
        encoding="utf-8"
    )

    assert "../../../tests/manifest_backed_integrations.fixture.json" in helper
    assert "MANIFEST_BACKED_INTEGRATIONS_FIXTURE_PATH =" not in helper
    assert 'readFileSync(resolve(__dirname, "../../../tests/manifest_backed_integrations.fixture.json"), "utf8")' in (
        helper
    )
    assert "const MANIFEST_BACKED_INTEGRATIONS_EXPORT_PATTERN =" not in helper
    assert "type ManifestBackedIntegration = {" in helper
    assert "description: string;" in helper
    assert "icon: string;" in helper
    assert "capabilities: string[];" in helper
    assert "auth_scheme: string;" in helper
    assert "required_scopes: string[];" in helper
    assert "read_only_default: boolean;" in helper
    assert "admin_controls: string[];" in helper
    assert "privacy_url: string;" in helper
    assert "terms_url: string;" in helper
    assert "support_url: string;" in helper
    assert "regions: string[];" in helper
    assert "status: string;" in helper
    assert "integrations: ManifestBackedIntegration[]" in helper
    assert "): ManifestBackedIntegration[]" in helper
    assert "const MANIFEST_BACKED_INTEGRATION_FIELDS =" not in helper
    assert "function normalizeManifestBackedIntegrationsWithAccessor<T>(" not in helper
    assert "function normalizeManifestBackedIntegrations(" in helper
    assert (
        "const fields = Object.keys(MANIFEST_BACKED_INTEGRATIONS[0]) as Array<keyof ManifestBackedIntegration>;"
        in helper
    )
    assert "function isCanonicalManifestBackedIntegrations(" not in helper
    assert "function normalizeOrReuseManifestBackedIntegrations(" in helper
    assert "return integrations === MANIFEST_BACKED_INTEGRATIONS" in helper
    assert "function expectManifestBackedIntegrationsWithAccessor<T>(" not in helper
    assert "export function expectManifestBackedIntegrations(" not in helper
    assert "export function expectManifestBackedIntegrationsEqual(" in helper
    assert (
        "const normalizedLeftIntegrations = normalizeOrReuseManifestBackedIntegrations(leftIntegrations);"
        in helper
    )
    assert "rightIntegrations === leftIntegrations" in helper
    assert "? normalizedLeftIntegrations" in helper
    assert "const normalizedRightIntegrations =" in helper
    assert ": normalizeOrReuseManifestBackedIntegrations(rightIntegrations);" in helper
    assert "expect(normalizedLeftIntegrations).toEqual(normalizedRightIntegrations);" in helper
    assert "pattern: RegExp = MANIFEST_BACKED_INTEGRATIONS_EXPORT_PATTERN" not in helper
    assert "const leftMatch = leftText.match(" in helper
    assert "/(?:export const INTEGRATIONS =|exports\\.INTEGRATIONS =)\\s*(\\[[\\s\\S]*?\\]);/" in helper
    assert "export function expectManifestBackedIntegrationExportText(" not in helper
    assert "export function expectManifestBackedIntegrationExportTextsEqual(" in helper
    assert "export function parseManifestBackedIntegrationExportText(" not in helper
    assert 'expect(leftMatch?.[1], "missing exported INTEGRATIONS array").toBeDefined();' in helper
    assert "const leftIntegrations = JSON.parse(leftMatch![1]) as ManifestBackedIntegration[];" in helper
    assert "rightText === leftText" in helper
    assert "if (rightText === leftText) {" in helper
    assert "return;" in helper
    assert "const rightMatch = rightText.match(" in helper
    assert 'expect(rightMatch?.[1], "missing exported INTEGRATIONS array").toBeDefined();' in helper
    assert "const rightIntegrations = JSON.parse(rightMatch![1]) as ManifestBackedIntegration[];" in helper
    assert (
        "expectManifestBackedIntegrationsEqual(leftIntegrations, MANIFEST_BACKED_INTEGRATIONS);"
        in helper
    )
    assert "expectManifestBackedIntegrations(rightIntegrations);" not in helper
    assert "expectManifestBackedIntegrationsEqual(leftIntegrations, rightIntegrations);" in helper


def test_typescript_dist_artifact_parity_uses_shared_export_text_equality_helper() -> None:
    parity_test = (
        ROOT / "packages" / "ts-sdk" / "src" / "dist_artifact_parity.test.ts"
    ).read_text(encoding="utf-8")

    assert "expectManifestBackedIntegrationExportTextsEqual," in parity_test
    assert "expectManifestBackedIntegrationsEqual," in parity_test
    assert "expectManifestBackedIntegrationExportTextsEqual(distContractText, sourceContractText);" in (
        parity_test
    )
    assert "expectManifestBackedIntegrationsEqual(" in parity_test
    assert "distContractModule.INTEGRATIONS," in parity_test
    assert "sourceContractModule.INTEGRATIONS," in parity_test
    assert "expectManifestBackedIntegrations(distContractModule.INTEGRATIONS);" not in parity_test
    assert "expectManifestBackedIntegrations(sourceContractModule.INTEGRATIONS);" not in parity_test
    assert "parseManifestBackedIntegrationExportText" not in parity_test


def test_typescript_contract_tests_use_shared_manifest_equality_helper() -> None:
    client_test = (ROOT / "packages" / "ts-sdk" / "src" / "client.test.ts").read_text(
        encoding="utf-8"
    )
    runtime_test = (ROOT / "packages" / "ts-sdk" / "src" / "runtime.test.ts").read_text(
        encoding="utf-8"
    )
    index_test = (ROOT / "packages" / "ts-sdk" / "src" / "index.test.ts").read_text(
        encoding="utf-8"
    )

    assert "expectManifestBackedIntegrationsEqual(contract.integrations, INTEGRATIONS);" in client_test
    assert "expectManifestBackedIntegrations(contract.integrations);" not in client_test
    assert "expectManifestBackedIntegrationsEqual(contract.integrations, INTEGRATIONS);" in runtime_test
    assert "expectManifestBackedIntegrations(contract.integrations);" not in runtime_test
    assert "expectManifestBackedIntegrationsEqual(INTEGRATIONS, INTEGRATIONS);" in index_test
    assert "expectManifestBackedIntegrations(INTEGRATIONS);" not in index_test


def test_python_ts_contract_artifact_proofs_use_shared_export_text_equality_helper() -> None:
    generation_test = (ROOT / "tests" / "test_platform_contract_generation.py").read_text(
        encoding="utf-8"
    )
    distribution_test = (ROOT / "tests" / "test_package_distribution_surface.py").read_text(
        encoding="utf-8"
    )

    assert "assert_manifest_backed_integration_texts_equal," in generation_test
    assert "assert_manifest_backed_integration_texts_equal(ts_dist_contract, ts_contract)" in (
        generation_test
    )
    assert "assert_manifest_backed_integration_text," not in generation_test
    assert "parse_manifest_backed_integration_text" not in generation_test
    assert "export const INTEGRATIONS =" not in generation_test
    assert "exports.INTEGRATIONS =" not in generation_test
    assert "assert_manifest_backed_integration_texts_equal," in distribution_test
    assert "assert_manifest_backed_integration_texts_equal(contract_text, source_contract_text)" in (
        distribution_test
    )
    assert "assert_manifest_backed_integration_text," not in distribution_test
    assert "parse_manifest_backed_integration_text" not in distribution_test
    assert "export const INTEGRATIONS =" not in distribution_test
    assert "exports.INTEGRATIONS =" not in distribution_test


def test_manifest_helper_test_files_pin_strict_vs_parity_semantics() -> None:
    python_helper_tests = (ROOT / "tests" / "test_platform_contract.py").read_text(
        encoding="utf-8"
    )
    typescript_helper_tests = (
        ROOT / "packages" / "ts-sdk" / "src" / "test_contract_helpers.test.ts"
    ).read_text(encoding="utf-8")

    assert "test_assert_manifest_backed_integrations_equal_accepts_matching_drifted_payloads" in (
        python_helper_tests
    )
    assert "test_contract_integrations_match_manifest_fails_closed_for_empty_sequences" in (
        python_helper_tests
    )
    assert "test_contract_integrations_match_manifest_fails_closed_for_malformed_input" in (
        python_helper_tests
    )
    assert "test_contract_integrations_match_manifest_accepts_attribute_backed_fixture_payload" in (
        python_helper_tests
    )
    assert "test_contract_integrations_match_manifest_fails_closed_for_drifted_payload" in (
        python_helper_tests
    )
    assert "test_normalize_manifest_backed_integrations_supports_attribute_backed_sequences" in (
        python_helper_tests
    )
    assert "test_normalize_manifest_backed_integrations_rejects_empty_sequences" in (
        python_helper_tests
    )
    assert "test_assert_manifest_backed_integrations_rejects_drifted_payload" in (
        python_helper_tests
    )
    assert "test_assert_manifest_backed_integrations_equal_rejects_drifted_payloads" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_missing_integration_export" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_missing_left_hand_integration_export" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_accepts_matching_esm_and_commonjs_exports" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_accepts_identical_export_texts" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_identical_drifted_export_texts" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_mismatched_integration_payloads" in (
        python_helper_tests
    )
    assert "test_manifest_export_text_helper_rejects_matching_drifted_payloads" in (
        python_helper_tests
    )
    assert "assert contract_integrations_match_manifest([object()]) is False" in python_helper_tests
    assert "assert contract_integrations_match_manifest([]) is False" in python_helper_tests
    assert "assert contract_integrations_match_manifest(integrations) is True" in python_helper_tests
    assert "assert contract_integrations_match_manifest(drifted_integrations) is False" in (
        python_helper_tests
    )
    assert (
        "with pytest.raises(AssertionError, match=\"expected manifest-backed integrations\"):\n"
        "        manifest_helpers.normalize_manifest_backed_integrations([])"
        in python_helper_tests
    )
    assert "assert manifest_helpers.normalize_manifest_backed_integrations(integrations) == (" in (
        python_helper_tests
    )
    assert "with pytest.raises(AssertionError):\n        assert_manifest_backed_integrations(drifted_integrations)" in (
        python_helper_tests
    )
    assert (
        "manifest_helpers.assert_manifest_backed_integrations_equal(\n"
        "        left_drifted_integrations,\n"
        "        right_drifted_integrations,\n"
        "    )"
        in python_helper_tests
    )
    assert (
        "manifest_helpers.assert_manifest_backed_integrations_equal(\n"
        "            list(MANIFEST_BACKED_INTEGRATIONS),\n"
        "            drifted_integrations,\n"
        "        )"
        in python_helper_tests
    )
    assert "with pytest.raises(AssertionError):\n        assert_manifest_backed_integration_texts_equal(" in (
        python_helper_tests
    )
    assert (
        "with pytest.raises(AssertionError, match=\"missing exported INTEGRATIONS array\"):\n"
        "        assert_manifest_backed_integration_texts_equal(\n"
        "            f\"export const INTEGRATIONS = {payload};\",\n"
        "            \"export const CONTRACT_VERSION = '2026.05.0';\",\n"
        "        )"
        in python_helper_tests
    )
    assert (
        "with pytest.raises(AssertionError, match=\"missing exported INTEGRATIONS array\"):\n"
        "        assert_manifest_backed_integration_texts_equal(\n"
            "            \"export const CONTRACT_VERSION = '2026.05.0';\",\n"
            "            f\"exports.INTEGRATIONS = {payload};\",\n"
        "        )"
        in python_helper_tests
    )
    assert "assert_manifest_backed_integration_texts_equal(esm_text, cjs_text)" in python_helper_tests
    assert "assert_manifest_backed_integration_texts_equal(text, text)" in python_helper_tests
    assert "with pytest.raises(AssertionError):\n        assert_manifest_backed_integration_texts_equal(text, text)" in (
        python_helper_tests
    )
    assert "f\"exports.INTEGRATIONS = {right_payload};\"" in python_helper_tests
    assert "fails closed when a copied integration payload drifts from the manifest" in (
        typescript_helper_tests
    )
    assert "normalizes copied manifest-backed integrations before comparing" in (
        typescript_helper_tests
    )
    assert "accepts matching drifted integration payloads in the two-sided parity helper" in (
        typescript_helper_tests
    )
    assert (
        "rejects matching drifted integration export payloads because the left-hand export must stay canonical"
        in typescript_helper_tests
    )
    assert "fails closed when the left-hand integration payload is empty" in typescript_helper_tests
    assert "fails closed when the right-hand integration payload is empty" in (
        typescript_helper_tests
    )
    assert "fails closed when an integration export is missing" in typescript_helper_tests
    assert "fails closed when the left-hand integration export is missing" in (
        typescript_helper_tests
    )
    assert "accepts matching ESM and CommonJS integration exports" in typescript_helper_tests
    assert "accepts identical integration export texts" in typescript_helper_tests
    assert (
        "rejects identical drifted integration export texts because the left-hand export must stay canonical"
        in typescript_helper_tests
    )
    assert "fails closed when an integration export payload drifts from the manifest" in (
        typescript_helper_tests
    )
    assert "expectManifestBackedIntegrationsEqual(cloneManifestBackedIntegrations(), INTEGRATIONS);" in (
        typescript_helper_tests
    )
    assert "expectManifestBackedIntegrationExportTextsEqual(" in typescript_helper_tests
    assert "`export const INTEGRATIONS = ${payload};`" in typescript_helper_tests
    assert "`exports.INTEGRATIONS = ${payload};`" in typescript_helper_tests
    assert "expectManifestBackedIntegrationExportTextsEqual(text, text);" in typescript_helper_tests
    assert "expect(() => expectManifestBackedIntegrationExportTextsEqual(text, text)).toThrowError();" in (
        typescript_helper_tests
    )
    assert "expectManifestBackedIntegrationsEqual(leftDriftedIntegrations, rightDriftedIntegrations);" in (
        typescript_helper_tests
    )
    assert "expect(() =>\n      expectManifestBackedIntegrationsEqual(mismatchedIntegrations, INTEGRATIONS)," in (
        typescript_helper_tests
    )
    assert "expect(() => expectManifestBackedIntegrationsEqual([], INTEGRATIONS)).toThrowError();" in (
        typescript_helper_tests
    )
    assert "expect(() => expectManifestBackedIntegrationsEqual(INTEGRATIONS, [])).toThrowError();" in (
        typescript_helper_tests
    )
    assert "expect(() =>\n      expectManifestBackedIntegrationExportTextsEqual(" in (
        typescript_helper_tests
    )
    assert ").toThrowError(\"missing exported INTEGRATIONS array\");" in typescript_helper_tests
    assert "expectManifestBackedIntegrationExportTextsEqual(" in typescript_helper_tests
    assert "`exports.INTEGRATIONS = ${JSON.stringify(mismatchedIntegrations)};`" in (
        typescript_helper_tests
    )


def test_outward_facing_contract_proofs_use_shared_normalized_manifest_fixture() -> None:
    meta_contract_api = (ROOT / "tests" / "test_meta_contract_api.py").read_text(
        encoding="utf-8"
    )
    mcp_data_tools = (ROOT / "tests" / "test_mcp_data_tools.py").read_text(encoding="utf-8")
    runtime_startup = (ROOT / "tests" / "test_runtime_startup_smoke.py").read_text(
        encoding="utf-8"
    )
    cli_data = (ROOT / "tests" / "test_cli_data.py").read_text(encoding="utf-8")
    mcp_meta_tools = (ROOT / "tests" / "test_mcp_meta_tools.py").read_text(encoding="utf-8")
    query_surface = (ROOT / "tests" / "test_decision_engine_query_surface.py").read_text(
        encoding="utf-8"
    )
    algenta_runtime = (ROOT / "tests" / "test_algenta_runtime.py").read_text(encoding="utf-8")
    platform_contract = (ROOT / "tests" / "test_platform_contract.py").read_text(
        encoding="utf-8"
    )
    decision_engine_client_wrapper = (
        ROOT / "tests" / "test_decision_engine_client_wrapper.py"
    ).read_text(encoding="utf-8")
    decision_engine_lazy_exports = (
        ROOT / "tests" / "test_decision_engine_lazy_exports.py"
    ).read_text(encoding="utf-8")
    algenta_lazy_exports = (ROOT / "tests" / "test_algenta_lazy_exports.py").read_text(
        encoding="utf-8"
    )
    distribution_artifact = (
        ROOT / "tests" / "test_distribution_artifact_privacy_runtime.py"
    ).read_text(encoding="utf-8")
    platform_contract_generation = (
        ROOT / "tests" / "test_platform_contract_generation.py"
    ).read_text(encoding="utf-8")

    assert "assert_manifest_backed_integrations," in meta_contract_api
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in meta_contract_api
    assert "assert_manifest_backed_integrations_equal(" not in meta_contract_api
    assert "assert_manifest_backed_integrations," in mcp_data_tools
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in mcp_data_tools
    assert "assert_manifest_backed_integrations_equal(" not in mcp_data_tools
    assert "assert_manifest_backed_integrations," in runtime_startup
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in runtime_startup
    assert "assert_manifest_backed_integrations_equal(" not in runtime_startup
    assert "assert_manifest_backed_integrations," in cli_data
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in cli_data
    assert "assert_manifest_backed_integrations_equal(" not in cli_data
    assert "assert_manifest_backed_integrations," in mcp_meta_tools
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in mcp_meta_tools
    assert "assert_manifest_backed_integrations_equal(" not in mcp_meta_tools
    assert "assert_manifest_backed_integrations," in query_surface
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in query_surface
    assert "assert_manifest_backed_integrations_equal(" not in query_surface
    assert "assert_manifest_backed_integrations," in algenta_runtime
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in algenta_runtime
    assert "assert_manifest_backed_integrations_equal(" not in algenta_runtime
    assert "assert_manifest_backed_integrations," in decision_engine_client_wrapper
    assert "assert_manifest_backed_integrations_equal," not in decision_engine_client_wrapper
    assert "assert_manifest_backed_integrations," in distribution_artifact
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in distribution_artifact
    assert "assert_manifest_backed_integrations," in platform_contract_generation
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in platform_contract_generation
    assert "assert_manifest_backed_integrations_equal(" not in platform_contract_generation
    assert "normalize_manifest_backed_integrations," not in meta_contract_api
    assert "normalize_manifest_backed_integrations," not in mcp_data_tools
    assert "normalize_manifest_backed_integrations," not in runtime_startup
    assert "normalize_manifest_backed_integrations," not in cli_data
    assert "normalize_manifest_backed_integrations," not in mcp_meta_tools
    assert "normalize_manifest_backed_integrations," not in query_surface
    assert "normalize_manifest_backed_integrations," not in algenta_runtime
    assert "normalize_manifest_backed_integrations," not in decision_engine_lazy_exports
    assert "normalize_manifest_backed_integrations," not in algenta_lazy_exports
    assert 'sys.modules["decision_engine._contract"].INTEGRATIONS' in decision_engine_lazy_exports
    assert 'sys.modules["algenta._contract"].INTEGRATIONS' in algenta_lazy_exports
    assert "_normalized_decision_engine_contract_integrations" not in decision_engine_lazy_exports
    assert "_normalized_algenta_contract_integrations" not in algenta_lazy_exports
    assert "assert_manifest_backed_integrations_equal(" in decision_engine_lazy_exports
    assert "assert_manifest_backed_integrations_equal(" in algenta_lazy_exports
    assert "NORMALIZED_ARTIFACT_CONTRACT_INTEGRATIONS =" not in distribution_artifact
    assert "normalize_manifest_backed_integrations," not in distribution_artifact
    assert "_normalized_module_integrations" not in distribution_artifact
    assert "assert_manifest_backed_integrations_equal(" in distribution_artifact
    assert "NORMALIZED_MANIFEST_INTEGRATIONS =" not in meta_contract_api
    assert "assert_manifest_backed_integrations_equal," not in platform_contract
    assert "normalize_manifest_backed_integrations," not in platform_contract
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in mcp_data_tools
    assert "NORMALIZED_EXPECTED_CONTRACT_INTEGRATIONS =" not in runtime_startup
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in cli_data
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in mcp_meta_tools
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in query_surface
    assert "NORMALIZED_PLATFORM_CONTRACT_INTEGRATIONS =" not in algenta_runtime
    assert "normalized_contract_integrations =" not in platform_contract_generation
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," not in decision_engine_client_wrapper


def test_platform_contract_proof_pins_canonical_manifest_fixture_and_fail_closed_guard() -> None:
    platform_contract = (ROOT / "tests" / "test_platform_contract.py").read_text(
        encoding="utf-8"
    )

    assert "MANIFEST_BACKED_INTEGRATIONS," in platform_contract
    assert 'assert manifest["integrations"] == list(MANIFEST_BACKED_INTEGRATIONS)' in (
        platform_contract
    )
    assert "assert_manifest_backed_integrations(manifest[\"integrations\"])" in platform_contract
    assert "contract_integrations_match_manifest," in platform_contract
    assert "assert contract_integrations_match_manifest([object()]) is False" in platform_contract


def test_python_manifest_helper_exports_normalized_fixture_constant() -> None:
    helper = (ROOT / "tests" / "_manifest_backed_integrations.py").read_text(encoding="utf-8")

    assert "manifest_backed_integrations.fixture.json" in helper
    assert "MANIFEST_BACKED_INTEGRATIONS_FIXTURE_PATH =" not in helper
    assert "MANIFEST_BACKED_INTEGRATIONS = tuple(" in helper
    assert 'Path(__file__)' in helper
    assert '.resolve()' in helper
    assert '.with_name("manifest_backed_integrations.fixture.json")' in helper
    assert "MANIFEST_BACKED_INTEGRATION_FIELDS =" not in helper
    assert "MANIFEST_BACKED_INTEGRATION_NAMES =" not in helper
    assert "MANIFEST_BACKED_READ_ONLY_INTEGRATIONS =" not in helper
    assert "MANIFEST_BACKED_INTEGRATIONS_EXPORT_PATTERN =" not in helper
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS = normalize_manifest_backed_integrations(" in (
        helper
    )
    assert "def assert_manifest_backed_integrations(integrations: Sequence[Any]) -> None:" in (
        helper
    )
    assert "def _get_integration_field(" not in helper
    assert "def _is_canonical_manifest_integration_sequence(" not in helper
    assert "def _normalize_or_reuse_manifest_backed_integrations(" in helper
    assert "integrations is MANIFEST_BACKED_INTEGRATIONS" in helper
    assert "or integrations is NORMALIZED_MANIFEST_BACKED_INTEGRATIONS" in helper
    assert "return NORMALIZED_MANIFEST_BACKED_INTEGRATIONS" in helper
    assert helper.count("if not integrations:") == 1
    assert "assert_manifest_backed_integrations_equal(" in (
        helper
    )
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS," in helper
    assert "def assert_manifest_backed_integration_texts_equal(" in helper
    assert "def parse_manifest_backed_integration_text(" not in helper
    assert 'left_match = re.search(' in helper
    assert 'raise AssertionError("missing exported INTEGRATIONS array")' in helper
    assert "left_integrations = json.loads(left_match.group(1))" in helper
    assert "if right_text == left_text:" in helper
    assert "return" in helper
    assert 'right_match = re.search(' in helper
    assert "right_integrations = json.loads(right_match.group(1))" in helper
    assert "assert_manifest_backed_integrations(left_integrations)" in helper
    assert "assert_manifest_backed_integrations(right_integrations)" not in helper
    assert "_normalize_or_reuse_manifest_backed_integrations(integrations)" in helper
    assert "if expected_integrations is integrations:" in helper
    assert "normalized_expected_integrations = normalized_integrations" in helper
    assert "_normalize_or_reuse_manifest_backed_integrations(" in helper
    assert "fields = tuple(MANIFEST_BACKED_INTEGRATIONS[0].keys())" in helper
    assert "integration[field] if isinstance(integration, Mapping) else getattr(integration, field)" in (
        helper
    )
    assert "assert_manifest_backed_integrations_equal(left_integrations, right_integrations)" in (
        helper
    )
    assert "assert normalized_integrations == normalized_expected_integrations" in helper
    assert "def contract_integrations_match_manifest(integrations: Sequence[Any]) -> bool:" in (
        helper
    )
    assert "_normalize_or_reuse_manifest_backed_integrations(integrations)" in helper
    assert "== NORMALIZED_MANIFEST_BACKED_INTEGRATIONS" in helper
    assert "assert_manifest_backed_integrations(integrations)" not in helper
    assert "except (AssertionError, AttributeError, IndexError, KeyError, TypeError):" in helper
    assert "NORMALIZED_MANIFEST_BACKED_INTEGRATIONS" in helper


def test_root_test_graph_includes_formal_runtime_foundation_proof_bundle() -> None:
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package_json["scripts"]

    assert scripts["test:js"] == (
        "pnpm --dir packages/ts-sdk test -- --run "
        "src/libraries.test.ts src/runtime_daemon_client.test.ts src/index.test.ts "
        "&& pnpm --dir apps/gateway test "
        "&& pnpm --dir apps/gateway exec tsx --test ../../examples/shared/privacyProfile.test.ts"
    )
    assert scripts["test"] == "pnpm test:js && pnpm test:formal-runtime-foundation"
    assert scripts["validate:formal-runtime-foundation"] == (
        "./scripts/run_repo_python.sh scripts/validate_runtime_release.py --format table"
    )
    assert (ROOT / "scripts" / "run_repo_python.sh").exists()
    assert "tests/test_platform_contract.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_platform_contract_schema_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_manifest.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_admin_api.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_release_validation.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_validate_runtime_release.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_manifest_model_validation.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_schema_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_startup_smoke.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_decision_engine_query_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_decision_engine_lazy_exports.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_algenta_lazy_exports.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_algenta_runtime.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_algenta_runtime_llm_and_agent_surface.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "tests/test_algenta_client_plan_surface.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "tests/test_cli_data.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_mcp_meta_tools.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_mcp_llm_agent_tools.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_mcp_router.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_js_workspace_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_package_distribution_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_surface_compatibility.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_benchmark_inventory_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_scorecard_suite_summaries.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_csv_pipeline_summary.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_benchmark_scorecard_sync.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_go_live_scorecard.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_live_integration_artifacts.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_llm_rollout_live_artifacts.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_llm_rollout_scorecard.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_plan_alignment_matrix.py" in scripts["test:formal-runtime-foundation"]
    assert scripts["test:formal-runtime-foundation"].startswith(
        "./scripts/run_repo_python.sh tests/integration/test_csv_pipeline.py && "
        "./scripts/run_repo_python.sh benchmarks/scorecard_suite_summaries.py && "
        'if [ "${DE_SKIP_GO_LIVE_VERIFY:-0}" != "1" ]; then ./scripts/run_repo_python.sh tests/go_live_verify.py; fi && '
        "./scripts/run_repo_python.sh benchmarks/llm_rollout_proof_bundle.py --skip-live && "
        "./scripts/run_repo_python.sh -m pytest -q "
    )
    assert 'DE_SKIP_GO_LIVE_VERIFY:-0' in scripts["test:formal-runtime-foundation"]
    assert (
        "&& ./scripts/run_repo_python.sh tests/integration/test_runtime_libraries_http_live.py"
        in scripts["test:formal-runtime-foundation"]
    )
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_cli.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_algenta_client_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_typescript_sdk_client_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_typescript_runtime_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_python_sdk.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_algenta_runtime_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_mcp_server.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_openapi.py" in scripts["test:formal-runtime-foundation"]
    assert (
        scripts["check"]
        == "pnpm lint && pnpm test && pnpm validate:formal-runtime-foundation && pnpm build"
    )


def test_go_live_full_real_skips_nested_verifier_inside_root_js_check() -> None:
    full_real = (ROOT / "tests" / "integration" / "test_go_live_full_real.py").read_text(
        encoding="utf-8"
    )

    assert 'if name == "Root JavaScript workspace check":' in full_real
    assert 'suite_env["DE_SKIP_GO_LIVE_VERIFY"] = "1"' in full_real
