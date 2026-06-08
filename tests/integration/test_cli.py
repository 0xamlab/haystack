"""
CLI integration tests — tests apps/cli/main.py against a live server at localhost:8000.

Prerequisites:
  1. API server running on localhost:8000
  2. PostgreSQL + Redis running
  3. Dev data seeded

Run:
  DE_API_KEY="..." python3 tests/integration/test_cli.py
"""

if __name__ != "__main__":
    import pytest

    pytest.skip(
        "Standalone integration script; run via python tests/integration/test_cli.py",
        allow_module_level=True,
    )

import atexit
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: noqa: E402
from apps.platform_contract import PlatformContractResponse
from apps.runtime_manifest import (
    RuntimeAdminBenchmarksResponse,
    normalize_runtime_validation_payload,
)
from tests._manifest_backed_integrations import (
    contract_integrations_match_manifest,
)
from tests.integration.live_capacity_blockers import (
    classify_simulation_capacity_blocker,
    parse_cli_error_payload,
)
from tests.integration.live_check_filter import (
    filtered_live_check_reason,
    live_check_filter_tokens,
    selected_live_check_filter,
    should_run_live_check,
)
from tests.integration.live_data_source_server import (
    default_refreshable_dataset_payload,
    static_json_server,
)
from tests.integration.live_integration_artifacts import write_live_integration_summary
from tests.integration.live_repository_fixture import (
    assert_repository_intelligence_capabilities_payload,
    live_repository_fixture,
    local_repository_live_support_reason,
)

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
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
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()
PROJECT_ROOT = str(ROOT)
CLI_SCRIPT = str(ROOT / "apps" / "cli" / "main.py")
SUITE_NAME = "cli_integration"
STARTED = time.perf_counter()
ACTIVE_LIVE_CHECK_FILTER = selected_live_check_filter()
ACTIVE_LIVE_CHECK_FILTER_TOKENS = live_check_filter_tokens(ACTIVE_LIVE_CHECK_FILTER)
_runtime_proc: subprocess.Popen[str] | None = None
_runtime_started_here = False
_runtime_log_path: Path | None = None

PASS = "✅"
SKIP = "⏭️"
FAIL = "❌"
results: list[tuple] = []


class EnvironmentBlocked(RuntimeError):  # noqa: N818
    """Raised when the live environment cannot run simulation checks."""


def _missing_live_api_key_reason(exc: BaseException) -> str | None:
    if API_KEY_CONFIGURED:
        return None
    payload = parse_cli_error_payload(str(exc)) or {}
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and error.get("code") == "invalid_api_key":
        return "DE_API_KEY is not set; skipping authenticated CLI checks that require a real live key."
    return None


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
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for {base_url}/v1/health: {last_error}.{_read_log(log_path)}"
    )


@contextlib.contextmanager
def webhook_receiver() -> tuple[str, list[dict[str, object]]]:
    deliveries: list[dict[str, object]] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(content_length)
            try:
                body = json.loads(payload)
            except Exception:
                body = {"raw": payload.decode("utf-8", errors="replace")}
            deliveries.append(
                {
                    "path": self.path,
                    "body": body,
                }
            )
            encoded = json.dumps({"received": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((DEFAULT_HOST, 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/webhook", deliveries
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _endpoint_serves_canonical_cli_surface(base_url: str) -> bool:
    try:
        status, health = _probe_json(base_url, "/v1/health", timeout=3.0)
        if status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
            return False
        status, spec = _probe_json(base_url, "/openapi.json", timeout=5.0)
        if status != 200 or not isinstance(spec, dict):
            return False
        expected_security = [{"BearerAuth": []}, {"LegacyApiKey": []}]
        for path, method in (
            ("/v1/me", "get"),
            ("/v1/me", "patch"),
            ("/v1/usage", "get"),
            ("/v1/limits", "get"),
            ("/v1/distributions", "get"),
            ("/v1/templates", "get"),
            ("/v1/billing/info", "get"),
            ("/v1/billing/checkout", "post"),
            ("/v1/billing/portal", "post"),
            ("/v1/metering", "post"),
            ("/v1/credits/refresh", "post"),
            ("/v1/team", "get"),
            ("/v1/team/invite", "post"),
            ("/v1/team/{user_id}/role", "patch"),
            ("/v1/team/{user_id}", "delete"),
            ("/v1/device/list", "get"),
            ("/v1/device/{registration_id}", "delete"),
            ("/v1/audit-logs", "get"),
            ("/v1/audit-logs/artifacts", "get"),
            ("/v1/execution/policy", "get"),
            ("/v1/execution/policy/snapshots", "get"),
            ("/v1/execution/policy", "patch"),
            ("/v1/api-keys", "get"),
            ("/v1/api-keys", "post"),
            ("/v1/api-keys/{key_id}", "delete"),
            ("/v1/connectors", "post"),
            ("/v1/connectors/test", "post"),
            ("/v1/connectors/browse", "post"),
            ("/v1/data/connect", "post"),
            ("/v1/data", "get"),
            ("/v1/data/{dataset_id}/refresh", "post"),
            ("/v1/data/{dataset_id}/summary", "get"),
            ("/v1/data/{dataset_id}", "get"),
            ("/v1/data/{dataset_id}", "delete"),
            ("/v1/repositories/capabilities", "get"),
            ("/v1/repositories/{repository_id}/snapshots", "post"),
            ("/v1/repositories/{repository_id}/snapshots/{snapshot_id}", "get"),
            ("/v1/repositories/{repository_id}/triage", "post"),
            ("/v1/repositories/{repository_id}/decision-plans", "post"),
            ("/v1/repositories/{repository_id}/simulate", "post"),
            ("/v1/repositories/{repository_id}/apply", "post"),
            ("/v1/connectors/{connector_id}", "get"),
            ("/v1/connectors/{connector_id}", "patch"),
            ("/v1/connectors/{connector_id}/test", "post"),
            ("/v1/connectors/{connector_id}/browse", "get"),
            ("/v1/connectors/{connector_id}", "delete"),
            ("/v1/jobs/list", "get"),
            ("/v1/jobs/{job_id}/result", "get"),
            ("/v1/jobs/{job_id}/cancel", "post"),
            ("/v1/webhooks/test", "post"),
            ("/v1/triggers", "get"),
            ("/v1/triggers", "post"),
            ("/v1/triggers/{trigger_id}/fire", "post"),
            ("/v1/triggers/{trigger_id}/pause", "patch"),
            ("/v1/triggers/{trigger_id}", "delete"),
            ("/v1/deployments/regions", "get"),
            ("/v1/deployments", "get"),
            ("/v1/deployments", "post"),
            ("/v1/deployments/{deployment_id}", "delete"),
            ("/v1/deployments/{deployment_id}/cost", "get"),
            ("/v1/recommend", "post"),
            ("/v1/score", "post"),
            ("/v1/batch", "post"),
            ("/v1/compare", "post"),
            ("/v1/models", "get"),
            ("/v1/artifacts/resolve", "post"),
            ("/v1/tokenize", "post"),
            ("/v1/count_tokens", "post"),
            ("/v1/chat/completions", "post"),
            ("/v1/responses", "post"),
            ("/v1/embeddings", "post"),
            ("/v1/embeddings/similarity", "post"),
            ("/v1/rerank", "post"),
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
        ):
            if spec.get("paths", {}).get(path, {}).get(method, {}).get("security") != expected_security:
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
        status, models = _probe_json(
            base_url,
            "/v1/models",
            timeout=5.0,
            headers=auth_headers,
        )
        if status != 200 or not isinstance(models, dict) or not isinstance(models.get("data"), list):
            return False
        status, me = _probe_json(
            base_url,
            "/v1/me",
            timeout=5.0,
            headers=auth_headers,
        )
        if status != 200 or not isinstance(me, dict):
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
    log_dir = Path(tempfile.mkdtemp(prefix="integration-cli-"))
    log_path = log_dir / "api_server.log"

    if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):
        try:
            _wait_for_health(base_url, log_path, timeout_seconds=5.0)
            if _endpoint_serves_canonical_cli_surface(base_url):
                return base_url
        except RuntimeError:
            pass

    port = _choose_free_port()
    base_url = f"http://{DEFAULT_HOST}:{port}"
    env = os.environ.copy()
    env.setdefault("ALGENTA_SOURCE_REGISTRY_ROOT", str(log_dir / "sources"))
    env.setdefault("ALGENTA_RUNTIME_DIR", str(log_dir / "runtime"))
    env.setdefault("ALGENTA_REPOSITORY_INTELLIGENCE_MODEL", "repository.deterministic_local_v1")
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
            cwd=PROJECT_ROOT,
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
API_KEY, API_KEY_CONFIGURED, LOCAL_LIVE_AUTH_BOOTSTRAP_ERROR = (
    ensure_bootstrapped_local_live_api_key(
        api_key=API_KEY,
        api_key_configured=API_KEY_CONFIGURED,
        active_base_url=BASE_URL,
    )
)
atexit.register(_cleanup_runtime)


def _emit(message: str = "") -> None:
    print(message, flush=True)


def check(name: str, fn):
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    if not should_run_live_check(name, ACTIVE_LIVE_CHECK_FILTER_TOKENS):
        reason = filtered_live_check_reason(ACTIVE_LIVE_CHECK_FILTER)
        results.append((SKIP, name, reason))
        _emit(f"  {SKIP} {name} ({time.monotonic() - started_at:.2f}s): {reason}")
        return
    try:
        fn()
        results.append((PASS, name))
        _emit(f"  {PASS} {name} ({time.monotonic() - started_at:.2f}s)")
    except EnvironmentBlocked as e:
        results.append((SKIP, name, str(e)))
        _emit(f"  {SKIP} {name} ({time.monotonic() - started_at:.2f}s): {e}")
    except AssertionError as e:
        missing_key_reason = _missing_live_api_key_reason(e)
        if missing_key_reason is not None:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({time.monotonic() - started_at:.2f}s): "
                f"{missing_key_reason}"
            )
            return
        results.append((FAIL, name, str(e)))
        _emit(f"  {FAIL} {name} ({time.monotonic() - started_at:.2f}s): {e}")
    except Exception as e:
        missing_key_reason = _missing_live_api_key_reason(e)
        if missing_key_reason is not None:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({time.monotonic() - started_at:.2f}s): "
                f"{missing_key_reason}"
            )
            return
        results.append((FAIL, name, str(e)))
        _emit(
            f"  {FAIL} {name} ({time.monotonic() - started_at:.2f}s): "
            f"{type(e).__name__}: {e}"
        )


def run_cli(
    *args: str, api_key: str | None = None, base_url: str | None = None, timeout: float = 15
) -> subprocess.CompletedProcess:
    """Run the CLI as a subprocess and return the result."""
    env = os.environ.copy()
    resolved_api_key = api_key or API_KEY
    resolved_base_url = base_url or BASE_URL
    # Keep both canonical and legacy env names aligned so subprocesses cannot
    # accidentally inherit a valid higher-priority key/base URL from the parent.
    env["DE_API_KEY"] = resolved_api_key
    env["ALGENTA_API_KEY"] = resolved_api_key
    env["DE_BASE_URL"] = resolved_base_url
    env["ALGENTA_BASE_URL"] = resolved_base_url
    env["PYTHONPATH"] = PROJECT_ROOT
    cmd = [sys.executable, CLI_SCRIPT] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=PROJECT_ROOT,
    )


