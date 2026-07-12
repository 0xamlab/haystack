from __future__ import annotations

import json
from pathlib import Path

from benchmarks import scorecard_sync

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_render_mcp_runtime_integration_row_includes_skipped_when_present() -> None:
    row = scorecard_sync.render_mcp_runtime_integration_row(
        {
            "passed": 36,
            "failed": 0,
            "skipped": 3,
            "total": 39,
            "details": {
                "runtime_proof_tool_count": 5,
                "expected_tool_count": 25,
            },
        }
    )

    assert row == (
        "| MCP runtime integration | 36/39 live MCP boundary tests passed; 5 runtime proof "
        "tools present, 25 tools expected overall, 3 skipped | "
        "`build/mcp_server_integration_summary.json`, `tests/integration/test_mcp_server.py` | "
        "Green |"
    )


def test_render_openapi_compliance_row_includes_skipped_when_present() -> None:
    row = scorecard_sync.render_openapi_compliance_row(
        {
            "passed": 64,
            "failed": 0,
            "skipped": 7,
            "total": 71,
            "details": {
                "path_count": 114,
                "schema_count": 293,
                "security_schemes": ["BearerAuth", "LegacyApiKey"],
            },
        }
    )

    assert row == (
        "| OpenAPI compliance | 64/71 compliance checks passed; 114 paths, 293 schemas, "
        "security BearerAuth, LegacyApiKey, 7 skipped | "
        "`build/openapi_integration_summary.json`, `tests/integration/test_openapi.py` | "
        "Green |"
    )


def test_render_provider_routing_overhead_row_uses_p50_latency_and_attempts() -> None:
    row = scorecard_sync.render_provider_routing_overhead_row(
        {
            "chat": {
                "baseline": {"p50_us": 4.625},
                "single_hop_router": {"p50_us": 7.708},
                "nested_router": {"p50_us": 12.542},
                "retryable_failover_router": {
                    "p50_us": 13.875,
                    "mean_provider_attempts": 2.0,
                },
            },
            "embeddings": {
                "baseline": {"p50_us": 4.584},
                "single_hop_router": {"p50_us": 7.584},
                "nested_router": {"p50_us": 15.333},
                "retryable_failover_router": {
                    "p50_us": 14.792,
                    "mean_provider_attempts": 2.0,
                },
            },
        }
    )

    assert row == (
        "| Provider routing overhead | p50 in-process routed latency (chat/embed) direct "
        "4.62/4.58 us, single 7.71/7.58 us, nested 12.54/15.33 us, failover 13.88/14.79 us; "
        "failover mean provider attempts 2.0/2.0 | "
        "`build/provider_routing_overhead_benchmark.json`, "
        "`benchmarks/provider_routing_overhead_benchmark.py`, "
        "`tests/test_provider_routing_overhead_benchmark.py` | Green |"
    )


