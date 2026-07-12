"""Tests for test_distribution_artifact_privacy_runtime: python_sdk.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-1/tests/test_distribution_artifact_privacy_runtime.py during modularization.
"""
from __future__ import annotations

from tests._test_distribution_artifact_privacy_runtime_helpers import *  # noqa: F401,F403


def test_python_sdk_build_artifact_resolve_client_base_url_blocks_algenta_cloud_in_private_profiles():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "privacy_profile") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.resolve_client_base_url(
                explicit_base_url=None,
                component="artifact client",
                env={"ALGENTA_DEPLOYMENT_MODE": "self_hosted"},
            )

        assert (
            module.resolve_client_base_url(
                explicit_base_url="http://localhost:8000",
                component="artifact client",
                env={"ALGENTA_DEPLOYMENT_MODE": "self_hosted"},
            )
            == "http://localhost:8000"
        )
        assert (
            module.resolve_client_base_url(
                explicit_base_url=None,
                component="artifact client",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                    "ALGENTA_API_URL": "http://localhost:8000",
                },
            )
            == "http://localhost:8000"
        )


def test_python_sdk_build_artifact_client_fails_closed_without_private_base_url(monkeypatch: pytest.MonkeyPatch):
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "decision_engine", "client_facade") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.DecisionEngineClient(api_key="de_live_test")


def test_python_sdk_build_artifact_client_wrapper_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "decision_engine", "client") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.DecisionEngineClient(api_key="de_live_test")


def test_python_sdk_build_artifact_package_root_client_exports_fail_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "decision_engine", "__init__") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AlgentaClient(api_key="de_live_test")
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.DecisionEngineClient(api_key="de_live_test")


def test_python_sdk_build_artifact_async_client_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "decision_engine", "async_client_facade") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AsyncDecisionEngineClient(api_key="de_live_test")


def test_python_sdk_build_artifact_async_client_wrapper_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "decision_engine", "async_client") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AsyncDecisionEngineClient(api_key="de_live_test")


def test_python_sdk_build_artifact_package_root_async_client_exports_fail_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    with _artifact_module(artifact_root, "decision_engine", "__init__") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AsyncAlgentaClient(api_key="de_live_test")
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AsyncDecisionEngineClient(api_key="de_live_test")


def test_python_sdk_build_artifact_clients_expose_extended_public_surface():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "client_facade") as module:
        client = module.DecisionEngineClient(api_key="de_live_test", base_url="http://localhost:8000")
        for name in (
            "plan_decision",
            "create_repository_snapshot",
            "get_repository_snapshot",
            "triage_repository",
            "create_repository_decision_plan",
            "simulate_repository",
            "apply_repository",
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
            "get_contract",
            "get_runtime_manifest",
            "get_runtime_modules",
            "get_runtime_benchmarks",
            "get_runtime_release_validation",
            "create_agent_run",
            "get_agent_run",
            "get_agent_run_events",
            "stream_agent_run_events",
            "resume_agent_run",
            "cancel_agent_run",
            "approve_agent_run",
            "list_deployment_regions",
            "get_deployment",
            "create_deployment",
            "delete_deployment",
            "get_deployment_cost",
        ):
            assert hasattr(client, name), name

    with _artifact_module(artifact_root, "decision_engine", "async_client_facade") as module:
        client = module.AsyncDecisionEngineClient(
            api_key="de_live_test",
            base_url="http://localhost:8000",
        )
        for name in (
            "plan_decision",
            "create_repository_snapshot",
            "get_repository_snapshot",
            "triage_repository",
            "create_repository_decision_plan",
            "simulate_repository",
            "apply_repository",
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
            "get_contract",
            "get_runtime_manifest",
            "get_runtime_modules",
            "get_runtime_benchmarks",
            "get_runtime_release_validation",
            "create_agent_run",
            "get_agent_run",
            "get_agent_run_events",
            "stream_agent_run_events",
            "resume_agent_run",
            "cancel_agent_run",
            "approve_agent_run",
            "list_deployment_regions",
            "get_deployment",
            "create_deployment",
            "delete_deployment",
            "get_deployment_cost",
        ):
            assert hasattr(client, name), name


