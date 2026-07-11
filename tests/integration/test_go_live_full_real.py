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
import socket
import struct
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
GO_LIVE_RUNTIME_DIR = ROOT / "build" / "go-live-runtime"
GO_LIVE_RUNTIME_WORKER_ENV = "ALGENTA_GO_LIVE_RUNTIME_WORKER"
GO_LIVE_RUNTIME_BUILD_TIMEOUT = int(
    os.environ.get("ALGENTA_GO_LIVE_RUNTIME_BUILD_TIMEOUT", "420")
)
GO_LIVE_RUNTIME_SMOKE_TIMEOUT = float(
    os.environ.get("ALGENTA_GO_LIVE_RUNTIME_SMOKE_TIMEOUT", "15")
)
GO_LIVE_RUNTIME_EXTRA_MODULES = ("ab_testing", "elevator")
RUNTIME_PREFLIGHT_SUITE = "Go-live source runtime worker preflight"

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
EXPECTED_SUITE_COUNT = 1 + 1 + len(LIVE_SUITES) + 1 + len(LOCAL_SUITES) + 1 + 1


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


def _tail(text: str, *, max_lines: int = 80) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:] if lines else ["<no output>"])


def _go_live_runtime_worker_path() -> Path:
    configured = os.environ.get(GO_LIVE_RUNTIME_WORKER_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return GO_LIVE_RUNTIME_DIR / "simulate"


def _go_live_runtime_required_modules() -> tuple[str, ...]:
    from tests.llm_rollout_matrix import LLM_ROLLOUT_MODULE_NAMES

    if not LLM_ROLLOUT_MODULE_NAMES:
        raise RuntimeError("LLM rollout runtime module fixture is empty.")
    return tuple(dict.fromkeys((*LLM_ROLLOUT_MODULE_NAMES, *GO_LIVE_RUNTIME_EXTRA_MODULES)))


def _runtime_worker_env(worker_path: Path) -> dict[str, str]:
    resolved = str(worker_path.resolve())
    return {
        "ALGENTA_NATIVE_WORKER": resolved,
        "ALGENTA_RUNTIME_WORKER": resolved,
        "ALGENTA_MOJO_BINARY": resolved,
        "MOJO_BINARY_PATH": resolved,
    }


def _worker_manifest_path(worker_path: Path) -> Path:
    return worker_path.with_name(f"{worker_path.name}.manifest.json")


def _read_worker_manifest(worker_path: Path) -> dict[str, Any] | None:
    manifest_path = _worker_manifest_path(worker_path)
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _worker_manifest_supports_modules(
    worker_path: Path,
    required_modules: tuple[str, ...],
) -> bool:
    manifest = _read_worker_manifest(worker_path)
    if manifest is None:
        return False
    module_filter = manifest.get("module_filter")
    if module_filter == []:
        return True
    if not isinstance(module_filter, list):
        return False
    filtered_modules = {item for item in module_filter if isinstance(item, str)}
    return set(required_modules).issubset(filtered_modules)


def _worker_manifest_is_current(
    worker_path: Path,
    required_modules: tuple[str, ...],
) -> bool:
    if not worker_path.exists() or not os.access(worker_path, os.X_OK):
        return False
    if not _worker_manifest_supports_modules(worker_path, required_modules):
        return False
    from apps.runtime.mojo_binary_freshness import inspect_mojo_binary_freshness

    return inspect_mojo_binary_freshness(worker_path).is_fresh


def _recv_worker_frame(sock: socket.socket) -> dict[str, Any]:
    header = sock.recv(4)
    if len(header) != 4:
        raise RuntimeError("Runtime worker returned a short frame header.")
    frame_len = struct.unpack(">I", header)[0]
    payload = bytearray()
    while len(payload) < frame_len:
        chunk = sock.recv(frame_len - len(payload))
        if not chunk:
            raise RuntimeError("Runtime worker closed the socket before completing a frame.")
        payload.extend(chunk)
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise RuntimeError("Runtime worker returned a non-object frame.")
    return decoded


def _send_worker_frame(sock: socket.socket, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    sock.sendall(struct.pack(">I", len(body)) + body)
    return _recv_worker_frame(sock)


def _wait_for_worker_socket(
    proc: subprocess.Popen[str],
    socket_path: Path,
) -> None:
    deadline = time.monotonic() + GO_LIVE_RUNTIME_SMOKE_TIMEOUT
    while not socket_path.exists():
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout is not None else ""
            raise RuntimeError(
                "Runtime worker exited before opening the smoke-test socket.\n"
                + _tail(output)
            )
        if time.monotonic() >= deadline:
            proc.terminate()
            raise TimeoutError("Timed out waiting for runtime worker smoke-test socket.")
        time.sleep(0.01)


def _connect_worker_socket(socket_path: Path) -> socket.socket:
    deadline = time.monotonic() + GO_LIVE_RUNTIME_SMOKE_TIMEOUT
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(GO_LIVE_RUNTIME_SMOKE_TIMEOUT)
        try:
            client.connect(str(socket_path))
            return client
        except OSError as exc:
            last_error = exc
            client.close()
            time.sleep(0.01)
    raise RuntimeError(f"Timed out connecting to runtime worker socket: {last_error}")


def _smoke_go_live_runtime_worker(worker_path: Path) -> None:
    from apps.runtime.mojo_library_runner import (
        build_runtime_library_worker_request,
        parse_runtime_library_worker_response,
    )
    from tests.llm_rollout_matrix import LLM_ROLLOUT_FUNCTION_CASES, assert_rollout_channel_result

    if not LLM_ROLLOUT_FUNCTION_CASES:
        raise RuntimeError("LLM rollout runtime function fixture is empty.")
    case = next(
        (
            item
            for item in LLM_ROLLOUT_FUNCTION_CASES
            if item.module == "bpe_tokenizer" and item.function == "bpe_merge_score"
        ),
        LLM_ROLLOUT_FUNCTION_CASES[0],
    )
    function_spec, request = build_runtime_library_worker_request(
        case.module,
        case.function,
        case.args,
    )
    tmp_dir = Path(tempfile.mkdtemp(prefix="algenta-go-live-runtime-smoke-"))
    socket_path = tmp_dir / "worker.sock"
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            [str(worker_path), "--server", str(socket_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_for_worker_socket(proc, socket_path)
        with _connect_worker_socket(socket_path) as client:
            ready = _recv_worker_frame(client)
            if ready != {"status": "ready"}:
                raise RuntimeError(f"Unexpected runtime worker handshake: {ready!r}")
            response = _send_worker_frame(client, request)
        result = parse_runtime_library_worker_response(
            case.module,
            case.function,
            response,
            function_spec=function_spec,
        )
        assert_rollout_channel_result(case, result)
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _build_go_live_runtime_worker(
    worker_path: Path,
    required_modules: tuple[str, ...],
) -> None:
    build_script = ROOT / "scripts" / "build_mojo_binary.sh"
    source_main = ROOT / "mojo" / "engine" / "main.mojo"
    worker_path.parent.mkdir(parents=True, exist_ok=True)
    build_dir = Path(tempfile.mkdtemp(prefix="src-", dir=str(worker_path.parent)))
    try:
        temp_main = build_dir / "main.mojo"
        temp_dispatch = build_dir / "runtime_library_dispatch_generated.mojo"
        temp_main.write_text(source_main.read_text(encoding="utf-8"), encoding="utf-8")
        env = {
            **os.environ,
            "MOJO_SRC": str(temp_main),
            "DISPATCH_OUTPUT_PATH": str(temp_dispatch),
            "ENGINE_INCLUDE_DIR": str(ROOT / "mojo" / "engine"),
            "BINARY_PATH": str(worker_path),
            "OBJECT_PATH": str(worker_path.with_suffix(".o")),
            "TEMP_OBJECT_PATH": str(worker_path.with_suffix(".o.tmp")),
            "TEMP_BINARY_PATH": str(worker_path.with_name(f"{worker_path.name}.tmp")),
            "MOJO_RUNTIME_MODULE_FILTER": ",".join(required_modules),
        }
        proc = subprocess.run(
            ["bash", str(build_script)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=GO_LIVE_RUNTIME_BUILD_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            "Timed out building the filtered go-live runtime worker after "
            f"{GO_LIVE_RUNTIME_BUILD_TIMEOUT}s."
        ) from exc
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)

    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise RuntimeError("Filtered go-live runtime worker build failed.\n" + _tail(output))


def _ensure_go_live_runtime_worker() -> Path:
    worker_path = _go_live_runtime_worker_path()
    required_modules = _go_live_runtime_required_modules()
    worker_path.parent.mkdir(parents=True, exist_ok=True)
    if _worker_manifest_is_current(worker_path, required_modules):
        try:
            _smoke_go_live_runtime_worker(worker_path)
            print(f"  {PASS} Using preflighted runtime worker: {worker_path}", flush=True)
            return worker_path
        except Exception as exc:  # noqa: BLE001
            print(f"  … Rebuilding runtime worker after smoke failure: {exc}", flush=True)

    print(
        "  … Building filtered go-live runtime worker "
        f"({len(required_modules)} modules): {worker_path}",
        flush=True,
    )
    _build_go_live_runtime_worker(worker_path, required_modules)
    if not _worker_manifest_is_current(worker_path, required_modules):
        raise RuntimeError("Filtered go-live runtime worker built without a current manifest.")
    _smoke_go_live_runtime_worker(worker_path)
    print(f"  {PASS} Runtime worker preflight passed: {worker_path}", flush=True)
    return worker_path


def _run_runtime_worker_preflight() -> tuple[bool, float, str, Path | None]:
    print(f"  … Starting {RUNTIME_PREFLIGHT_SUITE}", flush=True)
    started = time.perf_counter()
    try:
        worker_path = _ensure_go_live_runtime_worker()
        elapsed = time.perf_counter() - started
        return True, elapsed, str(worker_path), worker_path
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        message = f"{type(exc).__name__}: {exc}"
        print(f"  {FAIL} {RUNTIME_PREFLIGHT_SUITE} ({elapsed:.1f}s)", flush=True)
        print("    ── output tail ──", flush=True)
        for line in _tail(message).splitlines():
            print(f"    │ {line}", flush=True)
        return False, elapsed, message, None


def _fresh_live_suite_env(
    *,
    env_base: dict[str, str],
    api_port: int,
    api_key: str,
    runtime_dir: Path,
) -> dict[str, str]:
    base_url = f"http://127.0.0.1:{api_port}"
    return {
        **env_base,
        "DE_BASE_URL": base_url,
        "ALGENTA_BASE_URL": base_url,
        "ALGENTA_API_URL": base_url,
        "ALGENTA_CONTROL_PLANE_URL": base_url,
        "DE_API_KEY": api_key,
        "ALGENTA_API_KEY": api_key,
        "ALGENTA_TEST_IGNORE_HOSTED_LIVE_CREDENTIALS": "0",
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_SIMULATION_PERSIST_TRANSPORT": (
            LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT
        ),
    }


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
            env_live = _fresh_live_suite_env(
                env_base=env_base,
                api_port=api_port,
                api_key=api_key,
                runtime_dir=runtime_dir,
            )
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
        "top_level_suite_count": 4,
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
        ok, elapsed, _preflight_output, runtime_worker_path = _run_runtime_worker_preflight()
        results.append((RUNTIME_PREFLIGHT_SUITE, ok, elapsed))
        if not ok or runtime_worker_path is None:
            print("\nRuntime worker preflight failed. Aborting broader suite.", flush=True)
            return 1

        runtime_env = _runtime_worker_env(runtime_worker_path)

        # Phase 1: self-contained local connectivity gate
        env_base = {
            "PYTHONPATH": str(ROOT),
            "DATABASE_URL": DEFAULT_DB_URL,
            "DATABASE_URL_SYNC": DEFAULT_DB_URL_SYNC,
            "REDIS_URL": DEFAULT_REDIS_URL,
            "ARROW_USER_SIMD_LEVEL": os.environ.get("ARROW_USER_SIMD_LEVEL", "NONE"),
            **runtime_env,
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
