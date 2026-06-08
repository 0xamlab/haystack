"""
Python SDK integration tests — tests the decision_engine SDK against a live server.

Prerequisites:
  1. API server running on localhost:8000
  2. PostgreSQL + Redis running
  3. Dev data seeded

Run:
  DE_API_KEY="..." python3 tests/integration/test_python_sdk.py
"""

if __name__ != "__main__":
    import pytest

    pytest.skip(
        "Standalone integration script; run via python tests/integration/test_python_sdk.py",
        allow_module_level=True,
    )

import asyncio
import atexit
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

ROOT = Path(__file__).resolve().parents[2]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ROOT), str(PYTHON_SDK)):
    if path not in sys.path:
        sys.path.insert(0, path)

# ruff: noqa: E402
from decision_engine import (  # noqa: E402
    AsyncDecisionEngineClient,
    AuthenticationError,
    DecisionEngineClient,
    DecisionEngineError,
    DecisionEnvelope,
    ValidationError,
)

from apps.platform_contract import PlatformContractResponse  # noqa: E402
from apps.runtime_manifest import (  # noqa: E402
    RuntimeAdminBenchmarksResponse,
    normalize_runtime_validation_payload,
)
from tests._manifest_backed_integrations import (
    contract_integrations_match_manifest,
)
from tests.integration.live_capacity_blockers import (
    classify_simulation_capacity_blocker,  # noqa: E402
)
from tests.integration.live_check_filter import (  # noqa: E402
    filtered_live_check_reason,
    live_check_filter_tokens,
    selected_live_check_filter,
    should_run_live_check,
)
from tests.integration.live_data_source_server import (  # noqa: E402
    default_refreshable_dataset_payload,
    static_json_server,
)
from tests.integration.live_integration_artifacts import (
    write_live_integration_summary,  # noqa: E402
)
from tests.integration.live_repository_fixture import (  # noqa: E402
    assert_repository_intelligence_capabilities_payload,
    live_repository_fixture,
    local_repository_live_support_reason,
)
from tests.integration.live_webhook_receiver import webhook_receiver  # noqa: E402

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
SUITE_NAME = "python_sdk_integration"
STARTED = time.perf_counter()
ACTIVE_LIVE_CHECK_FILTER = selected_live_check_filter()
ACTIVE_LIVE_CHECK_FILTER_TOKENS = live_check_filter_tokens(ACTIVE_LIVE_CHECK_FILTER)
_runtime_proc: subprocess.Popen[str] | None = None
_runtime_started_here = False
_runtime_log_path: Path | None = None

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
MISSING_JOB_ID = "00000000-0000-0000-0000-000000000001"


class EnvironmentBlocked(RuntimeError):  # noqa: N818
    """Raised when live simulation capacity is exhausted for this environment."""


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _live_metering_events() -> list[dict[str, object]]:
    return [
        {
            "event_type": "runtime_call",
            "module": "integration",
            "function": "python_sdk_live",
            "engine_used": "python",
            "latency_ms": 12.5,
            "success": True,
        }
    ]


def _current_billing_period() -> str:
    return time.strftime("%Y-%m", time.gmtime())


def _live_credit_refresh_request(device_prefix: str) -> dict[str, object]:
    return {
        "device_id": f"{device_prefix}-{time.time_ns()}",
        "billing_period": _current_billing_period(),
        "credits_used": 0,
    }


def _live_trigger_request(name: str) -> dict[str, object]:
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
        "description": "Live integration trigger lifecycle check.",
        "auto_execute": False,
    }


def _live_refreshable_dataset_request(prefix: str, source_url: str) -> dict[str, object]:
    return {
        "connection_type": "api",
        "provider": "rest",
        "dataset_name": f"{prefix}-{time.time_ns()}",
        "description": "Live Python SDK refreshable dataset check.",
        "connection_config": {
            "url": source_url,
            "data_path": "items",
        },
    }


def _live_saved_connector_request(prefix: str, source_url: str) -> dict[str, object]:
    return {
        "name": f"{prefix}-{time.time_ns()}",
        "connector_type": "rest",
        "description": "Live Python SDK saved connector check.",
        "config": {
            "url": source_url,
            "data_path": "items",
        },
    }


def _assert_missing_job_error(exc: DecisionEngineError) -> None:
    assert exc.status_code == 404, exc
    assert exc.error_code in {"job_not_found", "not_found"}, exc
    payload = exc.response_body if isinstance(exc.response_body, dict) else {}
    error = payload.get("error") if isinstance(payload, dict) else {}
    assert isinstance(error, dict), payload
    assert error.get("code") in {"job_not_found", "not_found"}, payload


def _assert_repository_error(
    exc: DecisionEngineError,
    *,
    status_code: int,
    error_code: str,
) -> dict[str, object]:
    assert exc.status_code == status_code, exc
    assert exc.error_code == error_code, exc
    payload = exc.response_body if isinstance(exc.response_body, dict) else {}
    error = payload.get("error") if isinstance(payload, dict) else {}
    assert isinstance(error, dict), payload
    assert error.get("code") == error_code, payload
    return error


def _create_live_api_key_with_plan_fallback(
    client: DecisionEngineClient,
    *,
    label: str,
) -> tuple[dict[str, object], int]:
    requested_device_limit = 2
    try:
        created = client.create_api_key(name=label, device_limit=requested_device_limit)
    except DecisionEngineError as exc:
        if exc.status_code != 400 or exc.error_code != "invalid_device_limit":
            raise
        requested_device_limit = 0
        created = client.create_api_key(name=label)
    return created, requested_device_limit


async def _create_live_api_key_with_plan_fallback_async(
    client: AsyncDecisionEngineClient,
    *,
    label: str,
) -> tuple[dict[str, object], int]:
    requested_device_limit = 2
    try:
        created = await client.create_api_key(name=label, device_limit=requested_device_limit)
    except DecisionEngineError as exc:
        if exc.status_code != 400 or exc.error_code != "invalid_device_limit":
            raise
        requested_device_limit = 0
        created = await client.create_api_key(name=label)
    return created, requested_device_limit


def _assert_model_catalog_provider_metadata(models) -> None:
    assert models.object == "list"
    tokenizer = next((item for item in models.data if item.id == "text.tokenizer"), None)
    assert tokenizer is not None, models.data

    for item in models.data:
        assert item.provider_backend is None or isinstance(item.provider_backend, str), item
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
            value = getattr(item, field_name)
            assert isinstance(value, list), (item.id, field_name, value)
            assert all(isinstance(entry, str) and entry for entry in value), (
                item.id,
                field_name,
                value,
            )
        for field_name in (
            "routing_fallback_policy",
            "chat_routing_fallback_policy",
            "embedding_routing_fallback_policy",
        ):
            value = getattr(item, field_name)
            assert value is None or isinstance(value, str), (item.id, field_name, value)
        for field_name in (
            "routing_max_attempts",
            "chat_routing_max_attempts",
            "embedding_routing_max_attempts",
        ):
            value = getattr(item, field_name)
            assert value is None or (isinstance(value, int) and value > 0), (item.id, field_name, value)
        for field_name in ("timeout_seconds", "chat_timeout_seconds", "embedding_timeout_seconds"):
            value = getattr(item, field_name)
            assert value is None or (isinstance(value, int | float) and value > 0), (
                item.id,
                field_name,
                value,
            )
        assert isinstance(item.provider_auth_configured, bool), item
        assert isinstance(item.chat_provider_auth_configured, bool), item
        assert isinstance(item.embedding_provider_auth_configured, bool), item
        if item.provider_backend != "router":
            assert item.resolved_routing_targets == [], item
            assert item.resolved_chat_routing_targets == [], item
            assert item.resolved_embedding_routing_targets == [], item
            assert item.routing_fallback_policy is None, item
            assert item.chat_routing_fallback_policy is None, item
            assert item.embedding_routing_fallback_policy is None, item
            assert item.routing_fallback_on == [], item
            assert item.chat_routing_fallback_on == [], item
            assert item.embedding_routing_fallback_on == [], item
            assert item.routing_max_attempts is None, item
            assert item.chat_routing_max_attempts is None, item
            assert item.embedding_routing_max_attempts is None, item

    assert tokenizer.provider_backend is None, tokenizer
    assert tokenizer.routing_targets == [], tokenizer
    assert tokenizer.resolved_routing_targets == [], tokenizer
    assert tokenizer.chat_routing_targets == [], tokenizer
    assert tokenizer.resolved_chat_routing_targets == [], tokenizer
    assert tokenizer.embedding_routing_targets == [], tokenizer
    assert tokenizer.resolved_embedding_routing_targets == [], tokenizer
    assert tokenizer.routing_fallback_policy is None, tokenizer
    assert tokenizer.chat_routing_fallback_policy is None, tokenizer
    assert tokenizer.embedding_routing_fallback_policy is None, tokenizer
    assert tokenizer.routing_fallback_on == [], tokenizer
    assert tokenizer.chat_routing_fallback_on == [], tokenizer
    assert tokenizer.embedding_routing_fallback_on == [], tokenizer
    assert tokenizer.routing_max_attempts is None, tokenizer
    assert tokenizer.chat_routing_max_attempts is None, tokenizer
    assert tokenizer.embedding_routing_max_attempts is None, tokenizer
    assert tokenizer.timeout_seconds is None, tokenizer
    assert tokenizer.chat_timeout_seconds is None, tokenizer
    assert tokenizer.embedding_timeout_seconds is None, tokenizer
    assert tokenizer.required_provider_headers == [], tokenizer
    assert tokenizer.chat_required_provider_headers == [], tokenizer
    assert tokenizer.embedding_required_provider_headers == [], tokenizer
    assert tokenizer.provider_auth_env_vars == [], tokenizer
    assert tokenizer.chat_provider_auth_env_vars == [], tokenizer
    assert tokenizer.embedding_provider_auth_env_vars == [], tokenizer
    assert tokenizer.provider_auth_configured is False, tokenizer
    assert tokenizer.chat_provider_auth_configured is False, tokenizer
    assert tokenizer.embedding_provider_auth_configured is False, tokenizer


