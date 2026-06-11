"""
Live AlgentaClient integration tests against a real API server.

This validates the direct cloud wrapper path:
  - AlgentaClient health and usage helpers
  - governed contract and runtime-proof routes
  - decision runtime helpers
  - plan-aligned LLM utility routes
  - quota-aware decision planning, agent-runs, and bound cloud simulate path

Run:
  DE_API_KEY="..." python3 tests/integration/test_algenta_client_live.py
"""

from __future__ import annotations

import os
import sys

if __name__ == "__main__" and os.environ.get("ALGENTA_SKIP_MOJO_RUNTIME", "0") == "1":
    print("[skip] tests/integration/test_algenta_client_live.py — ALGENTA_SKIP_MOJO_RUNTIME=1")
    sys.exit(0)


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
from pathlib import Path
from typing import Any

import httpx

socket.setdefaulttimeout(15)

ROOT = Path(__file__).resolve().parents[2]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

# ruff: noqa: E402
from algenta import AlgentaClient  # noqa: E402
from decision_engine import DecisionEngineError  # noqa: E402

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
SUITE_NAME = "algenta_client_live"
STARTED = time.perf_counter()
ACTIVE_LIVE_CHECK_FILTER = selected_live_check_filter()
ACTIVE_LIVE_CHECK_FILTER_TOKENS = live_check_filter_tokens(ACTIVE_LIVE_CHECK_FILTER)
_runtime_proc: subprocess.Popen[str] | None = None
_runtime_started_here = False
_runtime_log_path: Path | None = None

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple[str, str, str]] = []


class EnvironmentBlocked(RuntimeError):  # noqa: N818
    """Raised when live capacity or quota blocks this integration path."""


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


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


def _create_live_api_key_with_plan_fallback(
    client: AlgentaClient,
    *,
    label: str,
) -> tuple[dict[str, Any], int]:
    requested_device_limit = 2
    try:
        created = client.create_api_key(name=label, device_limit=requested_device_limit)
    except DecisionEngineError as exc:
        if exc.status_code != 400 or exc.error_code != "invalid_device_limit":
            raise
        requested_device_limit = 0
        created = client.create_api_key(name=label)
    return created, requested_device_limit


def _live_metering_events() -> list[dict[str, object]]:
    return [
        {
            "event_type": "runtime_call",
            "module": "integration",
            "function": "algenta_client_live",
            "engine_used": "python",
            "latency_ms": 15.0,
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
        "description": "Live AlgentaClient trigger lifecycle check.",
        "auto_execute": False,
    }


def _live_refreshable_dataset_request(prefix: str, source_url: str) -> dict[str, object]:
    dataset_name = f"{prefix}-{time.time_ns()}"
    return {
        "connection_type": "api",
        "provider": "rest",
        "dataset_name": dataset_name,
        "description": "Live AlgentaClient refreshable dataset check.",
        "connection_config": {
            "url": source_url,
            "data_path": "items",
        },
    }


def _live_saved_connector_request(prefix: str, source_url: str) -> dict[str, object]:
    return {
        "name": f"{prefix}-{time.time_ns()}",
        "connector_type": "rest",
        "description": "Live AlgentaClient saved connector check.",
        "config": {
            "url": source_url,
            "data_path": "items",
        },
    }


def _assert_repository_error(
    exc: Exception,
    *,
    status_code: int,
    error_code: str,
) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    resolved_status: int | None = None
    resolved_code: str | None = None
    if isinstance(exc, DecisionEngineError):
        payload = exc.response_body if isinstance(exc.response_body, dict) else {}
        resolved_status = exc.status_code
        resolved_code = exc.error_code
    elif isinstance(exc, httpx.HTTPStatusError):
        resolved_status = exc.response.status_code
        try:
            response_payload = exc.response.json()
        except Exception:
            response_payload = {}
        payload = response_payload if isinstance(response_payload, dict) else {}
    assert resolved_status == status_code, exc
    if resolved_code is not None:
        assert resolved_code == error_code, exc
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    error = detail.get("error", detail) if isinstance(detail, dict) else None
    assert isinstance(error, dict), payload
    assert error.get("code") == error_code, payload
    return error


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


def _probe_json(base_url: str, path: str, timeout: float = 3.0):
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
            status, _body = _probe_json(base_url, "/v1/health", timeout=2.0)
            if status == 200:
                return
            last_error = f"status {status}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for {base_url}/v1/health: {last_error}.{_read_log(log_path)}"
    )


