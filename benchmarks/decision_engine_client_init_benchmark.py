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
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "decision_engine_client_init_benchmark.json"

_INIT_SNIPPET_TEMPLATE = """
import asyncio
import importlib
import json
import sys
import time
import warnings

warnings.filterwarnings("ignore", message='Field name "schema".*', category=UserWarning)

for module_name in list(sys.modules):
    if module_name == "decision_engine" or module_name.startswith("decision_engine."):
        sys.modules.pop(module_name, None)

start = time.perf_counter()
decision_engine = importlib.import_module("decision_engine")
client = getattr(decision_engine, {export_name!r})(api_key="de_test_init")
if {async_close!r}:
    asyncio.run(client.aclose())
else:
    client.close()
elapsed_ms = (time.perf_counter() - start) * 1000.0
print(json.dumps({{
    "elapsed_ms": elapsed_ms,
    "loaded_httpx": "httpx" in sys.modules,
    "loaded_facade": {facade_module!r} in sys.modules,
    "loaded_lazy_http_client": "decision_engine.lazy_http_client" in sys.modules,
}}))
"""


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


def _sample_client_init(
    *,
    export_name: str,
    facade_module: str,
    async_close: bool,
    iterations: int,
) -> list[dict[str, Any]]:
    env = {**os.environ, "PYTHONPATH": f"{PYTHON_SDK}:{PROJECT_ROOT}"}
    snippet = _INIT_SNIPPET_TEMPLATE.format(
        export_name=export_name,
        facade_module=facade_module,
        async_close=async_close,
    )
    samples: list[dict[str, Any]] = []
    for _ in range(iterations):
        output = subprocess.check_output(  # noqa: S603 - fixed interpreter command for repo benchmark
            [sys.executable, "-c", snippet],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
        )
        samples.append(json.loads(output))
    return samples


def _summarize_init_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    timings = [float(sample["elapsed_ms"]) for sample in samples]
    return {
        **_summarize_timing_samples(timings),
        "loads_httpx": all(bool(sample["loaded_httpx"]) for sample in samples),
        "loads_facade": all(bool(sample["loaded_facade"]) for sample in samples),
        "loads_lazy_http_client": all(
            bool(sample["loaded_lazy_http_client"]) for sample in samples
        ),
    }


def run_benchmark(*, iterations: int = 10) -> dict[str, Any]:
    sync_samples = _sample_client_init(
        export_name="DecisionEngineClient",
        facade_module="decision_engine.client_facade",
        async_close=False,
        iterations=iterations,
    )
    async_samples = _sample_client_init(
        export_name="AsyncDecisionEngineClient",
        facade_module="decision_engine.async_client_facade",
        async_close=True,
        iterations=iterations,
    )
    return {
        "iterations": iterations,
        "constructors": {
            "DecisionEngineClient": _summarize_init_samples(sync_samples),
            "AsyncDecisionEngineClient": _summarize_init_samples(async_samples),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark cold Decision Engine client construction without a request."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of fresh-process samples to collect per constructor.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the benchmark JSON artifact.",
    )
    args = parser.parse_args()

    result = run_benchmark(iterations=args.iterations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