def test_python_sdk_build_artifact_repository_surfaces_validate_repository_models():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
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
    snapshot_payload = {
        "repository_id": "repo_123",
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
    triage_payload = {
        "repository_id": "repo_123",
        "snapshot_id": "snapshot_123",
        "workspace_evidence_bundle_ref": "workspace_evidence_bundle:bundle_123",
        "created_at": "2026-05-29T15:01:00+00:00",
        "suspect_files": ["src/repository/service.py"],
        "suspect_symbols": ["resolve_repository_revision"],
        "raw_repo_token_estimate": 12000,
        "evidence_bundle_token_count": 920,
        "reduction_ratio": 0.0767,
        "evidence_items": [
            {
                "evidence_id": "evidence_123",
                "rank": 1,
                "source_type": "repository_file",
                "source_ref": "src/repository/service.py",
                "file_path": "src/repository/service.py",
                "symbol_name": "resolve_repository_revision",
                "summary": "Repository revision pinning path changed in the failing branch.",
                "snippet": "resolved_revision = normalize_repository_ref(ref)",
                "token_count": 118,
                "score": 0.94,
            }
        ],
        "workspace_evidence_bundle_artifact": {
            **artifact_payload,
            "artifact_id": "artifact_bundle_123",
            "artifact_kind": "WorkspaceEvidenceBundle",
        },
    }
    plan_revision_payload = {
        "repository_id": "repo_123",
        "snapshot_id": "snapshot_123",
        "decision_plan_id": "decision_plan_123",
        "created_at": "2026-05-29T15:02:00+00:00",
        "decision_plan": decision_plan_payload,
    }
    simulation_payload = {
        "run_id": "00000000-0000-0000-0000-000000000123",
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
        },
        "percentiles": {
            "p5": 0.78,
            "p25": 0.86,
            "p50": 0.9,
            "p75": 0.94,
            "p95": 0.98,
        },
        "scenarios_run": 512,
        "execution_ms": 18,
        "metadata": {
            "mode": "monte_carlo",
            "billing_units": 1,
            "engine_version": "2026.05.0",
            "seed": 7,
        },
        "score": 0.84,
        "score_breakdown": {"repository_blast_radius": 0.1},
        "decision_plan": decision_plan_payload,
    }
    apply_payload = {
        "repository_id": "repo_123",
        "snapshot_id": "snapshot_123",
        "decision_plan_id": "decision_plan_123",
        "simulation_id": "00000000-0000-0000-0000-000000000123",
        "mode": "patch_only",
        "applied": True,
        "created_at": "2026-05-29T15:03:00+00:00",
        "patch": "diff --git a/src/repository/service.py b/src/repository/service.py",
        "branch_name": "codex/repository-intelligence",
        "apply_gate": {"status": "passed"},
        "validation_summary": {"targeted_tests": ["tests/test_repository_routes.py::test_triage"]},
    }

    with _artifact_module(artifact_root, "decision_engine", "client_repository_surface") as module:
        calls: list[tuple[str, str, object | None]] = []

        class _FakeClient:
            def _request(self, method: str, path: str, json: object | None = None):
                calls.append((method, path, json))
                payloads = {
                    ("POST", "/v1/repositories/repo_123/snapshots"): snapshot_payload,
                    ("GET", "/v1/repositories/repo_123/snapshots/snapshot_123"): snapshot_payload,
                    ("POST", "/v1/repositories/repo_123/triage"): triage_payload,
                    ("POST", "/v1/repositories/repo_123/decision-plans"): plan_revision_payload,
                    ("POST", "/v1/repositories/repo_123/simulate"): simulation_payload,
                    ("POST", "/v1/repositories/repo_123/apply"): apply_payload,
                }
                return payloads[(method, path)]

        client = _FakeClient()
        snapshot = module.create_repository_snapshot(client, "repo_123", {"ref": "main"})
        fetched = module.get_repository_snapshot(client, "repo_123", "snapshot_123")
        triage = module.triage_repository(client, "repo_123", {"snapshot_id": "snapshot_123"})
        plan = module.create_repository_decision_plan(
            client,
            "repo_123",
            {"snapshot_id": "snapshot_123"},
        )
        simulation = module.simulate_repository(
            client,
            "repo_123",
            {"snapshot_id": "snapshot_123", "decision_plan_id": "decision_plan_123"},
        )
        apply_result = module.apply_repository(
            client,
            "repo_123",
            {
                "snapshot_id": "snapshot_123",
                "decision_plan_id": "decision_plan_123",
                "simulation_id": "00000000-0000-0000-0000-000000000123",
                "mode": "patch_only",
            },
        )

        assert snapshot.snapshot_id == "snapshot_123"
        assert fetched.repository_graph_artifact.artifact_kind == "RepositoryGraph"
        assert triage.evidence_items[0].symbol_name == "resolve_repository_revision"
        assert plan.decision_plan.repository_analysis.planner_model_id == "repo-fix-model"
        assert plan.decision_plan.repository_analysis.patch_impact_report_ref == (
            "artifact://patch-impact.parquet"
        )
        assert simulation.decision_plan.repository_analysis.planner_provider_backend == "openai"
        assert simulation.decision_plan.repository_analysis.root_cause.startswith("Regression")
        assert apply_result.apply_gate == {"status": "passed"}
        assert calls == [
            ("POST", "/v1/repositories/repo_123/snapshots", {"ref": "main"}),
            ("GET", "/v1/repositories/repo_123/snapshots/snapshot_123", None),
            ("POST", "/v1/repositories/repo_123/triage", {"snapshot_id": "snapshot_123"}),
            ("POST", "/v1/repositories/repo_123/decision-plans", {"snapshot_id": "snapshot_123"}),
            (
                "POST",
                "/v1/repositories/repo_123/simulate",
                {"snapshot_id": "snapshot_123", "decision_plan_id": "decision_plan_123"},
            ),
            (
                "POST",
                "/v1/repositories/repo_123/apply",
                {
                    "snapshot_id": "snapshot_123",
                    "decision_plan_id": "decision_plan_123",
                    "simulation_id": "00000000-0000-0000-0000-000000000123",
                    "mode": "patch_only",
                },
            ),
        ]

    with _artifact_module(artifact_root, "decision_engine", "async_client_repository_surface") as module:
        calls: list[tuple[str, str, object | None]] = []

        class _FakeAsyncClient:
            async def _request(self, method: str, path: str, json: object | None = None):
                calls.append((method, path, json))
                payloads = {
                    ("POST", "/v1/repositories/repo_123/snapshots"): snapshot_payload,
                    ("GET", "/v1/repositories/repo_123/snapshots/snapshot_123"): snapshot_payload,
                    ("POST", "/v1/repositories/repo_123/triage"): triage_payload,
                    ("POST", "/v1/repositories/repo_123/decision-plans"): plan_revision_payload,
                    ("POST", "/v1/repositories/repo_123/simulate"): simulation_payload,
                    ("POST", "/v1/repositories/repo_123/apply"): apply_payload,
                }
                return payloads[(method, path)]

        client = _FakeAsyncClient()
        snapshot = asyncio.run(module.create_repository_snapshot(client, "repo_123", {"ref": "main"}))
        triage = asyncio.run(
            module.triage_repository(client, "repo_123", {"snapshot_id": "snapshot_123"})
        )
        apply_result = asyncio.run(
            module.apply_repository(
                client,
                "repo_123",
                {
                    "snapshot_id": "snapshot_123",
                    "decision_plan_id": "decision_plan_123",
                    "simulation_id": "00000000-0000-0000-0000-000000000123",
                    "mode": "patch_only",
                },
            )
        )

        assert snapshot.symbol_graph_artifact.artifact_kind == "SymbolGraph"
        assert triage.workspace_evidence_bundle_artifact.artifact_kind == "WorkspaceEvidenceBundle"
        assert apply_result.branch_name == "codex/repository-intelligence"
        assert calls[0] == ("POST", "/v1/repositories/repo_123/snapshots", {"ref": "main"})


