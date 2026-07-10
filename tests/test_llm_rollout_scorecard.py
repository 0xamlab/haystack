import csv
import json
from pathlib import Path

from benchmarks.scorecard_sync import _format_counts, _format_us, format_speedup


def test_llm_rollout_scorecard_references_dedicated_artifacts_and_channels() -> None:
    text = Path("benchmarks/scorecard.md").read_text()

    assert "build/llm_rollout_parity_benchmark.json" in text
    assert "build/llm_compiled_runtime_benchmark.json" in text
    assert "build/llm_rollout_proof_bundle.json" in text
    assert "build/provider_routing_overhead_benchmark.json" in text
    assert "build/repository_intelligence_benchmark.json" in text
    assert "build/python_sdk_local_runtime_live_summary.json" in text
    assert "build/local_runtime_cli_mcp_matrix_live_summary.json" in text
    assert "build/typescript_sdk_local_runtime_live_summary.json" in text
    assert "build/public_http_library_routes_feature_flag_live_live_summary.json" in text
    assert "tests/integration/test_algenta_mojo_library_live.py" in text
    assert "tests/integration/test_cli_mcp_runtime_libraries_live.py" in text
    assert "tests/integration/test_typescript_runtime_live.py" in text
    assert "tests/test_algenta_mojo_sdk.py" in text
    assert "packages/ts-sdk/src/libraries.test.ts" in text
    assert "tests/test_runtime_libraries_api.py" in text
    assert "tests/integration/test_runtime_libraries_http_live.py" in text
    assert "benchmarks/llm_rollout_proof_bundle.py" in text
    assert "benchmarks/provider_routing_overhead_benchmark.py" in text
    assert "benchmarks/repository_intelligence_benchmark.py" in text
    assert "tests/test_llm_rollout_proof_bundle.py" in text
    assert "tests/test_provider_routing_overhead_benchmark.py" in text
    assert "tests/test_repository_intelligence_benchmark.py" in text
    assert "Python SDK" in text
    assert "TypeScript SDK" in text
    assert "CLI + DaemonClient + `Runtime(mode=\"local\")` + MCP" in text
    assert "SDK package contract coverage" in text
    assert "HTTP API flag contract coverage" in text
    assert "HTTP API flag live coverage" in text
    assert "Serving extension subset proof" in text
    assert "Serving extension channel coverage" in text
    assert "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED" in text
    assert "Repository intelligence workflow" in text