def _endpoint_serves_canonical_algenta_client_surface(base_url: str) -> bool:
    try:
        status, health = _probe_json(base_url, "/v1/health", timeout=3.0)
        if status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
            return False
        status, contract = _probe_json(base_url, "/v1/meta/contract", timeout=5.0)
        if status != 200 or not isinstance(contract, dict):
            return False
        if not contract_integrations_match_manifest(contract["integrations"]):
            return False
        privacy_registry = contract.get("privacy_registry")
        if not isinstance(privacy_registry, dict):
            return False
        if not isinstance(privacy_registry.get("vendor_telemetry_hosts"), list):
            return False
        if not isinstance(privacy_registry.get("private_host_suffixes"), list):
            return False
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
            ("/v1/recommend", "post"),
            ("/v1/score", "post"),
            ("/v1/batch", "post"),
            ("/v1/compare", "post"),
            ("/v1/models", "get"),
            ("/v1/artifacts/resolve", "post"),
            ("/v1/tokenize", "post"),
            ("/v1/count_tokens", "post"),
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
            ("/v1/me", "get"),
            ("/v1/me", "patch"),
            ("/v1/limits", "get"),
            ("/v1/distributions", "get"),
            ("/v1/templates", "get"),
            ("/v1/billing/info", "get"),
            ("/v1/api-keys", "get"),
            ("/v1/api-keys", "post"),
            ("/v1/webhooks/test", "post"),
            ("/v1/metering", "post"),
            ("/v1/credits/refresh", "post"),
            ("/v1/jobs", "post"),
            ("/v1/jobs/{job_id}", "get"),
            ("/v1/jobs/{job_id}/result", "get"),
            ("/v1/jobs/{job_id}/cancel", "post"),
            ("/v1/triggers", "get"),
            ("/v1/triggers", "post"),
            ("/v1/triggers/{trigger_id}/fire", "post"),
            ("/v1/triggers/{trigger_id}/pause", "patch"),
            ("/v1/triggers/{trigger_id}", "delete"),
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
    log_dir = Path(tempfile.mkdtemp(prefix="integration-algenta-client-"))
    log_path = log_dir / "api_server.log"

    if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):
        try:
            _wait_for_health(base_url, log_path, timeout_seconds=5.0)
            if _endpoint_serves_canonical_algenta_client_surface(base_url):
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


def _capacity_reason_from_exception(exc: Exception) -> str | None:
    if isinstance(exc, DecisionEngineError):
        return classify_simulation_capacity_blocker(
            status=exc.status_code,
            payload=exc.response_body,
            text=str(exc),
        )
    if isinstance(exc, httpx.HTTPStatusError):
        payload: dict[str, Any] | None = None
        try:
            payload = exc.response.json()
        except Exception:
            payload = None
        return classify_simulation_capacity_blocker(
            status=exc.response.status_code,
            payload=payload,
            text=str(exc),
        )
    status = getattr(exc, "status_code", None)
    payload = getattr(exc, "response_body", None)
    return classify_simulation_capacity_blocker(
        status=status if isinstance(status, int) else None,
        payload=payload,
        text=str(exc),
    )


def raise_if_capacity_blocked(exc: Exception) -> None:
    reason = _capacity_reason_from_exception(exc)
    if reason:
        raise EnvironmentBlocked(reason) from exc


def raise_if_deployment_mutation_blocked(exc: Exception) -> None:
    if isinstance(exc, DecisionEngineError):
        payload = exc.response_body if isinstance(exc.response_body, dict) else {}
        error = payload.get("error") if isinstance(payload, dict) else {}
        code = error.get("code") if isinstance(error, dict) else None
        if exc.status_code == 403:
            raise EnvironmentBlocked("deployment mutation requires owner role") from exc
        if exc.status_code == 409 or code == "deployment_exists":
            raise EnvironmentBlocked(
                "deployment mutation requires an org without an existing deployment"
            ) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        payload: Any = None
        try:
            payload = exc.response.json()
        except Exception:
            payload = None
        error = payload.get("error") if isinstance(payload, dict) else {}
        code = error.get("code") if isinstance(error, dict) else None
        if exc.response.status_code == 403:
            raise EnvironmentBlocked("deployment mutation requires owner role") from exc
        if exc.response.status_code == 409 or code == "deployment_exists":
            raise EnvironmentBlocked(
                "deployment mutation requires an org without an existing deployment"
            ) from exc


def raise_if_credit_refresh_blocked(exc: Exception) -> None:
    status: int | None = None
    payload: Any = None
    if isinstance(exc, DecisionEngineError):
        status = exc.status_code
        payload = exc.response_body
    elif isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            payload = exc.response.json()
        except Exception:
            payload = None
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else None
    code = None
    if isinstance(detail, dict):
        raw_code = detail.get("error", detail.get("code"))
        if isinstance(raw_code, str):
            code = raw_code
    text = str(exc).lower()
    if status == 429 and code in {"quota_exhausted", "quota_exceeded"}:
        raise EnvironmentBlocked("credit refresh quota exhausted for this live environment") from exc
    if status == 429 and ("quota_exhausted" in text or "quota_exceeded" in text):
        raise EnvironmentBlocked("credit refresh quota exhausted for this live environment") from exc


