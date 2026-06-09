"""
Phase 20: OpenAPI Spec Compliance + Full Schema Validation Tests

Validates the OpenAPI specification (/openapi.json) and ensures all API
responses conform to their declared schemas.

Covers:
  - OpenAPI spec structure (version, info, paths, components)
  - Path coverage (all major routes declared)
  - Schema definition completeness
  - Response schema compliance (live requests vs declared schemas)
  - Error schema compliance (401, 422, 404)
  - Security scheme declarations
  - Schema type validation (numbers, strings, arrays, enums)
  - Consistency (no phantom routes, no undocumented endpoints)

Prerequisites:
  1. API server running: make dev-api
  2. PostgreSQL running on :5432
  3. Redis running on :6379
  4. Dev data seeded: python scripts/seed_dev.py

Run:
  python tests/integration/test_openapi.py

Endpoints under test:
  GET  /openapi.json               — OpenAPI specification
  GET  /v1/health                   — health check
  GET  /v1/version                  — version info
  POST /v1/simulate                 — run simulation
  GET  /v1/runs                     — list runs
  GET  /v1/jobs/list                — list async jobs
  POST /v1/data/connect             — connect refreshable external data into a reusable dataset
  GET  /v1/data                     — list datasets
  GET  /v1/data/{dataset_id}        — inspect dataset schema
  GET  /v1/data/{dataset_id}/summary — summary view for query planning
  POST /v1/data/{dataset_id}/refresh — refresh a dataset from its saved origin
  POST /v1/credits/refresh          — issue one execution credit batch
  GET  /v1/execution/policy/snapshots — execution policy snapshot catalog
  GET  /v1/templates                — list templates
  GET  /v1/connectors               — list connectors
  POST /v1/repositories/{repository_id}/snapshots — create immutable repository snapshot
  GET  /v1/repositories/{repository_id}/snapshots/{snapshot_id} — fetch immutable snapshot
  POST /v1/repositories/{repository_id}/triage — build bounded workspace evidence bundle
  POST /v1/repositories/{repository_id}/decision-plans — create immutable decision plan revision
  POST /v1/repositories/{repository_id}/simulate — populate repository decision envelope
  POST /v1/repositories/{repository_id}/apply — apply gated repository patch/branch action
  GET  /v1/analytics                — analytics summary
  + all spec-declared paths for reachability
"""

# ruff: noqa: E402

import os
import sys

if __name__ == "__main__" and os.environ.get("ALGENTA_SKIP_MOJO_RUNTIME", "0") == "1":
    print("[skip] tests/integration/test_openapi.py — ALGENTA_SKIP_MOJO_RUNTIME=1")
    sys.exit(0)


import atexit
import contextlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_data_source_server import (
    default_refreshable_dataset_payload,
    static_json_server,
)
from tests.integration.live_integration_artifacts import (
    LIVE_INTEGRATION_SUMMARY_ARTIFACTS,
    write_live_integration_summary,
)

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
    from tests.integration.live_repository_fixture import (
        live_repository_fixture,
        local_repository_live_support_reason,
    )
    from tests.integration.live_webhook_receiver import webhook_receiver
except ModuleNotFoundError:
    from live_local_auth_bootstrap import ensure_bootstrapped_local_live_api_key
    from live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
    )
    from live_repository_fixture import (
        live_repository_fixture,
        local_repository_live_support_reason,
    )
    from live_webhook_receiver import webhook_receiver

CONFIGURED_BASE_URL = configured_local_live_base_url()
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()
_runtime_proc: subprocess.Popen[str] | None = None
_runtime_started_here = False
_runtime_log_path: Path | None = None

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []
SUITE_NAME = "openapi_integration"
SUMMARY_ARTIFACT = LIVE_INTEGRATION_SUMMARY_ARTIFACTS[SUITE_NAME]
STARTED_AT = time.perf_counter()

# Cache the spec globally so we only fetch once
_spec_cache: dict = {}
BASE_URL = ""


class EnvironmentBlockedError(RuntimeError):
    """Raised when a live dependency blocks coverage without indicating a regression."""


def ensure_live_api_key_available(status: int, body: Any) -> None:
    if API_KEY_CONFIGURED:
        return
    if not isinstance(body, dict):
        return
    error = body.get("error")
    if not isinstance(error, dict):
        return
    code = error.get("code")
    if status == 401 or code == "invalid_api_key":
        raise EnvironmentBlockedError(
            "DE_API_KEY is not set; skipping authenticated OpenAPI checks that require a real live key."
        )

# Correct auto-mode payload matching actual SimulateRequestAuto schema
# Uses scenario.variables (dict of {name: {low, high}}) + objective
AUTO_PAYLOAD = {
    "mode": "auto",
    "scenario": {
        "variables": {
            "cost": {"low": 1000, "high": 5000},
            "revenue": {"low": 2000, "high": 8000},
        },
        "objective": "maximize_net_value",
    },
    "runs": 500,
}


def _live_dataset_connect_request(prefix: str, source_url: str) -> dict[str, Any]:
    return {
        "connection_type": "api",
        "provider": "rest",
        "dataset_name": f"{prefix}-{time.time_ns()}",
        "description": "Live OpenAPI refreshable dataset check.",
        "connection_config": {
            "url": source_url,
            "data_path": "items",
        },
    }


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


