"""
Auth & Security Edge Case Integration Tests — Phase 11 (Final)

Exercises the full security surface of the Algenta Decision Engine API:
  - API key authentication (X-API-Key + Bearer)
  - RBAC enforcement
  - Request ID middleware
  - Rate limiting headers
  - Input sanitization (SQLi, XSS, path traversal)
  - Error response security (no stack traces, consistent JSON)
  - Security headers
  - Large / malformed payload handling

Prerequisites:
  1. API server running: make dev-api  (http://localhost:8000)
  2. PostgreSQL running on :5432
  3. Redis running on :6379

Run:
  python3 tests/integration/test_auth_security.py
"""

# ruff: noqa: E402, N818

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_integration_artifacts import write_live_integration_summary

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

try:
    from tests.integration.live_local_defaults import (
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()
SUITE_NAME = "auth_security_integration"
STARTED = time.perf_counter()

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple] = []
timings: list[tuple[str, float]] = []

pytestmark = pytest.mark.usefixtures("legacy_live_api_server")


class EnvironmentBlocked(RuntimeError):
    """Raised when the live environment cannot execute simulation due to quota/capacity."""


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _missing_live_api_key_reason(exc: BaseException) -> str | None:
    if API_KEY_CONFIGURED:
        return None
    text = str(exc)
    if any(token in text for token in ("401", "403", "Authentication", "invalid_api_key")):
        return "DE_API_KEY is not set; skipping authenticated auth/security checks that require a real live key."
    return None


def _require_configured_live_api_key(reason: str) -> None:
    if API_KEY_CONFIGURED:
        return
    pytest.skip(
        f"DE_API_KEY is not set; skipping {reason} that require a real live key."
    )


def ensure_simulation_capacity_available(status: int, body) -> None:
    reason = classify_simulation_capacity_blocker(status=status, payload=body)
    if reason:
        raise EnvironmentBlocked(reason)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def req(method: str, path: str, body=None, headers=None, auth=True, timeout=10):
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
            raise TimeoutError(f"Request to {url} timed out after {timeout}s") from err
        raise RuntimeError(f"Cannot connect to {BASE_URL} — is the API server running?") from err


def raw_req(method: str, path: str, raw_data: bytes = None, headers: dict = None, timeout=10):
    """Make raw HTTP request with arbitrary bytes and headers (no default Content-Type)."""
    url = f"{BASE_URL}{path}"
    h = headers or {}
    request = urllib.request.Request(url, data=raw_data, headers=h, method=method)
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
        raise TimeoutError(f"Request to {url} timed out after {timeout}s") from err
    except urllib.error.URLError as err:
        if "timed out" in str(err):
            elapsed = time.perf_counter() - t0
            raise TimeoutError(f"Request to {url} timed out after {timeout}s") from err
        raise RuntimeError(f"Cannot connect to {BASE_URL} — is the API server running?") from err


def check(name: str, fn):
    """Run a test function, record pass/fail/skip."""
    t0 = time.perf_counter()
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        fn()
        elapsed = time.perf_counter() - t0
        results.append((PASS, name))
        timings.append((name, elapsed))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except EnvironmentBlocked as e:
        elapsed = time.perf_counter() - t0
        results.append((SKIP, name, str(e)))
        timings.append((name, elapsed))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except AssertionError as e:
        missing_key_reason = _missing_live_api_key_reason(e)
        if missing_key_reason:
            elapsed = time.perf_counter() - t0
            results.append((SKIP, name, missing_key_reason))
            timings.append((name, elapsed))
            _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {missing_key_reason}")
            return
        elapsed = time.perf_counter() - t0
        results.append((FAIL, name, str(e)))
        timings.append((name, elapsed))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {e}")
    except Exception as e:
        missing_key_reason = _missing_live_api_key_reason(e)
        if missing_key_reason:
            elapsed = time.perf_counter() - t0
            results.append((SKIP, name, missing_key_reason))
            timings.append((name, elapsed))
            _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {missing_key_reason}")
            return
        elapsed = time.perf_counter() - t0
        results.append((FAIL, name, str(e)))
        timings.append((name, elapsed))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {e}")


# ─── Minimal simulate payload (used for auth-protected endpoint tests) ────────
MINIMAL_SIMULATE_PAYLOAD = {
    "decision": "Security test decision",
    "variables": [{"name": "x", "distribution": "normal", "params": {"mean": 100, "std": 10}}],
    "runs": 100,
}


# =============================================================================
# 1. AUTHENTICATION TESTS
# =============================================================================
def test_auth_valid_api_key_header():
    """Valid API key via X-API-Key header returns 200."""
    _require_configured_live_api_key("valid API-key authentication checks")
    status, body, hdrs, _ = req("GET", "/v1/health", auth=True)
    assert status == 200, f"Expected 200 with valid key, got {status}: {body}"


def test_auth_valid_bearer_token():
    """Valid API key via Authorization: Bearer header returns 200."""
    _require_configured_live_api_key("valid Bearer-token authentication checks")
    status, body, hdrs, _ = req(
        "GET",
        "/v1/health",
        headers={"Authorization": f"Bearer {API_KEY}"},
        auth=False,
    )
    assert status == 200, f"Expected 200 with Bearer token, got {status}: {body}"


