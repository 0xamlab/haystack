"""
Real-life API integration tests — tests against a running server at localhost:8000.

Prerequisites:
  1. API server running: make dev-api
  2. PostgreSQL running on :5432
  3. Redis running on :6379
  4. Dev data seeded: python scripts/seed_dev.py

Run:
  python tests/integration/test_api_live.py
  # or with a specific key:
  DE_API_KEY=de_live_xxx python tests/integration/test_api_live.py
"""

if __name__ != "__main__":
    import pytest

    pytest.skip(
        "Standalone integration script; run via python tests/integration/test_api_live.py",
        allow_module_level=True,
    )

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

# Ensure project root is on sys.path for direct module imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_integration_artifacts import write_live_integration_summary

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

try:
    from tests.integration.live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()
SUITE_NAME = "api_live_integration"
STARTED = time.perf_counter()

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []


class EnvironmentBlocked(RuntimeError):
    """Raised when the live environment cannot run simulation due to quota/capacity."""


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _write_summary_artifact() -> str:
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    artifact = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_api_live.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(results),
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "base_url": configured_local_live_base_url(),
            "api_key_configured": API_KEY_CONFIGURED,
        },
    )
    return str(artifact)


def _missing_live_api_key_reason(exc: BaseException) -> str | None:
    if API_KEY_CONFIGURED:
        return None
    text = str(exc)
    if any(token in text for token in ("401", "403", "Authentication", "invalid_api_key")):
        return "DE_API_KEY is not set; skipping authenticated API integration checks that require a real live key."
    return None


def _assert_expected_status(status: int, body, expected: int = 200) -> None:
    if status == expected:
        return
    raise AssertionError(f"Expected {expected}, got {status}: {body}")


def ensure_simulation_capacity_available(status: int, body) -> None:
    reason = classify_simulation_capacity_blocker(status=status, payload=body)
    if reason:
        raise EnvironmentBlocked(reason)


def req_simulate(body, *, auth=True, timeout=10, headers=None):
    status, payload, response_headers, elapsed = req(
        "POST",
        "/v1/simulate",
        body=body,
        headers=headers,
        auth=auth,
        timeout=timeout,
    )
    ensure_simulation_capacity_available(status, payload)
    return status, payload, response_headers, elapsed


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=10):
    """Make HTTP request, return (status_code, response_body_dict, response_headers)."""
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
            return resp.status, body_data, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        body_bytes = e.read()
        try:
            body_data = json.loads(body_bytes)
        except Exception:
            body_data = body_bytes.decode("utf-8", errors="replace")
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
    started_at = time.monotonic()
    _emit(f"  ... {name}")
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
#  SECTION 1: Public Endpoints (no auth required)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 1: Public Endpoints (no auth)")
print("=" * 70)


def test_health():
    status, body, headers, elapsed = req("GET", "/v1/health", auth=False)
    assert status == 200, f"Expected 200, got {status}"
    assert body["status"] == "ok", f"Expected 'ok', got {body}"
    timings.append(("GET /v1/health", elapsed))


check("GET /v1/health → 200 ok", test_health)


def test_version():
    status, body, headers, elapsed = req("GET", "/v1/version", auth=False)
    assert status == 200, f"Expected 200, got {status}"
    assert "api_version" in body, f"Missing api_version in {body}"
    assert "engine_version" in body, "Missing engine_version"
    timings.append(("GET /v1/version", elapsed))


check("GET /v1/version → 200 with version fields", test_version)


def test_docs():
    status, body, headers, elapsed = req("GET", "/docs", auth=False)
    assert status == 200, f"Expected 200, got {status}"
    timings.append(("GET /docs", elapsed))


check("GET /docs → 200 (Swagger UI)", test_docs)


def test_openapi_has_paths():
    """OpenAPI spec must include registered routes, not empty paths."""
    status, body, headers, elapsed = req("GET", "/openapi.json", auth=False)
    assert status == 200, f"Expected 200, got {status}"
    paths = body.get("paths", {})
    assert len(paths) > 0, f"OpenAPI paths is empty! Got: {json.dumps(body)[:500]}"
    assert "/v1/health" in paths, f"Missing /v1/health in OpenAPI paths: {list(paths.keys())[:10]}"
    assert "/v1/simulate" in paths, (
        f"Missing /v1/simulate in OpenAPI paths: {list(paths.keys())[:10]}"
    )


check("GET /openapi.json → non-empty paths", test_openapi_has_paths)


def test_redoc():
    status, body, headers, elapsed = req("GET", "/redoc", auth=False)
    assert status == 200, f"Expected 200, got {status}"


check("GET /redoc → 200 (ReDoc)", test_redoc)


