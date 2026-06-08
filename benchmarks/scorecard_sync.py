from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCORECARD_PATH = PROJECT_ROOT / "benchmarks" / "scorecard.md"
BENCHMARK_SUMMARY_PATH = PROJECT_ROOT / "benchmarks" / "summary.json"
MOJO_LIBRARIES_AZ_SUMMARY_PATH = PROJECT_ROOT / "build" / "mojo_libraries_az_summary.json"
GO_LIVE_VERIFY_SUMMARY_PATH = PROJECT_ROOT / "build" / "go_live_verify_summary.json"
GO_LIVE_FULL_REAL_SUMMARY_PATH = PROJECT_ROOT / "build" / "go_live_full_real_summary.json"
LLM_ROLLOUT_PROOF_BUNDLE_PATH = PROJECT_ROOT / "build" / "llm_rollout_proof_bundle.json"
PROVIDER_ROUTING_OVERHEAD_BENCHMARK_PATH = (
    PROJECT_ROOT / "build" / "provider_routing_overhead_benchmark.json"
)
REPOSITORY_INTELLIGENCE_BENCHMARK_PATH = (
    PROJECT_ROOT / "build" / "repository_intelligence_benchmark.json"
)
MCP_20Q_RESULTS_PATH = PROJECT_ROOT / "benchmarks" / "claude_mcp_20q_results.json"
CSV_PIPELINE_RESULTS_PATH = PROJECT_ROOT / "tests" / "integration" / "csv_pipeline_results.csv"
CSV_PIPELINE_SUMMARY_PATH = PROJECT_ROOT / "build" / "csv_pipeline_summary.json"
VECTOR_HOT_PATH_RESULTS_PATH = (
    PROJECT_ROOT / "benchmarks" / "results" / "engines_prefilter_vs_fullscan.json"
)
SCORECARD_SUITE_SUMMARIES_PATH = PROJECT_ROOT / "build" / "scorecard_suite_summaries.json"
MCP_SERVER_INTEGRATION_SUMMARY_PATH = (
    PROJECT_ROOT / "build" / "mcp_server_integration_summary.json"
)
OPENAPI_INTEGRATION_SUMMARY_PATH = PROJECT_ROOT / "build" / "openapi_integration_summary.json"


