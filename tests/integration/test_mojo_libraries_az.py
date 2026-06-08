"""
test_mojo_libraries_az.py — End-to-end tests for the current repo Mojo library pack.

Runs the auto-generated per-module Mojo test files in parallel using mojo run.
Each test file imports one current repo module and calls its testable public
functions with representative inputs, verifying numeric outputs are finite.

The generated test pack is derived from the current recursive mojo/engine tree.
If the generated inventory drifts from the source tree, this harness regenerates
the pack before executing it.

Run:
  python3 tests/integration/test_mojo_libraries_az.py
  DE_MOJO_WORKERS=16 python3 ...    # control parallelism (default: 4)
  DE_MOJO_TIMEOUT=30 python3 ...    # per-module timeout in seconds (default: 30)
"""

from __future__ import annotations

import concurrent.futures
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from benchmarks.scorecard_sync import sync_shared_benchmark_scorecard  # noqa: E402

mojo_test_gen = importlib.import_module("tests.generate_mojo_tests")

MOJO_ENV = _PROJECT_ROOT / "mojo_env"
MOJO_BIN = MOJO_ENV / ".pixi" / "envs" / "default" / "bin" / "mojo"
LIBS_DIR = _PROJECT_ROOT / "mojo" / "tests" / "libs"
ENGINE_DIR = _PROJECT_ROOT / "mojo" / "engine"
MODULAR_HOME = MOJO_ENV / ".pixi" / "envs" / "default" / "share" / "max"
MODULAR_CACHE_DIR = _PROJECT_ROOT / ".cache" / "modular"
MODULAR_DATA_DIR = _PROJECT_ROOT / ".local" / "share"
SUMMARY_ARTIFACT_PATH = _PROJECT_ROOT / "build" / "mojo_libraries_az_summary.json"

MAX_WORKERS = int(os.environ.get("DE_MOJO_WORKERS", "4"))
TIMEOUT = int(os.environ.get("DE_MOJO_TIMEOUT", "30"))
RETRY_TIMEOUT = max(TIMEOUT * 2, 60)

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"

_IMPORT_RE = re.compile(r"^\s*from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\s+", re.MULTILINE)
_ALLOWED_IMPORT_ROOTS = {"std", "math", "memory", "mojo", "sys"}


def _pixi_env_binary() -> str | None:
    pixi_home = os.environ.get("PIXI_HOME")
    if not pixi_home:
        return None
    candidate = Path(pixi_home).expanduser() / "bin" / "pixi"
    if candidate.exists():
        return str(candidate)
    return None


def _repo_local_pixi_binary() -> str | None:
    candidate = _PROJECT_ROOT / ".pixi" / "bin" / "pixi"
    if candidate.exists():
        return str(candidate)
    return None


def _pixi_binary() -> str | None:
    pixi_on_path = shutil.which("pixi")
    if pixi_on_path:
        return pixi_on_path
    pixi_from_env = _pixi_env_binary()
    if pixi_from_env:
        return pixi_from_env
    repo_local_pixi = _repo_local_pixi_binary()
    if repo_local_pixi:
        return repo_local_pixi
    home_pixi = Path.home() / ".pixi" / "bin" / "pixi"
    if home_pixi.exists():
        return str(home_pixi)
    return None


def _mojo_run_command(test_file: Path) -> list[str]:
    if MOJO_BIN.exists():
        return [str(MOJO_BIN), "run", f"-I{ENGINE_DIR}", str(test_file)]
    pixi_binary = _pixi_binary()
    if pixi_binary:
        return [pixi_binary, "run", "mojo", "run", f"-I{ENGINE_DIR}", str(test_file)]
    return [str(MOJO_BIN), "run", f"-I{ENGINE_DIR}", str(test_file)]


def _module_source_exists(import_path: str, engine_root: Path = ENGINE_DIR) -> bool:
    root = import_path.split(".", 1)[0]
    if root in _ALLOWED_IMPORT_ROOTS:
        return True

    module_path = engine_root / Path(*import_path.split("."))
    if module_path.with_suffix(".mojo").exists():
        return True
    if (module_path / "__init__.mojo").exists():
        return True
    return False


def _expected_generated_test_files() -> set[str]:
    return {f"test_{target.module_id}.mojo" for target, _ in mojo_test_gen.build_generation_plan()}


def _generated_test_inventory_needs_refresh(libs_dir: Path = LIBS_DIR) -> bool:
    expected = _expected_generated_test_files()
    actual = {test_file.name for test_file in libs_dir.glob("test_*.mojo")}
    return actual != expected


def _discover_missing_test_imports(
    libs_dir: Path = LIBS_DIR,
    engine_root: Path = ENGINE_DIR,
) -> dict[str, list[str]]:
    missing: dict[str, set[str]] = {}

    for test_file in sorted(libs_dir.glob("test_*.mojo")):
        source_text = test_file.read_text(encoding="utf-8", errors="replace")
        for import_path in _IMPORT_RE.findall(source_text):
            if _module_source_exists(import_path, engine_root):
                continue
            missing.setdefault(import_path, set()).add(test_file.name)

    return {import_path: sorted(referrers) for import_path, referrers in sorted(missing.items())}


# ── helpers ───────────────────────────────────────────────────────────────────