def test_llm_rollout_scorecard_matches_current_rollout_artifacts() -> None:
    text = Path("benchmarks/scorecard.md").read_text()
    bundle = json.loads(Path("build/llm_rollout_proof_bundle.json").read_text())

    parity_fragment = (
        f"{bundle['parity_artifact']['library_count']} libraries, "
        f"{bundle['parity_artifact']['function_count']} public runtime functions, "
        f"{format_speedup(float(bundle['parity_artifact']['median_speedup_x']))}x median, "
        f"{format_speedup(float(bundle['parity_artifact']['mean_speedup_x']))}x mean, "
        f"{format_speedup(float(bundle['parity_artifact']['max_speedup_x']))}x max"
    )
    compiled_fragment = (
        f"{bundle['compiled_runtime_artifact']['module_count']} modules, "
        f"{bundle['compiled_runtime_artifact']['function_count']} functions, "
        f"{bundle['compiled_runtime_artifact']['failed_function_count']} failures, "
        "all `engine_used=\"mojo\"`, "
        f"worst cold {float(bundle['compiled_runtime_artifact']['max_cold_ms']['value']):.2f} ms, "
        f"warm {float(bundle['compiled_runtime_artifact']['max_warm_ms']['value']):.3f} ms, "
        f"hot {float(bundle['compiled_runtime_artifact']['max_hot_ms']['value']):.3f} ms"
    )
    live_by_name = {item["name"]: item for item in bundle["live_suites"]}
    live_fragment = (
        f"Python SDK {live_by_name['python_sdk_local_runtime']['passed']}/"
        f"{live_by_name['python_sdk_local_runtime']['minimum_passed']} passed, "
        "CLI + DaemonClient + `Runtime(mode=\"local\")` + MCP "
        f"{live_by_name['local_runtime_cli_mcp_matrix']['passed']}/"
        f"{live_by_name['local_runtime_cli_mcp_matrix']['minimum_passed']} passed, "
        "TypeScript SDK "
        f"{live_by_name['typescript_sdk_local_runtime']['passed']} passed and "
        f"{live_by_name['typescript_sdk_local_runtime']['skipped']} API-backed skips when "
        "`DE_API_KEY` is unset"
    )
    sdk_contract_by_name = {item["name"]: item for item in bundle["sdk_contract_suites"]}
    sdk_contract_fragment = (
        "Python SDK package contract "
        f"{sdk_contract_by_name['python_sdk_package_contract']['passed']} passed; "
        "TypeScript SDK package contract "
        f"{sdk_contract_by_name['typescript_sdk_package_contract']['passed']} passed "
        f"and {sdk_contract_by_name['typescript_sdk_package_contract']['skipped']} skipped; "
        "both 0 failed"
    )
    http_flag_contract_by_name = {item["name"]: item for item in bundle["http_flag_contract_suites"]}
    http_flag_contract_fragment = (
        "HTTP API flag contract "
        f"{http_flag_contract_by_name['public_http_library_routes_feature_flag']['passed']} passed; "
        f"{http_flag_contract_by_name['public_http_library_routes_feature_flag']['failed']} failed"
    )
    http_flag_live_by_name = {item["name"]: item for item in bundle["http_flag_live_suites"]}
    http_flag_live_fragment = (
        "HTTP API feature-flag live suite "
        f"{http_flag_live_by_name['public_http_library_routes_feature_flag_live']['passed']}/"
        f"{http_flag_live_by_name['public_http_library_routes_feature_flag_live']['minimum_passed']} "
        "passed; "
        f"{http_flag_live_by_name['public_http_library_routes_feature_flag_live']['failed']} failed"
    )
    serving_extension_subset = bundle["serving_extension_subset"]
    fully_compared_modules = sum(
        1
        for module in serving_extension_subset["modules"]
        if int(module["parity_compared_count"]) == int(module["parity_function_count"])
    )
    serving_extension_fragment = (
        f"{serving_extension_subset['module_count']} modules, "
        f"{serving_extension_subset['function_count']} functions, "
        f"{serving_extension_subset['functions_compared']}/"
        f"{serving_extension_subset['function_count']} parity comparisons across "
        f"{fully_compared_modules}/{serving_extension_subset['module_count']} modules, "
        f"speedup range {format_speedup(float(serving_extension_subset['min_speedup_x']))}x "
        f"to {format_speedup(float(serving_extension_subset['max_speedup_x']))}x, "
        "compiled mojo-only, "
        f"worst cold {float(serving_extension_subset['max_cold_ms']['value']):.2f} ms, "
        f"warm {float(serving_extension_subset['max_warm_ms']['value']):.3f} ms, "
        f"hot {float(serving_extension_subset['max_hot_ms']['value']):.3f} ms"
    )
    serving_extension_channel_coverage = bundle["serving_extension_channel_coverage"]
    channel_names = ", ".join(
        channel["channel"] for channel in serving_extension_channel_coverage["channels"]
    )
    serving_extension_channel_fragment = (
        f"{channel_names} all passed for the "
        f"{serving_extension_channel_coverage['module_count']}-module / "
        f"{serving_extension_channel_coverage['function_count']}-function serving subset; "
        f"source rollout basis {serving_extension_channel_coverage['source_rollout_function_count']} "
        "functions"
    )
    http_flag_fragment = (
        "`/v1/libraries*` routes are feature-flag ready via "
        "`ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED` and remain disabled by default"
    )

    assert parity_fragment in text
    assert compiled_fragment in text
    assert serving_extension_fragment in text
    assert serving_extension_channel_fragment in text
    assert live_fragment in text
    assert sdk_contract_fragment in text
    assert http_flag_contract_fragment in text
    assert http_flag_live_fragment in text
    assert http_flag_fragment in text


