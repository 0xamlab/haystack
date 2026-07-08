"""Tests for test_distribution_artifact_privacy_runtime: algenta_core.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-1/tests/test_distribution_artifact_privacy_runtime.py during modularization.
"""
from __future__ import annotations

from tests._test_distribution_artifact_privacy_runtime_helpers import *  # noqa: F401,F403


def test_algenta_core_build_artifact_resolve_cloud_base_url_blocks_algenta_cloud_in_private_profiles():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "privacy_profile") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.resolve_cloud_base_url(
                explicit_base_url=None,
                component="artifact runtime",
                env={"ALGENTA_DEPLOYMENT_MODE": "air_gapped"},
            )

        assert (
            module.resolve_cloud_base_url(
                explicit_base_url="http://localhost:8000",
                component="artifact runtime",
                env={"ALGENTA_DEPLOYMENT_MODE": "air_gapped"},
            )
            == "http://localhost:8000"
        )
        assert (
            module.resolve_cloud_base_url(
                explicit_base_url=None,
                component="artifact runtime",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "air_gapped",
                    "ALGENTA_API_URL": "http://localhost:8000",
                },
            )
            == "http://localhost:8000"
        )


def test_algenta_core_build_artifact_runtime_api_mode_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "algenta", "runtime_facade") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.Runtime(mode="api", api_key="de_live_test")


def test_algenta_core_build_artifact_runtime_wrapper_api_mode_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "algenta", "runtime") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.Runtime(mode="api", api_key="de_live_test")


def test_algenta_core_build_artifact_package_root_runtime_export_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "algenta", "__init__") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.Runtime(mode="api", api_key="de_live_test")


def test_algenta_core_build_artifact_client_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "algenta", "client") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AlgentaClient(api_key="de_live_test")


def test_algenta_core_build_artifact_package_root_client_export_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "algenta", "__init__") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AlgentaClient(api_key="de_live_test")


def test_algenta_core_build_artifact_decision_cloud_mode_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "algenta", "decision") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.analyze(
                revenue=100000,
                mode="cloud",
                api_key="de_live_test",
            )


def test_algenta_core_build_artifact_forecast_cloud_mode_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "algenta", "forecast") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.predict(
                [1.0, 2.0, 3.0],
                mode="cloud",
                api_key="de_live_test",
            )


def test_algenta_core_build_artifact_simulate_cloud_mode_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "algenta", "simulate") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.risk(
                revenue=100000,
                mode="cloud",
                api_key="de_live_test",
            )


def test_algenta_core_build_artifact_runtime_local_mode_stays_offline(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    with _artifact_module(artifact_root, "algenta", "runtime_facade") as module:
        runtime = module.Runtime(mode="local")
        assert runtime._base_url == ""


def test_algenta_core_build_artifact_client_exposes_extended_public_surface():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "client") as module:
        client = module.AlgentaClient(api_key="de_live_test", base_url="http://localhost:8000")
        for name in (
            "me",
            "limits",
            "list_api_keys",
            "create_api_key",
            "revoke_api_key",
            "plan_decision",
            "recommend",
            "score",
            "batch",
            "compare",
            "get_contract",
            "get_runtime_manifest",
            "get_runtime_modules",
            "get_runtime_benchmarks",
            "get_runtime_release_validation",
            "resolve",
            "query",
            "query_with_metadata",
            "query_batch",
            "query_sql_report",
            "verify",
            "list_datasets",
            "get_dataset_summary",
            "list_deployment_regions",
            "get_deployment",
            "create_deployment",
            "delete_deployment",
            "get_deployment_cost",
            "list_models",
            "tokenize",
            "count_tokens",
            "chat_completions",
            "stream_chat_completions",
            "responses",
            "stream_responses",
            "embeddings",
            "embedding_similarity",
            "rerank",
            "create_agent_run",
            "get_agent_run",
            "get_agent_run_events",
            "stream_agent_run_events",
            "resume_agent_run",
            "cancel_agent_run",
            "approve_agent_run",
        ):
            assert hasattr(client, name), name