def raise_if_artifact_bridge_blocked(exc: Exception) -> None:
    payload: Any = None
    if isinstance(exc, DecisionEngineError):
        payload = exc.response_body
    elif isinstance(exc, httpx.HTTPStatusError):
        try:
            payload = exc.response.json()
        except Exception:
            payload = None
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else {}
    code = detail.get("code") if isinstance(detail, dict) else None
    if code == "artifact_bridge_backend_unavailable":
        raise EnvironmentBlocked(
            "artifact bridge requires the optional huggingface_hub backend in this checkout"
        ) from exc


def _missing_live_api_key_reason(exc: BaseException) -> str | None:
    if API_KEY_CONFIGURED:
        return None
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        payload: Any = None
        try:
            payload = exc.response.json()
        except Exception:
            payload = None
        error = payload.get("error") if isinstance(payload, dict) else None
        if status == 401 or (isinstance(error, dict) and error.get("code") == "invalid_api_key"):
            return (
                "DE_API_KEY is not set; skipping authenticated AlgentaClient checks that require a "
                "real live key."
            )
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status == 401:
        return (
            "DE_API_KEY is not set; skipping authenticated AlgentaClient checks that require a "
            "real live key."
        )
    text = str(exc)
    if "invalid_api_key" in text or "invalid, expired, or has been revoked" in text:
        return (
            "DE_API_KEY is not set; skipping authenticated AlgentaClient checks that require a "
            "real live key."
        )
    return None


def check(name: str, fn) -> None:
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    if not should_run_live_check(name, ACTIVE_LIVE_CHECK_FILTER_TOKENS):
        reason = filtered_live_check_reason(ACTIVE_LIVE_CHECK_FILTER)
        results.append((SKIP, name, reason))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {reason}")
        return
    try:
        fn()
        results.append((PASS, name, ""))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except EnvironmentBlocked as exc:
        results.append((SKIP, name, str(exc)))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
    except AssertionError as exc:
        missing_key_reason = _missing_live_api_key_reason(exc)
        if missing_key_reason:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
                f"{missing_key_reason}"
            )
            return
        results.append((FAIL, name, str(exc)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
    except Exception as exc:  # noqa: BLE001
        missing_key_reason = _missing_live_api_key_reason(exc)
        if missing_key_reason:
            results.append((SKIP, name, missing_key_reason))
            _emit(
                f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
                f"{missing_key_reason}"
            )
            return
        message = f"{type(exc).__name__}: {exc}"
        results.append((FAIL, name, message))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {message}")


def _write_summary() -> Path:
    passed = sum(1 for status, *_ in results if status == PASS)
    failed = sum(1 for status, *_ in results if status == FAIL)
    skipped = sum(1 for status, *_ in results if status == SKIP)
    artifact = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_algenta_client_live.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(results),
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "api_key_configured": API_KEY_CONFIGURED,
            "base_url": BASE_URL,
            "failed_checks": [name for status, name, _ in results if status == FAIL],
            "skipped_checks": [name for status, name, _ in results if status == SKIP],
        },
    )
    _emit(f"\nSummary artifact: {artifact}")
    return artifact


def _preflight() -> None:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live AlgentaClient integration.")
    response = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
    assert response.status_code == 200, f"/v1/health returned {response.status_code}"


def test_client_health_and_usage() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    health = client.health()
    assert health["status"] == "ok", health
    usage = client.usage()
    assert isinstance(usage, dict), type(usage)
    assert "billing_period" in usage, usage


def test_client_account_and_api_key_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)

    me = client.me()
    assert isinstance(me, dict), type(me)
    assert any(key in me for key in ("org_id", "organization", "email", "user", "org")), me

    limits = client.limits()
    assert isinstance(limits, dict), type(limits)

    listed_before = client.list_api_keys()
    assert isinstance(listed_before, list), type(listed_before)
    assert all(not hasattr(item, "raw_key") for item in listed_before)

    created = None
    revoked = False
    label = f"algenta-client-live-{time.time_ns()}"
    requested_device_limit = 0
    try:
        created, requested_device_limit = _create_live_api_key_with_plan_fallback(
            client,
            label=label,
        )
        assert created["label"] == label
        assert created["device_limit"] == requested_device_limit
        assert isinstance(created["raw_key"], str) and created["raw_key"].startswith(created["key_prefix"])

        listed_after = client.list_api_keys()
        created_entry = next((item for item in listed_after if str(item.id) == str(created["id"])), None)
        assert created_entry is not None
        assert created_entry.label == label
        assert created_entry.device_limit == requested_device_limit
        assert not hasattr(created_entry, "raw_key")

        revoke_result = client.revoke_api_key(str(created["id"]))
        revoked = True
        assert revoke_result == {}

        listed_final = client.list_api_keys()
        assert all(str(item.id) != str(created["id"]) for item in listed_final)
    finally:
        if created is not None and not revoked:
            client.revoke_api_key(str(created["id"]))