def _run_library_test(
    test_file: Path,
    *,
    timeout: int = TIMEOUT,
) -> tuple[str, int, int, float, str]:
    """Run one library test file. Returns (lib, passed, failed, elapsed, output)."""
    lib = test_file.stem.replace("test_", "", 1)
    t0 = time.perf_counter()
    run_env = {
        **os.environ,
        "MODULAR_HOME": str(MODULAR_HOME),
        "MODULAR_CACHE_DIR": str(MODULAR_CACHE_DIR),
        "XDG_DATA_HOME": str(MODULAR_DATA_DIR),
        "MODULAR_TELEMETRY_ENABLED": "0",
    }
    try:
        result = subprocess.run(
            _mojo_run_command(test_file),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(MOJO_ENV),
            env=run_env,
        )
        elapsed = time.perf_counter() - t0
        output = result.stdout + result.stderr

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
            f"({elapsed * 1000:.0f}ms) [retry timeout={RETRY_TIMEOUT}s]"
        )

    return [updated[result[0]] for result in results]


def _build_summary_payload(
    *,
    results: list[tuple[str, int, int, float, str]],
    suite_duration: float,
) -> dict[str, object]:
    total_passed = sum(result[1] for result in results)
    total_failed = sum(result[2] for result in results)
    passed_libraries = sum(1 for result in results if result[2] == 0)
    failed_libraries = len(results) - passed_libraries
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "library_count": len(results),
        "passed_library_count": passed_libraries,
        "failed_library_count": failed_libraries,
        "function_count": total_passed + total_failed,
        "passed_function_count": total_passed,
        "failed_function_count": total_failed,
        "suite_duration_s": round(suite_duration, 3),
        "workers": MAX_WORKERS,
        "timeout_seconds": TIMEOUT,
    }


def _write_summary_artifact(
    results: list[tuple[str, int, int, float, str]],
    *,
    suite_duration: float,
    output_path: Path = SUMMARY_ARTIFACT_PATH,
) -> dict[str, object]:
    summary = _build_summary_payload(results=results, suite_duration=suite_duration)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    pixi_binary = _pixi_binary()
    mojo_available = MOJO_BIN.exists() or pixi_binary
    if not mojo_available:
        print(f"  ❌  Mojo binary not found at {MOJO_BIN}")
        print("     Run: make setup-mojo")
        return 1

    MODULAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MODULAR_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Regenerate test files when the generated inventory no longer matches the
    # current mojo/engine tree. This keeps the suite load-bearing after
    # module moves or recursive layout changes.
    if not LIBS_DIR.exists() or _generated_test_inventory_needs_refresh():
        print("  Mojo test inventory is stale — regenerating...")
        gen_script = _PROJECT_ROOT / "tests" / "generate_mojo_tests.py"
        subprocess.run(
            [sys.executable, str(gen_script)],
            check=True,
            cwd=str(_PROJECT_ROOT),
        )

    missing_imports = _discover_missing_test_imports()
    if missing_imports:
        print("=" * 70)
        print("  Mojo Libraries A-Z — preflight failed")
        print("=" * 70)
        print("  Generated test files still reference missing Mojo modules:")
        for import_path, referrers in missing_imports.items():
            sample_referrers = ", ".join(referrers[:3])
            suffix = "" if len(referrers) <= 3 else f" (+{len(referrers) - 3} more)"
            print(f"  {FAIL} {import_path:<20} referenced by {sample_referrers}{suffix}")
        print()
        print("  Regenerate or fix the generated test pack before running the A-Z suite.")
        return 1

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
            print(f"  {icon}  {lib:<40}  pass={passed}  fail={failed}  ({elapsed * 1000:.0f}ms)")

    results = _rerun_timeout_failures(results)

    suite_duration = time.perf_counter() - suite_start

    # Sort results alphabetically for report
    results.sort(key=lambda r: r[0])

    total_passed = sum(r[1] for r in results)
    total_failed = sum(r[2] for r in results)
    libs_ok = sum(1 for r in results if r[2] == 0)
    libs_fail = len(results) - libs_ok
    _write_summary_artifact(results, suite_duration=suite_duration)
    sync_shared_benchmark_scorecard()

    print()
    print("=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    print(f"  Passed:   {total_passed}")
    print(f"  Failed:   {total_failed}")
    print("  Skipped:  0")
    print(f"  Libraries: {len(results)} total  {PASS} {libs_ok} passed  {FAIL} {libs_fail} failed")
    print(
        f"  Functions: {total_passed + total_failed} total  "
        f"{PASS} {total_passed}  {FAIL} {total_failed}"
    )
    print(f"  Duration:  {suite_duration:.1f}s  (parallelism={MAX_WORKERS})")
    print()

    # Print per-library breakdown
    print(f"  {'Library':<42} {'Pass':>5} {'Fail':>5} {'ms':>6}")
    print("  " + "-" * 60)
    for lib, passed, failed, elapsed, _ in results:
        icon = PASS if failed == 0 else FAIL
        print(f"  {icon} {lib:<40} {passed:>5} {failed:>5} {elapsed * 1000:>5.0f}")

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
        print(
            f"\n  {FAIL} {total_failed} function test(s) failed across "
            f"{libs_fail} library/libraries\n"
        )
        return 1

    print(f"\n  {PASS} ALL TESTS PASSED — {total_passed} functions across {libs_ok} libraries\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