def test_algenta_core_build_artifact_runtime_exposes_account_and_proof_helpers():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "runtime_facade") as module:
        events: list[str] = []

        class _FakeSurface:
            @staticmethod
            def usage_runtime_request(runtime):
                events.append("usage")
                return {"quota_used_pct": 12}

            @staticmethod
            def limits_runtime_request(runtime):
                events.append("limits")
                return {"plan": "enterprise"}

            @staticmethod
            def contract_runtime_request(runtime):
                events.append("contract")
                return _artifact_contract_payload()

            @staticmethod
            def runtime_manifest_runtime_request(runtime):
                events.append("manifest")
                return {"runtime_version": "2026.05.0"}

            @staticmethod
            def runtime_modules_runtime_request(runtime):
                events.append("modules")
                return {"modules": []}

        module._runtime_execution_surface_module = lambda: _FakeSurface

        runtime = module.Runtime(mode="local")
        assert runtime.usage() == {"quota_used_pct": 12}
        assert runtime.limits() == {"plan": "enterprise"}
        contract = runtime.get_contract()
        assert contract["api_base_url"] == "https://api.algenta.ai"
        assert contract["mcp_endpoint"] == "https://api.algenta.ai/mcp/sse"
        assert contract["primary_data_query_contract"]["api"]["contract_endpoint"] == (
            "/v1/meta/contract"
        )
        assert_manifest_backed_integrations(contract["integrations"])
        assert runtime.get_runtime_manifest() == {"runtime_version": "2026.05.0"}
        assert runtime.get_runtime_modules() == {"modules": []}
        assert events == ["usage", "limits", "contract", "manifest", "modules"]