def test_client_control_plane_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)

    team = client.list_team_members(page=1, limit=50)
    assert team.page == 1
    assert team.limit == 50
    assert team.total >= len(team.members)
    assert team.pages >= 1
    assert team.members
    assert team.members[0].email
    assert team.members[0].role

    billing = client.get_billing_info()
    assert billing.plan
    assert billing.subscription_status in {None, "active", "trialing", "past_due", "canceled", "incomplete"}

    try:
        credits = client.refresh_credits(**_live_credit_refresh_request("algenta-client-live"))
    except Exception as exc:  # noqa: BLE001
        raise_if_credit_refresh_blocked(exc)
        raise
    assert _value(credits, "billing_period") == _current_billing_period()
    assert _value(credits, "credits_granted") >= 0
    assert _value(credits, "credits_issued_this_month") >= _value(credits, "credits_granted")
    assert _value(credits, "monthly_limit") >= 0
    assert _value(credits, "monthly_remaining") >= 0
    assert _value(credits, "refresh_after") >= _value(credits, "server_time")
    assert _value(credits, "expires_at") >= _value(credits, "refresh_after")

    metering = client.ingest_metering_events(
        device_id=f"algenta-client-live-{time.time_ns()}",
        events=_live_metering_events(),
    )
    assert metering.accepted == 1
    assert metering.billing_period

    with webhook_receiver() as (callback_url, deliveries):
        webhook = client.test_webhook_delivery(callback_url)
        assert _value(webhook, "success") is True
        assert _value(webhook, "status_code") == 200
        assert deliveries, "Expected one webhook delivery to local receiver"
        assert deliveries[0]["path"] == "/webhook", deliveries[0]

    distributions = client.distributions()
    assert distributions.total >= len(distributions.distributions)
    assert distributions.distributions
    assert distributions.distributions[0].name

    templates = client.templates()
    assert templates.total >= len(templates.templates)
    assert templates.templates
    assert templates.templates[0].id

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
    assert logs.entries
    assert logs.entries[0].action
    assert logs.entries[0].resource_type
    assert logs.entries[0].result in {"success", "failure"}

    policy = client.get_execution_policy()
    assert 0 <= policy.min_confidence <= 1
    assert isinstance(policy.require_calibration, bool)
    assert isinstance(policy.allow_reexecution, bool)
    assert policy.updated_at

    snapshots = client.list_execution_policy_snapshots()
    snapshot_items = _value(snapshots, "data")
    assert _value(snapshots, "total_snapshots") >= len(snapshot_items)
    if snapshot_items:
        assert _value(snapshot_items[0], "snapshot_id")
        assert _value(snapshot_items[0], "revision") >= 1

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


def test_client_dataset_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        connectors = client.list_connectors(page=1, limit=50)
        connector_items = _value(connectors, "connectors")
        assert _value(connectors, "page") == 1
        assert _value(connectors, "limit") == 50
        assert _value(connectors, "total") >= len(connector_items)
        assert _value(connectors, "pages") >= 1

        created = client.connect_data(
            **_live_refreshable_dataset_request("algenta-client-live-dataset", source_url)
        )
        dataset_id = str(_value(created, "dataset_id"))
        dataset_name = str(_value(created, "dataset_name"))
        assert _value(created, "status") == "ready"
        assert dataset_id

        try:
            listed = client.list_datasets(search=dataset_name, compact=True)
            listed_items = _value(listed, "datasets")
            assert _value(listed, "total") >= len(listed_items)
            assert any(str(_value(item, "dataset_id")) == dataset_id for item in listed_items)

            refreshed = client.refresh_dataset(dataset_id)
            assert str(_value(refreshed, "dataset_id")) == dataset_id
            assert _value(refreshed, "status") == "ready"

            summary = client.get_dataset_summary(dataset_id)
            assert str(_value(summary, "dataset_id")) == dataset_id
            assert _value(summary, "name") == dataset_name
            assert _value(summary, "column_count") >= 2

            detail = client.get_dataset(dataset_id)
            dataset = _value(detail, "dataset")
            schema = _value(detail, "schema")
            assert str(_value(dataset, "dataset_id")) == dataset_id
            assert _value(dataset, "dataset_name") == dataset_name
            assert isinstance(schema, dict)
            assert len(schema.get("columns", [])) >= 2
        finally:
            deleted = client.delete_dataset(dataset_id)
            assert str(_value(deleted, "dataset_id")) == dataset_id
            assert _value(deleted, "status") == "deleted"


