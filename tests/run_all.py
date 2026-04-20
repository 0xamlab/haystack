"""
Master test runner — executes every integration test module in sequence
and produces a unified pass/fail report.

Usage:
  python tests/run_all.py                    # all integration tests
  python tests/run_all.py --fast             # skip slow/load tests
  python tests/run_all.py --suite csv        # only CSV pipeline tests
  python tests/run_all.py --suite e2e        # only the complete E2E suite

Environment variables forwarded to each subprocess:
  DE_BASE_URL   (default: http://localhost:8000)
  DE_API_KEY    (default: dev seed key)

Prerequisites: same as any individual test module (see each file's docstring).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

ROOT       = Path(__file__).resolve().parent.parent
TESTS_DIR  = ROOT / "tests" / "integration"

# ─── test catalogue ──────────────────────────────────────────────────────────
# Each entry: (filename, suite_tags, timeout_seconds)
TESTS: list[tuple[str, set[str], int]] = [
    # ── fast / core ───────────────────────────────────────────────────────────
    ("test_api_live.py",       {"core", "fast"},               120),
    ("test_auth_security.py",  {"core", "fast", "security"},   120),
    ("test_middleware.py",     {"core", "fast"},               120),
    ("test_openapi.py",        {"core", "fast", "schema"},     120),
    ("test_services.py",       {"core", "fast"},               120),
    # ── simulation engines ────────────────────────────────────────────────────
    ("test_all_engines.py",    {"engines"},                    300),
    ("test_templates.py",      {"engines", "templates"},       300),
    # ── data layer ────────────────────────────────────────────────────────────
    ("test_database.py",       {"data", "db"},                 120),
    ("test_redis.py",          {"data", "redis"},              120),
    ("test_connectors.py",     {"data", "connectors"},         120),
    ("test_csv_pipeline.py",   {"data", "csv"},                300),
    ("test_go_live_connectivity_real.py", {"go_live", "connectors", "data", "core", "mcp"}, 900),
    ("test_go_live_full_real.py", {"go_live", "real", "full", "connectors", "data", "core", "mcp", "sdk", "mojo", "az"}, 1800),
    # ── features ─────────────────────────────────────────────────────────────
    ("test_jobs.py",           {"jobs"},                       180),
    ("test_exports.py",        {"exports"},                    180),
    ("test_mcp_server.py",     {"mcp"},                        120),
    ("test_python_sdk.py",     {"sdk"},                        120),
    ("test_benchmarks.py",     {"benchmarks"},                 300),
    # ── infrastructure ────────────────────────────────────────────────────────
    ("test_mojo_pool.py",      {"infra", "mojo"},              120),
    # ── CLI ───────────────────────────────────────────────────────────────────
    ("test_cli.py",            {"cli"},                        120),
    # ── load ─────────────────────────────────────────────────────────────────
    ("test_load.py",           {"load", "slow"},               300),
    # ── comprehensive E2E (this repo's phase 21) ──────────────────────────────
    ("test_e2e_complete.py",          {"e2e", "csv", "engines", "core"}, 600),
    # ── Mojo engines with real CSV business data (phase 22) ───────────────────
    ("test_mojo_engines_realdata.py", {"mojo", "engines", "csv", "data"},  300),
    # ── All Mojo libraries A-Z (phase 22b) — 244 libs × 2414 fn tests ─────────
    ("test_mojo_libraries_az.py",    {"mojo", "libraries", "az"},          600),
]

SLOW_TAGS = {"load", "slow"}


# ─── result container ────────────────────────────────────────────────────────

class TestResult(NamedTuple):
    name:     str
    passed:   int
    failed:   int
    skipped:  int
    duration: float
    exit_code: int
    output:   str


# ─── output parsers ──────────────────────────────────────────────────────────

def _parse_counts(output: str) -> tuple[int, int, int]:
    """Extract (passed, failed, skipped) from test output."""
    passed = failed = skipped = 0

    # Prefer the summary block "Passed:  N" style
    m = re.search(r"Passed[:\s]+(\d+)", output, re.IGNORECASE)
    if m:
        passed = int(m.group(1))
    m = re.search(r"Failed[:\s]+(\d+)", output, re.IGNORECASE)
    if m:
        failed = int(m.group(1))
    m = re.search(r"Skipped[:\s]+(\d+)", output, re.IGNORECASE)
    if m:
        skipped = int(m.group(1))

    # Fall back: count ✅ / ❌ / ⏭️ lines
    if passed == 0 and failed == 0:
        passed  = output.count("✅")
        failed  = output.count("❌")
        skipped = output.count("⏭")

    return passed, failed, skipped


# ─── runner ──────────────────────────────────────────────────────────────────

def run_test(script: Path, timeout: int, env: dict) -> TestResult:
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **env},
        )
        duration  = time.perf_counter() - t0
        output    = proc.stdout + proc.stderr
        passed, failed, skipped = _parse_counts(output)

        # If we can't parse counts but the script exited 0, treat as 1 pass
        if passed == 0 and failed == 0 and proc.returncode == 0:
            passed = 1

        return TestResult(
            name=script.name,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration=duration,
            exit_code=proc.returncode,
            output=output,
        )

    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - t0
        return TestResult(
            name=script.name,
            passed=0,
            failed=1,
            skipped=0,
            duration=duration,
            exit_code=-1,
            output=f"TIMED OUT after {timeout}s",
        )
    except Exception as exc:
        duration = time.perf_counter() - t0
        return TestResult(
            name=script.name,
            passed=0,
            failed=1,
            skipped=0,
            duration=duration,
            exit_code=-1,
            output=str(exc),
        )


# ─── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Decision Engine master test runner")
    parser.add_argument(
        "--suite", metavar="TAG",
        help="Only run tests whose suite tags include TAG (e.g. csv, e2e, core, engines)",
    )
    parser.add_argument(
        "--fast", action="store_true",
        help="Skip tests tagged 'slow' or 'load'",
    )
    parser.add_argument(
        "--file", metavar="NAME",
        help="Run only this test file (e.g. test_e2e_complete.py)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print full output for each test module",
    )
    parser.add_argument(
        "--base-url", default=os.environ.get("DE_BASE_URL", "http://localhost:8000"),
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key", default=os.environ.get("DE_API_KEY", "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU"),
        help="API key",
    )
    args = parser.parse_args()

    env = {
        "DE_BASE_URL": args.base_url,
        "DE_API_KEY":  args.api_key,
        "PYTHONPATH":  str(ROOT),
    }

    # ── filter test list ──────────────────────────────────────────────────────
    selected: list[tuple[str, set[str], int]] = []
    for filename, tags, timeout in TESTS:
        if args.file and args.file != filename:
            continue
        if args.fast and tags & SLOW_TAGS:
            continue
        if args.suite and args.suite not in tags:
            continue
        script = TESTS_DIR / filename
        if not script.exists():
            print(f"  ⚠  {filename} — file not found, skipping")
            continue
        selected.append((filename, tags, timeout))

    if not selected:
        print("No tests matched the given filters.")
        return 0

    # ── header ────────────────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  Decision Engine — Full Integration Test Suite")
    print("═" * 70)
    print(f"  Target:  {args.base_url}")
    print(f"  Running: {len(selected)} test module(s)")
    if args.fast:
        print("  Mode:    --fast (load tests excluded)")
    if args.suite:
        print(f"  Suite:   {args.suite}")
    print("═" * 70 + "\n")

    # ── execute ───────────────────────────────────────────────────────────────
    results: list[TestResult] = []
    suite_start = time.perf_counter()

    for filename, tags, timeout in selected:
        script = TESTS_DIR / filename
        tag_str = ", ".join(sorted(tags))
        print(f"▶  {filename:<45} [{tag_str}]")

        result = run_test(script, timeout, env)
        results.append(result)

        # status icon
        if result.exit_code == 0 or result.failed == 0:
            icon = "✅"
        elif result.failed > 0 and result.passed > 0:
            icon = "⚠️ "
        else:
            icon = "❌"

        print(f"   {icon}  passed={result.passed}  failed={result.failed}  "
              f"skipped={result.skipped}  ({result.duration:.1f}s)\n")

        if args.verbose or result.failed > 0:
            # Show last 60 lines of output (or all if verbose)
            lines = result.output.splitlines()
            show  = lines if args.verbose else lines[-60:]
            for line in show:
                print(f"   │ {line}")
            print()

    # ── aggregate summary ─────────────────────────────────────────────────────
    suite_duration = time.perf_counter() - suite_start
    total_passed   = sum(r.passed  for r in results)
    total_failed   = sum(r.failed  for r in results)
    total_skipped  = sum(r.skipped for r in results)
    modules_ok     = sum(1 for r in results if r.exit_code == 0 and r.failed == 0)
    modules_fail   = len(results) - modules_ok

    print("═" * 70)
    print("  FINAL SUMMARY")
    print("═" * 70)
    print(f"  Modules:  {len(results)} run   {modules_ok} passed   {modules_fail} failed")
    print(f"  Tests:    {total_passed + total_failed + total_skipped} total  "
          f"✅ {total_passed}  ❌ {total_failed}  ⏭️  {total_skipped}")
    print(f"  Duration: {suite_duration:.1f}s")
    print()

    # Per-module breakdown
    print(f"  {'Module':<48} {'Pass':>5} {'Fail':>5} {'Skip':>5}  {'Time':>6}")
    print("  " + "-" * 70)
    for r in results:
        icon = "✅" if r.exit_code == 0 and r.failed == 0 else "❌"
        print(f"  {icon} {r.name:<46} {r.passed:>5} {r.failed:>5} {r.skipped:>5}  "
              f"{r.duration:>5.1f}s")

    print("═" * 70)

    if total_failed > 0 or modules_fail > 0:
        print(f"\n  ❌ SUITE FAILED — {total_failed} test(s) failed across "
              f"{modules_fail} module(s)\n")
        return 1

    print(f"\n  ✅ ALL TESTS PASSED ({total_passed} tests in {len(results)} modules)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