def test_algenta_core_build_artifact_runtime_exposes_repository_intelligence_helpers():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "runtime_facade") as module:
        events: list[tuple[str, str, object]] = []
        repository_models = importlib.import_module("algenta.runtime_model_repository_intelligence")
        decision_envelope_models = importlib.import_module("algenta.runtime_model_decision_envelope")

        artifact_payload = {
            "artifact_id": "artifact_snapshot_123",
            "artifact_kind": "RepositorySnapshot",
            "content_hash": "sha256:snapshot123",
            "storage_path": "artifacts/repository/snapshot.parquet",
            "schema_revision": "2026.05",
            "created_at": "2026-05-29T15:00:00+00:00",
        }
        decision_plan_payload = {
            "recommended_action": "patch_only",
            "confidence": 0.84,
            "expected_value": 1.0,
            "risk": {
                "p5": 0.1,
                "p95": 0.7,
                "probability_of_loss": 0.05,
                "var_95": 0.12,
            },
            "options": [
                {
                    "name": "patch_only",
                    "rank": 1,
                    "expected_value": 1.0,
                    "risk": {
                        "p5": 0.1,
                        "p95": 0.7,
                        "probability_of_loss": 0.05,
                        "var_95": 0.12,
                    },
                    "score": 0.91,
                }
            ],
            "rationale": "Repository evidence isolates the failure to one bounded patch.",
            "repository_analysis": {
                "root_cause": "Regression in dependency resolution after connector refactor.",
                "planner_model_id": "repo-fix-model",
                "planner_execution_mode": "provider_backed_chat",
                "planner_provider_backend": "openai",
                "candidate_fixes": ["restore previous revision pinning"],
                "impacted_services": ["api"],
                "impacted_symbols": ["resolve_repository_revision"],
                "likely_failing_tests": ["tests/test_repository_routes.py::test_triage"],
                "rollback_complexity": "low",
                "blast_radius": "bounded to repository ingestion",
                "workspace_evidence_refs": ["workspace_evidence_bundle:bundle_123"],
                "generated_patch_ref": "artifact://patch.diff",
                "patch_impact_report_ref": "artifact://patch-impact.parquet",
                "token_reduction_metrics": {
                    "raw_repo_token_estimate": 12000,
                    "evidence_bundle_token_count": 920,
                    "reduction_ratio": 0.0767,
                },
            },
        }

        class _FakeSurface:
            @staticmethod
            def create_repository_snapshot_runtime_request(runtime, repository_id, request):
                events.append(("snapshot", repository_id, request))
                return repository_models.RepositorySnapshotOutput.from_api(
                    {
                        "repository_id": repository_id,
                        "snapshot_id": "snapshot_123",
                        "connector_type": "local_repo",
                        "ref": "main",
                        "resolved_revision": "abc123",
                        "content_hash": "sha256:repo123",
                        "status": "ready",
                        "created_at": "2026-05-29T15:00:00+00:00",
                        "file_count": 12,
                        "language_counts": {"python": 12},
                        "raw_repo_token_estimate": 12000,
                        "repository_snapshot_artifact": artifact_payload,
                        "repository_graph_artifact": {
                            **artifact_payload,
                            "artifact_id": "artifact_graph_123",
                            "artifact_kind": "RepositoryGraph",
                        },
                        "symbol_graph_artifact": {
                            **artifact_payload,
                            "artifact_id": "artifact_symbol_123",
                            "artifact_kind": "SymbolGraph",
                        },
                        "dependency_graph_artifact": {
                            **artifact_payload,
                            "artifact_id": "artifact_dependency_123",
                            "artifact_kind": "DependencyGraph",
                        },
                    }
                )

            @staticmethod
            def get_repository_snapshot_runtime_request(runtime, repository_id, snapshot_id):
                events.append(("get_snapshot", repository_id, snapshot_id))
                return _FakeSurface.create_repository_snapshot_runtime_request(
                    runtime,
                    repository_id,
                    {"ref": "main"},
                )

            @staticmethod
            def triage_repository_runtime_request(runtime, repository_id, request):
                events.append(("triage", repository_id, request))
                return repository_models.RepositoryTriageOutput.from_api(
                    {
                        "repository_id": repository_id,
                        "snapshot_id": request["snapshot_id"],
                        "workspace_evidence_bundle_ref": "workspace_evidence_bundle:bundle_123",
                        "created_at": "2026-05-29T15:01:00+00:00",
                        "raw_repo_token_estimate": 12000,
                        "evidence_bundle_token_count": 920,
                        "reduction_ratio": 0.0767,
                        "evidence_items": [
                            {
                                "evidence_id": "evidence_123",
                                "rank": 1,
                                "source_type": "repository_file",
                                "source_ref": "src/repository/service.py",
                                "summary": "Repository revision pinning path changed in the failing branch.",
                                "snippet": "resolved_revision = normalize_repository_ref(ref)",
                                "token_count": 118,
                                "score": 0.94,
                                "file_path": "src/repository/service.py",
                                "symbol_name": "normalize_repository_ref",
                            }
                        ],
                        "workspace_evidence_bundle_artifact": {
                            **artifact_payload,
                            "artifact_id": "artifact_bundle_123",
                            "artifact_kind": "WorkspaceEvidenceBundle",
                        },
                        "suspect_files": ["src/repository/service.py"],
                        "suspect_symbols": ["normalize_repository_ref"],
                    }
                )

            @staticmethod
            def create_repository_decision_plan_runtime_request(runtime, repository_id, request):
                events.append(("decision_plan", repository_id, request))
                return repository_models.RepositoryDecisionPlanRevisionOutput.from_api(
                    {
                        "repository_id": repository_id,
                        "snapshot_id": request["snapshot_id"],
                        "decision_plan_id": "decision_plan_123",
                        "created_at": "2026-05-29T15:02:00+00:00",
                        "decision_plan": decision_plan_payload,
                    }
                )

            @staticmethod
            def simulate_repository_runtime_request(runtime, repository_id, request):
                events.append(("simulate", repository_id, request))
                return decision_envelope_models.DecisionEnvelopeOutput.from_api(
                    {
                        "run_id": "simulation_123",
                        "status": "completed",
                        "engine_version": "2026.05.0",
                        "recommended_action": "patch_only",
                        "confidence": 0.84,
                        "rationale": "Patch is bounded and the impact report stays below policy thresholds.",
                        "metrics": {
                            "expected_value": 0.91,
                            "median": 0.9,
                            "std_deviation": 0.05,
                            "variance": 0.0025,
                            "probability_of_loss": 0.04,
                            "var_95": 0.12,
                            "cvar_95": 0.15,
                        },
                        "percentiles": {
                            "p5": 0.78,
                            "p25": 0.86,
                            "p50": 0.9,
                            "p75": 0.94,
                            "p95": 0.98,
                            "p10": 0.82,
                            "p90": 0.96,
                        },
                        "scenarios_run": 512,
                        "execution_ms": 18,
                        "metadata": {
                            "mode": "monte_carlo",
                            "billing_units": 1,
                            "engine_version": "2026.05.0",
                            "seed": 7,
                        },
                        "simulation_model": "repository_patch_risk_v1",
                        "score": 0.84,
                        "score_breakdown": {"repository_blast_radius": 0.1},
                        "decision_plan": decision_plan_payload,
                    }
                )

            @staticmethod
            def apply_repository_runtime_request(runtime, repository_id, request):
                events.append(("apply", repository_id, request))
                return repository_models.RepositoryApplyOutput.from_api(
                    {
                        "repository_id": repository_id,
                        "snapshot_id": request["snapshot_id"],
                        "decision_plan_id": request["decision_plan_id"],
                        "simulation_id": request["simulation_id"],
                        "mode": request["mode"],
                        "applied": True,
                        "created_at": "2026-05-29T15:03:00+00:00",
                        "patch": "diff --git a/src/repository/service.py b/src/repository/service.py",
                        "apply_gate": {"status": "passed"},
                        "validation_summary": {
                            "targeted_tests": ["tests/test_repository_routes.py::test_triage"]
                        },
                        "branch_name": "codex/repository-intelligence",
                    }
                )

        module._runtime_execution_surface_module = lambda: _FakeSurface

        runtime = module.Runtime(mode="local")
        snapshot = runtime.create_repository_snapshot("repo_123", {"ref": "main"})
        fetched_snapshot = runtime.get_repository_snapshot("repo_123", "snapshot_123")
        triage = runtime.triage_repository("repo_123", {"snapshot_id": "snapshot_123"})
        plan_revision = runtime.create_repository_decision_plan(
            "repo_123",
            {
                "snapshot_id": "snapshot_123",
                "workspace_evidence_bundle_ref": "workspace_evidence_bundle:bundle_123",
            },
        )
        simulation = runtime.simulate_repository(
            "repo_123",
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
            },
        )
        applied = runtime.apply_repository(
            "repo_123",
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "simulation_123",
                "mode": "patch_only",
            },
        )

        assert snapshot.snapshot_id == "snapshot_123"
        assert fetched_snapshot.repository_graph_artifact.artifact_kind == "RepositoryGraph"
        assert triage.evidence_items[0].symbol_name == "normalize_repository_ref"
        assert (
            plan_revision.decision_plan.repository_analysis.planner_execution_mode
            == "provider_backed_chat"
        )
        assert (
            plan_revision.decision_plan.repository_analysis.patch_impact_report_ref
            == "artifact://patch-impact.parquet"
        )
        assert simulation.decision_plan.repository_analysis.planner_provider_backend == "openai"
        assert (
            simulation.decision_plan.repository_analysis.token_reduction_metrics.raw_repo_token_estimate
            == 12000
        )
        assert applied.apply_gate == {"status": "passed"}
        assert events == [
            ("snapshot", "repo_123", {"ref": "main"}),
            ("get_snapshot", "repo_123", "snapshot_123"),
            ("snapshot", "repo_123", {"ref": "main"}),
            ("triage", "repo_123", {"snapshot_id": "snapshot_123"}),
            (
                "decision_plan",
                "repo_123",
                {
                    "snapshot_id": "snapshot_123",
                    "workspace_evidence_bundle_ref": "workspace_evidence_bundle:bundle_123",
                },
            ),
            (
                "simulate",
                "repo_123",
                {"snapshot_id": "snapshot_123", "decision_plan_id": "decision_plan_123"},
            ),
            (
                "apply",
                "repo_123",
                {
                    "snapshot_id": "snapshot_123",
                    "decision_plan_id": "decision_plan_123",
                    "simulation_id": "simulation_123",
                    "mode": "patch_only",
                },
            ),
        ]


