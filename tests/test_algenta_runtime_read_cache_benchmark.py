from __future__ import annotations

from benchmarks.algenta_runtime_read_cache_benchmark import run_benchmark


def test_algenta_runtime_read_cache_benchmark_reports_expected_shape() -> None:
    results = run_benchmark(iterations=4)

    assert results["iterations"] == 4
    for operation in (
        "get_connector",
        "browse_connector",
        "list_connectors",
        "get_dataset",
        "list_datasets",
    ):
        entry = results[operation]
        assert entry["cold_ms"] >= 0.0
        assert entry["cold_requests"] == 1
        assert entry["warm_timings"]["p95_ms"] >= 0.0
        assert entry["warm_requests"]["max"] == 0
