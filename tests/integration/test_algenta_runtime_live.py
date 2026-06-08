"""
Live Python Runtime integration tests against a real API server.

This validates the published primary path:
  - local Runtime import/resolve/query on real repo CSVs
  - API-mode Runtime connect/resolve/verify/query on public REST, S3,
    SQLite, and Postgres descriptors
  - API-mode Runtime decision/LLM/agent plan-aligned surfaces

Run:
  DE_API_KEY="..." DE_BASE_URL="http://127.0.0.1:8000" \
    python3 tests/integration/test_algenta_runtime_live.py
"""

from __future__ import annotations

if __name__ != "__main__":
    import pytest

    pytest.skip(
        "Standalone integration script; run via python tests/integration/test_algenta_runtime_live.py",
        allow_module_level=True,
    )

import os
import sys

if __name__ == "__main__" and os.environ.get("ALGENTA_SKIP_MOJO_RUNTIME", "0") == "1":
    print("[skip] tests/integration/test_algenta_runtime_live.py — ALGENTA_SKIP_MOJO_RUNTIME=1")
    sys.exit(0)

import atexit
import contextlib
import json
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import httpx

socket.setdefaulttimeout(20)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
ROOT = Path(__file__).resolve().parents[2]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
TEST_FILES = ROOT / "test_files"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

# ruff: noqa: E402
from algenta import Runtime
from algenta.runtime import QueryOutput, ResolveOutput, SourceRegistration
from decision_engine import DecisionEngineError

from apps.platform_contract import PlatformContractResponse
from apps.runtime_manifest import (
    RuntimeAdminBenchmarksResponse,
    normalize_runtime_validation_payload,
)
from tests._manifest_backed_integrations import (
    contract_integrations_match_manifest,
)
from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
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
from tests.integration.live_webhook_receiver import webhook_receiver
from tests.integration.runtime_live_db_helpers import (
    postgres_canonical_connector,
    temporary_postgres_fixture,
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
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()
_runtime_proc: subprocess.Popen[str] | None = None
_runtime_started_here = False
_runtime_log_path: Path | None = None

REAL_MARCH_ORDERS = TEST_FILES / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
REAL_MARCH_FINANCIAL = TEST_FILES / "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"
REAL_MARCH_INACCURATE = (
    TEST_FILES
    / "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv"
)
REAL_LOCAL_PARQUET = TEST_FILES / ".algenta_cache" / "BookingsNew.parquet"
REAL_LOCAL_WORKBOOK = TEST_FILES / "QPL Price List_AAR_Expires 20241230.xlsx"

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
        "User-Agent": "algenta-runtime-live/1.0",
        "Accept": "application/geo+json",
    },
    "params": {"state": "CO"},
    "data_path": "features",
    "timeout": 60,
}

PASS = "✅"
SKIP = "⏭️"
FAIL = "❌"
SUITE_NAME = "algenta_runtime_live"
results: list[tuple[str, str, str]] = []


class EnvironmentBlocked(RuntimeError):  # noqa: N818
    """Raised when live capacity constraints prevent this integration path."""


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


def _create_runtime_api_key_with_plan_fallback(
    runtime: Runtime,
    *,
    label: str,
):
    requested_device_limit = 2
    try:
        created = runtime.create_api_key(
            label=label,
            device_limit=requested_device_limit,
        )
    except DecisionEngineError as exc:
        if exc.status_code != 400 or exc.error_code != "invalid_device_limit":
            raise
        requested_device_limit = 0
        created = runtime.create_api_key(label=label)
    return created, requested_device_limit