def test_python_sdk_build_artifact_error_exposes_nested_validation_details():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "__init__") as module:
        error = module.ValidationError(
            "invalid payload",
            status_code=422,
            response_body={
                "error": {
                    "code": "validation_failed",
                    "details": {
                        "validation_errors": [
                            {"path": "query.metric", "message": "is required"},
                        ]
                    },
                }
            },
        )
        assert error.details == {
            "validation_errors": [
                {"path": "query.metric", "message": "is required"},
            ]
        }
        assert error.validation_errors == [
            {"path": "query.metric", "message": "is required"},
        ]
        assert error.field_errors == error.validation_errors


def test_python_sdk_build_artifact_package_root_exposes_extended_contract_exports():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "__init__") as module:
        for name in (
            "DecisionPlanResult",
            "RepositorySnapshotResult",
            "DeploymentCostResult",
            "AgentRunResult",
            "LLMModelListResult",
            "PlatformContractResult",
            "RuntimeManifestResult",
            "QueryFilterCondition",
            "QueryFilterSpec",
            "CONTRACT_VERSION",
            "MCP_ENDPOINT",
            "INTEGRATIONS",
        ):
            assert name in module.__all__
            assert getattr(module, name) is not None
        assert_manifest_backed_integrations(module.INTEGRATIONS)