def test_scorecard_matches_current_go_live_verify_artifact() -> None:
    text = Path("benchmarks/scorecard.md").read_text()
    summary = json.loads(Path("build/go_live_verify_summary.json").read_text())
    matrix_summary = summary["matrix_summary"]
    gap_source_summary = summary["gap_source_summary"]
    gap_env_template_summary = summary["gap_env_template_summary"]

    serial_summary_fragment = (
        f"{matrix_summary['configured_cases']}/{matrix_summary['total_cases']} configured, "
        f"{matrix_summary['behavior_ready_cases']}/{matrix_summary['total_cases']} behavior-ready, "
        f"completed steps {' + '.join(summary['completed_steps'])}, "
        f"{len(summary['failed_steps'])} failed steps"
    )
    planned_steps_fragment = " + ".join(step["name"] for step in summary["planned_steps"])
    durations_fragment = ", ".join(
        f"{step['name']} {float(step['duration_s']):.2f}s" for step in summary["step_results"]
    )
    gap_source_fragment = (
        "static tiers credentialed_example "
        f"{gap_source_summary['static_gap_counts_by_tier'].get('credentialed_example', 0)}, "
        "customer_credentials_required "
        f"{gap_source_summary['static_gap_counts_by_tier'].get('customer_credentials_required', 0)}, "
        "public_no_auth "
        f"{gap_source_summary['static_gap_counts_by_tier'].get('public_no_auth', 0)}; "
        "live tiers credentialed_example "
        f"{gap_source_summary['live_skip_counts_by_tier'].get('credentialed_example', 0)}, "
        "customer_credentials_required "
        f"{gap_source_summary['live_skip_counts_by_tier'].get('customer_credentials_required', 0)}, "
        "public_no_auth "
        f"{gap_source_summary['live_skip_counts_by_tier'].get('public_no_auth', 0)}; "
        "merged sources "
        f"{_format_counts(gap_source_summary['merged_gap_counts_by_source'])}"
    )
    env_templates_fragment = (
        "root_env_example "
        f"{gap_env_template_summary['template_documented_counts']['root_env_example']}/"
        f"{gap_env_template_summary['gap_env_total_count']}, "
        "go_live_validation_env_example "
        f"{gap_env_template_summary['template_documented_counts']['go_live_validation_env_example']}/"
        f"{gap_env_template_summary['gap_env_total_count']}; missing none"
    )

    assert serial_summary_fragment in text
    assert planned_steps_fragment in text
    assert durations_fragment in text
    assert gap_source_fragment in text
    assert env_templates_fragment in text