def _live_metering_events() -> list[dict[str, object]]:
    return [
        {
            "event_type": "runtime_call",
            "module": "integration",
            "function": "algenta_runtime_live",
            "engine_used": "python",
            "latency_ms": 18.0,
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
        "description": "Live Runtime(mode='api') trigger lifecycle check.",
        "auto_execute": False,
    }


def _live_refreshable_runtime_dataset_request(prefix: str, source_url: str) -> dict[str, object]:
    dataset_name = f"{prefix}-{time.time_ns()}"
    return {
        "dataset_name": dataset_name,
        "description": "Live Runtime(mode='api') refreshable dataset check.",
        "connector": {
            "type": "rest",
            "url": source_url,
            "data_path": "items",
        },
    }


def raise_if_capacity_blocked(exc: Exception) -> None:
    status = getattr(exc, "status_code", None)
    payload = getattr(exc, "response_body", None)
    reason = classify_simulation_capacity_blocker(
        status=status if isinstance(status, int) else None,
        payload=payload,
        text=str(exc),
    )
    if reason:
        raise EnvironmentBlocked(reason) from exc


def raise_if_credit_refresh_blocked(exc: Exception) -> None:
    status = getattr(exc, "status_code", None)
    payload = getattr(exc, "response_body", None)
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


def raise_if_deployment_mutation_blocked(exc: Exception) -> None:
    status = getattr(exc, "status_code", None)
    payload = getattr(exc, "response_body", None)
    error = payload.get("error") if isinstance(payload, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(status, int) and status == 403:
        raise EnvironmentBlocked("deployment mutation requires owner role") from exc
    if (isinstance(status, int) and status == 409) or code == "deployment_exists":
        raise EnvironmentBlocked(
            "deployment mutation requires an org without an existing deployment"
        ) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        http_payload: Any = None
        try:
            http_payload = exc.response.json()
        except Exception:
            http_payload = None
        http_error = http_payload.get("error") if isinstance(http_payload, dict) else {}
        http_code = http_error.get("code") if isinstance(http_error, dict) else None
        if exc.response.status_code == 403:
            raise EnvironmentBlocked("deployment mutation requires owner role") from exc
        if exc.response.status_code == 409 or http_code == "deployment_exists":
            raise EnvironmentBlocked(
                "deployment mutation requires an org without an existing deployment"
            ) from exc


def raise_if_artifact_bridge_blocked(exc: Exception) -> None:
    payload: Any = None
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            payload = exc.response.json()
        except Exception:
            payload = None
    else:
        payload = getattr(exc, "response_body", None)
    detail = payload.get("detail", payload.get("error")) if isinstance(payload, dict) else {}
    code = detail.get("code") if isinstance(detail, dict) else None
    if code == "artifact_bridge_backend_unavailable":
        raise EnvironmentBlocked(
            "artifact bridge requires the optional huggingface_hub backend in this checkout"
        ) from exc


def _assert_repository_error(exc: Exception, *, status_code: int, error_code: str) -> None:
    if not isinstance(exc, DecisionEngineError):
        raise AssertionError(f"Expected DecisionEngineError, got {type(exc)!r}") from exc
    assert exc.status_code == status_code
    assert exc.error_code == error_code


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
                "DE_API_KEY is not set; skipping authenticated Runtime(mode='api') checks that "
                "require a real live key."
            )
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status == 401:
        return (
            "DE_API_KEY is not set; skipping authenticated Runtime(mode='api') checks that "
            "require a real live key."
        )
    text = str(exc)
    if "invalid_api_key" in text or "invalid, expired, or has been revoked" in text:
        return (
            "DE_API_KEY is not set; skipping authenticated Runtime(mode='api') checks that "
            "require a real live key."
        )
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
            ("/v1/recommend", "post"),
            ("/v1/score", "post"),
            ("/v1/batch", "post"),
            ("/v1/compare", "post"),
            ("/v1/models", "get"),
            ("/v1/artifacts/resolve", "post"),
            ("/v1/tokenize", "post"),
            ("/v1/count_tokens", "post"),
            ("/v1/me", "get"),
            ("/v1/me", "patch"),
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
            ("/v1/repositories/capabilities", "get"),
            ("/v1/repositories/{repository_id}/snapshots", "post"),
            ("/v1/repositories/{repository_id}/snapshots/{snapshot_id}", "get"),
            ("/v1/repositories/{repository_id}/triage", "post"),
            ("/v1/repositories/{repository_id}/decision-plans", "post"),
            ("/v1/repositories/{repository_id}/simulate", "post"),
            ("/v1/repositories/{repository_id}/apply", "post"),
            ("/v1/data/connect", "post"),
            ("/v1/data", "get"),
            ("/v1/data/{dataset_id}", "get"),
            ("/v1/data/{dataset_id}/summary", "get"),
            ("/v1/data/{dataset_id}/refresh", "post"),
            ("/v1/data/{dataset_id}", "delete"),
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
    log_dir = Path(tempfile.mkdtemp(prefix="integration-algenta-runtime-"))
    log_path = log_dir / "api_server.log"

    if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):
        try:
            _wait_for_health(base_url, log_path, timeout_seconds=5.0)
            if _endpoint_serves_canonical_runtime_surface(base_url):
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
ACTIVE_LIVE_CHECK_FILTER = selected_live_check_filter()
ACTIVE_LIVE_CHECK_FILTER_TOKENS = live_check_filter_tokens(ACTIVE_LIVE_CHECK_FILTER)


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
    except EnvironmentBlocked as exc:
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
        message = f"{type(exc).__name__}: {exc}"
        results.append((FAIL, name, message))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {message}")
        return None


def _preflight() -> None:
    if not API_KEY:
        raise RuntimeError("DE_API_KEY is required for live Runtime integration.")
    response = httpx.get(f"{BASE_URL}/v1/health", timeout=5.0)
    assert response.status_code == 200, f"/v1/health returned {response.status_code}"


def _write_sqlite_fixture(path: Path) -> None:
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


def _postgres_fixture_rows() -> list[dict[str, object]]:
    return [
        {"product_line": "Electronics", "revenue": 42193221.0, "region": "US"},
        {"product_line": "Apparel", "revenue": 28114992.0, "region": "US"},
        {"product_line": "Electronics", "revenue": 1204000.0, "region": "CA"},
    ]


def _registration_metric_field(registration: SourceRegistration) -> str:
    fields = registration.source_schema.get("fields", []) if registration.source_schema else []
    if not fields and registration.source_schema:
        fields = [
            str(column.get("name"))
            for column in registration.source_schema.get("columns", [])
            if isinstance(column, dict) and isinstance(column.get("name"), str)
        ]
    if not fields:
        raise AssertionError("Registration returned no queryable schema fields.")
    return str(fields[0])


def _result_scalar_value(result: QueryOutput) -> float:
    value = result.result
    if isinstance(value, dict):
        return float(value.get("value"))
    return float(value)


def _local_numeric_metric_field(runtime: Runtime, registration: SourceRegistration) -> str:
    source = runtime._local_sources.get(registration.name or "")  # type: ignore[attr-defined]
    if source is None:
        raise AssertionError("Connected local source is missing from runtime state.")
    for field in source.fields:
        if any(isinstance(row.get(field), int | float) for row in source.records):
            return str(field)
    raise AssertionError("Connected local source has no numeric field for deterministic count.")


