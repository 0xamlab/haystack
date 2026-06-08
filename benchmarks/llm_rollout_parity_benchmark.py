from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.llm_compiled_runtime_benchmark import TARGET_MODULES  # noqa: E402
from tests.llm_rollout_matrix import LLM_ROLLOUT_FUNCTIONS_BY_MODULE  # noqa: E402

DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "build" / "llm_rollout_parity_benchmark.json"
DEFAULT_OUTPUT_TXT = PROJECT_ROOT / "build" / "llm_rollout_parity_benchmark.txt"
_MODULE_TO_BENCH_LIB = {
    "text.tokenizer": "text_tokenizer",
    "vector_kernels.ranker": "vector_kernels_ranker",
    "vector_kernels.table": "vector_kernels_table",
}


def target_bench_libs() -> tuple[str, ...]:
    return tuple(
        _MODULE_TO_BENCH_LIB.get(module_name, module_name)
        for module_name in TARGET_MODULES
    )


def expected_library_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for module_name, functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
        counts[_MODULE_TO_BENCH_LIB.get(module_name, module_name)] = len(functions)
    return counts


def validate_rollout_summary(summary: dict[str, Any]) -> None:
    expected_counts = expected_library_counts()
    expected_libs = set(expected_counts)
    actual_libraries = summary.get("libraries")
    if not isinstance(actual_libraries, list):
        raise ValueError("benchmark summary is missing the libraries list")

    actual_libs = {str(item.get("lib", "")) for item in actual_libraries}
    if actual_libs != expected_libs:
        missing = sorted(expected_libs - actual_libs)
        extra = sorted(actual_libs - expected_libs)
        raise ValueError(
            f"rollout benchmark summary library mismatch: missing={missing}, extra={extra}"
        )

    if int(summary.get("n_libraries", 0)) != len(expected_libs):
        raise ValueError(
            f"expected {len(expected_libs)} libraries, found {summary.get('n_libraries')}"
        )

    total_functions_compared = int(summary.get("total_functions_compared", 0))
    if total_functions_compared != sum(expected_counts.values()):
        raise ValueError(
            "rollout benchmark compared-function count mismatch: "
            f"expected {sum(expected_counts.values())}, found {total_functions_compared}"
        )

    for item in actual_libraries:
        lib = str(item["lib"])
        expected_count = expected_counts[lib]
        if item.get("status") != "ok":
            raise ValueError(
                f"benchmark summary reported non-ok status for {lib}: "
                f"{item.get('status')}"
            )
        if int(item.get("n_functions", 0)) != expected_count:
            raise ValueError(
                f"benchmark summary n_functions mismatch for {lib}: "
                f"expected {expected_count}, found {item.get('n_functions')}"
            )
        if int(item.get("n_compared", 0)) != expected_count:
            raise ValueError(
                f"benchmark summary n_compared mismatch for {lib}: "
                f"expected {expected_count}, found {item.get('n_compared')}"
            )


def run_rollout_benchmark(output_json: Path, output_txt: Path) -> int:
    env = os.environ.copy()
    env["DE_BENCH_LIBS"] = ",".join(target_bench_libs())
    env["DE_BENCH_SUMMARY_JSON"] = str(output_json)
    env["DE_BENCH_SUMMARY_TXT"] = str(output_txt)
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(PROJECT_ROOT / "tests" / "benchmark_mojo_vs_python.py")],
        cwd=str(PROJECT_ROOT),
        env=env,
        check=False,
    )
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the dedicated LLM rollout parity benchmark via the canonical "
            "Mojo-vs-Python harness."
        )
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
        help=f"Summary JSON artifact path (default: {DEFAULT_OUTPUT_JSON})",
    )
    parser.add_argument(
        "--output-txt",
        type=Path,
        default=DEFAULT_OUTPUT_TXT,
        help=f"Summary text artifact path (default: {DEFAULT_OUTPUT_TXT})",
    )
    args = parser.parse_args()

    exit_code = run_rollout_benchmark(args.output_json, args.output_txt)
    if exit_code != 0:
        return exit_code

    summary = json.loads(args.output_json.read_text(encoding="utf-8"))
    validate_rollout_summary(summary)

    print()
    print("Validated rollout parity benchmark artifact:")
    print(f"  json: {args.output_json}")
    print(f"  txt:  {args.output_txt}")
    print(f"  libraries: {summary['n_libraries']}")
    print(f"  functions compared: {summary['total_functions_compared']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
