"""
Full go-live real-system suite.

This is intentionally not a smoke wrapper. It runs the existing real suites
that hit the live local stack, real files, real Mojo binaries, and the real
Python SDK/MCP layers.

Flow:
  1. Run the self-contained local connectivity gate.
  2. Seed a real API key into the local database.
  3. Start the real API server on localhost.
  4. Run live integration suites against that server.
  5. Run the feature-flagged HTTP runtime-library suite in-process.
  6. Validate the repo-root JavaScript workspace operator path.
  7. Regenerate the LLM rollout parity and compiled-runtime benchmarks.
  8. Emit the machine-readable LLM rollout proof bundle.
  9. Run broad Mojo + uploaded-data benchmarks.

Run:
  python3 tests/integration/test_go_live_full_real.py
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.integration.live_integration_artifacts import (  # noqa: E402
    LIVE_INTEGRATION_SUMMARY_ARTIFACTS,
    write_live_integration_summary,
)
from tests.integration.live_local_surface_env import (  # noqa: E402
    LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT,
)

_CONNECTIVITY_PATH = Path(__file__).resolve().with_name("test_go_live_connectivity_real.py")
_CONNECTIVITY_SPEC = importlib.util.spec_from_file_location(
    "go_live_connectivity_real", _CONNECTIVITY_PATH
)
if _CONNECTIVITY_SPEC is None or _CONNECTIVITY_SPEC.loader is None:
    raise RuntimeError(f"Unable to load connectivity helper module from {_CONNECTIVITY_PATH}")
_CONNECTIVITY = importlib.util.module_from_spec(_CONNECTIVITY_SPEC)
_CONNECTIVITY_SPEC.loader.exec_module(_CONNECTIVITY)

DEFAULT_DB_URL = _CONNECTIVITY.DEFAULT_DB_URL
DEFAULT_DB_URL_SYNC = _CONNECTIVITY.DEFAULT_DB_URL_SYNC
DEFAULT_REDIS_URL = _CONNECTIVITY.DEFAULT_REDIS_URL
free_port = _CONNECTIVITY.free_port
seed_api_key = _CONNECTIVITY.seed_api_key
start_api_server = _CONNECTIVITY.start_api_server
stop_process = _CONNECTIVITY.stop_process
wait_for_http = _CONNECTIVITY.wait_for_http

PASS = "✅"
FAIL = "❌"
SUITE_NAME = "go_live_full_real"
SUMMARY_ARTIFACT = LIVE_INTEGRATION_SUMMARY_ARTIFACTS[SUITE_NAME]

LIVE_SUITES: tuple[tuple[str, list[str], int], ...] = (
    ("Live MCP integration", [sys.executable, "tests/integration/test_mcp_server.py"], 300),
    (
        "Live MCP runtime compatibility",
        [sys.executable, "tests/integration/test_mcp_runtime_live.py"],
        420,
    ),
    (
        "Live Python SDK integration",
        [sys.executable, "tests/integration/test_python_sdk.py"],
        300,
    ),
    (
        "Live AlgentaClient integration",
        [sys.executable, "tests/integration/test_algenta_client_live.py"],
        300,
    ),
    (
        "Live Python Mojo library integration",
        [sys.executable, "tests/integration/test_algenta_mojo_library_live.py"],
        420,
    ),
    (
        "Live Python Runtime integration",
        [sys.executable, "tests/integration/test_algenta_runtime_live.py"],
        420,
    ),
    (
        "Live TypeScript Runtime integration",
        [sys.executable, "tests/integration/test_typescript_runtime_live.py"],
        420,
    ),
    (
        "Live TypeScript SDK client integration",
        [sys.executable, "tests/integration/test_typescript_sdk_client_live.py"],
        420,
    ),
    (
        "Live CLI and MCP runtime library integration",
        [sys.executable, "tests/integration/test_cli_mcp_runtime_libraries_live.py"],
        600,
    ),
    ("Live CLI integration", [sys.executable, "tests/integration/test_cli.py"], 300),
    (
        "Live local runtime integration",
        [sys.executable, "tests/integration/test_local_runtime_real.py"],
        300,
    ),
    (
        "Real-data Mojo engines",
        [sys.executable, "tests/integration/test_mojo_engines_realdata.py"],
        600,
    ),
)

LOCAL_SUITES: tuple[tuple[str, list[str], int], ...] = (
    ("Root JavaScript workspace check", ["make", "js-check"], 600),
    (
        "LLM rollout parity benchmark",
        [sys.executable, "benchmarks/llm_rollout_parity_benchmark.py"],
        600,
    ),
    (
        "LLM rollout compiled runtime benchmark",
        [sys.executable, "benchmarks/llm_compiled_runtime_benchmark.py"],
        600,
    ),
    (
        "Uploaded CSV exact benchmark",
        [sys.executable, "benchmarks/uploaded_csv_exact_benchmark.py"],
        600,
    ),
    (
        "Uploaded CSV spec benchmark",
        [sys.executable, "benchmarks/uploaded_csv_spec_reconstruction_benchmark.py"],
        600,
    ),
    (
        "Uploaded CSV warm benchmark",
        [sys.executable, "benchmarks/uploaded_csv_api_warm_benchmark.py"],
        600,
    ),
    (
        "Column-rank boundary benchmark",
        [
            sys.executable,
            "-m",
            "tests.benchmark.bench_column_rank_boundary",
            "--json",
            "--source-limit",
            "15",
            "--concurrency-workers",
            "8",
            "--concurrency-tasks",
            "1000",
        ],
        300,
    ),
    (
        "Source matrix runtime benchmark",
        [sys.executable, "benchmarks/source_matrix_runtime_benchmark.py"],
        1200,
    ),
)
EXPECTED_SUITE_COUNT = 1 + len(LIVE_SUITES) + 1 + len(LOCAL_SUITES) + 1 + 1


def _text_output(data: object) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return str(data)


def run_suite(
    name: str,
    cmd: list[str],
    *,
    env: dict[str, str],
    timeout: int,
) -> tuple[bool, float, str]:
    print(f"  … Starting {name}", flush=True)
    t0 = time.perf_counter()
    output = ""
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output_file:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                env={**os.environ, **env},
                stdout=output_file,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
            elapsed = time.perf_counter() - t0
            ok = proc.returncode == 0
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            ok = False
            output += f"\n[TIMEOUT after {timeout}s]"
        finally:
            output_file.seek(0)
            output = output_file.read() + output

    icon = PASS if ok else FAIL
    print(f"  {icon} {name} ({elapsed:.1f}s)", flush=True)
    if not ok:
        lines = output.splitlines()
        tail = lines[-80:] if lines else ["<no output>"]
        print("    ── output tail ──", flush=True)
        for line in tail:
            print(f"    │ {line}", flush=True)
    return ok, elapsed, output


def run_live_suite_with_fresh_server(
    name: str,
    cmd: list[str],
    *,
    env_base: dict[str, str],
    timeout: int,
) -> tuple[bool, float, str]:
    tmp_root = Path(tempfile.mkdtemp(prefix="go-live-live-suite-"))
    api_server: subprocess.Popen[str] | None = None

    try:
        print(f"  … Starting {name} with a fresh API server", flush=True)
        api_key, org_id = asyncio.run(seed_api_key(DEFAULT_DB_URL))
        last_start_error: Exception | None = None
        for attempt in range(1, 3):
            api_port = free_port()
            sources_dir = tmp_root / f"sources_{attempt}"
            runtime_dir = tmp_root / f"runtime_{attempt}"
            sources_dir.mkdir(parents=True, exist_ok=True)
            runtime_dir.mkdir(parents=True, exist_ok=True)
            env_live = {
                **env_base,
                "DE_BASE_URL": f"http://127.0.0.1:{api_port}",
                "DE_API_KEY": api_key,
                "ALGENTA_BASE_URL": f"http://127.0.0.1:{api_port}",
                "ALGENTA_API_KEY": api_key,
                "ALGENTA_RUNTIME_DIR": str(runtime_dir),
                "ALGENTA_SIMULATION_PERSIST_TRANSPORT": (
                    LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT
                ),
            }
            try:
                api_server = start_api_server(api_port, sources_dir, env_live)
                wait_for_http(
                    f"http://127.0.0.1:{api_port}/v1/health",
                    timeout=120.0,
                    proc=api_server,
                    log_path=getattr(api_server, "algenta_log_path", None),
                )
                print(f"  {PASS} Fresh API server ready on :{api_port} for org {org_id}", flush=True)
                ok, elapsed, output = run_suite(name, cmd, env=env_live, timeout=timeout)
                return ok, elapsed, output
            except Exception as exc:
                last_start_error = exc
                stop_process(api_server)
                api_server = None
                if attempt >= 2:
                    raise
                print(
                    f"  ⚠️ Fresh API server startup attempt {attempt} failed on :{api_port}; "
                    f"retrying once: {exc}",
                    flush=True,
                )
                time.sleep(1.0)
        if last_start_error is not None:
            raise last_start_error
        raise RuntimeError("Fresh API server startup failed without an explicit exception.")
    finally:
        stop_process(api_server)
        shutil.rmtree(tmp_root, ignore_errors=True)


def _print_summary(results: list[tuple[str, bool, float]]) -> int:
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed

    print("\n" + "=" * 72)
    print(f"Passed suites: {passed}")
    print(f"Failed suites: {failed}")
    if failed:
        print("Failed suite names:")
        for name, ok, _elapsed in results:
            if not ok:
                print(f"  - {name}")
    slowest = sorted(results, key=lambda item: item[2], reverse=True)
    print("Slowest suites:")
    for name, ok, elapsed in slowest[:10]:
        icon = PASS if ok else FAIL
        print(f"  - {icon} {name}: {elapsed:.1f}s")
    print("=" * 72)
    return failed


def _write_summary_artifact(results: list[tuple[str, bool, float]], *, completed: bool) -> Path:
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    slowest = [
        {"name": name, "ok": ok, "elapsed_seconds": round(elapsed, 3)}
        for name, ok, elapsed in sorted(results, key=lambda item: item[2], reverse=True)[:10]
    ]
    details = {
        "live_suite_count": len(LIVE_SUITES) + 1,
        "local_suite_count": len(LOCAL_SUITES),
        "top_level_suite_count": 3,
        "status": "complete" if completed else "incomplete",
        "completed_suite_count": len(results),
        "expected_suite_count": EXPECTED_SUITE_COUNT,
        "failed_suite_names": [name for name, ok, _ in results if not ok],
        "slowest_suites": slowest,
    }
    return write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_go_live_full_real.py",
        passed=passed,
        failed=failed,
        total=EXPECTED_SUITE_COUNT if completed else len(results),
        elapsed_seconds=sum(elapsed for _, _, elapsed in results),
        details=details,
    )


def _parse_live_suite_counts(output: str) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for key in counts:
        match = re.search(rf"{key.capitalize()}: (\d+)", output)
        if match:
            counts[key] = int(match.group(1))
    return counts


def _rollout_live_suite_summary(
    *,
    name: str,
    script: str,
    ok: bool,
    elapsed: float,
    output: str,
) -> dict[str, Any] | None:
    rollout_suite_names = {
        "tests/integration/test_algenta_mojo_library_live.py": {
            "name": "python_sdk_local_runtime",
            "channels": ["python_sdk"],
            "minimum_passed": 7,
        },
        "tests/integration/test_typescript_runtime_live.py": {
            "name": "typescript_sdk_local_runtime",
            "channels": ["typescript_sdk"],
            "minimum_passed": 2,
        },
        "tests/integration/test_cli_mcp_runtime_libraries_live.py": {
            "name": "local_runtime_cli_mcp_matrix",
            "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
            "minimum_passed": 11,
        },
        "tests/integration/test_runtime_libraries_http_live.py": {
            "name": "public_http_library_routes_feature_flag_live",
            "channels": ["http_api_feature_flag"],
            "minimum_passed": 4,
        },
    }
    metadata = rollout_suite_names.get(script)
    if metadata is None:
        return None

    counts = _parse_live_suite_counts(output)
    if ok and counts == {"passed": 0, "failed": 0, "skipped": 0}:
        raise ValueError(f"rollout live suite {name} did not emit a parseable summary")
    return {
        "name": metadata["name"],
        "status": "passed" if ok and counts["failed"] == 0 else "failed",
        "elapsed_seconds": round(elapsed, 3),
        "passed": counts["passed"],
        "failed": counts["failed"],
        "skipped": counts["skipped"],
        "channels": metadata["channels"],
        "minimum_passed": metadata["minimum_passed"],
    }


def _write_llm_rollout_proof_bundle(
    *,
    live_suite_results: list[dict[str, Any]],
    http_flag_live_suite_results: list[dict[str, Any]],
) -> tuple[bool, float]:
    started = time.perf_counter()
    try:
        from benchmarks.llm_rollout_proof_bundle import (
            DEFAULT_OUTPUT,
            SCORECARD_PATH,
            build_proof_bundle,
            sync_rollout_scorecard,
        )

        bundle = build_proof_bundle(
            run_live=False,
            refresh_artifacts=False,
            live_suite_results=live_suite_results,
            http_flag_live_suite_results=http_flag_live_suite_results,
        )
        DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        sync_rollout_scorecard(bundle)
        elapsed = time.perf_counter() - started
        print(f"  {PASS} LLM rollout proof bundle ({elapsed:.1f}s)")
        print(f"    │ Wrote {DEFAULT_OUTPUT}")
        print(f"    │ Synced {SCORECARD_PATH}")
        return True, elapsed
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        print(f"  {FAIL} LLM rollout proof bundle ({elapsed:.1f}s)")
        print(f"    │ {type(exc).__name__}: {exc}")
        return False, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Full real go-live suite")
    parser.add_argument(
        "--parallel-tasks",
        type=int,
        default=8,
        help="Parallel warm-query fanout for go-live connectivity test",
    )
    parser.add_argument(
        "--mojo-workers", type=int, default=4, help="Parallel workers for Mojo A-Z suite"
    )
    parser.add_argument(
        "--mojo-timeout", type=int, default=30, help="Per-library timeout for Mojo A-Z suite"
    )
    args = parser.parse_args()

    print("\n" + "=" * 72)
    print("  FULL GO-LIVE REAL SUITE")
    print("=" * 72)

    results: list[tuple[str, bool, float]] = []
    rollout_live_suite_results: list[dict[str, Any]] = []
    rollout_http_flag_live_suite_results: list[dict[str, Any]] = []
    completed = False

    try:
        # Phase 1: self-contained local connectivity gate
        env_base = {
            "PYTHONPATH": str(ROOT),
            "DATABASE_URL": DEFAULT_DB_URL,
            "DATABASE_URL_SYNC": DEFAULT_DB_URL_SYNC,
            "REDIS_URL": DEFAULT_REDIS_URL,
            "ARROW_USER_SIMD_LEVEL": os.environ.get("ARROW_USER_SIMD_LEVEL", "NONE"),
        }

        ok, elapsed, _ = run_suite(
            "Real local connectivity gate",
            [
                sys.executable,
                "tests/integration/test_go_live_connectivity_real.py",
                "--parallel-tasks",
                str(args.parallel_tasks),
                "--skip-external-validation",
                "--summary-name",
                "go_live_connectivity_local_only",
            ],
            env=env_base,
            timeout=900,
        )
        results.append(("Real local connectivity gate", ok, elapsed))
        if not ok:
            print("\nConnectivity gate failed. Aborting broader suite.", flush=True)
            return 1

        # Phase 2: live suites, each behind a fresh server to avoid state poisoning.
        env_live_base = env_base | {
            "DE_MOJO_WORKERS": str(args.mojo_workers),
            "DE_MOJO_TIMEOUT": str(args.mojo_timeout),
        }
        for name, cmd, timeout in LIVE_SUITES:
            ok, elapsed, output = run_live_suite_with_fresh_server(
                name,
                cmd,
                env_base=env_live_base,
                timeout=timeout,
            )
            results.append((name, ok, elapsed))
            rollout_summary = _rollout_live_suite_summary(
                name=name,
                script=cmd[1],
                ok=ok,
                elapsed=elapsed,
                output=output,
            )
            if rollout_summary is not None:
                if rollout_summary["name"] == "public_http_library_routes_feature_flag_live":
                    rollout_http_flag_live_suite_results.append(rollout_summary)
                else:
                    rollout_live_suite_results.append(rollout_summary)

        ok, elapsed, output = run_suite(
            "Live HTTP runtime library integration",
            [sys.executable, "tests/integration/test_runtime_libraries_http_live.py"],
            env=env_live_base,
            timeout=900,
        )
        results.append(("Live HTTP runtime library integration", ok, elapsed))
        rollout_summary = _rollout_live_suite_summary(
            name="Live HTTP runtime library integration",
            script="tests/integration/test_runtime_libraries_http_live.py",
            ok=ok,
            elapsed=elapsed,
            output=output,
        )
        if rollout_summary is not None:
            rollout_http_flag_live_suite_results.append(rollout_summary)

        # Phase 3: local benchmark/regression runs that do not require the live API server.
        for name, cmd, timeout in LOCAL_SUITES:
            suite_env = dict(env_live_base)
            if name == "Root JavaScript workspace check":
                suite_env["DE_SKIP_GO_LIVE_VERIFY"] = "1"
                suite_env.update(
                    {
                        "ALGENTA_TEST_START_API_SERVER": "1",
                        "ALGENTA_TEST_IGNORE_HOSTED_LIVE_CREDENTIALS": "1",
                        "DE_API_KEY": "",
                        "ALGENTA_API_KEY": "",
                        "DE_BASE_URL": "",
                        "ALGENTA_BASE_URL": "",
                        "ALGENTA_CONTROL_PLANE_URL": "",
                    }
                )
            ok, elapsed, _ = run_suite(name, cmd, env=suite_env, timeout=timeout)
            results.append((name, ok, elapsed))

        ok, elapsed = _write_llm_rollout_proof_bundle(
            live_suite_results=rollout_live_suite_results,
            http_flag_live_suite_results=rollout_http_flag_live_suite_results,
        )
        results.append(("LLM rollout proof bundle", ok, elapsed))

        # Phase 4: wide Mojo A-Z suite (does not need the API server)
        ok, elapsed, _ = run_suite(
            "Mojo libraries A-Z",
            [sys.executable, "tests/integration/test_mojo_libraries_az.py"],
            env=env_base
            | {
                "DE_MOJO_WORKERS": str(args.mojo_workers),
                "DE_MOJO_TIMEOUT": str(args.mojo_timeout),
            },
            timeout=900,
        )
        results.append(("Mojo libraries A-Z", ok, elapsed))
        completed = True

        failed = _print_summary(results)
        return 0 if failed == 0 else 1
    finally:
        artifact_path = _write_summary_artifact(results, completed=completed)
        print(f"Summary artifact: {artifact_path}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
