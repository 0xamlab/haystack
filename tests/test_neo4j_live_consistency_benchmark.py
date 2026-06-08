from __future__ import annotations

from benchmarks import neo4j_live_consistency_benchmark as benchmark


def test_build_probe_config_from_env_uses_neo4j_defaults(monkeypatch) -> None:
    monkeypatch.setenv("DE_TEST_NEO4J_URI", "neo4j+s://graph.example.com")
    monkeypatch.setenv("DE_TEST_NEO4J_USERNAME", "neo4j")
    monkeypatch.delenv("DE_TEST_NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("DE_TEST_NEO4J_DATABASE", raising=False)

    config = benchmark._build_probe_config_from_env()

    assert config == {
        "uri": "neo4j+s://graph.example.com",
        "username": "neo4j",
        "password": "",
        "database": "neo4j",
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