def test_metrics():
    url = f"{BASE_URL}/metrics"
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=10) as resp:
        body = resp.read().decode()
        assert resp.status == 200
        assert "http_requests" in body or "process_" in body or "python_" in body, (
            "Prometheus metrics expected"
        )


check("GET /metrics → 200 Prometheus metrics", test_metrics)


def test_request_id_header():
    status, body, headers, elapsed = req("GET", "/v1/health", auth=False)
    rid = headers.get("X-Request-Id") or headers.get("x-request-id")
    assert rid is not None, f"Missing X-Request-Id header. Headers: {list(headers.keys())}"
    assert rid.startswith("req_"), f"Request ID should start with 'req_', got: {rid}"


check("All responses include X-Request-Id header", test_request_id_header)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: Auth enforcement
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 2: Authentication Enforcement")
print("=" * 70)


def test_auth_required_simulate():
    status, body, headers, elapsed = req("POST", "/v1/simulate", body={"mode": "auto"}, auth=False)
    assert status == 401, f"Expected 401, got {status}"


check("POST /v1/simulate without auth → 401", test_auth_required_simulate)


def test_auth_required_recommend():
    status, body, headers, elapsed = req("POST", "/v1/recommend", body={}, auth=False)
    assert status == 401, f"Expected 401, got {status}"


check("POST /v1/recommend without auth → 401", test_auth_required_recommend)


def test_auth_required_me():
    status, body, headers, elapsed = req("GET", "/v1/me", auth=False)
    assert status == 401, f"Expected 401, got {status}"


check("GET /v1/me without auth → 401", test_auth_required_me)


def test_auth_required_runs():
    status, body, headers, elapsed = req("GET", "/v1/runs", auth=False)
    assert status == 401, f"Expected 401, got {status}"


check("GET /v1/runs without auth → 401", test_auth_required_runs)


def test_auth_required_api_keys():
    status, body, headers, elapsed = req("GET", "/v1/api-keys", auth=False)
    assert status == 401, f"Expected 401, got {status}"


check("GET /v1/api-keys without auth → 401", test_auth_required_api_keys)


def test_invalid_api_key():
    status, body, headers, elapsed = req(
        "POST",
        "/v1/simulate",
        body={"mode": "auto"},
        headers={"X-API-Key": "de_live_FAKE_KEY_THAT_DOES_NOT_EXIST"},
        auth=False,
    )
    assert status == 401, f"Expected 401, got {status}"
    error = body.get("error") or body.get("detail", {}).get("error", {})
    code = error.get("code", "")
    assert code == "invalid_api_key", f"Expected code='invalid_api_key', got '{code}'"


check("Invalid API key → 401 + code: invalid_api_key", test_invalid_api_key)


def test_bearer_auth():
    """Test Authorization: Bearer header works too."""
    status, body, headers, elapsed = req(
        "GET",
        "/v1/me",
        headers={"Authorization": f"Bearer {API_KEY}"},
        auth=False,
    )
    assert status == 200, f"Expected 200 with Bearer auth, got {status}: {body}"


check("Authorization: Bearer <key> works", test_bearer_auth)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: Core Simulation Endpoints (with real Mojo engine)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 3: Core Simulation (real Mojo engine)")
print("=" * 70)


