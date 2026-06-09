"""
Live TypeScript runtime integration tests against a real API server.

Prerequisites:
  1. API server running and reachable via DE_BASE_URL
  2. Valid API key in DE_API_KEY
  3. TypeScript SDK dependencies installed
  4. Mojo runtime build available for the local daemon-backed libraries surface

This validates:
  - local daemon-backed Mojo runtime libraries
  - API-key lifecycle and hosted device binding
  - Runtime(mode="api") connector/query matrix
  - Runtime(mode="api") plan-aligned helper routes

Run:
  DE_API_KEY="..." DE_BASE_URL="http://127.0.0.1:8000" \
    python3 tests/integration/test_typescript_runtime_live.py

Or start an isolated current-checkout API server with writable temp dirs:
  DE_API_KEY="..." ALGENTA_TEST_START_API_SERVER=1 \
    python3 tests/integration/test_typescript_runtime_live.py
"""

from __future__ import annotations

import os
import sys

if __name__ == "__main__" and os.environ.get("ALGENTA_SKIP_MOJO_RUNTIME", "0") == "1":
    print("[skip] tests/integration/test_typescript_runtime_live.py — ALGENTA_SKIP_MOJO_RUNTIME=1")
    sys.exit(0)

import asyncio
import contextlib
import importlib
import io
import json
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TS_SDK_DIR = ROOT / "packages" / "ts-sdk"
TS_DIST_ENTRY_CANDIDATES = (
    TS_SDK_DIR / "dist" / "index.mjs",
    TS_SDK_DIR / "dist" / "index.js",
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests._manifest_backed_integrations import (
    contract_integrations_match_manifest,
)

try:
    from tests.integration.live_local_auth_bootstrap import (
        ensure_bootstrapped_local_live_api_key,
    )
    from tests.integration.live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
    )
except ModuleNotFoundError:
    from live_local_auth_bootstrap import ensure_bootstrapped_local_live_api_key
    from live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
    )

CONFIGURED_BASE_URL = configured_local_live_base_url()
BASE_URL = (CONFIGURED_BASE_URL or "http://127.0.0.1:8000").rstrip("/")
_ISOLATED_API_SERVER_ACTIVE = False
API_KEY = resolve_local_live_api_key()
INITIAL_API_KEY_CONFIGURED = has_configured_local_live_api_key()
API_KEY_CONFIGURED = INITIAL_API_KEY_CONFIGURED
API_KEY, API_KEY_CONFIGURED, LOCAL_LIVE_AUTH_BOOTSTRAP_ERROR = (
    ensure_bootstrapped_local_live_api_key(
        api_key=API_KEY,
        api_key_configured=API_KEY_CONFIGURED,
        active_base_url=BASE_URL,
    )
)
TEST_FILES = ROOT / "test_files"

# ruff: noqa: E402
from apps.platform_contract import PlatformContractResponse
from apps.runtime_manifest import (
    RuntimeAdminBenchmarksResponse,
    normalize_runtime_validation_payload,
)
from benchmarks.llm_rollout_live_artifacts import (
    LIVE_SUMMARY_ARTIFACTS,
    write_live_summary_artifact,
)
from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_check_filter import (
    filtered_live_check_reason,
    filtered_minimum_passed,
    live_check_filter_tokens,
    selected_live_check_filter,
    should_run_live_check,
)
from tests.integration.live_data_source_server import (
    default_refreshable_dataset_payload,
    static_json_server,
)
from tests.integration.live_repository_fixture import (
    assert_repository_intelligence_capabilities_payload,
    live_repository_fixture,
    local_repository_live_support_reason,
)
from tests.integration.live_webhook_receiver import webhook_receiver
from tests.integration.runtime_live_db_helpers import (
    postgres_canonical_connector,
    temporary_postgres_fixture,
)
from tests.llm_rollout_matrix import (
    LLM_ROLLOUT_CASES_JSON,
    LLM_ROLLOUT_FUNCTION_CASES,
    LLM_ROLLOUT_FUNCTIONS_BY_MODULE,
    LLM_ROLLOUT_MODULE_NAMES,
    assert_rollout_channel_result,
)

REAL_MARCH_ORDERS = TEST_FILES / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
REAL_MARCH_FINANCIAL = TEST_FILES / "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"
REAL_MARCH_INACCURATE = (
    TEST_FILES
    / "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv"
)


PUBLIC_S3_CONNECTION = {
    "type": "s3",
    "bucket": "1000genomes",
    "key": "20131219.populations.tsv",
    "region": "us-east-1",
    "anonymous": True,
    "format": "tsv",
}
PUBLIC_S3_SOURCE_REF = "s3://1000genomes/20131219.populations.tsv"
PUBLIC_REST_CONNECTION = {
    "type": "rest",
    "base_url": "https://api.weather.gov",
    "path": "/stations",
    "method": "GET",
    "headers": {
        "User-Agent": "algenta-ts-runtime-live/1.0",
        "Accept": "application/geo+json",
    },
    "params": {"state": "CO"},
    "data_path": "features",
    "timeout": 60,
}
MOJO_LIBRARY_MODULE = "ab_testing"
MOJO_LIBRARY_FUNCTION = "sample_size_proportion"
MOJO_LIBRARY_ARGS = {
    "p1": 0.10,
    "p2": 0.12,
    "alpha": 0.05,
    "power": 0.8,
}

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
SUITE_NAME = "typescript_sdk_local_runtime"
SUMMARY_ARTIFACT = LIVE_SUMMARY_ARTIFACTS[SUITE_NAME]
ACTIVE_LIVE_CHECK_FILTER = selected_live_check_filter()
ACTIVE_LIVE_CHECK_FILTER_TOKENS = live_check_filter_tokens(ACTIVE_LIVE_CHECK_FILTER)
results: list[tuple[str, str, str]] = []
MISSING_JOB_ID = "00000000-0000-0000-0000-000000000001"


class SkippedCheckError(Exception):
    """Raised when an optional live slice is intentionally not configured."""


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _assert_empty_provider_trace_payload(
    payload: dict[str, Any], *, output_items: bool = False
) -> None:
    assert payload["provider_backend"] is None, payload
    assert payload["provider_model_id"] is None, payload
    assert payload["provider_attempts"] == [], payload
    if output_items:
        for item in payload["output"]:
            assert item["provider_backend"] is None, item
            assert item["provider_model_id"] is None, item
            assert item["provider_attempts"] == [], item


def check(name: str, fn) -> Any:
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    if not should_run_live_check(name, ACTIVE_LIVE_CHECK_FILTER_TOKENS):
        reason = filtered_live_check_reason(ACTIVE_LIVE_CHECK_FILTER)
        results.append((SKIP, name, reason))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {reason}")
        return None
    try:
        out = fn()
        results.append((PASS, name, ""))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
        return out
    except SkippedCheckError as exc:
        results.append((SKIP, name, str(exc)))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
        return None
    except AssertionError as exc:
        missing_key_reason = _missing_live_api_key_reason(exc)
        if missing_key_reason:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
                f"{missing_key_reason}"
            )
            return None
        results.append((FAIL, name, str(exc)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
        return None
    except Exception as exc:  # noqa: BLE001
        missing_key_reason = _missing_live_api_key_reason(exc)
        if missing_key_reason:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
                f"{missing_key_reason}"
            )
            return None
        results.append((FAIL, name, f"{type(exc).__name__}: {exc}"))
        _emit(
            f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): "
            f"{type(exc).__name__}: {exc}"
        )
        return None


def build_ts_sdk() -> None:
    proc = subprocess.run(
        _ts_build_command(),
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"TypeScript SDK build failed.\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    if _resolve_ts_dist_entry() is None:
        candidates = ", ".join(str(path) for path in TS_DIST_ENTRY_CANDIDATES)
        raise AssertionError(f"Built TypeScript runtime entry missing. Checked: {candidates}")


def _pnpm_command() -> list[str]:
    if shutil.which("pnpm"):
        return ["pnpm"]
    if shutil.which("corepack"):
        return ["corepack", "pnpm"]
    if shutil.which("npx"):
        return ["npx", "pnpm"]
    raise FileNotFoundError(
        "Unable to find pnpm-compatible package manager. Install pnpm or ensure corepack is available."
    )


def _ts_build_command() -> list[str]:
    tsconfig_path = TS_SDK_DIR / "tsconfig.json"
    try:
        pnpm_cmd = _pnpm_command()
    except FileNotFoundError:
        local_tsc = TS_SDK_DIR / "node_modules" / ".bin" / "tsc"
        if local_tsc.exists():
            return [str(local_tsc), "-p", str(tsconfig_path)]
        node_binary = shutil.which("node")
        bundled_tsc = TS_SDK_DIR / "node_modules" / "typescript" / "bin" / "tsc"
        if node_binary and bundled_tsc.exists():
            return [node_binary, str(bundled_tsc), "-p", str(tsconfig_path)]
        raise
    return [*pnpm_cmd, "--dir", str(TS_SDK_DIR), "build"]


def _resolve_ts_dist_entry() -> Path | None:
    for candidate in TS_DIST_ENTRY_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _free_tcp_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _port_open(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _probe_json(
    base_url: str,
    path: str,
    timeout: float = 3.0,
    *,
    headers: dict[str, str] | None = None,
):
    request = urllib.request.Request(
        f"{base_url}{path}",
        headers=headers or {},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            try:
                return response.status, json.loads(body)
            except Exception:
                return response.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        body = err.read()
        try:
            return err.code, json.loads(body)
        except Exception:
            return err.code, body.decode("utf-8", errors="replace")


def _endpoint_serves_canonical_runtime_surface(base_url: str) -> bool:
    try:
        status, health = _probe_json(base_url, "/v1/health", timeout=3.0)
        if status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
            return False
        auth_headers = {"Authorization": f"Bearer {API_KEY}"}
        status, contract = _probe_json(
            base_url,
            "/v1/meta/contract",
            timeout=5.0,
            headers=auth_headers,
        )
        if status != 200 or not isinstance(contract, dict):
            return False
        PlatformContractResponse.model_validate(contract)
        if not contract_integrations_match_manifest(contract["integrations"]):
            return False
        status, benchmarks = _probe_json(
            base_url,
            "/v1/admin/runtime/benchmarks",
            timeout=5.0,
            headers=auth_headers,
        )
        if status != 200 or not isinstance(benchmarks, dict):
            return False
        RuntimeAdminBenchmarksResponse.model_validate(
            normalize_runtime_validation_payload(benchmarks)
        )
        status, spec = _probe_json(base_url, "/openapi.json", timeout=5.0)
        if status != 200 or not isinstance(spec, dict):
            return False
        expected_security = [{"BearerAuth": []}, {"LegacyApiKey": []}]
        for path, method in (
            ("/v1/meta/contract", "get"),
            ("/v1/runtime/manifest", "get"),
            ("/v1/admin/runtime/modules", "get"),
            ("/v1/admin/runtime/benchmarks", "get"),
            ("/v1/admin/runtime/validation", "get"),
            ("/v1/me", "get"),
            ("/v1/me", "patch"),
            ("/v1/usage", "get"),
            ("/v1/limits", "get"),
            ("/v1/connectors", "get"),
            ("/v1/connectors", "post"),
            ("/v1/connectors/test", "post"),
            ("/v1/connectors/browse", "post"),
            ("/v1/connectors/{connector_id}", "get"),
            ("/v1/connectors/{connector_id}", "patch"),
            ("/v1/connectors/{connector_id}/test", "post"),
            ("/v1/connectors/{connector_id}/browse", "get"),
            ("/v1/connectors/{connector_id}", "delete"),
            ("/v1/data/connect", "post"),
            ("/v1/data", "get"),
            ("/v1/data/{dataset_id}", "get"),
            ("/v1/data/{dataset_id}/summary", "get"),
            ("/v1/data/{dataset_id}/refresh", "post"),
            ("/v1/data/{dataset_id}", "delete"),
            ("/v1/repositories/capabilities", "get"),
            ("/v1/repositories/{repository_id}/snapshots", "post"),
            ("/v1/repositories/{repository_id}/snapshots/{snapshot_id}", "get"),
            ("/v1/repositories/{repository_id}/triage", "post"),
            ("/v1/repositories/{repository_id}/decision-plans", "post"),
            ("/v1/repositories/{repository_id}/simulate", "post"),
            ("/v1/repositories/{repository_id}/apply", "post"),
            ("/v1/distributions", "get"),
            ("/v1/templates", "get"),
            ("/v1/billing/info", "get"),
            ("/v1/team", "get"),
            ("/v1/team/invite", "post"),
            ("/v1/team/{user_id}/role", "patch"),
            ("/v1/team/{user_id}", "delete"),
            ("/v1/jobs/list", "get"),
            ("/v1/jobs/{job_id}", "get"),
            ("/v1/jobs/{job_id}/result", "get"),
            ("/v1/jobs/{job_id}/cancel", "post"),
            ("/v1/triggers", "get"),
            ("/v1/triggers", "post"),
            ("/v1/triggers/{trigger_id}/fire", "post"),
            ("/v1/triggers/{trigger_id}/pause", "patch"),
            ("/v1/triggers/{trigger_id}", "delete"),
            ("/v1/device/list", "get"),
            ("/v1/device/{registration_id}", "delete"),
            ("/v1/metering", "post"),
            ("/v1/credits/refresh", "post"),
            ("/v1/audit-logs", "get"),
            ("/v1/audit-logs/artifacts", "get"),
            ("/v1/execution/policy", "get"),
            ("/v1/execution/policy/snapshots", "get"),
            ("/v1/execution/policy", "patch"),
            ("/v1/models", "get"),
            ("/v1/artifacts/resolve", "post"),
            ("/v1/tokenize", "post"),
            ("/v1/count_tokens", "post"),
            ("/v1/deployments/regions", "get"),
            ("/v1/deployments", "get"),
            ("/v1/chat/completions", "post"),
            ("/v1/responses", "post"),
            ("/v1/embeddings", "post"),
            ("/v1/embeddings/similarity", "post"),
            ("/v1/rerank", "post"),
            ("/v1/recommend", "post"),
            ("/v1/score", "post"),
            ("/v1/batch", "post"),
            ("/v1/compare", "post"),
            ("/v1/decision", "post"),
            ("/v1/agent/run", "post"),
            ("/v1/optimize", "post"),
            ("/v1/retrieve", "post"),
            ("/v1/forecast", "post"),
            ("/v1/decisions/plan", "post"),
            ("/v1/decisions", "post"),
            ("/v1/decisions", "get"),
            ("/v1/decisions/{decision_id}", "get"),
            ("/v1/decisions/{decision_id}/outcome", "patch"),
            ("/v1/decisions/{decision_id}/execute", "post"),
            ("/v1/decisions/{decision_id}", "delete"),
            ("/v1/agent/runs", "post"),
            ("/v1/agent/runs", "get"),
            ("/v1/agent/runs/{run_id}", "get"),
            ("/v1/agent/runs/{run_id}/events", "get"),
            ("/v1/agent/runs/{run_id}/checkpoints", "get"),
            ("/v1/agent/runs/checkpoints", "get"),
            ("/v1/agent/runs/{run_id}/mission-events", "get"),
            ("/v1/agent/runs/mission-events", "get"),
            ("/v1/agent/runs/{run_id}/telemetry", "get"),
            ("/v1/agent/runs/telemetry", "get"),
            ("/v1/agent/runs/{run_id}/approve", "post"),
            ("/v1/api-keys", "get"),
            ("/v1/api-keys", "post"),
            ("/v1/webhooks/test", "post"),
        ):
            operation = spec.get("paths", {}).get(path, {}).get(method, {})
            if path in {"/v1/meta/contract", "/v1/runtime/manifest"}:
                if operation.get("security") not in ([], None):
                    return False
            elif operation.get("security") != expected_security:
                return False
        for path, method in (
            ("/v1/chat/completions", "post"),
            ("/v1/responses", "post"),
            ("/v1/agent/runs/{run_id}/events", "get"),
        ):
            content = (
                spec.get("paths", {})
                .get(path, {})
                .get(method, {})
                .get("responses", {})
                .get("200", {})
                .get("content", {})
            )
            if "text/event-stream" not in content:
                return False
        status, models = _probe_json(
            base_url,
            "/v1/models",
            timeout=5.0,
            headers=auth_headers,
        )
        if status != 200 or not isinstance(models, dict) or not isinstance(models.get("data"), list):
            return False
        return True
    except Exception:
        return False


def _isolated_api_server_requested() -> bool:
    value = os.environ.get("ALGENTA_TEST_START_API_SERVER", "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    return not CONFIGURED_BASE_URL and not INITIAL_API_KEY_CONFIGURED


def _isolated_api_server_env(tmp_root: Path, port: int) -> dict[str, str]:
    sources_dir = tmp_root / "sources"
    runtime_dir = tmp_root / "runtime"
    sources_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "ALGENTA_SOURCES_DIR": str(sources_dir),
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL": "repository.deterministic_local_v1",
        "DE_BASE_URL": base_url,
        "ALGENTA_BASE_URL": base_url,
    }
    env.setdefault(
        "JWT_SECRET",
        "change-me-in-production-use-256-bit-random-value",
    )
    return env


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


def _run_api_migrations(env: dict[str, str]) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ROOT / "apps" / "api_server" / "alembic.ini"),
            "upgrade",
            "head",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Alembic upgrade failed for isolated API server.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )


def _runtime_daemon_env(runtime_dir: Path, tcp_port: int, api_key: str) -> dict[str, str]:
    env = {
        "ALGENTA_RUNTIME_DIR": str(runtime_dir),
        "ALGENTA_CONTROL_PLANE_URL": BASE_URL,
        "ALGENTA_BASE_URL": BASE_URL,
        "DE_BASE_URL": BASE_URL,
        "DE_API_KEY": api_key,
        "ALGENTA_DAEMON_SOCK": str(runtime_dir / "daemon.sock"),
        "ALGENTA_DAEMON_TCP": f"127.0.0.1:{tcp_port}",
        "ALGENTA_MOJO_SOCK": str(runtime_dir / "mojo.sock"),
        "JWT_SECRET": "change-me-in-production-use-256-bit-random-value",
    }
    if not api_key:
        env["ALGENTA_RUNTIME_DEV_MODE"] = "1"
    return env


def _runtime_daemon_api_key() -> str:
    return API_KEY if API_KEY_CONFIGURED else ""


def _reload_runtime_modules() -> None:
    modules = [
        "apps.runtime.license",
        "apps.runtime.credits",
        "apps.runtime.metering",
        "apps.runtime.entitlement",
        "apps.runtime.client",
        "apps.runtime.daemon",
        "apps.runtime.sdk",
    ]
    for module_name in modules:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])