def ensure_cli_simulation_not_capacity_blocked(result: subprocess.CompletedProcess) -> None:
    if result.returncode == 0:
        return

    combined = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
    payload = parse_cli_error_payload(combined)
    reason = classify_simulation_capacity_blocker(
        status=429 if "Error 429" in combined else None,
        payload=payload,
        text=combined,
    )
    if reason is not None:
        raise EnvironmentBlocked(reason)


def ensure_cli_credit_refresh_not_blocked(result: subprocess.CompletedProcess) -> None:
    if result.returncode == 0:
        return
    combined = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
    payload = parse_cli_error_payload(combined)
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    code = None
    if isinstance(detail, dict):
        raw_code = detail.get("error", detail.get("code"))
        if isinstance(raw_code, str):
            code = raw_code
    normalized = combined.lower()
    if code in {"quota_exhausted", "quota_exceeded"}:
        raise EnvironmentBlocked("credit refresh quota exhausted for this live environment")
    if "quota_exhausted" in normalized or "quota_exceeded" in normalized:
        raise EnvironmentBlocked("credit refresh quota exhausted for this live environment")


def ensure_cli_artifact_bridge_not_blocked(result: subprocess.CompletedProcess) -> None:
    if result.returncode == 0:
        return
    combined = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
    payload = parse_cli_error_payload(combined)
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    code = detail.get("code") if isinstance(detail, dict) else None
    if code == "artifact_bridge_backend_unavailable":
        raise EnvironmentBlocked(
            "artifact bridge requires the optional huggingface_hub backend in this checkout"
        )


def _assert_cli_repository_error(
    result: subprocess.CompletedProcess,
    *,
    error_code: str,
) -> dict[str, object]:
    combined = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
    payload = parse_cli_error_payload(combined)
    assert payload is not None, combined
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    error = detail.get("error", detail) if isinstance(detail, dict) else None
    assert isinstance(error, dict), payload
    assert error.get("code") == error_code, payload
    return error


def write_temp_json(data: dict) -> str:
    """Write a dict to a temp JSON file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="de_test_")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return path


def build_live_dataset_payload(prefix: str, source_url: str) -> dict:
    return {
        "connection_type": "api",
        "provider": "rest",
        "dataset_name": f"{prefix}-{time.time_ns()}",
        "description": "Live CLI refreshable dataset check.",
        "connection_config": {
            "url": source_url,
            "data_path": "items",
        },
    }


def build_live_connector_payload(prefix: str, source_url: str) -> dict:
    return {
        "name": f"{prefix}-{time.time_ns()}",
        "connector_type": "rest",
        "description": "Live CLI saved connector check.",
        "config": {
            "url": source_url,
            "data_path": "items",
        },
    }


def build_live_trigger_request(name: str) -> dict:
    return {
        "name": name,
        "condition": {
            "source_id": f"missing_source_{name}",
            "metric_hint": "revenue",
            "threshold": 1000.0,
            "direction": "above",
            "aggregation": "sum",
        },
        "simulation_template": {
            "mode": "auto",
            "scenario": {
                "variables": {"revenue": {"low": 1000, "high": 2000}},
                "objective": "maximize_net_value",
            },
            "runs": 50,
        },
        "description": "Live CLI trigger lifecycle check.",
        "auto_execute": False,
    }


def parse_json_lines(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: CLI — Basic Commands
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 1: CLI — Basic Commands")
print("=" * 70)


def test_cli_help():
    """Running with no args should show help/usage."""
    result = run_cli()
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr}"
    output = result.stdout + result.stderr
    # Should contain usage info
    assert (
        "simulate" in output.lower() or "usage" in output.lower() or "decision" in output.lower()
    ), f"Help output missing expected keywords: {output[:300]}"


check("CLI no args → help/usage text", test_cli_help)


def test_cli_health():
    result = run_cli("health")
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}: stderr={result.stderr}"
    )
    output = result.stdout
    assert "ok" in output.lower() or "✅" in output, f"Expected 'ok' in output: {output[:200]}"


check("CLI health → OK", test_cli_health)


def test_cli_version():
    result = run_cli("version")
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}: stderr={result.stderr}"
    )
    output = result.stdout
    assert "engine" in output.lower() or "api" in output.lower(), (
        f"Expected version info: {output[:200]}"
    )


check("CLI version → version info", test_cli_version)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: CLI — Simulate Command
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 2: CLI — Simulate Command")
print("=" * 70)


def test_cli_simulate_auto():
    """Run a simulation via CLI with an auto-mode payload file."""
    payload = {
        "mode": "auto",
        "runs": 1000,
        "scenario": {
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(result)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:500]}"
        )
        output = result.stdout.strip()
        # Should be valid JSON
        data = json.loads(output)
        assert "recommended_action" in data, f"Missing recommended_action: {list(data.keys())}"
        assert data["recommended_action"] in ("proceed", "hold", "reject"), (
            f"Unexpected action: {data['recommended_action']}"
        )
        assert "confidence" in data, "Missing confidence"
        assert 0 <= data["confidence"] <= 1, f"Confidence out of range: {data['confidence']}"
    finally:
        os.unlink(path)


check("CLI simulate auto → JSON with recommended_action", test_cli_simulate_auto)


def test_cli_simulate_expert():
    """Run an expert-mode simulation via CLI."""
    payload = {
        "mode": "expert",
        "runs": 500,
        "simulation": {
            "variables": [
                {
                    "name": "revenue",
                    "distribution": "triangular",
                    "params": {"low": 80000, "mode": 120000, "high": 200000},
                },
                {"name": "costs", "distribution": "normal", "params": {"mean": 55000, "std": 8000}},
            ],
            "objective_function": "revenue - costs",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(result)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:500]}"
        )
        data = json.loads(result.stdout.strip())
        assert "recommended_action" in data, "Missing recommended_action"
        assert "metrics" in data, "Missing metrics"
    finally:
        os.unlink(path)


check("CLI simulate expert → JSON with metrics", test_cli_simulate_expert)


def test_cli_simulate_table_format():
    """Default (table) format should produce readable output."""
    payload = {
        "mode": "auto",
        "runs": 100,
        "scenario": {
            "variables": {"x": {"low": 0, "high": 100}},
            "objective": "maximize_net_value",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path)
        ensure_cli_simulation_not_capacity_blocked(result)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:500]}"
        )
        output = result.stdout
        # Table format should contain "Recommendation" or the action or JSON fallback
        has_content = (
            "proceed" in output.lower()
            or "hold" in output.lower()
            or "reject" in output.lower()
            or "recommended_action" in output
        )
        assert has_content, f"Expected decision info in table output: {output[:300]}"
    finally:
        os.unlink(path)


check("CLI simulate table format → readable output", test_cli_simulate_table_format)


def test_cli_simulate_envelope_fields():
    """Verify the JSON output contains all envelope fields."""
    payload = {
        "mode": "auto",
        "runs": 1000,
        "scenario": {
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(result)
        assert result.returncode == 0, f"Exit {result.returncode}: {result.stderr[:300]}"
        data = json.loads(result.stdout.strip())
        required_fields = [
            "run_id",
            "status",
            "recommended_action",
            "confidence",
            "metrics",
            "percentiles",
            "scenarios_run",
            "execution_ms",
        ]
        for field in required_fields:
            assert field in data, f"Missing field '{field}' in envelope: {list(data.keys())}"
        # Validate metrics sub-object
        metrics = data["metrics"]
        assert "expected_value" in metrics, "Missing expected_value in metrics"
        assert "probability_of_loss" in metrics, "Missing probability_of_loss in metrics"
        # Validate percentiles
        pct = data["percentiles"]
        assert pct["p5"] <= pct["p95"], f"p5={pct['p5']} > p95={pct['p95']}"
    finally:
        os.unlink(path)


check(
    "CLI simulate → full envelope with metrics and percentiles", test_cli_simulate_envelope_fields
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: CLI — Error Cases
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 3: CLI — Error Cases")
print("=" * 70)


def test_cli_bad_api_key():
    """Bad API key should produce an error and non-zero exit."""
    payload = {
        "mode": "auto",
        "runs": 100,
        "scenario": {
            "variables": {"x": {"low": 0, "high": 100}},
            "objective": "maximize_net_value",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json", api_key="de_live_INVALID_KEY_FAKE")
        assert result.returncode != 0, (
            f"Expected non-zero exit for bad key, got {result.returncode}"
        )
        combined = result.stdout + result.stderr
        assert "401" in combined or "error" in combined.lower() or "❌" in combined, (
            f"Expected error message for bad key: {combined[:300]}"
        )
    finally:
        os.unlink(path)


check("CLI bad API key → error + non-zero exit", test_cli_bad_api_key)


def test_cli_bad_payload():
    """Invalid payload should produce an error."""
    payload = {"mode": "invalid_mode_xyz"}
    path = write_temp_json(payload)
    try:
        result = run_cli("simulate", path, "--format", "json")
        assert result.returncode != 0, (
            f"Expected non-zero exit for bad payload, got {result.returncode}"
        )
        combined = result.stdout + result.stderr
        assert "error" in combined.lower() or "❌" in combined or "422" in combined, (
            f"Expected error in output: {combined[:300]}"
        )
    finally:
        os.unlink(path)


check("CLI bad payload → error + non-zero exit", test_cli_bad_payload)


def test_cli_missing_file():
    """Non-existent file should produce an error."""
    result = run_cli("simulate", "/tmp/nonexistent_file_12345.json", "--format", "json")
    assert result.returncode != 0, (
        f"Expected non-zero exit for missing file, got {result.returncode}"
    )


check("CLI missing file → non-zero exit", test_cli_missing_file)


def test_cli_unknown_command():
    """Unknown command should produce an error."""
    result = run_cli("nonexistent_command_xyz")
    assert result.returncode != 0, (
        f"Expected non-zero exit for unknown command, got {result.returncode}"
    )


check("CLI unknown command → non-zero exit", test_cli_unknown_command)


def test_cli_invalid_json_file():
    """File with invalid JSON should fail."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="de_test_")
    with os.fdopen(fd, "w") as f:
        f.write("{ this is not valid json !!!")
    try:
        result = run_cli("simulate", path, "--format", "json")
        assert result.returncode != 0, (
            f"Expected non-zero exit for invalid JSON, got {result.returncode}"
        )
    finally:
        os.unlink(path)


