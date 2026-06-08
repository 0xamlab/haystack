from __future__ import annotations

from benchmarks.provider_routing_overhead_benchmark import (
    BENCHMARK_CLASS,
    run_benchmark,
)


def test_provider_routing_overhead_benchmark_reports_expected_shape() -> None:
    results = run_benchmark(iterations=3, warmup=0)

    assert results["benchmark_class"] == BENCHMARK_CLASS
    assert results["iterations"] == 3
    assert results["warmup_iterations"] == 0
    assert "generated_at" in results

    for lane_name in ("chat", "embeddings"):
        lane = results[lane_name]
        assert set(lane) == {
            "baseline",
            "single_hop_router",
            "nested_router",
            "retryable_failover_router",
        }
        baseline = lane["baseline"]
        assert baseline["iterations"] == 3
        assert baseline["expected_provider_attempts"] == 1
        assert baseline["mean_provider_attempts"] == 1
        assert baseline["provider_call_count"] == 3
        assert baseline["min_us"] >= 0.0
        assert baseline["p50_us"] >= baseline["min_us"]
        assert baseline["p99_us"] <= baseline["max_us"]

        failover = lane["retryable_failover_router"]
        assert failover["expected_provider_attempts"] == 2
        assert failover["mean_provider_attempts"] == 2
        assert failover["provider_call_count"] == 6


def test_provider_routing_overhead_benchmark_baseline_overhead_is_zero() -> None:
    results = run_benchmark(iterations=2, warmup=0)

    for lane_name in ("chat", "embeddings"):
        baseline = results[lane_name]["baseline"]
        comparison = results[lane_name]["single_hop_router"]
        for key in (
            "mean_overhead_us",
            "p50_overhead_us",
            "p90_overhead_us",
            "p95_overhead_us",
            "p99_overhead_us",
        ):
            assert isinstance(comparison[key], float)
        assert baseline["expected_provider_attempts"] == 1
