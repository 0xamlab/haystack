from __future__ import annotations

from benchmarks.decision_engine_client_init_benchmark import run_benchmark


def test_decision_engine_client_init_benchmark_reports_lazy_transport_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        "benchmarks.decision_engine_client_init_benchmark._sample_client_init",
        lambda *, export_name, facade_module, async_close, iterations: [
            {
                "elapsed_ms": 5.0 if export_name == "DecisionEngineClient" else 6.0,
                "loaded_httpx": False,
                "loaded_facade": True,
                "loaded_lazy_http_client": True,
            }
            for _ in range(iterations)
        ],
    )

    result = run_benchmark(iterations=4)

    assert result["iterations"] == 4
    assert result["constructors"]["DecisionEngineClient"]["mean_ms"] == 5.0
    assert result["constructors"]["DecisionEngineClient"]["loads_httpx"] is False
    assert result["constructors"]["DecisionEngineClient"]["loads_facade"] is True
    assert result["constructors"]["DecisionEngineClient"]["loads_lazy_http_client"] is True
    assert result["constructors"]["AsyncDecisionEngineClient"]["mean_ms"] == 6.0
    assert result["constructors"]["AsyncDecisionEngineClient"]["loads_httpx"] is False
    assert result["constructors"]["AsyncDecisionEngineClient"]["loads_facade"] is True
    assert result["constructors"]["AsyncDecisionEngineClient"]["loads_lazy_http_client"] is True