def _read_daemon_log(runtime_dir: Path) -> str:
    log_path = runtime_dir / "daemon.log"
    if not log_path.exists():
        return ""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    tail = "\n".join(lines[-40:])
    return f"\nDaemon log tail:\n{tail}"


def _read_log_tail(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not lines:
        return ""
    tail = "\n".join(lines[-80:])
    return f"\nLog tail:\n{tail}"


def _wait_for_api_server(
    base_url: str,
    proc: subprocess.Popen[str],
    log_path: Path,
    timeout: float = 30.0,
) -> None:
    start = time.monotonic()
    last_error = "server did not report healthy"
    while time.monotonic() - start < timeout:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Isolated API server exited early with code {proc.returncode}."
                f"{_read_log_tail(log_path)}"
            )
        request = urllib.request.Request(f"{base_url}/v1/health", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=2.0) as response:
                if response.status == 200:
                    return
                last_error = f"/v1/health returned {response.status}"
        except urllib.error.HTTPError as exc:
            last_error = f"/v1/health returned {exc.code}"
        except urllib.error.URLError as exc:
            last_error = str(exc.reason)
        time.sleep(0.2)
    raise RuntimeError(
        f"Timed out waiting for isolated API server at {base_url}: {last_error}."
        f"{_read_log_tail(log_path)}"
    )


def _wait_for_runtime_daemon(tcp_target: str, runtime_dir: Path, timeout: float = 20.0) -> None:
    start = time.monotonic()
    last_error = "daemon did not open its TCP listener"
    while time.monotonic() - start < timeout:
        host, port_text = tcp_target.rsplit(":", 1)
        port = int(port_text)
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) != 0:
                last_error = "daemon TCP target not reachable yet"
                time.sleep(0.1)
                continue
        from apps.runtime.client import DaemonClient

        health = asyncio.run(DaemonClient(tcp_addr=tcp_target, timeout=2.0).health())
        if health.get("status") == "ok":
            return
        last_error = str(health)
        time.sleep(0.1)
    raise RuntimeError(
        f"Timed out waiting for local runtime daemon at {tcp_target}: {last_error}."
        f"{_read_daemon_log(runtime_dir)}"
    )


def _bootstrap_runtime_entitlement() -> None:
    api_key = _runtime_daemon_api_key()
    if not api_key:
        return
    from apps.runtime.license import issue_and_store

    lic = issue_and_store(api_key)
    if not lic.valid:
        raise RuntimeError(
            "Runtime license bootstrap failed for the TypeScript local Mojo probe: "
            f"{lic.message or 'unknown error'}"
        )


@contextlib.contextmanager
def local_runtime_daemon() -> dict[str, str]:
    runtime_dir = Path(tempfile.mkdtemp(prefix="algenta-ts-mojo-live-"))
    runtime_api_key = _runtime_daemon_api_key()
    env_updates = _runtime_daemon_env(runtime_dir, _free_tcp_port(), runtime_api_key)
    env_updates.update(_license_verification_env())
    managed_keys = set(env_updates) | {"ALGENTA_API_KEY", "ALGENTA_RUNTIME_DEV_MODE"}
    old_env = {key: os.environ.get(key) for key in managed_keys}
    os.environ.update(env_updates)
    if "ALGENTA_RUNTIME_DEV_MODE" not in env_updates:
        os.environ.pop("ALGENTA_RUNTIME_DEV_MODE", None)
    if runtime_api_key:
        os.environ["ALGENTA_API_KEY"] = runtime_api_key
    else:
        os.environ.pop("ALGENTA_API_KEY", None)
    _reload_runtime_modules()
    from apps.runtime.daemon import cmd_start, cmd_stop, is_running

    try:
        _bootstrap_runtime_entitlement()
        if is_running():
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_stop()
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_start(foreground=False)
        _wait_for_runtime_daemon(env_updates["ALGENTA_DAEMON_TCP"], runtime_dir)
        yield env_updates
    finally:
        try:
            if is_running():
                with contextlib.redirect_stdout(io.StringIO()):
                    cmd_stop()
        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value
            _reload_runtime_modules()
            shutil.rmtree(runtime_dir, ignore_errors=True)


@contextlib.contextmanager
def _boot_isolated_api_server() -> str:
    global BASE_URL, _ISOLATED_API_SERVER_ACTIVE

    tmp_root = Path(tempfile.mkdtemp(prefix="algenta-ts-live-api-"))
    port = _free_tcp_port()
    base_url = f"http://127.0.0.1:{port}"
    env = _isolated_api_server_env(tmp_root, port)
    _run_api_migrations(env)
    log_path = tmp_root / f"api_server_{port}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api_server.main:app",
            "--host",
            "127.0.0.1",
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
    log_handle.close()
    old_base_url = BASE_URL
    old_env = {
        "DE_BASE_URL": os.environ.get("DE_BASE_URL"),
        "ALGENTA_BASE_URL": os.environ.get("ALGENTA_BASE_URL"),
    }
    try:
        _wait_for_api_server(base_url, proc, log_path)
        BASE_URL = base_url
        _ISOLATED_API_SERVER_ACTIVE = True
        os.environ["DE_BASE_URL"] = base_url
        os.environ["ALGENTA_BASE_URL"] = base_url
        yield base_url
    finally:
        BASE_URL = old_base_url
        _ISOLATED_API_SERVER_ACTIVE = False
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        shutil.rmtree(tmp_root, ignore_errors=True)


@contextlib.contextmanager
def isolated_api_server() -> str:
    if not _isolated_api_server_requested():
        yield BASE_URL
        return
    with _boot_isolated_api_server() as base_url:
        yield base_url


@contextlib.contextmanager
def canonical_runtime_api_surface_server() -> str:
    if CONFIGURED_BASE_URL:
        yield BASE_URL
        return
    if _ISOLATED_API_SERVER_ACTIVE:
        yield BASE_URL
        return
    if not INITIAL_API_KEY_CONFIGURED:
        with _boot_isolated_api_server() as base_url:
            yield base_url
            return
    if _endpoint_serves_canonical_runtime_surface(BASE_URL):
        yield BASE_URL
        return
    with _boot_isolated_api_server() as base_url:
        yield base_url


def write_sqlite_fixture(path: Path) -> None:
    rows = [
        {"product_line": "Electronics", "revenue": 42193221.0, "region": "US"},
        {"product_line": "Apparel", "revenue": 28114992.0, "region": "US"},
        {"product_line": "Electronics", "revenue": 1204000.0, "region": "CA"},
    ]
    connection = sqlite3.connect(path)
    try:
        connection.execute('DROP TABLE IF EXISTS "orders"')
        connection.execute(
            'CREATE TABLE "orders" ("product_line" TEXT, "revenue" REAL, "region" TEXT)'
        )
        connection.executemany(
            'INSERT INTO "orders" ("product_line", "revenue", "region") VALUES (?, ?, ?)',
            [(row["product_line"], row["revenue"], row["region"]) for row in rows],
        )
        connection.commit()
    finally:
        connection.close()


def postgres_fixture_rows() -> list[dict[str, object]]:
    return [
        {"product_line": "Electronics", "revenue": 42193221.0, "region": "US"},
        {"product_line": "Apparel", "revenue": 28114992.0, "region": "US"},
        {"product_line": "Electronics", "revenue": 1204000.0, "region": "CA"},
    ]