check("CLI invalid JSON file → non-zero exit", test_cli_invalid_json_file)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: CLI — Runtime Proof Commands
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 4: CLI — Runtime Proof Commands")
print("=" * 70)


def test_cli_runtime_admin_benchmarks():
    if not API_KEY_CONFIGURED:
        raise EnvironmentBlocked(
            "DE_API_KEY is not set; skipping authenticated CLI checks that require a real live key."
        )
    result = run_cli("runtime", "admin-benchmarks", "--format", "table")
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:300]}"
    )
    output = result.stdout
    assert "Algenta runtime benchmark catalog:" in output, output[:500]
    assert "Benchmark classes:" in output, output
    assert "B1: microkernel latency" in output, output
    assert "benchmarks/summary.json" in output, output
    assert "tests/benchmark_mojo_vs_python.py" in output, output
    assert "Quality gate benchmark classes:" in output, output
    assert "B6: checkpoint and replay overhead [evidence: none]" in output, output

    json_result = run_cli("runtime", "admin-benchmarks", "--format", "json")
    assert json_result.returncode == 0, (
        f"Expected exit 0, got {json_result.returncode}: stderr={json_result.stderr[:300]}"
    )
    payload = json.loads(json_result.stdout)
    provider_routing_overhead = next(
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] == "B8"
    )
    assert provider_routing_overhead["description"] == "provider routing overhead"
    assert provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    checkpoint_overhead = next(
        entry
        for entry in payload["quality_gate_benchmark_classes"]
        if entry["code"] == "B6"
    )
    assert checkpoint_overhead["description"] == "checkpoint and replay overhead"
    assert checkpoint_overhead["evidence_paths"] == []
    decision_workflow_completion = next(
        entry
        for entry in payload["quality_gate_benchmark_classes"]
        if entry["code"] == "B10"
    )
    assert decision_workflow_completion["description"] == "decision workflow completion latency"
    assert decision_workflow_completion["evidence_paths"] == [
        "build/repository_intelligence_benchmark.json",
        "benchmarks/repository_intelligence_benchmark.py",
        "tests/test_repository_intelligence_benchmark.py",
    ]
    assert {entry["code"] for entry in payload["quality_gate_benchmark_classes"]} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert [entry["name"] for entry in payload["quality_gate_slo_budgets"]] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert payload["evaluation_summary"]["replay_gate_enabled"] is True
    assert payload["evaluation_summary"]["tool_call_quality_gate_enabled"] is True
    assert payload["evaluation_summary"]["rag_quality_gate_enabled"] is True
    assert payload["evaluation_summary"]["decision_quality_gate_enabled"] is True


check("CLI runtime proof surface → benchmark classes + evidence", test_cli_runtime_admin_benchmarks)


def test_cli_runtime_manifest():
    if not API_KEY_CONFIGURED:
        raise EnvironmentBlocked(
            "DE_API_KEY is not set; skipping authenticated CLI checks that require a real live key."
        )
    result = run_cli("runtime", "manifest", "--format", "table")
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:300]}"
    )
    output = result.stdout
    assert "Algenta runtime manifest:" in output, output[:500]
    assert "22 shipping / 22 listed" in output, output

    json_result = run_cli("runtime", "manifest", "--format", "json")
    assert json_result.returncode == 0, (
        f"Expected exit 0, got {json_result.returncode}: stderr={json_result.stderr[:300]}"
    )
    payload = json.loads(json_result.stdout)
    provider_routing_overhead = next(
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] == "B8"
    )
    assert provider_routing_overhead["description"] == "provider routing overhead"
    assert provider_routing_overhead["evidence_paths"] == [
        "build/provider_routing_overhead_benchmark.json",
        "benchmarks/provider_routing_overhead_benchmark.py",
        "tests/test_provider_routing_overhead_benchmark.py",
    ]
    checkpoint_overhead = next(
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] == "B6"
    )
    assert checkpoint_overhead["description"] == "checkpoint and replay overhead"
    assert checkpoint_overhead["evidence_paths"] == []
    decision_workflow_completion = next(
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] == "B10"
    )
    assert decision_workflow_completion["description"] == "decision workflow completion latency"
    assert decision_workflow_completion["evidence_paths"] == [
        "build/repository_intelligence_benchmark.json",
        "benchmarks/repository_intelligence_benchmark.py",
        "tests/test_repository_intelligence_benchmark.py",
    ]


check("CLI runtime proof surface → signed manifest benchmark classes", test_cli_runtime_manifest)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: CLI — LLM, Decision, and Agent Commands
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 5: CLI — LLM, Decision, and Agent Commands")
print("=" * 70)


def test_cli_llm_models():
    result = run_cli("llm", "models", "--format", "json")
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:300]}"
    )
    data = json.loads(result.stdout.strip())
    assert data["object"] == "list", f"Unexpected object type: {data}"
    model_ids = {item["id"] for item in data["data"]}
    assert "text.tokenizer" in model_ids, f"Missing text.tokenizer in {model_ids}"
    assert any(model_id.startswith("embeddings.") for model_id in model_ids), (
        f"Expected embeddings utility model in {model_ids}"
    )
    tokenizer = next((item for item in data["data"] if item["id"] == "text.tokenizer"), None)
    assert tokenizer is not None, data["data"]
    assert tokenizer["provider_backend"] is None, tokenizer
    assert tokenizer["routing_targets"] == [], tokenizer
    assert tokenizer["resolved_routing_targets"] == [], tokenizer
    assert tokenizer["chat_routing_targets"] == [], tokenizer
    assert tokenizer["resolved_chat_routing_targets"] == [], tokenizer
    assert tokenizer["embedding_routing_targets"] == [], tokenizer
    assert tokenizer["resolved_embedding_routing_targets"] == [], tokenizer
    assert tokenizer["required_provider_headers"] == [], tokenizer
    assert tokenizer["chat_required_provider_headers"] == [], tokenizer
    assert tokenizer["embedding_required_provider_headers"] == [], tokenizer
    assert tokenizer["provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["chat_provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["embedding_provider_auth_env_vars"] == [], tokenizer
    assert tokenizer["provider_auth_configured"] is False, tokenizer
    assert tokenizer["chat_provider_auth_configured"] is False, tokenizer
    assert tokenizer["embedding_provider_auth_configured"] is False, tokenizer


check("CLI llm models → truthful catalog", test_cli_llm_models)


def test_cli_llm_resolve_artifact():
    request_path = write_temp_json(
        {
            "repo_id": "bert-base-uncased",
            "filename": "model.safetensors",
            "revision": "main",
            "local_files_only": True,
        }
    )
    try:
        result = run_cli("llm", "resolve-artifact", request_path, "--format", "json")
        ensure_cli_artifact_bridge_not_blocked(result)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:300]}"
        )
        data = json.loads(result.stdout.strip())
        assert data["status"] in {"resolved", "not_cached"}
        assert data["filename"] == "model.safetensors"
        if data.get("resolved_path") is not None:
            assert data["resolved_path"]
    finally:
        os.unlink(request_path)


check("CLI llm resolve-artifact → cache-safe artifact bridge output", test_cli_llm_resolve_artifact)


def test_cli_llm_tokenize_and_count_tokens():
    tokenize = run_cli(
        "llm",
        "tokenize",
        "--input",
        "alpha beta gamma",
        "--format",
        "json",
    )
    assert tokenize.returncode == 0, (
        f"Expected exit 0, got {tokenize.returncode}: stderr={tokenize.stderr[:300]}"
    )
    token_data = json.loads(tokenize.stdout.strip())
    assert token_data["object"] == "tokenization"
    assert token_data["model"] == "text.tokenizer"
    assert token_data["token_count"] == len(token_data["tokens"]) == 3

    count = run_cli(
        "llm",
        "count-tokens",
        "--input",
        "alpha beta gamma",
        "--format",
        "json",
    )
    assert count.returncode == 0, (
        f"Expected exit 0, got {count.returncode}: stderr={count.stderr[:300]}"
    )
    count_data = json.loads(count.stdout.strip())
    assert count_data["object"] == "token_count"
    assert count_data["token_count"] == 3


check(
    "CLI llm tokenize/count-tokens → deterministic counts",
    test_cli_llm_tokenize_and_count_tokens,
)


def test_cli_llm_chat_responses_and_embeddings():
    chat_path = write_temp_json(
        {
            "model": "text.tokenizer",
            "messages": [{"role": "user", "content": "summarize alpha beta"}],
        }
    )
    responses_path = write_temp_json({"model": "text.tokenizer", "input": "alpha beta"})
    embeddings_path = write_temp_json(
        {
            "model": "text.hash_embedding_v1",
            "input": ["alpha beta", "gamma"],
            "dimensions": 8,
        }
    )
    try:
        chat = run_cli("llm", "chat", chat_path, "--format", "json")
        assert chat.returncode == 0, f"Exit {chat.returncode}: {chat.stderr[:300]}"
        chat_data = json.loads(chat.stdout.strip())
        assert chat_data["object"] == "chat.completion"
        assert chat_data["choices"][0]["message"]["role"] == "assistant"
        assert chat_data["provider_backend"] is None, chat_data
        assert chat_data["provider_model_id"] is None, chat_data
        assert chat_data["provider_attempts"] == [], chat_data

        responses = run_cli("llm", "responses", responses_path, "--format", "json")
        assert responses.returncode == 0, f"Exit {responses.returncode}: {responses.stderr[:300]}"
        responses_data = json.loads(responses.stdout.strip())
        assert responses_data["object"] == "response"
        assert responses_data["status"] == "completed"
        assert len(responses_data["output"]) >= 1
        assert responses_data["provider_backend"] is None, responses_data
        assert responses_data["provider_model_id"] is None, responses_data
        assert responses_data["provider_attempts"] == [], responses_data
        for item in responses_data["output"]:
            assert item["provider_backend"] is None, item
            assert item["provider_model_id"] is None, item
            assert item["provider_attempts"] == [], item

        embeddings = run_cli("llm", "embeddings", embeddings_path, "--format", "json")
        assert embeddings.returncode == 0, (
            f"Exit {embeddings.returncode}: {embeddings.stderr[:300]}"
        )
        embeddings_data = json.loads(embeddings.stdout.strip())
        assert embeddings_data["object"] == "list"
        assert embeddings_data["model"] == "text.hash_embedding_v1"
        assert embeddings_data["dimensions"] == 8
        assert len(embeddings_data["data"]) == 2
        assert embeddings_data["provider_backend"] is None, embeddings_data
        assert embeddings_data["provider_model_id"] is None, embeddings_data
        assert embeddings_data["provider_attempts"] == [], embeddings_data
    finally:
        os.unlink(chat_path)
        os.unlink(responses_path)
        os.unlink(embeddings_path)