def test_sync_shared_benchmark_scorecard_rewrites_dynamic_rows(tmp_path: Path) -> None:
    scorecard_path = tmp_path / "scorecard.md"
    benchmark_summary_path = tmp_path / "summary.json"
    mojo_az_summary_path = tmp_path / "mojo_libraries_az_summary.json"
    go_live_verify_summary_path = tmp_path / "go_live_verify_summary.json"
    go_live_full_real_summary_path = tmp_path / "go_live_full_real_summary.json"
    llm_rollout_proof_bundle_path = tmp_path / "llm_rollout_proof_bundle.json"
    provider_routing_overhead_benchmark_path = tmp_path / "provider_routing_overhead_benchmark.json"
    repository_intelligence_benchmark_path = tmp_path / "repository_intelligence_benchmark.json"
    mcp_20q_results_path = tmp_path / "claude_mcp_20q_results.json"
    mcp_server_integration_summary_path = tmp_path / "mcp_server_integration_summary.json"
    openapi_integration_summary_path = tmp_path / "openapi_integration_summary.json"
    csv_pipeline_results_path = tmp_path / "csv_pipeline_results.csv"
    csv_pipeline_summary_path = tmp_path / "csv_pipeline_summary.json"
    scorecard_suite_summaries_path = tmp_path / "scorecard_suite_summaries.json"
    vector_hot_path_results_path = tmp_path / "engines_prefilter_vs_fullscan.json"

    scorecard_path.write_text(
        "# Decision Engine Scorecard\n\n"
        "Updated: 2026-05-01\n\n"
        "## Current measured state\n\n"
        "| Area | Current | Evidence | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| Mojo correctness (A-Z) | stale | stale | Green |\n"
        "| Narrow resolver regression | stale | stale | Yellow |\n"
        "| Join-path correctness | stale | stale | Green |\n"
        "| Import pipeline correctness | stale | stale | Green |\n"
        "| Import/planner regression suite | stale | stale | Green |\n"
        "| Mojo vs Python speed | stale | stale | Green |\n"
        "| Provider routing overhead | stale | stale | Green |\n"
        "| Repository intelligence workflow | stale | stale | Green |\n"
        "| MCP runtime integration | stale | stale | Green |\n"
        "| OpenAPI compliance | stale | stale | Green |\n"
        "| MCP end-to-end benchmark | stale | stale | Yellow |\n"
        "| CSV ingest throughput | stale | stale | Green |\n"
        "| Vector hot path | stale | stale | Green |\n"
        "| Resolver accuracy (universal) | Not measured yet | none | Red |\n"
        "## Go-live verifier (2026-05-01)\n\n"
        "| Area | Current | Evidence | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| Serial verifier summary | stale | stale | Green |\n"
        "| Full real suite | stale | stale | Green |\n"
        "| Planned serial steps | stale | stale | Green |\n"
        "| Latest serial durations | stale | stale | Green |\n"
        "| Canonical verifier mode | stale | stale | Green |\n"
        "| Static matrix operational gaps | stale | stale | Amber |\n"
        "| Live connectivity skips | stale | stale | Amber |\n"
        "| Gap source breakdown | stale | stale | Amber |\n"
        "| Gap connector breakdown | stale | stale | Amber |\n"
        "| Outstanding operational gaps | stale | stale | Amber |\n"
        "| Operator next actions | stale | stale | Amber |\n"
        "| Gap action routing | stale | stale | Amber |\n"
        "| Gap connector routing | stale | stale | Amber |\n"
        "| Gap env routing | stale | stale | Amber |\n"
        "| Gap env resolution | stale | stale | Amber |\n"
        "| Gap env templates | stale | stale | Green |\n"
        "## LLM rollout proof (2026-05-01)\n\n"
        "| Area | Current | Evidence | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| 22-library parity proof | stale | stale | Green |\n"
        "| Compiled runtime latency proof | stale | stale | Green |\n"
        "| Serving extension subset proof | stale | stale | Green |\n"
        "| Serving extension channel coverage | stale | stale | Green |\n"
        "| Supported channel coverage | stale | stale | Green |\n"
        "| SDK package contract coverage | stale | stale | Green |\n"
        "| HTTP API flag contract coverage | stale | stale | Green |\n"
        "| HTTP API flag live coverage | stale | stale | Green |\n"
        "| Public HTTP API flag readiness | stale | stale | Green |\n"
        "| Machine-readable rollout bundle | stale | stale | Green |\n",
        encoding="utf-8",
    )
    benchmark_summary_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-23T14:43:51",
                "benchmark_inventory": {
                    "total_libraries": 463,
                    "top_level_library_count": 410,
                    "nested_library_count": 53,
                },
                "shipping_runtime_contract": {
                    "module_count": 22,
                    "function_count": 209,
                },
                "median_speedup_x": 112.95,
                "mean_speedup_x": 182.42,
                "max_speedup_x": 3828.48,
                "min_speedup_x": 0.36,
                "total_functions_compared": 4168,
            }
        ),
        encoding="utf-8",
    )
    mojo_az_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-23T19:06:23Z",
                "library_count": 244,
                "passed_library_count": 244,
                "failed_library_count": 0,
                "function_count": 2414,
                "passed_function_count": 2414,
                "failed_function_count": 0,
                "suite_duration_s": 57.8,
            }
        ),
        encoding="utf-8",
    )
    go_live_verify_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-22T14:15:34Z",
                "completed_steps": ["connectivity", "full_real"],
                "failed_steps": [],
                "planned_steps": [{"name": "connectivity"}, {"name": "full_real"}],
                "step_results": [
                    {"name": "connectivity", "duration_s": 21.847},
                    {"name": "full_real", "duration_s": 204.368},
                ],
                "filters": [],
                "options": {
                    "strict": False,
                    "include_full_real": True,
                    "include_pytest": False,
                },
                "matrix_summary": {
                    "configured_cases": 8,
                    "behavior_ready_cases": 8,
                    "total_cases": 19,
                },
                "gap_source_summary": {
                    "static_gap_count": 11,
                    "live_skip_count": 12,
                    "merged_gap_count": 12,
                    "static_gap_counts_by_tier": {
                        "credentialed_example": 2,
                        "customer_credentials_required": 8,
                        "public_no_auth": 1,
                    },
                    "live_skip_counts_by_tier": {
                        "credentialed_example": 2,
                        "customer_credentials_required": 9,
                        "public_no_auth": 1,
                    },
                    "merged_gap_counts_by_source": {
                        "live_connectivity": 1,
                        "static_matrix+live_connectivity": 11,
                    },
                    "merged_gap_counts_by_connector_type": {
                        "azure_blob": 1,
                        "bigquery": 1,
                        "clickhouse": 1,
                        "elasticsearch": 1,
                        "gcs": 1,
                        "neo4j": 1,
                        "redis": 1,
                        "rest_api": 3,
                        "s3": 1,
                        "snowflake": 1,
                    },
                    "merged_gap_counts_by_tier": {
                        "credentialed_example": 2,
                        "customer_credentials_required": 9,
                        "public_no_auth": 1,
                    },
                },
                "next_actions": [{}, {}, {}, {}, {}],
                "gap_action_summary": {
                    "mapped_case_count": 12,
                    "unmapped_case_ids": [],
                    "action_case_counts": {
                        "enable_opt_in_public_cases": 1,
                        "resolve_network_policy_blockers": 1,
                        "set_credentialed_example_envs": 2,
                        "set_customer_connector_envs": 8,
                    },
                    "action_env_counts": {
                        "enable_opt_in_public_cases": 1,
                        "set_credentialed_example_envs": 2,
                        "set_customer_connector_envs": 20,
                    },
                    "action_connector_counts": {
                        "enable_opt_in_public_cases": 1,
                        "resolve_network_policy_blockers": 1,
                        "set_credentialed_example_envs": 1,
                        "set_customer_connector_envs": 8,
                    },
                    "terminal_action_codes": ["rerun_strict_go_live_gate"],
                },
                "gap_connector_summary": {
                    "connector_case_counts": {
                        "azure_blob": 1,
                        "bigquery": 1,
                        "clickhouse": 1,
                        "elasticsearch": 1,
                        "gcs": 1,
                        "neo4j": 1,
                        "redis": 1,
                        "rest_api": 3,
                        "s3": 1,
                        "snowflake": 1,
                    },
                    "connector_env_counts": {
                        "azure_blob": 5,
                        "bigquery": 2,
                        "clickhouse": 3,
                        "elasticsearch": 2,
                        "gcs": 2,
                        "neo4j": 3,
                        "redis": 1,
                        "rest_api": 3,
                        "s3": 2,
                    },
                },
                "gap_env_summary": {
                    "env_total_count": 23,
                    "shared_env_names": [],
                    "tier_env_counts": {
                        "credentialed_example": 2,
                        "customer_credentials_required": 20,
                        "public_no_auth": 1,
                    },
                },
                "gap_env_resolution_summary": {
                    "resolver_supported_count": 22,
                    "manual_only_count": 1,
                    "group_env_counts": {
                        "azure_blob": 5,
                        "bigquery": 2,
                        "clickhouse": 3,
                        "elasticsearch": 2,
                        "gcs": 2,
                        "neo4j": 3,
                        "redis": 1,
                        "s3": 2,
                    },
                    "manual_only_env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                },
                "gap_env_template_summary": {
                    "gap_env_total_count": 23,
                    "all_templates_cover_all_gap_envs": True,
                    "template_documented_counts": {
                        "root_env_example": 23,
                        "go_live_validation_env_example": 23,
                    },
                    "missing_in_any_template": [],
                },
            }
        ),
        encoding="utf-8",
    )
    go_live_full_real_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-24T02:00:00Z",
                "passed": 24,
                "failed": 0,
                "total": 24,
                "elapsed_seconds": 742.381,
                "details": {
                    "live_suite_count": 13,
                    "local_suite_count": 8,
                    "top_level_suite_count": 3,
                    "status": "complete",
                    "completed_suite_count": 24,
                    "expected_suite_count": 24,
                },
            }
        ),
        encoding="utf-8",
    )
    llm_rollout_proof_bundle_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-23T19:39:35Z",
                "public_http_library_routes_enable_env": "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED",
                "parity_artifact": {
                    "library_count": 22,
                    "function_count": 209,
                    "median_speedup_x": 102.88,
                    "mean_speedup_x": 100.8,
                    "max_speedup_x": 229.52,
                },
                "compiled_runtime_artifact": {
                    "module_count": 22,
                    "function_count": 209,
                    "failed_function_count": 0,
                    "max_cold_ms": {"value": 67.40324999555014},
                    "max_warm_ms": {"value": 0.4022920038551092},
                    "max_hot_ms": {"value": 0.49666650011204183},
                },
                "serving_extension_subset": {
                    "module_count": 6,
                    "function_count": 60,
                    "functions_compared": 60,
                    "modules": [
                        {"parity_compared_count": 10, "parity_function_count": 10}
                        for _ in range(6)
                    ],
                    "min_speedup_x": 31.63,
                    "max_speedup_x": 187.02,
                    "all_compiled_engine_used_mojo": True,
                    "max_cold_ms": {"value": 0.6642920052399859},
                    "max_warm_ms": {"value": 0.29083300614729524},
                    "max_hot_ms": {"value": 0.49666650011204183},
                },
                "serving_extension_channel_coverage": {
                    "module_count": 6,
                    "function_count": 60,
                    "source_rollout_function_count": 209,
                    "channels": [
                        {"channel": "python_sdk"},
                        {"channel": "typescript_sdk"},
                        {"channel": "cli"},
                        {"channel": "mcp"},
                        {"channel": "bundled_worker"},
                        {"channel": "runtime_local"},
                        {"channel": "http_api_feature_flag"},
                    ],
                },
                "live_suites": [
                    {
                        "name": "python_sdk_local_runtime",
                        "passed": 7,
                        "minimum_passed": 7,
                    },
                    {
                        "name": "typescript_sdk_local_runtime",
                        "passed": 4,
                        "skipped": 0,
                    },
                    {
                        "name": "local_runtime_cli_mcp_matrix",
                        "passed": 11,
                        "minimum_passed": 11,
                    },
                ],
                "sdk_contract_suites": [
                    {"name": "python_sdk_package_contract", "passed": 1, "failed": 0},
                    {
                        "name": "typescript_sdk_package_contract",
                        "passed": 1,
                        "failed": 0,
                        "skipped": 8,
                    },
                ],
                "http_flag_contract_suites": [{"passed": 2, "failed": 0}],
                "http_flag_live_suites": [{"passed": 4, "minimum_passed": 4, "failed": 0}],
            }
        ),
        encoding="utf-8",
    )
    provider_routing_overhead_benchmark_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-25T19:11:37Z",
                "chat": {
                    "baseline": {"p50_us": 4.625},
                    "single_hop_router": {"p50_us": 7.708},
                    "nested_router": {"p50_us": 12.542},
                    "retryable_failover_router": {
                        "p50_us": 13.875,
                        "mean_provider_attempts": 2.0,
                    },
                },
                "embeddings": {
                    "baseline": {"p50_us": 4.584},
                    "single_hop_router": {"p50_us": 7.584},
                    "nested_router": {"p50_us": 15.333},
                    "retryable_failover_router": {
                        "p50_us": 14.792,
                        "mean_provider_attempts": 2.0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    repository_intelligence_benchmark_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-25T19:15:00Z",
                "stages": {
                    "cold_snapshot": {"mean_ms": 12.4},
                    "existing_snapshot_hit": {"mean_ms": 1.8},
                    "triage": {"mean_ms": 4.7},
                    "decision_plan": {"mean_ms": 8.2},
                    "simulation": {"mean_ms": 2.1},
                    "apply_patch_only": {"mean_ms": 0.9},
                    "apply_local_branch": {"mean_ms": 5.6},
                },
                "token_reduction": {
                    "reduction_ratio": {"mean": 3.42},
                },
                "patch_impact": {
                    "patch_impact_risk_score": {"mean": 0.19},
                },
                "apply_gate": {
                    "blocked_runs": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    mcp_20q_results_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-15T00:53:44Z",
                "question_count": 20,
                "passed": 18,
                "avg_elapsed_ms": 428.6,
            }
        ),
        encoding="utf-8",
    )
    mcp_server_integration_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-24T00:48:47Z",
                "passed": 39,
                "failed": 0,
                "total": 39,
                "details": {
                    "runtime_proof_tool_count": 5,
                    "expected_tool_count": 25,
                },
            }
        ),
        encoding="utf-8",
    )
    openapi_integration_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-24T00:48:50Z",
                "passed": 71,
                "failed": 0,
                "total": 71,
                "details": {
                    "path_count": 114,
                    "schema_count": 293,
                    "security_schemes": ["BearerAuth", "LegacyApiKey"],
                },
            }
        ),
        encoding="utf-8",
    )
    csv_pipeline_results_path.write_text(
        "\n".join(
            [
                "filename,rows,columns,numeric_cols,parse_time_ms,map_time_ms,sim_time_ms,total_time_ms,status,rows_per_sec",
                "Backlog.csv,1535,39,10,49.28,36.0,25.19,116.13,simulated,31150",
                "bookings_new.csv,17719,52,9,777.14,0,0,777.14,parsed,22800",
                "quotes_new.csv,45237,80,14,2647.37,0,0,2647.37,parsed,17087",
                "Available_Inventory.csv,5820,244,43,1154.7,0,0,1154.7,parsed,5040",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    csv_pipeline_summary_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-23T20:11:00Z",
                "passed": 67,
                "failed": 0,
                "skipped": 0,
                "total": 67,
            }
        ),
        encoding="utf-8",
    )
    scorecard_suite_summaries_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-23T20:10:00Z",
                "narrow_resolver_regression": {
                    "accuracy": {"correct": 12, "total": 12, "percentage": 100.0},
                    "regression_suite": {"passed": 30, "failed": 0, "skipped": 0, "total": 30},
                },
                "join_path_correctness": {
                    "passed": 14,
                    "failed": 0,
                    "skipped": 0,
                    "total": 14,
                },
                "import_planner_regression_suite": {
                    "passed": 128,
                    "failed": 0,
                    "skipped": 0,
                    "total": 128,
                },
            }
        ),
        encoding="utf-8",
    )
    vector_hot_path_results_path.write_text(
        json.dumps(
            {
                "date": "2026-04-15",
                "results": [
                    {"n_columns": 32, "batch_pre_ns": 36, "speedup_D_over_C": 3.8},
                    {"n_columns": 2048, "batch_pre_ns": 650, "speedup_D_over_C": 43.0},
                ]
            }
        ),
        encoding="utf-8",
    )

    scorecard_sync.sync_shared_benchmark_scorecard(
        scorecard_path=scorecard_path,
        benchmark_summary_path=benchmark_summary_path,
        mojo_az_summary_path=mojo_az_summary_path,
        go_live_verify_summary_path=go_live_verify_summary_path,
        go_live_full_real_summary_path=go_live_full_real_summary_path,
        llm_rollout_proof_bundle_path=llm_rollout_proof_bundle_path,
        provider_routing_overhead_benchmark_path=provider_routing_overhead_benchmark_path,
        repository_intelligence_benchmark_path=repository_intelligence_benchmark_path,
        mcp_20q_results_path=mcp_20q_results_path,
        mcp_server_integration_summary_path=mcp_server_integration_summary_path,
        openapi_integration_summary_path=openapi_integration_summary_path,
        csv_pipeline_results_path=csv_pipeline_results_path,
        csv_pipeline_summary_path=csv_pipeline_summary_path,
        scorecard_suite_summaries_path=scorecard_suite_summaries_path,
        vector_hot_path_results_path=vector_hot_path_results_path,
    )

    text = scorecard_path.read_text(encoding="utf-8")
    assert "Updated: 2026-05-25" in text
    assert "## Go-live verifier (2026-05-22)" in text
    assert "## LLM rollout proof (2026-05-23)" in text
    assert (
        "| Mojo correctness (A-Z) | 244/244 libraries passed, 2414/2414 functions passed, "
        "57.8s total | `build/mojo_libraries_az_summary.json`, "
        "`tests/integration/test_mojo_libraries_az.py` | Green |"
    ) in text
    assert (
        "| Benchmark discovery inventory | 463 libraries benchmarkable today: 410 top-level, "
        "53 nested; shipping contract remains 22 modules / 209 functions | "
        "`benchmarks/summary.json`, `tests/benchmark_mojo_vs_python.py` | Green |"
    ) in text
    assert (
        "| Narrow resolver regression | 12/12 correct = 100% on one hospitality schema; "
        "30/30 regression tests passed | `build/scorecard_suite_summaries.json`, "
        "`tests/test_vector_resolver_hospitality.py` | Yellow |"
    ) in text
    assert (
        "| Join-path correctness | 14/14 passed | `build/scorecard_suite_summaries.json`, "
        "`tests/test_query_join_path.py` | Green |"
    ) in text
    csv_pipeline_summary = json.loads(csv_pipeline_summary_path.read_text())
    import_pipeline_row = (
        "| Import pipeline correctness | "
        f"{int(csv_pipeline_summary['passed'])}/{int(csv_pipeline_summary['total'])} "
        "active CSV pipeline integration checks passed"
    )
    skipped = int(csv_pipeline_summary.get("skipped", 0) or 0)
    if skipped:
        import_pipeline_row += f", {skipped} skipped"
    import_pipeline_row += (
        " | `build/csv_pipeline_summary.json`, "
        "`tests/integration/test_csv_pipeline.py` | Green |"
    )
    assert import_pipeline_row in text
    assert (
        "| Import/planner regression suite | 128/128 passed | "
        "`build/scorecard_suite_summaries.json`, `tests/unit/test_connectors.py`, "
        "`tests/test_auto_planner.py`, `tests/test_vector_resolver.py`, "
        "`tests/test_query_join_path.py` | Green |"
    ) in text
    assert (
        "| Mojo vs Python speed | 112.95x median, 182.42x mean, 3828.48x max, "
        "0.36x min across 4168 compared functions | "
        "`benchmarks/summary.json`, `tests/benchmark_mojo_vs_python.py` | Green |"
    ) in text
    assert (
        "| Provider routing overhead | p50 in-process routed latency (chat/embed) direct "
        "4.62/4.58 us, single 7.71/7.58 us, nested 12.54/15.33 us, failover 13.88/14.79 us; "
        "failover mean provider attempts 2.0/2.0 | "
        "`build/provider_routing_overhead_benchmark.json`, "
        "`benchmarks/provider_routing_overhead_benchmark.py`, "
        "`tests/test_provider_routing_overhead_benchmark.py` | Green |"
    ) in text
    assert (
        "| Repository intelligence workflow | mean stages cold snapshot 12.4 ms, existing hit "
        "1.8 ms, triage 4.7 ms, decision 8.2 ms, simulate 2.1 ms, apply patch 0.9 ms, "
        "local branch 5.6 ms; "
        "token reduction 3.42x mean, patch risk 0.19 | "
        "`build/repository_intelligence_benchmark.json`, "
        "`benchmarks/repository_intelligence_benchmark.py`, "
        "`tests/test_repository_intelligence_benchmark.py` | Green |"
    ) in text
    assert (
        "| MCP runtime integration | 39/39 live MCP boundary tests passed; 5 runtime proof "
        "tools present, 25 tools expected overall | "
        "`build/mcp_server_integration_summary.json`, `tests/integration/test_mcp_server.py` | "
        "Green |"
    ) in text
    assert (
        "| OpenAPI compliance | 71/71 compliance checks passed; 114 paths, 293 schemas, "
        "security BearerAuth, LegacyApiKey | "
        "`build/openapi_integration_summary.json`, `tests/integration/test_openapi.py` | "
        "Green |"
    ) in text

    scorecard_path.write_text(
        text.replace(
            "| Repository intelligence workflow | mean stages cold snapshot 12.4 ms, existing hit "
            "1.8 ms, triage 4.7 ms, decision 8.2 ms, simulate 2.1 ms, apply patch 0.9 ms, "
            "local branch 5.6 ms; token reduction 3.42x mean, patch risk 0.19 | "
            "`build/repository_intelligence_benchmark.json`, "
            "`benchmarks/repository_intelligence_benchmark.py`, "
            "`tests/test_repository_intelligence_benchmark.py` | Green |",
            "| Repository intelligence workflow | stale-again | stale | Green |",
        ),
        encoding="utf-8",
    )
    original_paths = {
        "SCORECARD_PATH": scorecard_sync.SCORECARD_PATH,
        "BENCHMARK_SUMMARY_PATH": scorecard_sync.BENCHMARK_SUMMARY_PATH,
        "MOJO_LIBRARIES_AZ_SUMMARY_PATH": scorecard_sync.MOJO_LIBRARIES_AZ_SUMMARY_PATH,
        "GO_LIVE_VERIFY_SUMMARY_PATH": scorecard_sync.GO_LIVE_VERIFY_SUMMARY_PATH,
        "GO_LIVE_FULL_REAL_SUMMARY_PATH": scorecard_sync.GO_LIVE_FULL_REAL_SUMMARY_PATH,
        "LLM_ROLLOUT_PROOF_BUNDLE_PATH": scorecard_sync.LLM_ROLLOUT_PROOF_BUNDLE_PATH,
        "PROVIDER_ROUTING_OVERHEAD_BENCHMARK_PATH": (
            scorecard_sync.PROVIDER_ROUTING_OVERHEAD_BENCHMARK_PATH
        ),
        "REPOSITORY_INTELLIGENCE_BENCHMARK_PATH": (
            scorecard_sync.REPOSITORY_INTELLIGENCE_BENCHMARK_PATH
        ),
        "MCP_20Q_RESULTS_PATH": scorecard_sync.MCP_20Q_RESULTS_PATH,
        "CSV_PIPELINE_RESULTS_PATH": scorecard_sync.CSV_PIPELINE_RESULTS_PATH,
        "CSV_PIPELINE_SUMMARY_PATH": scorecard_sync.CSV_PIPELINE_SUMMARY_PATH,
        "VECTOR_HOT_PATH_RESULTS_PATH": scorecard_sync.VECTOR_HOT_PATH_RESULTS_PATH,
        "SCORECARD_SUITE_SUMMARIES_PATH": scorecard_sync.SCORECARD_SUITE_SUMMARIES_PATH,
        "MCP_SERVER_INTEGRATION_SUMMARY_PATH": scorecard_sync.MCP_SERVER_INTEGRATION_SUMMARY_PATH,
        "OPENAPI_INTEGRATION_SUMMARY_PATH": scorecard_sync.OPENAPI_INTEGRATION_SUMMARY_PATH,
    }
    try:
        scorecard_sync.SCORECARD_PATH = scorecard_path
        scorecard_sync.BENCHMARK_SUMMARY_PATH = benchmark_summary_path
        scorecard_sync.MOJO_LIBRARIES_AZ_SUMMARY_PATH = mojo_az_summary_path
        scorecard_sync.GO_LIVE_VERIFY_SUMMARY_PATH = go_live_verify_summary_path
        scorecard_sync.GO_LIVE_FULL_REAL_SUMMARY_PATH = go_live_full_real_summary_path
        scorecard_sync.LLM_ROLLOUT_PROOF_BUNDLE_PATH = llm_rollout_proof_bundle_path
        scorecard_sync.PROVIDER_ROUTING_OVERHEAD_BENCHMARK_PATH = (
            provider_routing_overhead_benchmark_path
        )
        scorecard_sync.REPOSITORY_INTELLIGENCE_BENCHMARK_PATH = (
            repository_intelligence_benchmark_path
        )
        scorecard_sync.MCP_20Q_RESULTS_PATH = mcp_20q_results_path
        scorecard_sync.CSV_PIPELINE_RESULTS_PATH = csv_pipeline_results_path
        scorecard_sync.CSV_PIPELINE_SUMMARY_PATH = csv_pipeline_summary_path
        scorecard_sync.VECTOR_HOT_PATH_RESULTS_PATH = vector_hot_path_results_path
        scorecard_sync.SCORECARD_SUITE_SUMMARIES_PATH = scorecard_suite_summaries_path
        scorecard_sync.MCP_SERVER_INTEGRATION_SUMMARY_PATH = mcp_server_integration_summary_path
        scorecard_sync.OPENAPI_INTEGRATION_SUMMARY_PATH = openapi_integration_summary_path
        scorecard_sync.main()
    finally:
        for name, path in original_paths.items():
            setattr(scorecard_sync, name, path)

    rerendered_text = scorecard_path.read_text(encoding="utf-8")
    assert "| Repository intelligence workflow | stale-again | stale | Green |" not in rerendered_text
    assert (
        "| Repository intelligence workflow | mean stages cold snapshot 12.4 ms, existing hit "
        "1.8 ms, triage 4.7 ms, decision 8.2 ms, simulate 2.1 ms, apply patch 0.9 ms, "
        "local branch 5.6 ms; token reduction 3.42x mean, patch risk 0.19 | "
        "`build/repository_intelligence_benchmark.json`, "
        "`benchmarks/repository_intelligence_benchmark.py`, "
        "`tests/test_repository_intelligence_benchmark.py` | Green |"
    ) in rerendered_text
    assert (
        "| MCP end-to-end benchmark | 18/20 passed, 428.6 ms average latency | "
        "`benchmarks/claude_mcp_20q_results.json`, `benchmarks/bench_claude_mcp_20q.py` | "
        "Yellow |"
    ) in text
    assert (
        "| CSV ingest throughput | Backlog: 31,150 rows/s; bookings_new: 22,800 rows/s; "
        "quotes_new: 17,087 rows/s; Available_Inventory (244 cols): 5,040 rows/s | "
        "`tests/integration/csv_pipeline_results.csv`, `tests/integration/test_csv_pipeline.py` | "
        "Green |"
    ) in text
    assert (
        "| Vector hot path | Prefilter + rank at N=2048: 650 ns/query batch, 43.0x faster than "
        "full scan | `benchmarks/results/engines_prefilter_vs_fullscan.json`, "
        "`mojo/engine/vector_kernels/bench_prefilter.mojo` | Green |"
    ) in text
    assert (
        "| Serial verifier summary | 8/19 configured, 8/19 behavior-ready, completed steps "
        "connectivity + full_real, 0 failed steps | `build/go_live_verify_summary.json`, "
        "`build/go_live_verify_report.md`, `tests/go_live_verify.py`, "
        "`tests/test_go_live_verify.py` | Green |"
    ) in text
    assert (
        "| Full real suite | 24/24 suites passed; live API-facing 13, local benchmark/regression "
        "8, top-level verifier/bundle/A-Z 3 | `build/go_live_full_real_summary.json`, "
        "`tests/integration/test_go_live_full_real.py` | Green |"
    ) in text
    assert (
        "| Gap env templates | root_env_example 23/23, go_live_validation_env_example 23/23; "
        "missing none | `build/go_live_verify_summary.json`, "
        "`build/go_live_verify_report.md`, `.env.example`, "
        "`tests/integration/go_live_validation.env.example`, `tests/go_live_verify.py` | Green |"
    ) in text
    assert (
        "| 22-library parity proof | 22 libraries, 209 public runtime functions, 102.88x median, "
        "100.8x mean, 229.52x max | `build/llm_rollout_parity_benchmark.json`, "
        "`build/llm_rollout_parity_benchmark.txt`, "
        "`tests/test_llm_rollout_parity_benchmark.py` | Green |"
    ) in text
    assert (
        "| Serving extension subset proof | 6 modules, 60 functions, 60/60 parity comparisons "
        "across 6/6 modules, speedup range 31.63x to 187.02x, compiled mojo-only, worst cold "
        "0.66 ms, warm 0.291 ms, hot 0.497 ms | `build/llm_rollout_proof_bundle.json`, "
        "`tests/test_llm_rollout_proof_bundle.py` | Green |"
    ) in text
    assert (
        "| Public HTTP API flag readiness | `/v1/libraries*` routes are enabled by default "
        "and can be disabled via `ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED` | "
        "`tests/test_runtime_libraries_api.py`, `apps/api_server/main.py`, "
        "`apps/api_server/config.py` | Green |"
    ) in text