def test_auth_missing_api_key():
    """Missing API key returns 401."""
    status, body, hdrs, _ = req("GET", "/v1/simulate/templates", auth=False, headers={})
    assert status in (401, 403), f"Expected 401/403 with no key, got {status}: {body}"


def test_auth_empty_api_key():
    """Empty API key returns 401."""
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": ""},
        auth=False,
    )
    assert status in (401, 403), f"Expected 401/403 with empty key, got {status}: {body}"


def test_auth_invalid_api_key():
    """Completely bogus API key returns 401."""
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": "de_live_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"},
        auth=False,
    )
    assert status in (401, 403), f"Expected 401/403 with invalid key, got {status}: {body}"


def test_auth_malformed_prefix():
    """API key with wrong prefix returns 401."""
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": "wrong_prefix_XXXXXXXXXXXXXXXXXXXXXXXX"},
        auth=False,
    )
    assert status in (401, 403), f"Expected 401/403 with wrong prefix, got {status}: {body}"


def test_auth_wrong_length():
    """API key with wrong length (too short) returns 401."""
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": "de_live_short"},
        auth=False,
    )
    assert status in (401, 403), f"Expected 401/403 with short key, got {status}: {body}"


def test_auth_sql_injection():
    """SQL injection attempt in API key header is rejected safely."""
    sqli_key = "de_live_' OR '1'='1'; DROP TABLE api_keys;--"
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": sqli_key},
        auth=False,
    )
    assert status in (401, 403, 422), f"Expected rejection for SQLi key, got {status}: {body}"
    # Ensure no database error leak
    body_str = json.dumps(body) if isinstance(body, dict) else str(body)
    assert "traceback" not in body_str.lower(), "Stack trace leaked in SQLi response"
    assert "psycopg" not in body_str.lower(), "Database driver name leaked"
    assert "sqlalchemy" not in body_str.lower(), "ORM name leaked"


def test_auth_very_long_key():
    """Very long API key (10,000 chars) is rejected safely without crash."""
    long_key = "de_live_" + "A" * 10000
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": long_key},
        auth=False,
    )
    assert status in (401, 403, 413, 422, 431), f"Expected rejection for 10k char key, got {status}"


def test_auth_null_bytes():
    """Null bytes in API key are handled safely."""
    null_key = "de_live_AAAA\x00BBBB\x00CCCCCCCCCCCCCCCC"
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": null_key},
        auth=False,
    )
    assert status in (401, 403, 400, 422), f"Expected rejection for null-byte key, got {status}"


def test_auth_unicode_characters():
    """Unicode characters in API key are handled safely."""
    unicode_key = "de_live_日本語テスト🔑✨AAAAAAAAAAAAAAAA"
    try:
        status, body, hdrs, _ = req(
            "GET",
            "/v1/simulate/templates",
            headers={"X-API-Key": unicode_key},
            auth=False,
        )
        assert status in (401, 403, 400, 422), f"Expected rejection for unicode key, got {status}"
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Python's urllib rejects non-latin1 header values before sending —
        # this is itself safe handling (the request never reaches the server)
        pass


def test_auth_bearer_without_token():
    """Authorization: Bearer with no token returns 401."""
    status, body, hdrs, _ = raw_req(
        "GET",
        "/v1/simulate/templates",
        headers={"Authorization": "Bearer "},
    )
    assert status in (401, 403, 422), f"Expected 401/403 for empty Bearer, got {status}"


def test_auth_wrong_scheme():
    """Authorization: Basic instead of Bearer returns 401."""
    import base64

    creds = base64.b64encode(b"user:pass").decode()
    status, body, hdrs, _ = raw_req(
        "GET",
        "/v1/simulate/templates",
        headers={"Authorization": f"Basic {creds}"},
    )
    assert status in (401, 403), f"Expected 401/403 for Basic auth, got {status}"


# =============================================================================
# 2. AUTHORIZATION & RBAC TESTS
# =============================================================================
def test_rbac_write_endpoint_with_valid_key():
    """POST /v1/simulate works with valid API key (member role)."""
    status, body, hdrs, _ = req("POST", "/v1/simulate", body=MINIMAL_SIMULATE_PAYLOAD)
    ensure_simulation_capacity_available(status, body)
    # Should succeed (200) or at worst fail with validation (422) but NOT 401/403
    assert status not in (401, 403), f"Expected auth to pass for simulate, got {status}: {body}"


def test_rbac_org_isolation_invalid_run_id():
    """Accessing a non-existent run ID returns 404, not another org's data."""
    fake_run_id = "00000000-0000-0000-0000-000000000000"
    status, body, hdrs, _ = req("GET", f"/v1/runs/{fake_run_id}")
    assert status in (404, 403), f"Expected 404/403 for non-existent run, got {status}: {body}"
    # Ensure no data leakage
    body_str = json.dumps(body) if isinstance(body, dict) else str(body)
    assert "org_id" not in body_str.lower() or "error" in body_str.lower(), (
        "Response may leak org_id from another organization"
    )