def test_python_sdk_build_artifact_package_root_matches_source_contract_inventory():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    source_root = ROOT / "packages/python-sdk"
    with _artifact_module(artifact_root, "decision_engine", "__init__") as artifact_module:
        with _artifact_module(source_root, "decision_engine", "__init__") as source_module:
            _assert_artifact_contract_inventory_matches_source(artifact_module, source_module)


def test_python_sdk_build_artifact_contract_module_matches_manifest_inventory():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "_contract") as module:
        assert module.DEFAULT_BASE_URL == "https://api.algenta.ai"
        assert module.MCP_ENDPOINT == "https://api.algenta.ai/mcp"
        assert module.PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"] == (
            "/v1/meta/contract"
        )
        assert_manifest_backed_integrations(module.INTEGRATIONS)


def test_python_sdk_build_artifact_contract_module_matches_source_contract_inventory():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    source_root = ROOT / "packages/python-sdk"
    with _artifact_module(artifact_root, "decision_engine", "_contract") as artifact_module:
        with _artifact_module(source_root, "decision_engine", "_contract") as source_module:
            _assert_artifact_contract_inventory_matches_source(artifact_module, source_module)


def test_python_sdk_build_artifact_resolve_models_expose_filter_contract_types():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "models_resolve_result") as module:
        condition = module.QueryFilterCondition(
            dimension_hint="region",
            op="in",
            values=["United States", "Canada"],
        )
        spec = module.QueryFilterSpec(conditions=[condition])

        assert condition.dimension_hint == "region"
        assert condition.values == ["United States", "Canada"]
        assert spec.conditions[0].op == "in"


def test_python_sdk_build_artifact_source_registration_model_exposes_row_count():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "models_registration_result") as module:
        result = module.SourceRegistrationResult(
            status="ready",
            dataset_id="ds_123",
            row_count=42,
        )
        assert result.row_count == 42


def test_python_sdk_build_artifact_account_surface_normalizes_naive_expiry_to_utc():
    artifact_root = ROOT / "packages/python-sdk/build/lib"

    class _FakeClient:
        def __init__(self) -> None:
            self.seen: dict[str, object] | None = None

        def _request(self, method: str, path: str, json: dict[str, object] | None = None):
            self.seen = {"method": method, "path": path, "json": json}
            return {
                "id": "key_123",
                "key_prefix": "de_live_key_123",
                "raw_key": "de_live_key_123_secret",
            }

    with _artifact_module(artifact_root, "decision_engine", "client_account_surface") as module:
        client = _FakeClient()
        created = module.create_api_key(
            client,
            label="artifact-key",
            expires_at=datetime(2028, 5, 19, 0, 0, 0),
        )
        assert client.seen == {
            "method": "POST",
            "path": "/v1/api-keys",
            "json": {
                "label": "artifact-key",
                "expires_at": "2028-05-19T00:00:00+00:00",
            },
        }
        assert created["raw_key"] == "de_live_key_123_secret"


