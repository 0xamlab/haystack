from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = PROJECT_ROOT / "packages" / "algenta-core"
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "algenta_mojo_catalog_benchmark.json"


def _ensure_package_paths() -> None:
    for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(PROJECT_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _percentile_ms(samples: list[float], percentile: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = int(percentile * (len(ordered) - 1))
    return ordered[index]


def _sample_ms(fn: Callable[[], Any], iterations: int) -> list[float]:
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples


def _summarize_ms(samples: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.mean(samples) if samples else 0.0,
        "min_ms": min(samples) if samples else 0.0,
        "max_ms": max(samples) if samples else 0.0,
        "p90_ms": _percentile_ms(samples, 0.90),
        "p95_ms": _percentile_ms(samples, 0.95),
    }


def run_benchmark(*, iterations: int = 30) -> dict[str, Any]:
    _ensure_package_paths()

    from algenta import libraries

    cold_start = time.perf_counter()
    catalog = libraries(mode="local", auto_start_daemon=False)
    modules = catalog.list_modules()
    cold_ms = (time.perf_counter() - cold_start) * 1000.0

    same_runtime = _sample_ms(catalog.list_modules, iterations)
    new_runtime = _sample_ms(
        lambda: libraries(mode="local", auto_start_daemon=False).list_modules(),
        iterations,
    )

    list_functions_summary: dict[str, float] | None = None
    module_lookup_summary: dict[str, float] | None = None
    function_accessor_summary: dict[str, float] | None = None
    if modules:
        module_name = modules[0].name
        list_functions_summary = _summarize_ms(
            _sample_ms(lambda: catalog.list_functions(module_name), iterations)
        )
        module_lookup_summary = _summarize_ms(
            _sample_ms(lambda: catalog.module(module_name), iterations)
        )
        first_function = modules[0].functions[0] if modules[0].functions else None
        if first_function is not None:
            module_proxy = catalog.module(module_name)
            function_accessor_summary = _summarize_ms(
                _sample_ms(lambda: getattr(module_proxy, first_function), iterations)
            )

    return {
        "iterations": iterations,
        "module_count": len(modules),
        "cold_list_modules_ms": cold_ms,
        "warm_same_runtime_list_modules": _summarize_ms(same_runtime),
        "warm_new_runtime_list_modules": _summarize_ms(new_runtime),
        "warm_list_functions": list_functions_summary,
        "warm_module_lookup": module_lookup_summary,
        "warm_function_accessor": function_accessor_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the public algenta Mojo catalog.")
    parser.add_argument("--iterations", type=int, default=30, help="Samples per warm path.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the benchmark JSON artifact.",
    )
    args = parser.parse_args()

    results = run_benchmark(iterations=args.iterations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