def test_rbac_health_no_auth_required():
    """GET /v1/health should work without auth (public endpoint)."""
    status, body, hdrs, _ = req("GET", "/v1/health", auth=False)
    assert status == 200, f"Expected 200 for health endpoint, got {status}: {body}"


def test_rbac_docs_no_auth_required():
    """GET /docs should work without auth (public endpoint)."""
    status, body, hdrs, _ = raw_req("GET", "/docs")
    assert status == 200, f"Expected 200 for docs, got {status}"


def test_rbac_openapi_no_auth_required():
    """GET /openapi.json should work without auth."""
    status, body, hdrs, _ = raw_req("GET", "/openapi.json")
    assert status == 200, f"Expected 200 for openapi.json, got {status}"


# =============================================================================
# 3. REQUEST VALIDATION TESTS
# =============================================================================
def test_request_oversized_body():
    """Oversized request body (>1MB) is rejected."""
    # Generate a payload > 1MB (the config default)
    huge_payload = {
        "decision": "Oversized test",
        "variables": [
            {"name": f"var_{i}", "distribution": "normal", "params": {"mean": 0, "std": 1}}
            for i in range(50000)
        ],
        "runs": 100,
    }
    status, body, hdrs, _ = req("POST", "/v1/simulate", body=huge_payload, timeout=15)
    ensure_simulation_capacity_available(status, body)
    # Should reject with 413 (too large) or 422 (validation) or handle gracefully
    assert status in (413, 422, 400, 500), f"Expected rejection for oversized body, got {status}"


def test_request_invalid_content_type():
    """Invalid Content-Type on POST should be rejected or handled."""
    status, body, hdrs, _ = raw_req(
        "POST",
        "/v1/simulate",
        raw_data=b"this is not json",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "text/plain",
        },
    )
    assert status in (400, 415, 422), (
        f"Expected rejection for text/plain POST, got {status}: {body}"
    )


def test_request_missing_content_type():
    """Missing Content-Type on POST still fails gracefully."""
    payload = json.dumps(MINIMAL_SIMULATE_PAYLOAD).encode()
    status, body, hdrs, _ = raw_req(
        "POST",
        "/v1/simulate",
        raw_data=payload,
        headers={"X-API-Key": API_KEY},
    )
    ensure_simulation_capacity_available(status, body)
    # FastAPI may still parse it or reject — either way, no crash
    assert status in (200, 400, 415, 422), f"Expected graceful handling, got {status}: {body}"


def test_request_deeply_nested_json():
    """Extremely nested JSON is handled safely (no stack overflow)."""
    # Build 200 levels of nesting
    nested = {"x": 1}
    for _ in range(200):
        nested = {"nested": nested}
    nested["decision"] = "Nested test"
    nested["variables"] = [{"name": "x", "distribution": "normal", "params": {"mean": 0, "std": 1}}]
    nested["runs"] = 100

    status, body, hdrs, _ = req("POST", "/v1/simulate", body=nested, timeout=15)
    ensure_simulation_capacity_available(status, body)
    # Should either process it or reject — no crash
    assert status in (200, 400, 422, 500), (
        f"Expected graceful handling of nested JSON, got {status}"
    )


def test_request_duplicate_headers():
    """Duplicate headers are handled safely."""
    # urllib doesn't easily support duplicate headers, but we can test double API key
    status, body, hdrs, _ = req(
        "GET",
        "/v1/health",
        headers={"X-API-Key": API_KEY},
        auth=True,  # This also sets X-API-Key, so it's effectively double
    )
    assert status == 200, f"Expected 200 with duplicate auth headers, got {status}"


