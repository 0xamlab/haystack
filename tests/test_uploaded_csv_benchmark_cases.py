from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS_DIR = ROOT / "benchmarks"
sys.path.insert(0, str(BENCHMARKS_DIR))

# ruff: noqa: E402
import uploaded_csv_api_warm_benchmark as warm_benchmark
import uploaded_csv_exact_benchmark as exact_benchmark
import uploaded_csv_spec_reconstruction_benchmark as spec_benchmark
from uploaded_csv_spec_reconstruction_benchmark import _build_hint_cases


def test_uploaded_csv_hint_cases_match_current_cross_source_expectations() -> None:
    cases = {case.label: case for case in _build_hint_cases()}

    assert cases["Q9"].dim_hint == "pos inventory type"
    assert cases["Q9"].exact_case.group_source == "POSNew"
    assert cases["Q9"].exact_case.group_column == "INVENTORY_TYPE"

    assert cases["Q10"].dim_hint == "pos ohvendname"
    assert cases["Q10"].exact_case.group_source == "POSNew"
    assert cases["Q10"].exact_case.group_column == "OHVENDNAME"


def test_uploaded_csv_exact_benchmark_initializes_mojo_runtime(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "dummy.csv"
    csv_path.write_text("metric\n1\n", encoding="utf-8")
    events: list[str] = []

    async def _fake_setup() -> str:
        events.append("setup")
        return "pool"

    async def _fake_teardown() -> None:
        events.append("teardown")

    async def _fake_reset_runtime_state(_registry_dir: Path) -> None:
        return None

    async def _fake_register_source(*_args, **_kwargs):
        return {"status": "registered", "row_count": 1}

    async def _fake_query_sources(*_args, **_kwargs):
        return SimpleNamespace(result=1.0, row_count=1, plan=[])

    monkeypatch.setattr(exact_benchmark, "SOURCE_FILES", {"Dummy": csv_path})
    monkeypatch.setattr(exact_benchmark, "_setup_mojo_runtime", _fake_setup)
    monkeypatch.setattr(exact_benchmark, "_teardown_mojo_runtime", _fake_teardown)
    monkeypatch.setattr(exact_benchmark, "_reset_runtime_state", _fake_reset_runtime_state)
    monkeypatch.setattr(exact_benchmark, "register_source", _fake_register_source)
    monkeypatch.setattr(exact_benchmark, "query_sources", _fake_query_sources)
    monkeypatch.setattr(
        exact_benchmark,
        "_build_cases",
        lambda: [
            exact_benchmark.ExactQueryCase(
                label="Q1",
                description="dummy",
                source_name="Dummy",
                metric_column="metric",
                group_source=None,
                group_column=None,
                edges=(),
            )
        ],
    )
    monkeypatch.setattr(exact_benchmark, "_ensure_case_tables", lambda _planner, _case: None)
    monkeypatch.setattr(
        exact_benchmark,
        "_expected_result",
        lambda _case, _tables: (1.0, {"matched_rows": 1, "conflicts": set()}),
    )
    monkeypatch.setattr(
        exact_benchmark.AutoPlanner,
        "from_registry",
        staticmethod(lambda *_args, **_kwargs: SimpleNamespace(tables={})),
    )

    summary = asyncio.run(exact_benchmark._run())

    assert summary["mojo_runtime_mode"] == "pool"
    assert events == ["setup", "teardown"]


def test_uploaded_csv_spec_benchmark_initializes_mojo_runtime(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "dummy.csv"
    csv_path.write_text("metric\n1\n", encoding="utf-8")
    events: list[str] = []
    threaded_calls: list[str] = []

    async def _fake_setup() -> str:
        events.append("setup")
        return "pool"

    async def _fake_teardown() -> None:
        events.append("teardown")

    async def _fake_reset_runtime_state(_registry_dir: Path) -> None:
        return None

    async def _fake_register_source(*_args, **_kwargs):
        return {"status": "registered", "row_count": 1}

    dummy_exact = exact_benchmark.ExactQueryCase(
        label="Q1",
        description="dummy",
        source_name="Dummy",
        metric_column="metric",
        group_source=None,
        group_column=None,
        edges=(),
    )
    dummy_hint = spec_benchmark.HintQueryCase(
        label="Q1",
        description="dummy",
        metric_hint="metric",
        dim_hint=None,
        preferred_source="Dummy",
        exact_case=dummy_exact,
    )
    dummy_plan = SimpleNamespace(
        metric_src="Dummy",
        metric_col="metric",
        group_src=None,
        group_col=None,
        join_hops=(),
        error="",
        steps=[],
        metric_conf=0.9,
        group_conf=0.0,
        path_confidence=0.0,
        join_conf=0.0,
    )

    def _fake_plan(**_kwargs):
        return dummy_plan

    def _fake_execute_plan(_plan, limit=None):
        return (1.0, 1, [])

    async def _fake_to_thread(func, /, *args, **kwargs):
        threaded_calls.append(getattr(func, "__name__", repr(func)))
        return func(*args, **kwargs)

    dummy_planner = SimpleNamespace(
        tables={},
        plan=_fake_plan,
        execute_plan=_fake_execute_plan,
    )

    monkeypatch.setattr(spec_benchmark, "SOURCE_FILES", {"Dummy": csv_path})
    monkeypatch.setattr(spec_benchmark, "_setup_mojo_runtime", _fake_setup)
    monkeypatch.setattr(spec_benchmark, "_teardown_mojo_runtime", _fake_teardown)
    monkeypatch.setattr(spec_benchmark, "_reset_runtime_state", _fake_reset_runtime_state)
    monkeypatch.setattr(spec_benchmark, "register_source", _fake_register_source)
    monkeypatch.setattr(spec_benchmark, "_build_hint_cases", lambda: [dummy_hint])
    monkeypatch.setattr(spec_benchmark, "_ensure_case_tables", lambda _planner, _case: None)
    monkeypatch.setattr(spec_benchmark, "_expected_result", lambda _case, _tables: (1.0, {}))
    monkeypatch.setattr(spec_benchmark.asyncio, "to_thread", _fake_to_thread)
    monkeypatch.setattr(
        spec_benchmark.AutoPlanner,
        "from_registry",
        staticmethod(lambda *_args, **_kwargs: dummy_planner),
    )

    summary = asyncio.run(spec_benchmark._run())

    assert summary["mojo_runtime_mode"] == "pool"
    assert events == ["setup", "teardown"]
    assert threaded_calls == ["_fake_plan", "_fake_execute_plan"]


def test_uploaded_csv_warm_benchmark_initializes_mojo_runtime(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "dummy.csv"
    csv_path.write_text("metric\n1\n", encoding="utf-8")
    events: list[str] = []

    async def _fake_setup() -> str:
        events.append("setup")
        return "pool"

    async def _fake_teardown() -> None:
        events.append("teardown")

    async def _fake_reset_runtime_state(_registry_dir: Path) -> None:
        return None

    async def _fake_register_source(*_args, **_kwargs):
        return {"status": "registered", "row_count": 1, "planner_prewarm_ms": 1.0}

    async def _fake_run_case(*_args, **_kwargs):
        return {
            "label": "Q1",
            "latency_ms": 1.0,
            "query_correct": True,
            "planner_cache_hit": True,
            "result_cache_hit": True,
            "resolved_source": "Dummy",
            "resolved_column": "metric",
            "confidence": 0.9,
            "rejection_reason": None,
        }

    dummy_exact = exact_benchmark.ExactQueryCase(
        label="Q1",
        description="dummy",
        source_name="Dummy",
        metric_column="metric",
        group_source=None,
        group_column=None,
        edges=(),
    )
    dummy_hint = spec_benchmark.HintQueryCase(
        label="Q1",
        description="dummy",
        metric_hint="metric",
        dim_hint=None,
        preferred_source="Dummy",
        exact_case=dummy_exact,
    )
    dummy_hint_two = spec_benchmark.HintQueryCase(
        label="Q2",
        description="dummy 2",
        metric_hint="metric",
        dim_hint=None,
        preferred_source="Dummy",
        exact_case=dummy_exact,
    )

    monkeypatch.setattr(warm_benchmark, "SOURCE_FILES", {"Dummy": csv_path})
    monkeypatch.setattr(warm_benchmark, "_setup_mojo_runtime", _fake_setup)
    monkeypatch.setattr(warm_benchmark, "_teardown_mojo_runtime", _fake_teardown)
    monkeypatch.setattr(warm_benchmark, "_reset_runtime_state", _fake_reset_runtime_state)
    monkeypatch.setattr(warm_benchmark, "register_source", _fake_register_source)
    monkeypatch.setattr(
        warm_benchmark,
        "_build_hint_cases",
        lambda: [dummy_hint, dummy_hint_two],
    )
    monkeypatch.setattr(warm_benchmark, "_run_case", _fake_run_case)
    monkeypatch.setattr(
        warm_benchmark.AutoPlanner,
        "from_registry",
        staticmethod(lambda *_args, **_kwargs: SimpleNamespace(tables={})),
    )

    summary = asyncio.run(warm_benchmark._run())

    assert summary["mojo_runtime_mode"] == "pool"
    assert events == ["setup", "teardown"]