check(
    "CLI llm chat/responses/embeddings → deterministic utility outputs",
    test_cli_llm_chat_responses_and_embeddings,
)


def test_cli_llm_streaming_surface():
    chat_path = write_temp_json(
        {
            "model": "text.tokenizer",
            "messages": [{"role": "user", "content": "summarize alpha beta"}],
        }
    )
    responses_path = write_temp_json({"model": "text.tokenizer", "input": "alpha beta"})
    try:
        chat = run_cli("llm", "chat", chat_path, "--stream", "--format", "json")
        assert chat.returncode == 0, f"Exit {chat.returncode}: {chat.stderr[:300]}"
        chat_events = parse_json_lines(chat.stdout)
        assert len(chat_events) >= 2
        assert all(event["object"] == "chat.completion.chunk" for event in chat_events)
        assert chat_events[0]["choices"][0]["delta"]["role"] == "assistant"
        assert chat_events[-1]["choices"][0]["finish_reason"] == "stop"
        assert all(event["provider_backend"] is None for event in chat_events), chat_events
        assert all(event["provider_model_id"] is None for event in chat_events), chat_events
        assert all(event["provider_attempts"] == [] for event in chat_events), chat_events

        chat_table = run_cli("llm", "chat", chat_path, "--stream")
        assert chat_table.returncode == 0, (
            f"Exit {chat_table.returncode}: {chat_table.stderr[:300]}"
        )
        assert "Completion ID:" in chat_table.stdout
        assert "Assistant:" in chat_table.stdout
        assert "Finish reason:" in chat_table.stdout

        responses = run_cli("llm", "responses", responses_path, "--stream", "--format", "json")
        assert responses.returncode == 0, (
            f"Exit {responses.returncode}: {responses.stderr[:300]}"
        )
        response_events = parse_json_lines(responses.stdout)
        assert len(response_events) >= 2
        assert response_events[0]["type"] == "response.created"
        assert response_events[-1]["type"] == "response.completed"
        assert response_events[0]["response"]["provider_backend"] is None, response_events
        assert response_events[0]["response"]["provider_model_id"] is None, response_events
        assert response_events[0]["response"]["provider_attempts"] == [], response_events
        output_event = next(
            (event for event in response_events if event["type"] == "response.output_item.done"),
            None,
        )
        assert output_event is not None, response_events
        assert output_event["item"]["provider_backend"] is None, output_event
        assert output_event["item"]["provider_model_id"] is None, output_event
        assert output_event["item"]["provider_attempts"] == [], output_event
        assert response_events[-1]["response"]["provider_backend"] is None, response_events
        assert response_events[-1]["response"]["provider_model_id"] is None, response_events
        assert response_events[-1]["response"]["provider_attempts"] == [], response_events

        responses_table = run_cli("llm", "responses", responses_path, "--stream")
        assert responses_table.returncode == 0, (
            f"Exit {responses_table.returncode}: {responses_table.stderr[:300]}"
        )
        assert "Response created:" in responses_table.stdout
        assert "Response completed:" in responses_table.stdout
    finally:
        os.unlink(chat_path)
        os.unlink(responses_path)


check("CLI llm streaming surface → typed SSE JSON lines", test_cli_llm_streaming_surface)


def test_cli_llm_similarity_and_rerank():
    similarity_path = write_temp_json(
        {
            "model": "embeddings.cosine_similarity",
            "left": [1.0, 0.0, 0.0],
            "right": [0.5, 0.5, 0.0],
        }
    )
    rerank_path = write_temp_json(
        {
            "model": "embeddings.cosine_similarity",
            "query_embedding": [1.0, 0.0, 0.0],
            "documents": [
                {"id": "doc_a", "embedding": [1.0, 0.0, 0.0], "text": "alpha"},
                {"id": "doc_b", "embedding": [0.0, 1.0, 0.0], "text": "beta"},
            ],
            "top_n": 2,
        }
    )
    try:
        similarity = run_cli("llm", "embedding-similarity", similarity_path, "--format", "json")
        assert similarity.returncode == 0, (
            f"Exit {similarity.returncode}: {similarity.stderr[:300]}"
        )
        similarity_data = json.loads(similarity.stdout.strip())
        assert similarity_data["object"] == "embedding_similarity"
        assert similarity_data["dimension"] == 3
        assert isinstance(similarity_data["score"], float)

        rerank = run_cli("llm", "rerank", rerank_path, "--format", "json")
        assert rerank.returncode == 0, f"Exit {rerank.returncode}: {rerank.stderr[:300]}"
        rerank_data = json.loads(rerank.stdout.strip())
        assert rerank_data["object"] == "list"
        assert rerank_data["returned_documents"] == 2
        assert rerank_data["data"][0]["rank"] == 1
        assert rerank_data["data"][0]["id"] == "doc_a"
    finally:
        os.unlink(similarity_path)
        os.unlink(rerank_path)


check("CLI llm similarity/rerank → vector utility surfaces", test_cli_llm_similarity_and_rerank)