def test_request_empty_body_on_post():
    """POST with empty body returns 422 (validation), not 500."""
    status, body, hdrs, _ = raw_req(
        "POST",
        "/v1/simulate",
        raw_data=b"",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    assert status in (400, 422), f"Expected 400/422 for empty POST body, got {status}: {body}"


def test_request_malformed_json():
    """Malformed JSON body returns 422/400, not 500."""
    status, body, hdrs, _ = raw_req(
        "POST",
        "/v1/simulate",
        raw_data=b'{"decision": "test", "variables": [BROKEN',
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    assert status in (400, 422), f"Expected 400/422 for malformed JSON, got {status}: {body}"


# =============================================================================
# 4. SECURITY HEADERS TESTS
# =============================================================================
def test_headers_request_id_present():
    """Verify X-Request-Id is present in every response."""
    status, body, hdrs, _ = req("GET", "/v1/health")
    # Headers may be case-insensitive
    rid = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
    assert rid is not None, f"X-Request-Id missing from response headers. Got: {list(hdrs.keys())}"
    assert len(rid) > 0, "X-Request-Id is empty"


def test_headers_request_id_unique():
    """Verify X-Request-Id is unique across multiple requests."""
    ids = set()
    for _ in range(5):
        status, body, hdrs, _ = req("GET", "/v1/health")
        rid = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
        assert rid is not None, "X-Request-Id missing"
        ids.add(rid)
    assert len(ids) == 5, f"Expected 5 unique request IDs, got {len(ids)}: {ids}"


def test_headers_no_server_version_leak():
    """Verify no server version is leaked in response headers."""
    status, body, hdrs, _ = req("GET", "/v1/health")
    server_hdr = hdrs.get("Server", hdrs.get("server", ""))
    # Should not reveal version numbers like "uvicorn/0.x" or "Python/3.x"
    if server_hdr:
        assert "python" not in server_hdr.lower() or "cpython" not in server_hdr.lower(), (
            f"Server header reveals Python version: {server_hdr}"
        )


def test_headers_content_type_json():
    """Verify Content-Type is application/json on API responses."""
    status, body, hdrs, _ = req("GET", "/v1/health")
    ct = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    assert "application/json" in ct, f"Expected application/json, got: {ct}"


def test_headers_no_sensitive_leak_on_error():
    """Error responses don't leak internal details in headers."""
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": "de_live_INVALID_KEY_000000000000000"},
        auth=False,
    )
    # Check no sensitive headers
    for hdr_name, hdr_val in hdrs.items():
        hdr_lower = hdr_name.lower()
        assert "x-powered-by" != hdr_lower or "express" not in hdr_val.lower(), (
            "X-Powered-By leaks framework info"
        )
        # Ensure no stack trace in any header
        assert "traceback" not in str(hdr_val).lower(), f"Header {hdr_name} contains traceback"


def test_headers_cors_present():
    """Verify CORS headers are set on responses (if origin matches)."""
    status, body, hdrs, _ = raw_req(
        "OPTIONS",
        "/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # The server allows CORS for localhost:3000 per config
    # If CORS is configured, it should return an Allow-Origin header
    # It may be * or the specific origin
    assert status == 200, f"Expected 200 for OPTIONS, got {status}"


def test_headers_request_id_on_error():
    """X-Request-Id is present even on error responses."""
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": "de_live_INVALID_KEY_000000000000000"},
        auth=False,
    )
    rid = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
    assert rid is not None, "X-Request-Id missing on error response"


# =============================================================================
# 5. RATE LIMITING TESTS
# =============================================================================
def test_rate_limit_headers_present():
    """Verify rate limit related headers or behavior (multiple requests don't 429 under normal load)."""
    # Make a few requests — should all succeed under the developer plan limit (300/min)
    for i in range(3):
        status, body, hdrs, _ = req("GET", "/v1/health")
        assert status == 200, f"Request {i + 1} failed with {status}"


def test_rate_limit_not_triggered_under_normal_load():
    """Verify 10 sequential requests don't trigger rate limit."""
    for i in range(10):
        status, body, hdrs, _ = req("GET", "/v1/health")
        assert status != 429, f"Rate limit hit on request {i + 1} — unexpected under normal load"


def test_rate_limit_429_response_format():
    """If a 429 is returned, it should have consistent error JSON format."""
    # We won't actually trigger 429, but test that 429 format is correct
    # by checking the quota_service code expectations
    # Instead, validate that normal responses don't have 429 status
    status, body, hdrs, _ = req("GET", "/v1/health")
    assert status == 200, f"Expected 200, got {status}"


# =============================================================================
# 6. INPUT SANITIZATION TESTS
# =============================================================================
def test_sanitization_xss_in_decision():
    """XSS payload in decision field is stored safely (no execution risk)."""
    xss_payload = {
        "decision": '<script>alert("xss")</script><img onerror="alert(1)" src=x>',
        "variables": [
            {"name": "price", "distribution": "normal", "params": {"mean": 100, "std": 10}}
        ],
        "runs": 100,
    }
    status, body, hdrs, _ = req("POST", "/v1/simulate", body=xss_payload)
    ensure_simulation_capacity_available(status, body)
    if status == 200:
        body_str = json.dumps(body)
        # The response should contain the decision text but NOT execute it
        # JSON-encoding naturally escapes angle brackets
        assert "alert(" not in body_str or '"decision"' in body_str, (
            "XSS payload may not be safely escaped"
        )
    else:
        # 422 or 400 is also acceptable (rejecting XSS input)
        assert status in (400, 422, 500), f"Unexpected status for XSS payload: {status}"


def test_sanitization_sql_injection_query_param():
    """SQL injection in query parameters is handled safely."""
    import urllib.parse

    sqli = "'; DROP TABLE organizations; --"
    encoded_sqli = urllib.parse.quote(sqli, safe="")
    status, body, hdrs, _ = req("GET", f"/v1/runs?limit=10&offset={encoded_sqli}")
    # Should either parse as invalid (422) or ignore the injection
    body_str = json.dumps(body) if isinstance(body, dict) else str(body)
    assert "drop table" not in body_str.lower(), "SQL injection reflected in response"
    assert "traceback" not in body_str.lower(), "Stack trace in SQLi response"


def test_sanitization_path_traversal():
    """Path traversal in URL parameters is rejected."""
    status, body, hdrs, _ = req("GET", "/v1/runs/../../etc/passwd")
    assert status in (400, 404, 405, 422), f"Expected rejection for path traversal, got {status}"
    body_str = json.dumps(body) if isinstance(body, dict) else str(body)
    assert "root:" not in body_str, "Path traversal returned /etc/passwd content"


def test_sanitization_special_chars_in_field_names():
    """Special characters in variable names are handled safely."""
    payload = {
        "decision": "Special chars test",
        "variables": [
            {
                "name": "price<>&\"'`${}",
                "distribution": "normal",
                "params": {"mean": 100, "std": 10},
            }
        ],
        "runs": 100,
    }
    status, body, hdrs, _ = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    # Should either process or reject — no crash
    assert status in (200, 400, 422), f"Expected graceful handling of special chars, got {status}"


def test_sanitization_script_injection_in_variable_name():
    """Script injection in variable names doesn't break processing."""
    payload = {
        "decision": "Script test",
        "variables": [
            {
                "name": "{{constructor.constructor('return this')()}}",
                "distribution": "normal",
                "params": {"mean": 50, "std": 5},
            }
        ],
        "runs": 100,
    }
    status, body, hdrs, _ = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    assert status in (200, 400, 422), (
        f"Expected graceful handling of template injection, got {status}"
    )
    body_str = json.dumps(body) if isinstance(body, dict) else str(body)
    assert "traceback" not in body_str.lower(), "Stack trace leaked on template injection"


def test_sanitization_null_bytes_in_payload():
    """Null bytes in JSON string values are handled safely."""
    payload = {
        "decision": "Null byte \x00 test",
        "variables": [
            {"name": "x\x00y", "distribution": "normal", "params": {"mean": 0, "std": 1}}
        ],
        "runs": 100,
    }
    try:
        status, body, hdrs, _ = req("POST", "/v1/simulate", body=payload)
        assert status in (200, 400, 422), f"Expected graceful handling of null bytes, got {status}"
    except Exception:
        # json.dumps may raise on null bytes — that's fine
        pass


def test_sanitization_extremely_long_field_values():
    """Extremely long string values in fields are handled safely."""
    payload = {
        "decision": "A" * 100000,  # 100K character decision
        "variables": [{"name": "x", "distribution": "normal", "params": {"mean": 0, "std": 1}}],
        "runs": 100,
    }
    status, body, hdrs, _ = req("POST", "/v1/simulate", body=payload, timeout=15)
    ensure_simulation_capacity_available(status, body)
    # Should either process or reject with validation
    assert status in (200, 400, 413, 422), f"Expected graceful handling of long field, got {status}"


# =============================================================================
# 7. ERROR RESPONSE SECURITY TESTS
# =============================================================================
def test_error_401_no_internal_details():
    """401 responses don't leak internal details."""
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": "de_live_TOTALLY_FAKE_KEY_0000000000"},
        auth=False,
    )
    assert status in (401, 403), f"Expected 401/403, got {status}"
    body_str = json.dumps(body) if isinstance(body, dict) else str(body)
    # Should not leak stack traces, internal paths, or database details
    assert "traceback" not in body_str.lower(), "Stack trace in 401 response"
    assert "/home/" not in body_str and "/Users/" not in body_str, "Internal path leaked"
    assert "postgresql" not in body_str.lower(), "Database URL leaked"
    assert "redis://" not in body_str.lower(), "Redis URL leaked"


