"""Tests for test_runtime_surface_compatibility: misc_c.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-4/tests/test_runtime_surface_compatibility.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_surface_compatibility_helpers import *  # noqa: F401,F403


def test_runtime_benchmark_surfaces_lock_provider_routing_overhead_class() -> None:
    runtime_manifest_tests = (ROOT / "tests" / "test_runtime_manifest.py").read_text(
        encoding="utf-8"
    )
    algenta_runtime_tests = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "tests").glob("*algenta_runtime*.py"))
    )
    decision_engine_query_tests = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "tests").glob("*test_decision_engine_query_surface*.py"))
    )
    package_surface_tests = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(
            (ROOT / "tests").glob("*test_package_distribution_surface*.py")
        )
    )
    runtime_manifest_model_validation = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "tests").glob("test_runtime_manifest_model_validation_*.py"))
    )
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


def test_cli_legacy_harness_and_status_doc_mark_canonical_cli_path_truthfully() -> None:
    cli_full = (ROOT / "tests" / "integration" / "test_cli_full.py").read_text(encoding="utf-8")
    status_doc = (ROOT / "platform_contract_v1_2_status.md").read_text(encoding="utf-8")

    assert "Legacy supplemental CLI harness" in cli_full
    assert "The canonical live CLI proof path is test_cli.py." in cli_full
    assert "Complements test_cli.py which covers: health, version, simulate, keys list." not in cli_full
    assert "historical at that time: `DE_SKIP_API=1 python3 tests/integration/test_cli_full.py`" in status_doc
    assert "current canonical live CLI proof: `python3 tests/integration/test_cli.py`" in status_doc