def _local_numeric_value_count(
    runtime: Runtime,
    registration: SourceRegistration,
    field: str,
) -> int:
    source = runtime._local_sources.get(registration.name or "")  # type: ignore[attr-defined]
    if source is None:
        raise AssertionError("Connected local source is missing from runtime state.")
    return sum(1 for row in source.records if isinstance(row.get(field), int | float))


def _count_query(
    runtime: Runtime,
    registration: SourceRegistration,
    *,
    metric_field: str | None = None,
) -> dict[str, Any]:
    plan = runtime.resolve(
        {
            "source_name": registration.name,
            "metric": metric_field or _registration_metric_field(registration),
            "aggregation": "count",
        }
    )
    assert isinstance(plan, ResolveOutput)
    verified = runtime.verify(plan)
    result = runtime.query(plan)
    return {
        "plan_hash": plan.plan_hash,
        "schema_revision": plan.schema_revision,
        "valid": verified.valid,
        "row_count": registration.row_count,
        "scalar": _result_scalar_value(result),
        "latency_ms": result.latency_ms,
    }


def run_local_runtime_real_csv_flow() -> None:
    runtime = Runtime()
    imported = runtime.import_preview(
        REAL_MARCH_ORDERS,
        name="orders_detail",
        source_ref=REAL_MARCH_ORDERS.name,
    )
    metric_field = _local_numeric_metric_field(runtime, imported.registration)
    expected_count = _local_numeric_value_count(runtime, imported.registration, metric_field)
    summary = _count_query(runtime, imported.registration, metric_field=metric_field)
    bundle = runtime.import_bundle_preview(
        [REAL_MARCH_ORDERS, REAL_MARCH_FINANCIAL, REAL_MARCH_INACCURATE],
        names=["orders_detail_bundle", "orders_financial_bundle", "top_inaccurate_items_bundle"],
        source_refs=[
            REAL_MARCH_ORDERS.name,
            REAL_MARCH_FINANCIAL.name,
            REAL_MARCH_INACCURATE.name,
        ],
    )

    assert imported.registration.status == "ready"
    assert imported.registration.row_count is not None
    assert imported.registration.row_count > 0
    assert summary["valid"] is True
    assert float(summary["scalar"]) == float(expected_count)
    assert "Algenta Source Import" in imported.preview
    assert "Origin:" in imported.preview
    assert REAL_MARCH_ORDERS.stem in imported.preview

    assert len(bundle.registrations) == 3
    assert not bundle.failures
    assert "Algenta Source Bundle" in bundle.preview
    assert "orders_detail_bundle" in bundle.preview
    assert "orders_financial_bundle" in bundle.preview
    assert "top_inaccurate_items_bundle" in bundle.preview


def run_local_runtime_real_file_matrix() -> None:
    runtime = Runtime()

    parquet_import = runtime.import_preview(
        REAL_LOCAL_PARQUET,
        name="bookings_parquet",
        source_ref=REAL_LOCAL_PARQUET.name,
    )
    parquet_metric = _local_numeric_metric_field(runtime, parquet_import.registration)
    parquet_expected_count = _local_numeric_value_count(
        runtime,
        parquet_import.registration,
        parquet_metric,
    )
    parquet_summary = _count_query(
        runtime,
        parquet_import.registration,
        metric_field=parquet_metric,
    )

    workbook_import = runtime.import_preview(
        REAL_LOCAL_WORKBOOK,
        name="qpl_workbook",
        source_ref=REAL_LOCAL_WORKBOOK.name,
    )
    workbook_metric = _local_numeric_metric_field(runtime, workbook_import.registration)
    workbook_expected_count = _local_numeric_value_count(
        runtime,
        workbook_import.registration,
        workbook_metric,
    )
    workbook_summary = _count_query(
        runtime,
        workbook_import.registration,
        metric_field=workbook_metric,
    )

    assert parquet_import.registration.row_count is not None
    assert parquet_import.registration.row_count > 0
    assert parquet_import.registration.name == "bookings_parquet"
    assert "Algenta Source Import" in parquet_import.preview
    assert REAL_LOCAL_PARQUET.name in parquet_import.preview
    assert parquet_summary["valid"] is True
    assert float(parquet_summary["scalar"]) == float(parquet_expected_count)

    assert workbook_import.registration.row_count is not None
    assert workbook_import.registration.row_count > 0
    assert workbook_import.registration.name == "qpl_workbook"
    assert "Algenta Source Import" in workbook_import.preview
    assert REAL_LOCAL_WORKBOOK.name in workbook_import.preview
    assert workbook_summary["valid"] is True
    assert float(workbook_summary["scalar"]) == float(workbook_expected_count)


