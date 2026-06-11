"""
Live runtime-library coverage for the 22-library Mojo LLM rollout.

This verifies that the rollout modules are exposed through:
  - direct local daemon gRPC client
  - Python Runtime(mode="local")
  - CLI runtime library commands
  - MCP runtime library tools

Run:
  DE_API_KEY="..." DE_BASE_URL="http://127.0.0.1:8000" \
    python3 tests/integration/test_cli_mcp_runtime_libraries_live.py

Or let the script boot an isolated current-checkout API server automatically:
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
import atexit
import contextlib
import io
import importlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

API_KEY = os.environ.get("DE_API_KEY", "")
CLI = [sys.executable, "-m", "apps.cli.main"]
ROLLOUT_PARITY_BENCHMARK = ROOT / "build" / "llm_rollout_parity_benchmark.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
try:
    from tests.integration.live_local_defaults import configured_local_live_base_url
except ModuleNotFoundError:
    from live_local_defaults import configured_local_live_base_url

CONFIGURED_BASE_URL = configured_local_live_base_url()
_runtime_proc: subprocess.Popen[str] | None = None
_runtime_started_here = False
_runtime_log_path: Path | None = None
PASS = "✅"
FAIL = "❌"
SUITE_NAME = "local_runtime_cli_mcp_matrix"
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


def _free_tcp_port() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return f"127.0.0.1:{sock.getsockname()[1]}"


def _read_log(log_path: Path | None) -> str:
    if log_path is None:
        return ""
    try:
        contents = log_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not contents:
        return ""
    return f"\nServer log:\n{contents}"


def _port_open(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _choose_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((DEFAULT_HOST, 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _probe_json(base_url: str, path: str, timeout: float = 3.0) -> tuple[int, Any]:
    request = urllib.request.Request(f"{base_url}{path}", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        body = err.read()
        try:
            return err.code, json.loads(body)
        except Exception:
            return err.code, body.decode("utf-8", errors="replace")


def _wait_for_health(base_url: str, log_path: Path, timeout_seconds: float = 30.0) -> None:
    start = time.monotonic()
    last_error = "no response"
    while time.monotonic() - start < timeout_seconds:
        if _runtime_proc is not None and _runtime_proc.poll() is not None:
            raise RuntimeError(
                f"Runtime API exited before readiness probe with code {_runtime_proc.returncode}."
                f"{_read_log(log_path)}"
            )
        try:
            status, body = _probe_json(base_url, "/v1/health", timeout=2.0)
            if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                return
            last_error = f"status {status}"
        except Exception as exc:  # pragma: no cover - best effort probe
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for {base_url}/v1/health: {last_error}.{_read_log(log_path)}"
    )


def _endpoint_serves_canonical_runtime_contract(base_url: str) -> bool:
    try:
        status, manifest = _probe_json(base_url, "/v1/runtime/manifest", timeout=5.0)
        if status != 200 or not isinstance(manifest, dict):
            return False
        if manifest.get("runtime_version") != "2026.05.0":
            return False
        status, contract = _probe_json(base_url, "/v1/meta/contract", timeout=5.0)
        if status != 200 or not isinstance(contract, dict):
            return False
        status, spec = _probe_json(base_url, "/openapi.json", timeout=5.0)
        if status != 200 or not isinstance(spec, dict):
            return False
        if "/v1/query" not in spec.get("paths", {}):
            return False
        if "/mcp/tools" not in spec.get("paths", {}):
            return False
        return True
    except Exception:
        return False


def _cleanup_runtime() -> None:
    global _runtime_proc
    if not _runtime_started_here or _runtime_proc is None:
        return
    _runtime_proc.terminate()
    try:
        _runtime_proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _runtime_proc.kill()
        _runtime_proc.wait(timeout=5)
    _runtime_proc = None


def _resolve_base_url() -> str:
    global _runtime_proc, _runtime_started_here, _runtime_log_path
    if CONFIGURED_BASE_URL:
        return CONFIGURED_BASE_URL.rstrip("/")

    base_url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    log_dir = Path(tempfile.mkdtemp(prefix="integration-cli-mcp-runtime-"))
    log_path = log_dir / "api_server.log"

    if _port_open(DEFAULT_HOST, DEFAULT_PORT):
        try:
            _wait_for_health(base_url, log_path, timeout_seconds=5.0)
            if _endpoint_serves_canonical_runtime_contract(base_url):
                return base_url
        except RuntimeError:
            pass

    port = _choose_free_port()
    base_url = f"http://{DEFAULT_HOST}:{port}"
    env = os.environ.copy()
    env.setdefault("ALGENTA_SOURCE_REGISTRY_ROOT", str(log_dir / "sources"))
    env.setdefault("ALGENTA_RUNTIME_DIR", str(log_dir / "runtime"))
    with log_path.open("w", encoding="utf-8") as log_handle:
        _runtime_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "apps.api_server.main:app",
                "--host",
                DEFAULT_HOST,
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=str(ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    _runtime_started_here = True
    _runtime_log_path = log_path
    _wait_for_health(base_url, log_path)
    return base_url


BASE_URL = _resolve_base_url()
atexit.register(_cleanup_runtime)


def _license_verification_env() -> dict[str, str]:
    explicit = {
        "ALGENTA_LICENSE_SIGNING_SECRET": os.environ.get("ALGENTA_LICENSE_SIGNING_SECRET", ""),
        "LICENSE_SIGNING_SECRET": os.environ.get("LICENSE_SIGNING_SECRET", ""),
        "ALGENTA_JWT_SECRET": os.environ.get("ALGENTA_JWT_SECRET", ""),
        "JWT_SECRET": os.environ.get("JWT_SECRET", ""),
    }
    if any(value for value in explicit.values()):
        return {}

    try:
        from apps.api_server.config import get_settings
    except Exception:
        return {}

    settings = get_settings()
    if settings.license_signing_secret:
        return {"ALGENTA_LICENSE_SIGNING_SECRET": settings.license_signing_secret}
    if settings.jwt_secret:
        return {"ALGENTA_JWT_SECRET": settings.jwt_secret}
    return {}


def _reload_runtime_modules() -> None:
    for module_name in [
        "apps.runtime.license",
        "apps.runtime.credits",
        "apps.runtime.metering",
        "apps.runtime.entitlement",
        "apps.runtime.client",
        "apps.runtime.daemon",
        "apps.runtime.sdk",
    ]:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])


async def _wait_for_runtime_ready(timeout_seconds: float = 10.0) -> dict[str, Any] | None:
    from apps.runtime.client import DaemonClient

    client = DaemonClient(timeout=20.0)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        health = await client.health()
        if health.get("status") == "ok":
            return health
        await asyncio.sleep(0.1)
    return None


async def _wait_for_runtime_entitlement_ready(timeout_seconds: float = 10.0) -> dict[str, Any] | None:
    from apps.runtime.client import DaemonClient

    client = DaemonClient(timeout=20.0)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        entitlement = await client.entitlement()
        tier = str(entitlement.get("tier", "") or "")
        permitted_modules = entitlement.get("permitted_modules", [])
        if entitlement.get("valid") is True and tier not in {"", "unknown"}:
            if isinstance(permitted_modules, list) and "*" in permitted_modules:
                return entitlement
        await asyncio.sleep(0.1)
    return None


@contextmanager
def local_runtime_daemon() -> dict[str, str]:
    runtime_dir = Path(tempfile.mkdtemp(prefix="algenta-cli-mcp-mojo-live-"))
    daemon_sock = runtime_dir / "daemon.sock"
    mojo_sock = runtime_dir / "mojo.sock"
    env_updates = {
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_DAEMON_SOCK": str(daemon_sock),
        "ALGENTA_DAEMON_TCP": _free_tcp_port(),
        "ALGENTA_MOJO_SOCK": str(mojo_sock),
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
    if not API_KEY:
        env_updates["ALGENTA_RUNTIME_DEV_MODE"] = "1"
    env_updates.update(_license_verification_env())
    old_env = {key: os.environ.get(key) for key in env_updates}
    os.environ.update(env_updates)
    _reload_runtime_modules()

    from apps.runtime.daemon import cmd_start, cmd_stop, is_running

    try:
        if is_running():
            cmd_stop()
        cmd_start(foreground=False)
        health = asyncio.run(_wait_for_runtime_ready())
        if not health:
            raise RuntimeError("runtime daemon did not become healthy")
        entitlement = asyncio.run(_wait_for_runtime_entitlement_ready())
        if not entitlement:
            raise RuntimeError("runtime daemon entitlement did not become ready")
        yield env_updates
    finally:
        try:
            if is_running():
                cmd_stop()
        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value
            _reload_runtime_modules()
            shutil.rmtree(runtime_dir, ignore_errors=True)


def _preflight() -> None:
    if not API_KEY:
        return
    response = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
    assert response.status_code == 200, f"/v1/health returned {response.status_code}"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DE_API_KEY": API_KEY, "DE_BASE_URL": BASE_URL, "DE_NO_COLOR": "1"}
    return subprocess.run(
        CLI + list(args),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        timeout=60,
    )


def _run_cli_in_process(*args: str) -> subprocess.CompletedProcess[str]:
    from apps.cli import main as cli_main

    env_updates = {"DE_API_KEY": API_KEY, "DE_BASE_URL": BASE_URL, "DE_NO_COLOR": "1"}
    old_env = {key: os.environ.get(key) for key in env_updates}
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_argv = sys.argv[:]
    returncode = 0
    try:
        for key, value in env_updates.items():
            os.environ[key] = value
        sys.argv = ["de", *args]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                cli_main.main()
            except SystemExit as exc:  # pragma: no cover - mirrors CLI shell behavior
                code = exc.code
                returncode = int(code) if isinstance(code, int) else 1
    finally:
        sys.argv = old_argv
        for key, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value

    return subprocess.CompletedProcess(
        args=CLI + list(args),
        returncode=returncode,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )


def _ensure_rollout_parity_benchmark_artifact() -> None:
    expected_library_count = len(LLM_ROLLOUT_MODULE_NAMES)
    expected_function_count = len(LLM_ROLLOUT_FUNCTION_CASES)

    if ROLLOUT_PARITY_BENCHMARK.exists():
        try:
            payload = json.loads(ROLLOUT_PARITY_BENCHMARK.read_text())
        except (OSError, json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict):
            if (
                int(payload.get("n_libraries", 0)) == expected_library_count
                and int(payload.get("total_functions_compared", 0)) == expected_function_count
            ):
                return

    proc = subprocess.run(
        [sys.executable, str(ROOT / "benchmarks" / "llm_rollout_parity_benchmark.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Failed to regenerate the rollout parity benchmark artifact.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )


def _format_speedup_value(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def main() -> int:
    started = time.perf_counter()
    _emit("\n" + "=" * 70)
    _emit("  LIVE RUNTIME CLIENT + CLI + MCP LIBRARY COVERAGE")
    _emit("=" * 70)

    _preflight()

    with local_runtime_daemon():
        from apps.mcp_server.registry import call_tool, get_tool_specs
        from apps.runtime.client import DaemonClient
        from apps.runtime.sdk import Runtime

        daemon_client = DaemonClient(timeout=30.0)
        runtime_sdk = Runtime(
            mode="local",
            auto_start_daemon=False,
            api_key=API_KEY,
            base_url=BASE_URL,
        )

        def test_daemon_client_runtime_modules() -> None:
            modules = asyncio.run(daemon_client.list_modules())
            module_names = {item["name"] for item in modules}
            expected = set(LLM_ROLLOUT_MODULE_NAMES)
            assert expected.issubset(module_names)
            functions_by_name = {
                str(item["name"]): tuple(str(function) for function in item["functions"])
                for item in modules
            }
            for module_name, expected_functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
                assert set(functions_by_name[module_name]) == set(expected_functions)

        check(
            "DaemonClient lists all 22 rollout runtime modules",
            test_daemon_client_runtime_modules,
        )

        def test_daemon_client_runtime_execute() -> None:
            for case in LLM_ROLLOUT_FUNCTION_CASES:
                payload = asyncio.run(daemon_client.execute(case.module, case.function, case.args))
                assert payload["success"] is True
                assert payload["engine_used"] == "mojo"
                assert_rollout_channel_result(case, payload["result"])

        check("DaemonClient executes all LLM rollout functions", test_daemon_client_runtime_execute)

        def test_runtime_sdk_modules() -> None:
            modules = runtime_sdk.list_modules()
            module_names = {item["name"] for item in modules}
            expected = set(LLM_ROLLOUT_MODULE_NAMES)
            assert expected.issubset(module_names)
            functions_by_name = {
                str(item["name"]): tuple(str(function) for function in item["functions"])
                for item in modules
            }
            for module_name, expected_functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
                assert set(functions_by_name[module_name]) == set(expected_functions)

        check("Runtime(mode='local') lists all 22 rollout modules", test_runtime_sdk_modules)

        def test_runtime_sdk_execute() -> None:
            for case in LLM_ROLLOUT_FUNCTION_CASES:
                payload = runtime_sdk.execute(case.module, case.function, case.args)
                assert payload["success"] is True
                assert payload["engine_used"] == "mojo"
                assert_rollout_channel_result(case, payload["result"])

        check("Runtime(mode='local') executes all LLM rollout functions", test_runtime_sdk_execute)

        def test_cli_runtime_modules() -> None:
            proc = _run_cli("runtime", "modules", "--format", "json")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            module_names = {item["name"] for item in payload["modules"]}
            expected = set(LLM_ROLLOUT_MODULE_NAMES)
            assert expected.issubset(module_names)
            functions_by_name = {
                item["name"]: tuple(str(function) for function in item["functions"])
                for item in payload["modules"]
            }
            for module_name, expected_functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
                assert set(functions_by_name[module_name]) == set(expected_functions)

        check("CLI lists all 22 rollout runtime modules", test_cli_runtime_modules)

        def test_cli_runtime_functions() -> None:
            proc = _run_cli("runtime", "functions", "vector_kernels.table", "--format", "json")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            assert payload["module"] == "vector_kernels.table"
            assert set(payload["functions"]) == set(
                LLM_ROLLOUT_FUNCTIONS_BY_MODULE["vector_kernels.table"]
            )

        check("CLI runtime functions works for dotted rollout modules", test_cli_runtime_functions)

        def test_cli_runtime_execute() -> None:
            for case in LLM_ROLLOUT_FUNCTION_CASES:
                proc = _run_cli_in_process(
                    "runtime",
                    "execute",
                    case.module,
                    case.function,
                    "--args-json",
                    json.dumps(case.args),
                    "--format",
                    "json",
                )
                assert proc.returncode == 0, proc.stderr or proc.stdout
                payload = json.loads(proc.stdout)
                assert payload["module"] == case.module
                assert payload["function"] == case.function
                assert payload["engine_used"] == "mojo"
                assert payload["success"] is True
                assert_rollout_channel_result(case, payload["result"])

        check("CLI executes all LLM rollout functions", test_cli_runtime_execute)

        def test_cli_benchmark_rollout_artifact() -> None:
            _ensure_rollout_parity_benchmark_artifact()
            summary = json.loads(ROLLOUT_PARITY_BENCHMARK.read_text())
            proc = _run_cli("benchmark")
            assert proc.returncode == 0, proc.stderr or proc.stdout
            assert "Source: build/llm_rollout_parity_benchmark.json" in proc.stdout
            assert (
                f"Scope: {len(LLM_ROLLOUT_MODULE_NAMES)}-library "
                "LLM rollout parity proof."
            ) in proc.stdout
            assert (
                f"{len(LLM_ROLLOUT_FUNCTION_CASES)} public runtime functions" in proc.stdout
            )
            assert (
                f"{_format_speedup_value(float(summary['median_speedup_x']))}×" in proc.stdout
            )
            assert f"{_format_speedup_value(float(summary['max_speedup_x']))}×" in proc.stdout

        check("CLI benchmark reports rollout proof artifact", test_cli_benchmark_rollout_artifact)

        def test_mcp_tool_listing() -> None:
            tool_names = {tool["name"] for tool in get_tool_specs()}
            assert "list_runtime_libraries" in tool_names
            assert "execute_runtime_library" in tool_names

        check("MCP registry exposes runtime library tools", test_mcp_tool_listing)

        def test_mcp_runtime_libraries() -> None:
            payload = json.loads(asyncio.run(call_tool("list_runtime_libraries", {})))
            module_names = {item["name"] for item in payload["libraries"]}
            expected = set(LLM_ROLLOUT_MODULE_NAMES)
            assert expected.issubset(module_names)
            functions_by_name = {
                item["name"]: tuple(str(function) for function in item["functions"])
                for item in payload["libraries"]
            }
            for module_name, expected_functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
                assert set(functions_by_name[module_name]) == set(expected_functions)

        check("MCP lists every rollout function across all modules", test_mcp_runtime_libraries)

        def test_mcp_runtime_execute() -> None:
            for case in LLM_ROLLOUT_FUNCTION_CASES:
                payload = json.loads(
                    asyncio.run(
                        call_tool(
                            "execute_runtime_library",
                            {
                                "module": case.module,
                                "function": case.function,
                                "args": case.args,
                            },
                        )
                    )
                )
                assert payload["module"] == case.module
                assert payload["function"] == case.function
                assert payload["engine_used"] == "mojo"
                assert payload["success"] is True
                assert_rollout_channel_result(case, payload["result"])

        check("MCP executes all LLM rollout functions", test_mcp_runtime_execute)

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
        script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
        channels=("daemon_client", "runtime_local", "cli", "mcp"),
        minimum_passed=11,
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
