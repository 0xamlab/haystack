from __future__ import annotations

import sys
import types

from benchmarks.algenta_local_connect_benchmark import run_benchmark


class _FakeRegistration:
    def __init__(self, name: str, row_count: int = 4) -> None:
        self.name = name
        self.row_count = row_count
        self.dataset_id = f"ds_{name}"


class _FakeRuntime:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def connect(self, rows, *, name: str):
        assert len(rows) == 4
        return _FakeRegistration(name)

    def connect_many(self, rows, *, names: list[str]):
        assert len(rows) == 2
        assert names == ["orders_a", "orders_b"]
        return [_FakeRegistration(name) for name in names]


def test_algenta_local_connect_benchmark_reports_expected_shape(monkeypatch) -> None:
    fake_algenta = types.ModuleType("algenta")
    fake_algenta.Runtime = _FakeRuntime
    monkeypatch.setitem(sys.modules, "algenta", fake_algenta)

    results = run_benchmark(iterations=4)

    assert results["iterations"] == 4
    assert results["row_count"] == 4
    assert results["field_count"] > 0
    assert results["cold_single_connect_ms"] >= 0.0
    assert results["warm_single_connect"]["mean_ms"] >= 0.0
    assert results["warm_connect_many"]["p90_ms"] >= 0.0
    assert results["single_registration"]["name"] == "orders"
    assert results["connect_many_names"] == ["orders_a", "orders_b"]