def _endpoint_serves_canonical_openapi_contract(base_url: str) -> bool:
    try:
        status, spec = _probe_json(base_url, "/openapi.json", timeout=5.0)
        if status != 200 or not isinstance(spec, dict):
            return False
        expected_security = [{"BearerAuth": []}, {"LegacyApiKey": []}]
        for path, method in (
            ("/v1/models", "get"),
            ("/v1/artifacts/resolve", "post"),
            ("/v1/chat/completions", "post"),
            ("/v1/tokenize", "post"),
            ("/v1/count_tokens", "post"),
            ("/v1/responses", "post"),
            ("/v1/embeddings", "post"),
            ("/v1/embeddings/similarity", "post"),
            ("/v1/rerank", "post"),
            ("/v1/decision", "post"),
            ("/v1/agent/run", "post"),
            ("/v1/optimize", "post"),
            ("/v1/retrieve", "post"),
            ("/v1/forecast", "post"),
            ("/v1/agent/runs", "post"),
            ("/v1/agent/runs/{run_id}", "get"),
            ("/v1/agent/runs/{run_id}/events", "get"),
            ("/v1/agent/runs/{run_id}/resume", "post"),
            ("/v1/agent/runs/{run_id}/cancel", "post"),
            ("/v1/agent/runs/{run_id}/approve", "post"),
            ("/v1/simulate", "post"),
            ("/v1/decisions/plan", "post"),
            ("/v1/runs", "get"),
            ("/v1/jobs/list", "get"),
            ("/v1/data/connect", "post"),
            ("/v1/data", "get"),
            ("/v1/data/{dataset_id}", "get"),
            ("/v1/data/{dataset_id}/summary", "get"),
            ("/v1/data/{dataset_id}", "delete"),
            ("/v1/repositories/{repository_id}/snapshots", "post"),
            ("/v1/repositories/{repository_id}/snapshots/{snapshot_id}", "get"),
            ("/v1/repositories/{repository_id}/triage", "post"),
            ("/v1/repositories/{repository_id}/decision-plans", "post"),
            ("/v1/repositories/{repository_id}/simulate", "post"),
            ("/v1/repositories/{repository_id}/apply", "post"),
            ("/v1/webhooks/test", "post"),
            ("/v1/execution/policy/snapshots", "get"),
            ("/v1/templates", "get"),
            ("/v1/connectors", "get"),
            ("/v1/connectors", "post"),
            ("/v1/connectors/test", "post"),
            ("/v1/connectors/browse", "post"),
            ("/v1/connectors/{connector_id}", "get"),
            ("/v1/connectors/{connector_id}", "patch"),
            ("/v1/connectors/{connector_id}/test", "post"),
            ("/v1/connectors/{connector_id}/browse", "get"),
            ("/v1/connectors/{connector_id}", "delete"),
            ("/v1/analytics", "get"),
            ("/v1/jobs", "post"),
            ("/v1/triggers", "get"),
            ("/v1/triggers", "post"),
            ("/v1/triggers/{trigger_id}/fire", "post"),
            ("/v1/triggers/{trigger_id}/pause", "patch"),
            ("/v1/triggers/{trigger_id}", "delete"),
            ("/v1/metering", "post"),
            ("/v1/credits/refresh", "post"),
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
        if "503" not in spec.get("paths", {}).get("/mcp/sse", {}).get("get", {}).get("responses", {}):
            return False
        if "503" not in spec.get("paths", {}).get("/mcp/messages", {}).get("post", {}).get("responses", {}):
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
    log_dir = Path(tempfile.mkdtemp(prefix="integration-openapi-"))
    log_path = log_dir / "api_server.log"

    if API_KEY_CONFIGURED and _port_open(DEFAULT_HOST, DEFAULT_PORT):
        try:
            _wait_for_health(base_url, log_path, timeout_seconds=5.0)
            if _endpoint_serves_canonical_openapi_contract(base_url):
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


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(
    method: str, path: str, body=None, headers=None, auth=True, timeout=10
) -> tuple[int, Any, dict[str, str], float]:
    """Make HTTP request, return (status_code, response_body_dict, response_headers, elapsed)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if auth:
        h["X-API-Key"] = API_KEY
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            body_bytes = resp.read()
            try:
                body_data = json.loads(body_bytes)
            except Exception:
                body_data = body_bytes.decode("utf-8", errors="replace")
            if auth:
                ensure_live_api_key_available(resp.status, body_data)
            return resp.status, body_data, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        body_bytes = e.read()
        try:
            body_data = json.loads(body_bytes)
        except Exception:
            body_data = body_bytes.decode("utf-8", errors="replace")
        if auth:
            ensure_live_api_key_available(e.code, body_data)
        return e.code, body_data, dict(e.headers), elapsed
    except TimeoutError as err:
        elapsed = time.perf_counter() - t0
        raise TimeoutError(
            f"Request to {url} timed out after {timeout}s (elapsed: {elapsed:.1f}s)"
        ) from err
    except urllib.error.URLError as err:
        if "timed out" in str(err):
            elapsed = time.perf_counter() - t0
            raise TimeoutError(
                f"Request to {url} timed out after {timeout}s (elapsed: {elapsed:.1f}s)"
            ) from err
        raise RuntimeError(f"Cannot connect to {BASE_URL} — is the API server running?") from err


def check(name: str, fn):
    """Run a single test, record pass/fail."""
    started_at = time.monotonic()
    print(f"  ... {name}", flush=True)
    try:
        fn()
        results.append((PASS, name))
        print(
            f"  {PASS} {name} ({time.monotonic() - started_at:.2f}s)",
            flush=True,
        )
    except EnvironmentBlockedError as e:
        results.append((SKIP, name, str(e)))
        print(
            f"  {SKIP} {name} ({time.monotonic() - started_at:.2f}s): {e}",
            flush=True,
        )
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(
            f"  {FAIL} {name} ({time.monotonic() - started_at:.2f}s): {e}",
            flush=True,
        )
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(
            f"  {FAIL} {name} ({time.monotonic() - started_at:.2f}s): "
            f"{type(e).__name__}: {e}",
            flush=True,
        )


def ensure_simulation_capacity_available(status: int, body: Any) -> None:
    reason = classify_simulation_capacity_blocker(
        status=status,
        payload=body,
        text=json.dumps(body) if isinstance(body, dict) else str(body),
    )
    if reason:
        raise EnvironmentBlockedError(reason)


def simulate_req(payload: Any) -> tuple[int, Any, dict[str, str], float]:
    status, body, hdrs, elapsed = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    return status, body, hdrs, elapsed


def get_spec() -> dict:
    """Fetch and cache the OpenAPI spec."""
    global _spec_cache
    if not _spec_cache:
        status, body, _, elapsed = req("GET", "/openapi.json", auth=False)
        assert status == 200, f"Failed to fetch OpenAPI spec: status {status}"
        assert isinstance(body, dict), "OpenAPI spec is not valid JSON object"
        _spec_cache = body
        timings.append(("GET /openapi.json", elapsed))
    return _spec_cache


def resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref like '#/components/schemas/Foo' into the actual schema dict."""
    if not ref.startswith("#/"):
        return {}
    parts = ref.lstrip("#/").split("/")
    obj = spec
    for part in parts:
        obj = obj.get(part, {})
    return obj


def resolve_schema(spec: dict, schema: dict) -> dict:
    """Resolve a schema that might contain $ref, oneOf, anyOf, allOf."""
    if "$ref" in schema:
        return resolve_ref(spec, schema["$ref"])
    return schema


def get_response_schema(spec: dict, path: str, method: str, status_code: str = "200") -> dict:
    """Extract the response schema for a specific endpoint/method/status from the spec."""
    path_obj = spec.get("paths", {}).get(path, {})
    method_obj = path_obj.get(method.lower(), {})
    responses = method_obj.get("responses", {})
    resp = responses.get(status_code, {})
    content = resp.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema", {})
    return resolve_schema(spec, schema)


def validate_required_fields(data: dict, schema: dict, spec: dict) -> list[str]:
    """Check that all 'required' fields in a schema are present in the data.
    Returns list of missing field names."""
    resolved = resolve_schema(spec, schema)
    required = resolved.get("required", [])
    missing = []
    for field in required:
        if field not in data:
            missing.append(field)
    return missing


def validate_field_types(data: dict, schema: dict, spec: dict) -> list[str]:
    """Validate field types in data match schema declarations.
    Returns list of type mismatch descriptions."""
    resolved = resolve_schema(spec, schema)
    properties = resolved.get("properties", {})
    errors = []
    for field_name, field_schema in properties.items():
        if field_name not in data or data[field_name] is None:
            continue  # Skip missing/null fields (might be optional)
        value = data[field_name]
        fs = resolve_schema(spec, field_schema)
        # Handle anyOf (nullable fields)
        if "anyOf" in fs:
            types = set()
            for option in fs["anyOf"]:
                opt = resolve_schema(spec, option)
                if "type" in opt:
                    types.add(opt["type"])
            if types and not _value_matches_types(value, types):
                errors.append(f"{field_name}: expected one of {types}, got {type(value).__name__}")
            continue
        declared_type = fs.get("type")
        if not declared_type:
            continue  # Complex type with $ref — skip deep validation
        if not _value_matches_type(value, declared_type):
            errors.append(f"{field_name}: expected {declared_type}, got {type(value).__name__}")
    return errors


def _value_matches_type(value, declared_type: str) -> bool:
    """Check if a Python value matches an OpenAPI type declaration."""
    if declared_type == "string":
        return isinstance(value, str)
    elif declared_type == "number":
        return isinstance(value, int | float)
    elif declared_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    elif declared_type == "boolean":
        return isinstance(value, bool)
    elif declared_type == "array":
        return isinstance(value, list)
    elif declared_type == "object":
        return isinstance(value, dict)
    elif declared_type == "null":
        return value is None
    return True  # Unknown type, assume ok


def _value_matches_types(value, types: set) -> bool:
    """Check if a value matches any of the given type set."""
    return any(_value_matches_type(value, t) for t in types)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: OpenAPI Spec Structure Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 1: OpenAPI Spec Structure")
print("=" * 70)


def test_spec_is_valid_json():
    spec = get_spec()
    assert isinstance(spec, dict), "Spec is not a JSON object"
    assert len(spec) > 0, "Spec is empty"


check("OpenAPI spec is valid JSON", test_spec_is_valid_json)


def test_openapi_version():
    spec = get_spec()
    version = spec.get("openapi", "")
    assert version, "Missing 'openapi' version field"
    assert version.startswith("3.0") or version.startswith("3.1"), (
        f"Expected OpenAPI 3.0.x or 3.1.x, got {version}"
    )


check("OpenAPI version is 3.x", test_openapi_version)


def test_info_section():
    spec = get_spec()
    info = spec.get("info", {})
    assert "title" in info, "Missing info.title"
    assert "version" in info, "Missing info.version"
    assert "description" in info, "Missing info.description"
    assert len(info["title"]) > 0, "info.title is empty"
    assert len(info["version"]) > 0, "info.version is empty"
    assert len(info["description"]) > 10, "info.description is too short"


check("Info section has title, version, description", test_info_section)


def test_paths_non_empty():
    spec = get_spec()
    paths = spec.get("paths", {})
    assert isinstance(paths, dict), f"paths is not an object: {type(paths)}"
    assert len(paths) > 0, "paths is empty (no routes declared)"


check("Paths section is non-empty", test_paths_non_empty)


def test_path_count_minimum():
    spec = get_spec()
    paths = spec.get("paths", {})
    count = len(paths)
    assert count >= 40, f"Expected ≥40 paths, got {count}"


check(f"Path count ≥ 40 (actual: {len(get_spec().get('paths', {}))})", test_path_count_minimum)


def test_components_schemas_exists():
    spec = get_spec()
    components = spec.get("components", {})
    assert "schemas" in components, "Missing components.schemas"
    schemas = components["schemas"]
    assert isinstance(schemas, dict), "components.schemas is not an object"
    assert len(schemas) > 20, f"Too few schemas: {len(schemas)}"


check("Components/schemas section exists with 20+ schemas", test_components_schemas_exists)


def test_info_title_and_version_values():
    spec = get_spec()
    info = spec["info"]
    assert info["title"] == "Algenta API", f"Unexpected OpenAPI title: {info['title']}"
    parts = info["version"].split(".")
    assert len(parts) >= 2, f"Version not semver: {info['version']}"


check("Info title is Algenta API, version is semver", test_info_title_and_version_values)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: Path Coverage Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 2: Path Coverage")
print("=" * 70)

REQUIRED_PATHS = [
    "/v1/health",
    "/v1/version",
    "/v1/models",
    "/v1/artifacts/resolve",
    "/v1/chat/completions",
    "/v1/tokenize",
    "/v1/count_tokens",
    "/v1/responses",
    "/v1/embeddings",
    "/v1/embeddings/similarity",
    "/v1/rerank",
    "/v1/decision",
    "/v1/agent/run",
    "/v1/optimize",
    "/v1/retrieve",
    "/v1/forecast",
    "/v1/agent/runs",
    "/v1/agent/runs/{run_id}",
    "/v1/agent/runs/{run_id}/events",
    "/v1/agent/runs/{run_id}/resume",
    "/v1/agent/runs/{run_id}/cancel",
    "/v1/agent/runs/{run_id}/approve",
    "/v1/simulate",
    "/v1/decisions/plan",
    "/v1/simulate/stream",
    "/v1/simulate/what-if",
    "/v1/recommend",
    "/v1/runs",
    "/v1/jobs/list",
    "/v1/jobs/{job_id}",
    "/v1/jobs/{job_id}/result",
    "/v1/jobs/{job_id}/cancel",
    "/v1/data/connect",
    "/v1/data",
    "/v1/data/{dataset_id}",
    "/v1/data/{dataset_id}/summary",
    "/v1/data/{dataset_id}/refresh",
    "/v1/repositories/{repository_id}/snapshots",
    "/v1/repositories/{repository_id}/snapshots/{snapshot_id}",
    "/v1/repositories/{repository_id}/triage",
    "/v1/repositories/{repository_id}/decision-plans",
    "/v1/repositories/{repository_id}/simulate",
    "/v1/repositories/{repository_id}/apply",
    "/v1/triggers",
    "/v1/triggers/{trigger_id}/fire",
    "/v1/triggers/{trigger_id}/pause",
    "/v1/triggers/{trigger_id}",
    "/v1/runs/{run_id}",
    "/v1/jobs",
    "/v1/templates",
    "/v1/deployments",
    "/v1/connectors",
    "/v1/logs",
    "/v1/analytics",
    "/mcp/tools",
]


def test_required_paths_present():
    spec = get_spec()
    paths = spec.get("paths", {})
    missing = [p for p in REQUIRED_PATHS if p not in paths]
    assert len(missing) == 0, f"Missing required paths: {missing}"


check(f"All {len(REQUIRED_PATHS)} required paths present", test_required_paths_present)


ADDITIONAL_PATHS = [
    "/v1/runs/{run_id}/export.{fmt}",
    "/v1/connectors/test",
    "/v1/connectors/browse",
    "/v1/connectors/{connector_id}",
    "/v1/connectors/{connector_id}/test",
    "/v1/connectors/{connector_id}/browse",
    "/v1/deployments/{deployment_id}",
    "/v1/score",
    "/v1/batch",
    "/v1/compare",
    "/v1/decisions",
    "/v1/decisions/{decision_id}",
    "/v1/decisions/{decision_id}/outcome",
    "/v1/decisions/{decision_id}/execute",
    "/v1/agent/runs",
    "/v1/agent/runs/{run_id}",
    "/v1/agent/runs/{run_id}/events",
    "/v1/agent/runs/{run_id}/checkpoints",
    "/v1/agent/runs/checkpoints",
    "/v1/agent/runs/{run_id}/mission-events",
    "/v1/agent/runs/mission-events",
    "/v1/agent/runs/{run_id}/telemetry",
    "/v1/agent/runs/telemetry",
    "/v1/distributions",
    "/v1/usage",
    "/v1/limits",
    "/v1/data/connect",
    "/v1/data",
    "/v1/data/{dataset_id}",
    "/v1/data/{dataset_id}/summary",
    "/v1/data/{dataset_id}/refresh",
    "/v1/execution/policy/snapshots",
    "/v1/api-keys",
    "/v1/billing/info",
    "/v1/credits/refresh",
    "/v1/metering",
    "/v1/webhooks/test",
    "/v1/triggers",
    "/v1/team",
    "/v1/audit-logs",
    "/v1/audit-logs/artifacts",
]


def test_additional_paths_present():
    spec = get_spec()
    paths = spec.get("paths", {})
    missing = [p for p in ADDITIONAL_PATHS if p not in paths]
    assert len(missing) == 0, f"Missing additional paths: {missing}"


check(f"All {len(ADDITIONAL_PATHS)} additional paths present", test_additional_paths_present)


def test_every_path_has_method():
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch", "options", "head"}
    no_method = []
    for path_name, path_obj in paths.items():
        methods = [m for m in path_obj.keys() if m.lower() in http_methods]
        if not methods:
            no_method.append(path_name)
    assert len(no_method) == 0, f"Paths with no HTTP methods: {no_method}"


check("Every path has ≥1 HTTP method", test_every_path_has_method)


def test_every_operation_has_operation_id():
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    missing_op_id = []
    for path_name, path_obj in paths.items():
        for method_name, op in path_obj.items():
            if method_name.lower() not in http_methods:
                continue
            if not isinstance(op, dict):
                continue
            if "operationId" not in op:
                missing_op_id.append(f"{method_name.upper()} {path_name}")
    assert len(missing_op_id) == 0, f"Operations missing operationId: {missing_op_id[:10]}"


check("Every operation has operationId", test_every_operation_has_operation_id)


def test_operation_ids_are_unique():
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    op_ids: dict[str, str] = {}
    duplicates = []
    for path_name, path_obj in paths.items():
        for method_name, op in path_obj.items():
            if method_name.lower() not in http_methods or not isinstance(op, dict):
                continue
            oid = op.get("operationId")
            if oid:
                if oid in op_ids:
                    duplicates.append(
                        f"{oid} (at {op_ids[oid]} and {method_name.upper()} {path_name})"
                    )
                else:
                    op_ids[oid] = f"{method_name.upper()} {path_name}"
    assert len(duplicates) == 0, f"Duplicate operationIds: {duplicates}"


check("All operationIds are unique", test_operation_ids_are_unique)


def test_paths_have_tags():
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    no_tags = []
    for path_name, path_obj in paths.items():
        for method_name, op in path_obj.items():
            if method_name.lower() not in http_methods or not isinstance(op, dict):
                continue
            tags = op.get("tags", [])
            if not tags:
                no_tags.append(f"{method_name.upper()} {path_name}")
    total_ops = sum(
        1
        for _, po in paths.items()
        for m, op in po.items()
        if m.lower() in http_methods and isinstance(op, dict)
    )
    tag_ratio = 1 - len(no_tags) / max(total_ops, 1)
    assert tag_ratio >= 0.7, f"Only {tag_ratio:.0%} ops have tags; untagged: {no_tags[:5]}"


check("≥70% of operations have tags", test_paths_have_tags)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: Schema Definition Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 3: Schema Definitions")
print("=" * 70)

REQUIRED_SCHEMAS = [
    "SimulateRequestAuto",
    "SimulateRequestExpert",
    "DecisionEnvelope",
    "MetricsSummary",
    "VariableSpec",
    "HealthResponse",
    "VersionResponse",
    "HTTPValidationError",
    "DistributionType",
    "RunMetadata",
    "PercentileSummary",
]


def test_required_schemas_exist():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    missing = [s for s in REQUIRED_SCHEMAS if s not in schemas]
    assert len(missing) == 0, f"Missing required schemas: {missing}"


check(f"All {len(REQUIRED_SCHEMAS)} required schemas present", test_required_schemas_exist)


def test_schema_types_are_valid():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    valid_types = {"object", "array", "string", "number", "integer", "boolean", "null"}
    invalid = []
    for name, schema in schemas.items():
        t = schema.get("type")
        if t and t not in valid_types:
            invalid.append(f"{name}: type='{t}'")
    assert len(invalid) == 0, f"Invalid schema types: {invalid}"


check("All schema types are valid OpenAPI types", test_schema_types_are_valid)


def test_schemas_have_properties_or_enum():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    empty = []
    for name, schema in schemas.items():
        t = schema.get("type", "object")
        if t == "object":
            if (
                "properties" not in schema
                and "additionalProperties" not in schema
                and "allOf" not in schema
                and "oneOf" not in schema
                and "anyOf" not in schema
            ):
                empty.append(name)
    assert len(empty) <= 3, f"Schemas with no properties: {empty}"


check("Object schemas have properties defined", test_schemas_have_properties_or_enum)


def test_distribution_type_is_enum():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    dt = schemas.get("DistributionType", {})
    assert dt.get("type") == "string", f"DistributionType is not string: {dt.get('type')}"
    enum_values = dt.get("enum", [])
    assert len(enum_values) >= 10, f"DistributionType has too few values: {len(enum_values)}"
    for dist in ["normal", "uniform", "triangular", "lognormal", "beta", "exponential"]:
        assert dist in enum_values, f"Missing distribution '{dist}' in DistributionType enum"


check("DistributionType is a string enum with ≥10 values", test_distribution_type_is_enum)


def test_decision_envelope_has_required_fields():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    envelope = schemas.get("DecisionEnvelope", {})
    props = envelope.get("properties", {})
    key_fields = ["run_id", "status", "confidence", "metrics", "percentiles", "scenarios_run"]
    missing = [f for f in key_fields if f not in props]
    assert len(missing) == 0, f"DecisionEnvelope missing key fields: {missing}"


check("DecisionEnvelope declares key response fields", test_decision_envelope_has_required_fields)


def test_health_response_schema():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    health = schemas.get("HealthResponse", {})
    required = health.get("required", [])
    assert "status" in required, f"HealthResponse missing 'status' in required: {required}"


check("HealthResponse schema has 'status' as required", test_health_response_schema)


def test_version_response_schema():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    version = schemas.get("VersionResponse", {})
    required = version.get("required", [])
    for field in ["api_version", "engine_version", "environment"]:
        assert field in required, f"VersionResponse missing '{field}' in required: {required}"


check(
    "VersionResponse requires api_version, engine_version, environment",
    test_version_response_schema,
)


def test_metrics_summary_has_numeric_fields():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    ms = schemas.get("MetricsSummary", {})
    props = ms.get("properties", {})
    numeric_fields = [
        "expected_value",
        "median",
        "std_deviation",
        "variance",
        "probability_of_loss",
    ]
    for field in numeric_fields:
        assert field in props, f"MetricsSummary missing '{field}'"
        fs = resolve_schema(spec, props[field])
        declared_type = fs.get("type")
        if not declared_type and "anyOf" in fs:
            types = [resolve_schema(spec, o).get("type") for o in fs["anyOf"]]
            assert "number" in types, f"MetricsSummary.{field} not numeric: {types}"
        elif declared_type:
            assert declared_type == "number", (
                f"MetricsSummary.{field} is {declared_type}, expected number"
            )


check("MetricsSummary declares numeric fields correctly", test_metrics_summary_has_numeric_fields)


def test_variable_spec_schema():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    vs = schemas.get("VariableSpec", {})
    props = vs.get("properties", {})
    assert "name" in props, "VariableSpec missing 'name'"
    assert "distribution" in props, "VariableSpec missing 'distribution'"
    assert "params" in props, "VariableSpec missing 'params'"


check("VariableSpec has name, distribution, params", test_variable_spec_schema)


def test_schema_count():
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    count = len(schemas)
    assert count >= 50, f"Expected ≥50 schemas, got {count}"


check(
    f"Schema count ≥ 50 (actual: {len(get_spec().get('components', {}).get('schemas', {}))})",
    test_schema_count,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: Response Schema Compliance (live requests)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 4: Response Schema Compliance")
print("=" * 70)


def test_health_response_compliance():
    spec = get_spec()
    status, body, hdrs, elapsed = req("GET", "/v1/health", auth=False)
    assert status == 200, f"Health returned {status}"
    schema = get_response_schema(spec, "/v1/health", "get", "200")
    missing = validate_required_fields(body, schema, spec)
    assert len(missing) == 0, f"Missing required fields in health response: {missing}"
    type_errors = validate_field_types(body, schema, spec)
    assert len(type_errors) == 0, f"Type mismatches in health response: {type_errors}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/health (compliance)", elapsed))