def test_algenta_core_build_artifact_runtime_error_exposes_nested_validation_details():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "__init__") as module:
        error = module.RuntimeValidationError(
            "invalid_release",
            "invalid release payload",
            details={
                "source_error_details": {
                    "validation_errors": [
                        {"path": "proof_matrix.0.status", "message": "must be valid"},
                    ]
                }
            },
        )
        assert error.validation_errors == [
            {"path": "proof_matrix.0.status", "message": "must be valid"},
        ]
        assert error.field_errors == error.validation_errors


def test_algenta_core_build_artifact_package_root_exposes_extended_contract_exports():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "__init__") as module:
        for name in (
            "UsageOutput",
            "QueryFilterCondition",
            "DecisionPlanOutput",
            "RepositoryAnalysisOutput",
            "DecisionEnvelopeOutput",
            "RepositorySnapshotOutput",
            "DeploymentCostOutput",
            "LLMModelOutput",
            "AgentRunOutput",
            "PlatformContractOutput",
            "RuntimeManifestOutput",
            "CONTRACT_VERSION",
            "MCP_ENDPOINT",
            "INTEGRATIONS",
        ):
            assert name in module.__all__
            assert getattr(module, name) is not None
        assert_manifest_backed_integrations(module.INTEGRATIONS)


def test_algenta_core_build_artifact_package_root_matches_source_contract_inventory():
    artifact_root = ROOT / "packages/algenta/build/lib"
    source_root = ROOT / "packages/algenta"
    with _artifact_module(artifact_root, "algenta", "__init__") as artifact_module:
        with _artifact_module(source_root, "algenta", "__init__") as source_module:
            _assert_artifact_contract_inventory_matches_source(artifact_module, source_module)


