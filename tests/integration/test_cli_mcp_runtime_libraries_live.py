"""Live proof for the encapsulated public runtime across Python, CLI, and MCP.

Run with:
    python3 tests/integration/test_cli_mcp_runtime_libraries_live.py
"""

from __future__ import annotations

if __name__ != "__main__":
    import pytest

    pytest.skip(
        "Standalone integration script; run via python tests/integration/test_cli_mcp_runtime_libraries_live.py",
        allow_module_level=True,
    )

import asyncio
import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
for package_root in reversed(
    (
        ROOT,
        ROOT / "packages" / "algenta",
        ROOT / "packages" / "mcp",
        ROOT / "packages" / "python-sdk",
    )
):
    resolved_root = str(package_root)
    if resolved_root in sys.path:
        sys.path.remove(resolved_root)
    sys.path.insert(0, resolved_root)

from algenta import MojoRuntime  # noqa: E402
from algenta import cli as algenta_cli  # noqa: E402
from algenta.native import worker as bundled_worker  # noqa: E402
from algenta.runtime_library_contract import runtime_modules  # noqa: E402
from algenta_mcp import registry as mcp_registry  # noqa: E402

from benchmarks.llm_rollout_live_artifacts import (  # noqa: E402
    LIVE_SUMMARY_ARTIFACTS,
    write_live_summary_artifact,
)
from tests.llm_rollout_matrix import (  # noqa: E402
    LLM_ROLLOUT_FUNCTION_CASES,
    LLM_ROLLOUT_FUNCTIONS_BY_MODULE,
    LLM_ROLLOUT_MODULE_NAMES,
    assert_rollout_channel_result,
)

PASS = "PASS"
FAIL = "FAIL"
SUITE_NAME = "local_runtime_cli_mcp_matrix"
SUMMARY_ARTIFACT = LIVE_SUMMARY_ARTIFACTS[SUITE_NAME]
MAX_WARM_LATENCY_MS = 15.0
BASE_URL = (
    os.environ.get("ALGENTA_BASE_URL")
    or os.environ.get("DE_BASE_URL")
    or os.environ.get("ALGENTA_API_URL")
    or ""
).rstrip("/")
results: list[tuple[str, bool, str]] = []


def _emit(message: str = "") -> None:
    print(message, flush=True)


def check(name: str, fn) -> Any:
    started = time.perf_counter()
    _emit(f"  ... {name}")
    try:
        value = fn()
        results.append((name, True, ""))
        _emit(f"  {PASS} {name} ({time.perf_counter() - started:.2f}s)")
        return value
    except Exception as exc:  # noqa: BLE001
        message = f"{type(exc).__name__}: {exc}"
        results.append((name, False, message))
        _emit(f"  {FAIL} {name} ({time.perf_counter() - started:.2f}s): {message}")
        return None


def _assert_rollout_inventory(modules: list[dict[str, Any]]) -> None:
    modules_by_name = {str(module["name"]): module for module in modules}
    missing_modules = sorted(set(LLM_ROLLOUT_MODULE_NAMES) - set(modules_by_name))
    assert not missing_modules, f"missing rollout modules: {missing_modules}"
    for module_name, expected_functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
        actual_functions = set(modules_by_name[module_name]["functions"])
        expected = set(expected_functions)
        assert actual_functions == expected, (
            f"{module_name} function mismatch: missing={sorted(expected - actual_functions)}, "
            f"extra={sorted(actual_functions - expected)}"
        )


def _assert_case_result(case: Any, result: Any) -> None:
    try:
        assert_rollout_channel_result(case, result)
    except AssertionError as exc:
        raise AssertionError(f"{case.module}.{case.function} returned {result!r}") from exc


