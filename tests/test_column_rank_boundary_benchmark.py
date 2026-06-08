from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "tests" / "benchmark" / "bench_column_rank_boundary.py"
)
_SPEC = importlib.util.spec_from_file_location("bench_column_rank_boundary", _BENCHMARK_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load benchmark module from {_BENCHMARK_PATH}")
_BENCHMARK = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _BENCHMARK
_SPEC.loader.exec_module(_BENCHMARK)

_resolve_modes = _BENCHMARK._resolve_modes
run_mode_benchmark = _BENCHMARK.run_mode_benchmark


def test_resolve_modes_defaults_to_disabled_and_auto() -> None:
    assert _resolve_modes(include_force=False) == ["disabled", "auto"]
    assert _resolve_modes(include_force=True) == ["disabled", "auto", "force"]


def test_run_mode_benchmark_reports_scalar_batch_and_concurrency() -> None:
    class _FakeResolver:
        def __init__(self) -> None:
            self.scalar_calls = 0
            self.batch_calls = 0

        def resolve(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.scalar_calls += 1
            return SimpleNamespace(source="POS", column="UNIT_PRICE")

        def resolve_batch(self, requests, top_k=5):  # type: ignore[no-untyped-def]
            del top_k
            self.batch_calls += 1
            return [SimpleNamespace(source="POS", column="UNIT_PRICE") for _ in requests]

    class _FakePlanner:
        def __init__(self) -> None:
            self._vector_resolver = _FakeResolver()
            self.graph = {"POS": {"UNIT_PRICE": object(), "EXT_PRICE": object()}}
            self.mojo_engines = ["column_rank"]

    planner = _FakePlanner()
    result = run_mode_benchmark(
        planner,
        mode="auto",
        warmup=1,
        iterations=2,
        concurrency_workers=2,
        concurrency_tasks=4,
    )

    assert result["mode"] == "auto"
    assert result["resolver_class"] == "_FakeResolver"
    assert result["source_count"] == 1
    assert result["resolver_columns"] == 2
    assert result["graph_columns"] == 2
    assert result["scalar"]["n"] == 2.0
    assert result["batch"]["n"] == 2.0
    assert result["concurrency"]["tasks"] == 4.0
    assert result["probe"]["scalar_top_match"] == "POS.UNIT_PRICE"
    assert result["probe"]["batch_top_matches"] == ["POS.UNIT_PRICE"] * 6
    assert planner._vector_resolver.scalar_calls >= 3
    assert planner._vector_resolver.batch_calls >= 7
