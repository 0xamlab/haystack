#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MOJO_ENV = ROOT / "mojo_env"
MOJO_BIN = MOJO_ENV / ".pixi" / "envs" / "default" / "bin" / "mojo"
ENGINE_DIR = ROOT / "mojo" / "engine"
TEST_ALL_LIBRARIES = ROOT / "mojo" / "tests" / "test_all_libraries.mojo"
MODULAR_HOME = MOJO_ENV / ".pixi" / "envs" / "default" / "share" / "max"
MODULAR_CACHE_DIR = ROOT / ".cache" / "modular"
MODULAR_DATA_DIR = ROOT / ".local" / "share"


def _run_test_all(timeout_seconds: int) -> dict[str, object]:
    run_env = {
        **os.environ,
        "MODULAR_HOME": str(MODULAR_HOME),
        "MODULAR_CACHE_DIR": str(MODULAR_CACHE_DIR),
        "XDG_DATA_HOME": str(MODULAR_DATA_DIR),
        "MODULAR_TELEMETRY_ENABLED": "0",
    }
    MODULAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MODULAR_DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(  # noqa: S603
            [str(MOJO_BIN), "run", f"-I{ENGINE_DIR}", str(TEST_ALL_LIBRARIES)],
            cwd=str(MOJO_ENV),
            env=run_env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "timed_out": True,
            "returncode": None,
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout_seconds}s",
        }
    return {
        "success": result.returncode == 0,
        "timed_out": False,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the authoritative runnable Mojo inventory against test and benchmark artifacts."
        ),
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=400,
        help="Required source-backed library threshold for the exposure gate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the audit report as JSON.",
    )
    parser.add_argument(
        "--run-test-all",
        action="store_true",
        help="Execute mojo/tests/test_all_libraries.mojo with the current local Mojo environment.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Timeout for --run-test-all.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    from apps.runtime.mojo_inventory import build_inventory_report

    args = _build_parser().parse_args(argv)
    report = build_inventory_report(threshold_target=args.threshold)
    payload = report.to_dict()
    if args.run_test_all:
        payload["test_all_execution"] = _run_test_all(args.timeout_seconds)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Mojo inventory audit")
        print(f"  source modules: {payload['source_module_count']}")
        print(
            "  source modules with public functions: "
            f"{payload['source_modules_with_public_functions_count']}"
        )
        print(f"  source public functions: {payload['source_public_function_count']}")
        print(f"  threshold target: {payload['threshold_target']}")
        print(f"  threshold met: {payload['threshold_met']}")
        if not payload["threshold_met"]:
            print(f"  threshold gap: {payload['threshold_gap']}")
        print(f"  test_all missing from source: {payload['test_all_missing_from_source_count']}")
        print(
            "  benchmark results missing from source: "
            f"{payload['benchmark_results_missing_from_source_count']}"
        )
        print(
            "  benchmark benches missing from source: "
            f"{payload['benchmark_benches_missing_from_source_count']}"
        )
        if args.run_test_all:
            execution = payload["test_all_execution"]
            print(f"  test_all success: {execution['success']}")
            print(f"  test_all timed_out: {execution['timed_out']}")
            print(f"  test_all returncode: {execution['returncode']}")

    return 0 if payload["threshold_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
