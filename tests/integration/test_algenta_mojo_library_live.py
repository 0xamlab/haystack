"""
Live Python Mojo library integration through the published Algenta package surface.

This verifies the API-key-backed local package path:
  1. Use the automatically resolved compiled worker with no user-managed daemon.
  2. Use `algenta.MojoRuntime(mode="local", api_key=...)` for direct execution.
  3. Use `algenta.libraries(mode="local", api_key=...)` for catalog-backed library execution.

Run:
  DE_API_KEY="..." DE_BASE_URL="http://127.0.0.1:8000" \\
    python3 tests/integration/test_algenta_mojo_library_live.py
"""

from __future__ import annotations

if __name__ != "__main__":
    import pytest

    pytest.skip(
        "Standalone integration script; run via python tests/integration/test_algenta_mojo_library_live.py",
        allow_module_level=True,
    )

import importlib
import os
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import httpx

from benchmarks.llm_rollout_live_artifacts import (
    LIVE_SUMMARY_ARTIFACTS,
    write_live_summary_artifact,
)
from tests.llm_rollout_matrix import (
    LLM_ROLLOUT_FUNCTION_CASES,
    LLM_ROLLOUT_FUNCTIONS_BY_MODULE,
    LLM_ROLLOUT_MODULE_NAMES,
    assert_rollout_channel_result,
)

try:
    from tests.integration.live_local_defaults import resolve_local_live_base_url
except ModuleNotFoundError:
    from live_local_defaults import resolve_local_live_base_url

BASE_URL = resolve_local_live_base_url(strip_trailing_slash=True)
API_KEY = os.environ.get("DE_API_KEY", "")
PASS = "✅"
FAIL = "❌"
SUITE_NAME = "python_sdk_local_runtime"
SUMMARY_ARTIFACT = LIVE_SUMMARY_ARTIFACTS[SUITE_NAME]
results: list[tuple[str, bool, str]] = []


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def check(name: str, fn) -> Any:
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        value = fn()
        results.append((name, True, ""))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
        return value
    except AssertionError as exc:
        results.append((name, False, str(exc)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
        return None
    except Exception as exc:  # noqa: BLE001
        message = f"{type(exc).__name__}: {exc}"
        results.append((name, False, message))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {message}")
        return None


def _reload_runtime_modules() -> None:
    modules = [
        "algenta",
        "algenta.mojo_runtime",
        "algenta.mojo_entrypoints",
    ]
    for module_name in modules:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])


def _preflight() -> None:
    if not API_KEY:
        return
    response = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
    assert response.status_code == 200, f"/v1/health returned {response.status_code}"


@contextmanager
def local_bundled_runtime() -> dict[str, str]:
    runtime_dir = Path(tempfile.mkdtemp(prefix="algenta-python-mojo-live-"))
    env_updates = {
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_DEVICE_KEY_STORE": "file",
        "ALGENTA_CONTROL_PLANE_URL": BASE_URL,
        "ALGENTA_BASE_URL": BASE_URL,
        "DE_BASE_URL": BASE_URL,
        "ALGENTA_API_KEY": API_KEY,
        "DE_API_KEY": API_KEY,
        "JWT_SECRET": os.environ.get(
            "JWT_SECRET",
            "change-me-in-production-use-256-bit-random-value",
        ),
    }
    old_env = {key: os.environ.get(key) for key in env_updates}
    os.environ.update(env_updates)
    _reload_runtime_modules()
    try:
        yield env_updates
    finally:
        for key, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        _reload_runtime_modules()
        shutil.rmtree(runtime_dir, ignore_errors=True)


