from __future__ import annotations

import sys
import types

from benchmarks.algenta_mojo_catalog_benchmark import run_benchmark


class _FakeDescriptor:
    def __init__(self, name: str, functions: tuple[str, ...]) -> None:
        self.name = name
        self.functions = functions


class _FakeCatalog:
    def __init__(self) -> None:
        self._modules = [
            _FakeDescriptor("ab_testing", ("sample_size_proportion", "power_analysis"))
        ]
        self.ab_testing = type(
            "_FakeModuleProxy",
            (),
            {"sample_size_proportion": lambda self: None, "power_analysis": lambda self: None},
        )()

    def list_modules(self) -> list[_FakeDescriptor]:
        return self._modules

    def list_functions(self, module_name: str) -> tuple[str, ...]:
        if module_name != "ab_testing":
            raise KeyError(module_name)
        return self._modules[0].functions

    def module(self, module_name: str) -> object:
        if module_name != "ab_testing":
            raise KeyError(module_name)
        return self.ab_testing


def test_algenta_mojo_catalog_benchmark_reports_expected_shape(monkeypatch) -> None:
    fake_algenta = types.ModuleType("algenta")
    fake_algenta.libraries = lambda **_: _FakeCatalog()
    monkeypatch.setitem(sys.modules, "algenta", fake_algenta)

    results = run_benchmark(iterations=4)

    assert results["iterations"] == 4
    assert results["module_count"] == 1
    assert results["cold_list_modules_ms"] >= 0.0
    assert results["warm_same_runtime_list_modules"]["mean_ms"] >= 0.0
    assert results["warm_new_runtime_list_modules"]["p90_ms"] >= 0.0
    assert results["warm_list_functions"]["p95_ms"] >= 0.0
    assert results["warm_module_lookup"]["mean_ms"] >= 0.0
    assert results["warm_function_accessor"]["p95_ms"] >= 0.0