def test_llm_rollout_scorecard_matches_current_shared_benchmark_artifacts() -> None:
    text = Path("benchmarks/scorecard.md").read_text()
    summary = json.loads(Path("benchmarks/summary.json").read_text())
    provider_routing_overhead = json.loads(
        Path("build/provider_routing_overhead_benchmark.json").read_text()
    )
    mojo_az = json.loads(Path("build/mojo_libraries_az_summary.json").read_text())
    mcp_benchmark = json.loads(Path("benchmarks/claude_mcp_20q_results.json").read_text())
    vector_hot_path = json.loads(
        Path("benchmarks/results/engines_prefilter_vs_fullscan.json").read_text()
    )
    csv_pipeline_summary = json.loads(Path("build/csv_pipeline_summary.json").read_text())
    scorecard_suite_summaries = json.loads(Path("build/scorecard_suite_summaries.json").read_text())
    csv_pipeline_rows = list(
        csv.DictReader(Path("tests/integration/csv_pipeline_results.csv").open(encoding="utf-8-sig"))
    )

    mojo_correctness_fragment = (
        f"{mojo_az['passed_library_count']}/{mojo_az['library_count']} libraries passed, "
        f"{mojo_az['passed_function_count']}/{mojo_az['function_count']} functions passed, "
        f"{float(mojo_az['suite_duration_s']):.1f}s total"
    )
    benchmark_inventory_fragment = (
        f"{summary['benchmark_inventory']['total_libraries']} libraries benchmarkable today: "
        f"{summary['benchmark_inventory']['top_level_library_count']} top-level, "
        f"{summary['benchmark_inventory']['nested_library_count']} nested; "
        f"shipping contract remains {summary['shipping_runtime_contract']['module_count']} "
        f"modules / {summary['shipping_runtime_contract']['function_count']} functions"
    )
    speed_fragment = (
        f"{format_speedup(float(summary['median_speedup_x']))}x median, "
        f"{format_speedup(float(summary['mean_speedup_x']))}x mean, "
        f"{format_speedup(float(summary['max_speedup_x']))}x max, "
        f"{format_speedup(float(summary['min_speedup_x']))}x min across "
        f"{summary['total_functions_compared']} compared functions"
    )
    chat_benchmark = provider_routing_overhead["chat"]
    embedding_benchmark = provider_routing_overhead["embeddings"]
    provider_routing_fragment = (
        "p50 in-process routed latency (chat/embed) direct "
        f"{_format_us(float(chat_benchmark['baseline']['p50_us']))}/"
        f"{_format_us(float(embedding_benchmark['baseline']['p50_us']))} us, "
        f"single {_format_us(float(chat_benchmark['single_hop_router']['p50_us']))}/"
        f"{_format_us(float(embedding_benchmark['single_hop_router']['p50_us']))} us, "
        f"nested {_format_us(float(chat_benchmark['nested_router']['p50_us']))}/"
        f"{_format_us(float(embedding_benchmark['nested_router']['p50_us']))} us, "
        f"failover {_format_us(float(chat_benchmark['retryable_failover_router']['p50_us']))}/"
        f"{_format_us(float(embedding_benchmark['retryable_failover_router']['p50_us']))} us; "
        "failover mean provider attempts "
        f"{float(chat_benchmark['retryable_failover_router']['mean_provider_attempts']):.1f}/"
        f"{float(embedding_benchmark['retryable_failover_router']['mean_provider_attempts']):.1f}"
    )
    mcp_fragment = (
        f"{mcp_benchmark['passed']}/{mcp_benchmark['question_count']} passed, "
        f"{float(mcp_benchmark['avg_elapsed_ms']):.1f} ms average latency"
    )
    vector_target = next(
        item for item in vector_hot_path["results"] if int(item["n_columns"]) == 2048
    )
    vector_fragment = (
        f"Prefilter + rank at N=2048: {int(vector_target['batch_pre_ns'])} ns/query batch, "
        f"{float(vector_target['speedup_D_over_C']):.1f}x faster than full scan"
    )
    csv_by_name = {row["filename"]: row for row in csv_pipeline_rows}
    csv_fragment = (
        f"Backlog: {round(float(csv_by_name['Backlog.csv']['rows_per_sec'])):,.0f} rows/s; "
        f"bookings_new: {round(float(csv_by_name['bookings_new.csv']['rows_per_sec'])):,.0f} rows/s; "
        f"quotes_new: {round(float(csv_by_name['quotes_new.csv']['rows_per_sec'])):,.0f} rows/s; "
        "Available_Inventory "
        f"({int(csv_by_name['Available_Inventory.csv']['columns'])} cols): "
        f"{round(float(csv_by_name['Available_Inventory.csv']['rows_per_sec'])):,.0f} rows/s"
    )
    narrow_resolver = scorecard_suite_summaries["narrow_resolver_regression"]
    narrow_resolver_fragment = (
        f"{narrow_resolver['accuracy']['correct']}/{narrow_resolver['accuracy']['total']} "
        f"correct = {round(float(narrow_resolver['accuracy']['percentage'])):.0f}% on one hospitality schema; "
        f"{narrow_resolver['regression_suite']['passed']}/"
        f"{narrow_resolver['regression_suite']['total']} regression tests passed"
    )
    join_path_fragment = (
        f"{scorecard_suite_summaries['join_path_correctness']['passed']}/"
        f"{scorecard_suite_summaries['join_path_correctness']['total']} passed"
    )
    import_pipeline_fragment = (
        f"{csv_pipeline_summary['passed']}/{csv_pipeline_summary['total']} "
        "active CSV pipeline integration checks passed"
    )
    skipped = int(csv_pipeline_summary.get("skipped", 0) or 0)
    if skipped:
        import_pipeline_fragment += f", {skipped} skipped"
    import_planner_fragment = (
        f"{scorecard_suite_summaries['import_planner_regression_suite']['passed']}/"
        f"{scorecard_suite_summaries['import_planner_regression_suite']['total']} passed"
    )

    assert mojo_correctness_fragment in text
    assert benchmark_inventory_fragment in text
    assert speed_fragment in text
    assert provider_routing_fragment in text
    assert narrow_resolver_fragment in text
    assert join_path_fragment in text
    assert import_pipeline_fragment in text
    assert import_planner_fragment in text
    assert mcp_fragment in text
    assert vector_fragment in text
    assert csv_fragment in text
    assert len(csv_pipeline_rows) >= 5