def main() -> int:
    started = time.perf_counter()
    _emit("\n" + "=" * 70)
    _emit("  LIVE ALGENTA PYTHON MOJO LIBRARY INTEGRATION")
    _emit("=" * 70)

    _preflight()

    with local_bundled_runtime():
        import algenta

        runtime = algenta.MojoRuntime(
            mode="local",
            api_key=API_KEY,
            base_url=BASE_URL,
            auto_start_daemon=True,
        )
        catalog = algenta.libraries(
            mode="local",
            api_key=API_KEY,
            base_url=BASE_URL,
            auto_start_daemon=True,
        )

        def test_runtime_health() -> None:
            health = runtime.health()
            assert health == {
                "status": "ok",
                "mode": "bundled-worker",
                "fallback": "denied",
                "tcp_listeners": [],
            }

        check("MojoRuntime.health() reports mojo availability", test_runtime_health)

        def test_catalog_inventory() -> None:
            modules = catalog.list_modules()
            expected_modules = set(LLM_ROLLOUT_MODULE_NAMES) | {"ab_testing", "elevator"}
            assert {module.name for module in modules} == expected_modules
            assert modules[0].functions
            assert "sample_size_proportion" in catalog.list_functions("ab_testing")

        check(
            "algenta.libraries(mode='local') exposes executable inventory", test_catalog_inventory
        )

        def test_direct_runtime_execute() -> None:
            result = runtime.execute(
                "elevator",
                "annual_energy_consumption",
                [0.5, 0.5, 0.5, 0.5],
            )
            assert result["success"] is True
            assert result["engine_used"] == "mojo"
            assert isinstance(result["result"], float)
            assert result["result"] > 0.0

        check("MojoRuntime.execute() uses compiled worker path", test_direct_runtime_execute)

        def test_catalog_execution() -> None:
            result = catalog.ab_testing.sample_size_proportion(
                p1=0.10,
                p2=0.12,
                alpha=0.05,
                power=0.8,
            )
            assert isinstance(result, int)
            assert result > 0

        check(
            "catalog.ab_testing.sample_size_proportion(...) executes live", test_catalog_execution
        )

        def test_llm_rollout_inventory() -> None:
            module_names = {descriptor.name for descriptor in catalog.list_modules()}
            expected = set(LLM_ROLLOUT_MODULE_NAMES)
            assert expected.issubset(module_names)
            for module_name, expected_functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
                assert set(catalog.list_functions(module_name)) == set(expected_functions)

        check("algenta catalog exposes all 22 LLM rollout modules", test_llm_rollout_inventory)

        def test_llm_rollout_runtime_execution() -> None:
            for case in LLM_ROLLOUT_FUNCTION_CASES:
                result = runtime.execute(case.module, case.function, case.args)
                assert result["success"] is True
                assert result["engine_used"] == "mojo"
                assert_rollout_channel_result(case, result["result"])

        check(
            "MojoRuntime.execute() executes all LLM rollout functions",
            test_llm_rollout_runtime_execution,
        )

        def test_llm_rollout_catalog_execution() -> None:
            for case in LLM_ROLLOUT_FUNCTION_CASES:
                module = catalog.module(case.module)
                result = getattr(module, case.function)(case.args)
                assert_rollout_channel_result(case, result)

        check(
            "algenta catalog executes all LLM rollout functions",
            test_llm_rollout_catalog_execution,
        )

    failed = [name for name, ok, _ in results if not ok]
    _emit("\n" + "=" * 70)
    _emit(f"Passed: {sum(1 for _, ok, _ in results if ok)}")
    _emit(f"Failed: {len(failed)}")
    if failed:
        for name in failed:
            _emit(f"  - {name}")
    _emit("=" * 70)
    summary = write_live_summary_artifact(
        output_path=SUMMARY_ARTIFACT,
        suite_name=SUITE_NAME,
        script="tests/integration/test_algenta_mojo_library_live.py",
        channels=("python_sdk",),
        minimum_passed=7,
        passed=sum(1 for _, ok, _ in results if ok),
        failed=len(failed),
        skipped=0,
        elapsed_seconds=time.perf_counter() - started,
        extra={"base_url": BASE_URL, "api_key_configured": bool(API_KEY)},
    )
    _emit(f"Summary artifact: {SUMMARY_ARTIFACT}")
    assert summary["status"] == ("passed" if not failed else "failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