def test_algenta_core_build_artifact_contract_module_matches_manifest_inventory():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "_contract") as module:
        assert module.DEFAULT_BASE_URL == "https://api.algenta.ai"
        assert module.MCP_ENDPOINT == "https://api.algenta.ai/mcp/sse"
        assert module.PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"] == (
            "/v1/meta/contract"
        )
        assert_manifest_backed_integrations(module.INTEGRATIONS)


def test_algenta_core_build_artifact_contract_module_matches_source_contract_inventory():
    artifact_root = ROOT / "packages/algenta/build/lib"
    source_root = ROOT / "packages/algenta"
    with _artifact_module(artifact_root, "algenta", "_contract") as artifact_module:
        with _artifact_module(source_root, "algenta", "_contract") as source_module:
            _assert_artifact_contract_inventory_matches_source(artifact_module, source_module)


def test_algenta_core_build_artifact_resolved_plan_models_expose_filter_contract_types():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "runtime_model_resolved_plan") as module:
        condition = module.QueryFilterCondition(
            column="region",
            op="in",
            values=("United States", "Canada"),
        )
        spec = module.QueryFilterSpec(conditions=(condition,))

        assert condition.to_dict() == {
            "column": "region",
            "op": "in",
            "values": ["United States", "Canada"],
        }
        assert spec.to_dict() == {
            "conditions": [
                {
                    "column": "region",
                    "op": "in",
                    "values": ["United States", "Canada"],
                }
            ]
        }


def test_algenta_core_build_artifact_privacy_profile_exposes_dashboard_resolution():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "privacy_profile") as module:
        with pytest.raises(ValueError, match="explicit self-hosted dashboard or API base_url"):
            module.resolve_dashboard_url(
                component="artifact runtime",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "air_gapped",
                },
            )
        assert (
            module.resolve_dashboard_url(
                component="artifact runtime",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                    "ALGENTA_BASE_URL": "https://control.customer.internal",
                },
            )
            == "https://control.customer.internal/dashboard"
        )
        assert (
            module.resolve_dashboard_url(
                component="artifact runtime",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                    "DE_APP_BASE_URL": "https://console.customer.internal",
                },
            )
            == "https://console.customer.internal/dashboard"
        )
        with pytest.raises(
            ValueError,
            match="ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a self-hosted base_url",
        ):
            module.resolve_dashboard_url(
                component="artifact runtime",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                    "ALGENTA_APP_BASE_URL": "https://app.algenta.ai",
                },
            )


def test_algenta_core_build_artifact_local_execution_exports_filter_and_plan_helpers():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "runtime_local_execution") as module:
        condition = module.LocalFilterCondition(column="status", op="eq", value="closed")
        result = module.LocalExecutionResult(value=123, result_type="scalar", row_count=1)

        assert condition.column == "status"
        assert condition.op == "eq"
        assert condition.values == ()
        assert result.plan_steps == ()


def test_algenta_core_build_artifact_runtime_models_root_exposes_account_and_decision_exports():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "runtime_models") as module:
        for name in (
            "UsageOutput",
            "DecisionPlanOutput",
            "RepositoryAnalysisOutput",
            "DecisionEnvelopeOutput",
            "RepositorySnapshotOutput",
            "LLMModelOutput",
            "ImportPreview",
        ):
            assert name in module.__all__
            assert getattr(module, name) is not None


def test_algenta_core_build_artifact_runtime_local_limits_disable_hosted_limits_in_private_profiles(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/algenta/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    with _artifact_module(artifact_root, "algenta", "runtime_local_limits") as module:
        assert module.uses_hosted_local_limits(mode="local", enforce_limits=True) is False
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    with _artifact_module(artifact_root, "algenta", "runtime_local_limits") as module:
        assert module.uses_hosted_local_limits(mode="local", enforce_limits=True) is False


def test_algenta_core_build_artifact_demo_exports_scenarios():
    artifact_root = ROOT / "packages/algenta/build/lib"
    with _artifact_module(artifact_root, "algenta", "demo") as module:
        scenario = module.DemoScenario(
            key="top_products",
            title="Top products",
            summary="Checks ranked output.",
            request={"source_name": "demo_orders", "metric": "revenue"},
        )
        assert scenario.expect_query is True


