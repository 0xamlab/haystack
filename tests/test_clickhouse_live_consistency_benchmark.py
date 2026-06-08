from __future__ import annotations

from benchmarks import clickhouse_live_consistency_benchmark as benchmark


def test_summarize_series_reports_percentiles_and_bounds() -> None:
    summary = benchmark._summarize_series([10.0, 20.0, 30.0, 40.0])

    assert summary == {
        "count": 4,
        "values_ms": [10.0, 20.0, 30.0, 40.0],
        "min_ms": 10.0,
        "max_ms": 40.0,
        "mean_ms": 25.0,
        "median_ms": 25.0,
        "p90_ms": 40.0,
        "p95_ms": 40.0,
    }


def test_build_probe_config_from_env_uses_clickhouse_defaults(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DE_TEST_CLICKHOUSE_URL", "https://clickhouse.example.com:8443")
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_USER", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_CLICKHOUSE_DATABASE", raising=False)

    config = benchmark._build_probe_config_from_env()

    assert config == {
        "url": "https://clickhouse.example.com:8443",
        "user": "default",
        "password": "",
        "database": "default",
    }


def test_summarize_run_separates_cold_and_warm_paths() -> None:
    summary = benchmark._summarize_run([100.0, 20.0, 30.0, 40.0])

    assert summary["cold_first_ms"] == 100.0
    assert summary["all_ms"]["mean_ms"] == 47.5
    assert summary["warm_ms"] == {
        "count": 3,
        "values_ms": [20.0, 30.0, 40.0],
        "min_ms": 20.0,
        "max_ms": 40.0,
        "mean_ms": 30.0,
        "median_ms": 30.0,
        "p90_ms": 40.0,
        "p95_ms": 40.0,
    }
