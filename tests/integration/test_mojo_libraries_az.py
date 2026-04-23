"""
test_mojo_libraries_az.py — End-to-end tests for all 244 Mojo libraries (A → Z)

Runs the auto-generated per-library Mojo test files in parallel using mojo run.
Each test file imports one domain library and calls every public function with
representative inputs, verifying the outputs are finite numbers (non-NaN, non-Inf).

Coverage:
  244 libraries × avg 9.9 functions = 2,414 function tests
  Libraries A-Z: ab_testing → wind_energy

Prerequisites:
  python3 tests/generate_mojo_tests.py    # regenerate test files (run once)
  Mojo 0.26+ installed via pixi env at mojo_env/

Run:
  python3 tests/integration/test_mojo_libraries_az.py
  DE_MOJO_WORKERS=16 python3 ...    # control parallelism (default: 8)
  DE_MOJO_TIMEOUT=30 python3 ...    # per-library timeout in seconds (default: 15)
"""
from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

MOJO_ENV  = _PROJECT_ROOT / "mojo_env"
MOJO_BIN  = MOJO_ENV / ".pixi" / "envs" / "default" / "bin" / "mojo"
LIBS_DIR  = _PROJECT_ROOT / "mojo" / "tests" / "libs"
ENGINE_DIR = _PROJECT_ROOT / "mojo" / "engine"

MAX_WORKERS  = int(os.environ.get("DE_MOJO_WORKERS", "4"))
TIMEOUT      = int(os.environ.get("DE_MOJO_TIMEOUT",  "30"))
RETRY_TIMEOUT = max(TIMEOUT * 2, 60)

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"


def _pixi_binary() -> str | None:
    pixi_on_path = shutil.which("pixi")
    if pixi_on_path:
        return pixi_on_path
    home_pixi = Path.home() / ".pixi" / "bin" / "pixi"
    if home_pixi.exists():
        return str(home_pixi)
    return None


def _mojo_run_command(test_file: Path) -> list[str]:
    pixi_binary = _pixi_binary()
    if pixi_binary:
        return [pixi_binary, "run", "mojo", "run", f"-I{ENGINE_DIR}", str(test_file)]
    return [str(MOJO_BIN), "run", f"-I{ENGINE_DIR}", str(test_file)]


# ── helpers ───────────────────────────────────────────────────────────────────

def _run_library_test(
    test_file: Path,
    *,
    timeout: int = TIMEOUT,
) -> tuple[str, int, int, float, str]:
    """Run one library test file. Returns (lib, passed, failed, elapsed, output)."""
    lib = test_file.stem.replace("test_", "", 1)
    t0  = time.perf_counter()
    try:
        result = subprocess.run(
            _mojo_run_command(test_file),
            capture_output=True, text=True,
            timeout=timeout,
            cwd=str(MOJO_ENV),
        )
        elapsed = time.perf_counter() - t0
        output  = result.stdout + result.stderr

        # Parse pass/fail counts from output
        passed = output.count("✅")
        failed = output.count("❌")

        # If mojo exited non-zero but we see no ❌, treat as failed
        if result.returncode != 0 and failed == 0:
            failed = 1
            output += f"\n[exit code {result.returncode}]"

        return lib, passed, failed, elapsed, output

    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - t0
        return lib, 0, 1, elapsed, f"TIMEOUT after {timeout}s"
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return lib, 0, 1, elapsed, str(exc)


def _is_timeout_failure(result: tuple[str, int, int, float, str]) -> bool:
    _, _, failed, _, output = result
    return failed > 0 and output.startswith("TIMEOUT after ")


