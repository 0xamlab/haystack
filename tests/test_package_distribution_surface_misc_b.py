"""Tests for the secondary package distribution surface."""
from __future__ import annotations

from tests._test_package_distribution_surface_helpers import *  # noqa: F401,F403


def test_typescript_package_surface_includes_package_readme_and_registry_metadata() -> None:
    package_root = ROOT / "packages" / "ts-sdk"
    readme_text = (package_root / "README.md").read_text()
    package_json = json.loads((package_root / "package.json").read_text())
    tsconfig = json.loads((package_root / "tsconfig.json").read_text())
    source_contract_text = (package_root / "src" / "contract.ts").read_text()
    contract_text = (package_root / "dist" / "contract.js").read_text()
    # client.d.ts is now a barrel re-exporting per-domain sub-modules.
    # Concat the barrel + all _client_*.d.ts files so textual surface checks
    # cover the same definitions as the pre-split monolithic client.d.ts.
    dist_dir = package_root / "dist"
    client_types = (dist_dir / "client.d.ts").read_text() + "\n".join(
        p.read_text() for p in sorted(dist_dir.glob("_client_*.d.ts"))
    )
    # runtime.d.ts is now a barrel re-exporting per-domain sub-modules.
    # Concat the barrel + all _runtime_*.d.ts files so textual surface checks
    # cover the same definitions as the pre-split monolithic runtime.d.ts.
    runtime_types = (dist_dir / "runtime.d.ts").read_text() + "\n".join(
        p.read_text() for p in sorted(dist_dir.glob("_runtime_*.d.ts"))
    )
    # types.d.ts is now a barrel re-exporting sub-modules. Concat all
    # _types_*.d.ts so textual surface checks cover the same definitions.
    dist_dir = package_root / "dist"
    shared_types = (dist_dir / "types.d.ts").read_text() + "\n".join(
        p.read_text() for p in sorted(dist_dir.glob("_types_*.d.ts"))
    )

    assert package_json["name"] == "algenta-sdk"
    # LICENSE is published with the package (Apache-2.0, per GTM D2).
    assert package_json["files"] == ["dist", "proto", "README.md", "LICENSE"]
    assert package_json["homepage"] == "https://docs.algenta.ai/sdks/typescript"
    assert package_json["description"] == (
        "TypeScript and JavaScript SDK for Algenta's HTTP API, local runtime, "
        "simulations, governed data, and repository intelligence"
    )
    assert package_json["publishConfig"] == {
        "access": "public",
        "registry": "https://registry.npmjs.org/",
    }
    assert len(readme_text.splitlines()) <= 180
    assert len(readme_text.encode("utf-8")) <= 12000
    assert package_json["repository"]["directory"] == "packages/ts-sdk"
    # #717 repointed the published package's repository/bug-tracker metadata at the public
    # algenta-sdk repo (the SDK is mirrored/published there), not the algenta monorepo.
    assert package_json["bugs"]["url"] == "https://github.com/thyn-ai/algenta-sdk/issues"
    assert "src/**/*.test.ts" in tsconfig["exclude"]
    assert_manifest_backed_integration_texts_equal(contract_text, source_contract_text)
    for required in (
        "npm install algenta-sdk",
        "AlgentaClient",
        "PRIMARY_DATA_QUERY_CONTRACT.api.contract_endpoint",
        "client.listDatasets",
        "client.getDatasetSummary",
        "client.queryWithMetadata",
        "## Runtime and Local Libraries",
        "users do not",
        "separate Mojo process",
        "Runtime forwards the governed helper groups",
        "## Unified Capability Plane",
        "client.routeCapabilities",
        "client.executeCapability",
        "Execution ownership remains authoritative",
        "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1",
        "https://docs.algenta.ai/sdks/typescript",
        "npm run build",
    ):
        assert required in readme_text
    for forbidden in (
        "de_live_",
        "https://docs.algenta.ai/direct-api-client",
        "https://docs.algenta.ai/sdk/typescript",
        "Local Consumer Sync Checklist",
        "pagination-only `listDatasets(...)` shape",
        "`listDatasets({ page?, limit? })`",
        "stale `algenta-sdk` build",
    ):
        assert forbidden not in readme_text
    assert "usage(): Promise<UsageInfo>;" in client_types
    assert "limits(): Promise<LimitsInfo>;" in client_types
    assert "submitJob(request: SimulateRequest, callbackUrl?: string): Promise<JobSubmitResponse>;" in client_types
    assert "getJob(jobId: string): Promise<JobStatusResponse>;" in client_types
    assert "getJobResult(jobId: string): Promise<Record<string, unknown>>;" in client_types
    assert "listJobs(options?:" in client_types
    assert "Promise<JobListResponse>;" in client_types
    assert "cancelJob(jobId: string): Promise<JobStatusResponse>;" in client_types
    assert "pollJob(jobId: string, options?: {" in client_types
    assert "registerTrigger(request: RegisterTriggerRequest)" in client_types
    assert "listTriggers(options?:" in client_types
    assert "Promise<TriggerListResponse>;" in client_types
    assert "fireTrigger(triggerId: string" in client_types
    assert "Promise<TriggerFireResponse>;" in client_types
    assert "pauseTrigger(triggerId: string" in client_types
    assert "Promise<TriggerPauseResponse>;" in client_types
    assert "deleteTrigger(triggerId: string)" in client_types
    assert "Promise<TriggerDeleteResponse>;" in client_types
    assert "listDevices(options?:" in client_types
    assert "Promise<DeviceListResponse>;" in client_types
    assert "revokeDevice(registrationId: string): Promise<DeviceRevokeResponse>;" in client_types
    assert "usage(): Promise<UsageInfo>;" in runtime_types
    assert "limits(): Promise<LimitsInfo>;" in runtime_types
    assert "submitJob(request: SimulateRequest, callbackUrl?: string): Promise<JobSubmitResponse>;" in runtime_types
    assert "getJob(jobId: string): Promise<JobStatusResponse>;" in runtime_types
    assert "getJobResult(jobId: string): Promise<Record<string, unknown>>;" in runtime_types
    assert "listJobs(options?:" in runtime_types
    assert "Promise<JobListResponse>;" in runtime_types
    assert "cancelJob(jobId: string): Promise<JobStatusResponse>;" in runtime_types
    assert "pollJob(jobId: string, options?: {" in runtime_types
    assert "registerTrigger(request: RegisterTriggerRequest)" in runtime_types
    assert "listTriggers(options?:" in runtime_types
    assert "Promise<TriggerListResponse>;" in runtime_types
    assert "fireTrigger(triggerId: string" in runtime_types
    assert "Promise<TriggerFireResponse>;" in runtime_types
    assert "pauseTrigger(triggerId: string" in runtime_types
    assert "Promise<TriggerPauseResponse>;" in runtime_types
    assert "deleteTrigger(triggerId: string)" in runtime_types
    assert "Promise<TriggerDeleteResponse>;" in runtime_types
    assert "listDevices(options?:" in runtime_types
    assert "Promise<DeviceListResponse>;" in runtime_types
    assert "revokeDevice(registrationId: string): Promise<DeviceRevokeResponse>;" in runtime_types
    assert 'baseUrl: "http://localhost:8000"' in readme_text
    runtime_section = readme_text[readme_text.index("## Runtime and Local Libraries") :]
    assert 'baseUrl: "https://api.algenta.ai"' not in runtime_section
    assert "const models = await rt.listModels();" in readme_text
    assert "const tokenized = await rt.tokenize({ input: \"alpha beta\" });" in readme_text
    assert "const usage = await rt.usage();" in readme_text
    assert "const recommendation = await rt.recommend(" in readme_text
    assert "Runtime forwards the governed helper groups" in readme_text
    for runtime_group in (
        "models and vector utilities",
        "account and team controls",
        "connectors, datasets",
        "repository intelligence, agent runs",
        "deployment",
        "lifecycle, and decision helpers",
    ):
        assert runtime_group in readme_text
    assert "Private modes fail closed" in readme_text
    assert 'export type RuntimeMaturity = "experimental" | "benchmarked" | "parity_tested" | "channel_covered" | "enterprise_ready" | "deprecated";' in shared_types
    assert 'export type RuntimeSideEffectClass = "read_only" | "write_scoped" | "write_external" | "exec_external" | "network_external";' in shared_types
    assert 'export type RuntimeRiskLevel = "low" | "medium" | "high" | "critical";' in shared_types
    assert 'export type RuntimeReplayability = "deterministic" | "artifact_backed" | "non_replayable";' in shared_types
    assert 'export type RuntimeSupportedChannel = "python_sdk" | "typescript_sdk" | "cli" | "mcp";' in shared_types
    assert 'export type RuntimeAuxiliaryChannel = "bundled_worker" | "runtime_local";' in shared_types
    assert 'export type RuntimeFeatureFlagChannel = "http_api_feature_flag";' in shared_types
    assert "export type RuntimeBenchmarkClassCode =" in shared_types
    assert '"B1"' in shared_types
    assert '"B6"' in shared_types
    assert '"B8"' in shared_types
    assert '"B10";' in shared_types
    assert "evidence_paths: string[];" in shared_types
    # decision_engine.models_runtime_manifest is now a package; concatenate
    # the facade + every submodule so textual surface checks cover the same
    # source area as before modularization.
    python_manifest_dir = (
        ROOT / "packages" / "python-sdk" / "decision_engine" / "models_runtime_manifest"
    )
    python_runtime_manifest_models = "\n".join(
        p.read_text() for p in sorted(python_manifest_dir.glob("*.py"))
    )
    # runtime_model_manifest.py is a thin facade; the actual enum + model
    # definitions live in _runtime_manifest_*.py submodules. Concatenate the
    # facade with every submodule so the textual surface checks below still
    # cover the whole public-API source.
    algenta_dir = ROOT / "packages" / "algenta" / "algenta"
    algenta_runtime_manifest_models = "\n".join(
        [(algenta_dir / "runtime_model_manifest.py").read_text()]
        + [p.read_text() for p in sorted(algenta_dir.glob("_runtime_manifest_*.py"))]
    )
    assert 'checkpoint_replay_overhead = "B6"' in python_runtime_manifest_models
    assert 'checkpoint_replay_overhead = "B6"' in algenta_runtime_manifest_models
    assert 'provider_routing_overhead = "B8"' in python_runtime_manifest_models
    assert 'provider_routing_overhead = "B8"' in algenta_runtime_manifest_models
    assert "evidence_paths: list[StrictStr] = Field(default_factory=list)" in (
        python_runtime_manifest_models
    )
    assert "evidence_paths: list[str] = field(default_factory=list)" in (
        algenta_runtime_manifest_models
    )
    assert "export type RuntimeBenchmarkMetric =" in shared_types
    assert '"p50"' in shared_types
    assert '"cost_per_successful_run";' in shared_types
    assert "export type RuntimeBenchmarkBaseline =" in shared_types
    assert '"Python reference"' in shared_types
    assert '"Algenta Mojo-native path";' in shared_types
    assert 'export type RuntimeDeploymentMode = "saas" | "vpc" | "self_hosted" | "air_gapped" | "hybrid_provider" | "local_dev_daemon";' in shared_types
    assert 'export type RuntimeLayer = "mojo_llm_runtime_core" | "python_compatibility_ring" | "llm_api_provider_layer" | "agent_runtime" | "decision_runtime" | "enterprise_control_plane";' in shared_types
    assert "export type RuntimeExecutionTransition =" in shared_types
    assert '"model_call_started"' in shared_types
    assert '"failure_emitted";' in shared_types
    assert "export type RuntimeReleaseCondition =" in shared_types
    assert '"manifest-listed"' in shared_types
    assert '"deployment-mode validated";' in shared_types
    assert "export type RuntimeFailureCode =" in shared_types
    assert '"provider_timeout"' in shared_types
    assert '"checkpoint_state_overflow";' in shared_types
    assert "export type RuntimeInvariantName =" in shared_types
    assert '"Manifest Truth"' in shared_types
    assert '"Tenant Non-Interference";' in shared_types
    assert "export type RuntimeExecutionStateField =" in shared_types
    assert '"request"' in shared_types
    assert '"decision_state";' in shared_types
    assert "export type RuntimeExecutionValidityRule =" in shared_types
    assert '"schema-valid"' in shared_types
    assert '"audit-visible";' in shared_types
    assert "export type RuntimeLineageNodeField =" in shared_types
    assert '"node_id"' in shared_types
    assert '"schema_snapshot_id";' in shared_types
    assert "export type RuntimeExternalNondeterminismSource =" in shared_types
    assert '"provider responses"' in shared_types
    assert '"external API outputs";' in shared_types
    assert "export type RuntimeNondeterminismArtifact =" in shared_types
    assert '"provider response record"' in shared_types
    assert '"backend or version identifier";' in shared_types
    assert "export type RuntimeArtifactLineageStep =" in shared_types
    assert '"input"' in shared_types
    assert '"evaluation result";' in shared_types
    assert "export type RuntimeCapabilityField =" in shared_types
    assert '"tool_name"' in shared_types
    assert '"approval_required";' in shared_types
    assert "export type RuntimeCapabilityRule =" in shared_types
    assert '"MCP tools are untrusted by default."' in shared_types
    assert (
        '"Approvals and fallbacks derive from capability algebra, not ad hoc code paths.";'
        in shared_types
    )
    assert "export type RuntimeSchedulerPolicy =" in shared_types
    assert '"FIFO"' in shared_types
    assert '"policy_constrained";' in shared_types
    assert "export type RuntimeSchedulerMinimizeObjective =" in shared_types
    assert '"tail latency"' in shared_types
    assert '"starvation";' in shared_types
    assert "export type RuntimeSchedulerMaximizeObjective =" in shared_types
    assert '"GPU or CPU utilization"' in shared_types
    assert '"fairness";' in shared_types
    assert "export type RuntimeSchedulerInvariant =" in shared_types
    assert '"No request starves indefinitely."' in shared_types
    assert '"Speculative decoding may not emit unverified tokens.";' in shared_types
    assert "export type RuntimeMemoryRegion =" in shared_types
    assert '"model weights"' in shared_types
    assert '"tenant-local cache";' in shared_types
    assert "export type RuntimeMemoryRule =" in shared_types
    assert '"KV pages are tenant-scoped."' in shared_types
    assert '"Memory pressure must emit typed failure and never degrade silently.";' in shared_types
    assert "export type RuntimeModuleId =" in shared_types
    assert '"bpe_tokenizer"' in shared_types
    assert '"generation_loop";' in shared_types
    assert "export type RuntimePublicEndpoint =" in shared_types
    assert '"/v1/meta/contract"' in shared_types
    assert '"/v1/runtime/manifest";' in shared_types
    assert "export type RuntimeAdminEndpoint =" in shared_types
    assert '"/v1/admin/runtime/modules"' in shared_types
    assert '"/v1/admin/runtime/validation";' in shared_types
    assert "export type RuntimeFeatureFlagEndpoint =" in shared_types
    assert '"/v1/libraries"' in shared_types
    assert '"/v1/libraries/execute";' in shared_types
    assert "maturity_counts: Partial<Record<RuntimeMaturity, number>>;" in shared_types
    assert "layer_counts: Partial<Record<RuntimeLayer, number>>;" in shared_types
    assert "maturity: Partial<Record<RuntimeModuleId, RuntimeMaturity>>;" in shared_types
    assert 'export type RuntimeReleaseGateId = "A" | "B" | "C" | "D" | "E" | "F" | "G";' in shared_types
    assert "export type RuntimeSLOBudgetName =" in shared_types
    assert '"runtime_manifest_load"' in shared_types
    assert '"replay";' in shared_types
    assert "export type RuntimeSLOBudgetAppliesTo =" in shared_types
    assert '"first-party runtime manifest route"' in shared_types
    assert '"runs up to 1000 events";' in shared_types
    assert "export type RuntimeProofObligation =" in shared_types
    assert '"numerical parity"' in shared_types
    assert '"metering correctness";' in shared_types
    assert "export type RuntimeEvaluationMethod =" in shared_types
    assert '"bootstrap confidence intervals"' in shared_types
    assert '"sensitivity analysis";' in shared_types
    assert "export type RuntimeEvaluationDimension =" in shared_types
    assert '"answer correctness"' in shared_types
    assert '"latency-quality frontier";' in shared_types
    assert "export type RuntimeReleaseBlocker =" in shared_types
    assert '"replay success regression"' in shared_types
    assert '"decision-plan validity drop";' in shared_types
    assert "export type RuntimeThreatClass =" in shared_types
    assert '"prompt injection"' in shared_types
    assert '"quota bypass";' in shared_types
    assert "export type RuntimeThreatControl =" in shared_types
    assert '"tool allowlists"' in shared_types
    assert '"runtime attestation";' in shared_types
    assert 'export type RuntimeThreatRule = "MCP tools are untrusted by default.";'
    assert "export type RuntimeReleaseArtifact =" in shared_types
    assert '"signed runtime manifest"' in shared_types
    assert '"known limitations";' in shared_types
    assert "maturity: RuntimeMaturity;" in shared_types
    assert "status: RuntimeMaturity;" in shared_types
    assert "layer: RuntimeLayer;" in shared_types
    assert 'export type RuntimeCompiledEngine = "mojo" | "python_fallback";' in shared_types
    assert "export type RuntimeBenchmarkDiscoveryRule =" in shared_types
    assert "export type RuntimeNonShippingRule =" in shared_types
    assert "name: RuntimeModuleId;" in shared_types
    assert "compiled_engine: RuntimeCompiledEngine;" in shared_types
    assert "runtime_core_layer: RuntimeLayer;" in shared_types
    assert "benchmark_discovery_rule: RuntimeBenchmarkDiscoveryRule;" in shared_types
    assert "non_shipping_rule: RuntimeNonShippingRule;" in shared_types
    assert "name: RuntimeInvariantName;" in shared_types
    assert "state_fields: RuntimeExecutionStateField[];" in shared_types
    assert "validity_rules: RuntimeExecutionValidityRule[];" in shared_types
    assert "allowed_transitions: RuntimeExecutionTransition[];" in shared_types
    assert "condition: RuntimeReleaseCondition;" in shared_types
    assert "required_conditions: RuntimeReleaseCondition[];" in shared_types
    assert "code: RuntimeBenchmarkClassCode;" in shared_types
    assert "required_metrics: RuntimeBenchmarkMetric[];" in shared_types
    assert "baselines: RuntimeBenchmarkBaseline[];" in shared_types
    assert "sources: RuntimeExternalNondeterminismSource[];" in shared_types
    assert "required_artifacts: RuntimeNondeterminismArtifact[];" in shared_types
    assert "artifact_flow: RuntimeArtifactLineageStep[];" in shared_types
    assert "required_node_fields: RuntimeLineageNodeField[];" in shared_types
    assert "public_supported_channels: RuntimeSupportedChannel[];" in shared_types
    assert "validated_auxiliary_channels: RuntimeAuxiliaryChannel[];" in shared_types
    assert "feature_flag_channels: RuntimeFeatureFlagChannel[];" in shared_types
    assert "runtime_modules: RuntimeModuleId[];" in shared_types
    assert "public_endpoints: RuntimePublicEndpoint[];" in shared_types
    assert "admin_endpoints: RuntimeAdminEndpoint[];" in shared_types
    assert "feature_flag_endpoints: RuntimeFeatureFlagEndpoint[];" in shared_types
    assert "proof_obligations: RuntimeProofObligation[];" in shared_types
    assert "obligations: RuntimeProofObligation[];" in shared_types
    assert "methods: RuntimeEvaluationMethod[];" in shared_types
    assert "release_blockers: RuntimeReleaseBlocker[];" in shared_types
    assert "deployment_mode: RuntimeDeploymentMode | null;" in shared_types
    assert "deployment_mode_raw: string;" in shared_types
    assert "current: RuntimeDeploymentMode;" in shared_types
    assert "supported_modes: RuntimeDeploymentMode[];" in shared_types
    assert "side_effect_class: RuntimeSideEffectClass[];" in shared_types
    assert "risk_level: RuntimeRiskLevel[];" in shared_types
    assert "replayability: RuntimeReplayability[];" in shared_types
    assert "required_fields: RuntimeCapabilityField[];" in shared_types
    assert "rules: RuntimeCapabilityRule[];" in shared_types
    assert "name: RuntimeSLOBudgetName;" in shared_types
    assert "applies_to: RuntimeSLOBudgetAppliesTo;" in shared_types
    assert "policies: RuntimeSchedulerPolicy[];" in shared_types
    assert "minimize: RuntimeSchedulerMinimizeObjective[];" in shared_types
    assert "maximize: RuntimeSchedulerMaximizeObjective[];" in shared_types
    assert "invariants: RuntimeSchedulerInvariant[];" in shared_types
    assert "regions: RuntimeMemoryRegion[];" in shared_types
    assert "rules: RuntimeMemoryRule[];" in shared_types
    assert "failure_codes: RuntimeFailureCode[];" in shared_types
    assert "dimensions: RuntimeEvaluationDimension[];" in shared_types
    assert "threat_classes: RuntimeThreatClass[];" in shared_types
    assert "controls: RuntimeThreatControl[];" in shared_types
    assert "non_negotiable_rules: RuntimeThreatRule[];" in shared_types
    assert "code: RuntimeFailureCode;" in shared_types
    assert "gate: RuntimeReleaseGateId;" in shared_types
    assert "required_artifacts: RuntimeReleaseArtifact[];" in shared_types
    assert "shipping_runtime_benchmark_speedups_x: number[];" in shared_types
    assert "shipping_runtime_compiled_artifacts: string[];" in shared_types
    assert "shipping_runtime_compiled_engines: RuntimeCompiledEngine[];" in shared_types
    assert "shipping_runtime_max_cold_ms: number[];" in shared_types
    assert "shipping_runtime_max_warm_ms: number[];" in shared_types
    assert "shipping_runtime_max_hot_ms: number[];" in shared_types
    assert "export type RuntimeArtifactKind =" in shared_types
    assert '"proof_bundle"' in shared_types
    assert '"compiled_mojo_binary";' in shared_types
    assert 'export type RuntimeSignatureAlgorithm = "hmac-sha256";' in shared_types
    assert 'export type RuntimeSignatureScope = "control_plane_hmac_v1";' in shared_types
    assert "kind: RuntimeArtifactKind;" in shared_types
    assert "algorithm: RuntimeSignatureAlgorithm;" in shared_types
    assert "scope: RuntimeSignatureScope;" in shared_types
    assert "search?: string;" in client_types
    assert "status?: string;" in client_types
    assert "sourceName?: string;" in client_types
    assert "compact?: boolean;" in client_types
    assert "getContract(): Promise<PlatformContractResponse>;" in client_types
    assert "getRuntimeManifest(): Promise<RuntimeManifestResponse>;" in client_types
    assert "getRuntimeModules(): Promise<RuntimeAdminModulesResponse>;" in client_types
    assert "getRuntimeBenchmarks(): Promise<RuntimeAdminBenchmarksResponse>;" in client_types
    assert "get validationErrors(): Array<Record<string, unknown>>;" in client_types
    assert "get fieldErrors(): Array<Record<string, unknown>>;" in client_types
    assert (
        "getRuntimeReleaseValidation(): Promise<RuntimeReleaseValidationResponse>;"
        in client_types
    )
    assert "getDatasetSummary(datasetId: string): Promise<DatasetSummaryResult>;" in client_types
    assert (
        "queryWithMetadata(request: Record<string, unknown>): Promise<QueryWithMetadataResponse>;"
        in client_types
    )
    assert "queryBatch(request:" in client_types
    assert (
        "querySqlReport(request: QuerySqlReportRequest): Promise<QuerySqlReportResponse>;"
        in client_types
    )
    assert "getContract(): Promise<PlatformContractResponse>;" in runtime_types
    assert "getRuntimeManifest(): Promise<RuntimeManifestResponse>;" in runtime_types
    assert "getRuntimeModules(): Promise<RuntimeAdminModulesResponse>;" in runtime_types
    assert "getRuntimeBenchmarks(): Promise<RuntimeAdminBenchmarksResponse>;" in runtime_types
    assert "get validationErrors(): Array<Record<string, unknown>>;" in runtime_types
    assert "get fieldErrors(): Array<Record<string, unknown>>;" in runtime_types
    assert (
        "getRuntimeReleaseValidation(): Promise<RuntimeReleaseValidationResponse>;"
        in runtime_types
    )
    assert "getDatasetSummary(datasetId: string): Promise<DatasetSummaryResult>;" in runtime_types
    assert "queryWithMetadata(" in runtime_types
    assert "queryBatch(request:" in runtime_types
    assert (
        "querySqlReport(request: QuerySqlReportRequest): Promise<QuerySqlReportResponse>;"
        in runtime_types
    )