def _node_probe(
    sqlite_path: Path,
    postgres_connector: dict[str, Any],
) -> dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live TypeScript runtime integration.")
    dist_entry = _resolve_ts_dist_entry()
    if dist_entry is None:
        candidates = ", ".join(str(path) for path in TS_DIST_ENTRY_CANDIDATES)
        raise RuntimeError(f"TypeScript SDK dist entry missing. Checked: {candidates}")
    script = f"""
import {{ Runtime }} from {json.dumps(dist_entry.resolve().as_uri())};

const runtime = new Runtime({{
  mode: "api",
  apiKey: process.env.DE_API_KEY,
  baseUrl: process.env.DE_BASE_URL,
}});

const publicRest = {json.dumps(PUBLIC_REST_CONNECTION)};
const publicS3 = {json.dumps(PUBLIC_S3_CONNECTION)};
const sqliteDescriptor = {{
  type: "sqlite",
  path: {json.dumps(str(sqlite_path.resolve()))},
  table: "orders",
}};
const postgresDescriptor = {json.dumps(postgres_connector)};
const localOrdersCsv = {json.dumps(str(REAL_MARCH_ORDERS.resolve()))};
const localFinancialCsv = {json.dumps(str(REAL_MARCH_FINANCIAL.resolve()))};
const localInaccurateCsv = {json.dumps(str(REAL_MARCH_INACCURATE.resolve()))};

async function datasetSchema(registration) {{
  const datasetId = registration.dataset_id ?? registration.source_id;
  if (!datasetId) {{
    throw new Error(`No dataset id available for ${{registration?.name ?? "unknown"}}`);
  }}
  const response = await fetch(`${{process.env.DE_BASE_URL}}/v1/data/${{datasetId}}`, {{
    headers: {{
      "X-API-Key": String(process.env.DE_API_KEY ?? ""),
    }},
  }});
  if (!response.ok) {{
    throw new Error(`Schema fetch failed for ${{registration?.name ?? "unknown"}}: ${{response.status}}`);
  }}
  return await response.json();
}}

async function step(name, fn) {{
  try {{
    return await fn();
  }} catch (error) {{
    const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
    const details = error && typeof error === "object" && "details" in error
      ? JSON.stringify(error.details)
      : "";
    const message = error instanceof Error ? error.message : String(error);
    const suffix = details ? ` :: ${{details}}` : "";
    throw new Error(`${{name}} failed${{code ? ` [${{code}}]` : ""}}: ${{message}}${{suffix}}`);
  }}
}}

async function metricField(registration) {{
  const schema = registration?.source_schema ?? registration?.schema ?? await datasetSchema(registration);
  if (schema && typeof schema === "object" && "source_schema" in schema) {{
    const nested = schema.source_schema;
    if (nested && typeof nested === "object") {{
      return metricField({{ ...registration, source_schema: nested }});
    }}
  }}
  const rawSchema = schema && typeof schema === "object" ? schema : {{}};
  const fields = Array.isArray(rawSchema.fields)
    ? rawSchema.fields
    : Array.isArray(rawSchema.columns)
      ? rawSchema.columns.map((column) => column?.name).filter((name) => typeof name === "string" && name.length > 0)
      : [];
  if (fields.length > 0) {{
    return String(fields[0]);
  }}
  throw new Error(`No metric field available for ${{registration?.name ?? "unknown"}}`);
}}

async function countQuery(registration) {{
  const plan = await runtime.resolve({{
    source_name: registration.name,
    metric: await metricField(registration),
    aggregation: "count",
  }});
  const verified = await runtime.verify(plan);
  const result = await runtime.query(plan);
  const scalar = typeof result.result === "number"
    ? result.result
    : Number(result.result?.value);
  return {{
    planHash: plan.plan_hash ?? plan.resolved_plan?.plan_hash ?? null,
    schemaRevision: plan.schema_revision ?? plan.resolved_plan?.schema_revision ?? null,
    valid: verified.valid,
    rowCount: registration.row_count,
    scalar,
  }};
}}

async function countQueryWithMetric(runtimeInstance, registration, metric) {{
  const plan = await runtimeInstance.resolve({{
    source_name: registration.name,
    metric,
    aggregation: "count",
  }});
  const verified = await runtimeInstance.verify(plan);
  const result = await runtimeInstance.query(plan);
  const scalar = typeof result.result === "number"
    ? result.result
    : Number(result.result?.value);
  return {{
    planHash: plan.plan_hash ?? plan.resolved_plan?.plan_hash ?? null,
    schemaRevision: plan.schema_revision ?? plan.resolved_plan?.schema_revision ?? null,
    valid: verified.valid,
    rowCount: registration.row_count,
    scalar,
  }};
}}

try {{
  const localRuntime = new Runtime();
  const localImported = await step(
    "Local CSV import preview",
    () =>
      localRuntime.importPreview(localOrdersCsv, {{
        name: "orders_detail",
        sourceRef: "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv",
        color: false,
      }}),
  );
  const localCount = await step(
    "Local CSV count query",
    () => countQueryWithMetric(localRuntime, localImported.registration, "Sales (incl. tax)"),
  );
  const localBundle = await step(
    "Local CSV bundle preview",
    () =>
      localRuntime.importBundlePreview(
        [localOrdersCsv, localFinancialCsv, localInaccurateCsv],
        {{
          names: ["orders_detail_bundle", "orders_financial_bundle", "top_inaccurate_items_bundle"],
          sourceRefs: [
            "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv",
            "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv",
            "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv",
          ],
          color: false,
        }},
      ),
  );

  const restRegistration = await step("REST connect", () => runtime.connect(publicRest, {{ name: "weather_stations" }}));
  const rest = await step("REST count query", () => countQuery(restRegistration));

  const imported = await step(
    "S3 import preview",
    () =>
      runtime.importPreview(publicS3, {{
        name: "noaa_hourly",
        sourceRef: {json.dumps(PUBLIC_S3_SOURCE_REF)},
        color: false,
      }}),
  );
  const s3 = await step("S3 count query", () => countQuery(imported.registration));

  const sqliteRegistration = await step(
    "SQLite connect",
    () => runtime.connect(sqliteDescriptor, {{ name: "orders_sqlite" }}),
  );
  const sqlite = await step("SQLite count query", () => countQuery(sqliteRegistration));

  const postgresRegistration = await step(
    "Postgres connect",
    () => runtime.connect(postgresDescriptor, {{ name: "orders_postgres" }}),
  );
  const postgres = await step("Postgres count query", () => countQuery(postgresRegistration));

  const apiBundle = await step(
    "API bundle preview",
    () =>
      runtime.importBundlePreview(
        [sqliteDescriptor, postgresDescriptor, publicS3, publicRest],
        {{
          names: ["orders_sqlite_bundle", "orders_postgres_bundle", "noaa_hourly_bundle", "weather_stations_bundle"],
          sourceRefs: [
            {json.dumps(f"{sqlite_path.name}#orders")},
            {json.dumps(f"postgres://{postgres_connector['location']['schema']}.{postgres_connector['location']['table']}")},
            {json.dumps(PUBLIC_S3_SOURCE_REF)},
            "https://api.weather.gov/stations?state=CO",
          ],
          color: false,
        }},
      ),
  );

  process.stdout.write(JSON.stringify({{
    local: {{
      registration: localImported.registration,
      preview: localImported.preview,
      count: localCount,
    }},
    localBundle: {{
      preview: localBundle.preview,
      registrationCount: localBundle.registrations.length,
      failureCount: localBundle.failures.length,
    }},
    rest,
    s3: {{
      ...s3,
      preview: imported.preview,
    }},
    sqlite,
    postgres,
    apiBundle: {{
      preview: apiBundle.preview,
      registrationCount: apiBundle.registrations.length,
      failureCount: apiBundle.failures.length,
    }},
  }}));
}} catch (error) {{
  const message = error instanceof Error ? `${{error.name}}: ${{error.message}}` : String(error);
  process.stderr.write(message);
  process.exit(1);
}}
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=str(ROOT),
        env={
            **os.environ,
            "DE_BASE_URL": BASE_URL,
            "DE_API_KEY": API_KEY,
        },
        capture_output=True,
        text=True,
        timeout=240,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"TypeScript runtime probe failed.\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise RuntimeError(f"Failed to parse TypeScript runtime output: {proc.stdout}") from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected dict payload, received {type(payload)!r}")
    return payload


def _node_api_helper_probe(
    kind: str,
    *,
    webhook_url: str | None = None,
    dataset_source_url: str | None = None,
    repository_path: str | None = None,
) -> dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live TypeScript runtime integration.")
    dist_entry = _resolve_ts_dist_entry()
    if dist_entry is None:
        candidates = ", ".join(str(path) for path in TS_DIST_ENTRY_CANDIDATES)
        raise RuntimeError(f"TypeScript SDK dist entry missing. Checked: {candidates}")
    script = """
import { Runtime } from %DIST_ENTRY%;

const runtime = new Runtime({
  mode: "api",
  apiKey: process.env.DE_API_KEY,
  baseUrl: process.env.DE_BASE_URL,
  maxRetries: 0,
});

function output(payload) {
  process.stdout.write(JSON.stringify(payload));
}

async function captureJobError(operation) {
  try {
    const value = await operation();
    return { ok: true, value };
  } catch (error) {
    return {
      ok: false,
      name: error?.name ?? "Error",
      message: error?.message ?? String(error),
      statusCode: error?.statusCode ?? null,
      errorCode: error?.errorCode ?? null,
      responseBody: error?.responseBody ?? null,
    };
  }
}

async function captureApiError(operation) {
  try {
    const value = await operation();
    return { ok: true, value };
  } catch (error) {
    return {
      ok: false,
      name: error?.name ?? "Error",
      message: error?.message ?? String(error),
      statusCode: error?.statusCode ?? null,
      errorCode: error?.errorCode ?? null,
      responseBody: error?.responseBody ?? null,
    };
  }
}