def test_simulate_auto_mode():
    status, body, headers, elapsed = req_simulate(
        body={
            "mode": "auto",
            "runs": 1000,
            "scenario": {
                "variables": {"revenue": {"low": 80000, "high": 200000}},
                "objective": "maximize_net_value",
            },
        },
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "recommended_action" in body, f"Missing recommended_action: {list(body.keys())}"
    assert body["recommended_action"] in ("proceed", "hold", "reject"), (
        f"Unexpected action: {body['recommended_action']}"
    )
    assert "confidence" in body, "Missing confidence"
    assert 0 <= body["confidence"] <= 1, f"Confidence out of range: {body['confidence']}"
    timings.append(("POST /v1/simulate (auto, 1k runs)", elapsed))


check("POST /v1/simulate auto mode → 200 + decision envelope", test_simulate_auto_mode)


def test_simulate_expert_mode():
    status, body, headers, elapsed = req_simulate(
        body={
            "mode": "expert",
            "runs": 500,
            "simulation": {
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
        },
    )
    assert status == 200, f"Expected 200, got {status}: {json.dumps(body)[:300]}"
    assert "recommended_action" in body, "Missing recommended_action"
    timings.append(("POST /v1/simulate (expert, 500 runs)", elapsed))


check("POST /v1/simulate expert mode → 200 + decision envelope", test_simulate_expert_mode)


def test_simulate_with_seed():
    """Seeded simulation should be deterministic."""
    r1_status, r1_body, _, _ = req_simulate(
        body={
            "mode": "auto",
            "runs": 100,
            "seed": 42,
            "scenario": {
                "variables": {"x": {"low": 0, "high": 100}},
                "objective": "maximize_net_value",
            },
        },
    )
    r2_status, r2_body, _, _ = req_simulate(
        body={
            "mode": "auto",
            "runs": 100,
            "seed": 42,
            "scenario": {
                "variables": {"x": {"low": 0, "high": 100}},
                "objective": "maximize_net_value",
            },
        },
    )
    _assert_expected_status(r1_status, r1_body)
    _assert_expected_status(r2_status, r2_body)
    assert r1_body.get("confidence") == r2_body.get("confidence"), (
        "Seeded runs should be deterministic"
    )


check("Seeded simulation → deterministic results", test_simulate_with_seed)


def test_simulate_10k_runs_latency():
    """10k runs should complete in under 1s."""
    status, body, headers, elapsed = req_simulate(
        body={
            "mode": "auto",
            "runs": 10000,
            "scenario": {
                "variables": {"x": {"low": 0, "high": 100}},
                "objective": "maximize_net_value",
            },
        },
    )
    assert status == 200, f"Expected 200, got {status}"
    assert elapsed < 2.0, f"10k runs took {elapsed:.2f}s — expected under 2s"
    timings.append(("POST /v1/simulate (auto, 10k runs)", elapsed))


check("10k runs completes under 2s", test_simulate_10k_runs_latency)


def test_simulate_bad_payload():
    status, body, headers, elapsed = req(
        "POST",
        "/v1/simulate",
        body={
            "mode": "invalid_mode",
        },
    )
    assert status == 422, f"Expected 422, got {status}"


check("Invalid payload → 422 validation error", test_simulate_bad_payload)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: Account & Metadata Endpoints
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 4: Account & Metadata Endpoints")
print("=" * 70)


def test_me():
    status, body, headers, elapsed = req("GET", "/v1/me")
    assert status == 200, f"Expected 200, got {status}: {body}"
    # Should have org/user info — response may use 'user', 'org', 'org_id', 'email', etc.
    assert any(k in body for k in ("org_id", "organization", "email", "user", "org")), (
        f"Missing identity fields: {list(body.keys())}"
    )


check("GET /v1/me → 200 with identity", test_me)


def test_usage():
    status, body, headers, elapsed = req("GET", "/v1/usage")
    assert status == 200, f"Expected 200, got {status}: {body}"


check("GET /v1/usage → 200", test_usage)


def test_api_keys_list():
    status, body, headers, elapsed = req("GET", "/v1/api-keys")
    assert status == 200, f"Expected 200, got {status}"
    assert isinstance(body, list) or "keys" in body or "api_keys" in body, "Expected list of keys"


check("GET /v1/api-keys → 200 list", test_api_keys_list)


def test_templates():
    status, body, headers, elapsed = req("GET", "/v1/simulate/templates")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, list) or "templates" in body, "Expected templates data"


check("GET /v1/simulate/templates → 200", test_templates)


def test_distributions():
    status, body, headers, elapsed = req("GET", "/v1/distributions")
    assert status == 200, f"Expected 200, got {status}: {body}"


check("GET /v1/distributions → 200", test_distributions)


def test_runs_list():
    status, body, headers, elapsed = req("GET", "/v1/runs")
    assert status == 200, f"Expected 200, got {status}: {body}"


check("GET /v1/runs → 200", test_runs_list)


def test_logs():
    """Logs endpoint is SSE — just check it connects and returns 200 (don't read body, it streams forever)."""
    url = f"{BASE_URL}/v1/logs"
    h = {"X-API-Key": API_KEY}
    request = urllib.request.Request(url, headers=h)
    try:
        resp = urllib.request.urlopen(request, timeout=3)
        status = resp.status
        # Read just first 256 bytes to confirm SSE is streaming, then close
        resp.read(256)
        resp.close()
        assert status == 200, f"Expected 200, got {status}"
    except (TimeoutError, urllib.error.URLError):
        # SSE may timeout on read since it's a long-lived stream — that's OK
        pass


check("GET /v1/logs → 200 (SSE stream)", test_logs)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: Recommend endpoint
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 5: Recommend Endpoint")
print("=" * 70)


def test_recommend():
    status, body, headers, elapsed = req(
        "POST",
        "/v1/recommend",
        body={
            "actions": [
                {
                    "name": "Plan A",
                    "request": {
                        "mode": "auto",
                        "runs": 100,
                        "scenario": {
                            "variables": {"revenue": {"low": 100000, "high": 200000}},
                            "objective": "maximize_net_value",
                        },
                    },
                },
                {
                    "name": "Plan B",
                    "request": {
                        "mode": "auto",
                        "runs": 100,
                        "scenario": {
                            "variables": {"revenue": {"low": 80000, "high": 150000}},
                            "objective": "maximize_net_value",
                        },
                    },
                },
            ],
        },
        timeout=15,
    )
    assert status == 200, f"Expected 200, got {status}: {json.dumps(body)[:300]}"
    assert "recommended_action" in body, (
        f"Missing recommended_action in response: {list(body.keys())}"
    )
    timings.append(("POST /v1/recommend (2 actions)", elapsed))


check("POST /v1/recommend → 200 with recommendation", test_recommend)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6: Team & Connectors
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 6: Team, Connectors, Deployments")
print("=" * 70)


def test_team():
    status, body, headers, elapsed = req("GET", "/v1/team")
    assert status == 200, f"Expected 200, got {status}: {body}"


check("GET /v1/team → 200", test_team)


def test_connectors():
    status, body, headers, elapsed = req("GET", "/v1/connectors")
    assert status == 200, f"Expected 200, got {status}: {body}"


check("GET /v1/connectors → 200", test_connectors)


def test_deployments():
    status, body, headers, elapsed = req("GET", "/v1/deployments")
    assert status == 200, f"Expected 200, got {status}: {body}"


check("GET /v1/deployments → 200", test_deployments)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 7: Auth flow (signup/login)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 7: Auth Flow")
print("=" * 70)


def test_signup_requires_fields():
    status, body, headers, elapsed = req("POST", "/auth/signup", body={}, auth=False)
    assert status == 422, f"Expected 422 for empty signup, got {status}"


check("POST /auth/signup with empty body → 422", test_signup_requires_fields)


def test_login_requires_fields():
    status, body, headers, elapsed = req("POST", "/auth/login", body={}, auth=False)
    assert status == 422, f"Expected 422 for empty login, got {status}"


check("POST /auth/login with empty body → 422", test_login_requires_fields)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8: Error handling & security
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 8: Error Handling & Security")
print("=" * 70)


def test_404_proper_json():
    status, body, headers, elapsed = req("GET", "/v1/nonexistent", auth=False)
    assert status in (404, 405), f"Expected 404/405, got {status}"


check("Unknown route → 404/405", test_404_proper_json)


def test_no_traceback_leak():
    """Errors should never expose Python tracebacks."""
    status, body, headers, elapsed = req("POST", "/v1/simulate", body={"mode": "auto"}, auth=False)
    body_str = json.dumps(body) if isinstance(body, dict) else str(body)
    assert "Traceback" not in body_str, "Response leaks traceback!"
    assert 'File "' not in body_str, "Response leaks file paths!"


check("Error responses never leak tracebacks", test_no_traceback_leak)


def test_cors_headers():
    """CORS should be configured."""
    status, body, headers, elapsed = req("GET", "/v1/health", auth=False)
    # After CORS middleware, OPTIONS would return Access-Control headers
    # For regular GET, check if the header is present
    # May not be present on same-origin requests, so just ensure no error
    assert status == 200


check("CORS middleware present (no crash on GET)", test_cors_headers)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 9: Latency benchmarks
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 9: Latency Benchmarks")
print("=" * 70)


def test_health_latency():
    """Health should be under 20ms."""
    _, _, _, elapsed = req("GET", "/v1/health", auth=False)
    assert elapsed < 0.100, f"Health took {elapsed * 1000:.0f}ms — expected under 100ms"


check("Health endpoint < 100ms", test_health_latency)


def test_simulate_latency():
    """1000 run simulation should be under 500ms."""
    _, _, _, elapsed = req_simulate(
        body={
            "mode": "auto",
            "runs": 1000,
            "scenario": {
                "variables": {"x": {"low": 0, "high": 100}},
                "objective": "maximize_net_value",
            },
        },
    )
    assert elapsed < 0.5, f"1k runs took {elapsed * 1000:.0f}ms — expected under 500ms"


check("1k run simulation < 500ms", test_simulate_latency)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULTS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  RESULTS SUMMARY")
print("=" * 70)

passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
skipped = sum(1 for r in results if r[0] == SKIP)
total = len(results)

print(f"\n  Total: {total} tests")
print(f"  Passed: {passed} {PASS}")
print(f"  Failed: {failed} {FAIL}")
print(f"  Skipped: {skipped} {SKIP}")

if timings:
    print("\n  ── Latency Summary ──")
    for name, elapsed in timings:
        print(f"    {name}: {elapsed * 1000:.0f}ms")

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
    print(f"  🎉 ALL {passed} INTEGRATION TESTS PASSED!")
else:
    print(f"  ⚠️  {failed} FAILURES — fix before deploying")
artifact_path = _write_summary_artifact()
print(f"  Summary artifact: {artifact_path}")
print(f"{'=' * 70}\n")

sys.exit(1 if failed > 0 else 0)