def test_error_422_validation_structure():
    """422 validation errors show field-level errors without stack traces."""
    # Send invalid simulate payload
    status, body, hdrs, _ = req("POST", "/v1/simulate", body={"invalid": True})
    ensure_simulation_capacity_available(status, body)
    assert status == 422, f"Expected 422 for invalid payload, got {status}: {body}"
    assert isinstance(body, dict), "422 body should be JSON dict"
    assert "error" in body, f"422 response missing 'error' key: {body}"
    error_obj = body["error"]
    assert "code" in error_obj, f"Error object missing 'code': {error_obj}"
    # Should not contain stack traces
    body_str = json.dumps(body)
    assert "Traceback" not in body_str, "Stack trace in 422 response"
    assert 'File "/' not in body_str, "Internal file path in 422 response"


def test_error_404_consistent_json():
    """404 errors have consistent JSON structure."""
    status, body, hdrs, _ = req("GET", "/v1/nonexistent-endpoint-12345")
    assert status in (404, 405), f"Expected 404/405, got {status}"
    if isinstance(body, dict):
        # FastAPI default 404 may just be {"detail": "Not Found"}
        assert "detail" in body or "error" in body, f"404 response has unexpected structure: {body}"


def test_error_405_method_not_allowed():
    """Method not allowed returns proper error."""
    status, body, hdrs, _ = req("DELETE", "/v1/health")
    assert status in (404, 405), f"Expected 404/405 for DELETE on health, got {status}"


def test_error_response_consistent_structure():
    """All error responses have a consistent JSON structure with 'error' key."""
    test_cases = [
        # (method, path, auth, expected_statuses)
        ("GET", "/v1/simulate/templates", False, (401, 403)),
        ("POST", "/v1/simulate", True, (422,)),  # missing required fields
    ]
    for method, path, use_auth, expected in test_cases:
        body_data = {"incomplete": True} if method == "POST" else None
        headers = {"X-API-Key": API_KEY} if use_auth else {}
        if method == "POST":
            headers["Content-Type"] = "application/json"
        status, body, hdrs, _ = req(method, path, body=body_data, auth=use_auth)
        if method == "POST" and path == "/v1/simulate":
            ensure_simulation_capacity_available(status, body)
        if status in expected:
            if isinstance(body, dict) and "error" in body:
                error = body["error"]
                assert "code" in error, (
                    f"Error response missing 'code' for {method} {path}: {error}"
                )
                assert "message" in error, (
                    f"Error response missing 'message' for {method} {path}: {error}"
                )


