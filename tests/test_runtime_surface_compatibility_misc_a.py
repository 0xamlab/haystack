"""Tests for test_runtime_surface_compatibility: misc_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-4/tests/test_runtime_surface_compatibility.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_surface_compatibility_helpers import *  # noqa: F401,F403


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
    # runtime.ts is now a barrel re-exporting per-domain sub-modules; concat
    # the barrel + every _runtime_*.ts so textual surface checks cover the
    # same source content as before the modularization.
    src_dir = ROOT / "packages" / "ts-sdk" / "src"
    ts_runtime = (src_dir / "runtime.ts").read_text(encoding="utf-8") + "\n".join(
        p.read_text(encoding="utf-8") for p in sorted(src_dir.glob("_runtime_*.ts"))
    )
    ts_index = (src_dir / "index.ts").read_text(encoding="utf-8")

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

    # Counts are derived from the registry itself + a regression floor, never a
    # magic number that has to be bumped on every new tool (prior feedback).
    assert len(TOOLS) == len(set(TOOLS))  # no duplicate registrations
    assert len(specs) == len(TOOLS)  # specs and registry stay in lockstep
    assert len(TOOLS) >= 137  # regression floor: the surface must never shrink
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
        "list_agent_runs",
        "get_agent_run",
        "get_agent_run_events",
        "get_agent_run_checkpoints",
        "query_agent_run_checkpoints",
        "get_agent_run_mission_events",
        "query_agent_run_mission_events",
        "get_agent_run_telemetry",
        "query_agent_run_telemetry",
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
        "run_repository_pipeline",
        "simulate_repository_patch",
        "run_repository_fix",
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

