from __future__ import annotations

from benchmarks.algenta_api_exact_resolve_benchmark import run_benchmark


def test_algenta_api_exact_resolve_benchmark_reports_expected_shape() -> None:
    results = run_benchmark(iterations=4)

    assert results["iterations"] == 4

    exact = results["exact_resolve"]
    assert exact["planner_mode"] == "runtime_exact_spec"
    assert exact["cold_ms"] >= 0.0
    assert exact["cold_source_schema_requests"] == 1
    assert exact["cold_resolve_requests"] == 0
    assert exact["warm_timings"]["p95_ms"] >= 0.0
    assert exact["warm_source_schema_requests"]["max"] == 0
    assert exact["warm_resolve_requests"]["max"] == 0

    fuzzy = results["fuzzy_resolve"]
    assert fuzzy["planner_mode"] == "runtime"
    assert fuzzy["cold_ms"] >= 0.0
    assert fuzzy["cold_source_schema_requests"] == 0
    assert fuzzy["cold_resolve_requests"] == 1
    assert fuzzy["warm_timings"]["p95_ms"] >= 0.0
    assert fuzzy["warm_source_schema_requests"]["max"] == 0
    assert fuzzy["warm_resolve_requests"]["min"] == 1
    assert fuzzy["warm_resolve_requests"]["max"] == 1