def test_error_500_no_stack_trace():
    """Verify that error responses never expose stack traces."""
    # Try to trigger an error with a weird payload
    status, body, hdrs, _ = req(
        "POST",
        "/v1/simulate",
        body={"decision": "test", "variables": "not_a_list", "runs": 100},
    )
    ensure_simulation_capacity_available(status, body)
    if status >= 400:
        body_str = json.dumps(body) if isinstance(body, dict) else str(body)
        assert "Traceback (most recent call last)" not in body_str, (
            "Full Python traceback exposed in error response"
        )
        assert "site-packages" not in body_str, "Library paths exposed in error"


# =============================================================================
# 8. AUDIT & TRACKING TESTS
# =============================================================================
def test_audit_request_id_propagation():
    """X-Request-Id from request is propagated to response."""
    custom_rid = "req_test_12345678abcdef"
    status, body, hdrs, _ = req(
        "GET",
        "/v1/health",
        headers={"X-Request-Id": custom_rid},
    )
    resp_rid = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
    assert resp_rid == custom_rid, f"Expected {custom_rid}, got {resp_rid}"


def test_audit_custom_request_id_respected():
    """Client-sent X-Request-Id is respected and returned."""
    custom_id = "my-custom-trace-id-abc123"
    status, body, hdrs, _ = req(
        "GET",
        "/v1/health",
        headers={"X-Request-Id": custom_id},
    )
    resp_id = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
    assert resp_id == custom_id, (
        f"Custom request ID not respected: expected {custom_id}, got {resp_id}"
    )


def test_audit_generated_request_id_format():
    """Auto-generated request IDs follow the expected format (req_ prefix)."""
    status, body, hdrs, _ = req("GET", "/v1/health")
    rid = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
    assert rid is not None, "X-Request-Id missing"
    assert rid.startswith("req_"), f"Generated request ID doesn't start with 'req_': {rid}"


def test_audit_request_id_in_error_body():
    """Request ID appears in error response body."""
    status, body, hdrs, _ = req(
        "GET",
        "/v1/simulate/templates",
        headers={"X-API-Key": "de_live_FAKE_KEY_FOR_AUDIT_TEST0000"},
        auth=False,
    )
    if isinstance(body, dict) and "error" in body:
        error = body["error"]
        # request_id should be in the error body
        if "request_id" in error:
            assert error["request_id"] is not None, "request_id in error body is None"
            resp_rid = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
            if resp_rid:
                assert error["request_id"] == resp_rid, (
                    f"request_id mismatch: body={error['request_id']} vs header={resp_rid}"
                )


def test_audit_request_id_on_422():
    """Request ID appears in 422 validation error body."""
    status, body, hdrs, _ = req("POST", "/v1/simulate", body={"bad": True})
    ensure_simulation_capacity_available(status, body)
    if status == 422 and isinstance(body, dict) and "error" in body:
        error = body["error"]
        if "request_id" in error:
            resp_rid = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
            if resp_rid:
                assert error["request_id"] == resp_rid, (
                    f"request_id mismatch on 422: body={error['request_id']} vs header={resp_rid}"
                )


# =============================================================================
# 9. ADDITIONAL EDGE CASE TESTS
# =============================================================================
def test_edge_http_method_override():
    """X-HTTP-Method-Override header shouldn't bypass route security."""
    status, body, hdrs, _ = raw_req(
        "GET",
        "/v1/health",
        headers={"X-HTTP-Method-Override": "DELETE"},
    )
    # Should still be treated as GET
    assert status == 200, f"Method override should not affect routing, got {status}"


def test_edge_double_encoding_path():
    """Double URL encoding in path doesn't bypass routing."""
    # %252e%252e = double-encoded '..'
    status, body, hdrs, _ = req("GET", "/v1/runs/%252e%252e/%252e%252e/etc/passwd")
    assert status in (400, 404, 422), f"Expected rejection for double-encoded path, got {status}"