def run_api_runtime_connector_matrix() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)
    with tempfile.TemporaryDirectory(prefix="algenta-runtime-live-") as tmp_dir:
        run_suffix = Path(tmp_dir).name.replace("algenta-runtime-live-", "")
        rest_name = f"weather_stations_{run_suffix}"
        s3_name = f"noaa_hourly_{run_suffix}"
        sqlite_name = f"orders_sqlite_{run_suffix}"
        postgres_name = f"orders_postgres_{run_suffix}"
        sqlite_bundle_name = f"orders_sqlite_bundle_{run_suffix}"
        postgres_bundle_name = f"orders_postgres_bundle_{run_suffix}"
        s3_bundle_name = f"noaa_hourly_bundle_{run_suffix}"
        rest_bundle_name = f"weather_stations_bundle_{run_suffix}"
        sqlite_path = Path(tmp_dir) / "orders.db"
        _write_sqlite_fixture(sqlite_path)
        sqlite_descriptor = {
            "type": "sqlite",
            "path": str(sqlite_path.resolve()),
            "table": "orders",
        }
        with temporary_postgres_fixture(
            _postgres_fixture_rows(),
            table="orders",
        ) as postgres_descriptor:
            postgres_connector = postgres_canonical_connector(postgres_descriptor)
            rest_registration = runtime.connect(PUBLIC_REST_CONNECTION, name=rest_name)
            rest = _count_query(runtime, rest_registration)

            imported = runtime.import_preview(
                PUBLIC_S3_CONNECTION,
                name=s3_name,
                source_ref=PUBLIC_S3_SOURCE_REF,
            )
            s3 = _count_query(runtime, imported.registration)

            sqlite_registration = runtime.connect(sqlite_descriptor, name=sqlite_name)
            sqlite = _count_query(runtime, sqlite_registration)

            postgres_registration = runtime.connect(
                postgres_connector,
                name=postgres_name,
            )
            postgres = _count_query(runtime, postgres_registration)

            bundle = runtime.import_bundle_preview(
                [
                    sqlite_descriptor,
                    postgres_connector,
                    PUBLIC_S3_CONNECTION,
                    PUBLIC_REST_CONNECTION,
                ],
                names=[
                    sqlite_bundle_name,
                    postgres_bundle_name,
                    s3_bundle_name,
                    rest_bundle_name,
                ],
                source_refs=[
                    f"{sqlite_path.name}#orders",
                    f"postgres://{postgres_descriptor['schema']}.{postgres_descriptor['table']}",
                    PUBLIC_S3_SOURCE_REF,
                    "https://api.weather.gov/stations?state=CO",
                ],
            )

    assert rest["valid"] is True
    assert rest["row_count"] is not None
    assert rest["row_count"] > 0
    assert float(rest["scalar"]) == float(rest["row_count"])

    assert s3["valid"] is True
    assert s3["row_count"] is not None
    assert s3["row_count"] > 0
    assert float(s3["scalar"]) == float(s3["row_count"])
    assert "Algenta Source Import" in imported.preview
    assert PUBLIC_S3_SOURCE_REF in imported.preview

    assert sqlite["valid"] is True
    assert sqlite["row_count"] == 3
    assert float(sqlite["scalar"]) == 3.0

    assert postgres["valid"] is True
    assert postgres["row_count"] == 3
    assert float(postgres["scalar"]) == 3.0

    assert len(bundle.registrations) == 4
    assert not bundle.failures
    assert "Algenta Source Bundle" in bundle.preview
    assert sqlite_bundle_name in bundle.preview
    assert postgres_bundle_name in bundle.preview
    assert s3_bundle_name in bundle.preview
    assert rest_bundle_name in bundle.preview


def run_api_runtime_dataset_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        request = _live_refreshable_runtime_dataset_request(
            "algenta-runtime-live-dataset",
            source_url,
        )

        connectors = runtime.list_connectors(page=1, limit=50)
        assert isinstance(connectors, list), type(connectors)
        for connector in connectors:
            assert connector.id
            assert connector.connector_type

        saved_connector = runtime.create_connector(
            name=f"algenta-runtime-live-connector-{time.time_ns()}",
            connector_type="rest",
            config={"url": source_url, "data_path": "items"},
            description="Live Algenta Runtime saved connector check.",
        )
        preview_tested_connector = runtime.test_connector(
            connector={"type": "rest", "url": source_url, "data_path": "items"}
        )
        assert preview_tested_connector.success is True
        assert preview_tested_connector.status == "live"

        preview_browsed_connector = runtime.browse_connector(
            connector={"type": "rest", "url": source_url, "data_path": "items"}
        )
        assert preview_browsed_connector.connector_type == "rest"
        assert preview_browsed_connector.total >= 1

        connector_id = saved_connector.id
        connector_name = saved_connector.name
        assert connector_id
        assert connector_name

        try:
            listed_connectors = runtime.list_connectors(page=1, limit=25)
            assert isinstance(listed_connectors, list), type(listed_connectors)
            assert any(item.id == connector_id for item in listed_connectors)

            connector_detail = runtime.get_connector(connector_id)
            assert connector_detail.id == connector_id
            assert connector_detail.name == connector_name

            updated_connector = runtime.update_connector(
                connector_id,
                description="Live Algenta Runtime connector updated description.",
            )
            assert updated_connector.id == connector_id
            assert updated_connector.description == "Live Algenta Runtime connector updated description."

            tested_connector = runtime.test_connector(connector_id)
            assert tested_connector.success is True
            assert tested_connector.status == "live"

            browsed_connector = runtime.browse_connector(connector_id)
            assert browsed_connector.connector_type == "rest"
            assert browsed_connector.total >= 1

            created = runtime.connect(
                connector=request["connector"],
                dataset_name=request["dataset_name"],
                description=request["description"],
                persist=True,
            )
            dataset_id = created.dataset_id
            dataset_name = created.dataset_name
            assert created.status == "ready"
            assert dataset_id
            assert dataset_name

            try:
                listed = runtime.list_datasets(search=dataset_name, compact=True)
                assert listed.page == 1
                assert listed.limit == 200
                assert listed.total >= len(listed)
                assert listed.matched_total is None or listed.matched_total >= len(listed)
                assert any(item.dataset_id == dataset_id for item in listed)

                refreshed = runtime.refresh_dataset(dataset_id)
                assert refreshed.status == "ready"
                assert refreshed.dataset_id == dataset_id

                summary = runtime.get_dataset_summary(dataset_id)
                assert summary.dataset_id == dataset_id
                assert summary.name == dataset_name
                assert summary.column_count >= 2

                detail = runtime.get_dataset(dataset_id)
                assert detail.dataset.dataset_id == dataset_id
                assert detail.dataset.dataset_name == dataset_name
                assert isinstance(detail.schema, dict)
                detail_column_count = detail.dataset.column_count or detail.dataset.columns
                assert isinstance(detail_column_count, int)
                assert detail_column_count >= 2
            finally:
                deleted = runtime.delete_dataset(dataset_id)
                assert deleted.dataset_id == dataset_id
                assert deleted.status == "deleted"
        finally:
            runtime.delete_connector(connector_id)


