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
  5. Run broad Mojo + uploaded-data benchmarks.

Run:
  PYTHONPATH=. python3 tests/integration/test_go_live_full_real.py
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_CONNECTIVITY_PATH = Path(__file__).resolve().with_name("test_go_live_connectivity_real.py")
_CONNECTIVITY_SPEC = importlib.util.spec_from_file_location("go_live_connectivity_real", _CONNECTIVITY_PATH)
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
    print(f"  {icon} {name} ({elapsed:.1f}s)")
    if not ok:
        lines = output.splitlines()
        tail = lines[-80:] if lines else ["<no output>"]
        print("    ── output tail ──")
        for line in tail:
            print(f"    │ {line}")
    return ok, elapsed, output


def run_live_suite_with_fresh_server(
    name: str,
    cmd: list[str],
    *,
    env_base: dict[str, str],
    timeout: int,
) -> tuple[bool, float]:
    tmp_root = Path(tempfile.mkdtemp(prefix="go-live-live-suite-"))
    api_server: subprocess.Popen[str] | None = None

    try:
        api_key, org_id = asyncio.run(seed_api_key(DEFAULT_DB_URL))
        last_start_error: Exception | None = None
        for attempt in range(1, 3):
            api_port = free_port()
            sources_dir = tmp_root / f"sources_{attempt}"
            sources_dir.mkdir(parents=True, exist_ok=True)
            env_live = {
                **env_base,
                "DE_BASE_URL": f"http://127.0.0.1:{api_port}",
                "DE_API_KEY": api_key,
                "ALGENTA_BASE_URL": f"http://127.0.0.1:{api_port}",
                "ALGENTA_API_KEY": api_key,
            }
            try:
                api_server = start_api_server(api_port, sources_dir, env_live)
                wait_for_http(
                    f"http://127.0.0.1:{api_port}/v1/health",
                    timeout=120.0,
                    proc=api_server,
                    log_path=getattr(api_server, "algenta_log_path", None),
                )
                print(f"  {PASS} Fresh API server ready on :{api_port} for org {org_id}")
                ok, elapsed, _ = run_suite(name, cmd, env=env_live, timeout=timeout)
                return ok, elapsed
            except Exception as exc:
                last_start_error = exc
                stop_process(api_server)
                api_server = None
                if attempt >= 2:
                    raise
                print(
                    f"  ⚠️ Fresh API server startup attempt {attempt} failed on :{api_port}; "
                    f"retrying once: {exc}"
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Full real go-live suite")
    parser.add_argument("--parallel-tasks", type=int, default=8, help="Parallel warm-query fanout for go-live connectivity test")
    parser.add_argument("--mojo-workers", type=int, default=4, help="Parallel workers for Mojo A-Z suite")
    parser.add_argument("--mojo-timeout", type=int, default=30, help="Per-library timeout for Mojo A-Z suite")
    args = parser.parse_args()

    print("\n" + "=" * 72)
    print("  FULL GO-LIVE REAL SUITE")
    print("=" * 72)

    results: list[tuple[str, bool, float]] = []

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
        ],
        env=env_base,
        timeout=900,
    )
    results.append(("Real local connectivity gate", ok, elapsed))
    if not ok:
        print("\nConnectivity gate failed. Aborting broader suite.")
        return 1

    # Phase 2: live suites, each behind a fresh server to avoid state poisoning.
    live_suites = [
        ("Live MCP integration", [sys.executable, "tests/integration/test_mcp_server.py"], 300),
        ("Live MCP runtime compatibility", [sys.executable, "tests/integration/test_mcp_runtime_live.py"], 420),
        ("Live Python SDK integration", [sys.executable, "tests/integration/test_python_sdk.py"], 300),
        ("Live Python Runtime integration", [sys.executable, "tests/integration/test_algenta_runtime_live.py"], 420),
        ("Live TypeScript Runtime integration", [sys.executable, "tests/integration/test_typescript_runtime_live.py"], 420),
        ("Live CLI integration", [sys.executable, "tests/integration/test_cli_full.py"], 300),
        ("Live local runtime integration", [sys.executable, "tests/integration/test_local_runtime_real.py"], 300),
        ("Real-data Mojo engines", [sys.executable, "tests/integration/test_mojo_engines_realdata.py"], 600),
    ]
    env_live_base = env_base | {
        "DE_MOJO_WORKERS": str(args.mojo_workers),
        "DE_MOJO_TIMEOUT": str(args.mojo_timeout),
    }
    for name, cmd, timeout in live_suites:
        ok, elapsed = run_live_suite_with_fresh_server(
            name,
            cmd,
            env_base=env_live_base,
            timeout=timeout,
        )
        results.append((name, ok, elapsed))

    # Phase 3: local benchmark/regression runs that do not require the live API server.
    local_suites = [
        ("Uploaded CSV exact benchmark", [sys.executable, "benchmarks/uploaded_csv_exact_benchmark.py"], 600),
        ("Uploaded CSV spec benchmark", [sys.executable, "benchmarks/uploaded_csv_spec_reconstruction_benchmark.py"], 600),
        ("Uploaded CSV warm benchmark", [sys.executable, "benchmarks/uploaded_csv_api_warm_benchmark.py"], 600),
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
        ("Source matrix runtime benchmark", [sys.executable, "benchmarks/source_matrix_runtime_benchmark.py"], 1200),
    ]
    for name, cmd, timeout in local_suites:
        ok, elapsed, _ = run_suite(name, cmd, env=env_live_base, timeout=timeout)
        results.append((name, ok, elapsed))

    # Phase 4: wide Mojo A-Z suite (does not need the API server)
    ok, elapsed, _ = run_suite(
        "Mojo libraries A-Z",
        [sys.executable, "tests/integration/test_mojo_libraries_az.py"],
        env=env_base | {
            "DE_MOJO_WORKERS": str(args.mojo_workers),
            "DE_MOJO_TIMEOUT": str(args.mojo_timeout),
        },
        timeout=900,
    )
    results.append(("Mojo libraries A-Z", ok, elapsed))

    failed = _print_summary(results)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