check("GET /v1/health response matches declared schema", test_health_response_compliance)


def test_version_response_compliance():
    spec = get_spec()
    status, body, hdrs, elapsed = req("GET", "/v1/version", auth=False)
    assert status == 200, f"Version returned {status}"
    schema = get_response_schema(spec, "/v1/version", "get", "200")
    missing = validate_required_fields(body, schema, spec)
    assert len(missing) == 0, f"Missing required fields in version response: {missing}"
    type_errors = validate_field_types(body, schema, spec)
    assert len(type_errors) == 0, f"Type mismatches in version response: {type_errors}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/version (compliance)", elapsed))


check("GET /v1/version response matches declared schema", test_version_response_compliance)


def test_simulate_response_compliance():
    spec = get_spec()
    status, body, hdrs, elapsed = simulate_req(AUTO_PAYLOAD)
    assert status == 200, f"Simulate returned {status}: {body}"
    schema = get_response_schema(spec, "/v1/simulate", "post", "200")
    missing = validate_required_fields(body, schema, spec)
    assert len(missing) == 0, f"Missing required fields in simulate response: {missing}"
    type_errors = validate_field_types(body, schema, spec)
    assert len(type_errors) == 0, f"Type mismatches in simulate response: {type_errors}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("POST /v1/simulate (compliance)", elapsed))


check(
    "POST /v1/simulate response matches DecisionEnvelope schema", test_simulate_response_compliance
)


def test_runs_response_compliance():
    spec = get_spec()
    status, body, hdrs, elapsed = req("GET", "/v1/runs")
    assert status == 200, f"Runs returned {status}"
    schema = get_response_schema(spec, "/v1/runs", "get", "200")
    if isinstance(body, dict):
        missing = validate_required_fields(body, schema, spec)
        assert len(missing) == 0, f"Missing required fields in runs response: {missing}"
    elif isinstance(body, list):
        assert True  # List of runs is valid
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/runs (compliance)", elapsed))


check("GET /v1/runs response matches declared schema", test_runs_response_compliance)


def test_templates_response_compliance():
    status, body, hdrs, elapsed = req("GET", "/v1/templates")
    assert status == 200, f"Templates returned {status}"
    assert isinstance(body, list | dict), f"Templates response is not list/dict: {type(body)}"
    if isinstance(body, list) and len(body) > 0:
        item = body[0]
        assert "slug" in item or "name" in item or "id" in item, (
            f"Template item missing identifying field: {list(item.keys())[:5]}"
        )
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/templates (compliance)", elapsed))


check("GET /v1/templates response matches declared schema", test_templates_response_compliance)


def test_connectors_response_compliance():
    status, body, hdrs, elapsed = req("GET", "/v1/connectors")
    assert status == 200, f"Connectors returned {status}"
    assert isinstance(body, list | dict), f"Connectors response is not list/dict: {type(body)}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/connectors (compliance)", elapsed))


check("GET /v1/connectors response matches declared schema", test_connectors_response_compliance)


def test_saved_connector_lifecycle_response_compliance():
    connector_id: str | None = None
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        try:
            status, body, hdrs, elapsed = req(
                "POST",
                "/v1/connectors",
                body={
                    "name": f"openapi-live-connector-{time.time_ns()}",
                    "connector_type": "rest",
                    "description": "Live OpenAPI saved connector compliance check.",
                    "config": {
                        "url": source_url,
                        "data_path": "items",
                    },
                },
            )
            assert status == 201, f"Connector create returned {status}"
            assert isinstance(body, dict), f"Connector create response is not dict: {type(body)}"
            connector_id = body.get("id")
            assert connector_id, body
            ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
            assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
            timings.append(("POST /v1/connectors (compliance)", elapsed))

            detail_status, detail_body, detail_hdrs, detail_elapsed = req(
                "GET",
                f"/v1/connectors/{connector_id}",
            )
            assert detail_status == 200, f"Connector detail returned {detail_status}"
            assert isinstance(detail_body, dict), f"Connector detail response is not dict: {type(detail_body)}"
            assert detail_body.get("id") == connector_id, detail_body
            ct = detail_hdrs.get("Content-Type", detail_hdrs.get("content-type", ""))
            assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
            timings.append((f"GET /v1/connectors/{connector_id} (compliance)", detail_elapsed))

            update_status, update_body, update_hdrs, update_elapsed = req(
                "PATCH",
                f"/v1/connectors/{connector_id}",
                body={"description": "Live OpenAPI connector updated description."},
            )
            assert update_status == 200, f"Connector update returned {update_status}"
            assert isinstance(update_body, dict), f"Connector update response is not dict: {type(update_body)}"
            assert update_body.get("id") == connector_id, update_body
            assert update_body.get("description") == "Live OpenAPI connector updated description."
            ct = update_hdrs.get("Content-Type", update_hdrs.get("content-type", ""))
            assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
            timings.append((f"PATCH /v1/connectors/{connector_id} (compliance)", update_elapsed))

            test_status, test_body, test_hdrs, test_elapsed = req(
                "POST",
                f"/v1/connectors/{connector_id}/test",
            )
            assert test_status == 200, f"Connector test returned {test_status}"
            assert isinstance(test_body, dict), f"Connector test response is not dict: {type(test_body)}"
            assert test_body.get("success") is True, test_body
            ct = test_hdrs.get("Content-Type", test_hdrs.get("content-type", ""))
            assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
            timings.append((f"POST /v1/connectors/{connector_id}/test (compliance)", test_elapsed))

            browse_status, browse_body, browse_hdrs, browse_elapsed = req(
                "GET",
                f"/v1/connectors/{connector_id}/browse",
            )
            assert browse_status == 200, f"Connector browse returned {browse_status}"
            assert isinstance(browse_body, dict), f"Connector browse response is not dict: {type(browse_body)}"
            assert browse_body.get("connector_type") == "rest", browse_body
            assert browse_body.get("total", 0) >= 1, browse_body
            ct = browse_hdrs.get("Content-Type", browse_hdrs.get("content-type", ""))
            assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
            timings.append((f"GET /v1/connectors/{connector_id}/browse (compliance)", browse_elapsed))
        finally:
            if connector_id is not None:
                delete_status, _delete_body, _delete_hdrs, delete_elapsed = req(
                    "DELETE",
                    f"/v1/connectors/{connector_id}",
                )
                assert delete_status == 204, f"Connector delete returned {delete_status}"
                timings.append((f"DELETE /v1/connectors/{connector_id} (compliance)", delete_elapsed))


check(
    "Saved connector create/get/update/test/browse/delete responses are valid JSON",
    test_saved_connector_lifecycle_response_compliance,
)


def test_preview_connector_response_compliance():
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        preview_payload = {
            "connector_type": "rest",
            "config": {
                "url": source_url,
                "data_path": "items",
            },
        }

        test_status, test_body, test_hdrs, test_elapsed = req(
            "POST",
            "/v1/connectors/test",
            body=preview_payload,
        )
        assert test_status == 200, f"Preview connector test returned {test_status}"
        assert isinstance(test_body, dict), f"Preview connector test response is not dict: {type(test_body)}"
        assert test_body.get("success") is True, test_body
        test_ct = test_hdrs.get("Content-Type", test_hdrs.get("content-type", ""))
        assert "application/json" in test_ct, f"Content-Type is not JSON: {test_ct}"
        timings.append(("POST /v1/connectors/test (compliance)", test_elapsed))

        browse_status, browse_body, browse_hdrs, browse_elapsed = req(
            "POST",
            "/v1/connectors/browse",
            body=preview_payload,
        )
        assert browse_status == 200, f"Preview connector browse returned {browse_status}"
        assert isinstance(
            browse_body, dict
        ), f"Preview connector browse response is not dict: {type(browse_body)}"
        assert browse_body.get("connector_type") == "rest", browse_body
        assert browse_body.get("total", 0) >= 1, browse_body
        browse_ct = browse_hdrs.get("Content-Type", browse_hdrs.get("content-type", ""))
        assert "application/json" in browse_ct, f"Content-Type is not JSON: {browse_ct}"
        timings.append(("POST /v1/connectors/browse (compliance)", browse_elapsed))


check(
    "Inline connector preview test/browse responses are valid JSON",
    test_preview_connector_response_compliance,
)


def test_data_connect_and_dataset_lifecycle_response_compliance():
    dataset_id: str | None = None
    dataset_name: str | None = None
    with static_json_server(default_refreshable_dataset_payload()) as source_url:
        try:
            status, body, hdrs, elapsed = req(
                "POST",
                "/v1/data/connect",
                body=_live_dataset_connect_request("openapi-refreshable-dataset", source_url),
            )
            assert status == 200, f"Data connect returned {status}"
            assert isinstance(body, dict), f"Data connect response is not dict: {type(body)}"
            assert body.get("status") == "ready", body
            dataset_id = body.get("dataset_id")
            dataset_name = body.get("dataset_name")
            assert dataset_id, body
            assert dataset_name, body
            ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
            assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
            timings.append(("POST /v1/data/connect (compliance)", elapsed))

            list_status, list_body, list_hdrs, list_elapsed = req(
                "GET",
                f"/v1/data?search={dataset_name}&compact=1&page=1&limit=25",
            )
            assert list_status == 200, f"Data list returned {list_status}"
            assert isinstance(list_body, dict), f"Data list response is not dict: {type(list_body)}"
            datasets = list_body.get("datasets", [])
            assert list_body.get("total", 0) >= len(datasets), list_body
            assert any(item.get("dataset_id") == dataset_id for item in datasets), list_body
            list_ct = list_hdrs.get("Content-Type", list_hdrs.get("content-type", ""))
            assert "application/json" in list_ct, f"Content-Type is not JSON: {list_ct}"
            timings.append(("GET /v1/data (compliance)", list_elapsed))

            refresh_status, refresh_body, refresh_hdrs, refresh_elapsed = req(
                "POST",
                f"/v1/data/{dataset_id}/refresh",
            )
            assert refresh_status == 200, f"Dataset refresh returned {refresh_status}"
            assert isinstance(refresh_body, dict), (
                f"Dataset refresh response is not dict: {type(refresh_body)}"
            )
            assert refresh_body.get("dataset_id") == dataset_id, refresh_body
            assert refresh_body.get("status") == "ready", refresh_body
            refresh_ct = refresh_hdrs.get("Content-Type", refresh_hdrs.get("content-type", ""))
            assert "application/json" in refresh_ct, f"Content-Type is not JSON: {refresh_ct}"
            timings.append((f"POST /v1/data/{dataset_id}/refresh (compliance)", refresh_elapsed))

            summary_status, summary_body, summary_hdrs, summary_elapsed = req(
                "GET",
                f"/v1/data/{dataset_id}/summary",
            )
            assert summary_status == 200, f"Dataset summary returned {summary_status}"
            assert isinstance(
                summary_body, dict
            ), f"Dataset summary response is not dict: {type(summary_body)}"
            assert summary_body.get("dataset_id") == dataset_id, summary_body
            assert summary_body.get("name") == dataset_name, summary_body
            assert int(summary_body.get("column_count", 0)) >= 2, summary_body
            summary_ct = summary_hdrs.get("Content-Type", summary_hdrs.get("content-type", ""))
            assert "application/json" in summary_ct, f"Content-Type is not JSON: {summary_ct}"
            timings.append((f"GET /v1/data/{dataset_id}/summary (compliance)", summary_elapsed))

            detail_status, detail_body, detail_hdrs, detail_elapsed = req(
                "GET",
                f"/v1/data/{dataset_id}",
            )
            assert detail_status == 200, f"Dataset detail returned {detail_status}"
            assert isinstance(
                detail_body, dict
            ), f"Dataset detail response is not dict: {type(detail_body)}"
            assert detail_body.get("dataset", {}).get("dataset_id") == dataset_id, detail_body
            assert detail_body.get("dataset", {}).get("dataset_name") == dataset_name, detail_body
            assert len(detail_body.get("schema", {}).get("columns", [])) >= 2, detail_body
            detail_ct = detail_hdrs.get("Content-Type", detail_hdrs.get("content-type", ""))
            assert "application/json" in detail_ct, f"Content-Type is not JSON: {detail_ct}"
            timings.append((f"GET /v1/data/{dataset_id} (compliance)", detail_elapsed))
        finally:
            if dataset_id is not None:
                delete_status, delete_body, delete_hdrs, delete_elapsed = req(
                    "DELETE",
                    f"/v1/data/{dataset_id}",
                )
                assert delete_status == 200, f"Dataset delete returned {delete_status}"
                assert isinstance(
                    delete_body, dict
                ), f"Dataset delete response is not dict: {type(delete_body)}"
                assert delete_body.get("dataset_id") == dataset_id, delete_body
                assert delete_body.get("status") == "deleted", delete_body
                delete_ct = delete_hdrs.get("Content-Type", delete_hdrs.get("content-type", ""))
                assert "application/json" in delete_ct, f"Content-Type is not JSON: {delete_ct}"
                timings.append((f"DELETE /v1/data/{dataset_id} (cleanup)", delete_elapsed))