def _run_cli(*args: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    original_argv = sys.argv[:]
    return_code = 0
    try:
        sys.argv = ["algenta", *args]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                algenta_cli.main()
            except SystemExit as exc:
                return_code = int(exc.code) if isinstance(exc.code, int) else 1
    finally:
        sys.argv = original_argv
    return return_code, stdout.getvalue(), stderr.getvalue()


def _preflight_api() -> None:
    assert BASE_URL, "ALGENTA_BASE_URL or DE_BASE_URL is required for live MCP proof"
    response = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
    assert response.status_code == 200, response.text


def main() -> int:
    started = time.perf_counter()
    _emit("\n" + "=" * 70)
    _emit("  LIVE ENCAPSULATED RUNTIME + CLI + MCP COVERAGE")
    _emit("=" * 70)
    _preflight_api()

    runtime = MojoRuntime(mode="local", timeout=30.0)

    def test_sanitized_contract() -> None:
        modules = runtime_modules()
        assert len(modules) == 635
        assert sum(len(module.functions) for module in modules) == 5983
        _assert_rollout_inventory(
            [
                {
                    "name": module.import_path,
                    "functions": [function.name for function in module.functions],
                }
                for module in modules
            ]
        )

    check("Wheel contract exposes 635 modules and 5,983 functions", test_sanitized_contract)

    def test_runtime_health() -> None:
        health = runtime.health()
        assert health == {
            "status": "ok",
            "mode": "bundled-worker",
            "fallback": "denied",
            "tcp_listeners": [],
        }
        assert bundled_worker.info()["warm_session"] is True

    check("Public runtime starts its private bundled worker automatically", test_runtime_health)

    def test_runtime_inventory() -> None:
        _assert_rollout_inventory(runtime.list_modules())

    check("MojoRuntime lists every rollout function", test_runtime_inventory)

    def test_runtime_executes_all() -> None:
        for case in LLM_ROLLOUT_FUNCTION_CASES:
            payload = runtime.execute(case.module, case.function, case.args)
            assert payload["success"] is True, payload
            assert payload["engine_used"] == "mojo"
            _assert_case_result(case, payload["result"])

    check("MojoRuntime executes every rollout function", test_runtime_executes_all)

    def test_warm_latency() -> None:
        case = LLM_ROLLOUT_FUNCTION_CASES[0]
        runtime.execute(case.module, case.function, case.args)
        latencies = []
        for _ in range(10):
            payload = runtime.execute(case.module, case.function, case.args)
            assert payload["success"] is True, payload
            latencies.append(float(payload["latency_ms"]))
        assert max(latencies) <= MAX_WARM_LATENCY_MS, latencies
        assert bundled_worker.info()["warm_session"] is True

    check("Warm public runtime stays at or below 15 ms", test_warm_latency)

    def test_cli_modules() -> None:
        return_code, stdout, stderr = _run_cli("runtime", "modules")
        assert return_code == 0, stderr
        _assert_rollout_inventory(json.loads(stdout)["modules"])

    check("algenta CLI lists every rollout function", test_cli_modules)

    def test_cli_functions() -> None:
        return_code, stdout, stderr = _run_cli(
            "runtime", "functions", "vector_kernels.table"
        )
        assert return_code == 0, stderr
        payload = json.loads(stdout)
        assert set(payload["functions"]) == set(
            LLM_ROLLOUT_FUNCTIONS_BY_MODULE["vector_kernels.table"]
        )

    check("algenta CLI resolves dotted module functions", test_cli_functions)

    def test_cli_execute() -> None:
        case = LLM_ROLLOUT_FUNCTION_CASES[0]
        return_code, stdout, stderr = _run_cli(
            "runtime",
            "execute",
            case.module,
            case.function,
            "--args-json",
            json.dumps(case.args),
        )
        assert return_code == 0, stderr or stdout
        payload = json.loads(stdout)
        assert payload["success"] is True, payload
        assert payload["engine_used"] == "mojo"
        _assert_case_result(case, payload["result"])

    check("algenta CLI executes through the same warm worker", test_cli_execute)

    def test_mcp_catalog() -> None:
        names = {spec["name"] for spec in mcp_registry.get_tool_specs()}
        assert {"list_runtime_libraries", "execute_runtime_library"} <= names

    check("algenta-mcp exposes both runtime tools", test_mcp_catalog)

    def test_mcp_list() -> None:
        payload = json.loads(
            asyncio.run(
                mcp_registry.call_tool("list_runtime_libraries", {"limit": 1000})
            )
        )
        _assert_rollout_inventory(payload["modules"])

    check("algenta-mcp lists live runtime libraries", test_mcp_list)

    def test_mcp_execute() -> None:
        case = LLM_ROLLOUT_FUNCTION_CASES[0]
        payload = json.loads(
            asyncio.run(
                mcp_registry.call_tool(
                    "execute_runtime_library",
                    {
                        "module": case.module,
                        "function": case.function,
                        "args": case.args,
                        "request_id": "req_mcp_encapsulated_runtime",
                    },
                )
            )
        )
        assert payload["engine_used"] == "mojo"
        _assert_case_result(case, payload["result"])

    check("algenta-mcp executes against the live warm API worker", test_mcp_execute)

    failed = [name for name, ok, _ in results if not ok]
    _emit("\n" + "=" * 70)
    _emit(f"Passed: {sum(1 for _, ok, _ in results if ok)}")
    _emit(f"Failed: {len(failed)}")
    for name in failed:
        _emit(f"  - {name}")
    _emit("=" * 70)
    summary = write_live_summary_artifact(
        output_path=SUMMARY_ARTIFACT,
        suite_name=SUITE_NAME,
        script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
        channels=("bundled_worker", "runtime_local", "cli", "mcp"),
        minimum_passed=11,
        passed=sum(1 for _, ok, _ in results if ok),
        failed=len(failed),
        skipped=0,
        elapsed_seconds=time.perf_counter() - started,
        extra={
            "base_url": BASE_URL,
            "warm_latency_gate_ms": MAX_WARM_LATENCY_MS,
            "separate_daemon_required": False,
        },
    )
    _emit(f"Summary artifact: {SUMMARY_ARTIFACT}")
    assert summary["status"] == ("passed" if not failed else "failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