def test_cli_decision_runtime_surface():
    recommend_path = write_temp_json(
        {
            "actions": [
                {
                    "name": "expand",
                    "request": {
                        "mode": "expert",
                        "runs": 150,
                        "simulation": {
                            "variables": [
                                {
                                    "name": "outcome",
                                    "distribution": "fixed",
                                    "params": {"value": 120},
                                }
                            ],
                            "objective_function": "outcome",
                        },
                    },
                },
                {
                    "name": "hold",
                    "request": {
                        "mode": "expert",
                        "runs": 150,
                        "simulation": {
                            "variables": [
                                {
                                    "name": "outcome",
                                    "distribution": "fixed",
                                    "params": {"value": 100},
                                }
                            ],
                            "objective_function": "outcome",
                        },
                    },
                },
            ]
        }
    )
    score_path = write_temp_json(
        {
            "request": {
                "mode": "expert",
                "runs": 150,
                "simulation": {
                    "variables": [
                        {
                            "name": "outcome",
                            "distribution": "normal",
                            "params": {"mean": 100, "std": 10},
                        }
                    ],
                    "objective_function": "outcome",
                },
            },
            "scoring_weights": {"expected_value": 0.7, "downside_risk": 0.3},
        }
    )
    batch_path = write_temp_json(
        {
            "items": [
                {
                    "mode": "expert",
                    "runs": 100,
                    "simulation": {
                        "variables": [
                            {
                                "name": "outcome",
                                "distribution": "fixed",
                                "params": {"value": 100},
                            }
                        ],
                        "objective_function": "outcome",
                    },
                },
                {
                    "mode": "expert",
                    "runs": 100,
                    "simulation": {
                        "variables": [
                            {
                                "name": "outcome",
                                "distribution": "fixed",
                                "params": {"value": 120},
                            }
                        ],
                        "objective_function": "outcome",
                    },
                },
            ]
        }
    )
    compare_path = write_temp_json(
        {
            "scenarios": [
                {
                    "name": "base",
                    "request": {
                        "mode": "expert",
                        "runs": 150,
                        "simulation": {
                            "variables": [
                                {
                                    "name": "outcome",
                                    "distribution": "fixed",
                                    "params": {"value": 100},
                                }
                            ],
                            "objective_function": "outcome",
                        },
                    },
                },
                {
                    "name": "stretch",
                    "request": {
                        "mode": "expert",
                        "runs": 150,
                        "simulation": {
                            "variables": [
                                {
                                    "name": "outcome",
                                    "distribution": "fixed",
                                    "params": {"value": 120},
                                }
                            ],
                            "objective_function": "outcome",
                        },
                    },
                },
            ]
        }
    )
    try:
        recommend = run_cli("recommend", recommend_path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(recommend)
        assert recommend.returncode == 0, (
            f"Expected exit 0, got {recommend.returncode}: stderr={recommend.stderr[:400]}"
        )
        recommend_data = json.loads(recommend.stdout.strip())
        assert recommend_data["recommended_action"]
        assert len(recommend_data["action_results"]) == 2

        score = run_cli("decision", "score", score_path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(score)
        assert score.returncode == 0, (
            f"Expected exit 0, got {score.returncode}: stderr={score.stderr[:400]}"
        )
        score_data = json.loads(score.stdout.strip())
        assert isinstance(score_data["score"], float)
        assert "score_breakdown" in score_data

        batch = run_cli("decision", "batch", batch_path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(batch)
        assert batch.returncode == 0, (
            f"Expected exit 0, got {batch.returncode}: stderr={batch.stderr[:400]}"
        )
        batch_data = json.loads(batch.stdout.strip())
        assert batch_data["total"] == 2
        assert len(batch_data["results"]) == 2

        compare = run_cli("decision", "compare", compare_path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(compare)
        assert compare.returncode == 0, (
            f"Expected exit 0, got {compare.returncode}: stderr={compare.stderr[:400]}"
        )
        compare_data = json.loads(compare.stdout.strip())
        assert compare_data["winner"] in {"base", "stretch"}
        assert len(compare_data["scenarios"]) == 2
    finally:
        os.unlink(recommend_path)
        os.unlink(score_path)
        os.unlink(batch_path)
        os.unlink(compare_path)


check("CLI decision runtime surface → recommend/score/batch/compare", test_cli_decision_runtime_surface)


def test_cli_product_surface():
    decision_path = write_temp_json(
        {
            "inputs": [
                {
                    "name": "revenue",
                    "value": 120000,
                    "low": 100000,
                    "high": 150000,
                    "unit": "USD",
                },
                {
                    "name": "cost",
                    "value": 70000,
                    "low": 60000,
                    "high": 90000,
                    "unit": "USD",
                },
            ],
            "risk_tolerance": "medium",
            "scenarios": 1000,
        }
    )
    agent_run_path = write_temp_json(
        {
            "task": f"Summarize benchmark blockers {time.time_ns()}",
            "tools": ["search"],
            "max_steps": 3,
        }
    )
    optimize_path = write_temp_json(
        {
            "objective": "maximize profit",
            "variables": [
                {"name": "price", "min": 50, "max": 150},
                {"name": "discount", "min": 0.0, "max": 0.2},
            ],
            "iterations": 100,
        }
    )
    retrieve_path = write_temp_json(
        {
            "query": "launch checklist",
            "documents": [
                {"id": "doc_1", "content": "Launch checklist for product release."},
                {"id": "doc_2", "content": "Pricing review for launch approval."},
            ],
            "top_k": 2,
        }
    )
    forecast_path = write_temp_json(
        {
            "metric": "monthly_revenue",
            "history": [100, 120, 130, 140],
            "horizon": 3,
        }
    )
    try:
        decision = run_cli("product", "decision", decision_path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(decision)
        assert decision.returncode == 0, (
            f"Expected exit 0, got {decision.returncode}: stderr={decision.stderr[:400]}"
        )
        decision_data = json.loads(decision.stdout.strip())
        assert decision_data["action"]
        assert 0 <= decision_data["confidence"] <= 1

        agent_run = run_cli("product", "agent-run", agent_run_path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(agent_run)
        assert agent_run.returncode == 0, (
            f"Expected exit 0, got {agent_run.returncode}: stderr={agent_run.stderr[:400]}"
        )
        agent_run_data = json.loads(agent_run.stdout.strip())
        assert agent_run_data["run_id"]
        assert agent_run_data["status"] in {"completed", "requires_approval", "running"}

        optimize = run_cli("product", "optimize", optimize_path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(optimize)
        assert optimize.returncode == 0, (
            f"Expected exit 0, got {optimize.returncode}: stderr={optimize.stderr[:400]}"
        )
        optimize_data = json.loads(optimize.stdout.strip())
        assert optimize_data["status"] == "completed"
        assert optimize_data["optimal_values"]

        retrieve = run_cli("product", "retrieve", retrieve_path, "--format", "json")
        assert retrieve.returncode == 0, (
            f"Expected exit 0, got {retrieve.returncode}: stderr={retrieve.stderr[:400]}"
        )
        retrieve_data = json.loads(retrieve.stdout.strip())
        assert retrieve_data["results"]
        assert retrieve_data["results"][0]["content"]

        forecast = run_cli("product", "forecast", forecast_path, "--format", "json")
        assert forecast.returncode == 0, (
            f"Expected exit 0, got {forecast.returncode}: stderr={forecast.stderr[:400]}"
        )
        forecast_data = json.loads(forecast.stdout.strip())
        assert forecast_data["forecast_mean"] >= 0
        assert forecast_data["periods"]
    finally:
        os.unlink(decision_path)
        os.unlink(agent_run_path)
        os.unlink(optimize_path)
        os.unlink(retrieve_path)
        os.unlink(forecast_path)


check("CLI product surface → decision/agent-run/optimize/retrieve/forecast", test_cli_product_surface)


def test_cli_decision_plan():
    payload = {
        "mode": "expert",
        "simulation_model": "monte_carlo",
        "runs": 250,
        "simulation": {
            "variables": [
                {
                    "name": "outcome",
                    "distribution": "normal",
                    "params": {"mean": 100, "std": 10},
                }
            ],
            "objective_function": "outcome",
        },
    }
    path = write_temp_json(payload)
    try:
        result = run_cli("decision", "plan", path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(result)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr[:400]}"
        )
        data = json.loads(result.stdout.strip())
        assert "recommended_action" in data, f"Missing recommended_action: {data}"
        assert "confidence" in data, f"Missing confidence: {data}"
        assert "risk" in data, f"Missing risk: {data}"
    finally:
        os.unlink(path)


check("CLI decision plan → structured DecisionPlan", test_cli_decision_plan)


def test_cli_agent_run_lifecycle():
    payload = {
        "task": f"Search the latest benchmark notes {time.time_ns()}",
        "tools": ["search"],
        "approval_mode": "manual",
    }
    path = write_temp_json(payload)
    try:
        created = run_cli("agent-runs", "create", path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(created)
        assert created.returncode == 0, (
            f"Expected exit 0, got {created.returncode}: stderr={created.stderr[:400]}"
        )
        create_data = json.loads(created.stdout.strip())
        run_id = create_data["run_id"]
        assert create_data["status"] == "requires_approval"

        fetched = run_cli("agent-runs", "get", run_id, "--format", "json")
        assert fetched.returncode == 0, (
            f"Expected exit 0, got {fetched.returncode}: stderr={fetched.stderr[:300]}"
        )
        fetched_data = json.loads(fetched.stdout.strip())
        assert fetched_data["run_id"] == run_id
        assert fetched_data["status"] == "requires_approval"

        events = run_cli("agent-runs", "events", run_id, "--limit", "20", "--format", "json")
        assert events.returncode == 0, (
            f"Expected exit 0, got {events.returncode}: stderr={events.stderr[:300]}"
        )
        events_data = json.loads(events.stdout.strip())
        assert events_data["run_id"] == run_id
        assert events_data["total_events"] >= 3

        approved = run_cli("agent-runs", "approve", run_id, "--format", "json")
        assert approved.returncode == 0, (
            f"Expected exit 0, got {approved.returncode}: stderr={approved.stderr[:300]}"
        )
        approved_data = json.loads(approved.stdout.strip())
        assert approved_data["run_id"] == run_id
        assert approved_data["status"] == "completed"
        assert "search" in approved_data.get("tools_used", [])
    finally:
        os.unlink(path)


check("CLI agent-runs lifecycle → create/get/events/approve", test_cli_agent_run_lifecycle)


def test_cli_agent_run_event_stream():
    payload = {
        "task": f"Search the latest benchmark notes {time.time_ns()}",
        "tools": ["search"],
        "approval_mode": "manual",
    }
    path = write_temp_json(payload)
    try:
        created = run_cli("agent-runs", "create", path, "--format", "json")
        ensure_cli_simulation_not_capacity_blocked(created)
        assert created.returncode == 0, (
            f"Expected exit 0, got {created.returncode}: stderr={created.stderr[:400]}"
        )
        run_id = json.loads(created.stdout.strip())["run_id"]

        approved = run_cli("agent-runs", "approve", run_id, "--format", "json")
        assert approved.returncode == 0, (
            f"Expected exit 0, got {approved.returncode}: stderr={approved.stderr[:300]}"
        )
        approved_data = json.loads(approved.stdout.strip())
        assert approved_data["run_id"] == run_id
        assert approved_data["status"] == "completed"

        streamed = run_cli(
            "agent-runs",
            "events",
            run_id,
            "--limit",
            "20",
            "--stream",
            "--format",
            "json",
        )
        assert streamed.returncode == 0, (
            f"Expected exit 0, got {streamed.returncode}: stderr={streamed.stderr[:300]}"
        )
        events = parse_json_lines(streamed.stdout)
        assert any(event["type"] == "agent.run.event" for event in events)
        completed = events[-1]
        assert completed["type"] == "agent.run.completed"
        assert completed["run_id"] == run_id
        assert completed["status"] == "completed"

        streamed_table = run_cli(
            "agent-runs",
            "events",
            run_id,
            "--limit",
            "20",
            "--stream",
        )
        assert streamed_table.returncode == 0, (
            f"Expected exit 0, got {streamed_table.returncode}: stderr={streamed_table.stderr[:300]}"
        )
        assert "Run completed:" in streamed_table.stdout
    finally:
        os.unlink(path)


check("CLI agent-runs event stream → SSE JSON lines", test_cli_agent_run_event_stream)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: CLI — Keys & Metadata Commands
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 5: CLI — Keys & Metadata Commands")
print("=" * 70)


def test_cli_keys_list():
    result = run_cli("keys", "list")
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}: {result.stderr[:300]}"
    )
    output = result.stdout
    assert "key" in output.lower() or "api" in output.lower() or "de_live" in output, (
        f"Expected key info in output: {output[:300]}"
    )


check("CLI keys list → key info", test_cli_keys_list)


def test_cli_account_surface():
    me = run_cli("account", "me", "--format", "json")
    assert me.returncode == 0, f"Expected exit 0, got {me.returncode}: {me.stderr[:300]}"
    me_payload = json.loads(me.stdout.strip())
    assert any(key in me_payload for key in ("org_id", "organization", "email", "user", "org")), me_payload

    usage = run_cli("account", "usage", "--format", "json")
    assert usage.returncode == 0, (
        f"Expected exit 0, got {usage.returncode}: {usage.stderr[:300]}"
    )
    usage_payload = json.loads(usage.stdout.strip())
    assert "billing_period" in usage_payload
    assert "quota_limit" in usage_payload

    limits = run_cli("account", "limits", "--format", "json")
    assert limits.returncode == 0, (
        f"Expected exit 0, got {limits.returncode}: {limits.stderr[:300]}"
    )
    limits_payload = json.loads(limits.stdout.strip())
    assert any(key in limits_payload for key in ("plan", "simulations_per_month", "rate_limit_per_minute"))

    distributions = run_cli("account", "distributions", "--format", "json")
    assert distributions.returncode == 0, (
        f"Expected exit 0, got {distributions.returncode}: {distributions.stderr[:300]}"
    )
    distributions_payload = json.loads(distributions.stdout.strip())
    listed_distributions = (
        distributions_payload
        if isinstance(distributions_payload, list)
        else distributions_payload.get("distributions", [])
    )
    assert isinstance(listed_distributions, list), distributions_payload
    assert listed_distributions, distributions_payload

    templates = run_cli("account", "templates", "--format", "json")
    assert templates.returncode == 0, (
        f"Expected exit 0, got {templates.returncode}: {templates.stderr[:300]}"
    )
    templates_payload = json.loads(templates.stdout.strip())
    listed_templates = (
        templates_payload
        if isinstance(templates_payload, list)
        else templates_payload.get("templates", [])
    )
    assert isinstance(listed_templates, list), templates_payload
    assert listed_templates, templates_payload

    billing = run_cli("billing", "info", "--format", "json")
    assert billing.returncode == 0, (
        f"Expected exit 0, got {billing.returncode}: {billing.stderr[:300]}"
    )
    billing_payload = json.loads(billing.stdout.strip())
    assert billing_payload["plan"]


check("CLI account surface → me/usage/limits/distributions/templates/billing", test_cli_account_surface)


def test_cli_team_surface():
    team = run_cli("team", "list", "--format", "json")
    assert team.returncode == 0, (
        f"Expected exit 0, got {team.returncode}: {team.stderr[:300]}"
    )
    team_payload = json.loads(team.stdout.strip())
    members = team_payload if isinstance(team_payload, list) else team_payload.get("members", [])
    assert members, team_payload
    assert members[0]["email"]
    assert members[0]["role"]


check("CLI team surface → members list", test_cli_team_surface)


def test_cli_job_list_surface():
    jobs = run_cli("job", "list", "--page", "1", "--limit", "5", "--status", "queued", "--format", "json")
    assert jobs.returncode == 0, (
        f"Expected exit 0, got {jobs.returncode}: {jobs.stderr[:300]}"
    )
    payload = json.loads(jobs.stdout.strip())
    assert isinstance(payload, dict), payload
    assert payload["page"] == 1
    assert payload["limit"] == 5
    assert payload["total"] >= len(payload["jobs"])
    assert payload["pages"] >= 1
    for item in payload["jobs"]:
        assert item["status"] == "queued"
        assert item["queue_name"]


check("CLI job surface → paginated queued job list", test_cli_job_list_surface)


def test_cli_job_result_missing_job():
    result = run_cli("job", "result", "00000000-0000-0000-0000-000000000001", "--format", "json")
    assert result.returncode != 0, "Expected non-zero exit for missing job result"
    combined = ((result.stderr or "") + "\n" + (result.stdout or "")).lower()
    assert "404" in combined or "not found" in combined, combined[:300]


check("CLI job result surface → structured missing-job error", test_cli_job_result_missing_job)


def test_cli_job_cancel_missing_job():
    result = run_cli("job", "cancel", "00000000-0000-0000-0000-000000000001", "--format", "json")
    assert result.returncode != 0, "Expected non-zero exit for missing job cancel"
    combined = ((result.stderr or "") + "\n" + (result.stdout or "")).lower()
    assert "404" in combined or "not found" in combined, combined[:300]


check("CLI job cancel surface → structured missing-job error", test_cli_job_cancel_missing_job)


def test_cli_trigger_surface():
    path = write_temp_json(build_live_trigger_request(f"cli-trigger-{time.time_ns()}"))
    trigger_id = None
    try:
        created = run_cli("triggers", "register", path, "--format", "json")
        assert created.returncode == 0, (
            f"Expected exit 0, got {created.returncode}: {created.stderr[:300]}"
        )
        created_payload = json.loads(created.stdout.strip())
        trigger_id = created_payload["trigger_id"]
        assert created_payload["status"] == "active"

        listed = run_cli(
            "triggers",
            "list",
            "--status",
            "all",
            "--page",
            "1",
            "--limit",
            "25",
            "--format",
            "json",
        )
        assert listed.returncode == 0, (
            f"Expected exit 0, got {listed.returncode}: {listed.stderr[:300]}"
        )
        listed_payload = json.loads(listed.stdout.strip())
        assert listed_payload["page"] == 1
        assert listed_payload["limit"] == 25
        assert listed_payload["total"] >= len(listed_payload["triggers"])
        assert any(item["trigger_id"] == trigger_id for item in listed_payload["triggers"])

        fired = run_cli("triggers", "fire", trigger_id, "--format", "json")
        assert fired.returncode == 0, (
            f"Expected exit 0, got {fired.returncode}: {fired.stderr[:300]}"
        )
        fired_payload = json.loads(fired.stdout.strip())
        assert fired_payload["trigger_id"] == trigger_id
        assert fired_payload["condition_met"] is False
        assert fired_payload["fired"] is False

        paused = run_cli("triggers", "pause", trigger_id, "--format", "json")
        assert paused.returncode == 0, (
            f"Expected exit 0, got {paused.returncode}: {paused.stderr[:300]}"
        )
        assert json.loads(paused.stdout.strip())["status"] == "paused"

        resumed = run_cli("triggers", "resume", trigger_id, "--format", "json")
        assert resumed.returncode == 0, (
            f"Expected exit 0, got {resumed.returncode}: {resumed.stderr[:300]}"
        )
        assert json.loads(resumed.stdout.strip())["status"] == "active"
    finally:
        os.unlink(path)
        if trigger_id is not None:
            deleted = run_cli("triggers", "delete", trigger_id, "--format", "json")
            assert deleted.returncode == 0, (
                f"Expected exit 0, got {deleted.returncode}: {deleted.stderr[:300]}"
            )
            deleted_payload = json.loads(deleted.stdout.strip())
            assert deleted_payload == {"trigger_id": trigger_id, "deleted": True}


check("CLI trigger lifecycle surface → register/list/fire/pause/resume/delete", test_cli_trigger_surface)


def test_cli_devices_surface():
    devices = run_cli("devices", "list", "--format", "json")
    assert devices.returncode == 0, (
        f"Expected exit 0, got {devices.returncode}: {devices.stderr[:300]}"
    )
    payload = json.loads(devices.stdout.strip())
    assert isinstance(payload, dict), payload
    listed = payload.get("devices", [])
    assert isinstance(listed, list), payload
    assert "device_count" in payload
    assert "device_limit" in payload
    assert "plan" in payload
    if listed:
        assert listed[0]["device_id"]
        assert listed[0]["status"]


check("CLI devices surface → registered device list", test_cli_devices_surface)


def test_cli_data_surface():
    dataset_id: str | None = None
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        payload = build_live_dataset_payload("cli-refreshable-dataset", source_url)
        path = write_temp_json(payload)
        try:
            connected = run_cli("data", "connect", "--request", path, "--format", "json")
            assert connected.returncode == 0, (
                f"Expected exit 0, got {connected.returncode}: {connected.stderr[:300]}"
            )
            connected_payload = json.loads(connected.stdout.strip())
            assert connected_payload["status"] == "ready"
            dataset_id = connected_payload["dataset_id"]
            dataset_name = connected_payload["dataset_name"]
            assert dataset_id
            assert dataset_name

            listed = run_cli(
                "data", "list", "--search", dataset_name, "--compact", "--format", "json"
            )
            assert listed.returncode == 0, (
                f"Expected exit 0, got {listed.returncode}: {listed.stderr[:300]}"
            )
            listed_payload = json.loads(listed.stdout.strip())
            datasets = listed_payload.get("datasets", [])
            assert listed_payload["total"] >= len(datasets)
            assert any(item["dataset_id"] == dataset_id for item in datasets)

            refreshed = run_cli("data", "refresh", dataset_id, "--format", "json")
            assert refreshed.returncode == 0, (
                f"Expected exit 0, got {refreshed.returncode}: {refreshed.stderr[:300]}"
            )
            refreshed_payload = json.loads(refreshed.stdout.strip())
            assert refreshed_payload["dataset_id"] == dataset_id
            assert refreshed_payload["status"] == "ready"

            summary = run_cli("data", "summary", dataset_id, "--format", "json")
            assert summary.returncode == 0, (
                f"Expected exit 0, got {summary.returncode}: {summary.stderr[:300]}"
            )
            summary_payload = json.loads(summary.stdout.strip())
            assert summary_payload["dataset_id"] == dataset_id
            assert summary_payload["name"] == dataset_name
            assert summary_payload["column_count"] >= 2

            detail = run_cli("data", "inspect", dataset_id, "--format", "json")
            assert detail.returncode == 0, (
                f"Expected exit 0, got {detail.returncode}: {detail.stderr[:300]}"
            )
            detail_payload = json.loads(detail.stdout.strip())
            assert detail_payload["dataset"]["dataset_id"] == dataset_id
            assert detail_payload["dataset"]["dataset_name"] == dataset_name
            assert len(detail_payload["schema"].get("columns", [])) >= 2
        finally:
            os.unlink(path)
            if dataset_id is not None:
                deleted = run_cli("data", "disconnect", dataset_id, "--yes", "--format", "json")
                assert deleted.returncode == 0, (
                    f"Expected exit 0, got {deleted.returncode}: {deleted.stderr[:300]}"
                )
                deleted_payload = json.loads(deleted.stdout.strip())
                assert deleted_payload["dataset_id"] == dataset_id
                assert deleted_payload["status"] == "deleted"


check("CLI data surface → connect/list/refresh/summary/inspect/disconnect", test_cli_data_surface)


def test_cli_connector_surface():
    connector_id: str | None = None
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        payload = build_live_connector_payload("cli-live-connector", source_url)
        preview_payload = {
            "connector_type": "rest",
            "config": {"url": source_url, "data_path": "items"},
        }
        path = write_temp_json(payload)
        preview_path = write_temp_json(preview_payload)
        try:
            preview_test = run_cli("connectors", "preview-test", preview_path, "--format", "json")
            assert preview_test.returncode == 0, (
                f"Expected exit 0, got {preview_test.returncode}: {preview_test.stderr[:300]}"
            )
            preview_test_payload = json.loads(preview_test.stdout.strip())
            assert preview_test_payload["success"] is True
            assert preview_test_payload["status"] == "live"

            preview_browse = run_cli("connectors", "preview-browse", preview_path, "--format", "json")
            assert preview_browse.returncode == 0, (
                f"Expected exit 0, got {preview_browse.returncode}: {preview_browse.stderr[:300]}"
            )
            preview_browse_payload = json.loads(preview_browse.stdout.strip())
            assert preview_browse_payload["connector_type"] == "rest"
            assert preview_browse_payload["total"] >= 1

            created = run_cli("connectors", "create", path, "--format", "json")
            assert created.returncode == 0, (
                f"Expected exit 0, got {created.returncode}: {created.stderr[:300]}"
            )
            created_payload = json.loads(created.stdout.strip())
            connector_id = created_payload["id"]
            connector_name = created_payload["name"]
            assert connector_id
            assert connector_name

            listed = run_cli("connectors", "list", "--page", "1", "--limit", "25", "--format", "json")
            assert listed.returncode == 0, (
                f"Expected exit 0, got {listed.returncode}: {listed.stderr[:300]}"
            )
            listed_payload = json.loads(listed.stdout.strip())
            assert listed_payload["total"] >= len(listed_payload["connectors"])
            assert any(item["id"] == connector_id for item in listed_payload["connectors"])

            detail = run_cli("connectors", "get", connector_id, "--format", "json")
            assert detail.returncode == 0, (
                f"Expected exit 0, got {detail.returncode}: {detail.stderr[:300]}"
            )
            detail_payload = json.loads(detail.stdout.strip())
            assert detail_payload["id"] == connector_id
            assert detail_payload["name"] == connector_name

            update_path = write_temp_json({"description": "Live CLI connector updated description."})
            try:
                updated = run_cli("connectors", "update", connector_id, update_path, "--format", "json")
                assert updated.returncode == 0, (
                    f"Expected exit 0, got {updated.returncode}: {updated.stderr[:300]}"
                )
                updated_payload = json.loads(updated.stdout.strip())
                assert updated_payload["id"] == connector_id
                assert updated_payload["description"] == "Live CLI connector updated description."
            finally:
                os.unlink(update_path)

            tested = run_cli("connectors", "test", connector_id, "--format", "json")
            assert tested.returncode == 0, (
                f"Expected exit 0, got {tested.returncode}: {tested.stderr[:300]}"
            )
            tested_payload = json.loads(tested.stdout.strip())
            assert tested_payload["success"] is True
            assert tested_payload["status"] == "live"

            browsed = run_cli("connectors", "browse", connector_id, "--format", "json")
            assert browsed.returncode == 0, (
                f"Expected exit 0, got {browsed.returncode}: {browsed.stderr[:300]}"
            )
            browsed_payload = json.loads(browsed.stdout.strip())
            assert browsed_payload["connector_type"] == "rest"
            assert browsed_payload["total"] >= 1
        finally:
            os.unlink(path)
            os.unlink(preview_path)
            if connector_id is not None:
                deleted = run_cli("connectors", "delete", connector_id, "--format", "json")
                assert deleted.returncode == 0, (
                    f"Expected exit 0, got {deleted.returncode}: {deleted.stderr[:300]}"
                )
                deleted_payload = json.loads(deleted.stdout.strip())
                assert deleted_payload == {"connector_id": connector_id, "deleted": True}


check(
    "CLI connectors surface → create/list/get/update/test/browse/delete",
    test_cli_connector_surface,
)


def test_cli_repository_surface():
    reason = local_repository_live_support_reason(BASE_URL)
    if reason is not None:
        raise EnvironmentBlocked(reason)

    connector_id: str | None = None
    temp_paths: list[str] = []
    with live_repository_fixture("cli") as repository_fixture:
        capabilities = run_cli("repositories", "capabilities", "--format", "json")
        assert capabilities.returncode == 0, (
            f"Expected exit 0, got {capabilities.returncode}: {capabilities.stderr[:300]}"
        )
        assert_repository_intelligence_capabilities_payload(
            json.loads(capabilities.stdout.strip())
        )
        connector_path = write_temp_json(repository_fixture.connector_request)
        temp_paths.append(connector_path)
        try:
            created = run_cli("connectors", "create", connector_path, "--format", "json")
            assert created.returncode == 0, (
                f"Expected exit 0, got {created.returncode}: {created.stderr[:300]}"
            )
            created_payload = json.loads(created.stdout.strip())
            connector_id = created_payload["id"]
            assert created_payload["connector_type"] == "local_repo"

            snapshot_path = write_temp_json(repository_fixture.snapshot_request)
            temp_paths.append(snapshot_path)
            snapshot = run_cli(
                "repositories",
                "snapshot",
                connector_id,
                snapshot_path,
                "--format",
                "json",
            )
            assert snapshot.returncode == 0, (
                f"Expected exit 0, got {snapshot.returncode}: {snapshot.stderr[:300]}"
            )
            snapshot_payload = json.loads(snapshot.stdout.strip())
            snapshot_id = snapshot_payload["snapshot_id"]
            assert snapshot_payload["connector_type"] == "local_repo"
            assert snapshot_payload["file_count"] >= 2

            fetched_snapshot = run_cli(
                "repositories",
                "get-snapshot",
                connector_id,
                snapshot_id,
                "--format",
                "json",
            )
            assert fetched_snapshot.returncode == 0, (
                f"Expected exit 0, got {fetched_snapshot.returncode}: {fetched_snapshot.stderr[:300]}"
            )
            fetched_snapshot_payload = json.loads(fetched_snapshot.stdout.strip())
            assert fetched_snapshot_payload["snapshot_id"] == snapshot_id
            assert fetched_snapshot_payload["content_hash"] == snapshot_payload["content_hash"]

            repeated_snapshot = run_cli(
                "repositories",
                "snapshot",
                connector_id,
                snapshot_path,
                "--format",
                "json",
            )
            assert repeated_snapshot.returncode == 0, (
                f"Expected exit 0, got {repeated_snapshot.returncode}: {repeated_snapshot.stderr[:300]}"
            )
            repeated_snapshot_payload = json.loads(repeated_snapshot.stdout.strip())
            assert repeated_snapshot_payload["snapshot_id"] == snapshot_id
            assert repeated_snapshot_payload["status"] == "existing"

            triage_path = write_temp_json(repository_fixture.triage_request(snapshot_id))
            temp_paths.append(triage_path)
            triage = run_cli(
                "repositories",
                "triage",
                connector_id,
                triage_path,
                "--format",
                "json",
            )
            assert triage.returncode == 0, (
                f"Expected exit 0, got {triage.returncode}: {triage.stderr[:300]}"
            )
            triage_payload = json.loads(triage.stdout.strip())
            assert triage_payload["workspace_evidence_bundle_ref"]
            assert triage_payload["reduction_ratio"] >= 1.0
            assert triage_payload["evidence_items"]
            assert triage_payload["suspect_files"][0] == repository_fixture.primary_file
            assert (
                triage_payload["workspace_evidence_bundle_artifact"]["artifact_kind"]
                == "WorkspaceEvidenceBundle"
            )

            graph_path = write_temp_json(
                repository_fixture.graph_query_request(
                    snapshot_id,
                    triage_payload["workspace_evidence_bundle_ref"],
                )
            )
            temp_paths.append(graph_path)
            graph = run_cli(
                "repositories",
                "graph-query",
                connector_id,
                graph_path,
                "--format",
                "json",
            )
            assert graph.returncode == 0, (
                f"Expected exit 0, got {graph.returncode}: {graph.stderr[:300]}"
            )
            graph_payload = json.loads(graph.stdout.strip())
            assert graph_payload["snapshot_id"] == snapshot_id
            assert repository_fixture.primary_file in graph_payload["seed_file_paths"]
            assert repository_fixture.primary_file in graph_payload["impacted_files"]
            assert graph_payload["graph_nodes"]
            assert graph_payload["top_change_risk_files"]

            plan_path = write_temp_json(
                repository_fixture.decision_plan_request(
                    snapshot_id,
                    triage_payload["workspace_evidence_bundle_ref"],
                )
            )
            temp_paths.append(plan_path)
            plan = run_cli(
                "repositories",
                "decision-plan",
                connector_id,
                plan_path,
                "--format",
                "json",
            )
            if plan.returncode != 0:
                _assert_cli_repository_error(plan, error_code="repository_model_unavailable")
                return

            plan_payload = json.loads(plan.stdout.strip())
            decision_plan_id = plan_payload["decision_plan_id"]
            repository_analysis = plan_payload["decision_plan"]["repository_analysis"]
            assert repository_analysis["planner_model_id"] == "repository.deterministic_local_v1"
            assert repository_analysis["planner_execution_mode"] == "deterministic_local"
            assert repository_analysis["planner_provider_backend"] is None
            assert repository_analysis["generated_patch_ref"]
            assert repository_analysis["patch_impact_report_ref"]
            assert repository_analysis["token_reduction_metrics"]["reduction_ratio"] >= 1.0

            simulation_path = write_temp_json(
                repository_fixture.simulation_request(snapshot_id, decision_plan_id)
            )
            temp_paths.append(simulation_path)
            simulation = run_cli(
                "repositories",
                "simulate",
                connector_id,
                simulation_path,
                "--format",
                "json",
            )
            ensure_cli_simulation_not_capacity_blocked(simulation)
            assert simulation.returncode == 0, (
                f"Expected exit 0, got {simulation.returncode}: {simulation.stderr[:300]}"
            )
            simulation_payload = json.loads(simulation.stdout.strip())
            simulation_id = simulation_payload["validated_inputs"]["simulation_id"]
            apply_gate = simulation_payload["score_breakdown"]["apply_gate"]
            assert simulation_id
            assert apply_gate["policy_snapshot_id"]

            branch_name = "algenta/live-repository-fix"
            apply_path = write_temp_json(
                repository_fixture.apply_local_branch_request(
                    snapshot_id,
                    decision_plan_id,
                    simulation_id,
                    branch_name=branch_name,
                )
            )
            temp_paths.append(apply_path)
            apply = run_cli(
                "repositories",
                "apply",
                connector_id,
                apply_path,
                "--format",
                "json",
            )
            if apply_gate["passed"]:
                assert apply.returncode == 0, (
                    f"Expected exit 0, got {apply.returncode}: {apply.stderr[:300]}"
                )
                apply_payload = json.loads(apply.stdout.strip())
                assert apply_payload["mode"] == "local_branch"
                assert apply_payload["applied"] is True
                assert apply_payload["patch"]
                assert apply_payload["branch_name"] == branch_name
                assert apply_payload["commit_sha"]
                assert apply_payload["local_checkout_path"]
                repository_fixture.assert_local_branch_applied(
                    branch_name=branch_name,
                    checkout_path=apply_payload["local_checkout_path"],
                )
                assert repository_fixture.primary_file in apply_payload["validation_summary"][
                    "patch_files"
                ]
            else:
                assert apply.returncode != 0, "Expected repository apply to fail closed."
                _assert_cli_repository_error(apply, error_code="repository_apply_gate_failed")
        finally:
            for path in temp_paths:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(path)
            if connector_id is not None:
                deleted = run_cli("connectors", "delete", connector_id, "--format", "json")
                assert deleted.returncode == 0, (
                    f"Expected exit 0, got {deleted.returncode}: {deleted.stderr[:300]}"
                )
                deleted_payload = json.loads(deleted.stdout.strip())
                assert deleted_payload == {"connector_id": connector_id, "deleted": True}


check(
    "CLI repository intelligence surface → snapshot/triage/graph/plan/simulate/apply",
    test_cli_repository_surface,
)


def test_cli_metering_surface():
    payload = {
        "device_id": f"cli-live-{time.time_ns()}",
        "events": [
            {
                "event_type": "runtime_call",
                "module": "integration",
                "function": "cli_live",
                "engine_used": "python",
                "latency_ms": 11.0,
                "success": True,
            }
        ],
    }
    path = write_temp_json(payload)
    try:
        metering = run_cli("metering", "ingest", path, "--format", "json")
        assert metering.returncode == 0, (
            f"Expected exit 0, got {metering.returncode}: {metering.stderr[:300]}"
        )
        metering_payload = json.loads(metering.stdout.strip())
        assert metering_payload["accepted"] == 1
        assert metering_payload["billing_period"]
    finally:
        os.unlink(path)


check("CLI metering surface → accepted event batch", test_cli_metering_surface)


def test_cli_credit_refresh_surface():
    payload = {
        "device_id": f"cli-credit-live-{time.time_ns()}",
        "billing_period": time.strftime("%Y-%m", time.gmtime()),
        "credits_used": 0,
    }
    path = write_temp_json(payload)
    try:
        refreshed = run_cli("credits", "refresh", path, "--format", "json")
        ensure_cli_credit_refresh_not_blocked(refreshed)
        assert refreshed.returncode == 0, (
            f"Expected exit 0, got {refreshed.returncode}: {refreshed.stderr[:300]}"
        )
        refreshed_payload = json.loads(refreshed.stdout.strip())
        assert refreshed_payload["billing_period"] == payload["billing_period"]
        assert refreshed_payload["credits_granted"] >= 0
        assert refreshed_payload["credits_issued_this_month"] >= refreshed_payload["credits_granted"]
        assert refreshed_payload["monthly_limit"] >= 0
        assert refreshed_payload["monthly_remaining"] >= 0
        assert refreshed_payload["refresh_after"] >= refreshed_payload["server_time"]
        assert refreshed_payload["expires_at"] >= refreshed_payload["refresh_after"]
    finally:
        os.unlink(path)


check("CLI credits surface → refresh execution credits", test_cli_credit_refresh_surface)


def test_cli_webhook_test_surface():
    with webhook_receiver() as (callback_url, deliveries):
        webhook = run_cli("webhook", "test", callback_url, "--format", "json")
        assert webhook.returncode == 0, (
            f"Expected exit 0, got {webhook.returncode}: {webhook.stderr[:300]}"
        )
        payload = json.loads(webhook.stdout.strip())
        assert payload["success"] is True, payload
        assert int(payload["status_code"]) == 200, payload
        assert deliveries, "Expected one webhook delivery to local receiver"
        assert deliveries[0]["path"] == "/webhook", deliveries[0]


check("CLI webhook surface → test delivery", test_cli_webhook_test_surface)


def test_cli_audit_logs_surface():
    logs = run_cli("team", "audit-logs", "--format", "json")
    if logs.returncode != 0:
        combined = ((logs.stderr or "") + "\n" + (logs.stdout or "")).strip()
        payload = parse_cli_error_payload(combined)
        normalized = combined.lower()
        if payload and (
            "insufficient_role" in normalized
            or "required_role" in normalized
            or "access_scope_denied" in normalized
        ):
            raise EnvironmentBlocked("audit log access requires admin role")
        assert logs.returncode == 0, f"Expected exit 0, got {logs.returncode}: {combined[:300]}"
    logs_payload = json.loads(logs.stdout.strip())
    entries = logs_payload.get("entries", []) if isinstance(logs_payload, dict) else []
    assert isinstance(entries, list), logs_payload
    if entries:
        assert entries[0]["action"]


def test_cli_audit_artifacts_surface():
    logs = run_cli("team", "audit-artifacts", "--format", "json")
    if logs.returncode != 0:
        combined = ((logs.stderr or "") + "\n" + (logs.stdout or "")).strip()
        payload = parse_cli_error_payload(combined)
        normalized = combined.lower()
        if payload and (
            "insufficient_role" in normalized
            or "required_role" in normalized
            or "access_scope_denied" in normalized
        ):
            raise EnvironmentBlocked("audit artifact access requires admin role")
        assert logs.returncode == 0, f"Expected exit 0, got {logs.returncode}: {combined[:300]}"
    logs_payload = json.loads(logs.stdout.strip())
    entries = logs_payload.get("entries", []) if isinstance(logs_payload, dict) else []
    assert isinstance(entries, list), logs_payload
    if entries:
        assert "content_hash" in entries[0]
        assert entries[0]["result"]


check("CLI audit logs surface → paginated entries", test_cli_audit_logs_surface)


def test_cli_execution_policy_surface():
    policy = run_cli("execution-policy", "get", "--format", "json")
    assert policy.returncode == 0, (
        f"Expected exit 0, got {policy.returncode}: {policy.stderr[:300]}"
    )
    policy_payload = json.loads(policy.stdout.strip())
    assert "min_confidence" in policy_payload
    assert "require_calibration" in policy_payload
    assert "allow_reexecution" in policy_payload

    snapshots = run_cli("execution-policy", "snapshots", "--format", "json")
    assert snapshots.returncode == 0, (
        f"Expected exit 0, got {snapshots.returncode}: {snapshots.stderr[:300]}"
    )
    snapshots_payload = json.loads(snapshots.stdout.strip())
    entries = snapshots_payload.get("data", []) if isinstance(snapshots_payload, dict) else []
    assert isinstance(entries, list), snapshots_payload
    assert snapshots_payload.get("total_snapshots", len(entries)) >= len(entries)
    if entries:
        assert entries[0]["snapshot_id"]
        assert "revision" in entries[0]


check("CLI execution policy surface → current thresholds + snapshots", test_cli_execution_policy_surface)


def test_cli_deployment_surface():
    regions = run_cli("deployments", "regions", "--format", "json")
    assert regions.returncode == 0, (
        f"Expected exit 0, got {regions.returncode}: {regions.stderr[:300]}"
    )
    regions_payload = json.loads(regions.stdout.strip())
    providers = regions_payload.get("providers", [])
    managed = next((item for item in providers if item.get("id") == "algenta_shared"), None)
    assert managed is not None, regions_payload
    assert managed.get("regions"), managed

    current = run_cli("deployments", "get", "--format", "json")
    assert current.returncode == 0, (
        f"Expected exit 0, got {current.returncode}: {current.stderr[:300]}"
    )
    current_payload = json.loads(current.stdout.strip())
    if current_payload is None:
        return

    assert current_payload["deployment_id"]
    assert current_payload["provider"]

    cost = run_cli("deployments", "cost", current_payload["deployment_id"], "--format", "json")
    assert cost.returncode == 0, (
        f"Expected exit 0, got {cost.returncode}: {cost.stderr[:300]}"
    )
    cost_payload = json.loads(cost.stdout.strip())
    assert cost_payload["deployment_id"] == current_payload["deployment_id"]
    assert float(cost_payload["cost_usd_month"]) >= 0


check("CLI deployment surface → regions/current/cost", test_cli_deployment_surface)


def test_cli_key_lifecycle():
    anchor_label = f"cli-live-key-anchor-{time.time_ns()}"
    label = f"cli-live-key-{time.time_ns()}"
    anchor_created = run_cli("keys", "create", anchor_label, "--format", "json")
    assert anchor_created.returncode == 0, (
        f"Expected exit 0, got {anchor_created.returncode}: {anchor_created.stderr[:300]}"
    )
    anchor_payload = json.loads(anchor_created.stdout.strip())
    anchor_key_id = anchor_payload["id"]
    created = run_cli("keys", "create", label, "--device-limit", "2", "--format", "json")
    requested_device_limit = 2
    if created.returncode != 0:
        combined = ((created.stderr or "") + "\n" + (created.stdout or "")).strip()
        payload = parse_cli_error_payload(combined)
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict) and error.get("code") == "invalid_device_limit":
            created = run_cli("keys", "create", label, "--format", "json")
            requested_device_limit = 0
    assert created.returncode == 0, (
        f"Expected exit 0, got {created.returncode}: {created.stderr[:300]}"
    )
    created_payload = json.loads(created.stdout.strip())
    assert created_payload["label"] == label
    assert created_payload["device_limit"] == requested_device_limit
    assert created_payload["raw_key"].startswith(created_payload["key_prefix"])

    key_id = created_payload["id"]
    try:
        listed = run_cli("keys", "list", "--format", "json")
        assert listed.returncode == 0, (
            f"Expected exit 0, got {listed.returncode}: {listed.stderr[:300]}"
        )
        listed_payload = json.loads(listed.stdout.strip())
        items = listed_payload if isinstance(listed_payload, list) else listed_payload.get("api_keys", [])
        created_entry = next((item for item in items if str(item.get("id")) == str(key_id)), None)
        assert created_entry is not None
        assert created_entry["label"] == label
        assert created_entry["device_limit"] == requested_device_limit
        assert "raw_key" not in created_entry

        revoked = run_cli("keys", "revoke", str(key_id), "--format", "json")
        assert revoked.returncode == 0, (
            f"Expected exit 0, got {revoked.returncode}: {revoked.stderr[:300]}"
        )
        revoked_payload = json.loads(revoked.stdout.strip())
        assert revoked_payload == {}

        listed_after = run_cli("keys", "list", "--format", "json")
        assert listed_after.returncode == 0, (
            f"Expected exit 0, got {listed_after.returncode}: {listed_after.stderr[:300]}"
        )
        listed_after_payload = json.loads(listed_after.stdout.strip())
        after_items = (
            listed_after_payload
            if isinstance(listed_after_payload, list)
            else listed_after_payload.get("api_keys", [])
        )
        assert all(str(item.get("id")) != str(key_id) for item in after_items)
    finally:
        run_cli("keys", "revoke", str(key_id), "--format", "json")
        run_cli("keys", "revoke", str(anchor_key_id), "--format", "json")


check("CLI keys create/revoke → API-key lifecycle", test_cli_key_lifecycle)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULTS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  RESULTS SUMMARY — CLI Integration Tests")
print("=" * 70)

passed = sum(1 for r in results if r[0] == PASS)
skipped = sum(1 for r in results if r[0] == SKIP)
failed = sum(1 for r in results if r[0] == FAIL)
total = len(results)

print(f"\n  Total:  {total} tests")
print(f"  Passed: {passed} {PASS}")
print(f"  Skipped: {skipped} {SKIP}")
print(f"  Failed: {failed} {FAIL}")

if failed > 0:
    print("\n  ── Failures ──")
    for r in results:
        if r[0] == FAIL:
            print(f"    {FAIL} {r[1]}: {r[2] if len(r) > 2 else ''}")
if skipped > 0:
    print("\n  ── Skipped ──")
    for r in results:
        if r[0] == SKIP:
            print(f"    {SKIP} {r[1]}: {r[2] if len(r) > 2 else ''}")

print(f"\n{'=' * 70}")
if failed == 0:
    if skipped > 0:
        skipped_reasons = [str(r[2]) for r in results if r[0] == SKIP and len(r) > 2]
        skip_summary = "live environment constraints"
        if skipped_reasons and all("capacity" in reason.lower() for reason in skipped_reasons):
            skip_summary = "live capacity limits"
        print(f"  ✅ {passed} CLI tests passed; {skipped} skipped due to {skip_summary}")
    else:
        print(f"  🎉 ALL {passed} CLI TESTS PASSED!")
else:
    print(f"  ⚠️  {failed}/{total} FAILURES")
print(f"{'=' * 70}\n")

artifact_path = write_live_integration_summary(
    SUITE_NAME,
    script="tests/integration/test_cli.py",
    passed=passed,
    failed=failed,
    skipped=skipped,
    total=total,
    elapsed_seconds=time.perf_counter() - STARTED,
    details={
        "api_key_configured": API_KEY_CONFIGURED,
        "base_url": BASE_URL,
        "failed_checks": [result[1] for result in results if result[0] == FAIL],
        "skipped_checks": [result[1] for result in results if result[0] == SKIP],
        "skipped_count": skipped,
    },
)
print(f"Summary artifact: {artifact_path}")

sys.exit(1 if failed > 0 else 0)