def _assert_empty_provider_trace(result, *, output_items: bool = False) -> None:
    assert result.provider_backend is None, result
    assert result.provider_model_id is None, result
    assert result.provider_attempts == [], result
    if output_items:
        for item in result.output:
            assert item.provider_backend is None, item
            assert item.provider_model_id is None, item
            assert item.provider_attempts == [], item


def _credit_refresh_reason(*, status: int | None, payload: object, text: str) -> str | None:
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    code = None
    if isinstance(detail, dict):
        raw_code = detail.get("error", detail.get("code"))
        if isinstance(raw_code, str):
            code = raw_code
    normalized = text.lower()
    if status == 429 and code in {"quota_exhausted", "quota_exceeded"}:
        return "credit refresh quota exhausted for this live environment"
    if status == 429 and ("quota_exhausted" in normalized or "quota_exceeded" in normalized):
        return "credit refresh quota exhausted for this live environment"
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
            if status == 200:
                return
            last_error = f"status {status}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for {base_url}/v1/health: {last_error}.{_read_log(log_path)}"
    )


def _endpoint_serves_canonical_sdk_surface(base_url: str) -> bool:
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
            ("/v1/api-keys", "get"),
            ("/v1/api-keys", "post"),
            ("/v1/api-keys/{key_id}", "delete"),
            ("/v1/webhooks/test", "post"),
            ("/v1/jobs/list", "get"),
            ("/v1/jobs/{job_id}", "get"),
            ("/v1/jobs/{job_id}/result", "get"),
            ("/v1/jobs/{job_id}/cancel", "post"),
            ("/v1/triggers", "get"),
            ("/v1/triggers", "post"),
            ("/v1/triggers/{trigger_id}/fire", "post"),
            ("/v1/triggers/{trigger_id}/pause", "patch"),
            ("/v1/triggers/{trigger_id}", "delete"),
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
    log_dir = Path(tempfile.mkdtemp(prefix="integration-python-sdk-"))
    log_path = log_dir / "api_server.log"

    if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):
        try:
            _wait_for_health(base_url, log_path, timeout_seconds=5.0)
            if _endpoint_serves_canonical_sdk_surface(base_url):
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
API_KEY, API_KEY_CONFIGURED, LOCAL_LIVE_AUTH_BOOTSTRAP_ERROR = (
    ensure_bootstrapped_local_live_api_key(
        api_key=API_KEY,
        api_key_configured=API_KEY_CONFIGURED,
        active_base_url=BASE_URL,
    )
)
atexit.register(_cleanup_runtime)


def raise_if_simulation_capacity_blocked(exc: DecisionEngineError) -> None:
    reason = classify_simulation_capacity_blocker(
        status=exc.status_code,
        payload=exc.response_body,
        text=str(exc),
    )
    if reason:
        raise EnvironmentBlocked(reason) from exc


def raise_if_deployment_mutation_blocked(exc: DecisionEngineError) -> None:
    payload = exc.response_body if isinstance(exc.response_body, dict) else {}
    error = payload.get("error") if isinstance(payload, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    if exc.status_code == 403:
        raise EnvironmentBlocked("deployment mutation requires owner role") from exc
    if exc.status_code == 409 or code == "deployment_exists":
        raise EnvironmentBlocked("deployment mutation requires an org without an existing deployment") from exc


def raise_if_credit_refresh_blocked(exc: DecisionEngineError) -> None:
    reason = _credit_refresh_reason(
        status=exc.status_code,
        payload=exc.response_body,
        text=str(exc),
    )
    if reason:
        raise EnvironmentBlocked(reason) from exc


def raise_if_artifact_bridge_blocked(exc: DecisionEngineError) -> None:
    payload = exc.response_body if isinstance(exc.response_body, dict) else {}
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else {}
    code = detail.get("code") if isinstance(detail, dict) else None
    if code == "artifact_bridge_backend_unavailable":
        raise EnvironmentBlocked(
            "artifact bridge requires the optional huggingface_hub backend in this checkout"
        ) from exc


def _missing_live_api_key_reason(exc: BaseException) -> str | None:
    if API_KEY_CONFIGURED:
        return None
    if isinstance(exc, AuthenticationError):
        return (
            "DE_API_KEY is not set; skipping authenticated Python SDK checks that require a "
            "real live key."
        )
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status == 401:
        return (
            "DE_API_KEY is not set; skipping authenticated Python SDK checks that require a "
            "real live key."
        )
    text = str(exc)
    if any(
        token in text
        for token in (
            "invalid, expired, or has been revoked",
            "Authentication failed",
            "Auth failed",
            "got 401",
        )
    ):
        return (
            "DE_API_KEY is not set; skipping authenticated Python SDK checks that require a "
            "real live key."
        )
    return None


def check(name: str, fn):
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    if not should_run_live_check(name, ACTIVE_LIVE_CHECK_FILTER_TOKENS):
        reason = filtered_live_check_reason(ACTIVE_LIVE_CHECK_FILTER)
        results.append((SKIP, name, reason))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {reason}")
        return
    try:
        fn()
        results.append((PASS, name))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except EnvironmentBlocked as e:
        results.append((SKIP, name, str(e)))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except AssertionError as e:
        missing_key_reason = _missing_live_api_key_reason(e)
        if missing_key_reason:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
                f"{missing_key_reason}"
            )
            return
        results.append((FAIL, name, str(e)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except Exception as e:
        missing_key_reason = _missing_live_api_key_reason(e)
        if missing_key_reason:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
                f"{missing_key_reason}"
            )
            return
        results.append((FAIL, name, str(e)))
        _emit(
            f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): "
            f"{type(e).__name__}: {e}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: Sync Client — Initialization
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 1: Sync Client — Initialization")
print("=" * 70)


def test_client_init_with_explicit_key():
    client = DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0)
    assert client._api_key == API_KEY
    assert client._base_url == BASE_URL
    client.close()


check("Client init with explicit api_key and base_url", test_client_init_with_explicit_key)


def test_client_init_from_env():
    """Client should pick up ALGENTA_API_KEY from environment."""
    old_algenta = os.environ.get("ALGENTA_API_KEY")
    old_legacy = os.environ.pop("DE_API_KEY", None)
    os.environ["ALGENTA_API_KEY"] = API_KEY
    try:
        client = DecisionEngineClient(base_url=BASE_URL)
        assert client._api_key == API_KEY
        client.close()
    finally:
        if old_algenta is None:
            os.environ.pop("ALGENTA_API_KEY", None)
        else:
            os.environ["ALGENTA_API_KEY"] = old_algenta
        if old_legacy is not None:
            os.environ["DE_API_KEY"] = old_legacy


check("Client init from ALGENTA_API_KEY env var", test_client_init_from_env)


def test_client_init_no_key_raises():
    old_algenta = os.environ.pop("ALGENTA_API_KEY", None)
    old_legacy = os.environ.pop("DE_API_KEY", None)
    try:
        raised = False
        try:
            DecisionEngineClient(base_url=BASE_URL)
        except ValueError as e:
            raised = True
            assert "API key required" in str(e)
        assert raised, "Expected ValueError for missing API key"
    finally:
        if old_algenta is not None:
            os.environ["ALGENTA_API_KEY"] = old_algenta
        if old_legacy is not None:
            os.environ["DE_API_KEY"] = old_legacy


check("Client init with no key raises ValueError", test_client_init_no_key_raises)


def test_client_context_manager():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        assert client._api_key == API_KEY


check("Client works as context manager", test_client_context_manager)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: Sync Client — Health & Version
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 2: Sync Client — Health & Version")
print("=" * 70)


def test_health():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        data = client.health()
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert data.get("status") == "ok", f"Expected status=ok, got {data}"


check("client.health() → status ok", test_health)


def test_version():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        data = client.version()
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert "api_version" in data, f"Missing api_version: {data}"
        assert "engine_version" in data, f"Missing engine_version: {data}"


check("client.version() → api_version + engine_version", test_version)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: Sync Client — Simulation (live Mojo engine)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 3: Sync Client — Simulation (live engine)")
print("=" * 70)