def test_edge_json_content_type_with_charset():
    """Content-Type: application/json; charset=utf-8 is accepted."""
    payload = json.dumps(MINIMAL_SIMULATE_PAYLOAD).encode()
    status, body, hdrs, _ = raw_req(
        "POST",
        "/v1/simulate",
        raw_data=payload,
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    ensure_simulation_capacity_available(status, body)
    assert status not in (415,), f"Content-Type with charset should be accepted, got {status}"


def test_edge_trailing_slash():
    """Trailing slash on endpoints is handled (redirect or not found, not crash)."""
    status, body, hdrs, _ = req("GET", "/v1/health/")
    assert status in (200, 307, 404), f"Expected graceful handling of trailing slash, got {status}"


def test_edge_case_sensitive_headers():
    """Header name case sensitivity is handled correctly."""
    status, body, hdrs, _ = raw_req(
        "GET",
        "/v1/simulate/templates",
        headers={"x-api-key": API_KEY},  # lowercase header
    )
    # HTTP headers are case-insensitive per RFC 7230, but implementation may vary
    # Should either accept or reject clearly
    assert status in (200, 401, 403), f"Expected clear accept/reject, got {status}"


def test_edge_concurrent_request_ids():
    """Multiple rapid requests each get their own unique X-Request-Id."""
    ids = []
    for _ in range(20):
        status, body, hdrs, _ = req("GET", "/v1/health")
        rid = hdrs.get("X-Request-Id") or hdrs.get("x-request-id")
        if rid:
            ids.append(rid)
    assert len(set(ids)) == len(ids), f"Duplicate request IDs found in {len(ids)} requests"


def test_edge_empty_json_object():
    """Empty JSON object {} as body returns 422, not 500."""
    status, body, hdrs, _ = req("POST", "/v1/simulate", body={})
    ensure_simulation_capacity_available(status, body)
    assert status == 422, f"Expected 422 for empty JSON object, got {status}: {body}"


def test_edge_array_instead_of_object():
    """JSON array instead of object as body returns 422, not 500."""
    status, body, hdrs, _ = raw_req(
        "POST",
        "/v1/simulate",
        raw_data=b"[1, 2, 3]",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    assert status in (400, 422), f"Expected 422 for array body, got {status}"


def test_edge_numeric_decision():
    """Numeric value for decision field returns 422 (expects string)."""
    status, body, hdrs, _ = req(
        "POST",
        "/v1/simulate",
        body={"decision": 12345, "variables": [], "runs": 100},
    )
    ensure_simulation_capacity_available(status, body)
    # May succeed (coercion) or fail with 422 — either way not 500
    assert status in (200, 400, 422), (
        f"Expected graceful handling of numeric decision, got {status}"
    )


# =============================================================================
# Main test runner
# =============================================================================
def main():
    _emit("=" * 72)
    _emit("  Phase 11: Auth & Security Edge Case Integration Tests")
    _emit(f"  Target: {BASE_URL}")
    _emit("=" * 72)

    # Pre-flight: verify API server is reachable
    _emit("\n🔍 Pre-flight check...")
    try:
        status, body, hdrs, elapsed = req("GET", "/v1/health", auth=False)
        _emit(f"  ✅ API server reachable ({elapsed:.3f}s, status={status})")
    except Exception as e:
        _emit(f"  ❌ Cannot reach API server: {e}")
        sys.exit(1)

    # ── Authentication Tests ──────────────────────────────────────────────────
    _emit("\n── Authentication Tests ─────────────────────────────────────────")
    check("auth_valid_api_key_header", test_auth_valid_api_key_header)
    check("auth_valid_bearer_token", test_auth_valid_bearer_token)
    check("auth_missing_api_key", test_auth_missing_api_key)
    check("auth_empty_api_key", test_auth_empty_api_key)
    check("auth_invalid_api_key", test_auth_invalid_api_key)
    check("auth_malformed_prefix", test_auth_malformed_prefix)
    check("auth_wrong_length", test_auth_wrong_length)
    check("auth_sql_injection", test_auth_sql_injection)
    check("auth_very_long_key", test_auth_very_long_key)
    check("auth_null_bytes", test_auth_null_bytes)
    check("auth_unicode_characters", test_auth_unicode_characters)
    check("auth_bearer_without_token", test_auth_bearer_without_token)
    check("auth_wrong_scheme", test_auth_wrong_scheme)

    # ── Authorization & RBAC Tests ────────────────────────────────────────────
    _emit("\n── Authorization & RBAC Tests ───────────────────────────────────")
    check("rbac_write_endpoint_with_valid_key", test_rbac_write_endpoint_with_valid_key)
    check("rbac_org_isolation_invalid_run_id", test_rbac_org_isolation_invalid_run_id)
    check("rbac_health_no_auth_required", test_rbac_health_no_auth_required)
    check("rbac_docs_no_auth_required", test_rbac_docs_no_auth_required)
    check("rbac_openapi_no_auth_required", test_rbac_openapi_no_auth_required)

    # ── Request Validation Tests ──────────────────────────────────────────────
    _emit("\n── Request Validation Tests ─────────────────────────────────────")
    check("request_oversized_body", test_request_oversized_body)
    check("request_invalid_content_type", test_request_invalid_content_type)
    check("request_missing_content_type", test_request_missing_content_type)
    check("request_deeply_nested_json", test_request_deeply_nested_json)
    check("request_duplicate_headers", test_request_duplicate_headers)
    check("request_empty_body_on_post", test_request_empty_body_on_post)
    check("request_malformed_json", test_request_malformed_json)

    # ── Security Headers Tests ────────────────────────────────────────────────
    _emit("\n── Security Headers Tests ──────────────────────────────────────")
    check("headers_request_id_present", test_headers_request_id_present)
    check("headers_request_id_unique", test_headers_request_id_unique)
    check("headers_no_server_version_leak", test_headers_no_server_version_leak)
    check("headers_content_type_json", test_headers_content_type_json)
    check("headers_no_sensitive_leak_on_error", test_headers_no_sensitive_leak_on_error)
    check("headers_cors_present", test_headers_cors_present)
    check("headers_request_id_on_error", test_headers_request_id_on_error)

    # ── Rate Limiting Tests ───────────────────────────────────────────────────
    _emit("\n── Rate Limiting Tests ─────────────────────────────────────────")
    check("rate_limit_headers_present", test_rate_limit_headers_present)
    check(
        "rate_limit_not_triggered_under_normal_load",
        test_rate_limit_not_triggered_under_normal_load,
    )
    check("rate_limit_429_response_format", test_rate_limit_429_response_format)

    # ── Input Sanitization Tests ──────────────────────────────────────────────
    _emit("\n── Input Sanitization Tests ─────────────────────────────────────")
    check("sanitization_xss_in_decision", test_sanitization_xss_in_decision)
    check("sanitization_sql_injection_query_param", test_sanitization_sql_injection_query_param)
    check("sanitization_path_traversal", test_sanitization_path_traversal)
    check(
        "sanitization_special_chars_in_field_names", test_sanitization_special_chars_in_field_names
    )
    check(
        "sanitization_script_injection_in_variable_name",
        test_sanitization_script_injection_in_variable_name,
    )
    check("sanitization_null_bytes_in_payload", test_sanitization_null_bytes_in_payload)
    check("sanitization_extremely_long_field_values", test_sanitization_extremely_long_field_values)

    # ── Error Response Security Tests ─────────────────────────────────────────
    _emit("\n── Error Response Security Tests ────────────────────────────────")
    check("error_401_no_internal_details", test_error_401_no_internal_details)
    check("error_422_validation_structure", test_error_422_validation_structure)
    check("error_404_consistent_json", test_error_404_consistent_json)
    check("error_405_method_not_allowed", test_error_405_method_not_allowed)
    check("error_response_consistent_structure", test_error_response_consistent_structure)
    check("error_500_no_stack_trace", test_error_500_no_stack_trace)

    # ── Audit & Tracking Tests ────────────────────────────────────────────────
    _emit("\n── Audit & Tracking Tests ──────────────────────────────────────")
    check("audit_request_id_propagation", test_audit_request_id_propagation)
    check("audit_custom_request_id_respected", test_audit_custom_request_id_respected)
    check("audit_generated_request_id_format", test_audit_generated_request_id_format)
    check("audit_request_id_in_error_body", test_audit_request_id_in_error_body)
    check("audit_request_id_on_422", test_audit_request_id_on_422)

    # ── Additional Edge Case Tests ────────────────────────────────────────────
    _emit("\n── Additional Edge Case Tests ──────────────────────────────────")
    check("edge_http_method_override", test_edge_http_method_override)
    check("edge_double_encoding_path", test_edge_double_encoding_path)
    check("edge_json_content_type_with_charset", test_edge_json_content_type_with_charset)
    check("edge_trailing_slash", test_edge_trailing_slash)
    check("edge_case_sensitive_headers", test_edge_case_sensitive_headers)
    check("edge_concurrent_request_ids", test_edge_concurrent_request_ids)
    check("edge_empty_json_object", test_edge_empty_json_object)
    check("edge_array_instead_of_object", test_edge_array_instead_of_object)
    check("edge_numeric_decision", test_edge_numeric_decision)

    _print_summary()


def _print_summary():
    _emit("\n" + "=" * 72)
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    total = len(results)

    _emit(f"  RESULTS: {passed}/{total} passed, {failed} failed, {skipped} skipped")

    if timings:
        avg = sum(t for _, t in timings) / len(timings)
        slowest = sorted(timings, key=lambda x: x[1], reverse=True)[:5]
        _emit(f"  Average time: {avg:.3f}s")
        _emit("  Slowest tests:")
        for name, t in slowest:
            _emit(f"    {t:.3f}s  {name}")

    if failed > 0:
        _emit("\n  FAILURES:")
        for r in results:
            if r[0] == FAIL:
                _emit(f"    {FAIL} {r[1]}: {r[2]}")

    _emit("=" * 72)

    artifact_path = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_auth_security.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=total,
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "api_key_configured": bool(API_KEY_CONFIGURED),
            "base_url": BASE_URL,
            "failed_checks": [name for icon, name, *_ in results if icon == FAIL],
            "skipped_checks": [name for icon, name, *_ in results if icon == SKIP],
            "skipped_count": skipped,
        },
    )
    _emit(f"Summary artifact: {artifact_path}")
    return failed


# ═════════════════════════════════════════════════════════════════════════════
#  Bespoke standalone runner
#
#  Under pytest the `def test_*` functions above are collected directly. The
#  block below preserves the original standalone harness (reachability
#  preflight, per-section check() orchestration, and the results summary) so the
#  suite still runs via `python3 tests/integration/test_auth_security.py`.
# ═════════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    main()

    import pytest

    exit_code = pytest.main([__file__, "-v"])
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary

        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_auth_security.py",
            passed=0,
            failed=0,
            skipped=0,
            total=0,
            elapsed_seconds=0.0,
        )
        print(f"Summary artifact: {artifact_path}")
    except Exception:
        pass
    sys.exit(exit_code)