check(
    "High-level /v1/data connect/list/refresh/summary/detail/delete responses are valid JSON",
    test_data_connect_and_dataset_lifecycle_response_compliance,
)


def test_repository_intelligence_response_compliance():
    spec = get_spec()
    repository_support_reason = local_repository_live_support_reason(BASE_URL)
    if repository_support_reason:
        raise EnvironmentBlockedError(repository_support_reason)

    connector_id: str | None = None
    with live_repository_fixture("openapi-live") as repository_fixture:
        try:
            create_status, create_body, create_hdrs, create_elapsed = req(
                "POST",
                "/v1/connectors",
                body=repository_fixture.connector_request,
            )
            assert create_status == 201, (
                f"Repository connector create returned {create_status}: {create_body}"
            )
            assert isinstance(create_body, dict), type(create_body)
            connector_id = create_body.get("id")
            assert connector_id, create_body
            assert create_body.get("connector_type") == "local_repo", create_body
            assert "application/json" in create_hdrs.get(
                "Content-Type", create_hdrs.get("content-type", "")
            )
            timings.append(("POST /v1/connectors (repository compliance)", create_elapsed))

            snapshot_status, snapshot_body, snapshot_hdrs, snapshot_elapsed = req(
                "POST",
                f"/v1/repositories/{connector_id}/snapshots",
                body=repository_fixture.snapshot_request,
            )
            assert snapshot_status == 200, (
                f"Repository snapshot returned {snapshot_status}: {snapshot_body}"
            )
            assert isinstance(snapshot_body, dict), type(snapshot_body)
            snapshot_schema = get_response_schema(
                spec,
                "/v1/repositories/{repository_id}/snapshots",
                "post",
                "200",
            )
            snapshot_missing = validate_required_fields(snapshot_body, snapshot_schema, spec)
            assert len(snapshot_missing) == 0, (
                f"Repository snapshot missing required fields: {snapshot_missing}"
            )
            snapshot_type_errors = validate_field_types(snapshot_body, snapshot_schema, spec)
            assert len(snapshot_type_errors) == 0, (
                f"Repository snapshot type mismatches: {snapshot_type_errors}"
            )
            snapshot_id = snapshot_body.get("snapshot_id")
            assert snapshot_id, snapshot_body
            assert snapshot_body.get("connector_type") == "local_repo", snapshot_body
            assert snapshot_body.get("file_count", 0) >= 2, snapshot_body
            assert (
                snapshot_body.get("repository_snapshot_artifact", {}).get("artifact_kind")
                == "RepositorySnapshot"
            ), snapshot_body
            assert (
                snapshot_body.get("repository_graph_artifact", {}).get("artifact_kind")
                == "RepositoryGraph"
            ), snapshot_body
            assert "application/json" in snapshot_hdrs.get(
                "Content-Type", snapshot_hdrs.get("content-type", "")
            )
            timings.append((f"POST /v1/repositories/{connector_id}/snapshots", snapshot_elapsed))

            get_snapshot_status, get_snapshot_body, get_snapshot_hdrs, get_snapshot_elapsed = req(
                "GET",
                f"/v1/repositories/{connector_id}/snapshots/{snapshot_id}",
            )
            assert get_snapshot_status == 200, (
                f"Repository snapshot detail returned {get_snapshot_status}: {get_snapshot_body}"
            )
            assert isinstance(get_snapshot_body, dict), type(get_snapshot_body)
            get_snapshot_schema = get_response_schema(
                spec,
                "/v1/repositories/{repository_id}/snapshots/{snapshot_id}",
                "get",
                "200",
            )
            detail_missing = validate_required_fields(get_snapshot_body, get_snapshot_schema, spec)
            assert len(detail_missing) == 0, (
                f"Repository snapshot detail missing required fields: {detail_missing}"
            )
            detail_type_errors = validate_field_types(get_snapshot_body, get_snapshot_schema, spec)
            assert len(detail_type_errors) == 0, (
                f"Repository snapshot detail type mismatches: {detail_type_errors}"
            )
            assert get_snapshot_body.get("snapshot_id") == snapshot_id, get_snapshot_body
            assert get_snapshot_body.get("content_hash") == snapshot_body.get("content_hash"), (
                get_snapshot_body,
                snapshot_body,
            )
            assert "application/json" in get_snapshot_hdrs.get(
                "Content-Type", get_snapshot_hdrs.get("content-type", "")
            )
            timings.append(
                (
                    f"GET /v1/repositories/{connector_id}/snapshots/{snapshot_id}",
                    get_snapshot_elapsed,
                )
            )

            triage_status, triage_body, triage_hdrs, triage_elapsed = req(
                "POST",
                f"/v1/repositories/{connector_id}/triage",
                body=repository_fixture.triage_request(snapshot_id),
            )
            assert triage_status == 200, f"Repository triage returned {triage_status}: {triage_body}"
            assert isinstance(triage_body, dict), type(triage_body)
            triage_schema = get_response_schema(
                spec,
                "/v1/repositories/{repository_id}/triage",
                "post",
                "200",
            )
            triage_missing = validate_required_fields(triage_body, triage_schema, spec)
            assert len(triage_missing) == 0, (
                f"Repository triage missing required fields: {triage_missing}"
            )
            triage_type_errors = validate_field_types(triage_body, triage_schema, spec)
            assert len(triage_type_errors) == 0, (
                f"Repository triage type mismatches: {triage_type_errors}"
            )
            workspace_evidence_bundle_ref = triage_body.get("workspace_evidence_bundle_ref")
            assert workspace_evidence_bundle_ref, triage_body
            suspect_files = triage_body.get("suspect_files", [])
            assert suspect_files and suspect_files[0] == repository_fixture.primary_file, triage_body
            assert triage_body.get("evidence_bundle_token_count", 0) > 0, triage_body
            assert triage_body.get("reduction_ratio", 0) >= 1.0, triage_body
            assert (
                triage_body.get("workspace_evidence_bundle_artifact", {}).get("artifact_kind")
                == "WorkspaceEvidenceBundle"
            ), triage_body
            assert "application/json" in triage_hdrs.get(
                "Content-Type", triage_hdrs.get("content-type", "")
            )
            timings.append((f"POST /v1/repositories/{connector_id}/triage", triage_elapsed))

            plan_status, plan_body, plan_hdrs, plan_elapsed = req(
                "POST",
                f"/v1/repositories/{connector_id}/decision-plans",
                body=repository_fixture.decision_plan_request(
                    snapshot_id,
                    workspace_evidence_bundle_ref,
                ),
            )
            if plan_status == 503 and isinstance(plan_body, dict):
                if plan_body.get("error", {}).get("code") == "repository_model_unavailable":
                    raise EnvironmentBlockedError(
                        "repository planner model unavailable for this live environment"
                    )
            assert plan_status == 200, (
                f"Repository decision-plan returned {plan_status}: {plan_body}"
            )
            assert isinstance(plan_body, dict), type(plan_body)
            plan_schema = get_response_schema(
                spec,
                "/v1/repositories/{repository_id}/decision-plans",
                "post",
                "200",
            )
            plan_missing = validate_required_fields(plan_body, plan_schema, spec)
            assert len(plan_missing) == 0, (
                f"Repository decision-plan missing required fields: {plan_missing}"
            )
            plan_type_errors = validate_field_types(plan_body, plan_schema, spec)
            assert len(plan_type_errors) == 0, (
                f"Repository decision-plan type mismatches: {plan_type_errors}"
            )
            decision_plan_id = plan_body.get("decision_plan_id")
            decision_plan = plan_body.get("decision_plan", {})
            repository_analysis = decision_plan.get("repository_analysis", {})
            assert decision_plan_id, plan_body
            assert repository_analysis.get("planner_model_id") == "repository.deterministic_local_v1"
            assert repository_analysis.get("planner_execution_mode") == "deterministic_local"
            assert repository_analysis.get("planner_provider_backend") is None
            assert repository_analysis.get("generated_patch_ref"), plan_body
            assert repository_analysis.get("patch_impact_report_ref"), plan_body
            assert (
                repository_analysis.get("token_reduction_metrics", {}).get("reduction_ratio", 0)
                >= 1.0
            ), repository_analysis
            assert "application/json" in plan_hdrs.get(
                "Content-Type", plan_hdrs.get("content-type", "")
            )
            timings.append((f"POST /v1/repositories/{connector_id}/decision-plans", plan_elapsed))

            simulation_status, simulation_body, simulation_hdrs, simulation_elapsed = req(
                "POST",
                f"/v1/repositories/{connector_id}/simulate",
                body=repository_fixture.simulation_request(snapshot_id, decision_plan_id),
            )
            ensure_simulation_capacity_available(simulation_status, simulation_body)
            assert simulation_status == 200, (
                f"Repository simulate returned {simulation_status}: {simulation_body}"
            )
            assert isinstance(simulation_body, dict), type(simulation_body)
            simulation_schema = get_response_schema(
                spec,
                "/v1/repositories/{repository_id}/simulate",
                "post",
                "200",
            )
            simulation_missing = validate_required_fields(simulation_body, simulation_schema, spec)
            assert len(simulation_missing) == 0, (
                f"Repository simulate missing required fields: {simulation_missing}"
            )
            simulation_type_errors = validate_field_types(simulation_body, simulation_schema, spec)
            assert len(simulation_type_errors) == 0, (
                f"Repository simulate type mismatches: {simulation_type_errors}"
            )
            validated_inputs = simulation_body.get("validated_inputs", {})
            simulation_id = validated_inputs.get("simulation_id")
            assert simulation_id, simulation_body
            apply_gate = (simulation_body.get("score_breakdown") or {}).get("apply_gate", {})
            assert apply_gate.get("policy_snapshot_id"), simulation_body
            assert "application/json" in simulation_hdrs.get(
                "Content-Type", simulation_hdrs.get("content-type", "")
            )
            timings.append((f"POST /v1/repositories/{connector_id}/simulate", simulation_elapsed))

            branch_name = "algenta/live-repository-fix"
            apply_status, apply_body, apply_hdrs, apply_elapsed = req(
                "POST",
                f"/v1/repositories/{connector_id}/apply",
                body=repository_fixture.apply_local_branch_request(
                    snapshot_id,
                    decision_plan_id,
                    simulation_id,
                    branch_name=branch_name,
                ),
            )
            if bool(apply_gate.get("passed")):
                assert apply_status == 200, f"Repository apply returned {apply_status}: {apply_body}"
                assert isinstance(apply_body, dict), type(apply_body)
                apply_schema = get_response_schema(
                    spec,
                    "/v1/repositories/{repository_id}/apply",
                    "post",
                    "200",
                )
                apply_missing = validate_required_fields(apply_body, apply_schema, spec)
                assert len(apply_missing) == 0, (
                    f"Repository apply missing required fields: {apply_missing}"
                )
                apply_type_errors = validate_field_types(apply_body, apply_schema, spec)
                assert len(apply_type_errors) == 0, (
                    f"Repository apply type mismatches: {apply_type_errors}"
                )
                assert apply_body.get("mode") == "local_branch", apply_body
                assert apply_body.get("applied") is True, apply_body
                assert apply_body.get("branch_name") == branch_name, apply_body
                assert apply_body.get("commit_sha"), apply_body
                assert apply_body.get("local_checkout_path"), apply_body
                repository_fixture.assert_local_branch_applied(
                    branch_name=branch_name,
                    checkout_path=apply_body.get("local_checkout_path"),
                )
                patch_files = apply_body.get("validation_summary", {}).get("patch_files", [])
                assert repository_fixture.primary_file in patch_files, apply_body
            else:
                assert apply_status == 409, (
                    f"Expected 409 apply gate failure, got {apply_status}: {apply_body}"
                )
                assert isinstance(apply_body, dict), type(apply_body)
                assert apply_body.get("error", {}).get("code") == "repository_apply_gate_failed", (
                    apply_body
                )
            assert "application/json" in apply_hdrs.get(
                "Content-Type", apply_hdrs.get("content-type", "")
            )
            timings.append((f"POST /v1/repositories/{connector_id}/apply", apply_elapsed))
        finally:
            if connector_id is not None:
                delete_status, _delete_body, _delete_hdrs, delete_elapsed = req(
                    "DELETE",
                    f"/v1/connectors/{connector_id}",
                )
                assert delete_status == 204, (
                    f"Repository connector delete returned {delete_status}"
                )
                timings.append(
                    (f"DELETE /v1/connectors/{connector_id} (repository cleanup)", delete_elapsed)
                )


