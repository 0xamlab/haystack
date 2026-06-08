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
PYTHON_SDK = PROJECT_ROOT / "packages" / "python-sdk"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "decision_engine_import_benchmark.json"

_IMPORT_SNIPPET = """
import importlib
import sys
import time
import warnings

warnings.filterwarnings("ignore", message='Field name "schema".*', category=UserWarning)

for module_name in list(sys.modules):
    if module_name == "decision_engine" or module_name.startswith("decision_engine."):
        sys.modules.pop(module_name, None)

start = time.perf_counter()
importlib.import_module("decision_engine")
elapsed_ms = (time.perf_counter() - start) * 1000.0
print(elapsed_ms)
"""

_EXPORT_SNIPPET_TEMPLATE = """
import importlib
import json
import sys
import time
import warnings

warnings.filterwarnings("ignore", message='Field name "schema".*', category=UserWarning)

preload_modules = {preload_modules!r}
for preload_module in preload_modules:
    importlib.import_module(preload_module)

for module_name in list(sys.modules):
    if module_name == "decision_engine" or module_name.startswith("decision_engine."):
        sys.modules.pop(module_name, None)

start = time.perf_counter()
decision_engine = importlib.import_module("decision_engine")
getattr(decision_engine, {export_name!r})
elapsed_ms = (time.perf_counter() - start) * 1000.0
loaded_model_modules = sorted(
    name
    for name in sys.modules
    if name == "decision_engine.models" or name.startswith("decision_engine.models_")
)
loaded_connector_surface_modules = sorted(
    name
    for name in sys.modules
    if name in {{
        "decision_engine.client_connector_surface",
        "decision_engine.async_client_connector_surface",
        "decision_engine.connector_surface_common",
    }}
)
loaded_service_surface_modules = sorted(
    name
    for name in sys.modules
    if name in {{
        "decision_engine.client_service_surface",
        "decision_engine.async_client_service_surface",
    }}
)
loaded_request_helper_modules = sorted(
    name
    for name in sys.modules
    if name in {{
        "decision_engine.request_helpers",
    }}
)
print(json.dumps({{
    "elapsed_ms": elapsed_ms,
    "loaded_client": "decision_engine.client" in sys.modules,
    "loaded_async_client": "decision_engine.async_client" in sys.modules,
    "loaded_client_facade": "decision_engine.client_facade" in sys.modules,
    "loaded_async_client_facade": "decision_engine.async_client_facade" in sys.modules,
    "loaded_models": bool(loaded_model_modules),
    "loaded_model_modules": loaded_model_modules,
    "loaded_connector_surfaces": bool(loaded_connector_surface_modules),
    "loaded_connector_surface_modules": loaded_connector_surface_modules,
    "loaded_service_surfaces": bool(loaded_service_surface_modules),
    "loaded_service_surface_modules": loaded_service_surface_modules,
    "loaded_request_helpers": bool(loaded_request_helper_modules),
    "loaded_request_helper_modules": loaded_request_helper_modules,
    "loaded_exceptions": "decision_engine.exceptions" in sys.modules,
    "loaded_httpx": "httpx" in sys.modules,
}}))
"""


def _sample_import_ms(*, iterations: int) -> list[float]:
    env = {**os.environ, "PYTHONPATH": f"{PYTHON_SDK}:{PROJECT_ROOT}"}
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


def _sample_export_resolution(
    *,
    export_name: str,
    iterations: int,
    preload_modules: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    env = {**os.environ, "PYTHONPATH": f"{PYTHON_SDK}:{PROJECT_ROOT}"}
    samples: list[dict[str, Any]] = []
    snippet = _EXPORT_SNIPPET_TEMPLATE.format(
        export_name=export_name,
        preload_modules=preload_modules,
    )
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
        "loads_client": all(bool(sample["loaded_client"]) for sample in samples),
        "loads_async_client": all(bool(sample["loaded_async_client"]) for sample in samples),
        "loads_client_facade": all(bool(sample["loaded_client_facade"]) for sample in samples),
        "loads_async_client_facade": all(
            bool(sample["loaded_async_client_facade"]) for sample in samples
        ),
        "loads_models": all(bool(sample["loaded_models"]) for sample in samples),
        "model_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_model_modules", [])
            }
        ),
        "loads_connector_surfaces": all(
            bool(sample["loaded_connector_surfaces"]) for sample in samples
        ),
        "connector_surface_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_connector_surface_modules", [])
            }
        ),
        "loads_service_surfaces": all(
            bool(sample["loaded_service_surfaces"]) for sample in samples
        ),
        "service_surface_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_service_surface_modules", [])
            }
        ),
        "loads_request_helpers": all(bool(sample["loaded_request_helpers"]) for sample in samples),
        "request_helper_modules": sorted(
            {
                module_name
                for sample in samples
                for module_name in sample.get("loaded_request_helper_modules", [])
            }
        ),
        "loads_exceptions": all(bool(sample["loaded_exceptions"]) for sample in samples),
        "loads_httpx": all(bool(sample["loaded_httpx"]) for sample in samples),
    }


def run_benchmark(*, iterations: int = 10) -> dict[str, Any]:
    samples = _sample_import_ms(iterations=iterations)
    decision_envelope_samples = _sample_export_resolution(
        export_name="DecisionEnvelope",
        iterations=iterations,
    )
    decision_envelope_preloaded_samples = _sample_export_resolution(
        export_name="DecisionEnvelope",
        iterations=iterations,
        preload_modules=("pydantic",),
    )
    query_result_samples = _sample_export_resolution(
        export_name="QueryResult",
        iterations=iterations,
    )
    query_result_preloaded_samples = _sample_export_resolution(
        export_name="QueryResult",
        iterations=iterations,
        preload_modules=("pydantic",),
    )
    connector_info_samples = _sample_export_resolution(
        export_name="ConnectorInfo",
        iterations=iterations,
    )
    connector_info_preloaded_samples = _sample_export_resolution(
        export_name="ConnectorInfo",
        iterations=iterations,
        preload_modules=("pydantic",),
    )
    async_client_samples = _sample_export_resolution(
        export_name="AsyncDecisionEngineClient",
        iterations=iterations,
    )
    client_samples = _sample_export_resolution(
        export_name="DecisionEngineClient",
        iterations=iterations,
    )
    return {
        "iterations": iterations,
        **_summarize_timing_samples(samples),
        "exports": {
            "DecisionEnvelope": {
                **_summarize_export_resolution(decision_envelope_samples),
                "pydantic_preloaded": _summarize_export_resolution(
                    decision_envelope_preloaded_samples
                ),
            },
            "QueryResult": {
                **_summarize_export_resolution(query_result_samples),
                "pydantic_preloaded": _summarize_export_resolution(query_result_preloaded_samples),
            },
            "ConnectorInfo": {
                **_summarize_export_resolution(connector_info_samples),
                "pydantic_preloaded": _summarize_export_resolution(
                    connector_info_preloaded_samples
                ),
            },
            "AsyncDecisionEngineClient": _summarize_export_resolution(async_client_samples),
            "DecisionEngineClient": _summarize_export_resolution(client_samples),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark cold import time for the decision_engine package root."
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
