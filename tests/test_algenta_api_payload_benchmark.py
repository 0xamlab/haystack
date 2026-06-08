from __future__ import annotations

from benchmarks.algenta_api_payload_benchmark import run_benchmark


def test_algenta_api_payload_benchmark_reports_expected_shape() -> None:
    results = run_benchmark(iterations=5)

    assert results["iterations"] == 5
    for key in (
        "resolve_payload",
        "query_payload_from_resolve_output",
        "query_payload_from_exact_mapping",
        "plan_from_exact_mapping",
    ):
        entry = results[key]
        assert entry["cold_ms"] >= 0.0
        assert entry["warm_timings"]["p95_ms"] >= 0.0
        assert entry["result_keys"]