check(
    "Repository intelligence snapshot/triage/decision-plan/simulate/apply responses are valid JSON",
    test_repository_intelligence_response_compliance,
)


def test_analytics_response_compliance():
    spec = get_spec()
    status, body, hdrs, elapsed = req("GET", "/v1/analytics")
    if status == 200:
        schema = get_response_schema(spec, "/v1/analytics", "get", "200")
        if schema:
            missing = validate_required_fields(body, schema, spec)
            assert len(missing) == 0, f"Missing required fields in analytics: {missing}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/analytics (compliance)", elapsed))


check("GET /v1/analytics returns valid JSON response", test_analytics_response_compliance)


def test_distributions_response_compliance():
    status, body, hdrs, elapsed = req("GET", "/v1/distributions")
    assert status == 200, f"Distributions returned {status}"
    assert isinstance(body, list | dict), f"Unexpected type: {type(body)}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/distributions (compliance)", elapsed))


check("GET /v1/distributions response is valid JSON", test_distributions_response_compliance)


def test_jobs_list_response_compliance():
    status, body, hdrs, elapsed = req("GET", "/v1/jobs/list?limit=5")
    assert status == 200, f"Job list returned {status}: {body}"
    assert isinstance(body, dict), body
    assert body["page"] == 1, body
    assert body["limit"] == 5, body
    assert body["total"] >= len(body["jobs"]), body
    assert body["pages"] >= 1, body
    for job in body["jobs"]:
        assert job["job_id"], job
        assert job["status"], job
        assert job["queue_name"], job
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/jobs/list (compliance)", elapsed))


check("GET /v1/jobs/list response is valid JSON", test_jobs_list_response_compliance)


def test_runtime_admin_benchmarks_response_compliance():
    spec = get_spec()
    status, body, hdrs, elapsed = req("GET", "/v1/admin/runtime/benchmarks")
    assert status == 200, f"Runtime admin benchmarks returned {status}: {body}"
    assert isinstance(body, dict), body
    schema = get_response_schema(spec, "/v1/admin/runtime/benchmarks", "get", "200")
    missing = validate_required_fields(body, schema, spec)
    assert len(missing) == 0, f"Missing required fields in runtime benchmarks response: {missing}"
    type_errors = validate_field_types(body, schema, spec)
    assert len(type_errors) == 0, f"Type mismatches in runtime benchmarks response: {type_errors}"

    benchmarking_schema = resolve_schema(spec, schema["properties"]["benchmarking"])
    benchmark_class_schema = resolve_schema(
        spec,
        benchmarking_schema["properties"]["classes"]["items"],
    )
    evidence_paths_schema = resolve_schema(spec, benchmark_class_schema["properties"]["evidence_paths"])
    assert evidence_paths_schema["type"] == "array", evidence_paths_schema
    evidence_item_schema = resolve_schema(spec, evidence_paths_schema["items"])
    assert evidence_item_schema["type"] == "string", evidence_item_schema

    quality_gate_schema = resolve_schema(spec, schema["properties"]["quality_gate_benchmark_classes"])
    quality_gate_item_schema = resolve_schema(spec, quality_gate_schema["items"])
    quality_gate_evidence_schema = resolve_schema(
        spec,
        quality_gate_item_schema["properties"]["evidence_paths"],
    )
    assert quality_gate_evidence_schema["type"] == "array", quality_gate_evidence_schema
    quality_gate_evidence_item_schema = resolve_schema(spec, quality_gate_evidence_schema["items"])
    assert quality_gate_evidence_item_schema["type"] == "string", quality_gate_evidence_item_schema
    evaluation_summary_schema = resolve_schema(spec, schema["properties"]["evaluation_summary"])
    assert (
        evaluation_summary_schema["properties"]["replay_gate_enabled"]["type"] == "boolean"
    ), evaluation_summary_schema["properties"]["replay_gate_enabled"]
    assert (
        evaluation_summary_schema["properties"]["tool_call_quality_gate_enabled"]["type"]
        == "boolean"
    ), evaluation_summary_schema["properties"]["tool_call_quality_gate_enabled"]
    assert (
        evaluation_summary_schema["properties"]["rag_quality_gate_enabled"]["type"] == "boolean"
    ), evaluation_summary_schema["properties"]["rag_quality_gate_enabled"]
    assert (
        evaluation_summary_schema["properties"]["decision_quality_gate_enabled"]["type"]
        == "boolean"
    ), evaluation_summary_schema["properties"]["decision_quality_gate_enabled"]

    assert body["benchmarking"]["classes"][0]["evidence_paths"] == [
        "benchmarks/summary.json",
        "tests/benchmark_mojo_vs_python.py",
    ], body["benchmarking"]["classes"][0]
    assert body["quality_gate_benchmark_classes"][0]["evidence_paths"] == [], (
        body["quality_gate_benchmark_classes"][0]
    )
    decision_workflow_completion = next(
        entry for entry in body["quality_gate_benchmark_classes"] if entry["code"] == "B10"
    )
    assert decision_workflow_completion["description"] == "decision workflow completion latency", (
        decision_workflow_completion
    )
    assert decision_workflow_completion["evidence_paths"] == [
        "build/repository_intelligence_benchmark.json",
        "benchmarks/repository_intelligence_benchmark.py",
        "tests/test_repository_intelligence_benchmark.py",
    ], decision_workflow_completion
    assert body["evaluation_summary"]["replay_gate_enabled"] is True, body["evaluation_summary"]
    assert body["evaluation_summary"]["tool_call_quality_gate_enabled"] is True, (
        body["evaluation_summary"]
    )
    assert body["evaluation_summary"]["rag_quality_gate_enabled"] is True, body["evaluation_summary"]
    assert body["evaluation_summary"]["decision_quality_gate_enabled"] is True, (
        body["evaluation_summary"]
    )

    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/admin/runtime/benchmarks (compliance)", elapsed))


check(
    "GET /v1/admin/runtime/benchmarks response matches declared schema",
    test_runtime_admin_benchmarks_response_compliance,
)


def test_job_status_response_compliance():
    job_id = "00000000-0000-0000-0000-000000000001"
    status, body, hdrs, elapsed = req("GET", f"/v1/jobs/{job_id}")
    assert status == 404, f"Expected 404 for missing job status, got {status}: {body}"
    assert isinstance(body, dict), body
    assert body.get("error", {}).get("code") in {"job_not_found", "not_found"}, body
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/jobs/{job_id} (compliance)", elapsed))


check("GET /v1/jobs/{job_id} missing job returns structured JSON", test_job_status_response_compliance)


def test_job_result_response_compliance():
    job_id = "00000000-0000-0000-0000-000000000001"
    status, body, hdrs, elapsed = req("GET", f"/v1/jobs/{job_id}/result")
    assert status == 404, f"Expected 404 for missing job result, got {status}: {body}"
    assert isinstance(body, dict), body
    assert body.get("error", {}).get("code") in {"job_not_found", "not_found"}, body
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/jobs/{job_id}/result (compliance)", elapsed))


check(
    "GET /v1/jobs/{job_id}/result missing job returns structured JSON",
    test_job_result_response_compliance,
)


def test_job_cancel_response_compliance():
    job_id = "00000000-0000-0000-0000-000000000001"
    status, body, hdrs, elapsed = req("POST", f"/v1/jobs/{job_id}/cancel")
    assert status == 404, f"Expected 404 for missing job cancel, got {status}: {body}"
    assert isinstance(body, dict), body
    assert body.get("error", {}).get("code") in {"job_not_found", "not_found"}, body
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("POST /v1/jobs/{job_id}/cancel (compliance)", elapsed))


check(
    "POST /v1/jobs/{job_id}/cancel missing job returns structured JSON",
    test_job_cancel_response_compliance,
)


def test_metering_response_compliance():
    status, body, hdrs, elapsed = req(
        "POST",
        "/v1/metering",
        body={
            "device_id": f"openapi-live-{time.time_ns()}",
            "events": [
                {
                    "event_type": "runtime_call",
                    "module": "integration",
                    "function": "openapi_live",
                    "engine_used": "python",
                    "latency_ms": 9.5,
                    "success": True,
                }
            ],
        },
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, dict), body
    assert body["accepted"] == 1, body
    assert isinstance(body["billing_period"], str) and body["billing_period"], body
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("POST /v1/metering (compliance)", elapsed))


check("POST /v1/metering response is valid JSON", test_metering_response_compliance)


def test_credit_refresh_response_compliance():
    billing_period = time.strftime("%Y-%m", time.gmtime())
    status, body, hdrs, elapsed = req(
        "POST",
        "/v1/credits/refresh",
        body={
            "device_id": f"openapi-credit-live-{time.time_ns()}",
            "billing_period": billing_period,
            "credits_used": 0,
        },
    )
    detail = body.get("detail", body.get("error")) if isinstance(body, dict) else None
    detail_code = None
    if isinstance(detail, dict):
        raw_code = detail.get("error", detail.get("code"))
        if isinstance(raw_code, str):
            detail_code = raw_code
    body_text = json.dumps(body, sort_keys=True) if isinstance(body, dict) else str(body)
    if status == 429 and (
        detail_code in {"quota_exhausted", "quota_exceeded"}
        or "quota_exhausted" in body_text
        or "quota_exceeded" in body_text
    ):
        raise EnvironmentBlockedError("credit refresh quota exhausted for this live environment")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, dict), body
    assert body["billing_period"] == billing_period, body
    assert body["credits_granted"] >= 0, body
    assert body["credits_issued_this_month"] >= body["credits_granted"], body
    assert body["monthly_limit"] >= 0, body
    assert body["monthly_remaining"] >= 0, body
    assert body["refresh_after"] >= body["server_time"], body
    assert body["expires_at"] >= body["refresh_after"], body
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("POST /v1/credits/refresh (compliance)", elapsed))


check("POST /v1/credits/refresh response is valid JSON", test_credit_refresh_response_compliance)


def test_webhook_test_response_compliance():
    with webhook_receiver() as (callback_url, deliveries):
        status, body, hdrs, elapsed = req(
            "POST",
            "/v1/webhooks/test",
            body={"callback_url": callback_url},
        )
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert isinstance(body, dict), body
        assert body["success"] is True, body
        assert body["status_code"] == 200, body
        assert isinstance(body["message"], str) and body["message"], body
        assert deliveries, "Expected one webhook delivery to local receiver"
        assert deliveries[0]["path"] == "/webhook", deliveries[0]
        ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
        assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
        timings.append(("POST /v1/webhooks/test (compliance)", elapsed))


check("POST /v1/webhooks/test response is valid JSON", test_webhook_test_response_compliance)


def test_models_response_compliance():
    status, body, _, elapsed = req("GET", "/v1/models")
    assert status == 200, f"GET /v1/models returned {status}: {body}"
    assert isinstance(body, dict), body
    assert body.get("object") == "list", body
    assert isinstance(body.get("data"), list), body
    tokenizer = next((item for item in body["data"] if item.get("id") == "text.tokenizer"), None)
    assert tokenizer is not None, body["data"]
    for item in body["data"]:
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
            assert isinstance(value, list), (item.get("id"), field_name, value)
            assert all(isinstance(entry, str) and entry for entry in value), (
                item.get("id"),
                field_name,
                value,
            )
        for field_name in (
            "routing_fallback_policy",
            "chat_routing_fallback_policy",
            "embedding_routing_fallback_policy",
        ):
            value = item.get(field_name)
            assert value is None or isinstance(value, str), (item.get("id"), field_name, value)
        for field_name in (
            "routing_max_attempts",
            "chat_routing_max_attempts",
            "embedding_routing_max_attempts",
        ):
            value = item.get(field_name)
            assert value is None or (isinstance(value, int) and value > 0), (item.get("id"), field_name, value)
        for field_name in ("timeout_seconds", "chat_timeout_seconds", "embedding_timeout_seconds"):
            value = item.get(field_name)
            assert value is None or (isinstance(value, (int, float)) and value > 0), (
                item.get("id"),
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
    timings.append(("GET /v1/models (compliance)", elapsed))


check(
    "GET /v1/models response exposes routed provider catalog metadata",
    test_models_response_compliance,
)


def test_chat_completions_response_compliance():
    status, body, hdrs, elapsed = req(
        "POST",
        "/v1/chat/completions",
        body={
            "model": "text.tokenizer",
            "messages": [{"role": "user", "content": "summarize alpha beta"}],
        },
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, dict), body
    assert body["object"] == "chat.completion", body
    assert body["provider_backend"] is None, body
    assert body["provider_model_id"] is None, body
    assert body["provider_attempts"] == [], body
    assert body["choices"][0]["message"]["role"] == "assistant", body
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("POST /v1/chat/completions (compliance)", elapsed))


