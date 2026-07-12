from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGENTA_PACKAGE = PROJECT_ROOT / "packages" / "algenta"
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "algenta_import_benchmark.json"

_IMPORT_SNIPPET = """
import importlib
import sys
import time

for module_name in list(sys.modules):
    if module_name == "algenta" or module_name.startswith("algenta."):
        sys.modules.pop(module_name, None)

start = time.perf_counter()
importlib.import_module("algenta")
elapsed_ms = (time.perf_counter() - start) * 1000.0
print(elapsed_ms)
"""

_EXPORT_SNIPPET_TEMPLATE = """
import importlib
import json
import sys
import time

for module_name in list(sys.modules):
    if module_name == "algenta" or module_name.startswith("algenta."):
        sys.modules.pop(module_name, None)

start = time.perf_counter()
algenta = importlib.import_module("algenta")
getattr(algenta, {export_name!r})
elapsed_ms = (time.perf_counter() - start) * 1000.0
print(json.dumps({{
    "elapsed_ms": elapsed_ms,
    "loaded_runtime": (
        "algenta.runtime" in sys.modules or "algenta.runtime_facade" in sys.modules
    ),
    "loaded_runtime_modules": sorted(
        name
        for name in sys.modules
        if name == "algenta.runtime" or name == "algenta.runtime_facade"
    ),
    "loaded_runtime_errors": "algenta.runtime_errors" in sys.modules,
    "loaded_runtime_model_modules": sorted(
        name
        for name in sys.modules
        if name == "algenta.runtime_models" or name.startswith("algenta.runtime_model_")
    ),
    "loaded_runtime_support_modules": sorted(
        name
        for name in sys.modules
        if name in {{"algenta.runtime_execution_surface", "algenta.runtime_registration_surface"}}
    ),
    "loaded_map": "algenta.map" in sys.modules,
    "loaded_connector_modules": sorted(
        name
        for name in sys.modules
        if name == "algenta.runtime_connectors"
        or name == "algenta.runtime_connector_models"
        or name.startswith("algenta.runtime_connector_model_")
        or name == "algenta.runtime_connector_preview"
        or name == "algenta.runtime_surface_cache"
    ),
    "loaded_map_modules": sorted(
        name
        for name in sys.modules
        if name == "algenta.map" or name.startswith("algenta.map_")
    ),
    "loaded_mojo_modules": sorted(
        name
        for name in sys.modules
        if name == "algenta.mojo"
        or name == "algenta.mojo_runtime"
        or name == "algenta.mojo_entrypoints"
        or name == "algenta.mojo_errors"
    ),
}}))
"""


def _sample_import_ms(*, iterations: int) -> list[float]:
    env = {
        **os.environ,
        "PYTHONPATH": f"{ALGENTA_PACKAGE}:{PYTHON_SDK}:{PROJECT_ROOT}",
    }
    samples: list[float] = []
    for _ in range(iterations):
        output = subprocess.check_output(  # noqa: S603 - fixed interpreter command for repo benchmark
            [sys.executable, "-c", _IMPORT_SNIPPET],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
        )
        samples.append(float(output.strip()))
    return samples


def _sample_export_resolution(*, export_name: str, iterations: int) -> list[dict[str, Any]]:
    env = {
        **os.environ,
        "PYTHONPATH": f"{ALGENTA_PACKAGE}:{PYTHON_SDK}:{PROJECT_ROOT}",
    }
    samples: list[dict[str, Any]] = []
    snippet = _EXPORT_SNIPPET_TEMPLATE.format(export_name=export_name)
    for _ in range(iterations):
        output = subprocess.check_output(  # noqa: S603 - fixed interpreter command for repo benchmark
            [sys.executable, "-c", snippet],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
        )
        samples.append(json.loads(output))
    return samples


def _percentile_ms(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = int(percentile * (len(ordered) - 1))
    return ordered[index]


def _summarize_timing_samples(samples: list[float]) -> dict[str, Any]:
    return {
        "mean_ms": statistics.mean(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "p90_ms": _percentile_ms(samples, 0.90),
        "p95_ms": _percentile_ms(samples, 0.95),
    }


def _summarize_export_resolution(samples: list[dict[str, Any]]) -> dict[str, Any]:
    timings = [float(sample["elapsed_ms"]) for sample in samples]
    return {
        **_summarize_timing_samples(timings),
        "loads_runtime": all(bool(sample["loaded_runtime"]) for sample in samples),
        "runtime_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_runtime_modules", [])
            }
        ),
        "loads_runtime_models": all(
            bool(sample.get("loaded_runtime_model_modules")) for sample in samples
        ),
        "loads_runtime_errors": all(bool(sample["loaded_runtime_errors"]) for sample in samples),
        "runtime_model_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_runtime_model_modules", [])
            }
        ),
        "runtime_support_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_runtime_support_modules", [])
            }
        ),
        "loads_map": all(bool(sample["loaded_map"]) for sample in samples),
        "connector_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_connector_modules", [])
            }
        ),
        "map_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_map_modules", [])
            }
        ),
        "mojo_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_mojo_modules", [])
            }
        ),
    }


def run_benchmark(*, iterations: int = 10) -> dict[str, Any]:
    samples = _sample_import_ms(iterations=iterations)
    model_samples = _sample_export_resolution(export_name="QueryOutput", iterations=iterations)
    connector_model_samples = _sample_export_resolution(
        export_name="ConnectorMetadata",
        iterations=iterations,
    )
    map_data_samples = _sample_export_resolution(export_name="map_data", iterations=iterations)
    runtime_samples = _sample_export_resolution(export_name="Runtime", iterations=iterations)
    libraries_samples = _sample_export_resolution(export_name="libraries", iterations=iterations)
    mojo_runtime_samples = _sample_export_resolution(
        export_name="MojoRuntime",
        iterations=iterations,
    )
    return {
        "iterations": iterations,
        **_summarize_timing_samples(samples),
        "exports": {
            "QueryOutput": _summarize_export_resolution(model_samples),
            "ConnectorMetadata": _summarize_export_resolution(connector_model_samples),
            "map_data": _summarize_export_resolution(map_data_samples),
            "Runtime": _summarize_export_resolution(runtime_samples),
            "libraries": _summarize_export_resolution(libraries_samples),
            "MojoRuntime": _summarize_export_resolution(mojo_runtime_samples),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark cold import time for the algenta package."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of fresh-process imports.",
    )
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
