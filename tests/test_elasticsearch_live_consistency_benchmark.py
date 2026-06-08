from __future__ import annotations

from benchmarks import elasticsearch_live_consistency_benchmark as benchmark


def test_build_probe_config_from_env_uses_elasticsearch_defaults(monkeypatch) -> None:
    monkeypatch.setenv("DE_TEST_ELASTICSEARCH_URL", "https://elastic.example.com:443")
    monkeypatch.setenv("DE_TEST_ELASTICSEARCH_API_KEY", "elastic-key")
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_INDEX", raising=False)
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_QUERY", raising=False)
    monkeypatch.delenv("DE_TEST_ELASTICSEARCH_LIMIT", raising=False)

    config = benchmark._build_probe_config_from_env()

    assert config == {
        "url": "https://elastic.example.com:443",
        "api_key": "elastic-key",
        "index": "",
        "query": "",
        "limit": 100,
    }


def test_summarize_run_separates_cold_and_warm_paths() -> None:
    summary = benchmark._summarize_run([120.0, 30.0, 40.0, 50.0])

    assert summary["cold_first_ms"] == 120.0
    assert summary["all_ms"]["mean_ms"] == 60.0
    assert summary["warm_ms"] == {
        "count": 3,
        "values_ms": [30.0, 40.0, 50.0],
        "min_ms": 30.0,
        "max_ms": 50.0,
        "mean_ms": 40.0,
        "median_ms": 40.0,
        "p90_ms": 50.0,
        "p95_ms": 50.0,
    }