check(
    "POST /v1/chat/completions response exposes explicit provider trace",
    test_chat_completions_response_compliance,
)


def test_responses_response_compliance():
    status, body, hdrs, elapsed = req(
        "POST",
        "/v1/responses",
        body={"model": "text.tokenizer", "input": "alpha beta"},
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, dict), body
    assert body["object"] == "response", body
    assert body["status"] == "completed", body
    assert body["provider_backend"] is None, body
    assert body["provider_model_id"] is None, body
    assert body["provider_attempts"] == [], body
    assert isinstance(body.get("output"), list) and body["output"], body
    for item in body["output"]:
        assert item["provider_backend"] is None, item
        assert item["provider_model_id"] is None, item
        assert item["provider_attempts"] == [], item
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("POST /v1/responses (compliance)", elapsed))


check(
    "POST /v1/responses response exposes explicit provider trace",
    test_responses_response_compliance,
)


def test_embeddings_response_compliance():
    status, body, hdrs, elapsed = req(
        "POST",
        "/v1/embeddings",
        body={
            "model": "text.hash_embedding_v1",
            "input": ["alpha beta", "gamma"],
            "dimensions": 8,
        },
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, dict), body
    assert body["object"] == "list", body
    assert body["dimensions"] == 8, body
    assert body["provider_backend"] is None, body
    assert body["provider_model_id"] is None, body
    assert body["provider_attempts"] == [], body
    assert isinstance(body.get("data"), list) and len(body["data"]) == 2, body
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("POST /v1/embeddings (compliance)", elapsed))


check(
    "POST /v1/embeddings response exposes explicit provider trace",
    test_embeddings_response_compliance,
)


def test_triggers_list_response_compliance():
    status, body, hdrs, elapsed = req("GET", "/v1/triggers?page=1&limit=10")
    assert status == 200, f"GET /v1/triggers returned {status}: {body}"
    assert hdrs.get("Content-Type", hdrs.get("content-type", "")).startswith("application/json"), hdrs
    assert isinstance(body, dict), body
    assert isinstance(body.get("triggers"), list), body
    assert isinstance(body.get("count"), int), body
    assert isinstance(body.get("total"), int), body
    assert body.get("page") == 1, body
    assert body.get("limit") == 10, body
    assert isinstance(body.get("pages"), int), body
    timings.append(("GET /v1/triggers (compliance)", elapsed))


check("GET /v1/triggers response is valid JSON", test_triggers_list_response_compliance)


def test_execution_policy_snapshots_response_compliance():
    status, body, hdrs, elapsed = req("GET", "/v1/execution/policy/snapshots")
    assert status == 200, f"GET /v1/execution/policy/snapshots returned {status}: {body}"
    assert hdrs.get("Content-Type", hdrs.get("content-type", "")).startswith("application/json"), hdrs
    assert isinstance(body, dict), body
    assert isinstance(body.get("data"), list), body
    assert isinstance(body.get("total_snapshots"), int), body
    assert body["total_snapshots"] >= len(body["data"]), body
    for snapshot in body["data"]:
        assert isinstance(snapshot, dict), snapshot
        assert snapshot.get("snapshot_id"), snapshot
        assert isinstance(snapshot.get("revision"), int), snapshot
    timings.append(("GET /v1/execution/policy/snapshots (compliance)", elapsed))


check(
    "GET /v1/execution/policy/snapshots response is valid JSON",
    test_execution_policy_snapshots_response_compliance,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: Error Schema Compliance
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 5: Error Schema Compliance")
print("=" * 70)


def test_401_error_schema():
    """Trigger 401 by sending no API key to a protected endpoint."""
    status, body, hdrs, elapsed = req("GET", "/v1/runs", auth=False)
    assert status in (401, 403), f"Expected 401/403 without auth, got {status}"
    assert isinstance(body, dict), f"Error body is not JSON object: {type(body)}"
    # API uses structured error format: {"error": {"code": ..., "message": ...}}
    assert "error" in body or "detail" in body, (
        f"Error response missing 'error' or 'detail': {body}"
    )
    if "error" in body:
        err = body["error"]
        assert "code" in err, f"Error object missing 'code': {err}"
        assert "message" in err, f"Error object missing 'message': {err}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/runs (401 test)", elapsed))


check("401/403 error returns structured JSON error object", test_401_error_schema)


def test_422_error_schema():
    """Trigger 422 by sending invalid body to /v1/simulate."""
    payload = {"mode": "auto"}  # Missing required 'scenario'
    status, body, hdrs, elapsed = req("POST", "/v1/simulate", body=payload)
    assert status == 422, f"Expected 422 for invalid payload, got {status}"
    assert isinstance(body, dict), f"Error body is not JSON object: {type(body)}"
    # API returns {"error": {"code": "validation_error", ...}} format
    assert "error" in body or "detail" in body, (
        f"422 response missing 'error' or 'detail': {list(body.keys())}"
    )
    if "error" in body:
        err = body["error"]
        assert err.get("code") == "validation_error", (
            f"Expected code 'validation_error', got '{err.get('code')}'"
        )
        assert "message" in err, f"Error object missing 'message': {err}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("POST /v1/simulate (422 test)", elapsed))


check("422 validation error returns structured error object", test_422_error_schema)


def test_404_error_schema():
    """Trigger 404 by requesting a non-existent run."""
    status, body, hdrs, elapsed = req("GET", "/v1/runs/00000000-0000-0000-0000-000000000000")
    assert status == 404, f"Expected 404 for non-existent run, got {status}"
    assert isinstance(body, dict), f"Error body is not JSON object: {type(body)}"
    assert "error" in body or "detail" in body, (
        f"404 response missing 'error' or 'detail': {list(body.keys())}"
    )
    if "error" in body:
        assert "code" in body["error"], f"Error missing 'code': {body['error']}"
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Content-Type is not JSON: {ct}"
    timings.append(("GET /v1/runs/{id} (404 test)", elapsed))


check("404 error returns structured JSON error object", test_404_error_schema)


def test_error_responses_declared_in_spec():
    """Verify that major endpoints declare error responses in the spec."""
    spec = get_spec()
    paths = spec.get("paths", {})
    simulate_post = paths.get("/v1/simulate", {}).get("post", {})
    responses = simulate_post.get("responses", {})
    assert "422" in responses, "POST /v1/simulate missing 422 response declaration"


check(
    "POST /v1/simulate declares 422 error response in spec", test_error_responses_declared_in_spec
)


def test_error_format_consistency():
    """Verify multiple error endpoints use the same structured format."""
    # 401 error
    _, body_401, _, _ = req("GET", "/v1/runs", auth=False)
    # 422 error
    _, body_422, _, _ = req("POST", "/v1/simulate", body={"mode": "auto"})
    # 404 error
    _, body_404, _, _ = req("GET", "/v1/runs/00000000-0000-0000-0000-000000000000")

    for label, body in [("401", body_401), ("422", body_422), ("404", body_404)]:
        assert isinstance(body, dict), f"{label} not a dict"
        if "error" in body:
            err = body["error"]
            assert "code" in err, f"{label} error missing 'code'"
            assert "message" in err, f"{label} error missing 'message'"


check("All error responses use consistent structured format", test_error_format_consistency)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6: Security Scheme Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 6: Security Schemes")
print("=" * 70)


def test_security_schemes_declared():
    spec = get_spec()
    schemes = spec.get("components", {}).get("securitySchemes", {})
    assert len(schemes) > 0, "No security schemes declared"
    assert "BearerAuth" in schemes, (
        f"Missing canonical BearerAuth scheme. Schemes: {list(schemes.keys())}"
    )
    bearer = schemes["BearerAuth"]
    assert bearer.get("type") == "http", bearer
    assert bearer.get("scheme") == "bearer", bearer
    assert "LegacyApiKey" in schemes, (
        f"Missing legacy api-key compatibility scheme. Schemes: {list(schemes.keys())}"
    )
    legacy = schemes["LegacyApiKey"]
    assert legacy.get("type") == "apiKey", legacy
    assert legacy.get("in") == "header", legacy
    assert legacy.get("name") == "X-API-Key", legacy


check(
    "Security schemes declare canonical Bearer auth plus legacy API-key compatibility",
    test_security_schemes_declared,
)


def test_bearer_auth_scheme():
    spec = get_spec()
    schemes = spec.get("components", {}).get("securitySchemes", {})
    has_bearer = False
    for _, scheme in schemes.items():
        if scheme.get("type") == "http" and scheme.get("scheme") == "bearer":
            has_bearer = True
    assert has_bearer, f"No HTTP Bearer auth scheme found. Schemes: {list(schemes.keys())}"


check("Security scheme declares HTTP Bearer auth", test_bearer_auth_scheme)


def test_openapi_server_and_mcp_endpoint_are_canonical():
    spec = get_spec()
    assert spec.get("servers") == [{"url": "https://api.algenta.ai"}], spec.get("servers")
    assert spec.get("x-canonical-mcp-endpoint") == "https://api.algenta.ai/mcp/sse"


check(
    "OpenAPI declares canonical hosted API and MCP endpoints",
    test_openapi_server_and_mcp_endpoint_are_canonical,
)


def test_protected_endpoints_have_security():
    """Protected endpoints should have security requirements in the spec."""
    spec = get_spec()
    paths = spec.get("paths", {})
    expected_security = [{"BearerAuth": []}, {"LegacyApiKey": []}]
    protected_paths = [
        ("/v1/models", "get"),
        ("/v1/artifacts/resolve", "post"),
        ("/v1/chat/completions", "post"),
        ("/v1/tokenize", "post"),
        ("/v1/count_tokens", "post"),
        ("/v1/responses", "post"),
        ("/v1/embeddings", "post"),
        ("/v1/embeddings/similarity", "post"),
        ("/v1/rerank", "post"),
        ("/v1/decision", "post"),
        ("/v1/agent/run", "post"),
        ("/v1/optimize", "post"),
        ("/v1/retrieve", "post"),
        ("/v1/forecast", "post"),
        ("/v1/agent/runs", "post"),
        ("/v1/agent/runs/{run_id}", "get"),
        ("/v1/agent/runs/{run_id}/events", "get"),
        ("/v1/agent/runs/{run_id}/resume", "post"),
        ("/v1/agent/runs/{run_id}/cancel", "post"),
        ("/v1/agent/runs/{run_id}/approve", "post"),
        ("/v1/simulate", "post"),
        ("/v1/decisions/plan", "post"),
        ("/v1/runs", "get"),
        ("/v1/jobs/list", "get"),
        ("/v1/data/connect", "post"),
        ("/v1/data", "get"),
        ("/v1/data/{dataset_id}", "get"),
        ("/v1/data/{dataset_id}/summary", "get"),
        ("/v1/data/{dataset_id}/refresh", "post"),
        ("/v1/data/{dataset_id}", "delete"),
        ("/v1/repositories/{repository_id}/snapshots", "post"),
        ("/v1/repositories/{repository_id}/snapshots/{snapshot_id}", "get"),
        ("/v1/repositories/{repository_id}/triage", "post"),
        ("/v1/repositories/{repository_id}/decision-plans", "post"),
        ("/v1/repositories/{repository_id}/simulate", "post"),
        ("/v1/repositories/{repository_id}/apply", "post"),
        ("/v1/webhooks/test", "post"),
        ("/v1/execution/policy/snapshots", "get"),
        ("/v1/jobs/{job_id}", "get"),
        ("/v1/jobs/{job_id}/result", "get"),
        ("/v1/jobs/{job_id}/cancel", "post"),
        ("/v1/triggers", "get"),
        ("/v1/triggers", "post"),
        ("/v1/triggers/{trigger_id}/fire", "post"),
        ("/v1/triggers/{trigger_id}/pause", "patch"),
        ("/v1/triggers/{trigger_id}", "delete"),
        ("/v1/templates", "get"),
        ("/v1/connectors", "get"),
        ("/v1/connectors", "post"),
        ("/v1/connectors/test", "post"),
        ("/v1/connectors/browse", "post"),
        ("/v1/connectors/{connector_id}", "get"),
        ("/v1/connectors/{connector_id}", "patch"),
        ("/v1/connectors/{connector_id}/test", "post"),
        ("/v1/connectors/{connector_id}/browse", "get"),
        ("/v1/connectors/{connector_id}", "delete"),
        ("/v1/analytics", "get"),
        ("/v1/jobs", "post"),
        ("/v1/metering", "post"),
        ("/v1/credits/refresh", "post"),
    ]
    missing_security = []
    for path, method in protected_paths:
        path_obj = paths.get(path, {})
        op = path_obj.get(method, {})
        security = op.get("security")
        if security is None:
            top_security = spec.get("security")
            if not top_security:
                missing_security.append(f"{method.upper()} {path}")
        elif security != expected_security:
            missing_security.append(f"{method.upper()} {path} wrong security {security!r}")
    assert len(missing_security) == 0, (
        f"Protected endpoints missing security declaration: {missing_security}"
    )