def test_cli_docs_cover_streaming_runtime_surface() -> None:
    text = CLI_DOC.read_text()
    assert "de recommend recommend_request.json --format json" in text
    assert "de decision score score_request.json --format json" in text
    assert "de decision batch batch_request.json --format json" in text
    assert "de decision compare compare_request.json --format json" in text
    assert "de product decision product_decision_request.json --format json" in text
    assert "de product agent-run product_agent_run_request.json --format json" in text
    assert "de product optimize product_optimize_request.json --format json" in text
    assert "de product retrieve product_retrieve_request.json --format json" in text
    assert "de product forecast product_forecast_request.json --format json" in text
    assert "de connectors create connector_request.json --format json" in text
    assert "de connectors preview-test connector_preview_request.json --format json" in text
    assert "de connectors browse <connector_id> --format json" in text
    assert "de connectors preview-browse connector_preview_request.json --format json" in text
    assert "de team list --format json" in text
    assert "de team invite new.user@example.com member --format json" in text
    assert "de team update-role user_123 viewer --format json" in text
    assert "de team remove user_123 --format json" in text
    assert "de team audit-logs --format json" in text
    assert "de team audit-artifacts --format json" in text
    assert "de devices list --format json" in text
    assert "de devices revoke <registration_id> --format json" in text
    assert "de billing info --format json" in text
    assert "de metering ingest metering_request.json --format json" in text
    assert "de execution-policy get --format json" in text
    assert "de execution-policy snapshots --format json" in text
    assert "de deployments regions --format json" in text
    assert "de deployments get --format json" in text
    assert "de deployments cost <deployment_id> --format json" in text
    assert "de llm resolve-artifact artifact_request.json --format json" in text
    assert "de llm chat chat_request.json --stream --format json" in text
    assert "de llm responses responses_request.json --stream" in text
    assert "de agent-runs list --status completed --format json" in text
    assert "de agent-runs events <run_id> --stream --format json" in text
    assert "de agent-runs checkpoints <run_id> --format json" in text
    assert "de agent-runs query-checkpoints --status completed --format json" in text
    assert "de agent-runs mission-events <run_id> --limit 25 --format json" in text
    assert "de agent-runs query-mission-events --status completed --format json" in text
    assert "de agent-runs telemetry <run_id> --limit 25 --format json" in text
    assert "de agent-runs query-telemetry --status completed --format json" in text
    assert "`de recommend <request.json>`" in text
    assert "`de decision score <request.json>`" in text
    assert "`de decision batch <request.json>`" in text
    assert "`de decision compare <request.json>`" in text
    assert "`de product decision <request.json>`" in text
    assert "`de product agent-run <request.json>`" in text
    assert "`de product optimize <request.json>`" in text
    assert "`de product retrieve <request.json>`" in text
    assert "`de product forecast <request.json>`" in text
    assert "`de connectors create <request.json>`" in text
    assert "`de connectors preview-test <request.json>`" in text
    assert "`de connectors browse <connector_id>`" in text
    assert "`de connectors preview-browse <request.json>`" in text
    assert "`de team list`" in text
    assert "`de team invite <email> [role]`" in text
    assert "`de team update-role <user_id> <role>`" in text
    assert "`de team remove <user_id>`" in text
    assert "`de team audit-logs`" in text
    assert "`de team audit-artifacts`" in text
    assert "`de devices list`" in text
    assert "`de devices revoke <registration_id>`" in text
    assert "`de billing info`" in text
    assert "`de metering ingest <request.json>`" in text
    assert "`de execution-policy get`" in text
    assert "`de execution-policy snapshots`" in text
    assert "`de deployments regions`" in text
    assert "`de deployments get`" in text
    assert "`de deployments cost <deployment_id>`" in text
    assert "`de llm resolve-artifact <request.json>`" in text
    assert "`de llm chat <request.json> --stream`" in text
    assert "`de llm responses <request.json> --stream`" in text
    assert "`de agent-runs list [--status ...]`" in text
    assert "`de agent-runs events <run_id> --stream`" in text
    assert "`de agent-runs checkpoints <run_id>`" in text
    assert "`de agent-runs query-checkpoints [--status ...]`" in text
    assert "`de agent-runs mission-events <run_id> [--limit ...]`" in text
    assert "`de agent-runs query-mission-events [--status ...]`" in text
    assert "`de agent-runs telemetry <run_id> [--limit ...]`" in text
    assert "`de agent-runs query-telemetry [--status ...]`" in text
    assert "--format json` prints one JSON object per SSE event line" in text
    assert "default table mode renders deterministic summaries" in text