def _rerun_timeout_failures(
    results: list[tuple[str, int, int, float, str]],
) -> list[tuple[str, int, int, float, str]]:
    timeout_failures = [result for result in results if _is_timeout_failure(result)]
    if not timeout_failures:
        return results

    print()
    print("=" * 70)
    print("  RETRYING TIMEOUT LIBRARIES SEQUENTIALLY")
    print("=" * 70)

    updated = {result[0]: result for result in results}
    for lib, _, _, _, _ in timeout_failures:
        test_file = LIBS_DIR / f"test_{lib}.mojo"
        retried = _run_library_test(test_file, timeout=RETRY_TIMEOUT)
        updated[lib] = retried
        _, passed, failed, elapsed, _ = retried
        icon = PASS if failed == 0 else FAIL
        print(
            f"  {icon}  {lib:<40}  pass={passed}  fail={failed}  "
            f"({elapsed*1000:.0f}ms) [retry timeout={RETRY_TIMEOUT}s]"
        )

    return [updated[result[0]] for result in results]


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    pixi_binary = _pixi_binary()
    mojo_available = MOJO_BIN.exists() or pixi_binary
    if not mojo_available:
        print(f"  ❌  Mojo binary not found at {MOJO_BIN}")
        print("     Run: cd mojo_env && pixi install")
        return 1

    # Regenerate test files if libs dir is missing or empty
    if not LIBS_DIR.exists() or not list(LIBS_DIR.glob("test_*.mojo")):
        print("  Test files not found — regenerating...")
        gen_script = _PROJECT_ROOT / "tests" / "generate_mojo_tests.py"
        subprocess.run([sys.executable, str(gen_script)], check=True,
                       cwd=str(_PROJECT_ROOT))

    test_files = sorted(LIBS_DIR.glob("test_*.mojo"))
    if not test_files:
        print("  No test files found in", LIBS_DIR)
        return 1

    print("=" * 70)
    print("  Mojo Libraries A-Z — End-to-End Function Tests")
    print("=" * 70)
    print(f"  Libraries:  {len(test_files)}")
    print(f"  Workers:    {MAX_WORKERS} parallel")
    print(f"  Timeout:    {TIMEOUT}s per library")
    print(f"  Mojo:       {f'{pixi_binary} run mojo' if pixi_binary else MOJO_BIN}")
    print("=" * 70)

    results: list[tuple[str, int, int, float, str]] = []
    suite_start = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_run_library_test, f): f for f in test_files}
        for fut in concurrent.futures.as_completed(futures):
            lib, passed, failed, elapsed, output = fut.result()
            results.append((lib, passed, failed, elapsed, output))
            icon = PASS if failed == 0 else FAIL
            print(f"  {icon}  {lib:<40}  pass={passed}  fail={failed}  "
                  f"({elapsed*1000:.0f}ms)")

    results = _rerun_timeout_failures(results)

    suite_duration = time.perf_counter() - suite_start

    # Sort results alphabetically for report
    results.sort(key=lambda r: r[0])

    total_passed  = sum(r[1] for r in results)
    total_failed  = sum(r[2] for r in results)
    libs_ok       = sum(1 for r in results if r[2] == 0)
    libs_fail     = len(results) - libs_ok

    print()
    print("=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    print(f"  Libraries: {len(results)} total  "
          f"{PASS} {libs_ok} passed  {FAIL} {libs_fail} failed")
    print(f"  Functions: {total_passed + total_failed} total  "
          f"{PASS} {total_passed}  {FAIL} {total_failed}")
    print(f"  Duration:  {suite_duration:.1f}s  "
          f"(parallelism={MAX_WORKERS})")
    print()

    # Print per-library breakdown
    print(f"  {'Library':<42} {'Pass':>5} {'Fail':>5} {'ms':>6}")
    print("  " + "-" * 60)
    for lib, passed, failed, elapsed, _ in results:
        icon = PASS if failed == 0 else FAIL
        print(f"  {icon} {lib:<40} {passed:>5} {failed:>5} {elapsed*1000:>5.0f}")

    # Print failures detail
    failures = [(lib, out) for lib, p, f, _, out in results if f > 0]
    if failures:
        print()
        print("=" * 70)
        print("  FAILED LIBRARIES — detailed output")
        print("=" * 70)
        for lib, output in failures:
            print(f"\n  ── {lib} ──")
            for line in output.splitlines()[-30:]:
                if line.strip():
                    print(f"    {line}")

    print("=" * 70)

    if total_failed > 0 or libs_fail > 0:
        print(f"\n  {FAIL} {total_failed} function test(s) failed across "
              f"{libs_fail} library/libraries\n")
        return 1

    print(f"\n  {PASS} ALL TESTS PASSED — "
          f"{total_passed} functions across {libs_ok} libraries\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