def test_python_sdk_build_artifact_async_account_surface_normalizes_naive_expiry_to_utc():
    artifact_root = ROOT / "packages/python-sdk/build/lib"

    class _FakeAsyncClient:
        def __init__(self) -> None:
            self.seen: dict[str, object] | None = None

        async def _request(self, method: str, path: str, json: dict[str, object] | None = None):
            self.seen = {"method": method, "path": path, "json": json}
            return {
                "id": "key_123",
                "key_prefix": "de_live_key_123",
                "raw_key": "de_live_key_123_secret",
            }

    with _artifact_module(artifact_root, "decision_engine", "async_client_account_surface") as module:
        client = _FakeAsyncClient()
        created = asyncio.run(
            module.create_api_key(
                client,
                label="artifact-key",
                expires_at=datetime(2028, 5, 19, 0, 0, 0),
            )
        )
        assert client.seen == {
            "method": "POST",
            "path": "/v1/api-keys",
            "json": {
                "label": "artifact-key",
                "expires_at": "2028-05-19T00:00:00+00:00",
            },
        }
        assert created["raw_key"] == "de_live_key_123_secret"


def test_python_sdk_build_artifact_connector_surface_connect_data_uses_canonical_payload():
    artifact_root = ROOT / "packages/python-sdk/build/lib"

    class _FakeClient:
        def __init__(self) -> None:
            self.seen: dict[str, object] | None = None

        def _request(self, method: str, path: str, json: dict[str, object] | None = None):
            self.seen = {"method": method, "path": path, "json": json}
            return {
                "dataset_id": "ds_123",
                "status": "ready",
            }

    with _artifact_module(artifact_root, "decision_engine", "client_connector_surface") as module:
        client = _FakeClient()
        result = module.connect_data(
            client,
            {"dataset_name": "orders", "connector_id": "conn_123"},
            description=None,
            visibility="private",
        )
        assert client.seen == {
            "method": "POST",
            "path": "/v1/data/connect",
            "json": {
                "dataset_name": "orders",
                "connector_id": "conn_123",
                "visibility": "private",
            },
        }
        assert result.dataset_id == "ds_123"


def test_python_sdk_build_artifact_models_root_exposes_contract_and_llm_exports():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "models") as module:
        for name in (
            "PlatformContractResult",
            "LLMModelListResult",
            "RuntimeManifestResult",
            "AgentRunResult",
            "RepositorySnapshotResult",
        ):
            assert name in module.__all__
            assert getattr(module, name) is not None


def test_python_sdk_build_artifact_privacy_profile_requires_explicit_console_or_api_origin():
    artifact_root = ROOT / "packages/python-sdk/build/lib"
    with _artifact_module(artifact_root, "decision_engine", "privacy_profile") as module:
        with pytest.raises(ValueError, match="explicit self-hosted dashboard or API base_url"):
            module.resolve_console_base_url(
                component="artifact client",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                },
            )
        assert (
            module.resolve_console_base_url(
                component="artifact client",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "air_gapped",
                    "DE_APP_BASE_URL": "https://console.customer.internal",
                },
            )
            == "https://console.customer.internal"
        )
        with pytest.raises(
            ValueError,
            match="ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a self-hosted base_url",
        ):
            module.resolve_console_base_url(
                component="artifact client",
                env={
                    "ALGENTA_DEPLOYMENT_MODE": "self_hosted",
                    "ALGENTA_APP_BASE_URL": "https://app.algenta.ai",
                },
            )


