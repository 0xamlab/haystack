from __future__ import annotations

import sys
import types

from benchmarks.algenta_local_runtime_exact_benchmark import run_benchmark


class _FakePlan:
    def to_dict(self) -> dict[str, object]:
        return {
            "source_name": "orders",
            "metric_column": "revenue",
            "aggregation": "sum",
            "group_column": "product_line",
            "schema_revision": "schema_v1",
        }


class _FakeResolveOutput:
    def __init__(self) -> None:
        self.resolved_plan = _FakePlan()


class _FakeQueryOutput:
    def __init__(self) -> None:
        self.result_type = "table"


class _FakeVerifyOutput:
    def __init__(self) -> None:
        self.valid = True


class _FakeRegistration:
    def __init__(self) -> None:
        self.name = "orders"
        self.row_count = 4


class _FakeRuntime:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def connect(self, rows, *, name: str):
        assert name == "orders"
        assert len(rows) == 4
        return _FakeRegistration()

    def resolve(self, request: dict[str, object]):
        assert request == {"metric": "revenue", "group_by": "product_line"}
        return _FakeResolveOutput()

    def query(self, resolved):
        assert isinstance(resolved, _FakeResolveOutput)
        return _FakeQueryOutput()

    def verify(self, resolved):
        assert isinstance(resolved, _FakeResolveOutput)
        return _FakeVerifyOutput()


def test_algenta_local_runtime_exact_benchmark_reports_expected_shape(monkeypatch) -> None:
    fake_algenta = types.ModuleType("algenta")
    fake_algenta.Runtime = _FakeRuntime
    monkeypatch.setitem(sys.modules, "algenta", fake_algenta)

    results = run_benchmark(iterations=4)

    assert results["iterations"] == 4
    assert results["source_name"] == "orders"
    assert results["row_count"] == 4
    assert results["field_count"] > 0
    assert results["cold_round_trip_ms"] >= 0.0
    assert results["warm_resolve"]["p95_ms"] >= 0.0
    assert results["warm_query"]["mean_ms"] >= 0.0
    assert results["warm_verify"]["p90_ms"] >= 0.0
    assert results["resolved_plan"]["source_name"] == "orders"
    assert results["cold_query_result_type"] == "table"
    assert results["cold_verify_valid"] is True
