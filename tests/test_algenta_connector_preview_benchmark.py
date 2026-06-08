from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_benchmark_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "benchmarks" / "algenta_connector_preview_benchmark.py"
    spec = importlib.util.spec_from_file_location(
        "algenta_connector_preview_benchmark", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_algenta_connector_preview_benchmark_reports_request_reduction() -> None:
    module = _load_benchmark_module()
    result = module.run_benchmark(iterations=5)

    assert result["iterations"] == 5
    assert result["test_inline_preview"]["requests_per_call"] == {
        "direct": 1,
        "fallback": 4,
        "reduction_x": 4.0,
    }
    assert result["browse_inline_preview"]["requests_per_call"] == {
        "direct": 1,
        "fallback": 5,
        "reduction_x": 5.0,
    }

    for group in ("test_inline_preview", "browse_inline_preview"):
        assert result[group]["direct"]["mean_ms"] >= 0.0
        assert result[group]["fallback"]["mean_ms"] >= 0.0
        adaptive = result[group]["adaptive_fallback"]
        assert adaptive["timings"]["mean_ms"] >= 0.0
        assert (
            adaptive["requests_per_call"]["first"] > adaptive["requests_per_call"]["steady_state"]
        )

    test_adaptive = result["test_inline_preview"]["adaptive_fallback"]["requests_per_call"]
    assert test_adaptive["first"] == 4
    assert test_adaptive["steady_state"] == 3
    assert test_adaptive["mean"] == pytest.approx(3.2)
    assert test_adaptive["reduction_vs_cold_x"] == pytest.approx(4 / 3)

    browse_adaptive = result["browse_inline_preview"]["adaptive_fallback"]["requests_per_call"]
    assert browse_adaptive["first"] == 5
    assert browse_adaptive["steady_state"] == 4
    assert browse_adaptive["mean"] == pytest.approx(4.2)
    assert browse_adaptive["reduction_vs_cold_x"] == pytest.approx(5 / 4)