async function main() {
  const kind = process.argv[1];
  try {
    switch (kind) {
      case "proof": {
        const manifest = await runtime.getRuntimeManifest();
        const modules = await runtime.getRuntimeModules();
        const benchmarks = await runtime.getRuntimeBenchmarks();
        const validation = await runtime.getRuntimeReleaseValidation();
        output({ ok: true, manifest, modules, benchmarks, validation });
        return;
      }
      case "llm": {
        const models = await runtime.listModels();
        const artifact = await runtime.resolveArtifactBridge({
          repo_id: "bert-base-uncased",
          filename: "model.safetensors",
          revision: "main",
          local_files_only: true,
        });
        const tokenized = await runtime.tokenize({ input: "alpha beta gamma" });
        const counted = await runtime.countTokens({ input: "alpha beta gamma" });
        const deploymentRegions = await runtime.listDeploymentRegions();
        const deployment = await runtime.getDeployment();
        const deploymentCost =
          deployment && deployment.deployment_id
            ? await runtime.getDeploymentCost(deployment.deployment_id)
            : null;
        const chat = await runtime.chatCompletions({
          messages: [{ role: "user", content: "summarize alpha beta" }],
        });
        const chatChunks = [];
        for await (const chunk of runtime.streamChatCompletions({
          messages: [{ role: "user", content: "summarize alpha beta" }],
        })) {
          chatChunks.push(chunk);
        }
        const responses = await runtime.responses({ input: "alpha beta" });
        const responseEvents = [];
        for await (const event of runtime.streamResponses({ input: "alpha beta" })) {
          responseEvents.push(event);
        }
        const embeddings = await runtime.embeddings({
          input: ["alpha beta", "gamma"],
          dimensions: 8,
        });
        const similarity = await runtime.embeddingSimilarity({
          left: [1.0, 0.0],
          right: [0.5, 0.5],
        });
        const rerank = await runtime.rerank({
          query_embedding: [1.0, 0.0],
          documents: [
            { id: "doc_a", embedding: [1.0, 0.0], text: "alpha" },
            { id: "doc_b", embedding: [0.0, 1.0], text: "beta" },
          ],
          top_n: 2,
        });
        output({
          ok: true,
          models,
          artifact,
          tokenized,
          counted,
          deploymentRegions,
          deployment,
          deploymentCost,
          chat,
          chatChunks,
          responses,
          responseEvents,
          embeddings,
          similarity,
          rerank,
        });
        return;
      }
      case "account": {
        const me = await runtime.me();
        const usage = await runtime.usage();
        const limits = await runtime.limits();
        const distributions = await runtime.distributions();
        const templates = await runtime.templates();
        const label = `ts-runtime-account-${Date.now()}-${process.pid}`;
        let created = null;
        let requestedDeviceLimit = 2;
        try {
          const listedBefore = await runtime.listApiKeys();
          try {
            created = await runtime.createApiKey({
              label,
              expires_at: "2028-05-19T00:00:00Z",
              device_limit: requestedDeviceLimit,
            });
          } catch (error) {
            if (error?.errorCode !== "invalid_device_limit") {
              throw error;
            }
            requestedDeviceLimit = 0;
            created = await runtime.createApiKey({
              label,
              expires_at: "2028-05-19T00:00:00Z",
            });
          }
          const listedAfter = await runtime.listApiKeys();
          const revoke = await runtime.revokeApiKey(created.id);
          const listedFinal = await runtime.listApiKeys();
          output({
            ok: true,
            me,
            usage,
            limits,
            distributions,
            templates,
            listedBefore,
            created,
            requestedDeviceLimit,
            listedAfter,
            revoke,
            listedFinal,
          });
          return;
        } catch (error) {
          if (created && typeof created.id === "string") {
            try {
              await runtime.revokeApiKey(created.id);
            } catch {}
          }
          throw error;
        }
      }
      case "datasets": {
        if (!process.env.DE_REFRESHABLE_DATASET_URL) {
          throw new Error("DE_REFRESHABLE_DATASET_URL is required for dataset helper checks.");
        }
        const connectors = await runtime.listConnectors({ page: 1, limit: 50 });
        const previewTestedConnector = await runtime.testConnector({
          type: "rest",
          url: process.env.DE_REFRESHABLE_DATASET_URL,
          data_path: "items",
        });
        const previewBrowsedConnector = await runtime.browseConnector({
          type: "rest",
          url: process.env.DE_REFRESHABLE_DATASET_URL,
          data_path: "items",
        });
        const savedConnector = await runtime.createConnector({
          name: `ts-runtime-connector-${Date.now()}-${process.pid}`,
          connectorType: "rest",
          description: "Live TypeScript Runtime(mode='api') saved connector check.",
          config: {
            url: process.env.DE_REFRESHABLE_DATASET_URL,
            data_path: "items",
          },
        });
        const connectorId = savedConnector.id;
        if (!connectorId) {
          throw new Error(`saved connector response missing id: ${JSON.stringify(savedConnector)}`);
        }
        try {
          const created = await runtime.connect(null, {
            connector: {
              type: "rest",
              url: process.env.DE_REFRESHABLE_DATASET_URL,
              data_path: "items",
            },
            datasetName: `ts-runtime-refreshable-${Date.now()}-${process.pid}`,
            description: "Live TypeScript Runtime(mode='api') refreshable dataset check.",
            persist: true,
          });
          const datasetId = created.dataset_id;
          const datasetName = created.dataset_name ?? created.name;
          if (!datasetId || !datasetName) {
            throw new Error(`dataset connect response missing identifiers: ${JSON.stringify(created)}`);
          }

          const listedConnectors = await runtime.listConnectors({ page: 1, limit: 25 });
          const connectorDetail = await runtime.getConnector(connectorId);
          const updatedConnector = await runtime.updateConnector(connectorId, {
            description: "Live TypeScript Runtime connector updated description.",
          });
          const testedConnector = await runtime.testConnector(connectorId);
          const browsedConnector = await runtime.browseConnector(connectorId);
          try {
            const datasets = await runtime.listDatasets({
              search: datasetName,
              compact: true,
              page: 1,
              limit: 25,
            });
            const refreshed = await runtime.refreshDataset(datasetId);
            const summary = await runtime.getDatasetSummary(datasetId);
            const detail = await runtime.getDataset(datasetId);
            output({
              ok: true,
              connectors,
              previewTestedConnector,
              previewBrowsedConnector,
              savedConnector,
              listedConnectors,
              connectorDetail,
              updatedConnector,
              testedConnector,
              browsedConnector,
              created,
              datasets,
              refreshed,
              summary,
              detail,
            });
            return;
          } finally {
            await runtime.deleteDataset(datasetId);
          }
        } finally {
          await runtime.deleteConnector(connectorId);
        }
      }
      case "repositories": {
        if (!process.env.DE_LOCAL_REPOSITORY_PATH) {
          throw new Error("DE_LOCAL_REPOSITORY_PATH is required for repository helper checks.");
        }
        const capabilities = await runtime.getRepositoryIntelligenceCapabilities();
        const savedConnector = await runtime.createConnector({
          name: `ts-runtime-repository-${Date.now()}-${process.pid}`,
          connectorType: "local_repo",
          description: "Live TypeScript Runtime(mode='api') repository intelligence check.",
          config: {
            path: process.env.DE_LOCAL_REPOSITORY_PATH,
          },
        });
        const repositoryId = savedConnector.id;
        if (!repositoryId) {
          throw new Error(`saved repository connector response missing id: ${JSON.stringify(savedConnector)}`);
        }
        try {
          const snapshot = await runtime.createRepositorySnapshot(repositoryId, {
            include_patterns: ["src/**", "tests/**", "README.md"],
            exclude_patterns: ["**/__pycache__/**"],
            max_files: 128,
            max_file_size_bytes: 100000,
          });
          const fetchedSnapshot = await runtime.getRepositorySnapshot(repositoryId, snapshot.snapshot_id);
          const repeatedSnapshot = await runtime.createRepositorySnapshot(repositoryId, {
            include_patterns: ["src/**", "tests/**", "README.md"],
            exclude_patterns: ["**/__pycache__/**"],
            max_files: 128,
            max_file_size_bytes: 100000,
          });
          const triage = await runtime.triageRepository(repositoryId, {
            snapshot_id: snapshot.snapshot_id,
            signals: {
              issue_text: "Production regression: normalize_status returns closed for OPEN inputs after the latest deploy.",
              diagnostics: [
                {
                  path: "src/service.py",
                  line: 4,
                  severity: "error",
                  message: "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                },
              ],
              failing_tests: ["tests/test_service.py::test_normalize_status_open"],
              changed_files: ["src/service.py"],
              workspace_context: ["incident/normalize-status-regression", "jira/REPO-1842"],
            },
          });
          const graph = await runtime.queryRepositoryGraph(repositoryId, {
            snapshot_id: snapshot.snapshot_id,
            workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
            file_path: "src/service.py",
            symbol_name: "normalize_status",
            direction: "both",
            max_depth: 2,
            max_nodes: 64,
          });
          const planAttempt = await captureApiError(() =>
            runtime.createRepositoryDecisionPlan(repositoryId, {
              snapshot_id: snapshot.snapshot_id,
              workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
            }),
          );
          let simulation = null;
          let applyAttempt = null;
          if (planAttempt.ok) {
            simulation = await runtime.simulateRepository(repositoryId, {
              snapshot_id: snapshot.snapshot_id,
              decision_plan_id: planAttempt.value.decision_plan_id,
              runs: 1000,
              seed: 42,
            });
            const simulationId = simulation?.validated_inputs?.simulation_id;
            if (!simulationId) {
              throw new Error(`repository simulation missing simulation_id: ${JSON.stringify(simulation)}`);
            }
            applyAttempt = await captureApiError(() =>
              runtime.applyRepository(repositoryId, {
                snapshot_id: snapshot.snapshot_id,
                decision_plan_id: planAttempt.value.decision_plan_id,
                simulation_id: simulationId,
                mode: "local_branch",
                write_permission: true,
                branch_name: "algenta/live-repository-fix",
              }),
            );
          }
          output({
            ok: true,
            capabilities,
            savedConnector,
            snapshot,
            fetchedSnapshot,
            repeatedSnapshot,
            triage,
            graph,
            planAttempt,
            simulation,
            applyAttempt,
          });
          return;
        } finally {
          await runtime.deleteConnector(repositoryId);
        }
      }
      case "control_plane": {
        const team = await runtime.listTeamMembers({ page: 1, limit: 50 });
        const jobs = await runtime.listJobs({ page: 1, limit: 5, status: "queued" });
        const missingJob = await captureJobError(() => runtime.getJob("00000000-0000-0000-0000-000000000001"));
        const missingJobResult = await captureJobError(() => runtime.getJobResult("00000000-0000-0000-0000-000000000001"));
        const cancelledMissingJob = await captureJobError(() => runtime.cancelJob("00000000-0000-0000-0000-000000000001"));
        const polledMissingJob = await captureJobError(() => runtime.pollJob("00000000-0000-0000-0000-000000000001", { timeoutMs: 10, pollIntervalMs: 1 }));
        const billing = await runtime.getBillingInfo();
        const credits = await runtime.refreshCredits({
          device_id: `ts-runtime-credit-live-${Date.now()}-${process.pid}`,
          billing_period: new Date().toISOString().slice(0, 7),
          credits_used: 0,
        });
        const metering = await runtime.ingestMeteringEvents({
          device_id: `ts-runtime-live-${Date.now()}-${process.pid}`,
          events: [
            {
              event_type: "runtime_call",
              module: "integration",
              function: "typescript_runtime_live",
              engine_used: "typescript",
              latency_ms: 16.0,
              success: true,
            },
          ],
        });
        const webhook = process.env.DE_TEST_WEBHOOK_URL
          ? await runtime.testWebhookDelivery(process.env.DE_TEST_WEBHOOK_URL)
          : null;
        const devices = await runtime.listDevices({ page: 1, limit: 25 });
        const logs = await runtime.getAuditLogs({ page: 1, limit: 20 });
        const policy = await runtime.getExecutionPolicy();
        const snapshots = await runtime.listExecutionPolicySnapshots();
        const updated = await runtime.updateExecutionPolicy({
          min_confidence: policy.min_confidence,
          risk_floor: policy.risk_floor,
          require_calibration: policy.require_calibration,
          allow_reexecution: policy.allow_reexecution,
        });
        output({
          ok: true,
          team,
          jobs,
          missingJob,
          missingJobResult,
          cancelledMissingJob,
          polledMissingJob,
          billing,
          credits,
          metering,
          webhook,
          devices,
          logs,
          policy,
          snapshots,
          updated,
        });
        return;
      }
      case "triggers": {
        let created = null;
        try {
          created = await runtime.registerTrigger({
            name: `ts-runtime-trigger-${Date.now()}-${process.pid}`,
            condition: {
              source_id: `missing_source_ts_runtime_${Date.now()}_${process.pid}`,
              metric_hint: "revenue",
              threshold: 1000,
              direction: "above",
              aggregation: "sum",
            },
            simulation_template: {
              mode: "auto",
              scenario: {
                variables: { revenue: { low: 1000, high: 2000 } },
                objective: "maximize_net_value",
              },
              runs: 50,
            },
            description: "Live TypeScript runtime trigger lifecycle check.",
            auto_execute: false,
          });
          const listed = await runtime.listTriggers({ status: "all", page: 1, limit: 25 });
          const fired = await runtime.fireTrigger(created.trigger_id, { force: false });
          const paused = await runtime.pauseTrigger(created.trigger_id, { paused: true });
          const resumed = await runtime.pauseTrigger(created.trigger_id, { paused: false });
          const deleted = await runtime.deleteTrigger(created.trigger_id);
          output({ ok: true, created, listed, fired, paused, resumed, deleted });
          return;
        } catch (error) {
          if (created?.trigger_id) {
            try {
              await runtime.deleteTrigger(created.trigger_id);
            } catch {}
          }
          throw error;
        }
      }
      case "deployment": {
        const current = await runtime.getDeployment();
        if (current) {
          output({
            ok: false,
            error: {
              name: "EnvironmentBlocked",
              message: "deployment mutation requires an org without an existing deployment",
              statusCode: 409,
              errorCode: "deployment_exists",
              responseBody: { error: { code: "deployment_exists" } },
            },
          });
          return;
        }
        const created = await runtime.createDeployment({
          provider: "algenta_shared",
          region: "algenta-shared",
          config: { instance_size: "small" },
          billing_markup_pct: 20,
        });
        const cost = await runtime.getDeploymentCost(created.deployment_id);
        const deleted = await runtime.deleteDeployment(created.deployment_id);
        output({ ok: true, created, cost, deleted });
        return;
      }
      case "decision": {
        const recommendation = await runtime.recommend(
          [
            {
              name: "expand",
              request: {
                mode: "expert",
                runs: 250,
                simulation: {
                  variables: [
                    { name: "outcome", distribution: "fixed", params: { value: 140000 } },
                  ],
                  objective_function: "outcome",
                },
              },
            },
            {
              name: "hold",
              request: {
                mode: "expert",
                runs: 250,
                simulation: {
                  variables: [
                    { name: "outcome", distribution: "fixed", params: { value: 90000 } },
                  ],
                  objective_function: "outcome",
                },
              },
            },
          ],
          { runs: 250, seed: 42 },
        );
        const score = await runtime.score(
          {
            mode: "expert",
            runs: 250,
            simulation: {
              variables: [
                { name: "outcome", distribution: "normal", params: { mean: 100, std: 10 } },
              ],
              objective_function: "outcome",
            },
          },
          { expected_value: 0.7, downside_risk: 0.3 },
        );
        const batch = await runtime.batch([
          {
            mode: "expert",
            runs: 100,
            simulation: {
              variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
              objective_function: "outcome",
            },
          },
          {
            mode: "expert",
            runs: 100,
            simulation: {
              variables: [{ name: "outcome", distribution: "fixed", params: { value: 120 } }],
              objective_function: "outcome",
            },
          },
        ]);
        const compared = await runtime.compare([
          {
            name: "base",
            request: {
              mode: "expert",
              runs: 150,
              simulation: {
                variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
                objective_function: "outcome",
              },
            },
          },
          {
            name: "stretch",
            request: {
              mode: "expert",
              runs: 150,
              simulation: {
                variables: [{ name: "outcome", distribution: "fixed", params: { value: 120 } }],
                objective_function: "outcome",
              },
            },
          },
        ]);
        output({ ok: true, recommendation, score, batch, compared });
        return;
      }
      case "product": {
        const decision = await runtime.productDecision({
          inputs: [
            {
              name: "revenue",
              value: 120000,
              low: 100000,
              high: 150000,
              unit: "USD",
            },
            {
              name: "cost",
              value: 70000,
              low: 60000,
              high: 90000,
              unit: "USD",
            },
          ],
          risk_tolerance: "medium",
          scenarios: 1000,
        });
        const agentRun = await runtime.productAgentRun({
          task: `Summarize benchmark blockers ${Date.now()}`,
          tools: ["search"],
          max_steps: 3,
        });
        const optimize = await runtime.productOptimize({
          objective: "maximize profit",
          variables: [
            { name: "price", min: 50, max: 150 },
            { name: "discount", min: 0.0, max: 0.2 },
          ],
          iterations: 100,
        });
        const retrieve = await runtime.productRetrieve({
          query: "launch checklist",
          documents: [
            { id: "doc_1", content: "Launch checklist for product release." },
            { id: "doc_2", content: "Pricing review for launch approval." },
          ],
          top_k: 2,
        });
        const forecast = await runtime.productForecast({
          metric: "monthly_revenue",
          history: [100, 120, 130, 140],
          horizon: 3,
        });
        output({ ok: true, decision, agentRun, optimize, retrieve, forecast });
        return;
      }
      case "plan_agent": {
        const plan = await runtime.planDecision({
          mode: "expert",
          runs: 250,
          simulation: {
            variables: [
              {
                name: "outcome",
                distribution: "normal",
                params: { mean: 100, std: 10 },
              },
            ],
            objective_function: "outcome",
          },
        });
        const created = await runtime.createAgentRun({
          task: `Search benchmark notes ${Date.now()}`,
          tools: ["search"],
          approval_mode: "manual",
        });
        const fetched = await runtime.getAgentRun(created.run_id);
        const events = await runtime.getAgentRunEvents(created.run_id, { limit: 20 });
        const approved = await runtime.approveAgentRun(created.run_id);
        const streamCreated = await runtime.createAgentRun({
          task: `Search benchmark notes stream ${Date.now()}`,
          tools: ["search"],
          approval_mode: "auto",
        });
        const streamedEvents = [];
        for await (const event of runtime.streamAgentRunEvents(streamCreated.run_id, { limit: 20 })) {
          streamedEvents.push(event);
        }
        output({ ok: true, plan, created, fetched, events, approved, streamCreated, streamedEvents });
        return;
      }
      default:
        output({ ok: false, error: { message: `unknown check kind: ${kind}` } });
    }
  } catch (error) {
    output({
      ok: false,
      error: {
        name: error?.name ?? "Error",
        message: error?.message ?? String(error),
        statusCode: error?.statusCode ?? null,
        errorCode: error?.errorCode ?? null,
        responseBody: error?.responseBody ?? null,
      },
    });
  }
}

await main();
""".replace("%DIST_ENTRY%", json.dumps(dist_entry.resolve().as_uri()))
    proc = subprocess.run(
        ["node", "--input-type=module", "--eval", script, kind],
        cwd=str(ROOT),
        env={
            **os.environ,
            "DE_BASE_URL": BASE_URL,
            "DE_API_KEY": API_KEY,
            "DE_TEST_WEBHOOK_URL": webhook_url or "",
            "DE_REFRESHABLE_DATASET_URL": dataset_source_url or "",
            "DE_LOCAL_REPOSITORY_PATH": repository_path or "",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "TypeScript runtime api helper probe failed.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse TypeScript runtime helper output: {proc.stdout}") from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected dict payload, received {type(payload)!r}")
    if payload.get("ok") is True:
        return payload
    error = payload.get("error", {})
    raise RuntimeError(json.dumps(error, sort_keys=True))


def _capacity_reason_from_runtime_probe_error(exc: Exception) -> str | None:
    message = str(exc)
    payload: dict[str, Any] | None = None
    status: int | None = None
    try:
        parsed = json.loads(message)
        if isinstance(parsed, dict):
            payload = parsed.get("responseBody")
            raw_status = parsed.get("statusCode")
            if isinstance(raw_status, int):
                status = raw_status
            message = str(parsed.get("message") or message)
    except json.JSONDecodeError:
        payload = None
    return classify_simulation_capacity_blocker(
        status=status,
        payload=payload,
        text=message,
    )


def raise_if_artifact_bridge_blocked(exc: Exception) -> None:
    try:
        parsed = json.loads(str(exc))
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return
    payload = parsed.get("responseBody")
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    code = detail.get("code") if isinstance(detail, dict) else None
    if code == "artifact_bridge_backend_unavailable":
        raise SkippedCheckError(
            "artifact bridge requires the optional huggingface_hub backend in this checkout"
        ) from exc


def raise_if_credit_refresh_blocked(exc: Exception) -> None:
    try:
        parsed = json.loads(str(exc))
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return
    status = parsed.get("statusCode")
    payload = parsed.get("responseBody")
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    code = None
    if isinstance(detail, dict):
        raw_code = detail.get("error", detail.get("code"))
        if isinstance(raw_code, str):
            code = raw_code
    text = str(parsed.get("message") or exc).lower()
    if status == 429 and code in {"quota_exhausted", "quota_exceeded"}:
        raise SkippedCheckError("credit refresh quota exhausted for this live environment") from exc
    if status == 429 and ("quota_exhausted" in text or "quota_exceeded" in text):
        raise SkippedCheckError("credit refresh quota exhausted for this live environment") from exc


def raise_if_deployment_mutation_blocked(exc: Exception) -> None:
    try:
        parsed = json.loads(str(exc))
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return
    status = parsed.get("statusCode")
    code = parsed.get("errorCode")
    if status == 403:
        raise SkippedCheckError("deployment mutation requires owner role") from exc
    if status == 409 or code == "deployment_exists":
        raise SkippedCheckError(
            "deployment mutation requires an org without an existing deployment"
        ) from exc


def _assert_repository_error_payload(
    payload: dict[str, Any],
    *,
    status_code: int,
    error_code: str,
) -> None:
    assert payload["statusCode"] == status_code, payload
    assert payload["errorCode"] == error_code, payload
    response_body = payload.get("responseBody")
    detail = (
        response_body.get("detail", response_body.get("error"))
        if isinstance(response_body, dict)
        else None
    )
    error = detail.get("error", detail) if isinstance(detail, dict) else None
    assert isinstance(error, dict), response_body
    assert error.get("code") == error_code, response_body


def _missing_live_api_key_reason(exc: BaseException) -> str | None:
    if API_KEY_CONFIGURED:
        return None
    text = str(exc)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        status = parsed.get("statusCode")
        if status == 401 or parsed.get("errorCode") == "invalid_api_key":
            return (
                "DE_API_KEY is not set; skipping authenticated TypeScript Runtime(mode='api') "
                "checks that require a real live key."
            )
    if any(
        token in text
        for token in (
            "invalid_api_key",
            "invalid, expired, or has been revoked",
            "hosted license is required before offline execution",
            "Control plane registration failed",
        )
    ):
        return (
            "DE_API_KEY is not set; skipping authenticated TypeScript Runtime(mode='api') "
            "checks that require a real live key."
        )
    return None


def _node_mojo_probe(daemon_tcp: str) -> dict[str, Any]:
    dist_entry = _resolve_ts_dist_entry()
    if dist_entry is None:
        candidates = ", ".join(str(path) for path in TS_DIST_ENTRY_CANDIDATES)
        raise RuntimeError(f"TypeScript SDK dist entry missing. Checked: {candidates}")
    script = f"""
import {{ MojoRuntime, libraries }} from {json.dumps(dist_entry.resolve().as_uri())};

const runtime = new MojoRuntime({{
  mode: "local",
  tcpAddress: process.env.ALGENTA_DAEMON_TCP,
  timeout: 10_000,
}});

try {{
  const health = await runtime.health();
  const modules = await runtime.listModules();
  const catalog = await libraries({{
    mode: "local",
    tcpAddress: process.env.ALGENTA_DAEMON_TCP,
    timeout: 10_000,
  }});
  const rolloutCases = {json.dumps(LLM_ROLLOUT_CASES_JSON)};
  const rolloutFunctionsByModule = {json.dumps(LLM_ROLLOUT_FUNCTIONS_BY_MODULE)};
  const catalogNames = catalog.names();
  const rolloutMissingModules = rolloutCases
    .map(item => item.module)
    .filter(moduleName => !catalogNames.includes(moduleName));
  const rolloutFunctionMismatches = [];
  for (const [moduleName, expectedFunctions] of Object.entries(rolloutFunctionsByModule)) {{
    const actualFunctions = catalog.listFunctions(moduleName);
    const missingFunctions = expectedFunctions.filter(
      functionName => !actualFunctions.includes(functionName),
    );
    const unexpectedFunctions = actualFunctions.filter(
      functionName => !expectedFunctions.includes(functionName),
    );
    if (missingFunctions.length > 0 || unexpectedFunctions.length > 0) {{
      rolloutFunctionMismatches.push({{
        module: moduleName,
        missingFunctions,
        unexpectedFunctions,
      }});
    }}
  }}
  const rolloutResults = [];
  const rolloutDirectResults = [];
  for (const item of rolloutCases) {{
    const moduleProxy = catalog.module(item.module);
    const result = await moduleProxy[item.function](item.args);
    rolloutResults.push({{
      module: item.module,
      function: item.function,
      result,
    }});
    const directResult = await runtime.execute(item.module, item.function, item.args);
    rolloutDirectResults.push({{
      module: item.module,
      function: item.function,
      result: directResult,
    }});
  }}
  const direct = await runtime.execute(
    {json.dumps(MOJO_LIBRARY_MODULE)},
    {json.dumps(MOJO_LIBRARY_FUNCTION)},
    {json.dumps(MOJO_LIBRARY_ARGS)},
  );
  const catalogResult = await catalog.ab_testing.sample_size_proportion(
    {json.dumps(MOJO_LIBRARY_ARGS)},
  );
  let hostedConfigError = null;
  try {{
    new MojoRuntime({{ baseUrl: process.env.DE_BASE_URL }});
  }} catch (error) {{
    hostedConfigError = {{
      code: error && typeof error === "object" && "code" in error ? String(error.code) : null,
      message: error instanceof Error ? error.message : String(error),
    }};
  }}

  process.stdout.write(JSON.stringify({{
    health,
    moduleCount: modules.length,
    firstModule: modules[0] ?? null,
    abTestingFunctions: await runtime.listFunctions("ab_testing"),
    rolloutMissingModules,
    rolloutFunctionMismatches,
    rolloutResults,
    rolloutDirectResults,
    direct,
    catalogResult,
    hostedConfigError,
  }}));
}} catch (error) {{
  const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
  const details = error && typeof error === "object" && "details" in error
    ? JSON.stringify(error.details)
    : "";
  const message = error instanceof Error ? error.message : String(error);
  const suffix = details ? ` :: ${{details}}` : "";
  process.stderr.write(`${{code ? `[${{code}}] ` : ""}}${{message}}${{suffix}}`);
  process.exit(1);
}}
"""
    attempts = 3
    last_error: RuntimeError | None = None
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=str(ROOT),
            env={
                **os.environ,
                "ALGENTA_DAEMON_TCP": daemon_tcp,
                "DE_BASE_URL": BASE_URL,
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:  # noqa: PERF203
                raise RuntimeError(
                    f"Failed to parse TypeScript runtime Mojo output: {proc.stdout}"
                ) from exc
            if not isinstance(payload, dict):
                raise AssertionError(f"Expected dict payload, received {type(payload)!r}")
            return payload
        last_error = RuntimeError(
            "TypeScript runtime Mojo probe failed.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
        stderr_text = proc.stderr.lower()
        if (
            "failed parsing http/2" not in stderr_text
            and "connect econnrefused" not in stderr_text
            and "connection dropped" not in stderr_text
        ) or attempt == attempts:
            raise last_error
        time.sleep(0.5 * attempt)
    assert last_error is not None
    raise last_error


def _node_api_key_probe() -> dict[str, Any]:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live TypeScript API key integration.")
    dist_entry = _resolve_ts_dist_entry()
    if dist_entry is None:
        candidates = ", ".join(str(path) for path in TS_DIST_ENTRY_CANDIDATES)
        raise RuntimeError(f"TypeScript SDK dist entry missing. Checked: {candidates}")
    script = """
import { AlgentaClient } from %DIST_ENTRY%;

const client = new AlgentaClient({
  apiKey: process.env.DE_API_KEY,
  baseUrl: process.env.DE_BASE_URL,
  maxRetries: 0,
  timeout: 20_000,
});

const label = `ts-live-${Date.now()}-${process.pid}`;
const anchorLabel = `${label}-anchor`;
const deviceLimit = 2;
let anchor = null;
let created = null;

function deviceHeaders(deviceId, overrides = {}) {
  const hostnameHash =
    typeof overrides.hostnameHash === "string" && overrides.hostnameHash.length > 0
      ? overrides.hostnameHash
      : "deadbeef".repeat(8);
  return {
    "X-Algenta-Device-Id": deviceId,
    "X-Algenta-Platform": "linux",
    "X-Algenta-Platform-Version": "6.8",
    "X-Algenta-Hostname-Hash": hostnameHash,
    "X-Algenta-SDK-Version": "algenta-ts-live/1.0.0",
  };
}

async function callHostedMe(rawKey, deviceId, overrides = {}) {
  const boundClient = new AlgentaClient({
    apiKey: rawKey,
    baseUrl: process.env.DE_BASE_URL,
    maxRetries: 0,
    timeout: 20_000,
    defaultHeaders: deviceHeaders(deviceId, overrides),
  });
  try {
    const body = await boundClient.me();
    return { status: "ok", body };
  } catch (error) {
    const statusCode =
      error && typeof error === "object" && "statusCode" in error
        ? Number(error.statusCode)
        : null;
    const errorCode =
      error && typeof error === "object" && "errorCode" in error
        ? String(error.errorCode)
        : "";
    const responseBody =
      error && typeof error === "object" && "responseBody" in error
        ? error.responseBody
        : null;
    const message = error instanceof Error ? error.message : String(error);
    return {
      status: "error",
      statusCode,
      errorCode,
      responseBody,
      message,
    };
  }
}

async function callHostedMeWithEnvDeviceId(rawKey, deviceId) {
  const previousAlgentaDeviceId = process.env.ALGENTA_DEVICE_ID;
  const previousDeDeviceId = process.env.DE_DEVICE_ID;
  process.env.ALGENTA_DEVICE_ID = deviceId;
  process.env.DE_DEVICE_ID = deviceId;
  try {
    const boundClient = new AlgentaClient({
      apiKey: rawKey,
      baseUrl: process.env.DE_BASE_URL,
      maxRetries: 0,
      timeout: 20_000,
    });
    const body = await boundClient.me();
    return { status: "ok", body };
  } catch (error) {
    const statusCode =
      error && typeof error === "object" && "statusCode" in error
        ? Number(error.statusCode)
        : null;
    const errorCode =
      error && typeof error === "object" && "errorCode" in error
        ? String(error.errorCode)
        : "";
    const responseBody =
      error && typeof error === "object" && "responseBody" in error
        ? error.responseBody
        : null;
    const message = error instanceof Error ? error.message : String(error);
    return {
      status: "error",
      statusCode,
      errorCode,
      responseBody,
      message,
    };
  } finally {
    if (previousAlgentaDeviceId === undefined) {
      delete process.env.ALGENTA_DEVICE_ID;
    } else {
      process.env.ALGENTA_DEVICE_ID = previousAlgentaDeviceId;
    }
    if (previousDeDeviceId === undefined) {
      delete process.env.DE_DEVICE_ID;
    } else {
      process.env.DE_DEVICE_ID = previousDeDeviceId;
    }
  }
}

try {
  try {
    anchor = await client.createApiKey({
      label: anchorLabel,
      expires_at: "2028-05-19T00:00:00Z",
      device_limit: deviceLimit,
    });
    created = await client.createApiKey({
      label,
      expires_at: "2028-05-19T00:00:00Z",
      device_limit: deviceLimit,
    });
  } catch (error) {
    if (error?.errorCode === "invalid_device_limit") {
      process.stdout.write(JSON.stringify({
        skipped: true,
        reason: "Current plan does not allow per-key device limits; skipping hosted device-binding proof.",
      }));
      process.exit(0);
    }
    throw error;
  }
  const firstHosted = await callHostedMe(created.raw_key, "hosted-device-0001");
  const repeatedHosted = await callHostedMe(created.raw_key, "hosted-device-0001");
  const mismatchedHosted = await callHostedMe(created.raw_key, "hosted-device-0001", {
    hostnameHash: "cafebabe".repeat(8),
  });
  const envHosted = await callHostedMeWithEnvDeviceId(created.raw_key, "hosted-env-device-0002");
  const thirdHosted = await callHostedMe(created.raw_key, "hosted-device-0003");
  const listed = await client.listApiKeys();
  const listedMatch = listed.find((entry) => entry.id === created.id) ?? null;
  const listedLeaksRawKey =
    listedMatch !== null
      && Object.prototype.hasOwnProperty.call(listedMatch, "raw_key");
  await client.revokeApiKey(created.id);
  const revokedHosted = await callHostedMe(created.raw_key, "hosted-device-0001");
  const listedAfterRevoke = await client.listApiKeys();
  const presentAfterRevoke = listedAfterRevoke.some((entry) => entry.id === created.id);
  process.stdout.write(JSON.stringify({
    created,
    firstHosted,
    repeatedHosted,
    mismatchedHosted,
    envHosted,
    thirdHosted,
    revokedHosted,
    listedMatch,
    listedLeaksRawKey,
    presentAfterRevoke,
  }));
} catch (error) {
  if (created && typeof created.id === "string") {
    try {
      await client.revokeApiKey(created.id);
    } catch {
      // Best-effort cleanup only; keep the original failure.
    }
  }
  if (anchor && typeof anchor.id === "string") {
    try {
      await client.revokeApiKey(anchor.id);
    } catch {
      // Best-effort cleanup only; keep the original failure.
    }
  }
  const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
  const details = error && typeof error === "object" && "responseBody" in error
    ? JSON.stringify(error.responseBody)
    : "";
  const message = error instanceof Error ? error.message : String(error);
  const suffix = details ? ` :: ${details}` : "";
  process.stderr.write(`${code ? `[${code}] ` : ""}${message}${suffix}`);
  process.exit(1);
}
""".replace("%DIST_ENTRY%", json.dumps(dist_entry.resolve().as_uri()))
    proc = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=str(ROOT),
        env={
            **os.environ,
            "DE_BASE_URL": BASE_URL,
            "DE_API_KEY": API_KEY,
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "TypeScript runtime API key probe failed.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise RuntimeError(f"Failed to parse TypeScript API key output: {proc.stdout}") from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected dict payload, received {type(payload)!r}")
    return payload


def run_typescript_mojo_library_surface() -> None:
    try:
        with local_runtime_daemon() as daemon_env:
            payload = _node_mojo_probe(daemon_env["ALGENTA_DAEMON_TCP"])
    except Exception as exc:
        text = str(exc)
        if (
            isinstance(exc, PermissionError)
            or "local_runtime_not_included" in text
            or "Upgrade to PRO" in text
        ):
            raise SkippedCheckError(
                "Current plan does not include the local runtime; skipping TypeScript Mojo proof."
            ) from exc
        raise

    health = payload.get("health")
    direct = payload.get("direct")
    catalog_result = payload.get("catalogResult")
    hosted_config_error = payload.get("hostedConfigError")

    assert isinstance(health, dict), "Missing Mojo health payload"
    assert health["status"] == "ok"
    assert health["engine"] == "mojo"
    assert health["runtime_available"] is True
    assert health["module_count"] >= 400
    assert payload["moduleCount"] >= 400
    assert isinstance(payload["firstModule"], dict), "Missing first module descriptor"
    assert payload["firstModule"]["functions"], "First module descriptor is missing functions"
    assert "sample_size_proportion" in payload["abTestingFunctions"]
    assert payload["rolloutMissingModules"] == []
    assert payload["rolloutFunctionMismatches"] == []
    rollout_results = payload["rolloutResults"]
    rollout_direct_results = payload["rolloutDirectResults"]
    assert len(rollout_results) == len(LLM_ROLLOUT_CASES_JSON)
    assert len(rollout_direct_results) == len(LLM_ROLLOUT_CASES_JSON)
    rollout_results_by_key = {
        (item["module"], item["function"]): item["result"] for item in rollout_results
    }
    rollout_direct_results_by_key = {
        (item["module"], item["function"]): item["result"] for item in rollout_direct_results
    }
    assert set(LLM_ROLLOUT_MODULE_NAMES).issubset({item["module"] for item in rollout_results})
    for case in LLM_ROLLOUT_FUNCTION_CASES:
        assert_rollout_channel_result(
            case,
            rollout_results_by_key[(case.module, case.function)],
        )
        direct_result = rollout_direct_results_by_key[(case.module, case.function)]
        assert direct_result["module"] == case.module
        assert direct_result["function"] == case.function
        assert direct_result["engine_used"] == "mojo"
        assert_rollout_channel_result(case, direct_result["result"])

    assert isinstance(direct, dict), "Missing direct execution payload"
    assert direct["module"] == MOJO_LIBRARY_MODULE
    assert direct["function"] == MOJO_LIBRARY_FUNCTION
    assert direct["engine_used"] == "mojo"
    assert isinstance(direct["result"], int), "Expected integer direct Mojo result"
    assert direct["result"] > 0
    assert catalog_result == direct["result"]

    assert isinstance(hosted_config_error, dict), "Expected hosted config failure payload"
    assert hosted_config_error["code"] == "compute_runtime_unavailable"


def run_typescript_runtime_connector_matrix() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the API-backed TypeScript connector matrix."
        )
    with canonical_runtime_api_surface_server():
        with tempfile.TemporaryDirectory(prefix="algenta-ts-runtime-live-") as tmp_dir:
            sqlite_path = Path(tmp_dir) / "orders.db"
            write_sqlite_fixture(sqlite_path)
            with temporary_postgres_fixture(
                postgres_fixture_rows(), table="orders"
            ) as postgres_descriptor:
                payload = _node_probe(
                    sqlite_path,
                    postgres_canonical_connector(postgres_descriptor),
                )

    local = payload.get("local")
    local_bundle = payload.get("localBundle")
    rest = payload.get("rest")
    s3 = payload.get("s3")
    sqlite = payload.get("sqlite")
    postgres = payload.get("postgres")
    api_bundle = payload.get("apiBundle")
    assert isinstance(local, dict), "Missing local runtime result block"
    assert isinstance(local_bundle, dict), "Missing local bundle result block"
    assert isinstance(rest, dict), "Missing REST result block"
    assert isinstance(s3, dict), "Missing S3 result block"
    assert isinstance(sqlite, dict), "Missing SQLite result block"
    assert isinstance(postgres, dict), "Missing Postgres result block"
    assert isinstance(api_bundle, dict), "Missing API bundle result block"

    local_registration = local.get("registration")
    local_count = local.get("count")
    assert isinstance(local_registration, dict), "Missing local registration payload"
    assert isinstance(local_count, dict), "Missing local count payload"
    assert local_registration["status"] == "ready"
    assert local_registration["row_count"] > 0
    assert local_count["valid"] is True
    assert float(local_count["scalar"]) == float(local_registration["row_count"])
    assert "Algenta Source Import" in str(local["preview"])
    assert REAL_MARCH_ORDERS.stem in str(local["preview"])

    assert local_bundle["registrationCount"] == 3
    assert local_bundle["failureCount"] == 0
    assert "Algenta Source Bundle" in str(local_bundle["preview"])
    assert "orders_detail_bundle" in str(local_bundle["preview"])
    assert "orders_financial_bundle" in str(local_bundle["preview"])
    assert "top_inaccurate_items_bundle" in str(local_bundle["preview"])

    assert rest["valid"] is True
    assert rest["rowCount"] > 0
    assert float(rest["scalar"]) == float(rest["rowCount"])

    assert s3["valid"] is True
    assert s3["rowCount"] > 0
    assert float(s3["scalar"]) == float(s3["rowCount"])
    assert "Algenta Source Import" in str(s3["preview"])
    assert PUBLIC_S3_SOURCE_REF in str(s3["preview"])

    assert sqlite["valid"] is True
    assert sqlite["rowCount"] == 3
    assert float(sqlite["scalar"]) == 3.0

    assert postgres["valid"] is True
    assert postgres["rowCount"] == 3
    assert float(postgres["scalar"]) == 3.0

    assert api_bundle["registrationCount"] == 4
    assert api_bundle["failureCount"] == 0
    assert "Algenta Source Bundle" in str(api_bundle["preview"])
    assert "orders_sqlite_bundle" in str(api_bundle["preview"])
    assert "orders_postgres_bundle" in str(api_bundle["preview"])
    assert "noaa_hourly_bundle" in str(api_bundle["preview"])
    assert "weather_stations_bundle" in str(api_bundle["preview"])


def run_typescript_runtime_api_llm_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') TypeScript helper surface."
        )
    try:
        with canonical_runtime_api_surface_server():
            payload = _node_api_helper_probe("llm")
    except Exception as exc:  # noqa: BLE001
        raise_if_artifact_bridge_blocked(exc)
        raise
    tokenizer = next((item for item in payload["models"]["data"] if item["id"] == "text.tokenizer"), None)
    assert tokenizer is not None, payload["models"]["data"]
    for item in payload["models"]["data"]:
        assert item.get("provider_backend") is None or isinstance(item.get("provider_backend"), str), item
        for field_name in (
            "routing_targets",
            "resolved_routing_targets",
            "chat_routing_targets",
            "resolved_chat_routing_targets",
            "embedding_routing_targets",
            "resolved_embedding_routing_targets",
            "routing_fallback_on",
            "chat_routing_fallback_on",
            "embedding_routing_fallback_on",
            "required_provider_headers",
            "chat_required_provider_headers",
            "embedding_required_provider_headers",
            "provider_auth_env_vars",
            "chat_provider_auth_env_vars",
            "embedding_provider_auth_env_vars",
        ):
            value = item.get(field_name)
            assert isinstance(value, list), (item["id"], field_name, value)
            assert all(isinstance(entry, str) and entry for entry in value), (
                item["id"],
                field_name,
                value,
            )
        for field_name in (
            "routing_fallback_policy",
            "chat_routing_fallback_policy",
            "embedding_routing_fallback_policy",
        ):
            value = item.get(field_name)
            assert value is None or isinstance(value, str), (item["id"], field_name, value)
        for field_name in (
            "routing_max_attempts",
            "chat_routing_max_attempts",
            "embedding_routing_max_attempts",
        ):
            value = item.get(field_name)
            assert value is None or (isinstance(value, int) and value > 0), (item["id"], field_name, value)
        for field_name in ("timeout_seconds", "chat_timeout_seconds", "embedding_timeout_seconds"):
            value = item.get(field_name)
            assert value is None or (isinstance(value, int | float) and value > 0), (
                item["id"],
                field_name,
                value,
            )
        assert isinstance(item.get("provider_auth_configured"), bool), item
        assert isinstance(item.get("chat_provider_auth_configured"), bool), item
        assert isinstance(item.get("embedding_provider_auth_configured"), bool), item
        if item.get("provider_backend") != "router":
            assert item["resolved_routing_targets"] == [], item
            assert item["resolved_chat_routing_targets"] == [], item
            assert item["resolved_embedding_routing_targets"] == [], item
            assert item["routing_fallback_policy"] is None, item
            assert item["chat_routing_fallback_policy"] is None, item
            assert item["embedding_routing_fallback_policy"] is None, item
            assert item["routing_fallback_on"] == [], item
            assert item["chat_routing_fallback_on"] == [], item
            assert item["embedding_routing_fallback_on"] == [], item
            assert item["routing_max_attempts"] is None, item
            assert item["chat_routing_max_attempts"] is None, item
            assert item["embedding_routing_max_attempts"] is None, item
    assert tokenizer["provider_backend"] is None, tokenizer
    assert tokenizer["routing_targets"] == [], tokenizer
    assert tokenizer["resolved_routing_targets"] == [], tokenizer
    assert tokenizer["chat_routing_targets"] == [], tokenizer
    assert tokenizer["resolved_chat_routing_targets"] == [], tokenizer
    assert tokenizer["embedding_routing_targets"] == [], tokenizer
    assert tokenizer["resolved_embedding_routing_targets"] == [], tokenizer
    assert tokenizer["routing_fallback_policy"] is None, tokenizer
    assert tokenizer["chat_routing_fallback_policy"] is None, tokenizer
    assert tokenizer["embedding_routing_fallback_policy"] is None, tokenizer
    assert tokenizer["routing_fallback_on"] == [], tokenizer
    assert tokenizer["chat_routing_fallback_on"] == [], tokenizer
    assert tokenizer["embedding_routing_fallback_on"] == [], tokenizer
    assert tokenizer["routing_max_attempts"] is None, tokenizer
    assert tokenizer["chat_routing_max_attempts"] is None, tokenizer
    assert tokenizer["embedding_routing_max_attempts"] is None, tokenizer
    assert tokenizer["timeout_seconds"] is None, tokenizer
    assert tokenizer["chat_timeout_seconds"] is None, tokenizer
    assert tokenizer["embedding_timeout_seconds"] is None, tokenizer
    assert tokenizer["required_provider_headers"] == [], tokenizer
    assert tokenizer["chat_required_provider_headers"] == [], tokenizer
    assert tokenizer["embedding_required_provider_headers"] == [], tokenizer
    assert tokenizer["provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["chat_provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["embedding_provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["provider_auth_configured"] is False, tokenizer
    assert tokenizer["chat_provider_auth_configured"] is False, tokenizer
    assert tokenizer["embedding_provider_auth_configured"] is False, tokenizer
    model_ids = {item["id"] for item in payload["models"]["data"]}
    assert "text.tokenizer" in model_ids
    assert "text.hash_embedding_v1" in model_ids
    assert "embeddings.cosine_similarity" in model_ids
    assert payload["artifact"]["status"] in {"resolved", "not_cached"}
    assert payload["artifact"]["filename"] == "model.safetensors"
    if payload["artifact"]["resolved_path"] is not None:
        assert payload["artifact"]["resolved_path"]
    assert payload["tokenized"]["token_count"] == 3
    assert payload["counted"]["token_count"] == 3
    assert payload["deploymentRegions"]["providers"]
    managed_provider = next(
        (
            provider
            for provider in payload["deploymentRegions"]["providers"]
            if provider["id"] == "algenta_shared"
        ),
        None,
    )
    assert managed_provider is not None
    assert managed_provider["regions"]
    if payload["deployment"] is not None:
        assert payload["deployment"]["deployment_id"]
        assert payload["deploymentCost"] is not None
        assert (
            payload["deploymentCost"]["deployment_id"] == payload["deployment"]["deployment_id"]
        )
    assert payload["chat"]["object"] == "chat.completion"
    _assert_empty_provider_trace_payload(payload["chat"])
    assert len(payload["chatChunks"]) >= 2
    assert all(chunk["provider_backend"] is None for chunk in payload["chatChunks"]), payload[
        "chatChunks"
    ]
    assert all(chunk["provider_model_id"] is None for chunk in payload["chatChunks"]), payload[
        "chatChunks"
    ]
    assert all(chunk["provider_attempts"] == [] for chunk in payload["chatChunks"]), payload[
        "chatChunks"
    ]
    assert payload["responses"]["status"] == "completed"
    _assert_empty_provider_trace_payload(payload["responses"], output_items=True)
    assert len(payload["responseEvents"]) == 3
    assert payload["responseEvents"][0]["response"]["provider_backend"] is None, payload[
        "responseEvents"
    ]
    assert payload["responseEvents"][0]["response"]["provider_model_id"] is None, payload[
        "responseEvents"
    ]
    assert payload["responseEvents"][0]["response"]["provider_attempts"] == [], payload[
        "responseEvents"
    ]
    assert payload["responseEvents"][1]["item"]["provider_backend"] is None, payload[
        "responseEvents"
    ]
    assert payload["responseEvents"][1]["item"]["provider_model_id"] is None, payload[
        "responseEvents"
    ]
    assert payload["responseEvents"][1]["item"]["provider_attempts"] == [], payload[
        "responseEvents"
    ]
    assert payload["responseEvents"][2]["response"]["provider_backend"] is None, payload[
        "responseEvents"
    ]
    assert payload["responseEvents"][2]["response"]["provider_model_id"] is None, payload[
        "responseEvents"
    ]
    assert payload["responseEvents"][2]["response"]["provider_attempts"] == [], payload[
        "responseEvents"
    ]
    assert payload["embeddings"]["dimensions"] == 8
    _assert_empty_provider_trace_payload(payload["embeddings"])
    assert payload["similarity"]["dimension"] == 2
    assert payload["rerank"]["data"][0]["id"] == "doc_a"


def run_typescript_runtime_proof_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') TypeScript proof surface."
        )
    with canonical_runtime_api_surface_server():
        payload = _node_api_helper_probe("proof")

    manifest = payload["manifest"]
    modules = payload["modules"]
    benchmarks = payload["benchmarks"]
    validation = payload["validation"]

    assert manifest["runtime_version"]
    assert len(manifest["modules"]) >= 1
    manifest_provider_routing_overhead = next(
        (entry for entry in manifest["benchmarking"]["classes"] if entry["code"] == "B8"),
        None,
    )
    assert manifest_provider_routing_overhead is not None, manifest["benchmarking"]["classes"]
    assert manifest_provider_routing_overhead["description"] == "provider routing overhead"
    assert manifest_provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    manifest_checkpoint_replay_overhead = next(
        (entry for entry in manifest["benchmarking"]["classes"] if entry["code"] == "B6"),
        None,
    )
    assert manifest_checkpoint_replay_overhead is not None, manifest["benchmarking"]["classes"]
    assert manifest_checkpoint_replay_overhead["description"] == "checkpoint and replay overhead"
    assert manifest_checkpoint_replay_overhead["evidence_paths"] == []
    manifest_decision_workflow_completion = next(
        (entry for entry in manifest["benchmarking"]["classes"] if entry["code"] == "B10"),
        None,
    )
    assert manifest_decision_workflow_completion is not None, manifest["benchmarking"]["classes"]
    assert (
        manifest_decision_workflow_completion["description"]
        == "decision workflow completion latency"
    )
    assert manifest_decision_workflow_completion["evidence_paths"] == [
        "build/repository_intelligence_benchmark.json",
        "benchmarks/repository_intelligence_benchmark.py",
        "tests/test_repository_intelligence_benchmark.py",
    ]
    assert len(modules["modules"]) >= 1
    assert modules["summary"]["module_count"] >= 1
    assert len(benchmarks["module_benchmarks"]) >= 1
    provider_routing_overhead = next(
        (entry for entry in benchmarks["benchmarking"]["classes"] if entry["code"] == "B8"),
        None,
    )
    assert provider_routing_overhead is not None, benchmarks["benchmarking"]["classes"]
    assert provider_routing_overhead["description"] == "provider routing overhead"
    assert provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    checkpoint_replay_overhead = next(
        (entry for entry in benchmarks["quality_gate_benchmark_classes"] if entry["code"] == "B6"),
        None,
    )
    assert checkpoint_replay_overhead is not None, benchmarks["quality_gate_benchmark_classes"]
    assert checkpoint_replay_overhead["description"] == "checkpoint and replay overhead"
    assert checkpoint_replay_overhead["evidence_paths"] == []
    decision_workflow_completion = next(
        (entry for entry in benchmarks["quality_gate_benchmark_classes"] if entry["code"] == "B10"),
        None,
    )
    assert decision_workflow_completion is not None, benchmarks["quality_gate_benchmark_classes"]
    assert decision_workflow_completion["description"] == "decision workflow completion latency"
    assert decision_workflow_completion["evidence_paths"] == [
        "build/repository_intelligence_benchmark.json",
        "benchmarks/repository_intelligence_benchmark.py",
        "tests/test_repository_intelligence_benchmark.py",
    ]
    assert {entry["code"] for entry in benchmarks["quality_gate_benchmark_classes"]} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert [entry["name"] for entry in benchmarks["quality_gate_slo_budgets"]] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert benchmarks["evaluation_summary"]["replay_gate_enabled"] is True
    assert benchmarks["evaluation_summary"]["tool_call_quality_gate_enabled"] is True
    assert benchmarks["evaluation_summary"]["rag_quality_gate_enabled"] is True
    assert benchmarks["evaluation_summary"]["decision_quality_gate_enabled"] is True
    assert validation["valid_release"] is True


def run_typescript_runtime_account_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') account helpers."
        )
    with canonical_runtime_api_surface_server():
        payload = _node_api_helper_probe("account")
    me = payload["me"]
    usage = payload["usage"]
    limits = payload["limits"]
    distributions = payload["distributions"]
    templates = payload["templates"]
    created = payload["created"]
    requested_device_limit = payload["requestedDeviceLimit"]
    listed_after = payload["listedAfter"]
    listed_final = payload["listedFinal"]
    assert any(key in me for key in ("org_id", "organization", "email", "user", "org")), me
    assert usage["billing_period"]
    assert usage["quota_limit"] >= 0
    assert any(
        key in limits for key in ("plan", "simulations_per_month", "rate_limit_per_minute")
    ), limits
    assert distributions["page"] == 1
    assert distributions["limit"] >= 1
    assert distributions["total"] >= len(distributions["distributions"])
    assert distributions["pages"] >= 1
    assert distributions["distributions"]
    assert distributions["distributions"][0]["name"]
    assert templates["page"] == 1
    assert templates["limit"] >= 1
    assert templates["total"] >= len(templates["templates"])
    assert templates["pages"] >= 1
    assert templates["templates"]
    assert templates["templates"][0]["id"]
    assert created["label"].startswith("ts-runtime-account-")
    assert created["device_limit"] == requested_device_limit
    assert created["raw_key"].startswith(created["key_prefix"])
    listed_match = next((entry for entry in listed_after if entry["id"] == created["id"]), None)
    assert isinstance(listed_match, dict), "Created API key missing from Runtime.listApiKeys()"
    assert listed_match["device_limit"] == requested_device_limit
    assert listed_match["expires_at"] == "2028-05-19T00:00:00Z"
    assert listed_match["key_prefix"] == created["key_prefix"]
    assert not any(entry["id"] == created["id"] for entry in listed_final)


def run_typescript_runtime_dataset_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') dataset helpers."
        )
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        with canonical_runtime_api_surface_server():
            payload = _node_api_helper_probe("datasets", dataset_source_url=source_url)

    connectors = payload["connectors"]
    preview_tested_connector = payload["previewTestedConnector"]
    preview_browsed_connector = payload["previewBrowsedConnector"]
    saved_connector = payload["savedConnector"]
    listed_connectors = payload["listedConnectors"]
    connector_detail = payload["connectorDetail"]
    updated_connector = payload["updatedConnector"]
    tested_connector = payload["testedConnector"]
    browsed_connector = payload["browsedConnector"]
    created = payload["created"]
    datasets = payload["datasets"]
    refreshed = payload["refreshed"]
    summary = payload["summary"]
    detail = payload["detail"]
    dataset_id = created["dataset_id"]
    dataset_name = created.get("dataset_name") or created.get("name")

    assert connectors["page"] == 1
    assert connectors["limit"] == 50
    assert connectors["total"] >= len(connectors["connectors"])
    assert connectors["pages"] >= 1
    if connectors["connectors"]:
        assert connectors["connectors"][0]["id"]
        assert connectors["connectors"][0]["connector_type"]
    assert preview_tested_connector["success"] is True
    assert preview_tested_connector["status"] == "live"
    assert preview_browsed_connector["connector_type"] == "rest"
    assert preview_browsed_connector["total"] >= 1
    assert saved_connector["id"]
    assert saved_connector["name"]
    assert listed_connectors["page"] == 1
    assert listed_connectors["limit"] == 25
    assert listed_connectors["total"] >= len(listed_connectors["connectors"])
    assert any(item["id"] == saved_connector["id"] for item in listed_connectors["connectors"])
    assert connector_detail["id"] == saved_connector["id"]
    assert connector_detail["name"] == saved_connector["name"]
    assert updated_connector["id"] == saved_connector["id"]
    assert updated_connector["description"] == "Live TypeScript Runtime connector updated description."
    assert tested_connector["success"] is True
    assert tested_connector["status"] == "live"
    assert browsed_connector["connector_type"] == "rest"
    assert browsed_connector["total"] >= 1

    assert created["status"] == "ready"
    assert dataset_id
    assert dataset_name

    assert datasets["page"] == 1
    assert datasets["limit"] == 25
    assert datasets["total"] >= len(datasets["datasets"])
    matched_total = datasets.get("matched_total")
    assert matched_total is None or matched_total >= len(datasets["datasets"])
    assert any(item["dataset_id"] == dataset_id for item in datasets["datasets"])
    assert refreshed["status"] == "ready"
    assert refreshed["dataset_id"] == dataset_id

    assert summary["dataset_id"] == dataset_id
    assert summary["name"] == dataset_name
    assert summary["column_count"] >= 2

    assert detail["dataset"]["dataset_id"] == dataset_id
    assert detail["dataset"]["dataset_name"] == dataset_name
    assert isinstance(detail["schema"], dict)
    assert len(detail["schema"].get("columns", [])) >= 2


def run_typescript_runtime_repository_surface() -> None:
    reason = local_repository_live_support_reason(BASE_URL)
    if reason is not None:
        raise SkippedCheckError(reason)
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') repository helpers."
        )

    with live_repository_fixture("ts-runtime") as repository_fixture:
        with canonical_runtime_api_surface_server():
            try:
                payload = _node_api_helper_probe(
                    "repositories",
                    repository_path=str(repository_fixture.root_path),
                )
            except Exception as exc:  # noqa: BLE001
                reason = _capacity_reason_from_runtime_probe_error(exc)
                if reason:
                    raise SkippedCheckError(reason) from exc
                raise
            assert_repository_intelligence_capabilities_payload(payload["capabilities"])
            saved_connector = payload["savedConnector"]
            snapshot = payload["snapshot"]
            fetched_snapshot = payload["fetchedSnapshot"]
            repeated_snapshot = payload["repeatedSnapshot"]
            triage = payload["triage"]
            graph = payload["graph"]
            plan_attempt = payload["planAttempt"]
            simulation = payload["simulation"]
            apply_attempt = payload["applyAttempt"]

            assert saved_connector["id"]
            assert saved_connector["connector_type"] == "local_repo"
            assert snapshot["connector_type"] == "local_repo"
            assert snapshot["file_count"] >= 2
            assert fetched_snapshot["snapshot_id"] == snapshot["snapshot_id"]
            assert fetched_snapshot["content_hash"] == snapshot["content_hash"]
            assert repeated_snapshot["snapshot_id"] == snapshot["snapshot_id"]
            assert repeated_snapshot["status"] == "existing"
            assert triage["workspace_evidence_bundle_ref"]
            assert triage["reduction_ratio"] >= 1.0
            assert triage["evidence_items"]
            assert triage["suspect_files"][0] == repository_fixture.primary_file
            assert triage["workspace_evidence_bundle_artifact"]["artifact_kind"] == "WorkspaceEvidenceBundle"
            assert graph["snapshot_id"] == snapshot["snapshot_id"]
            assert repository_fixture.primary_file in graph["seed_file_paths"]
            assert repository_fixture.primary_file in graph["impacted_files"]
            assert graph["graph_nodes"]
            assert graph["top_change_risk_files"]

            if not plan_attempt["ok"]:
                _assert_repository_error_payload(
                    plan_attempt,
                    status_code=503,
                    error_code="repository_model_unavailable",
                )
                return

            decision_plan = plan_attempt["value"]
            repository_analysis = decision_plan["decision_plan"]["repository_analysis"]
            assert decision_plan["decision_plan_id"]
            assert repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"
            assert repository_analysis["planner_execution_mode"] == "deterministic_local"
            assert repository_analysis["planner_provider_backend"] is None
            assert repository_analysis["generated_patch_ref"]
            assert repository_analysis["patch_impact_report_ref"]
            assert repository_analysis["token_reduction_metrics"]["reduction_ratio"] >= 1.0

            assert simulation is not None
            simulation_id = simulation["validated_inputs"]["simulation_id"]
            apply_gate = simulation["score_breakdown"]["apply_gate"]
            assert simulation_id
            assert apply_gate["policy_snapshot_id"]

            assert apply_attempt is not None
            if apply_gate["passed"]:
                assert apply_attempt["ok"] is True, apply_attempt
                applied = apply_attempt["value"]
                assert applied["mode"] == "local_branch"
                assert applied["applied"] is True
                assert applied["patch"]
                assert applied["branch_name"] == "algenta/live-repository-fix"
                assert applied["commit_sha"]
                assert applied["local_checkout_path"]
                repository_fixture.assert_local_branch_applied(
                    branch_name="algenta/live-repository-fix",
                    checkout_path=applied["local_checkout_path"],
                )
                assert repository_fixture.primary_file in applied["validation_summary"]["patch_files"]
            else:
                assert apply_attempt["ok"] is False, apply_attempt
                _assert_repository_error_payload(
                    apply_attempt,
                    status_code=409,
                    error_code="repository_apply_gate_failed",
                )


def run_typescript_runtime_control_plane_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') control-plane helpers."
        )
    with webhook_receiver() as (callback_url, deliveries):
        with canonical_runtime_api_surface_server():
            try:
                payload = _node_api_helper_probe("control_plane", webhook_url=callback_url)
            except Exception as exc:  # noqa: BLE001
                raise_if_credit_refresh_blocked(exc)
                raise
        team = payload["team"]
        jobs = payload["jobs"]
        missing_job = payload["missingJob"]
        missing_job_result = payload["missingJobResult"]
        cancelled_missing_job = payload["cancelledMissingJob"]
        polled_missing_job = payload["polledMissingJob"]
        billing = payload["billing"]
        credits = payload["credits"]
        metering = payload["metering"]
        webhook = payload["webhook"]
        devices = payload["devices"]
        logs = payload["logs"]
        policy = payload["policy"]
        snapshots = payload["snapshots"]
        updated = payload["updated"]
        assert team["page"] == 1
        assert team["limit"] == 50
        assert team["total"] >= len(team["members"])
        assert team["pages"] >= 1
        assert team["members"]
        assert team["members"][0]["email"]
        assert team["members"][0]["role"]
        assert jobs["page"] == 1
        assert jobs["limit"] == 5
        assert jobs["total"] >= len(jobs["jobs"])
        assert jobs["pages"] >= 1
        for job in jobs["jobs"]:
            assert job["status"] == "queued"
            assert job["queue_name"]
        for missing in (missing_job, missing_job_result, cancelled_missing_job, polled_missing_job):
            assert missing["ok"] is False
            assert missing["statusCode"] == 404, missing
            assert missing["errorCode"] in {"job_not_found", "not_found"}, missing
            response_body = missing["responseBody"]
            assert isinstance(response_body, dict), missing
            assert response_body.get("error", {}).get("code") in {"job_not_found", "not_found"}, missing
        assert billing["plan"]
        assert credits["billing_period"] == time.strftime("%Y-%m", time.gmtime())
        assert credits["credits_granted"] >= 0
        assert credits["credits_issued_this_month"] >= credits["credits_granted"]
        assert credits["monthly_limit"] >= 0
        assert credits["monthly_remaining"] >= 0
        assert credits["refresh_after"] >= credits["server_time"]
        assert credits["expires_at"] >= credits["refresh_after"]
        assert metering["accepted"] == 1
        assert metering["billing_period"]
        assert webhook["success"] is True
        assert webhook["status_code"] == 200
        assert deliveries, "Expected one webhook delivery to local receiver"
        assert deliveries[0]["path"] == "/webhook", deliveries[0]
        assert devices["page"] == 1
        assert devices["limit"] == 25
        assert devices["total"] >= len(devices["devices"])
        assert devices["pages"] >= 1
        assert devices["device_count"] == len(devices["devices"])
        assert devices["plan"]
        assert logs["page"] == 1
        assert logs["limit"] == 20
        assert logs["total"] >= len(logs["entries"])
        assert logs["pages"] >= 1
        assert logs["entries"]
        assert logs["entries"][0]["action"]
        assert logs["entries"][0]["resource_type"]
        assert logs["entries"][0]["result"] in {"success", "failure"}
        assert 0 <= policy["min_confidence"] <= 1
        assert isinstance(policy["require_calibration"], bool)
        assert isinstance(policy["allow_reexecution"], bool)
        assert policy["updated_at"]
        assert snapshots["total_snapshots"] >= len(snapshots["data"])
        if snapshots["data"]:
            assert snapshots["data"][0]["snapshot_id"]
            assert snapshots["data"][0]["revision"] >= 1
        assert updated["min_confidence"] == policy["min_confidence"]
        assert updated["risk_floor"] == policy["risk_floor"]
        assert updated["require_calibration"] == policy["require_calibration"]
        assert updated["allow_reexecution"] == policy["allow_reexecution"]


def run_typescript_runtime_trigger_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') trigger helpers."
        )
    with canonical_runtime_api_surface_server():
        payload = _node_api_helper_probe("triggers")
    created = payload["created"]
    listed = payload["listed"]
    fired = payload["fired"]
    paused = payload["paused"]
    resumed = payload["resumed"]
    deleted = payload["deleted"]
    assert created["trigger_id"]
    assert created["status"] == "active"
    assert listed["page"] == 1
    assert listed["limit"] == 25
    assert listed["total"] >= len(listed["triggers"])
    assert any(item["trigger_id"] == created["trigger_id"] for item in listed["triggers"])
    assert fired["trigger_id"] == created["trigger_id"]
    assert fired["condition_met"] is False
    assert fired["fired"] is False
    assert paused["status"] == "paused"
    assert resumed["status"] == "active"
    assert deleted["trigger_id"] == created["trigger_id"]
    assert deleted["deleted"] is True


def run_typescript_runtime_deployment_lifecycle_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') deployment lifecycle."
        )
    try:
        with canonical_runtime_api_surface_server():
            payload = _node_api_helper_probe("deployment")
    except Exception as exc:  # noqa: BLE001
        raise_if_deployment_mutation_blocked(exc)
        raise
    created = payload["created"]
    cost = payload["cost"]
    deleted = payload["deleted"]
    assert created["deployment_id"]
    assert created["provider"] == "algenta_shared"
    assert created["region"] == "algenta-shared"
    assert created["status"] in {"requested", "provisioning", "active"}
    assert cost["deployment_id"] == created["deployment_id"]
    assert cost["provider"] == created["provider"]
    assert cost["billable_cost_usd_month"] >= cost["cost_usd_month"]
    assert deleted["deployment_id"] == created["deployment_id"]
    assert deleted["status"] in {"deprovisioning", "deleted"}


def run_typescript_runtime_api_decision_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') decision-runtime helpers."
        )
    with canonical_runtime_api_surface_server():
        try:
            payload = _node_api_helper_probe("decision")
        except Exception as exc:  # noqa: BLE001
            reason = _capacity_reason_from_runtime_probe_error(exc)
            if reason:
                raise SkippedCheckError(reason) from exc
            raise

    recommendation = payload["recommendation"]
    score = payload["score"]
    batch = payload["batch"]
    compared = payload["compared"]
    assert recommendation["recommended_action"]
    assert len(recommendation["action_results"]) == 2
    assert isinstance(score["score"], int | float)
    assert isinstance(score["score_breakdown"], dict)
    assert score["score_breakdown"]
    assert batch["total"] == 2
    assert len(batch["results"]) == 2
    assert compared["winner"] in {"base", "stretch"}
    assert len(compared["scenarios"]) == 2


def run_typescript_runtime_product_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') simplified product helpers."
        )
    with canonical_runtime_api_surface_server():
        try:
            payload = _node_api_helper_probe("product")
        except Exception as exc:  # noqa: BLE001
            reason = _capacity_reason_from_runtime_probe_error(exc)
            if reason:
                raise SkippedCheckError(reason) from exc
            raise

    assert payload["decision"]["action"]
    assert 0 <= payload["decision"]["confidence"] <= 1
    assert payload["agentRun"]["run_id"]
    assert payload["agentRun"]["status"] in {"completed", "requires_approval", "running"}
    assert payload["optimize"]["status"] == "completed"
    assert payload["optimize"]["optimal_values"]
    assert payload["retrieve"]["results"]
    assert payload["retrieve"]["results"][0]["content"]
    assert payload["forecast"]["forecast_mean"] >= 0
    assert payload["forecast"]["periods"]


def run_typescript_runtime_plan_and_agent_surface() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the Runtime(mode='api') plan and agent-run helpers."
        )
    with canonical_runtime_api_surface_server():
        try:
            payload = _node_api_helper_probe("plan_agent")
        except Exception as exc:  # noqa: BLE001
            reason = _capacity_reason_from_runtime_probe_error(exc)
            if reason:
                raise SkippedCheckError(reason) from exc
            raise

    assert payload["plan"]["recommended_action"]
    assert payload["created"]["status"] == "requires_approval"
    assert payload["fetched"]["run_id"] == payload["created"]["run_id"]
    assert payload["events"]["run_id"] == payload["created"]["run_id"]
    assert payload["events"]["total_events"] >= 1
    assert len(payload["streamedEvents"]) >= 2
    assert payload["streamCreated"]["status"] in {"running", "completed"}
    assert payload["streamedEvents"][-1]["type"] == "agent.run.completed"
    assert payload["approved"]["status"] == "completed"


def run_typescript_api_key_lifecycle() -> None:
    if not API_KEY:
        raise SkippedCheckError(
            "DE_API_KEY is not set; skipping the TypeScript API key lifecycle probe."
        )
    payload = _node_api_key_probe()
    if payload.get("skipped") is True:
        raise SkippedCheckError(
            str(
                payload.get("reason")
                or "TypeScript API key lifecycle is not available on the current plan."
            )
        )

    created = payload.get("created")
    first_hosted = payload.get("firstHosted")
    repeated_hosted = payload.get("repeatedHosted")
    mismatched_hosted = payload.get("mismatchedHosted")
    env_hosted = payload.get("envHosted")
    third_hosted = payload.get("thirdHosted")
    revoked_hosted = payload.get("revokedHosted")
    listed_match = payload.get("listedMatch")
    listed_leaks_raw_key = payload.get("listedLeaksRawKey")
    present_after_revoke = payload.get("presentAfterRevoke")

    assert isinstance(created, dict), "Missing created API key payload"
    assert created.get("device_limit") == 2, (
        f"Created API key payload is missing the expected device_limit: {created!r}"
    )
    assert created.get("expires_at") == "2028-05-19T00:00:00Z", (
        f"Created API key payload is missing the expected expires_at: {created!r}"
    )
    raw_key = created.get("raw_key")
    key_prefix = created.get("key_prefix")
    assert isinstance(raw_key, str), "Missing raw_key on created API key"
    assert isinstance(key_prefix, str), "Missing key_prefix on created API key"
    assert raw_key.startswith(key_prefix)

    assert isinstance(listed_match, dict), "Created API key missing from listApiKeys()"
    assert listed_match.get("device_limit") == 2, (
        f"listApiKeys() is missing the expected device_limit: {listed_match!r}"
    )
    assert listed_match.get("expires_at") == "2028-05-19T00:00:00Z", (
        f"listApiKeys() is missing the expected expires_at: {listed_match!r}"
    )
    assert listed_match.get("key_prefix") == key_prefix

    assert isinstance(first_hosted, dict), "Missing first hosted request payload"
    assert first_hosted.get("status") == "ok", (
        f"First hosted request failed unexpectedly: {first_hosted!r}"
    )
    assert isinstance(first_hosted.get("body"), dict), (
        f"First hosted request returned malformed body: {first_hosted!r}"
    )
    assert isinstance(first_hosted["body"].get("org"), dict), (
        f"First hosted request is missing org payload: {first_hosted!r}"
    )

    assert isinstance(repeated_hosted, dict), "Missing repeated hosted request payload"
    assert repeated_hosted.get("status") == "ok", (
        f"Repeated hosted request failed unexpectedly: {repeated_hosted!r}"
    )
    assert isinstance(repeated_hosted.get("body"), dict), (
        f"Repeated hosted request returned malformed body: {repeated_hosted!r}"
    )
    assert isinstance(repeated_hosted["body"].get("org"), dict), (
        f"Repeated hosted request is missing org payload: {repeated_hosted!r}"
    )

    assert isinstance(mismatched_hosted, dict), "Missing mismatched hosted request payload"
    assert mismatched_hosted.get("status") == "error", (
        f"Mismatched hosted request should fail closed: {mismatched_hosted!r}"
    )
    assert mismatched_hosted.get("statusCode") == 403, (
        f"Mismatched hosted request should return 403: {mismatched_hosted!r}"
    )
    assert mismatched_hosted.get("errorCode") == "device_identity_mismatch", (
        f"Mismatched hosted request returned the wrong error code: {mismatched_hosted!r}"
    )
    mismatched_body = mismatched_hosted.get("responseBody")
    assert isinstance(mismatched_body, dict), (
        f"Mismatched hosted request returned malformed error body: {mismatched_hosted!r}"
    )
    mismatched_error = mismatched_body.get("error")
    if mismatched_error is None:
        detail = mismatched_body.get("detail", mismatched_body)
        mismatched_error = detail.get("error", detail) if isinstance(detail, dict) else None
    assert isinstance(mismatched_error, dict), (
        f"Mismatched hosted request returned malformed structured error: {mismatched_hosted!r}"
    )
    assert mismatched_error.get("code") == "device_identity_mismatch"
    assert mismatched_error.get("device_id") == "hosted-device-0001"
    assert mismatched_error.get("mismatched_fields") == ["hostname_hash"]

    assert isinstance(env_hosted, dict), "Missing env-hosted request payload"
    assert env_hosted.get("status") == "ok", (
        f"Env-hosted request failed unexpectedly: {env_hosted!r}"
    )
    assert isinstance(env_hosted.get("body"), dict), (
        f"Env-hosted request returned malformed body: {env_hosted!r}"
    )
    assert isinstance(env_hosted["body"].get("org"), dict), (
        f"Env-hosted request is missing org payload: {env_hosted!r}"
    )

    assert isinstance(third_hosted, dict), "Missing third hosted request payload"
    assert third_hosted.get("status") == "error", (
        f"Third hosted request should fail closed at the device limit: {third_hosted!r}"
    )
    assert third_hosted.get("statusCode") == 402, (
        f"Third hosted request should return 402 at the device limit: {third_hosted!r}"
    )
    assert third_hosted.get("errorCode") == "device_limit_reached", (
        f"Third hosted request returned the wrong error code: {third_hosted!r}"
    )
    third_body = third_hosted.get("responseBody")
    assert isinstance(third_body, dict), (
        f"Third hosted request returned malformed error body: {third_hosted!r}"
    )
    error = third_body.get("error")
    if error is None:
        detail = third_body.get("detail", third_body)
        error = detail.get("error", detail) if isinstance(detail, dict) else None
    assert isinstance(error, dict), (
        f"Third hosted request returned malformed structured error: {third_hosted!r}"
    )
    assert error.get("code") == "device_limit_reached"
    assert error.get("device_limit") == 2
    assert error.get("device_count") == 2

    assert isinstance(revoked_hosted, dict), "Missing revoked hosted request payload"
    assert revoked_hosted.get("status") == "error", (
        f"Revoked hosted request should fail closed immediately: {revoked_hosted!r}"
    )
    assert revoked_hosted.get("statusCode") == 401, (
        f"Revoked hosted request should return 401: {revoked_hosted!r}"
    )
    assert revoked_hosted.get("errorCode") == "invalid_api_key", (
        f"Revoked hosted request returned the wrong SDK error code: {revoked_hosted!r}"
    )
    revoked_body = revoked_hosted.get("responseBody")
    assert isinstance(revoked_body, dict), (
        f"Revoked hosted request returned malformed error body: {revoked_hosted!r}"
    )
    revoked_error = revoked_body.get("error")
    if revoked_error is None:
        detail = revoked_body.get("detail", revoked_body)
        revoked_error = detail.get("error", detail) if isinstance(detail, dict) else None
    assert isinstance(revoked_error, dict), (
        f"Revoked hosted request returned malformed structured error: {revoked_hosted!r}"
    )
    assert revoked_error.get("code") == "invalid_api_key"

    assert listed_leaks_raw_key is False
    assert present_after_revoke is False


def main() -> int:
    started = time.perf_counter()
    _emit("\n" + "=" * 70)
    _emit("  LIVE TYPESCRIPT RUNTIME INTEGRATION")
    _emit("=" * 70)

    with isolated_api_server():
        check("Build TypeScript SDK", build_ts_sdk)
        check("TypeScript Mojo library surface", run_typescript_mojo_library_surface)
        check("TypeScript API key lifecycle", run_typescript_api_key_lifecycle)
        check("TypeScript Runtime connector matrix", run_typescript_runtime_connector_matrix)
        check("TypeScript Runtime(mode='api') LLM helper surface", run_typescript_runtime_api_llm_surface)
        check("TypeScript Runtime(mode='api') proof routes", run_typescript_runtime_proof_surface)
        check("TypeScript Runtime(mode='api') account helpers", run_typescript_runtime_account_surface)
        check(
            "TypeScript Runtime(mode='api') connectors + dataset lifecycle helpers",
            run_typescript_runtime_dataset_surface,
        )
        check(
            "TypeScript Runtime(mode='api') repository intelligence helpers",
            run_typescript_runtime_repository_surface,
        )
        check(
            "TypeScript Runtime(mode='api') team/credits/metering/audit/execution-policy helpers",
            run_typescript_runtime_control_plane_surface,
        )
        check("TypeScript Runtime(mode='api') trigger helpers", run_typescript_runtime_trigger_surface)
        check(
            "TypeScript Runtime(mode='api') deployment lifecycle",
            run_typescript_runtime_deployment_lifecycle_surface,
        )
        check("TypeScript Runtime(mode='api') decision runtime helpers", run_typescript_runtime_api_decision_surface)
        check("TypeScript Runtime(mode='api') simplified product helpers", run_typescript_runtime_product_surface)
        check("TypeScript Runtime(mode='api') plan + agent-run helpers", run_typescript_runtime_plan_and_agent_surface)

    skipped = [result for result in results if result[0] == SKIP]
    failed = [result for result in results if result[0] == FAIL]
    _emit("\n" + "=" * 70)
    _emit(f"Passed: {sum(1 for result in results if result[0] == PASS)}")
    _emit(f"Skipped: {len(skipped)}")
    _emit(f"Failed: {len(failed)}")
    if skipped:
        _emit("Skipped:")
        for _, name, message in skipped:
            _emit(f"  - {name}: {message}")
    if failed:
        _emit("Failures:")
        for _, name, message in failed:
            _emit(f"  - {name}: {message}")
    _emit("=" * 70)
    minimum_passed = filtered_minimum_passed(
        2 if API_KEY_CONFIGURED else 1,
        ACTIVE_LIVE_CHECK_FILTER_TOKENS,
    )
    summary = write_live_summary_artifact(
        output_path=SUMMARY_ARTIFACT,
        suite_name=SUITE_NAME,
        script="tests/integration/test_typescript_runtime_live.py",
        channels=("typescript_sdk",),
        minimum_passed=minimum_passed,
        passed=sum(1 for result in results if result[0] == PASS),
        failed=len(failed),
        skipped=len(skipped),
        elapsed_seconds=time.perf_counter() - started,
        extra={
            "base_url": BASE_URL,
            "api_key_configured": API_KEY_CONFIGURED,
            "total": len(results),
        },
    )
    _emit(f"Summary artifact: {SUMMARY_ARTIFACT}")
    expected_status = "passed" if not failed and summary["passed"] >= minimum_passed else "failed"
    assert summary["status"] == expected_status
    return 0 if not failed else 1


if __name__ == "__main__":
    import pytest

    exit_code = pytest.main([__file__, "-v"])
    # Write summary artifact for CI consumers (preserves the
    # tests/test_runtime_surface_compatibility surface contract).
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary

        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_typescript_runtime_live.py",
            passed=0,  # TODO: parse from pytest result
            failed=0,
            skipped=0,
            total=0,
            elapsed_seconds=0.0,
        )
        print(f"Summary artifact: {artifact_path}")
    except Exception:
        pass
    sys.exit(exit_code)