def run_api_runtime_repository_surface() -> None:
    reason = local_repository_live_support_reason(BASE_URL)
    if reason is not None:
        raise EnvironmentBlocked(reason)

    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)
    capabilities = runtime.get_repository_intelligence_capabilities()
    assert_repository_intelligence_capabilities_payload(capabilities)
    repository_id: str | None = None
    with live_repository_fixture("algenta-runtime") as repository_fixture:
        created_connector = runtime.create_connector(**repository_fixture.connector_request)
        repository_id = created_connector.id
        assert created_connector.connector_type == "local_repo"
        try:
            snapshot = runtime.create_repository_snapshot(
                repository_id,
                repository_fixture.snapshot_request,
            )
            snapshot_id = snapshot.snapshot_id
            fetched_snapshot = runtime.get_repository_snapshot(repository_id, snapshot_id)
            repeated_snapshot = runtime.create_repository_snapshot(
                repository_id,
                repository_fixture.snapshot_request,
            )

            assert snapshot.connector_type == "local_repo"
            assert snapshot.file_count >= 2
            assert fetched_snapshot.snapshot_id == snapshot_id
            assert fetched_snapshot.content_hash == snapshot.content_hash
            assert repeated_snapshot.snapshot_id == snapshot_id
            assert repeated_snapshot.status == "existing"

            triage = runtime.triage_repository(
                repository_id,
                repository_fixture.triage_request(snapshot_id),
            )
            assert triage.workspace_evidence_bundle_ref
            assert triage.reduction_ratio >= 1.0
            assert triage.evidence_items
            assert triage.suspect_files[0] == repository_fixture.primary_file
            assert (
                triage.workspace_evidence_bundle_artifact.artifact_kind
                == "WorkspaceEvidenceBundle"
            )

            graph = runtime.query_repository_graph(
                repository_id,
                repository_fixture.graph_query_request(
                    snapshot_id,
                    triage.workspace_evidence_bundle_ref,
                ),
            )
            assert graph.snapshot_id == snapshot_id
            assert repository_fixture.primary_file in graph.seed_file_paths
            assert repository_fixture.primary_file in graph.impacted_files
            assert graph.graph_nodes
            assert graph.top_change_risk_files

            try:
                decision_plan = runtime.create_repository_decision_plan(
                    repository_id,
                    repository_fixture.decision_plan_request(
                        snapshot_id,
                        triage.workspace_evidence_bundle_ref,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                _assert_repository_error(
                    exc,
                    status_code=503,
                    error_code="repository_model_unavailable",
                )
                return

            assert decision_plan.decision_plan_id
            repository_analysis = decision_plan.decision_plan.repository_analysis
            assert repository_analysis is not None
            assert repository_analysis.planner_model_id == "repository.deterministic_local_v1"
            assert repository_analysis.planner_execution_mode == "deterministic_local"
            assert repository_analysis.planner_provider_backend is None
            assert repository_analysis.generated_patch_ref
            assert repository_analysis.patch_impact_report_ref
            assert repository_analysis.token_reduction_metrics.reduction_ratio >= 1.0

            try:
                simulation = runtime.simulate_repository(
                    repository_id,
                    repository_fixture.simulation_request(
                        snapshot_id,
                        decision_plan.decision_plan_id,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                raise_if_capacity_blocked(exc)
                raise

            validated_inputs = simulation.validated_inputs or {}
            score_breakdown = simulation.score_breakdown or {}
            apply_gate = score_breakdown.get("apply_gate", {})
            simulation_id = str(validated_inputs.get("simulation_id") or "")
            assert simulation_id
            assert simulation.decision_plan is not None
            assert isinstance(apply_gate, dict)
            assert apply_gate.get("policy_snapshot_id")

            branch_name = "algenta/live-repository-fix"
            apply_request = repository_fixture.apply_local_branch_request(
                snapshot_id,
                decision_plan.decision_plan_id,
                simulation_id,
                branch_name=branch_name,
            )
            if bool(apply_gate.get("passed")):
                applied = runtime.apply_repository(repository_id, apply_request)
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
                patch_files = applied.validation_summary.get("patch_files")
                assert patch_files == [repository_fixture.primary_file]
            else:
                try:
                    runtime.apply_repository(repository_id, apply_request)
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
                runtime.delete_connector(repository_id)


def run_api_runtime_account_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    me = runtime.me()
    assert isinstance(me, dict), type(me)
    assert any(key in me for key in ("org_id", "organization", "email", "user", "org")), me

    usage = runtime.usage()
    assert usage.billing_period
    assert usage.quota_limit >= 0

    limits = runtime.limits()
    assert isinstance(limits, dict), type(limits)

    listed_before = runtime.list_api_keys()
    assert all(not hasattr(item, "raw_key") for item in listed_before)

    created = None
    revoked = False
    label = f"algenta-runtime-live-{time.time_ns()}"
    requested_device_limit = 0
    try:
        created, requested_device_limit = _create_runtime_api_key_with_plan_fallback(
            runtime,
            label=label,
        )
        assert created.label == label
        assert created.device_limit == requested_device_limit
        assert created.raw_key.startswith(created.key_prefix)

        listed_after = runtime.list_api_keys()
        created_entry = next((item for item in listed_after if item.id == created.id), None)
        assert created_entry is not None
        assert created_entry.label == label
        assert created_entry.device_limit == requested_device_limit

        revoke_result = runtime.revoke_api_key(created.id)
        revoked = True
        assert revoke_result == {}

        listed_final = runtime.list_api_keys()
        assert all(item.id != created.id for item in listed_final)
    finally:
        if created is not None and not revoked:
            runtime.revoke_api_key(created.id)


def run_api_runtime_control_plane_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    team = runtime.list_team_members(page=1, limit=50)
    assert team.page == 1
    assert team.limit == 50
    assert team.total >= len(team.members)
    assert team.pages >= 1
    assert team.members
    assert team.members[0].email
    assert team.members[0].role

    billing = runtime.get_billing_info()
    assert billing.plan
    assert billing.subscription_status in {None, "active", "trialing", "past_due", "canceled", "incomplete"}

    try:
        credits = runtime.refresh_credits(**_live_credit_refresh_request("algenta-runtime-live"))
    except Exception as exc:  # noqa: BLE001
        raise_if_credit_refresh_blocked(exc)
        raise
    assert credits.billing_period == _current_billing_period()
    assert credits.credits_granted >= 0
    assert credits.credits_issued_this_month >= credits.credits_granted
    assert credits.monthly_limit >= 0
    assert credits.monthly_remaining >= 0
    assert credits.refresh_after >= credits.server_time
    assert credits.expires_at >= credits.refresh_after

    metering = runtime.ingest_metering_events(
        device_id=f"algenta-runtime-live-{time.time_ns()}",
        events=_live_metering_events(),
    )
    assert metering.accepted == 1
    assert metering.billing_period

    distributions = runtime.distributions()
    assert distributions.total >= len(distributions.distributions)
    assert distributions.distributions
    assert distributions.distributions[0].name

    templates = runtime.templates()
    assert templates.total >= len(templates.templates)
    assert templates.templates
    assert templates.templates[0].id

    devices = runtime.list_devices(page=1, limit=25)
    assert devices.page == 1
    assert devices.limit == 25
    assert devices.total >= len(devices.devices)
    assert devices.pages >= 1
    assert devices.device_count == len(devices.devices)
    assert devices.plan

    logs = runtime.get_audit_logs(page=1, limit=20)
    assert logs.page == 1
    assert logs.limit == 20
    assert logs.total >= len(logs.entries)
    assert logs.pages >= 1
    assert logs.entries
    assert logs.entries[0].action
    assert logs.entries[0].resource_type
    assert logs.entries[0].result in {"success", "failure"}

    policy = runtime.get_execution_policy()
    assert 0 <= policy.min_confidence <= 1
    assert isinstance(policy.require_calibration, bool)
    assert isinstance(policy.allow_reexecution, bool)
    assert policy.updated_at

    snapshots = runtime.list_execution_policy_snapshots()
    assert snapshots.total_snapshots >= len(snapshots.data)
    if snapshots.data:
        assert snapshots.data[0].snapshot_id
        assert snapshots.data[0].revision >= 1

    with webhook_receiver() as (callback_url, deliveries):
        webhook = runtime.test_webhook_delivery(callback_url)
        assert webhook.success is True
        assert webhook.status_code == 200
        assert deliveries, "Expected one webhook delivery to local receiver"
        assert deliveries[0]["path"] == "/webhook", deliveries[0]

    updated = runtime.update_execution_policy(
        min_confidence=policy.min_confidence,
        risk_floor=policy.risk_floor,
        require_calibration=policy.require_calibration,
        allow_reexecution=policy.allow_reexecution,
    )
    assert updated.min_confidence == policy.min_confidence
    assert updated.risk_floor == policy.risk_floor
    assert updated.require_calibration == policy.require_calibration
    assert updated.allow_reexecution == policy.allow_reexecution


def run_api_runtime_jobs_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    try:
        submitted = runtime.submit_job(
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
        status = runtime.get_job(submitted.job_id)
        listed = runtime.list_jobs(page=1, limit=25, status="queued")
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise

    assert submitted.job_id
    assert submitted.poll_url.endswith(submitted.job_id)
    assert status.job_id == submitted.job_id
    assert status.status in {"queued", "running", "completed", "failed", "cancelled"}
    assert listed.page == 1
    assert listed.limit == 25

    if status.status == "completed":
        result = runtime.get_job_result(submitted.job_id)
        assert result.get("status") == "completed"


def run_api_runtime_trigger_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)
    created = runtime.register_trigger(**_live_trigger_request(f"algenta-runtime-{time.time_ns()}"))
    trigger_id = created.trigger_id
    try:
        assert trigger_id
        assert created.status == "active"

        listed = runtime.list_triggers(status="all", page=1, limit=25)
        assert listed.page == 1
        assert listed.limit == 25
        assert listed.total >= len(listed.triggers)
        assert any(item.trigger_id == trigger_id for item in listed.triggers)

        fired = runtime.fire_trigger(trigger_id, force=False)
        assert fired.trigger_id == trigger_id
        assert fired.condition_met is False
        assert fired.fired is False

        paused = runtime.pause_trigger(trigger_id, paused=True)
        assert paused.trigger_id == trigger_id
        assert paused.status == "paused"

        resumed = runtime.pause_trigger(trigger_id, paused=False)
        assert resumed.trigger_id == trigger_id
        assert resumed.status == "active"
    finally:
        deleted = runtime.delete_trigger(trigger_id)
        assert deleted.trigger_id == trigger_id
        assert deleted.deleted is True


def run_api_runtime_plan_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    models = runtime.list_models()
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
        artifact = runtime.resolve_artifact_bridge(
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

    tokenized = runtime.tokenize("alpha beta gamma")
    assert tokenized.object == "tokenization"
    assert tokenized.token_count == len(tokenized.tokens) == 3

    counted = runtime.count_tokens("alpha beta gamma")
    assert counted.object == "token_count"
    assert counted.token_count == 3

    chat = runtime.chat_completions([{"role": "user", "content": "summarize alpha beta"}])
    assert chat.object == "chat.completion"
    assert chat.choices[0].message.role == "assistant"
    _assert_empty_provider_trace(chat)

    response = runtime.responses("alpha beta")
    assert response.object == "response"
    assert response.status == "completed"
    assert len(response.output) >= 1
    _assert_empty_provider_trace(response, output_items=True)

    embedded = runtime.embeddings(["alpha beta", "gamma"], dimensions=8)
    assert embedded.object == "list"
    assert embedded.model == "text.hash_embedding_v1"
    assert embedded.dimensions == 8
    assert len(embedded.data) == 2
    _assert_empty_provider_trace(embedded)

    similarity = runtime.embedding_similarity([1.0, 0.0], [0.5, 0.5])
    assert similarity.object == "embedding_similarity"
    assert similarity.dimension == 2

    reranked = runtime.rerank(
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


def run_api_runtime_proof_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    manifest = runtime.get_runtime_manifest()
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

    modules = runtime.get_runtime_modules()
    assert len(modules.modules) >= 1
    assert modules.summary.module_count >= 1

    benchmarks = runtime.get_runtime_benchmarks()
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

    validation = runtime.get_runtime_release_validation()
    assert validation.valid_release is True


def run_api_runtime_deployment_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    deployment_regions = runtime.list_deployment_regions()
    assert deployment_regions.providers
    managed_provider = next(
        (provider for provider in deployment_regions.providers if provider.id == "algenta_shared"),
        None,
    )
    assert managed_provider is not None
    assert managed_provider.regions

    deployment = runtime.get_deployment()
    if deployment is not None:
        assert deployment.deployment_id
        assert deployment.provider
        deployment_cost = runtime.get_deployment_cost(deployment.deployment_id)
        assert deployment_cost.deployment_id == deployment.deployment_id
        assert deployment_cost.provider == deployment.provider
        assert deployment_cost.cost_usd_month >= 0


def run_api_runtime_deployment_lifecycle_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    deployment = runtime.get_deployment()
    if deployment is not None:
        raise EnvironmentBlocked("deployment mutation requires an org without an existing deployment")

    try:
        created = runtime.create_deployment(
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

    cost = runtime.get_deployment_cost(created.deployment_id)
    assert cost.deployment_id == created.deployment_id
    assert cost.provider == created.provider
    assert cost.billable_cost_usd_month >= cost.cost_usd_month

    deleted = runtime.delete_deployment(created.deployment_id)
    assert deleted.deployment_id == created.deployment_id
    assert deleted.status in {"deprovisioning", "deleted"}


def run_api_runtime_decision_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    try:
        recommendation = runtime.recommend(
            {
                "options": [
                    {"name": "expand", "expected_value": 140_000, "risk": 0.15},
                    {"name": "hold", "expected_value": 90_000, "risk": 0.08},
                ],
                "runs": 250,
            }
        )
        score = runtime.score(
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
        batch = runtime.batch(
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
        compared = runtime.compare(
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


def run_api_runtime_product_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    try:
        decision = runtime.product_decision(
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
        agent_run = runtime.product_agent_run(
            {
                "task": f"Summarize benchmark blockers {time.time_ns()}",
                "tools": ["search"],
                "max_steps": 3,
            }
        )
        optimize = runtime.product_optimize(
            {
                "objective": "maximize profit",
                "variables": [
                    {"name": "price", "min": 50.0, "max": 150.0},
                    {"name": "discount", "min": 0.0, "max": 0.2},
                ],
                "iterations": 100,
            }
        )
        retrieve = runtime.product_retrieve(
            {
                "query": "launch checklist",
                "documents": [
                    {"id": "doc_1", "content": "Launch checklist for product release."},
                    {"id": "doc_2", "content": "Pricing review for launch approval."},
                ],
                "top_k": 2,
            }
        )
        forecast = runtime.product_forecast(
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


def run_api_runtime_streaming_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    chat_chunks = list(
        runtime.stream_chat_completions([{"role": "user", "content": "summarize alpha beta"}])
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

    response_events = list(runtime.stream_responses("alpha beta"))
    assert len(response_events) == 3, f"Expected 3 response stream events, got {len(response_events)}"
    assert response_events[0].type == "response.created"
    assert response_events[1].type == "response.output_item.done"
    assert response_events[1].item is not None
    assert response_events[1].item.content[0].token_count >= 2
    assert response_events[2].type == "response.completed"
    assert response_events[2].response is not None
    assert response_events[2].response.status == "completed"


def run_api_runtime_agent_surface() -> None:
    runtime = Runtime(mode="api", api_key=API_KEY, base_url=BASE_URL)

    try:
        created = runtime.create_agent_run(
            task=f"Search benchmark notes {time.time_ns()}",
            tools=["search"],
            approval_mode="manual",
        )
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise
    assert created.status == "requires_approval"
    assert created.pending_action == "approve"

    fetched = runtime.get_agent_run(created.run_id)
    assert fetched.run_id == created.run_id
    assert fetched.status == "requires_approval"

    events = runtime.get_agent_run_events(created.run_id, limit=20)
    assert events.run_id == created.run_id
    assert events.total_events >= 3

    approved = runtime.approve_agent_run(created.run_id)
    assert approved.run_id == created.run_id
    assert approved.status == "completed"
    assert "search" in approved.tools_used

    try:
        streamed_created = runtime.create_agent_run(
            task=f"Search benchmark notes stream {time.time_ns()}",
            tools=["search"],
            approval_mode="auto",
        )
    except Exception as exc:  # noqa: BLE001
        raise_if_capacity_blocked(exc)
        raise

    streamed_events = list(runtime.stream_agent_run_events(streamed_created.run_id, limit=20))
    assert len(streamed_events) >= 2
    assert streamed_events[0].type == "agent.run.event"
    assert streamed_events[0].event is not None
    assert streamed_events[0].event.event_type == "run_created"
    assert streamed_events[-1].type == "agent.run.completed"
    assert streamed_events[-1].status == "completed"


def main() -> int:
    started = time.perf_counter()
    _emit("\n" + "=" * 70)
    _emit("  LIVE PYTHON RUNTIME INTEGRATION")
    _emit("=" * 70)

    _preflight()

    check("Local Runtime real CSV import/query path", run_local_runtime_real_csv_flow)
    check("Local Runtime real Parquet/Excel import/query path", run_local_runtime_real_file_matrix)
    check("API Runtime connector matrix", run_api_runtime_connector_matrix)
    check("API Runtime connectors + dataset lifecycle surface", run_api_runtime_dataset_surface)
    check("API Runtime repository intelligence surface", run_api_runtime_repository_surface)
    check("API Runtime account + API-key surface", run_api_runtime_account_surface)
    check(
        "API Runtime team/credits/metering/audit/execution-policy surface",
        run_api_runtime_control_plane_surface,
    )
    check("API Runtime async jobs surface", run_api_runtime_jobs_surface)
    check("API Runtime trigger lifecycle surface", run_api_runtime_trigger_surface)
    check("API Runtime LLM utility plan surface", run_api_runtime_plan_surface)
    check("API Runtime proof routes", run_api_runtime_proof_surface)
    check("API Runtime deployment control surface", run_api_runtime_deployment_surface)
    check(
        "API Runtime deployment create/delete lifecycle",
        run_api_runtime_deployment_lifecycle_surface,
    )
    check("API Runtime decision runtime plan surface", run_api_runtime_decision_surface)
    check("API Runtime simplified product surface", run_api_runtime_product_surface)
    check("API Runtime streaming LLM surface", run_api_runtime_streaming_surface)
    check("API Runtime agent-run plan surface", run_api_runtime_agent_surface)

    failed = [result for result in results if result[0] == FAIL]
    skipped = [result for result in results if result[0] == SKIP]
    _emit("\n" + "=" * 70)
    _emit(f"Passed: {sum(1 for status, _, _ in results if status == PASS)}")
    _emit(f"Skipped: {len(skipped)}")
    _emit(f"Failed: {len(failed)}")
    if failed:
        _emit("Failures:")
        for _, name, message in failed:
            _emit(f"  - {name}: {message}")
    if skipped:
        _emit("Skipped:")
        for _, name, message in skipped:
            _emit(f"  - {name}: {message}")
    _emit("=" * 70)
    artifact_path = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_algenta_runtime_live.py",
        passed=sum(1 for status, _, _ in results if status == PASS),
        failed=len(failed),
        skipped=len(skipped),
        total=len(results),
        elapsed_seconds=time.perf_counter() - started,
        details={
            "api_key_configured": API_KEY_CONFIGURED,
            "base_url": BASE_URL,
            "failed_checks": [name for _, name, _ in failed],
            "skipped_checks": [name for _, name, _ in skipped],
        },
    )
    _emit(f"Summary artifact: {artifact_path}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