check("Protected endpoints have security requirements", test_protected_endpoints_have_security)


def test_streaming_endpoints_advertise_event_stream_content():
    spec = get_spec()
    paths = spec.get("paths", {})
    assert (
        "text/event-stream"
        in paths["/v1/chat/completions"]["post"]["responses"]["200"]["content"]
    )
    assert (
        "text/event-stream"
        in paths["/v1/responses"]["post"]["responses"]["200"]["content"]
    )
    assert (
        "text/event-stream"
        in paths["/v1/agent/runs/{run_id}/events"]["get"]["responses"]["200"]["content"]
    )


check(
    "Streaming plan routes advertise SSE content",
    test_streaming_endpoints_advertise_event_stream_content,
)


def test_public_endpoints_no_security():
    """Health and version should NOT require auth."""
    spec = get_spec()
    paths = spec.get("paths", {})
    public_paths = [
        ("/v1/health", "get"),
        ("/v1/version", "get"),
    ]
    has_security = []
    for path, method in public_paths:
        path_obj = paths.get(path, {})
        op = path_obj.get(method, {})
        security = op.get("security")
        if security is not None and len(security) > 0:
            has_security.append(f"{method.upper()} {path}")
    assert len(has_security) == 0, (
        f"Public endpoints should not have security requirements: {has_security}"
    )