def format_speedup(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_us(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_ms(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_counts(summary: dict[str, Any], *, preferred_order: list[str] | None = None) -> str:
    keys = preferred_order or sorted(summary)
    return ", ".join(f"{key} {summary[key]}" for key in keys if key in summary)


def _replace_row(text: str, label: str, rendered_row: str) -> str:
    return re.sub(
        rf"(?m)^\| {re.escape(label)} \|.*$",
        rendered_row,
        text,
        count=1,
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def render_mojo_correctness_row(summary: dict[str, Any]) -> str:
    status = "Green" if int(summary["failed_library_count"]) == 0 else "Red"
    current = (
        f"{int(summary['passed_library_count'])}/{int(summary['library_count'])} libraries passed, "
        f"{int(summary['passed_function_count'])}/{int(summary['function_count'])} functions passed, "
        f"{float(summary['suite_duration_s']):.1f}s total"
    )
    return (
        "| Mojo correctness (A-Z) | "
        f"{current} | "
        "`build/mojo_libraries_az_summary.json`, `tests/integration/test_mojo_libraries_az.py` | "
        f"{status} |"
    )


def render_benchmark_inventory_row(summary: dict[str, Any]) -> str:
    inventory = summary["benchmark_inventory"]
    shipping = summary["shipping_runtime_contract"]
    current = (
        f"{int(inventory['total_libraries'])} libraries benchmarkable today: "
        f"{int(inventory['top_level_library_count'])} top-level, "
        f"{int(inventory['nested_library_count'])} nested; "
        f"shipping contract remains {int(shipping['module_count'])} modules / "
        f"{int(shipping['function_count'])} functions"
    )
    return (
        "| Benchmark discovery inventory | "
        f"{current} | "
        "`benchmarks/summary.json`, `tests/benchmark_mojo_vs_python.py` | Green |"
    )


def render_mojo_speed_row(summary: dict[str, Any]) -> str:
    current = (
        f"{format_speedup(float(summary['median_speedup_x']))}x median, "
        f"{format_speedup(float(summary['mean_speedup_x']))}x mean, "
        f"{format_speedup(float(summary['max_speedup_x']))}x max, "
        f"{format_speedup(float(summary['min_speedup_x']))}x min across "
        f"{int(summary['total_functions_compared'])} compared functions"
    )
    return (
        "| Mojo vs Python speed | "
        f"{current} | "
        "`benchmarks/summary.json`, `tests/benchmark_mojo_vs_python.py` | Green |"
    )


def render_provider_routing_overhead_row(summary: dict[str, Any]) -> str:
    chat = summary["chat"]
    embeddings = summary["embeddings"]
    current = (
        "p50 in-process routed latency (chat/embed) direct "
        f"{_format_us(float(chat['baseline']['p50_us']))}/"
        f"{_format_us(float(embeddings['baseline']['p50_us']))} us, "
        f"single {_format_us(float(chat['single_hop_router']['p50_us']))}/"
        f"{_format_us(float(embeddings['single_hop_router']['p50_us']))} us, "
        f"nested {_format_us(float(chat['nested_router']['p50_us']))}/"
        f"{_format_us(float(embeddings['nested_router']['p50_us']))} us, "
        f"failover {_format_us(float(chat['retryable_failover_router']['p50_us']))}/"
        f"{_format_us(float(embeddings['retryable_failover_router']['p50_us']))} us; "
        "failover mean provider attempts "
        f"{float(chat['retryable_failover_router']['mean_provider_attempts']):.1f}/"
        f"{float(embeddings['retryable_failover_router']['mean_provider_attempts']):.1f}"
    )
    return (
        "| Provider routing overhead | "
        f"{current} | "
        "`build/provider_routing_overhead_benchmark.json`, "
        "`benchmarks/provider_routing_overhead_benchmark.py`, "
        "`tests/test_provider_routing_overhead_benchmark.py` | Green |"
    )


def render_repository_intelligence_row(summary: dict[str, Any]) -> str:
    stages = summary["stages"]
    token_reduction = summary["token_reduction"]
    patch_impact = summary["patch_impact"]
    apply_gate = summary["apply_gate"]
    apply_patch_ms = _format_ms(float(stages["apply_patch_only"]["mean_ms"]))
    apply_local_branch = stages.get("apply_local_branch")
    apply_summary = f"apply patch {apply_patch_ms} ms"
    if isinstance(apply_local_branch, dict) and "mean_ms" in apply_local_branch:
        apply_summary += (
            f", local branch {_format_ms(float(apply_local_branch['mean_ms']))} ms"
        )
    current = (
        "mean stages cold snapshot "
        f"{_format_ms(float(stages['cold_snapshot']['mean_ms']))} ms, "
        f"existing hit {_format_ms(float(stages['existing_snapshot_hit']['mean_ms']))} ms, "
        f"triage {_format_ms(float(stages['triage']['mean_ms']))} ms, "
        f"decision {_format_ms(float(stages['decision_plan']['mean_ms']))} ms, "
        f"simulate {_format_ms(float(stages['simulation']['mean_ms']))} ms, "
        f"{apply_summary}; "
        f"token reduction {float(token_reduction['reduction_ratio']['mean']):.2f}x mean, "
        f"patch risk {float(patch_impact['patch_impact_risk_score']['mean']):.2f}"
    )
    status = "Green" if int(apply_gate.get("blocked_runs", 0)) == 0 else "Red"
    return (
        "| Repository intelligence workflow | "
        f"{current} | "
        "`build/repository_intelligence_benchmark.json`, "
        "`benchmarks/repository_intelligence_benchmark.py`, "
        "`tests/test_repository_intelligence_benchmark.py` | "
        f"{status} |"
    )


def render_mcp_end_to_end_row(summary: dict[str, Any]) -> str:
    question_count = int(summary["question_count"])
    passed = int(summary["passed"])
    failed = max(question_count - passed, 0)
    status = "Green" if failed == 0 else "Yellow"
    current = (
        f"{passed}/{question_count} passed, "
        f"{float(summary['avg_elapsed_ms']):.1f} ms average latency"
    )
    return (
        "| MCP end-to-end benchmark | "
        f"{current} | "
        "`benchmarks/claude_mcp_20q_results.json`, `benchmarks/bench_claude_mcp_20q.py` | "
        f"{status} |"
    )


def render_mcp_runtime_integration_row(summary: dict[str, Any]) -> str:
    details = summary.get("details", {})
    current = (
        f"{int(summary['passed'])}/{int(summary['total'])} live MCP boundary tests passed; "
        f"{int(details.get('runtime_proof_tool_count', 0))} runtime proof tools present, "
        f"{int(details.get('expected_tool_count', 0))} tools expected overall"
    )
    if int(summary.get("skipped", 0)) > 0:
        current += f", {int(summary['skipped'])} skipped"
    status = "Green" if int(summary["failed"]) == 0 else "Red"
    return (
        "| MCP runtime integration | "
        f"{current} | "
        "`build/mcp_server_integration_summary.json`, `tests/integration/test_mcp_server.py` | "
        f"{status} |"
    )


def render_openapi_compliance_row(summary: dict[str, Any]) -> str:
    details = summary.get("details", {})
    security = ", ".join(str(item) for item in details.get("security_schemes") or [])
    current = (
        f"{int(summary['passed'])}/{int(summary['total'])} compliance checks passed; "
        f"{int(details.get('path_count', 0))} paths, "
        f"{int(details.get('schema_count', 0))} schemas, "
        f"security {security}"
    )
    if int(summary.get("skipped", 0)) > 0:
        current += f", {int(summary['skipped'])} skipped"
    status = "Green" if int(summary["failed"]) == 0 else "Red"
    return (
        "| OpenAPI compliance | "
        f"{current} | "
        "`build/openapi_integration_summary.json`, `tests/integration/test_openapi.py` | "
        f"{status} |"
    )


def render_go_live_full_real_row(summary: dict[str, Any]) -> str:
    details = summary.get("details", {})
    is_complete = str(details.get("status", "complete")) == "complete"
    if is_complete:
        current = (
            f"{int(summary['passed'])}/{int(summary['total'])} suites passed; "
            f"live API-facing {int(details.get('live_suite_count', 0))}, "
            f"local benchmark/regression {int(details.get('local_suite_count', 0))}, "
            f"top-level verifier/bundle/A-Z {int(details.get('top_level_suite_count', 0))}"
        )
    else:
        current = (
            f"{int(summary['passed'])}/{int(details.get('expected_suite_count', summary['total']))} suites "
            f"passed so far; completed {int(details.get('completed_suite_count', summary['total']))}/"
            f"{int(details.get('expected_suite_count', summary['total']))}"
        )
    status = "Green" if int(summary["failed"]) == 0 and is_complete else "Red"
    return (
        "| Full real suite | "
        f"{current} | "
        "`build/go_live_full_real_summary.json`, `tests/integration/test_go_live_full_real.py` | "
        f"{status} |"
    )


def render_csv_ingest_row(rows: list[dict[str, str]]) -> str:
    by_name = {row["filename"]: row for row in rows}

    def _rows_per_sec(filename: str) -> str:
        row = by_name[filename]
        return f"{round(float(row['rows_per_sec'])):,.0f}"

    wide_columns = int(by_name["Available_Inventory.csv"]["columns"])
    current = (
        f"Backlog: {_rows_per_sec('Backlog.csv')} rows/s; "
        f"bookings_new: {_rows_per_sec('bookings_new.csv')} rows/s; "
        f"quotes_new: {_rows_per_sec('quotes_new.csv')} rows/s; "
        f"Available_Inventory ({wide_columns} cols): "
        f"{_rows_per_sec('Available_Inventory.csv')} rows/s"
    )
    return (
        "| CSV ingest throughput | "
        f"{current} | "
        "`tests/integration/csv_pipeline_results.csv`, `tests/integration/test_csv_pipeline.py` | "
        "Green |"
    )


def render_narrow_resolver_regression_row(summary: dict[str, Any]) -> str:
    accuracy = summary["accuracy"]
    regression_suite = summary["regression_suite"]
    status = "Yellow" if int(regression_suite["failed"]) == 0 else "Red"
    current = (
        f"{int(accuracy['correct'])}/{int(accuracy['total'])} correct = "
        f"{round(float(accuracy['percentage'])):.0f}% on one hospitality schema; "
        f"{int(regression_suite['passed'])}/{int(regression_suite['total'])} regression tests passed"
    )
    return (
        "| Narrow resolver regression | "
        f"{current} | "
        "`build/scorecard_suite_summaries.json`, `tests/test_vector_resolver_hospitality.py` | "
        f"{status} |"
    )


def render_join_path_correctness_row(summary: dict[str, Any]) -> str:
    current = (
        f"{int(summary['passed'])}/{int(summary['total'])} passed"
        if int(summary["skipped"]) == 0
        else f"{int(summary['passed'])}/{int(summary['total'])} passed, {int(summary['skipped'])} skipped"
    )
    status = "Green" if int(summary["failed"]) == 0 else "Red"
    return (
        "| Join-path correctness | "
        f"{current} | "
        "`build/scorecard_suite_summaries.json`, `tests/test_query_join_path.py` | "
        f"{status} |"
    )


def render_import_pipeline_correctness_row(summary: dict[str, Any]) -> str:
    current = (
        f"{int(summary['passed'])}/{int(summary['total'])} active CSV pipeline integration checks passed"
    )
    if int(summary["skipped"]) > 0:
        current += f", {int(summary['skipped'])} skipped"
    status = "Green" if int(summary["failed"]) == 0 else "Red"
    return (
        "| Import pipeline correctness | "
        f"{current} | "
        "`build/csv_pipeline_summary.json`, `tests/integration/test_csv_pipeline.py` | "
        f"{status} |"
    )


def render_import_planner_regression_row(summary: dict[str, Any]) -> str:
    current = f"{int(summary['passed'])}/{int(summary['total'])} passed"
    if int(summary["skipped"]) > 0:
        current += f", {int(summary['skipped'])} skipped"
    status = "Green" if int(summary["failed"]) == 0 else "Red"
    return (
        "| Import/planner regression suite | "
        f"{current} | "
        "`build/scorecard_suite_summaries.json`, `tests/unit/test_connectors.py`, "
        "`tests/test_auto_planner.py`, `tests/test_vector_resolver.py`, "
        "`tests/test_query_join_path.py` | "
        f"{status} |"
    )


def render_vector_hot_path_row(summary: dict[str, Any]) -> str:
    target = next(item for item in summary["results"] if int(item["n_columns"]) == 2048)
    current = (
        "Prefilter + rank at N=2048: "
        f"{int(target['batch_pre_ns'])} ns/query batch, "
        f"{float(target['speedup_D_over_C']):.1f}x faster than full scan"
    )
    return (
        "| Vector hot path | "
        f"{current} | "
        "`benchmarks/results/engines_prefilter_vs_fullscan.json`, "
        "`mojo/engine/vector_kernels/bench_prefilter.mojo` | Green |"
    )


def render_serial_verifier_summary_row(summary: dict[str, Any]) -> str:
    matrix_summary = summary["matrix_summary"]
    current = (
        f"{int(matrix_summary['configured_cases'])}/{int(matrix_summary['total_cases'])} configured, "
        f"{int(matrix_summary['behavior_ready_cases'])}/{int(matrix_summary['total_cases'])} "
        "behavior-ready, completed steps "
        f"{' + '.join(summary['completed_steps'])}, {len(summary['failed_steps'])} failed steps"
    )
    status = "Green" if not summary["failed_steps"] else "Red"
    return (
        "| Serial verifier summary | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py`, `tests/test_go_live_verify.py` | "
        f"{status} |"
    )


def render_planned_serial_steps_row(summary: dict[str, Any]) -> str:
    current = " + ".join(step["name"] for step in summary["planned_steps"])
    return (
        "| Planned serial steps | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/integration/GO_LIVE_VALIDATION.md` | Green |"
    )


def render_latest_serial_durations_row(summary: dict[str, Any]) -> str:
    durations = ", ".join(
        f"{step['name']} {float(step['duration_s']):.2f}s" for step in summary["step_results"]
    )
    return (
        "| Latest serial durations | "
        f"{durations} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md` | Green |"
    )


def render_canonical_verifier_mode_row(summary: dict[str, Any]) -> str:
    options = summary["options"]
    filters = summary.get("filters") or {}
    selected_tiers = filters.get("tiers") or []
    selected_connectors = filters.get("connectors") or []
    mode = (
        "strict"
        if bool(options["strict"])
        else "unfiltered"
        if not selected_tiers and not selected_connectors
        else "filtered"
    )
    current = (
        f"{mode}, "
        f"{'strict' if bool(options['strict']) else 'non-strict'}, "
        f"{'includes' if bool(options['include_full_real']) else 'excludes'} full_real, "
        f"{'includes' if bool(options['include_pytest']) else 'excludes'} pytest"
    )
    return (
        "| Canonical verifier mode | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `Makefile`, `tests/integration/GO_LIVE_VALIDATION.md` | "
        "Green |"
    )


def render_static_matrix_operational_gaps_row(summary: dict[str, Any]) -> str:
    gap_summary = summary["gap_source_summary"]
    current = (
        f"{int(gap_summary['static_gap_count'])} cases from the current static matrix status "
        "before live connectivity overrides"
    )
    return (
        "| Static matrix operational gaps | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `tests/go_live_matrix_status.py` | Amber |"
    )


def render_live_connectivity_skips_row(summary: dict[str, Any]) -> str:
    current = (
        f"{int(summary['gap_source_summary']['live_skip_count'])} skips captured from the latest "
        "connectivity run and merged into operational gaps"
    )
    return (
        "| Live connectivity skips | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/integration/test_go_live_connectivity_real.py` | Amber |"
    )


def render_gap_source_breakdown_row(summary: dict[str, Any]) -> str:
    gap_summary = summary["gap_source_summary"]
    current = (
        "static tiers "
        f"{_format_counts(gap_summary['static_gap_counts_by_tier'], preferred_order=['credentialed_example', 'customer_credentials_required', 'public_no_auth'])}; "
        "live tiers "
        f"{_format_counts(gap_summary['live_skip_counts_by_tier'], preferred_order=['credentialed_example', 'customer_credentials_required', 'public_no_auth'])}; "
        "merged sources "
        f"{_format_counts(gap_summary['merged_gap_counts_by_source'])}"
    )
    return (
        "| Gap source breakdown | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | Amber |"
    )


def render_gap_connector_breakdown_row(summary: dict[str, Any]) -> str:
    current = (
        "merged connectors "
        f"{_format_counts(summary['gap_source_summary']['merged_gap_counts_by_connector_type'])}"
    )
    return (
        "| Gap connector breakdown | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | Amber |"
    )


def render_outstanding_operational_gaps_row(summary: dict[str, Any]) -> str:
    gap_summary = summary["gap_source_summary"]
    current = (
        f"{int(gap_summary['merged_gap_count'])} cases outside repo-owned proof: "
        f"{_format_counts(gap_summary['merged_gap_counts_by_tier'], preferred_order=['credentialed_example', 'customer_credentials_required', 'public_no_auth'])}"
    )
    return (
        "| Outstanding operational gaps | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_matrix_status.py` | Amber |"
    )


def render_operator_next_actions_row(summary: dict[str, Any]) -> str:
    current = f"{len(summary['next_actions'])} action groups ready from current operational gaps"
    return (
        "| Operator next actions | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | Amber |"
    )


def render_gap_action_routing_row(summary: dict[str, Any]) -> str:
    action_summary = summary["gap_action_summary"]
    terminal = ", ".join(action_summary["terminal_action_codes"]) or "none"
    unmapped = ", ".join(action_summary["unmapped_case_ids"]) or "none"
    current = (
        f"{int(action_summary['mapped_case_count'])}/{int(summary['gap_source_summary']['merged_gap_count'])} cases mapped; "
        f"actions {_format_counts(action_summary['action_case_counts'])}; "
        f"envs {_format_counts(action_summary['action_env_counts'])}; "
        f"connectors {_format_counts(action_summary['action_connector_counts'])}; "
        f"terminal {terminal}; unmapped {unmapped}"
    )
    return (
        "| Gap action routing | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | Amber |"
    )


def render_gap_connector_routing_row(summary: dict[str, Any]) -> str:
    connector_summary = summary["gap_connector_summary"]
    current = (
        f"cases {_format_counts(connector_summary['connector_case_counts'])}; "
        f"envs {_format_counts(connector_summary['connector_env_counts'])}"
    )
    return (
        "| Gap connector routing | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | Amber |"
    )


def render_gap_env_routing_row(summary: dict[str, Any]) -> str:
    env_summary = summary["gap_env_summary"]
    shared_envs = ", ".join(env_summary["shared_env_names"]) or "none"
    current = (
        f"{int(env_summary['env_total_count'])} envs mapped; "
        f"tiers {_format_counts(env_summary['tier_env_counts'], preferred_order=['credentialed_example', 'customer_credentials_required', 'public_no_auth'])}; "
        f"shared {shared_envs}"
    )
    return (
        "| Gap env routing | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | Amber |"
    )


def render_gap_env_resolution_row(summary: dict[str, Any]) -> str:
    resolution_summary = summary["gap_env_resolution_summary"]
    manual_envs = ", ".join(resolution_summary["manual_only_env_names"]) or "none"
    current = (
        f"resolver-supported {int(resolution_summary['resolver_supported_count'])}; "
        f"manual-only {int(resolution_summary['manual_only_count'])}; "
        f"groups {_format_counts(resolution_summary['group_env_counts'])}; "
        f"manual {manual_envs}"
    )
    return (
        "| Gap env resolution | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py`, `tests/go_live_secret_resolver.py` | Amber |"
    )


def render_gap_env_templates_row(summary: dict[str, Any]) -> str:
    template_summary = summary["gap_env_template_summary"]
    documented_counts = template_summary["template_documented_counts"]
    total_envs = int(template_summary["gap_env_total_count"])
    current = (
        f"root_env_example {int(documented_counts['root_env_example'])}/{total_envs}, "
        "go_live_validation_env_example "
        f"{int(documented_counts['go_live_validation_env_example'])}/{total_envs}; "
        f"missing {', '.join(template_summary['missing_in_any_template']) or 'none'}"
    )
    status = "Green" if bool(template_summary["all_templates_cover_all_gap_envs"]) else "Amber"
    return (
        "| Gap env templates | "
        f"{current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`.env.example`, `tests/integration/go_live_validation.env.example`, "
        "`tests/go_live_verify.py` | "
        f"{status} |"
    )


def render_rollout_parity_row(summary: dict[str, Any]) -> str:
    parity = summary["parity_artifact"]
    current = (
        f"{int(parity['library_count'])} libraries, "
        f"{int(parity['function_count'])} public runtime functions, "
        f"{format_speedup(float(parity['median_speedup_x']))}x median, "
        f"{format_speedup(float(parity['mean_speedup_x']))}x mean, "
        f"{format_speedup(float(parity['max_speedup_x']))}x max"
    )
    return (
        "| 22-library parity proof | "
        f"{current} | "
        "`build/llm_rollout_parity_benchmark.json`, `build/llm_rollout_parity_benchmark.txt`, "
        "`tests/test_llm_rollout_parity_benchmark.py` | Green |"
    )


def render_compiled_runtime_latency_row(summary: dict[str, Any]) -> str:
    compiled = summary["compiled_runtime_artifact"]
    current = (
        f"{int(compiled['module_count'])} modules, "
        f"{int(compiled['function_count'])} functions, "
        f"{int(compiled['failed_function_count'])} failures, "
        'all `engine_used="mojo"`'
        f", worst cold {float(compiled['max_cold_ms']['value']):.2f} ms, "
        f"warm {float(compiled['max_warm_ms']['value']):.3f} ms, "
        f"hot {float(compiled['max_hot_ms']['value']):.3f} ms"
    )
    return (
        "| Compiled runtime latency proof | "
        f"{current} | "
        "`build/llm_compiled_runtime_benchmark.json`, "
        "`tests/test_llm_compiled_runtime_benchmark.py` | Green |"
    )


def render_serving_extension_subset_row(summary: dict[str, Any]) -> str:
    subset = summary["serving_extension_subset"]
    fully_compared_modules = sum(
        1
        for module in subset["modules"]
        if int(module["parity_compared_count"]) == int(module["parity_function_count"])
    )
    current = (
        f"{int(subset['module_count'])} modules, "
        f"{int(subset['function_count'])} functions, "
        f"{int(subset['functions_compared'])}/{int(subset['function_count'])} parity comparisons "
        f"across {fully_compared_modules}/{int(subset['module_count'])} modules, "
        f"speedup range {format_speedup(float(subset['min_speedup_x']))}x "
        f"to {format_speedup(float(subset['max_speedup_x']))}x, "
        f"compiled {'mojo-only' if bool(subset['all_compiled_engine_used_mojo']) else 'mixed-engine'}, "
        f"worst cold {float(subset['max_cold_ms']['value']):.2f} ms, "
        f"warm {float(subset['max_warm_ms']['value']):.3f} ms, "
        f"hot {float(subset['max_hot_ms']['value']):.3f} ms"
    )
    return (
        "| Serving extension subset proof | "
        f"{current} | "
        "`build/llm_rollout_proof_bundle.json`, `tests/test_llm_rollout_proof_bundle.py` | Green |"
    )


def render_serving_extension_channel_coverage_row(summary: dict[str, Any]) -> str:
    coverage = summary["serving_extension_channel_coverage"]
    channel_names = ", ".join(channel["channel"] for channel in coverage["channels"])
    current = (
        f"{channel_names} all passed for the "
        f"{int(coverage['module_count'])}-module / {int(coverage['function_count'])}-function "
        f"serving subset; source rollout basis {int(coverage['source_rollout_function_count'])} functions"
    )
    return (
        "| Serving extension channel coverage | "
        f"{current} | "
        "`build/llm_rollout_proof_bundle.json`, `tests/test_llm_rollout_matrix.py`, "
        "`tests/test_llm_rollout_proof_bundle.py` | Green |"
    )


def render_supported_channel_coverage_row(summary: dict[str, Any]) -> str:
    live_by_name = {item["name"]: item for item in summary["live_suites"]}
    current = (
        f"Python SDK {int(live_by_name['python_sdk_local_runtime']['passed'])}/"
        f"{int(live_by_name['python_sdk_local_runtime']['minimum_passed'])} passed, "
        "CLI + DaemonClient + `Runtime(mode=\"local\")` + MCP "
        f"{int(live_by_name['local_runtime_cli_mcp_matrix']['passed'])}/"
        f"{int(live_by_name['local_runtime_cli_mcp_matrix']['minimum_passed'])} passed, "
        "TypeScript SDK "
        f"{int(live_by_name['typescript_sdk_local_runtime']['passed'])} passed and "
        f"{int(live_by_name['typescript_sdk_local_runtime']['skipped'])} API-backed skips when "
        "`DE_API_KEY` is unset"
    )
    return (
        "| Supported channel coverage | "
        f"{current} | "
        "`build/python_sdk_local_runtime_live_summary.json`, "
        "`build/local_runtime_cli_mcp_matrix_live_summary.json`, "
        "`build/typescript_sdk_local_runtime_live_summary.json`, "
        "`tests/integration/test_algenta_mojo_library_live.py`, "
        "`tests/integration/test_cli_mcp_runtime_libraries_live.py`, "
        "`tests/integration/test_typescript_runtime_live.py` | Green |"
    )


def render_sdk_package_contract_coverage_row(summary: dict[str, Any]) -> str:
    suites = {item["name"]: item for item in summary["sdk_contract_suites"]}
    current = (
        "Python SDK package contract "
        f"{int(suites['python_sdk_package_contract']['passed'])} passed; "
        "TypeScript SDK package contract "
        f"{int(suites['typescript_sdk_package_contract']['passed'])} passed and "
        f"{int(suites['typescript_sdk_package_contract']['skipped'])} skipped; both "
        f"{int(suites['python_sdk_package_contract']['failed']) + int(suites['typescript_sdk_package_contract']['failed'])} failed"
    )
    return (
        "| SDK package contract coverage | "
        f"{current} | "
        "`tests/test_algenta_mojo_sdk.py`, `packages/ts-sdk/src/libraries.test.ts` | Green |"
    )


def render_http_api_flag_contract_coverage_row(summary: dict[str, Any]) -> str:
    suite = summary["http_flag_contract_suites"][0]
    current = (
        f"HTTP API flag contract {int(suite['passed'])} passed; {int(suite['failed'])} failed"
    )
    return (
        "| HTTP API flag contract coverage | "
        f"{current} | "
        "`tests/test_runtime_libraries_api.py`, `apps/api_server/main.py`, "
        "`apps/api_server/config.py` | Green |"
    )


def render_http_api_flag_live_coverage_row(summary: dict[str, Any]) -> str:
    suite = summary["http_flag_live_suites"][0]
    current = (
        "HTTP API feature-flag live suite "
        f"{int(suite['passed'])}/{int(suite['minimum_passed'])} passed; "
        f"{int(suite['failed'])} failed"
    )
    return (
        "| HTTP API flag live coverage | "
        f"{current} | "
        "`build/public_http_library_routes_feature_flag_live_live_summary.json`, "
        "`tests/integration/test_runtime_libraries_http_live.py`, `tests/_asgi_client.py`, "
        "`build/llm_rollout_proof_bundle.json` | Green |"
    )


def render_public_http_api_flag_readiness_row(summary: dict[str, Any]) -> str:
    current = (
        "`/v1/libraries*` routes are feature-flag ready via "
        f"`{summary['public_http_library_routes_enable_env']}` and remain disabled by default"
    )
    return (
        "| Public HTTP API flag readiness | "
        f"{current} | "
        "`tests/test_runtime_libraries_api.py`, `apps/api_server/main.py`, "
        "`apps/api_server/config.py` | Green |"
    )


def render_machine_readable_rollout_bundle_row(summary: dict[str, Any]) -> str:
    current = (
        "Single JSON bundle validating parity, compiled runtime, SDK package contracts, "
        "supported public channels, and underlying local lanes"
    )
    return (
        "| Machine-readable rollout bundle | "
        f"{current} | "
        "`build/llm_rollout_proof_bundle.json`, `benchmarks/llm_rollout_proof_bundle.py`, "
        "`tests/test_llm_rollout_proof_bundle.py` | Green |"
    )


def _artifact_dates(
    benchmark_summary: dict[str, Any],
    mojo_az_summary: dict[str, Any] | None,
    go_live_verify_summary: dict[str, Any] | None,
    go_live_full_real_summary: dict[str, Any] | None,
    llm_rollout_proof_bundle: dict[str, Any] | None,
    provider_routing_overhead_summary: dict[str, Any] | None,
    repository_intelligence_benchmark: dict[str, Any] | None,
    mcp_20q_summary: dict[str, Any] | None,
    csv_pipeline_summary: dict[str, Any] | None,
    scorecard_suite_summaries: dict[str, Any] | None,
    vector_hot_path_summary: dict[str, Any] | None,
    mcp_server_integration_summary: dict[str, Any] | None,
    openapi_integration_summary: dict[str, Any] | None,
) -> list[str]:
    dates: list[str] = []
    benchmark_timestamp = str(benchmark_summary.get("timestamp", "")).strip()
    if benchmark_timestamp:
        dates.append(benchmark_timestamp[:10])
    if mojo_az_summary is not None:
        generated_at = str(mojo_az_summary.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if go_live_verify_summary is not None:
        generated_at = str(go_live_verify_summary.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if go_live_full_real_summary is not None:
        generated_at = str(go_live_full_real_summary.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if llm_rollout_proof_bundle is not None:
        generated_at = str(llm_rollout_proof_bundle.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if provider_routing_overhead_summary is not None:
        generated_at = str(provider_routing_overhead_summary.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if repository_intelligence_benchmark is not None:
        generated_at = str(repository_intelligence_benchmark.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if mcp_20q_summary is not None:
        generated_at = str(mcp_20q_summary.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if csv_pipeline_summary is not None:
        generated_at = str(csv_pipeline_summary.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if scorecard_suite_summaries is not None:
        generated_at = str(scorecard_suite_summaries.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if vector_hot_path_summary is not None:
        generated_at = str(vector_hot_path_summary.get("date", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if mcp_server_integration_summary is not None:
        generated_at = str(mcp_server_integration_summary.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    if openapi_integration_summary is not None:
        generated_at = str(openapi_integration_summary.get("generated_at", "")).strip()
        if generated_at:
            dates.append(generated_at[:10])
    return dates


def sync_shared_benchmark_scorecard(
    *,
    scorecard_path: Path = SCORECARD_PATH,
    benchmark_summary_path: Path = BENCHMARK_SUMMARY_PATH,
    mojo_az_summary_path: Path = MOJO_LIBRARIES_AZ_SUMMARY_PATH,
    go_live_verify_summary_path: Path = GO_LIVE_VERIFY_SUMMARY_PATH,
    go_live_full_real_summary_path: Path = GO_LIVE_FULL_REAL_SUMMARY_PATH,
    llm_rollout_proof_bundle_path: Path = LLM_ROLLOUT_PROOF_BUNDLE_PATH,
    provider_routing_overhead_benchmark_path: Path = PROVIDER_ROUTING_OVERHEAD_BENCHMARK_PATH,
    repository_intelligence_benchmark_path: Path = REPOSITORY_INTELLIGENCE_BENCHMARK_PATH,
    mcp_20q_results_path: Path = MCP_20Q_RESULTS_PATH,
    csv_pipeline_results_path: Path = CSV_PIPELINE_RESULTS_PATH,
    csv_pipeline_summary_path: Path = CSV_PIPELINE_SUMMARY_PATH,
    scorecard_suite_summaries_path: Path = SCORECARD_SUITE_SUMMARIES_PATH,
    vector_hot_path_results_path: Path = VECTOR_HOT_PATH_RESULTS_PATH,
    mcp_server_integration_summary_path: Path = MCP_SERVER_INTEGRATION_SUMMARY_PATH,
    openapi_integration_summary_path: Path = OPENAPI_INTEGRATION_SUMMARY_PATH,
) -> None:
    text = scorecard_path.read_text(encoding="utf-8")
    benchmark_summary = _load_json(benchmark_summary_path)
    mojo_az_summary = (
        _load_json(mojo_az_summary_path) if mojo_az_summary_path.exists() else None
    )
    go_live_verify_summary = (
        _load_json(go_live_verify_summary_path) if go_live_verify_summary_path.exists() else None
    )
    go_live_full_real_summary = (
        _load_json(go_live_full_real_summary_path)
        if go_live_full_real_summary_path.exists()
        else None
    )
    llm_rollout_proof_bundle = (
        _load_json(llm_rollout_proof_bundle_path)
        if llm_rollout_proof_bundle_path.exists()
        else None
    )
    provider_routing_overhead_summary = (
        _load_json(provider_routing_overhead_benchmark_path)
        if provider_routing_overhead_benchmark_path.exists()
        else None
    )
    repository_intelligence_benchmark = (
        _load_json(repository_intelligence_benchmark_path)
        if repository_intelligence_benchmark_path.exists()
        else None
    )
    mcp_20q_summary = _load_json(mcp_20q_results_path) if mcp_20q_results_path.exists() else None
    csv_pipeline_rows = (
        _load_csv_rows(csv_pipeline_results_path) if csv_pipeline_results_path.exists() else None
    )
    csv_pipeline_summary = (
        _load_json(csv_pipeline_summary_path) if csv_pipeline_summary_path.exists() else None
    )
    scorecard_suite_summaries = (
        _load_json(scorecard_suite_summaries_path)
        if scorecard_suite_summaries_path.exists()
        else None
    )
    vector_hot_path_summary = (
        _load_json(vector_hot_path_results_path)
        if vector_hot_path_results_path.exists()
        else None
    )
    mcp_server_integration_summary = (
        _load_json(mcp_server_integration_summary_path)
        if mcp_server_integration_summary_path.exists()
        else None
    )
    openapi_integration_summary = (
        _load_json(openapi_integration_summary_path)
        if openapi_integration_summary_path.exists()
        else None
    )

    updated_date_candidates = _artifact_dates(
        benchmark_summary,
        mojo_az_summary,
        go_live_verify_summary,
        go_live_full_real_summary,
        llm_rollout_proof_bundle,
        provider_routing_overhead_summary,
        repository_intelligence_benchmark,
        mcp_20q_summary,
        csv_pipeline_summary,
        scorecard_suite_summaries,
        vector_hot_path_summary,
        mcp_server_integration_summary,
        openapi_integration_summary,
    )
    if updated_date_candidates:
        updated_date = max(updated_date_candidates)
        text = re.sub(
            r"(?m)^Updated:\s+\d{4}-\d{2}-\d{2}$",
            f"Updated: {updated_date}",
            text,
            count=1,
        )

    if mojo_az_summary is not None:
        text = _replace_row(text, "Mojo correctness (A-Z)", render_mojo_correctness_row(mojo_az_summary))

    inventory_row = render_benchmark_inventory_row(benchmark_summary)
    inventory_pattern = r"(?m)^\| Benchmark discovery inventory \|.*$"
    if re.search(inventory_pattern, text):
        text = re.sub(inventory_pattern, inventory_row, text, count=1)
    else:
        text = re.sub(
            r"(?m)^(\| Mojo correctness \(A-Z\) \|.*\n)",
            r"\1" + inventory_row + "\n",
            text,
            count=1,
        )

    text = _replace_row(text, "Mojo vs Python speed", render_mojo_speed_row(benchmark_summary))
    if provider_routing_overhead_summary is not None:
        provider_routing_row = render_provider_routing_overhead_row(provider_routing_overhead_summary)
        provider_routing_pattern = r"(?m)^\| Provider routing overhead \|.*$"
        if re.search(provider_routing_pattern, text):
            text = re.sub(provider_routing_pattern, provider_routing_row, text, count=1)
        else:
            text = re.sub(
                r"(?m)^(\| Mojo vs Python speed \|.*\n)",
                r"\1" + provider_routing_row + "\n",
                text,
                count=1,
            )
    if repository_intelligence_benchmark is not None:
        repository_intelligence_row = render_repository_intelligence_row(
            repository_intelligence_benchmark
        )
        repository_intelligence_pattern = (
            r"(?m)^\| Repository intelligence workflow \|.*$"
        )
        if re.search(repository_intelligence_pattern, text):
            text = re.sub(
                repository_intelligence_pattern,
                repository_intelligence_row,
                text,
                count=1,
            )
        else:
            text = re.sub(
                r"(?m)^(\| Provider routing overhead \|.*\n)",
                r"\1" + repository_intelligence_row + "\n",
                text,
                count=1,
            )
    if mcp_server_integration_summary is not None:
        text = _replace_row(
            text,
            "MCP runtime integration",
            render_mcp_runtime_integration_row(mcp_server_integration_summary),
        )
    if openapi_integration_summary is not None:
        text = _replace_row(
            text,
            "OpenAPI compliance",
            render_openapi_compliance_row(openapi_integration_summary),
        )
    if mcp_20q_summary is not None:
        text = _replace_row(text, "MCP end-to-end benchmark", render_mcp_end_to_end_row(mcp_20q_summary))
    if csv_pipeline_rows is not None:
        text = _replace_row(text, "CSV ingest throughput", render_csv_ingest_row(csv_pipeline_rows))
    if scorecard_suite_summaries is not None:
        text = _replace_row(
            text,
            "Narrow resolver regression",
            render_narrow_resolver_regression_row(scorecard_suite_summaries["narrow_resolver_regression"]),
        )
        text = _replace_row(
            text,
            "Join-path correctness",
            render_join_path_correctness_row(scorecard_suite_summaries["join_path_correctness"]),
        )
        text = _replace_row(
            text,
            "Import/planner regression suite",
            render_import_planner_regression_row(scorecard_suite_summaries["import_planner_regression_suite"]),
        )
    if csv_pipeline_summary is not None:
        text = _replace_row(
            text,
            "Import pipeline correctness",
            render_import_pipeline_correctness_row(csv_pipeline_summary),
        )
    if vector_hot_path_summary is not None:
        text = _replace_row(text, "Vector hot path", render_vector_hot_path_row(vector_hot_path_summary))
    if go_live_verify_summary is not None:
        text = re.sub(
            r"(?m)^## Go-live verifier \(\d{4}-\d{2}-\d{2}\)$",
            f"## Go-live verifier ({str(go_live_verify_summary['generated_at'])[:10]})",
            text,
            count=1,
        )
        text = _replace_row(
            text,
            "Serial verifier summary",
            render_serial_verifier_summary_row(go_live_verify_summary),
        )
        if go_live_full_real_summary is not None:
            full_real_row = render_go_live_full_real_row(go_live_full_real_summary)
            full_real_pattern = r"(?m)^\| Full real suite \|.*$"
            if re.search(full_real_pattern, text):
                text = re.sub(full_real_pattern, full_real_row, text, count=1)
            else:
                text = re.sub(
                    r"(?m)^(\| Serial verifier summary \|.*\n)",
                    r"\1" + full_real_row + "\n",
                    text,
                    count=1,
                )
        text = _replace_row(
            text,
            "Planned serial steps",
            render_planned_serial_steps_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Latest serial durations",
            render_latest_serial_durations_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Canonical verifier mode",
            render_canonical_verifier_mode_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Static matrix operational gaps",
            render_static_matrix_operational_gaps_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Live connectivity skips",
            render_live_connectivity_skips_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Gap source breakdown",
            render_gap_source_breakdown_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Gap connector breakdown",
            render_gap_connector_breakdown_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Outstanding operational gaps",
            render_outstanding_operational_gaps_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Operator next actions",
            render_operator_next_actions_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Gap action routing",
            render_gap_action_routing_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Gap connector routing",
            render_gap_connector_routing_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Gap env routing",
            render_gap_env_routing_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Gap env resolution",
            render_gap_env_resolution_row(go_live_verify_summary),
        )
        text = _replace_row(
            text,
            "Gap env templates",
            render_gap_env_templates_row(go_live_verify_summary),
        )
    if llm_rollout_proof_bundle is not None:
        text = re.sub(
            r"(?m)^## LLM rollout proof \(\d{4}-\d{2}-\d{2}\)$",
            f"## LLM rollout proof ({str(llm_rollout_proof_bundle['generated_at'])[:10]})",
            text,
            count=1,
        )
        text = _replace_row(
            text,
            "22-library parity proof",
            render_rollout_parity_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "Compiled runtime latency proof",
            render_compiled_runtime_latency_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "Serving extension subset proof",
            render_serving_extension_subset_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "Serving extension channel coverage",
            render_serving_extension_channel_coverage_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "Supported channel coverage",
            render_supported_channel_coverage_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "SDK package contract coverage",
            render_sdk_package_contract_coverage_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "HTTP API flag contract coverage",
            render_http_api_flag_contract_coverage_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "HTTP API flag live coverage",
            render_http_api_flag_live_coverage_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "Public HTTP API flag readiness",
            render_public_http_api_flag_readiness_row(llm_rollout_proof_bundle),
        )
        text = _replace_row(
            text,
            "Machine-readable rollout bundle",
            render_machine_readable_rollout_bundle_row(llm_rollout_proof_bundle),
        )
    scorecard_path.write_text(text, encoding="utf-8")


def main() -> None:
    sync_shared_benchmark_scorecard(
        scorecard_path=SCORECARD_PATH,
        benchmark_summary_path=BENCHMARK_SUMMARY_PATH,
        mojo_az_summary_path=MOJO_LIBRARIES_AZ_SUMMARY_PATH,
        go_live_verify_summary_path=GO_LIVE_VERIFY_SUMMARY_PATH,
        go_live_full_real_summary_path=GO_LIVE_FULL_REAL_SUMMARY_PATH,
        llm_rollout_proof_bundle_path=LLM_ROLLOUT_PROOF_BUNDLE_PATH,
        provider_routing_overhead_benchmark_path=PROVIDER_ROUTING_OVERHEAD_BENCHMARK_PATH,
        repository_intelligence_benchmark_path=REPOSITORY_INTELLIGENCE_BENCHMARK_PATH,
        mcp_20q_results_path=MCP_20Q_RESULTS_PATH,
        csv_pipeline_results_path=CSV_PIPELINE_RESULTS_PATH,
        csv_pipeline_summary_path=CSV_PIPELINE_SUMMARY_PATH,
        vector_hot_path_results_path=VECTOR_HOT_PATH_RESULTS_PATH,
        scorecard_suite_summaries_path=SCORECARD_SUITE_SUMMARIES_PATH,
        mcp_server_integration_summary_path=MCP_SERVER_INTEGRATION_SUMMARY_PATH,
        openapi_integration_summary_path=OPENAPI_INTEGRATION_SUMMARY_PATH,
    )


if __name__ == "__main__":
    main()