def test_client_saved_connector_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    connector_id: str | None = None
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        preview_tested = client.preview_test_connector(
            connector_type="rest",
            config={"url": source_url, "data_path": "items"},
        )
        assert _value(preview_tested, "success") is True
        assert _value(preview_tested, "status") == "live"

        preview_browsed = client.preview_browse_connector(
            connector_type="rest",
            config={"url": source_url, "data_path": "items"},
        )
        assert _value(preview_browsed, "connector_type") == "rest"
        assert _value(preview_browsed, "total") >= 1

        created = client.create_connector(**_live_saved_connector_request("algenta-client-connector", source_url))
        connector_id = str(_value(created, "id"))
        connector_name = str(_value(created, "name"))
        assert connector_id
        assert connector_name

        try:
            listed = client.list_connectors(page=1, limit=25)
            listed_items = _value(listed, "connectors")
            assert _value(listed, "total") >= len(listed_items)
            assert any(str(_value(item, "id")) == connector_id for item in listed_items)

            detail = client.get_connector(connector_id)
            assert str(_value(detail, "id")) == connector_id
            assert _value(detail, "name") == connector_name

            updated = client.update_connector(
                connector_id,
                description="Live AlgentaClient connector updated description.",
            )
            assert str(_value(updated, "id")) == connector_id
            assert _value(updated, "description") == "Live AlgentaClient connector updated description."

            tested = client.test_connector(connector_id)
            assert _value(tested, "success") is True
            assert _value(tested, "status") == "live"

            browsed = client.browse_connector(connector_id)
            assert _value(browsed, "connector_type") == "rest"
            assert _value(browsed, "total") >= 1
        finally:
            if connector_id is not None:
                client.delete_connector(connector_id)