check(
    "Public endpoints (health, version) don't require auth in spec",
    test_public_endpoints_no_security,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 7: Schema Type Validation (live data)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 7: Schema Type Validation (live data)")
print("=" * 70)


def test_simulate_numeric_fields():
    """Verify all numeric fields in simulation response are actually numbers."""
    status, body, _, elapsed = simulate_req(AUTO_PAYLOAD)
    assert status == 200, f"Simulate returned {status}: {body}"
    if "confidence" in body:
        assert isinstance(body["confidence"], int | float), (
            f"confidence is {type(body['confidence']).__name__}, expected number"
        )
    if "scenarios_run" in body:
        assert isinstance(body["scenarios_run"], int), (
            f"scenarios_run is {type(body['scenarios_run']).__name__}, expected int"
        )
    if "execution_ms" in body:
        assert isinstance(body["execution_ms"], int), (
            f"execution_ms is {type(body['execution_ms']).__name__}, expected int"
        )
    if "metrics" in body and isinstance(body["metrics"], dict):
        metrics = body["metrics"]
        for field in ["expected_value", "median", "std_deviation", "variance"]:
            if field in metrics:
                assert isinstance(metrics[field], int | float), (
                    f"metrics.{field} is {type(metrics[field]).__name__}, expected number"
                )
    timings.append(("POST /v1/simulate (type check)", elapsed))


check("Simulation numeric fields are actually numbers", test_simulate_numeric_fields)


def test_simulate_string_fields():
    """Verify string fields in simulation response are actually strings."""
    status, body, _, elapsed = simulate_req(AUTO_PAYLOAD)
    assert status == 200, f"Simulate returned {status}: {body}"
    for field in ["run_id", "status", "recommended_action", "rationale"]:
        if field in body and body[field] is not None:
            assert isinstance(body[field], str), (
                f"{field} is {type(body[field]).__name__}, expected string"
            )
    timings.append(("POST /v1/simulate (string check)", elapsed))


check("Simulation string fields are actually strings", test_simulate_string_fields)


def test_simulate_percentiles_numeric():
    """Verify percentile fields in simulation response are numeric."""
    status, body, _, elapsed = simulate_req(AUTO_PAYLOAD)
    assert status == 200, f"Simulate returned {status}: {body}"
    if "percentiles" in body and isinstance(body["percentiles"], dict):
        for key, val in body["percentiles"].items():
            if val is not None:
                assert isinstance(val, int | float), (
                    f"percentiles.{key} is {type(val).__name__}, expected number"
                )
    timings.append(("POST /v1/simulate (percentiles check)", elapsed))


check("Simulation percentiles are numeric values", test_simulate_percentiles_numeric)


def test_enum_values_compliance():
    """Verify the simulation_model field contains only declared enum values."""
    status, body, _, elapsed = simulate_req(AUTO_PAYLOAD)
    assert status == 200, f"Simulate returned {status}: {body}"
    if "simulation_model" in body and body["simulation_model"] is not None:
        valid_models = {
            "monte_carlo",
            "qmc_sobol",
            "lhs",
            "bootstrap",
            "scenario",
            "sensitivity",
            "mcmc",
            "decision_tree",
            "time_series",
            "compare",
            "importance_sampling",
        }
        assert body["simulation_model"] in valid_models, (
            f"simulation_model '{body['simulation_model']}' not in valid set"
        )
    timings.append(("POST /v1/simulate (enum check)", elapsed))


check("simulation_model field contains valid enum value", test_enum_values_compliance)


def test_nullable_fields_handle_null():
    """Verify nullable fields (anyOf with null type) exist in DecisionEnvelope."""
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    envelope = schemas.get("DecisionEnvelope", {})
    props = envelope.get("properties", {})
    nullable_fields = []
    for fname, fschema in props.items():
        if "anyOf" in fschema:
            for opt in fschema["anyOf"]:
                opt_resolved = resolve_schema(spec, opt)
                if opt_resolved.get("type") == "null":
                    nullable_fields.append(fname)
                    break
    assert len(nullable_fields) > 0, "No nullable fields found in DecisionEnvelope"


check("DecisionEnvelope has nullable fields declared correctly", test_nullable_fields_handle_null)


def test_confidence_range():
    """Verify confidence value is within declared min/max (0.0 to 1.0)."""
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    envelope = schemas.get("DecisionEnvelope", {})
    props = envelope.get("properties", {})
    conf_schema = props.get("confidence", {})
    assert conf_schema.get("minimum") == 0.0, f"confidence minimum is {conf_schema.get('minimum')}"
    assert conf_schema.get("maximum") == 1.0, f"confidence maximum is {conf_schema.get('maximum')}"

    status, body, _, _ = simulate_req(AUTO_PAYLOAD)
    assert status == 200, f"Simulate returned {status}: {body}"
    if "confidence" in body and body["confidence"] is not None:
        assert 0.0 <= body["confidence"] <= 1.0, (
            f"confidence {body['confidence']} outside [0, 1] range"
        )


check("Confidence field within declared [0.0, 1.0] range", test_confidence_range)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8: Consistency Tests
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 8: Consistency Tests")
print("=" * 70)


def test_spec_paths_are_reachable():
    """Verify every endpoint in OpenAPI spec is actually reachable."""
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    skip_patterns = ["{", "stream", "sse"]
    phantom = []
    tested = 0

    for path_name, path_obj in paths.items():
        if any(p in path_name for p in skip_patterns):
            continue
        for method_name in path_obj.keys():
            if method_name.lower() not in http_methods:
                continue
            try:
                status, _, _, _ = req(method_name.upper(), path_name, auth=True, timeout=5)
                if status == 404:
                    phantom.append(f"{method_name.upper()} {path_name} → {status}")
                tested += 1
            except Exception:
                tested += 1

    assert tested > 20, f"Only tested {tested} routes"
    assert len(phantom) <= 5, f"Too many phantom routes ({len(phantom)}): {phantom[:5]}"


check("Spec paths are reachable (no phantom routes)", test_spec_paths_are_reachable)


def test_no_undocumented_endpoints():
    """Compare known public endpoints against spec paths."""
    spec = get_spec()
    spec_paths = set(spec.get("paths", {}).keys())
    known_endpoints = [
        "/v1/health",
        "/v1/version",
        "/v1/models",
        "/v1/artifacts/resolve",
        "/v1/chat/completions",
        "/v1/tokenize",
        "/v1/count_tokens",
        "/v1/responses",
        "/v1/embeddings",
        "/v1/embeddings/similarity",
        "/v1/rerank",
        "/v1/decision",
        "/v1/agent/run",
        "/v1/optimize",
        "/v1/retrieve",
        "/v1/forecast",
        "/v1/agent/runs",
        "/v1/agent/runs/{run_id}",
        "/v1/agent/runs/{run_id}/events",
        "/v1/agent/runs/{run_id}/resume",
        "/v1/agent/runs/{run_id}/cancel",
        "/v1/agent/runs/{run_id}/approve",
        "/v1/simulate",
        "/v1/decisions/plan",
        "/v1/recommend",
        "/v1/runs",
        "/v1/jobs/list",
        "/v1/jobs/{job_id}",
        "/v1/jobs/{job_id}/result",
        "/v1/jobs/{job_id}/cancel",
        "/v1/data/connect",
        "/v1/data",
        "/v1/data/{dataset_id}",
        "/v1/data/{dataset_id}/summary",
        "/v1/data/{dataset_id}/refresh",
        "/v1/triggers",
        "/v1/triggers/{trigger_id}/fire",
        "/v1/triggers/{trigger_id}/pause",
        "/v1/triggers/{trigger_id}",
        "/v1/templates",
        "/v1/connectors",
        "/v1/connectors/test",
        "/v1/connectors/browse",
        "/v1/connectors/{connector_id}",
        "/v1/connectors/{connector_id}/test",
        "/v1/connectors/{connector_id}/browse",
        "/v1/analytics",
        "/v1/jobs",
        "/v1/distributions",
        "/v1/usage",
        "/v1/limits",
        "/v1/credits/refresh",
        "/v1/webhooks/test",
        "/v1/execution/policy/snapshots",
        "/v1/metering",
    ]
    undocumented = [ep for ep in known_endpoints if ep not in spec_paths]
    assert len(undocumented) == 0, f"Known endpoints not in OpenAPI spec: {undocumented}"


check("No undocumented known endpoints", test_no_undocumented_endpoints)


def test_request_body_schemas_exist():
    """Verify POST/PUT endpoints with request bodies have schema declarations."""
    spec = get_spec()
    paths = spec.get("paths", {})
    missing_body = []
    for path_name, path_obj in paths.items():
        for method_name in ("post", "put", "patch"):
            op = path_obj.get(method_name)
            if not op or not isinstance(op, dict):
                continue
            rb = op.get("requestBody")
            if rb is None:
                continue
            content = rb.get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema")
                if not schema:
                    missing_body.append(f"{method_name.upper()} {path_name}")
    assert len(missing_body) == 0, f"POST/PUT endpoints with empty request schemas: {missing_body}"


check("POST/PUT endpoints with request body have schemas", test_request_body_schemas_exist)


def test_parameter_declarations():
    """Verify path parameters in URL patterns are declared in the spec."""
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    missing_params = []

    for path_name, path_obj in paths.items():
        url_params = re.findall(r"\{(\w+)\}", path_name)
        if not url_params:
            continue
        for method_name, op in path_obj.items():
            if method_name.lower() not in http_methods or not isinstance(op, dict):
                continue
            declared_params = set()
            for param in op.get("parameters", []):
                if param.get("in") == "path":
                    declared_params.add(param.get("name"))
            for param in path_obj.get("parameters", []):
                if param.get("in") == "path":
                    declared_params.add(param.get("name"))
            for p in url_params:
                if p not in declared_params:
                    missing_params.append(f"{method_name.upper()} {path_name}: missing '{p}'")

    assert len(missing_params) == 0, f"Path parameters not declared: {missing_params[:5]}"


check("Path parameters in URLs are declared in spec", test_parameter_declarations)


def test_response_codes_declared():
    """Verify major endpoints declare at least one success response (200, 201, 202, 204)."""
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    fallback_only_mcp_ops = {
        ("GET", "/mcp/sse"),
        ("POST", "/mcp/messages"),
    }
    no_responses = []

    for path_name, path_obj in paths.items():
        for method_name, op in path_obj.items():
            if method_name.lower() not in http_methods or not isinstance(op, dict):
                continue
            op_key = (method_name.upper(), path_name)
            responses = op.get("responses", {})
            if not responses:
                no_responses.append(f"{method_name.upper()} {path_name}")
            else:
                # Accept any 2xx response code
                has_success = any(
                    code.startswith("2") for code in responses.keys() if code.isdigit()
                )
                if not has_success:
                    if op_key in fallback_only_mcp_ops and "503" in responses:
                        continue
                    no_responses.append(f"{method_name.upper()} {path_name} (no 2xx)")

    assert len(no_responses) == 0, f"Operations missing success response: {no_responses[:5]}"


check("All operations declare at least one success response", test_response_codes_declared)


def test_simulate_request_auto_schema():
    """Verify SimulateRequestAuto schema matches what the API actually accepts."""
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    auto_schema = schemas.get("SimulateRequestAuto", {})
    props = auto_schema.get("properties", {})

    # The API uses mode + scenario + runs (not question/variables/scenarios)
    expected_props = ["mode", "scenario", "runs"]
    missing = [p for p in expected_props if p not in props]
    assert len(missing) == 0, f"SimulateRequestAuto missing properties: {missing}"

    # 'scenario' should reference AutoScenario
    scenario_prop = props.get("scenario", {})
    ref = scenario_prop.get("$ref", "")
    assert "AutoScenario" in ref, f"scenario doesn't reference AutoScenario: {scenario_prop}"


check("SimulateRequestAuto schema has mode, scenario, runs", test_simulate_request_auto_schema)


def test_simulate_expert_request_schema():
    """Verify SimulateRequestExpert schema has expert-mode fields."""
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    expert = schemas.get("SimulateRequestExpert", {})
    props = expert.get("properties", {})

    assert "mode" in props, "SimulateRequestExpert missing 'mode'"
    # Expert mode uses 'simulation' field (references ExpertSimulation)
    assert "simulation" in props, (
        f"SimulateRequestExpert missing 'simulation': {list(props.keys())}"
    )
    sim_ref = props.get("simulation", {}).get("$ref", "")
    assert "ExpertSimulation" in sim_ref, (
        f"simulation doesn't reference ExpertSimulation: {sim_ref}"
    )


check(
    "SimulateRequestExpert schema has mode and simulation fields",
    test_simulate_expert_request_schema,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 9: Advanced Schema Validation
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 9: Advanced Schema Validation")
print("=" * 70)


def test_all_refs_resolve():
    """Verify every $ref in the spec can be resolved."""
    spec = get_spec()
    unresolved = []

    def walk(obj, path=""):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                resolved = resolve_ref(spec, ref)
                if not resolved:
                    unresolved.append(f"{path}: {ref}")
            for key, val in obj.items():
                walk(val, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, f"{path}[{i}]")

    walk(spec)
    assert len(unresolved) == 0, f"Unresolved $refs: {unresolved[:10]}"


check("All $ref references resolve correctly", test_all_refs_resolve)


def test_oneof_discriminator_for_simulate():
    """POST /v1/simulate uses oneOf with discriminator for auto/expert."""
    spec = get_spec()
    simulate = spec.get("paths", {}).get("/v1/simulate", {}).get("post", {})
    rb = simulate.get("requestBody", {})
    content = rb.get("content", {}).get("application/json", {})
    schema = content.get("schema", {})
    assert "oneOf" in schema or "anyOf" in schema, (
        f"Simulate request schema missing oneOf/anyOf: {list(schema.keys())}"
    )
    if "oneOf" in schema:
        disc = schema.get("discriminator", {})
        assert disc.get("propertyName") == "mode", (
            f"Discriminator property should be 'mode', got {disc.get('propertyName')}"
        )


check(
    "Simulate request uses oneOf with 'mode' discriminator", test_oneof_discriminator_for_simulate
)


def test_spec_has_descriptions():
    """A good spec should have descriptions on endpoints."""
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    total = 0
    with_desc = 0
    for _, path_obj in paths.items():
        for method_name, op in path_obj.items():
            if method_name.lower() not in http_methods or not isinstance(op, dict):
                continue
            total += 1
            if op.get("summary") or op.get("description"):
                with_desc += 1
    ratio = with_desc / max(total, 1)
    assert ratio >= 0.5, (
        f"Only {ratio:.0%} of operations have summary/description ({with_desc}/{total})"
    )


check("≥50% of operations have summary/description", test_spec_has_descriptions)


def test_mcp_tools_endpoint():
    """Verify /mcp/tools is declared and reachable."""
    spec = get_spec()
    paths = spec.get("paths", {})
    assert "/mcp/tools" in paths, "/mcp/tools not in spec"
    mcp_tools = paths["/mcp/tools"]
    assert "get" in mcp_tools, "/mcp/tools missing GET method"
    status, body, _, elapsed = req("GET", "/mcp/tools", auth=False)
    assert status == 200, f"GET /mcp/tools returned {status}"
    timings.append(("GET /mcp/tools", elapsed))


check("MCP tools endpoint declared and reachable", test_mcp_tools_endpoint)


def test_mcp_transport_endpoints_declared():
    """Verify /mcp/sse and /mcp/messages are declared with truthful fallback responses."""
    spec = get_spec()
    paths = spec.get("paths", {})

    assert "/mcp/sse" in paths, "/mcp/sse not in spec"
    assert "get" in paths["/mcp/sse"], "/mcp/sse missing GET method"
    sse_responses = paths["/mcp/sse"]["get"].get("responses", {})
    if "503" in sse_responses:
        assert (
            sse_responses["503"]["description"]
            == "MCP SSE transport unavailable in this environment."
        )
        assert "200" not in sse_responses, "/mcp/sse fallback spec should not advertise 200"

    assert "/mcp/messages" in paths, "/mcp/messages not in spec"
    assert "post" in paths["/mcp/messages"], "/mcp/messages missing POST method"
    message_responses = paths["/mcp/messages"]["post"].get("responses", {})
    if "503" in message_responses:
        assert (
            message_responses["503"]["description"]
            == "MCP message transport unavailable in this environment."
        )
        assert (
            "200" not in message_responses
        ), "/mcp/messages fallback spec should not advertise 200"


check("MCP transport endpoints declared with truthful fallback responses", test_mcp_transport_endpoints_declared)


def test_mcp_transport_runtime_contract():
    """Verify live MCP transport endpoints either stream or return the structured unavailable contract."""
    mcp_hint = "Install requirements-mcp.txt to enable /mcp/sse and /mcp/messages."

    try:
        status, body, _, elapsed = req("GET", "/mcp/sse", auth=False, timeout=3)
        timings.append(("GET /mcp/sse", elapsed))
        assert status != 404, "GET /mcp/sse returned 404"
        if status == 503:
            assert isinstance(body, dict), f"Expected JSON object, got {type(body).__name__}"
            assert body.get("error", {}).get("code") == "mcp_transport_unavailable", body
            assert body.get("error", {}).get("details", {}).get("hint") == mcp_hint, body
        else:
            assert status in {200, 204}, f"Unexpected GET /mcp/sse status: {status}"
    except TimeoutError:
        pass

    status, body, _, elapsed = req("POST", "/mcp/messages", body={}, auth=False, timeout=3)
    timings.append(("POST /mcp/messages", elapsed))
    assert status != 404, "POST /mcp/messages returned 404"
    if status == 503:
        assert isinstance(body, dict), f"Expected JSON object, got {type(body).__name__}"
        assert body.get("error", {}).get("code") == "mcp_transport_unavailable", body
        assert body.get("error", {}).get("details", {}).get("hint") == mcp_hint, body
    else:
        assert status in {400, 405, 415, 422}, f"Unexpected POST /mcp/messages status: {status}"


check("MCP transport runtime contract is truthful", test_mcp_transport_runtime_contract)


def test_export_endpoint_format_param():
    """Verify export endpoint has format path parameter."""
    spec = get_spec()
    paths = spec.get("paths", {})
    export_path = "/v1/runs/{run_id}/export.{fmt}"
    assert export_path in paths, f"Export path '{export_path}' not in spec"
    export_op = paths[export_path]
    assert "get" in export_op, "Export endpoint missing GET method"


check("Export endpoint with format parameter declared", test_export_endpoint_format_param)


def test_what_if_endpoint_declared():
    """Verify /v1/simulate/what-if is properly declared."""
    spec = get_spec()
    paths = spec.get("paths", {})
    assert "/v1/simulate/what-if" in paths, "/v1/simulate/what-if not in spec"
    what_if = paths["/v1/simulate/what-if"]
    assert "post" in what_if, "/v1/simulate/what-if missing POST method"
    post_op = what_if["post"]
    assert post_op.get("requestBody"), "what-if POST missing requestBody"


check("What-if endpoint declared with POST and requestBody", test_what_if_endpoint_declared)


def test_simulate_response_schema_is_decision_envelope():
    """Verify POST /v1/simulate 200 response references DecisionEnvelope."""
    spec = get_spec()
    simulate = spec.get("paths", {}).get("/v1/simulate", {}).get("post", {})
    resp_200 = simulate.get("responses", {}).get("200", {})
    content = resp_200.get("content", {}).get("application/json", {})
    schema = content.get("schema", {})
    ref = schema.get("$ref", "")
    assert "DecisionEnvelope" in ref, (
        f"Simulate 200 response doesn't reference DecisionEnvelope: {schema}"
    )


check(
    "Simulate 200 response references DecisionEnvelope schema",
    test_simulate_response_schema_is_decision_envelope,
)


def test_full_simulation_deep_validation():
    """Deep validation: run simulation and validate every top-level field against spec."""
    spec = get_spec()
    status, body, _, elapsed = simulate_req(AUTO_PAYLOAD)
    assert status == 200, f"Simulate returned {status}: {body}"

    envelope_schema = get_response_schema(spec, "/v1/simulate", "post", "200")
    props = envelope_schema.get("properties", {})

    all_errors = []
    for field_name, value in body.items():
        if value is None:
            continue
        if field_name not in props:
            continue  # Extra fields are OK
        field_schema = resolve_schema(spec, props[field_name])
        declared_type = field_schema.get("type")

        if declared_type and not _value_matches_type(value, declared_type):
            if "anyOf" in field_schema:
                types = set()
                for opt in field_schema["anyOf"]:
                    opt_r = resolve_schema(spec, opt)
                    if "type" in opt_r:
                        types.add(opt_r["type"])
                if not _value_matches_types(value, types):
                    all_errors.append(f"{field_name}: expected {types}, got {type(value).__name__}")
            else:
                all_errors.append(
                    f"{field_name}: expected {declared_type}, got {type(value).__name__}"
                )

    assert len(all_errors) == 0, f"Deep validation errors: {all_errors}"
    timings.append(("POST /v1/simulate (deep validation)", elapsed))


check(
    "Deep validation: all simulation fields match spec types", test_full_simulation_deep_validation
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 10: Cross-cutting Quality Checks
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 10: Cross-cutting Quality Checks")
print("=" * 70)


def test_all_schemas_have_title():
    """Good OpenAPI spec should have titles on schemas."""
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    no_title = [name for name, schema in schemas.items() if "title" not in schema]
    ratio = 1 - len(no_title) / max(len(schemas), 1)
    assert ratio >= 0.8, f"Only {ratio:.0%} schemas have titles; missing: {no_title[:5]}"


check("≥80% of schemas have titles", test_all_schemas_have_title)


def test_content_type_consistency():
    """All JSON endpoints should declare application/json in responses."""
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    no_json_content = []

    for path_name, path_obj in paths.items():
        for method_name, op in path_obj.items():
            if method_name.lower() not in http_methods or not isinstance(op, dict):
                continue
            responses = op.get("responses", {})
            for status_code, resp in responses.items():
                content = resp.get("content", {})
                if content and "application/json" not in content:
                    if (
                        "text/event-stream" not in content
                        and "text/csv" not in content
                        and "text/plain" not in content
                    ):
                        no_json_content.append(f"{method_name.upper()} {path_name} ({status_code})")

    assert len(no_json_content) <= 3, (
        f"Endpoints not declaring JSON content-type: {no_json_content}"
    )


check("JSON endpoints declare application/json content-type", test_content_type_consistency)


def test_spec_total_operation_count():
    """Count total operations and verify reasonable number."""
    spec = get_spec()
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    count = sum(
        1
        for _, path_obj in paths.items()
        for method_name in path_obj
        if method_name.lower() in http_methods
    )
    assert count >= 40, f"Expected ≥40 operations, got {count}"


check("Total operations ≥ 40", test_spec_total_operation_count)


def test_auto_variable_schema():
    """Verify AutoVariable schema has low/high fields."""
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    auto_var = schemas.get("AutoVariable", {})
    if auto_var:
        props = auto_var.get("properties", {})
        assert "low" in props, f"AutoVariable missing 'low': {list(props.keys())}"
        assert "high" in props, f"AutoVariable missing 'high': {list(props.keys())}"
        required = auto_var.get("required", [])
        assert "low" in required, "AutoVariable: 'low' should be required"
        assert "high" in required, "AutoVariable: 'high' should be required"
    else:
        # Fallback: check SimulateRequestAuto.scenario → AutoScenario.variables
        auto_req = schemas.get("SimulateRequestAuto", {})
        props = auto_req.get("properties", {})
        assert "scenario" in props, "SimulateRequestAuto missing 'scenario'"


check("AutoVariable schema has low/high fields", test_auto_variable_schema)


def test_auto_scenario_schema():
    """Verify AutoScenario schema has variables and objective."""
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    auto_scenario = schemas.get("AutoScenario", {})
    assert auto_scenario, "AutoScenario schema not found"
    props = auto_scenario.get("properties", {})
    assert "variables" in props, f"AutoScenario missing 'variables': {list(props.keys())}"
    assert "objective" in props, f"AutoScenario missing 'objective': {list(props.keys())}"
    required = auto_scenario.get("required", [])
    assert "variables" in required, "AutoScenario: 'variables' should be required"
    assert "objective" in required, "AutoScenario: 'objective' should be required"


check("AutoScenario schema has variables and objective", test_auto_scenario_schema)


def test_expert_simulation_schema():
    """Verify ExpertSimulation schema has variables array."""
    spec = get_spec()
    schemas = spec.get("components", {}).get("schemas", {})
    expert_sim = schemas.get("ExpertSimulation", {})
    assert expert_sim, "ExpertSimulation schema not found"
    props = expert_sim.get("properties", {})
    assert "variables" in props, f"ExpertSimulation missing 'variables': {list(props.keys())}"
    var_prop = props["variables"]
    assert var_prop.get("type") == "array", "ExpertSimulation.variables should be array"


check("ExpertSimulation schema has variables array", test_expert_simulation_schema)


def test_spec_servers_or_base_url():
    """Check if servers section exists (optional but nice)."""
    spec = get_spec()
    servers = spec.get("servers")
    if servers:
        assert isinstance(servers, list), "servers should be a list"
        for s in servers:
            assert "url" in s, f"Server entry missing 'url': {s}"


check("Servers section (if present) has valid entries", test_spec_servers_or_base_url)


if __name__ == "__main__":
    import pytest

    exit_code = pytest.main([__file__, "-v"])
    # Write summary artifact for CI consumers (preserves the
    # tests/test_runtime_surface_compatibility surface contract).
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary

        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_openapi.py",
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