def test_simulate_auto_mode():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            result = client.simulate(
                mode="auto",
                runs=1000,
                scenario={
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        assert isinstance(result, DecisionEnvelope), (
            f"Expected DecisionEnvelope, got {type(result)}"
        )
        assert result.status == "completed", f"Expected status=completed, got {result.status}"
        assert result.recommended_action in ("proceed", "hold", "reject"), (
            f"Unexpected action: {result.recommended_action}"
        )
        assert 0 <= result.confidence <= 1, f"Confidence out of range: {result.confidence}"
        assert result.scenarios_run >= 1000, (
            f"Expected >= 1000 scenarios, got {result.scenarios_run}"
        )
        assert result.execution_ms >= 0, f"Negative execution_ms: {result.execution_ms}"


check("client.simulate(auto) → DecisionEnvelope with valid fields", test_simulate_auto_mode)


def test_simulate_expert_mode():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            result = client.simulate(
                mode="expert",
                runs=500,
                simulation={
                    "variables": [
                        {
                            "name": "revenue",
                            "distribution": "triangular",
                            "params": {"low": 80000, "mode": 120000, "high": 200000},
                        },
                        {
                            "name": "costs",
                            "distribution": "normal",
                            "params": {"mean": 55000, "std": 8000},
                        },
                    ],
                    "objective_function": "revenue - costs",
                },
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        assert isinstance(result, DecisionEnvelope), (
            f"Expected DecisionEnvelope, got {type(result)}"
        )
        assert result.recommended_action in ("proceed", "hold", "reject"), (
            f"Unexpected action: {result.recommended_action}"
        )


check("client.simulate(expert) → DecisionEnvelope", test_simulate_expert_mode)


def test_envelope_metrics():
    """Validate the metrics sub-object on the envelope."""
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            result = client.simulate(
                mode="auto",
                runs=1000,
                scenario={
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        m = result.metrics
        assert isinstance(m.expected_value, int | float), (
            f"expected_value not numeric: {m.expected_value}"
        )
        assert m.std_deviation >= 0, f"std_deviation negative: {m.std_deviation}"
        assert m.variance >= 0, f"variance negative: {m.variance}"
        assert 0 <= m.probability_of_loss <= 1, (
            f"probability_of_loss out of range: {m.probability_of_loss}"
        )


check(
    "Envelope metrics: expected_value, std_deviation, variance, probability_of_loss",
    test_envelope_metrics,
)


def test_envelope_percentiles():
    """Validate percentile ordering."""
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            result = client.simulate(
                mode="auto",
                runs=1000,
                scenario={
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        p = result.percentiles
        assert p.p5 <= p.p25, f"p5={p.p5} > p25={p.p25}"
        assert p.p25 <= p.p50, f"p25={p.p25} > p50={p.p50}"
        assert p.p50 <= p.p75, f"p50={p.p50} > p75={p.p75}"
        assert p.p75 <= p.p95, f"p75={p.p75} > p95={p.p95}"


check("Envelope percentiles ordered: p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95", test_envelope_percentiles)


def test_envelope_run_id_is_uuid():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            result = client.simulate(
                mode="auto",
                runs=100,
                scenario={
                    "variables": {"x": {"low": 0, "high": 100}},
                    "objective": "maximize_net_value",
                },
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        assert isinstance(result.run_id, uuid.UUID), f"run_id is not a UUID: {result.run_id}"
        assert result.engine_version, "engine_version is empty"


check("Envelope run_id is valid UUID", test_envelope_run_id_is_uuid)


def test_simulate_seeded_determinism():
    """Two seeded simulations with same seed should produce identical confidence."""
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        kwargs = {
            "mode": "auto",
            "runs": 100,
            "seed": 42,
            "scenario": {
                "variables": {"x": {"low": 0, "high": 100}},
                "objective": "maximize_net_value",
            },
        }
        try:
            r1 = client.simulate(**kwargs)
            r2 = client.simulate(**kwargs)
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        assert r1.confidence == r2.confidence, (
            f"Seeded runs differ: {r1.confidence} vs {r2.confidence}"
        )


check("Seeded simulate → deterministic confidence", test_simulate_seeded_determinism)


def test_envelope_metadata():
    """Metadata sub-object should be populated."""
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            result = client.simulate(
                mode="auto",
                runs=100,
                scenario={
                    "variables": {"x": {"low": 0, "high": 100}},
                    "objective": "maximize_net_value",
                },
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        meta = result.metadata
        assert meta.mode, "metadata.mode is empty"
        assert meta.billing_units >= 0, f"billing_units negative: {meta.billing_units}"
        assert meta.engine_version, "metadata.engine_version is empty"


check("Envelope metadata: mode, billing_units, engine_version", test_envelope_metadata)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: Sync Client — Error Handling
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 4: Sync Client — Error Handling")
print("=" * 70)


def test_bad_api_key_raises_auth_error():
    with DecisionEngineClient(
        api_key="de_live_INVALID_KEY_FAKE", base_url=BASE_URL, max_retries=0
    ) as client:
        raised = False
        try:
            client.simulate(
                mode="auto",
                runs=100,
                scenario={
                    "variables": {"x": {"low": 0, "high": 100}},
                    "objective": "maximize_net_value",
                },
            )
        except AuthenticationError as e:
            raised = True
            assert e.status_code == 401, f"Expected 401, got {e.status_code}"
        assert raised, "Expected AuthenticationError for bad key"


check("Bad API key → AuthenticationError (401)", test_bad_api_key_raises_auth_error)


def test_bad_payload_raises_validation_error():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        raised = False
        try:
            client.simulate(mode="invalid_mode_xyz")
        except (ValidationError, DecisionEngineError) as e:
            raised = True
            assert e.status_code in (400, 422), f"Expected 400/422, got {e.status_code}"
        assert raised, "Expected ValidationError for bad payload"


check("Bad payload → ValidationError (422)", test_bad_payload_raises_validation_error)


def test_empty_simulate_raises():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        raised = False
        try:
            client.simulate()
        except (ValidationError, DecisionEngineError) as e:
            raised = True
            assert e.status_code in (400, 422), f"Expected 400/422, got {e.status_code}"
        assert raised, "Expected error for empty simulate"


check("Empty simulate() → error", test_empty_simulate_raises)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: Sync Client — LLM, Planning, and Agent Runs
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 5: Sync Client — LLM, Planning, and Agent Runs")
print("=" * 70)


def test_sync_llm_utility_surface():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        models = client.list_models()
        _assert_model_catalog_provider_metadata(models)
        model_ids = {item.id for item in models.data}
        assert "text.tokenizer" in model_ids, f"Missing text.tokenizer in {model_ids}"
        assert "text.hash_embedding_v1" in model_ids, (
            f"Missing text.hash_embedding_v1 in {model_ids}"
        )
        assert "embeddings.cosine_similarity" in model_ids, (
            f"Missing embeddings.cosine_similarity in {model_ids}"
        )
        try:
            artifact = client.resolve_artifact_bridge(
                repo_id="bert-base-uncased",
                filename="model.safetensors",
                revision="main",
                local_files_only=True,
            )
        except DecisionEngineError as exc:
            raise_if_artifact_bridge_blocked(exc)
            raise
        assert artifact.status in {"resolved", "not_cached"}
        assert artifact.filename == "model.safetensors"
        if artifact.resolved_path is not None:
            assert artifact.resolved_path

        tokenized = client.tokenize("alpha beta gamma")
        assert tokenized.object == "tokenization"
        assert tokenized.model == "text.tokenizer"
        assert tokenized.token_count == len(tokenized.tokens) == 3

        counted = client.count_tokens("alpha beta gamma")
        assert counted.object == "token_count"
        assert counted.token_count == 3

        deployment_regions = client.list_deployment_regions()
        assert deployment_regions.providers, "Expected at least one deployment provider"
        managed_provider = next(
            (provider for provider in deployment_regions.providers if provider.id == "algenta_shared"),
            None,
        )
        assert managed_provider is not None, "Expected algenta_shared provider in deployment regions"
        assert managed_provider.regions, "Expected at least one managed deployment region"

        deployment = client.get_deployment()
        if deployment is not None:
            assert deployment.deployment_id
            assert deployment.provider
            deployment_cost = client.get_deployment_cost(deployment.deployment_id)
            assert deployment_cost.deployment_id == deployment.deployment_id
            assert deployment_cost.provider == deployment.provider
            assert deployment_cost.cost_usd_month >= 0

        chat = client.chat_completions([{"role": "user", "content": "summarize alpha beta"}])
        assert chat.object == "chat.completion"
        assert chat.model == "text.tokenizer"
        assert chat.choices[0].message.role == "assistant"
        assert chat.usage.total_tokens >= chat.usage.prompt_tokens
        _assert_empty_provider_trace(chat)

        response = client.responses("alpha beta")
        assert response.object == "response"
        assert response.status == "completed"
        assert len(response.output) >= 1
        _assert_empty_provider_trace(response, output_items=True)

        embedded = client.embeddings(["alpha beta", "gamma"], dimensions=8)
        assert embedded.object == "list"
        assert embedded.model == "text.hash_embedding_v1"
        assert embedded.dimensions == 8
        assert len(embedded.data) == 2
        _assert_empty_provider_trace(embedded)

        similarity = client.embedding_similarity([1.0, 0.0], [0.5, 0.5])
        assert similarity.object == "embedding_similarity"
        assert similarity.dimension == 2
        assert isinstance(similarity.score, float)

        reranked = client.rerank(
            [1.0, 0.0],
            [
                {"id": "doc_a", "embedding": [1.0, 0.0], "text": "alpha"},
                {"id": "doc_b", "embedding": [0.0, 1.0], "text": "beta"},
            ],
            top_n=2,
        )
        assert reranked.object == "list"
        assert reranked.returned_documents == 2
        assert reranked.data[0].rank == 1
        assert reranked.data[0].id == "doc_a"


check("Sync client LLM utility routes → typed live results", test_sync_llm_utility_surface)


def test_sync_account_surface():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        me = client.me()
        assert me.user.email
        assert me.org.name

        usage = client.usage()
        assert usage.billing_period, "Expected billing_period on usage"
        assert usage.quota_limit >= 0

        limits = client.limits()
        assert isinstance(limits, dict), type(limits)
        assert any(key in limits for key in ("plan", "simulations_per_month", "rate_limit_per_minute")), limits

        distributions = client.distributions()
        assert distributions.total >= len(distributions.distributions)
        assert distributions.distributions
        assert distributions.distributions[0].name

        templates = client.templates()
        assert templates.total >= len(templates.templates)
        assert templates.templates
        assert templates.templates[0].id

        listed_before = client.list_api_keys()
        before_ids = {str(item.id) for item in listed_before}

        label = f"python-sdk-live-{time.time_ns()}"
        created_id: str | None = None
        try:
            created, requested_device_limit = _create_live_api_key_with_plan_fallback(
                client,
                label=label,
            )
            created_id = str(created["id"])
            assert created["label"] == label
            assert created["device_limit"] == requested_device_limit
            assert created["raw_key"].startswith("de_live_"), created

            listed_after = client.list_api_keys()
            after_ids = {str(item.id) for item in listed_after}
            assert created_id in after_ids, (created_id, after_ids)
            created_entry = next((item for item in listed_after if str(item.id) == created_id), None)
            assert created_entry is not None
            assert created_entry.device_limit == requested_device_limit

            revoke_result = client.revoke_api_key(created_id)
            assert revoke_result == {} or revoke_result.get("revoked") is True, revoke_result
            created_id = None

            listed_final = client.list_api_keys()
            final_ids = {str(item.id) for item in listed_final}
            assert before_ids.issubset(final_ids), (before_ids, final_ids)
            assert label not in {item.label for item in listed_final}
        finally:
            if created_id is not None:
                client.revoke_api_key(created_id)


check("Sync client account/API-key surface → typed live results", test_sync_account_surface)


def test_sync_runtime_proof_surface():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        manifest = client.get_runtime_manifest()
        assert manifest.runtime_version
        assert len(manifest.modules) >= 1
        manifest_provider_routing_overhead = next(
            (entry for entry in manifest.benchmarking.classes if entry.code.value == "B8"),
            None,
        )
        assert manifest_provider_routing_overhead is not None
        assert manifest_provider_routing_overhead.description == "provider routing overhead"
        assert manifest_provider_routing_overhead.evidence_paths == [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ]
        manifest_checkpoint_replay_overhead = next(
            (entry for entry in manifest.benchmarking.classes if entry.code.value == "B6"),
            None,
        )
        assert manifest_checkpoint_replay_overhead is not None
        assert manifest_checkpoint_replay_overhead.description == "checkpoint and replay overhead"
        assert manifest_checkpoint_replay_overhead.evidence_paths == []
        manifest_decision_workflow_completion = next(
            (entry for entry in manifest.benchmarking.classes if entry.code.value == "B10"),
            None,
        )
        assert manifest_decision_workflow_completion is not None
        assert (
            manifest_decision_workflow_completion.description
            == "decision workflow completion latency"
        )
        assert manifest_decision_workflow_completion.evidence_paths == [
            "build/repository_intelligence_benchmark.json",
            "benchmarks/repository_intelligence_benchmark.py",
            "tests/test_repository_intelligence_benchmark.py",
        ]

        modules = client.get_runtime_modules()
        assert len(modules.modules) >= 1
        assert modules.summary.module_count >= 1

        benchmarks = client.get_runtime_benchmarks()
        assert len(benchmarks.module_benchmarks) >= 1
        provider_routing_overhead = next(
            (entry for entry in benchmarks.benchmarking.classes if entry.code.value == "B8"),
            None,
        )
        assert provider_routing_overhead is not None
        assert provider_routing_overhead.description == "provider routing overhead"
        assert provider_routing_overhead.evidence_paths == [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ]
        checkpoint_replay_overhead = next(
            (entry for entry in benchmarks.quality_gate_benchmark_classes if entry.code.value == "B6"),
            None,
        )
        assert checkpoint_replay_overhead is not None
        assert checkpoint_replay_overhead.description == "checkpoint and replay overhead"
        assert checkpoint_replay_overhead.evidence_paths == []
        decision_workflow_completion = next(
            (
                entry
                for entry in benchmarks.quality_gate_benchmark_classes
                if entry.code.value == "B10"
            ),
            None,
        )
        assert decision_workflow_completion is not None
        assert decision_workflow_completion.description == "decision workflow completion latency"
        assert decision_workflow_completion.evidence_paths == [
            "build/repository_intelligence_benchmark.json",
            "benchmarks/repository_intelligence_benchmark.py",
            "tests/test_repository_intelligence_benchmark.py",
        ]
        assert {entry.code.value for entry in benchmarks.quality_gate_benchmark_classes} == {
            "B6",
            "B7",
            "B9",
            "B10",
        }
        assert [entry.name.value for entry in benchmarks.quality_gate_slo_budgets] == [
            "mcp_call_first_party",
            "decision_plan_creation",
            "replay",
        ]
        assert benchmarks.evaluation_summary.replay_gate_enabled is True
        assert benchmarks.evaluation_summary.tool_call_quality_gate_enabled is True
        assert benchmarks.evaluation_summary.rag_quality_gate_enabled is True
        assert benchmarks.evaluation_summary.decision_quality_gate_enabled is True

        validation = client.get_runtime_release_validation()
        assert validation.valid_release is True


check("Sync client runtime proof routes → signed live results", test_sync_runtime_proof_surface)


def test_sync_dataset_surface():
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
            preview_tested = client.preview_test_connector(
                connector_type="rest",
                config={"url": source_url, "data_path": "items"},
            )
            assert preview_tested.success is True
            assert preview_tested.status == "live"

            preview_browsed = client.preview_browse_connector(
                connector_type="rest",
                config={"url": source_url, "data_path": "items"},
            )
            assert preview_browsed.connector_type == "rest"
            assert preview_browsed.total >= 1

            connector = client.create_connector(
                **_live_saved_connector_request("python-sdk-sync-connector", source_url)
            )
            connector_id = connector.id
            connector_name = connector.name
            assert connector_id
            assert connector_name
            try:
                connectors = client.list_connectors(page=1, limit=50)
                assert connectors.page == 1
                assert connectors.limit == 50
                assert connectors.total >= len(connectors.connectors)
                assert connectors.pages >= 1
                assert any(item.id == connector_id for item in connectors.connectors)

                detail = client.get_connector(connector_id)
                assert detail.id == connector_id
                assert detail.name == connector_name

                updated = client.update_connector(
                    connector_id,
                    description="Live Python SDK connector updated description.",
                )
                assert updated.id == connector_id
                assert updated.description == "Live Python SDK connector updated description."

                tested = client.test_connector(connector_id)
                assert tested.success is True
                assert tested.status == "live"

                browsed = client.browse_connector(connector_id)
                assert browsed.connector_type == "rest"
                assert browsed.total >= 1

                created = client.connect_data(
                    **_live_refreshable_dataset_request("python-sdk-sync-dataset", source_url)
                )
                dataset_id = created.dataset_id
                dataset_name = created.dataset_name
                assert created.status == "ready"
                assert dataset_id
                assert dataset_name

                try:
                    listed = client.list_datasets(search=dataset_name, compact=True)
                    assert listed.total >= len(listed.datasets)
                    assert any(item.dataset_id == dataset_id for item in listed.datasets)

                    refreshed = client.refresh_dataset(dataset_id)
                    assert refreshed.status == "ready"
                    assert refreshed.dataset_id == dataset_id

                    summary = client.get_dataset_summary(dataset_id)
                    assert summary.dataset_id == dataset_id
                    assert summary.name == dataset_name
                    assert summary.column_count >= 2

                    detail = client.get_dataset(dataset_id)
                    assert detail.dataset.dataset_id == dataset_id
                    assert detail.dataset.dataset_name == dataset_name
                    assert isinstance(detail.schema, dict)
                    assert len(detail.schema.get("columns", [])) >= 2
                finally:
                    deleted = client.delete_dataset(dataset_id)
                    assert deleted.dataset_id == dataset_id
                    assert deleted.status == "deleted"
            finally:
                client.delete_connector(connector_id)


check("Sync client saved connector + dataset lifecycle → typed live results", test_sync_dataset_surface)


def test_sync_repository_surface():
    reason = local_repository_live_support_reason(BASE_URL)
    if reason is not None:
        raise EnvironmentBlocked(reason)

    repository_id: str | None = None
    with live_repository_fixture("python-sdk-sync") as repository_fixture:
        with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
            capabilities = client.get_repository_intelligence_capabilities()
            assert_repository_intelligence_capabilities_payload(capabilities)
            created_connector = client.create_connector(**repository_fixture.connector_request)
            repository_id = str(created_connector.id)
            assert created_connector.connector_type == "local_repo"
            try:
                snapshot = client.create_repository_snapshot(
                    repository_id,
                    repository_fixture.snapshot_request,
                )
                fetched_snapshot = client.get_repository_snapshot(repository_id, snapshot.snapshot_id)
                repeated_snapshot = client.create_repository_snapshot(
                    repository_id,
                    repository_fixture.snapshot_request,
                )

                assert snapshot.connector_type == "local_repo"
                assert snapshot.file_count >= 2
                assert fetched_snapshot.snapshot_id == snapshot.snapshot_id
                assert fetched_snapshot.content_hash == snapshot.content_hash
                assert repeated_snapshot.snapshot_id == snapshot.snapshot_id
                assert repeated_snapshot.status == "existing"

                triage = client.triage_repository(
                    repository_id,
                    repository_fixture.triage_request(snapshot.snapshot_id),
                )
                assert triage.snapshot_id == snapshot.snapshot_id
                assert triage.workspace_evidence_bundle_ref
                assert triage.reduction_ratio >= 1.0
                assert triage.evidence_items
                assert triage.suspect_files[0] == repository_fixture.primary_file
                assert (
                    triage.workspace_evidence_bundle_artifact.artifact_kind
                    == "WorkspaceEvidenceBundle"
                )

                graph = client.query_repository_graph(
                    repository_id,
                    repository_fixture.graph_query_request(
                        snapshot.snapshot_id,
                        triage.workspace_evidence_bundle_ref,
                    ),
                )
                assert graph.snapshot_id == snapshot.snapshot_id
                assert repository_fixture.primary_file in graph.seed_file_paths
                assert repository_fixture.primary_file in graph.impacted_files
                assert graph.graph_nodes
                assert graph.top_change_risk_files

                try:
                    decision_plan = client.create_repository_decision_plan(
                        repository_id,
                        repository_fixture.decision_plan_request(
                            snapshot.snapshot_id,
                            triage.workspace_evidence_bundle_ref,
                        ),
                    )
                except DecisionEngineError as exc:
                    _assert_repository_error(
                        exc,
                        status_code=503,
                        error_code="repository_model_unavailable",
                    )
                    return

                repository_analysis = decision_plan.decision_plan.repository_analysis
                assert decision_plan.decision_plan_id
                assert repository_analysis is not None
                assert repository_analysis.planner_model_id == "repository.deterministic_local_v1"
                assert repository_analysis.planner_execution_mode == "deterministic_local"
                assert repository_analysis.planner_provider_backend is None
                assert repository_analysis.generated_patch_ref
                assert repository_analysis.patch_impact_report_ref
                assert (
                    repository_analysis.token_reduction_metrics.reduction_ratio >= 1.0
                )

                try:
                    simulation = client.simulate_repository(
                        repository_id,
                        repository_fixture.simulation_request(
                            snapshot.snapshot_id,
                            decision_plan.decision_plan_id,
                        ),
                    )
                except DecisionEngineError as exc:
                    raise_if_simulation_capacity_blocked(exc)
                    raise

                validated_inputs = simulation.validated_inputs or {}
                simulation_id = str(validated_inputs.get("simulation_id") or "")
                apply_gate = (simulation.score_breakdown or {}).get("apply_gate", {})
                assert simulation_id
                assert simulation.decision_plan is not None
                assert isinstance(apply_gate, dict)
                assert apply_gate.get("policy_snapshot_id")

                branch_name = "algenta/live-repository-fix"
                apply_request = repository_fixture.apply_local_branch_request(
                    snapshot.snapshot_id,
                    decision_plan.decision_plan_id,
                    simulation_id,
                    branch_name=branch_name,
                )
                if bool(apply_gate.get("passed")):
                    applied = client.apply_repository(repository_id, apply_request)
                    assert applied.mode == "local_branch"
                    assert applied.applied is True
                    assert applied.patch
                    assert applied.branch_name == branch_name
                    assert applied.commit_sha
                    assert applied.local_checkout_path
                    repository_fixture.assert_local_branch_applied(
                        branch_name=branch_name,
                        checkout_path=applied.local_checkout_path,
                    )
                    assert repository_fixture.primary_file in applied.validation_summary.get(
                        "patch_files", []
                    )
                else:
                    try:
                        client.apply_repository(repository_id, apply_request)
                    except DecisionEngineError as exc:
                        _assert_repository_error(
                            exc,
                            status_code=409,
                            error_code="repository_apply_gate_failed",
                        )
                    else:
                        raise AssertionError(
                            "Repository apply should fail when the apply gate does not pass."
                        )
            finally:
                if repository_id is not None:
                    client.delete_connector(repository_id)


check("Sync client repository intelligence surface → typed live results", test_sync_repository_surface)


def test_sync_control_plane_surface():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        team = client.list_team_members(page=1, limit=50)
        assert team.page == 1
        assert team.limit == 50
        assert team.total >= len(team.members)
        assert team.pages >= 1
        assert team.members, "Expected at least one team member"
        assert team.members[0].email
        assert team.members[0].role

        jobs = client.list_jobs(page=1, limit=5, status="queued")
        assert jobs.page == 1
        assert jobs.limit == 5
        assert jobs.total >= len(jobs.jobs)
        assert jobs.pages >= 1
        for job in jobs.jobs:
            assert job.status == "queued", job
            assert job.queue_name

        for op in (
            lambda: client.get_job(MISSING_JOB_ID),
            lambda: client.get_job_result(MISSING_JOB_ID),
            lambda: client.cancel_job(MISSING_JOB_ID),
            lambda: client.poll_job(MISSING_JOB_ID, timeout=0.1, poll_interval=0.01),
        ):
            try:
                op()
            except DecisionEngineError as exc:
                _assert_missing_job_error(exc)
            else:
                raise AssertionError("Expected missing-job operation to fail with structured 404")

        billing = client.get_billing_info()
        assert billing.plan
        assert billing.subscription_status in {None, "active", "trialing", "past_due", "canceled", "incomplete"}

        try:
            credits = client.refresh_credits(**_live_credit_refresh_request("python-sdk-live"))
        except DecisionEngineError as exc:
            raise_if_credit_refresh_blocked(exc)
            raise
        assert credits.billing_period == _current_billing_period()
        assert credits.credits_granted >= 0
        assert credits.credits_issued_this_month >= credits.credits_granted
        assert credits.monthly_limit >= 0
        assert credits.monthly_remaining >= 0
        assert credits.refresh_after >= credits.server_time
        assert credits.expires_at >= credits.refresh_after

        metering = client.ingest_metering_events(
            device_id=f"python-sdk-live-{time.time_ns()}",
            events=_live_metering_events(),
        )
        assert metering.accepted == 1
        assert metering.billing_period

        with webhook_receiver() as (callback_url, deliveries):
            webhook = client.test_webhook_delivery(callback_url)
            assert webhook["success"] is True
            assert webhook["status_code"] == 200
            assert deliveries, "Expected one webhook delivery to local receiver"
            assert deliveries[0]["path"] == "/webhook", deliveries[0]

        devices = client.list_devices(page=1, limit=25)
        assert devices.page == 1
        assert devices.limit == 25
        assert devices.total >= len(devices.devices)
        assert devices.pages >= 1
        assert devices.device_count == len(devices.devices)
        assert devices.plan

        logs = client.get_audit_logs(page=1, limit=20)
        assert logs.page == 1
        assert logs.limit == 20
        assert logs.total >= len(logs.entries)
        assert logs.pages >= 1
        assert logs.entries, "Expected at least one audit log entry"
        assert logs.entries[0].action
        assert logs.entries[0].resource_type
        assert logs.entries[0].result in {"success", "failure"}

        policy = client.get_execution_policy()
        assert 0 <= policy.min_confidence <= 1
        assert isinstance(policy.require_calibration, bool)
        assert isinstance(policy.allow_reexecution, bool)
        assert policy.updated_at

        snapshots = client.list_execution_policy_snapshots()
        assert snapshots.total_snapshots >= len(snapshots.data)
        if snapshots.data:
            assert snapshots.data[0].snapshot_id
            assert snapshots.data[0].revision >= 1

        updated = client.update_execution_policy(
            min_confidence=policy.min_confidence,
            risk_floor=policy.risk_floor,
            require_calibration=policy.require_calibration,
            allow_reexecution=policy.allow_reexecution,
        )
        assert updated.min_confidence == policy.min_confidence
        assert updated.risk_floor == policy.risk_floor
        assert updated.require_calibration == policy.require_calibration
        assert updated.allow_reexecution == policy.allow_reexecution


check(
    "Sync client team/credits/metering/audit/execution-policy helpers → typed live results",
    test_sync_control_plane_surface,
)


def test_sync_trigger_surface():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        created = client.register_trigger(**_live_trigger_request(f"python-sdk-sync-{time.time_ns()}"))
        trigger_id = created.trigger_id
        try:
            assert trigger_id
            assert created.status == "active"

            listed = client.list_triggers(status="all", page=1, limit=25)
            assert listed.page == 1
            assert listed.limit == 25
            assert listed.total >= len(listed.triggers)
            assert any(item.trigger_id == trigger_id for item in listed.triggers)

            fired = client.fire_trigger(trigger_id, force=False)
            assert fired.trigger_id == trigger_id
            assert fired.condition_met is False
            assert fired.fired is False

            paused = client.pause_trigger(trigger_id, paused=True)
            assert paused.trigger_id == trigger_id
            assert paused.status == "paused"

            resumed = client.pause_trigger(trigger_id, paused=False)
            assert resumed.trigger_id == trigger_id
            assert resumed.status == "active"
        finally:
            deleted = client.delete_trigger(trigger_id)
            assert deleted.trigger_id == trigger_id
            assert deleted.deleted is True


check("Sync client trigger lifecycle → typed live results", test_sync_trigger_surface)


def test_sync_deployment_lifecycle_surface():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        deployment = client.get_deployment()
        if deployment is not None:
            raise EnvironmentBlocked("deployment mutation requires an org without an existing deployment")
        try:
            created = client.create_deployment(
                provider="algenta_shared",
                region="algenta-shared",
                config={"instance_size": "small"},
                billing_markup_pct=20.0,
            )
        except DecisionEngineError as exc:
            raise_if_deployment_mutation_blocked(exc)
            raise
        assert created.deployment_id
        assert created.provider == "algenta_shared"
        assert created.region == "algenta-shared"
        assert created.status in {"requested", "provisioning", "active"}

        cost = client.get_deployment_cost(created.deployment_id)
        assert cost.deployment_id == created.deployment_id
        assert cost.provider == created.provider
        assert cost.billable_cost_usd_month >= cost.cost_usd_month

        deleted = client.delete_deployment(created.deployment_id)
        assert deleted.deployment_id == created.deployment_id
        assert deleted.status in {"deprovisioning", "deleted"}


check("Sync client deployment create/delete lifecycle → typed live results", test_sync_deployment_lifecycle_surface)


def test_sync_llm_streaming_surface():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        chat_chunks = list(
            client.stream_chat_completions(
                [{"role": "user", "content": "summarize alpha beta gamma"}]
            )
        )
        assert len(chat_chunks) >= 2, f"Expected multiple chat stream chunks, got {len(chat_chunks)}"
        assert chat_chunks[0].object == "chat.completion.chunk"
        assert chat_chunks[0].choices[0].delta.role == "assistant"
        assert any(
            (chunk.choices[0].delta.content or "").strip()
            for chunk in chat_chunks
            if chunk.choices
        ), "Expected at least one streamed content delta"
        assert chat_chunks[-1].choices[0].finish_reason == "stop"

        response_events = list(client.stream_responses("alpha beta"))
        assert len(response_events) == 3, f"Expected 3 response stream events, got {len(response_events)}"
        assert response_events[0].type == "response.created"
        assert response_events[1].type == "response.output_item.done"
        assert response_events[1].item is not None
        assert response_events[1].item.content[0].token_count >= 2
        assert response_events[2].type == "response.completed"
        assert response_events[2].response is not None
        assert response_events[2].response.status == "completed"


check("Sync client streaming LLM routes → typed SSE live results", test_sync_llm_streaming_surface)


def test_sync_product_surface():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            decision = client.product_decision(
                {
                    "inputs": [
                        {
                            "name": "revenue",
                            "value": 120000.0,
                            "low": 100000.0,
                            "high": 150000.0,
                            "unit": "USD",
                        },
                        {
                            "name": "cost",
                            "value": 70000.0,
                            "low": 60000.0,
                            "high": 90000.0,
                            "unit": "USD",
                        },
                    ],
                    "risk_tolerance": "medium",
                    "scenarios": 1000,
                }
            )
            agent_run = client.product_agent_run(
                {
                    "task": f"Summarize benchmark blockers {time.time_ns()}",
                    "tools": ["search"],
                    "max_steps": 3,
                }
            )
            optimize = client.product_optimize(
                {
                    "objective": "maximize profit",
                    "variables": [
                        {"name": "price", "min": 50.0, "max": 150.0},
                        {"name": "discount", "min": 0.0, "max": 0.2},
                    ],
                    "iterations": 100,
                }
            )
            retrieve = client.product_retrieve(
                {
                    "query": "launch checklist",
                    "documents": [
                        {"id": "doc_1", "content": "Launch checklist for product release."},
                        {"id": "doc_2", "content": "Pricing review for launch approval."},
                    ],
                    "top_k": 2,
                }
            )
            forecast = client.product_forecast(
                {
                    "metric": "monthly_revenue",
                    "history": [100.0, 120.0, 130.0, 140.0],
                    "horizon": 3,
                }
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        assert decision.action
        assert 0 <= decision.confidence <= 1
        assert agent_run.run_id
        assert agent_run.status in {"completed", "requires_approval", "running"}
        assert optimize.status == "completed"
        assert optimize.optimal_values
        assert retrieve.results
        assert retrieve.results[0].content
        assert forecast.forecast_mean >= 0
        assert forecast.periods


check("Sync client product routes → typed live results", test_sync_product_surface)


def test_sync_decision_plan_route():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            plan = client.plan_decision(
                {
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
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        assert isinstance(plan.recommended_action, str) and plan.recommended_action
        assert 0 <= plan.confidence <= 1, f"Confidence out of range: {plan.confidence}"
        assert isinstance(plan.expected_value, int | float)
        assert isinstance(plan.rationale, str) and plan.rationale


check("Sync client plan_decision() → DecisionPlanResult", test_sync_decision_plan_route)


def test_sync_agent_run_lifecycle():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            created = client.create_agent_run(
                task=f"Search benchmark notes {time.time_ns()}",
                tools=["search"],
                approval_mode="manual",
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        assert created.status == "requires_approval", created.status
        assert created.pending_action == "approve", created.pending_action

        fetched = client.get_agent_run(created.run_id)
        assert fetched.run_id == created.run_id
        assert fetched.status == "requires_approval"

        events = client.get_agent_run_events(created.run_id, limit=20)
        assert events.run_id == created.run_id
        assert events.total_events >= 3, events.total_events

        approved = client.approve_agent_run(created.run_id)
        assert approved.run_id == created.run_id
        assert approved.status == "completed"
        assert "search" in approved.tools_used


check("Sync client agent-runs lifecycle → persisted live resource", test_sync_agent_run_lifecycle)


def test_sync_agent_run_event_stream():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        try:
            created = client.create_agent_run(
                task=f"Search benchmark notes {time.time_ns()}",
                tools=["search"],
                approval_mode="auto",
            )
        except DecisionEngineError as exc:
            raise_if_simulation_capacity_blocked(exc)
            raise
        events = list(client.stream_agent_run_events(created.run_id, limit=20))
        assert len(events) >= 2, f"Expected at least 2 streamed agent-run events, got {len(events)}"
        assert events[0].type == "agent.run.event"
        assert events[0].event is not None
        assert events[0].event.event_type == "run_created"
        assert events[-1].type == "agent.run.completed"
        assert events[-1].status == "completed"


check("Sync client agent-runs event stream → SSE live results", test_sync_agent_run_event_stream)


def test_distributions():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        data = client.distributions()
        assert data.total >= len(data.distributions)
        assert data.distributions, "No distributions returned"


check("client.distributions() → typed non-empty list", test_distributions)


def test_templates():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        data = client.templates()
        assert data.total >= len(data.templates)
        assert data.templates, "No templates returned"


check("client.templates() → typed non-empty list", test_templates)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6: Async Client
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 6: Async Client")
print("=" * 70)


def test_async_simulate():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            try:
                result = await client.simulate(
                    mode="auto",
                    runs=1000,
                    scenario={
                        "variables": {"revenue": {"low": 80000, "high": 200000}},
                        "objective": "maximize_net_value",
                    },
                )
            except DecisionEngineError as exc:
                raise_if_simulation_capacity_blocked(exc)
                raise
            assert isinstance(result, DecisionEnvelope), (
                f"Expected DecisionEnvelope, got {type(result)}"
            )
            assert result.status == "completed", f"Expected completed, got {result.status}"
            assert result.recommended_action in ("proceed", "hold", "reject")
            assert 0 <= result.confidence <= 1
            return result

    asyncio.run(_run())


check("AsyncClient.simulate(auto) → DecisionEnvelope", test_async_simulate)


def test_async_health():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            data = await client.health()
            assert data.get("status") == "ok"

    asyncio.run(_run())


check("AsyncClient.health() → ok", test_async_health)


def test_async_version():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            data = await client.version()
            assert "api_version" in data
            assert "engine_version" in data

    asyncio.run(_run())


check("AsyncClient.version() → api_version + engine_version", test_async_version)


def test_async_llm_and_agent_run_surface():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            models = await client.list_models()
            _assert_model_catalog_provider_metadata(models)
            model_ids = {item.id for item in models.data}
            assert "text.tokenizer" in model_ids
            try:
                artifact = await client.resolve_artifact_bridge(
                    repo_id="bert-base-uncased",
                    filename="model.safetensors",
                    revision="main",
                    local_files_only=True,
                )
            except DecisionEngineError as exc:
                raise_if_artifact_bridge_blocked(exc)
                raise
            assert artifact.status in {"resolved", "not_cached"}
            assert artifact.filename == "model.safetensors"
            if artifact.resolved_path is not None:
                assert artifact.resolved_path

            deployment_regions = await client.list_deployment_regions()
            assert deployment_regions.providers
            deployment = await client.get_deployment()
            if deployment is not None:
                deployment_cost = await client.get_deployment_cost(deployment.deployment_id)
                assert deployment_cost.deployment_id == deployment.deployment_id
                assert deployment_cost.provider == deployment.provider

            tokenized = await client.tokenize("alpha beta")
            assert tokenized.token_count == 2

            counted = await client.count_tokens("alpha beta")
            assert counted.token_count == 2

            chat = await client.chat_completions(
                [{"role": "user", "content": "summarize alpha beta"}]
            )
            assert chat.object == "chat.completion"
            assert chat.choices[0].message.role == "assistant"
            _assert_empty_provider_trace(chat)

            response = await client.responses("alpha beta")
            assert response.object == "response"
            assert response.status == "completed"
            assert len(response.output) >= 1
            _assert_empty_provider_trace(response, output_items=True)

            embedded = await client.embeddings("alpha beta", dimensions=8)
            assert embedded.dimensions == 8
            assert len(embedded.data) == 1
            _assert_empty_provider_trace(embedded)

            similarity = await client.embedding_similarity([1.0, 0.0], [0.5, 0.5])
            assert similarity.dimension == 2

            reranked = await client.rerank(
                [1.0, 0.0],
                [
                    {"id": "doc_a", "embedding": [1.0, 0.0], "text": "alpha"},
                    {"id": "doc_b", "embedding": [0.0, 1.0], "text": "beta"},
                ],
                top_n=2,
            )
            assert reranked.returned_documents == 2
            assert reranked.data[0].id == "doc_a"

            try:
                created = await client.create_agent_run(
                    task=f"Search benchmark notes {time.time_ns()}",
                    tools=["search"],
                    approval_mode="manual",
                )
            except DecisionEngineError as exc:
                raise_if_simulation_capacity_blocked(exc)
                raise
            assert created.status == "requires_approval"

            approved = await client.approve_agent_run(created.run_id)
            assert approved.status == "completed"
            assert "search" in approved.tools_used

    asyncio.run(_run())


check("AsyncClient LLM + agent-runs surfaces → typed live results", test_async_llm_and_agent_run_surface)


def test_async_deployment_lifecycle_surface():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            deployment = await client.get_deployment()
            if deployment is not None:
                raise EnvironmentBlocked(
                    "deployment mutation requires an org without an existing deployment"
                )
            try:
                created = await client.create_deployment(
                    provider="algenta_shared",
                    region="algenta-shared",
                    config={"instance_size": "small"},
                    billing_markup_pct=20.0,
                )
            except DecisionEngineError as exc:
                raise_if_deployment_mutation_blocked(exc)
                raise
            assert created.deployment_id
            assert created.provider == "algenta_shared"
            assert created.region == "algenta-shared"
            assert created.status in {"requested", "provisioning", "active"}

            cost = await client.get_deployment_cost(created.deployment_id)
            assert cost.deployment_id == created.deployment_id
            assert cost.provider == created.provider
            assert cost.billable_cost_usd_month >= cost.cost_usd_month

            deleted = await client.delete_deployment(created.deployment_id)
            assert deleted.deployment_id == created.deployment_id
            assert deleted.status in {"deprovisioning", "deleted"}

    asyncio.run(_run())


check(
    "AsyncClient deployment create/delete lifecycle → typed live results",
    test_async_deployment_lifecycle_surface,
)


def test_async_account_surface():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            me = await client.me()
            assert me.user.email
            assert me.org.name

            usage = await client.usage()
            assert usage.billing_period
            assert usage.api_calls >= 0

            limits = await client.limits()
            assert isinstance(limits, dict), type(limits)
            assert any(
                key in limits for key in ("plan", "simulations_per_month", "rate_limit_per_minute")
            ), limits

            distributions = await client.distributions()
            assert distributions.total >= len(distributions.distributions)
            assert distributions.distributions

            templates = await client.templates()
            assert templates.total >= len(templates.templates)
            assert templates.templates

            listed_before = await client.list_api_keys()
            before_ids = {str(item.id) for item in listed_before}

            label = f"python-sdk-live-async-{time.time_ns()}"
            created_id: str | None = None
            try:
                created, requested_device_limit = await _create_live_api_key_with_plan_fallback_async(
                    client,
                    label=label,
                )
                created_id = str(created["id"])
                assert created["label"] == label
                assert created["device_limit"] == requested_device_limit
                assert created["raw_key"].startswith("de_live_"), created

                listed_after = await client.list_api_keys()
                after_ids = {str(item.id) for item in listed_after}
                assert created_id in after_ids, (created_id, after_ids)
                created_entry = next(
                    (item for item in listed_after if str(item.id) == created_id),
                    None,
                )
                assert created_entry is not None
                assert created_entry.device_limit == requested_device_limit

                revoke_result = await client.revoke_api_key(created_id)
                assert revoke_result == {} or revoke_result.get("revoked") is True, revoke_result
                created_id = None

                listed_final = await client.list_api_keys()
                final_ids = {str(item.id) for item in listed_final}
                assert before_ids.issubset(final_ids), (before_ids, final_ids)
                assert label not in {item.label for item in listed_final}
            finally:
                if created_id is not None:
                    await client.revoke_api_key(created_id)

    asyncio.run(_run())


check("AsyncClient account/API-key surface → typed live results", test_async_account_surface)


def test_async_dataset_surface():
    async def _run():
        with static_json_server(default_refreshable_dataset_payload()) as source_url:
            async with AsyncDecisionEngineClient(
                api_key=API_KEY, base_url=BASE_URL, max_retries=0
            ) as client:
                preview_tested = await client.preview_test_connector(
                    connector_type="rest",
                    config={"url": source_url, "data_path": "items"},
                )
                assert preview_tested.success is True
                assert preview_tested.status == "live"

                preview_browsed = await client.preview_browse_connector(
                    connector_type="rest",
                    config={"url": source_url, "data_path": "items"},
                )
                assert preview_browsed.connector_type == "rest"
                assert preview_browsed.total >= 1

                connector = await client.create_connector(
                    **_live_saved_connector_request("python-sdk-async-connector", source_url)
                )
                connector_id = connector.id
                connector_name = connector.name
                assert connector_id
                assert connector_name
                try:
                    connectors = await client.list_connectors(page=1, limit=50)
                    assert connectors.page == 1
                    assert connectors.limit == 50
                    assert connectors.total >= len(connectors.connectors)
                    assert connectors.pages >= 1
                    assert any(item.id == connector_id for item in connectors.connectors)

                    detail = await client.get_connector(connector_id)
                    assert detail.id == connector_id
                    assert detail.name == connector_name

                    updated = await client.update_connector(
                        connector_id,
                        description="Live Python Async SDK connector updated description.",
                    )
                    assert updated.id == connector_id
                    assert updated.description == "Live Python Async SDK connector updated description."

                    tested = await client.test_connector(connector_id)
                    assert tested.success is True
                    assert tested.status == "live"

                    browsed = await client.browse_connector(connector_id)
                    assert browsed.connector_type == "rest"
                    assert browsed.total >= 1

                    created = await client.connect_data(
                        **_live_refreshable_dataset_request("python-sdk-async-dataset", source_url)
                    )
                    dataset_id = created.dataset_id
                    dataset_name = created.dataset_name
                    assert created.status == "ready"
                    assert dataset_id
                    assert dataset_name

                    try:
                        listed = await client.list_datasets(search=dataset_name, compact=True)
                        assert listed.total >= len(listed.datasets)
                        assert any(item.dataset_id == dataset_id for item in listed.datasets)

                        refreshed = await client.refresh_dataset(dataset_id)
                        assert refreshed.status == "ready"
                        assert refreshed.dataset_id == dataset_id

                        summary = await client.get_dataset_summary(dataset_id)
                        assert summary.dataset_id == dataset_id
                        assert summary.name == dataset_name
                        assert summary.column_count >= 2

                        detail = await client.get_dataset(dataset_id)
                        assert detail.dataset.dataset_id == dataset_id
                        assert detail.dataset.dataset_name == dataset_name
                        assert isinstance(detail.schema, dict)
                        assert len(detail.schema.get("columns", [])) >= 2
                    finally:
                        deleted = await client.delete_dataset(dataset_id)
                        assert deleted.dataset_id == dataset_id
                        assert deleted.status == "deleted"
                finally:
                    await client.delete_connector(connector_id)

    asyncio.run(_run())


check("AsyncClient saved connector + dataset lifecycle → typed live results", test_async_dataset_surface)


def test_async_repository_surface():
    reason = local_repository_live_support_reason(BASE_URL)
    if reason is not None:
        raise EnvironmentBlocked(reason)

    async def _run() -> None:
        repository_id: str | None = None
        with live_repository_fixture("python-sdk-async") as repository_fixture:
            async with AsyncDecisionEngineClient(
                api_key=API_KEY,
                base_url=BASE_URL,
                max_retries=0,
            ) as client:
                capabilities = await client.get_repository_intelligence_capabilities()
                assert_repository_intelligence_capabilities_payload(capabilities)
                created_connector = await client.create_connector(
                    **repository_fixture.connector_request
                )
                repository_id = str(created_connector.id)
                assert created_connector.connector_type == "local_repo"
                try:
                    snapshot = await client.create_repository_snapshot(
                        repository_id,
                        repository_fixture.snapshot_request,
                    )
                    fetched_snapshot = await client.get_repository_snapshot(
                        repository_id,
                        snapshot.snapshot_id,
                    )
                    repeated_snapshot = await client.create_repository_snapshot(
                        repository_id,
                        repository_fixture.snapshot_request,
                    )

                    assert snapshot.connector_type == "local_repo"
                    assert snapshot.file_count >= 2
                    assert fetched_snapshot.snapshot_id == snapshot.snapshot_id
                    assert fetched_snapshot.content_hash == snapshot.content_hash
                    assert repeated_snapshot.snapshot_id == snapshot.snapshot_id
                    assert repeated_snapshot.status == "existing"

                    triage = await client.triage_repository(
                        repository_id,
                        repository_fixture.triage_request(snapshot.snapshot_id),
                    )
                    assert triage.snapshot_id == snapshot.snapshot_id
                    assert triage.workspace_evidence_bundle_ref
                    assert triage.reduction_ratio >= 1.0
                    assert triage.evidence_items
                    assert triage.suspect_files[0] == repository_fixture.primary_file
                    assert (
                        triage.workspace_evidence_bundle_artifact.artifact_kind
                        == "WorkspaceEvidenceBundle"
                    )

                    graph = await client.query_repository_graph(
                        repository_id,
                        repository_fixture.graph_query_request(
                            snapshot.snapshot_id,
                            triage.workspace_evidence_bundle_ref,
                        ),
                    )
                    assert graph.snapshot_id == snapshot.snapshot_id
                    assert repository_fixture.primary_file in graph.seed_file_paths
                    assert repository_fixture.primary_file in graph.impacted_files
                    assert graph.graph_nodes
                    assert graph.top_change_risk_files

                    try:
                        decision_plan = await client.create_repository_decision_plan(
                            repository_id,
                            repository_fixture.decision_plan_request(
                                snapshot.snapshot_id,
                                triage.workspace_evidence_bundle_ref,
                            ),
                        )
                    except DecisionEngineError as exc:
                        _assert_repository_error(
                            exc,
                            status_code=503,
                            error_code="repository_model_unavailable",
                        )
                        return

                    repository_analysis = decision_plan.decision_plan.repository_analysis
                    assert decision_plan.decision_plan_id
                    assert repository_analysis is not None
                    assert (
                        repository_analysis.planner_model_id
                        == "repository.deterministic_local_v1"
                    )
                    assert repository_analysis.planner_execution_mode == "deterministic_local"
                    assert repository_analysis.planner_provider_backend is None
                    assert repository_analysis.generated_patch_ref
                    assert repository_analysis.patch_impact_report_ref
                    assert (
                        repository_analysis.token_reduction_metrics.reduction_ratio >= 1.0
                    )

                    try:
                        simulation = await client.simulate_repository(
                            repository_id,
                            repository_fixture.simulation_request(
                                snapshot.snapshot_id,
                                decision_plan.decision_plan_id,
                            ),
                        )
                    except DecisionEngineError as exc:
                        raise_if_simulation_capacity_blocked(exc)
                        raise

                    validated_inputs = simulation.validated_inputs or {}
                    simulation_id = str(validated_inputs.get("simulation_id") or "")
                    apply_gate = (simulation.score_breakdown or {}).get("apply_gate", {})
                    assert simulation_id
                    assert simulation.decision_plan is not None
                    assert isinstance(apply_gate, dict)
                    assert apply_gate.get("policy_snapshot_id")

                    branch_name = "algenta/live-repository-fix"
                    apply_request = repository_fixture.apply_local_branch_request(
                        snapshot.snapshot_id,
                        decision_plan.decision_plan_id,
                        simulation_id,
                        branch_name=branch_name,
                    )
                    if bool(apply_gate.get("passed")):
                        applied = await client.apply_repository(repository_id, apply_request)
                        assert applied.mode == "local_branch"
                        assert applied.applied is True
                        assert applied.patch
                        assert applied.branch_name == branch_name
                        assert applied.commit_sha
                        assert applied.local_checkout_path
                        repository_fixture.assert_local_branch_applied(
                            branch_name=branch_name,
                            checkout_path=applied.local_checkout_path,
                        )
                        assert repository_fixture.primary_file in applied.validation_summary.get(
                            "patch_files", []
                        )
                    else:
                        try:
                            await client.apply_repository(repository_id, apply_request)
                        except DecisionEngineError as exc:
                            _assert_repository_error(
                                exc,
                                status_code=409,
                                error_code="repository_apply_gate_failed",
                            )
                        else:
                            raise AssertionError(
                                "Repository apply should fail when the apply gate does not pass."
                            )
                finally:
                    if repository_id is not None:
                        await client.delete_connector(repository_id)

    asyncio.run(_run())


check("AsyncClient repository intelligence surface → typed live results", test_async_repository_surface)


def test_async_control_plane_surface():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            team = await client.list_team_members(page=1, limit=50)
            assert team.page == 1
            assert team.limit == 50
            assert team.total >= len(team.members)
            assert team.pages >= 1
            assert team.members
            assert team.members[0].email
            assert team.members[0].role

            jobs = await client.list_jobs(page=1, limit=5, status="queued")
            assert jobs.page == 1
            assert jobs.limit == 5
            assert jobs.total >= len(jobs.jobs)
            assert jobs.pages >= 1
            for job in jobs.jobs:
                assert job.status == "queued", job
                assert job.queue_name

            for op in (
                lambda: client.get_job(MISSING_JOB_ID),
                lambda: client.get_job_result(MISSING_JOB_ID),
                lambda: client.cancel_job(MISSING_JOB_ID),
                lambda: client.poll_job(MISSING_JOB_ID, timeout=0.1, poll_interval=0.01),
            ):
                try:
                    await op()
                except DecisionEngineError as exc:
                    _assert_missing_job_error(exc)
                else:
                    raise AssertionError(
                        "Expected missing-job async operation to fail with structured 404"
                    )

            billing = await client.get_billing_info()
            assert billing.plan
            assert billing.subscription_status in {
                None,
                "active",
                "trialing",
                "past_due",
                "canceled",
                "incomplete",
            }

            try:
                credits = await client.refresh_credits(
                    **_live_credit_refresh_request("python-sdk-live-async")
                )
            except DecisionEngineError as exc:
                raise_if_credit_refresh_blocked(exc)
                raise
            assert credits.billing_period == _current_billing_period()
            assert credits.credits_granted >= 0
            assert credits.credits_issued_this_month >= credits.credits_granted
            assert credits.monthly_limit >= 0
            assert credits.monthly_remaining >= 0
            assert credits.refresh_after >= credits.server_time
            assert credits.expires_at >= credits.refresh_after

            metering = await client.ingest_metering_events(
                device_id=f"python-sdk-live-async-{time.time_ns()}",
                events=_live_metering_events(),
            )
            assert metering.accepted == 1
            assert metering.billing_period

            with webhook_receiver() as (callback_url, deliveries):
                webhook = await client.test_webhook_delivery(callback_url)
                assert webhook["success"] is True
                assert webhook["status_code"] == 200
                assert deliveries, "Expected one webhook delivery to local receiver"
                assert deliveries[0]["path"] == "/webhook", deliveries[0]

            devices = await client.list_devices(page=1, limit=25)
            assert devices.page == 1
            assert devices.limit == 25
            assert devices.total >= len(devices.devices)
            assert devices.pages >= 1
            assert devices.device_count == len(devices.devices)
            assert devices.plan

            logs = await client.get_audit_logs(page=1, limit=20)
            assert logs.page == 1
            assert logs.limit == 20
            assert logs.total >= len(logs.entries)
            assert logs.pages >= 1
            assert logs.entries
            assert logs.entries[0].action
            assert logs.entries[0].resource_type
            assert logs.entries[0].result in {"success", "failure"}

            policy = await client.get_execution_policy()
            assert 0 <= policy.min_confidence <= 1
            assert isinstance(policy.require_calibration, bool)
            assert isinstance(policy.allow_reexecution, bool)
            assert policy.updated_at

            snapshots = await client.list_execution_policy_snapshots()
            assert snapshots.total_snapshots >= len(snapshots.data)
            if snapshots.data:
                assert snapshots.data[0].snapshot_id
                assert snapshots.data[0].revision >= 1

            updated = await client.update_execution_policy(
                min_confidence=policy.min_confidence,
                risk_floor=policy.risk_floor,
                require_calibration=policy.require_calibration,
                allow_reexecution=policy.allow_reexecution,
            )
            assert updated.min_confidence == policy.min_confidence
            assert updated.risk_floor == policy.risk_floor
            assert updated.require_calibration == policy.require_calibration
            assert updated.allow_reexecution == policy.allow_reexecution

    asyncio.run(_run())


check(
    "AsyncClient team/credits/metering/audit/execution-policy helpers → typed live results",
    test_async_control_plane_surface,
)


def test_async_trigger_surface():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            created = await client.register_trigger(
                **_live_trigger_request(f"python-sdk-async-{time.time_ns()}")
            )
            trigger_id = created.trigger_id
            try:
                assert trigger_id
                assert created.status == "active"

                listed = await client.list_triggers(status="all", page=1, limit=25)
                assert listed.page == 1
                assert listed.limit == 25
                assert listed.total >= len(listed.triggers)
                assert any(item.trigger_id == trigger_id for item in listed.triggers)

                fired = await client.fire_trigger(trigger_id, force=False)
                assert fired.trigger_id == trigger_id
                assert fired.condition_met is False
                assert fired.fired is False

                paused = await client.pause_trigger(trigger_id, paused=True)
                assert paused.trigger_id == trigger_id
                assert paused.status == "paused"

                resumed = await client.pause_trigger(trigger_id, paused=False)
                assert resumed.trigger_id == trigger_id
                assert resumed.status == "active"
            finally:
                deleted = await client.delete_trigger(trigger_id)
                assert deleted.trigger_id == trigger_id
                assert deleted.deleted is True

    asyncio.run(_run())


check("AsyncClient trigger lifecycle → typed live results", test_async_trigger_surface)


def test_async_product_surface():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            try:
                decision = await client.product_decision(
                    {
                        "inputs": [
                            {
                                "name": "revenue",
                                "value": 120000.0,
                                "low": 100000.0,
                                "high": 150000.0,
                                "unit": "USD",
                            },
                            {
                                "name": "cost",
                                "value": 70000.0,
                                "low": 60000.0,
                                "high": 90000.0,
                                "unit": "USD",
                            },
                        ],
                        "risk_tolerance": "medium",
                        "scenarios": 1000,
                    }
                )
                agent_run = await client.product_agent_run(
                    {
                        "task": f"Summarize benchmark blockers {time.time_ns()}",
                        "tools": ["search"],
                        "max_steps": 3,
                    }
                )
                optimize = await client.product_optimize(
                    {
                        "objective": "maximize profit",
                        "variables": [
                            {"name": "price", "min": 50.0, "max": 150.0},
                            {"name": "discount", "min": 0.0, "max": 0.2},
                        ],
                        "iterations": 100,
                    }
                )
                retrieve = await client.product_retrieve(
                    {
                        "query": "launch checklist",
                        "documents": [
                            {"id": "doc_1", "content": "Launch checklist for product release."},
                            {"id": "doc_2", "content": "Pricing review for launch approval."},
                        ],
                        "top_k": 2,
                    }
                )
                forecast = await client.product_forecast(
                    {
                        "metric": "monthly_revenue",
                        "history": [100.0, 120.0, 130.0, 140.0],
                        "horizon": 3,
                    }
                )
            except DecisionEngineError as exc:
                raise_if_simulation_capacity_blocked(exc)
                raise
            assert decision.action
            assert 0 <= decision.confidence <= 1
            assert agent_run.run_id
            assert agent_run.status in {"completed", "requires_approval", "running"}
            assert optimize.status == "completed"
            assert optimize.optimal_values
            assert retrieve.results
            assert retrieve.results[0].content
            assert forecast.forecast_mean >= 0
            assert forecast.periods

    asyncio.run(_run())


check("AsyncClient product routes → typed live results", test_async_product_surface)


def test_async_llm_streaming_surface():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            chat_chunks = [
                chunk
                async for chunk in client.stream_chat_completions(
                    [{"role": "user", "content": "summarize alpha beta gamma"}]
                )
            ]
            assert len(chat_chunks) >= 2
            assert chat_chunks[0].choices[0].delta.role == "assistant"
            assert chat_chunks[-1].choices[0].finish_reason == "stop"

            response_events = [event async for event in client.stream_responses("alpha beta")]
            assert len(response_events) == 3
            assert response_events[0].type == "response.created"
            assert response_events[2].response is not None
            assert response_events[2].response.status == "completed"

    asyncio.run(_run())


check("AsyncClient streaming LLM routes → typed SSE live results", test_async_llm_streaming_surface)


def test_async_bad_key():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key="de_live_INVALID_KEY_FAKE", base_url=BASE_URL, max_retries=0
        ) as client:
            raised = False
            try:
                await client.simulate(
                    mode="auto",
                    runs=100,
                    scenario={
                        "variables": {"x": {"low": 0, "high": 100}},
                        "objective": "maximize_net_value",
                    },
                )
            except AuthenticationError:
                raised = True
            assert raised, "Expected AuthenticationError"

    asyncio.run(_run())


check("AsyncClient bad key → AuthenticationError", test_async_bad_key)


def test_async_concurrent_simulations():
    """Run 3 simulations concurrently via the async client."""

    async def _run():
        async with AsyncDecisionEngineClient(
            api_key=API_KEY, base_url=BASE_URL, max_retries=0
        ) as client:
            tasks = []
            for i in range(3):
                tasks.append(
                    client.simulate(
                        mode="auto",
                        runs=100,
                        scenario={
                            "variables": {"x": {"low": 0, "high": 100 * (i + 1)}},
                            "objective": "maximize_net_value",
                        },
                    )
                )
            try:
                results_list = await asyncio.gather(*tasks)
            except DecisionEngineError as exc:
                raise_if_simulation_capacity_blocked(exc)
                raise
            assert len(results_list) == 3, f"Expected 3 results, got {len(results_list)}"
            for r in results_list:
                assert isinstance(r, DecisionEnvelope)
                assert r.status == "completed"

    asyncio.run(_run())


check("AsyncClient 3 concurrent simulations → all completed", test_async_concurrent_simulations)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULTS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  RESULTS SUMMARY — Python SDK Integration Tests")
print("=" * 70)

passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
skipped = sum(1 for r in results if r[0] == SKIP)
total = len(results)

print(f"\n  Total:  {total} tests")
print(f"  Passed: {passed} {PASS}")
print(f"  Failed: {failed} {FAIL}")
print(f"  Skipped: {skipped} {SKIP}")

if failed > 0:
    print("\n  ── Failures ──")
    for r in results:
        if r[0] == FAIL:
            print(f"    {FAIL} {r[1]}: {r[2] if len(r) > 2 else ''}")

if skipped > 0:
    print("\n  ── Skips ──")
    for r in results:
        if r[0] == SKIP:
            print(f"    {SKIP} {r[1]}: {r[2] if len(r) > 2 else ''}")

print(f"\n{'=' * 70}")
if failed == 0:
    print(f"  🎉 ALL {passed} SDK TESTS PASSED!")
else:
    print(f"  ⚠️  {failed}/{total} FAILURES")
print(f"{'=' * 70}\n")

artifact_path = write_live_integration_summary(
    SUITE_NAME,
    script="tests/integration/test_python_sdk.py",
    passed=passed,
    failed=failed,
    skipped=skipped,
    total=total,
    elapsed_seconds=time.perf_counter() - STARTED,
    details={
        "api_key_configured": API_KEY_CONFIGURED,
        "base_url": BASE_URL,
        "failed_checks": [result[1] for result in results if result[0] == FAIL],
    },
)
print(f"Summary artifact: {artifact_path}")

sys.exit(1 if failed > 0 else 0)