def test_client_repository_surface() -> None:
    reason = local_repository_live_support_reason(BASE_URL)
    if reason is not None:
        raise EnvironmentBlocked(reason)

    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    capabilities = client.get_repository_intelligence_capabilities()
    assert_repository_intelligence_capabilities_payload(capabilities)
    repository_id: str | None = None
    with live_repository_fixture("algenta-client") as repository_fixture:
        created_connector = client.create_connector(**repository_fixture.connector_request)
        repository_id = str(_value(created_connector, "id"))
        assert _value(created_connector, "connector_type") == "local_repo"
        try:
            snapshot = client.create_repository_snapshot(
                repository_id,
                repository_fixture.snapshot_request,
            )
            snapshot_id = str(_value(snapshot, "snapshot_id"))
            fetched_snapshot = client.get_repository_snapshot(repository_id, snapshot_id)
            repeated_snapshot = client.create_repository_snapshot(
                repository_id,
                repository_fixture.snapshot_request,
            )

            assert _value(snapshot, "connector_type") == "local_repo"
            assert _value(snapshot, "file_count") >= 2
            assert str(_value(fetched_snapshot, "snapshot_id")) == snapshot_id
            assert _value(fetched_snapshot, "content_hash") == _value(snapshot, "content_hash")
            assert str(_value(repeated_snapshot, "snapshot_id")) == snapshot_id
            assert _value(repeated_snapshot, "status") == "existing"

            triage = client.triage_repository(
                repository_id,
                repository_fixture.triage_request(snapshot_id),
            )
            suspect_files = _value(triage, "suspect_files")
            assert _value(triage, "workspace_evidence_bundle_ref")
            assert _value(triage, "reduction_ratio") >= 1.0
            assert _value(triage, "evidence_items")
            assert suspect_files[0] == repository_fixture.primary_file
            assert (
                _value(_value(triage, "workspace_evidence_bundle_artifact"), "artifact_kind")
                == "WorkspaceEvidenceBundle"
            )

            graph = client.query_repository_graph(
                repository_id,
                repository_fixture.graph_query_request(
                    snapshot_id,
                    str(_value(triage, "workspace_evidence_bundle_ref")),
                ),
            )
            assert str(_value(graph, "snapshot_id")) == snapshot_id
            assert repository_fixture.primary_file in _value(graph, "seed_file_paths")
            assert repository_fixture.primary_file in _value(graph, "impacted_files")
            assert _value(graph, "graph_nodes")
            assert _value(graph, "top_change_risk_files")

            try:
                decision_plan = client.create_repository_decision_plan(
                    repository_id,
                    repository_fixture.decision_plan_request(
                        snapshot_id,
                        str(_value(triage, "workspace_evidence_bundle_ref")),
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                _assert_repository_error(
                    exc,
                    status_code=503,
                    error_code="repository_model_unavailable",
                )
                return

            decision_plan_id = str(_value(decision_plan, "decision_plan_id"))
            decision_plan_payload = _value(decision_plan, "decision_plan")
            repository_analysis = _value(decision_plan_payload, "repository_analysis")
            assert decision_plan_id
            assert _value(repository_analysis, "planner_model_id") == "repository.deterministic_local_v1"
            assert _value(repository_analysis, "planner_execution_mode") == "deterministic_local"
            assert _value(repository_analysis, "planner_provider_backend") is None
            assert _value(repository_analysis, "generated_patch_ref")
            assert _value(repository_analysis, "patch_impact_report_ref")
            assert (
                _value(
                    _value(repository_analysis, "token_reduction_metrics"),
                    "reduction_ratio",
                )
                >= 1.0
            )

            try:
                simulation = client.simulate_repository(
                    repository_id,
                    repository_fixture.simulation_request(snapshot_id, decision_plan_id),
                )
            except Exception as exc:  # noqa: BLE001
                raise_if_capacity_blocked(exc)
                raise

            validated_inputs = _value(simulation, "validated_inputs") or {}
            score_breakdown = _value(simulation, "score_breakdown") or {}
            apply_gate = score_breakdown.get("apply_gate", {})
            simulation_id = str(validated_inputs.get("simulation_id") or "")
            assert simulation_id
            assert _value(simulation, "decision_plan") is not None
            assert isinstance(apply_gate, dict)
            assert apply_gate.get("policy_snapshot_id")

            branch_name = "algenta/live-repository-fix"
            apply_request = repository_fixture.apply_local_branch_request(
                snapshot_id,
                decision_plan_id,
                simulation_id,
                branch_name=branch_name,
            )
            if bool(apply_gate.get("passed")):
                applied = client.apply_repository(repository_id, apply_request)
                assert _value(applied, "mode") == "local_branch"
                assert _value(applied, "applied") is True
                assert _value(applied, "patch")
                assert _value(applied, "branch_name") == branch_name
                assert _value(applied, "commit_sha")
                assert _value(applied, "local_checkout_path")
                repository_fixture.assert_local_branch_applied(
                    branch_name=branch_name,
                    checkout_path=str(_value(applied, "local_checkout_path")),
                )
                assert repository_fixture.primary_file in _value(
                    _value(applied, "validation_summary"),
                    "patch_files",
                )
            else:
                try:
                    client.apply_repository(repository_id, apply_request)
                except Exception as exc:  # noqa: BLE001
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


def _value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def test_client_trigger_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    created = client.register_trigger(**_live_trigger_request(f"algenta-client-{time.time_ns()}"))
    trigger_id = str(_value(created, "trigger_id"))
    try:
        assert trigger_id
        assert _value(created, "status") == "active"

        listed = client.list_triggers(status="all", page=1, limit=25)
        listed_triggers = _value(listed, "triggers")
        assert _value(listed, "page") == 1
        assert _value(listed, "limit") == 25
        assert _value(listed, "total") >= len(listed_triggers)
        assert any(str(_value(item, "trigger_id")) == trigger_id for item in listed_triggers)

        fired = client.fire_trigger(trigger_id, force=False)
        assert str(_value(fired, "trigger_id")) == trigger_id
        assert _value(fired, "condition_met") is False
        assert _value(fired, "fired") is False

        paused = client.pause_trigger(trigger_id, paused=True)
        assert _value(paused, "status") == "paused"

        resumed = client.pause_trigger(trigger_id, paused=False)
        assert _value(resumed, "status") == "active"
    finally:
        deleted = client.delete_trigger(trigger_id)
        assert _value(deleted, "deleted") is True


def test_client_jobs_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)

    try:
        submitted = client.submit_job(
            {
                "mode": "auto",
                "scenario": {
                    "variables": {
                        "revenue": {"low": 100000, "high": 130000},
                        "cost": {"low": -90000, "high": -65000},
                    }
                },
            }
        )
        submitted_job_id = submitted["job_id"] if isinstance(submitted, dict) else submitted.job_id
        submitted_poll_url = submitted["poll_url"] if isinstance(submitted, dict) else submitted.poll_url
        status = client.get_job(str(submitted_job_id))
        listed = client.list_jobs(page=1, limit=25, status="queued")
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise

    status_job_id = status["job_id"] if isinstance(status, dict) else status.job_id
    status_value = status["status"] if isinstance(status, dict) else status.status
    assert str(submitted_job_id)
    assert str(submitted_poll_url).endswith(str(submitted_job_id))
    assert str(status_job_id) == str(submitted_job_id)
    assert status_value in {"queued", "running", "completed", "failed", "cancelled"}
    listed_jobs = listed["jobs"] if isinstance(listed, dict) else listed.jobs
    assert isinstance(listed_jobs, list)
    assert len(listed_jobs) >= 0

    if status_value == "completed":
        result = client.get_job_result(str(submitted_job_id))
        assert isinstance(result, dict)
        assert result.get("status") == "completed"


def test_client_contract_and_runtime_proof_routes() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    contract = client.get_contract()
    assert isinstance(contract.api_base_url, str) and contract.api_base_url.startswith("http")
    assert contract.mcp_endpoint.endswith("/mcp/sse")
    assert contract_integrations_match_manifest(contract.integrations)

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
    assert manifest_decision_workflow_completion.description == "decision workflow completion latency"
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
        (entry for entry in benchmarks.quality_gate_benchmark_classes if entry.code.value == "B10"),
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


def test_client_llm_utility_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)

    models = client.list_models()
    _assert_model_catalog_provider_metadata(models)
    model_ids = {item.id for item in models.data}
    assert "text.tokenizer" in model_ids
    assert "text.hash_embedding_v1" in model_ids
    assert "embeddings.cosine_similarity" in model_ids
    try:
        artifact = client.resolve_artifact_bridge(
            repo_id="bert-base-uncased",
            filename="model.safetensors",
            revision="main",
            local_files_only=True,
        )
    except Exception as exc:
        raise_if_artifact_bridge_blocked(exc)
        raise
    assert artifact.status in {"resolved", "not_cached"}
    assert artifact.filename == "model.safetensors"
    if artifact.resolved_path is not None:
        assert artifact.resolved_path

    tokenized = client.tokenize("alpha beta gamma")
    assert tokenized.object == "tokenization"
    assert tokenized.token_count == len(tokenized.tokens) == 3

    counted = client.count_tokens("alpha beta gamma")
    assert counted.object == "token_count"
    assert counted.token_count == 3

    chat = client.chat_completions([{"role": "user", "content": "summarize alpha beta"}])
    assert chat.object == "chat.completion"
    assert chat.choices[0].message.role == "assistant"
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


def test_client_deployment_control_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)

    deployment_regions = client.list_deployment_regions()
    assert deployment_regions.providers
    managed_provider = next(
        (provider for provider in deployment_regions.providers if provider.id == "algenta_shared"),
        None,
    )
    assert managed_provider is not None
    assert managed_provider.regions

    deployment = client.get_deployment()
    if deployment is not None:
        assert deployment.deployment_id
        assert deployment.provider
        deployment_cost = client.get_deployment_cost(deployment.deployment_id)
        assert deployment_cost.deployment_id == deployment.deployment_id
        assert deployment_cost.provider == deployment.provider
        assert deployment_cost.cost_usd_month >= 0


def test_client_deployment_lifecycle_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)

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
    except Exception as exc:  # noqa: BLE001
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
    deleted_deployment_id = (
        deleted.get("deployment_id") if isinstance(deleted, dict) else getattr(deleted, "deployment_id", None)
    )
    deleted_status = deleted.get("status") if isinstance(deleted, dict) else getattr(deleted, "status", None)
    assert deleted_deployment_id == created.deployment_id
    assert deleted_status in {"deprovisioning", "deleted"}


def test_client_decision_runtime_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    try:
        recommendation = client.recommend(
            {
                "options": [
                    {"name": "expand", "expected_value": 140_000, "risk": 0.15},
                    {"name": "hold", "expected_value": 90_000, "risk": 0.08},
                ],
                "runs": 250,
            }
        )
        score = client.score(
            {
                "mode": "expert",
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
            },
            scoring_weights={"expected_value": 0.7, "downside_risk": 0.3},
        )
        batch = client.batch(
            [
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
        )
        compared = client.compare(
            [
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
        )
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise

    assert recommendation["recommended_action"]
    assert len(recommendation["action_results"]) == 2
    assert isinstance(score["score"], int | float)
    assert len(batch) == 2
    assert compared["winner"] in {"base", "stretch"}


def test_client_streaming_llm_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    chat_chunks = list(
        client.stream_chat_completions([{"role": "user", "content": "summarize alpha beta"}])
    )
    assert len(chat_chunks) >= 2
    assert chat_chunks[0].object == "chat.completion.chunk"
    assert chat_chunks[0].choices[0].delta.role == "assistant"
    assert chat_chunks[-1].choices[0].finish_reason == "stop"

    response_events = list(client.stream_responses("alpha beta"))
    assert len(response_events) == 3
    assert response_events[0].type == "response.created"
    assert response_events[1].item is not None
    assert response_events[1].item.content[0].token_count >= 2
    assert response_events[2].response is not None
    assert response_events[2].response.status == "completed"


def test_client_product_surface() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
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
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
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


def test_client_plan_decision_and_agent_runs() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
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
        created = client.create_agent_run(
            task=f"Search benchmark notes {time.time_ns()}",
            tools=["search"],
            approval_mode="manual",
        )
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise

    assert isinstance(plan.recommended_action, str) and plan.recommended_action
    assert 0 <= plan.confidence <= 1
    assert created.status == "requires_approval"
    assert created.pending_action == "approve"

    fetched = client.get_agent_run(created.run_id)
    assert fetched.run_id == created.run_id
    assert fetched.status == "requires_approval"

    events = client.get_agent_run_events(created.run_id, limit=20)
    assert events.run_id == created.run_id
    assert events.total_events >= 3

    approved = client.approve_agent_run(created.run_id)
    assert approved.run_id == created.run_id
    assert approved.status == "completed"
    assert "search" in approved.tools_used


def test_client_agent_run_event_stream() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    try:
        created = client.create_agent_run(
            task=f"Search benchmark notes {time.time_ns()}",
            tools=["search"],
            approval_mode="auto",
        )
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise
    events = list(client.stream_agent_run_events(created.run_id, limit=20))
    assert len(events) >= 2
    assert events[0].type == "agent.run.event"
    assert events[0].event is not None
    assert events[0].event.event_type == "run_created"
    assert events[-1].type == "agent.run.completed"
    assert events[-1].status == "completed"


def test_client_bound_simulate_cloud_path() -> None:
    client = AlgentaClient(api_key=API_KEY, base_url=BASE_URL)
    try:
        result = client.simulate.risk(revenue=120000, cost=-70000, runs=200)
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise

    assert result.engine == "cloud"
    assert result.runs >= 200
    assert isinstance(result.expected_value, int | float)


def main() -> int:
    _emit("\n" + "=" * 70)
    _emit("  LIVE ALGENTA CLIENT INTEGRATION")
    _emit("=" * 70)

    _preflight()

    check("AlgentaClient health() + usage()", test_client_health_and_usage)
    check("AlgentaClient account + API-key surface", test_client_account_and_api_key_surface)
    check("AlgentaClient saved connector lifecycle surface", test_client_saved_connector_surface)
    check("AlgentaClient connectors + dataset lifecycle surface", test_client_dataset_surface)
    check("AlgentaClient repository intelligence surface", test_client_repository_surface)
    check(
        "AlgentaClient team/credits/metering/audit/execution-policy helpers",
        test_client_control_plane_surface,
    )
    check("AlgentaClient async jobs surface", test_client_jobs_surface)
    check("AlgentaClient contract + runtime proof routes", test_client_contract_and_runtime_proof_routes)
    check("AlgentaClient LLM utility surface", test_client_llm_utility_surface)
    check("AlgentaClient trigger lifecycle surface", test_client_trigger_surface)
    check("AlgentaClient deployment control surface", test_client_deployment_control_surface)
    check("AlgentaClient deployment create/delete lifecycle", test_client_deployment_lifecycle_surface)
    check("AlgentaClient decision runtime helpers", test_client_decision_runtime_surface)
    check("AlgentaClient streaming LLM surface", test_client_streaming_llm_surface)
    check("AlgentaClient simplified product surface", test_client_product_surface)
    check("AlgentaClient plan_decision + agent-runs lifecycle", test_client_plan_decision_and_agent_runs)
    check("AlgentaClient agent-run event stream", test_client_agent_run_event_stream)
    check("AlgentaClient bound simulate cloud path", test_client_bound_simulate_cloud_path)

    passed = sum(1 for status, *_ in results if status == PASS)
    skipped = sum(1 for status, *_ in results if status == SKIP)
    failed = sum(1 for status, *_ in results if status == FAIL)

    _emit("\n" + "=" * 70)
    _emit(f"Passed: {passed}")
    _emit(f"Skipped: {skipped}")
    _emit(f"Failed: {failed}")
    if skipped:
        _emit("Skipped:")
        for status, name, detail in results:
            if status == SKIP:
                _emit(f"  - {name}: {detail}")
    if failed:
        _emit("Failures:")
        for status, name, detail in results:
            if status == FAIL:
                _emit(f"  - {name}: {detail}")
    _emit("=" * 70)

    _write_summary()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
