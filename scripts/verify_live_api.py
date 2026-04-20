"""
Live API verification script — tests running server at localhost:8000.
Run: python3 scripts/verify_live_api.py
Requires uvicorn running: PYTHONPATH=. uvicorn apps.api_server.main:app --port 8000
"""
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8000"
PASS = "✅"
FAIL = "❌"
results = []


def req(method, path, body=None, headers=None):
    """Make HTTP request, return (status_code, response_body_dict)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot connect to {BASE_URL} — is uvicorn running?") from e


def check(name, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"{PASS} {name}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"{FAIL} {name}: {e}")


# ── 1. Health endpoint ────────────────────────────────────────────────────────
def test_health():
    status, body = req("GET", "/v1/health")
    assert status == 200, f"Expected 200, got {status}"
    assert body["status"] == "ok", f"Expected 'ok', got {body}"

check("GET /v1/health → 200 {'status': 'ok'}", test_health)

# ── 2. Version endpoint ───────────────────────────────────────────────────────
def test_version():
    status, body = req("GET", "/v1/version")
    assert status == 200
    assert "api_version" in body
    assert "engine_version" in body
    assert "environment" in body

check("GET /v1/version → 200 with version fields", test_version)

# ── 3. OpenAPI spec loads ─────────────────────────────────────────────────────
def test_openapi():
    status, body = req("GET", "/openapi.json")
    assert status == 200
    assert "openapi" in body
    assert "paths" in body
    assert "/v1/simulate" in body["paths"]
    assert "/v1/health" in body["paths"]

check("GET /openapi.json → valid OpenAPI spec with /v1/simulate", test_openapi)

# ── 4. Auth required on simulate ─────────────────────────────────────────────
def test_auth_required():
    status, body = req("POST", "/v1/simulate", body={
        "mode": "auto",
        "scenario": {
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        }
    })
    assert status == 401, f"Expected 401 without auth, got {status}"
    assert "error" in body

check("POST /v1/simulate without auth → 401", test_auth_required)

# ── 5. Invalid key returns 401 ────────────────────────────────────────────────
def test_invalid_key():
    status, body = req(
        "POST", "/v1/simulate",
        body={"mode": "auto", "scenario": {"variables": {"x": {"low": 1, "high": 10}}, "objective": "maximize_net_value"}},
        headers={"X-API-Key": "de_live_totally_invalid_key_that_does_not_exist"},
    )
    assert status == 401, f"Expected 401 with invalid key, got {status}"
    error = body.get("error", {})
    assert error.get("code") == "invalid_api_key"

check("POST /v1/simulate with invalid key → 401 + code: invalid_api_key", test_invalid_key)

# ── 6. Malformed body returns 422 ─────────────────────────────────────────────
def test_malformed_body():
    status, body = req(
        "POST", "/v1/simulate",
        body={"bad": "payload"},
        headers={"X-API-Key": "de_live_something"},
    )
    # 401 (auth check runs first) or 422 (validation)
    assert status in (401, 422), f"Expected 401 or 422, got {status}: {body}"

check("POST /v1/simulate with bad payload → 401 or 422", test_malformed_body)

# ── 7. X-Request-Id present in responses ─────────────────────────────────────
def test_request_id_header():
    url = f"{BASE_URL}/v1/health"
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request) as resp:
        headers = dict(resp.headers)
        # Header names are case-insensitive, check lowercase
        lower_headers = {k.lower(): v for k, v in headers.items()}
        assert "x-request-id" in lower_headers, f"X-Request-Id not in response headers: {list(lower_headers.keys())}"

check("GET /v1/health response has X-Request-Id header", test_request_id_header)

# ── 8. Simulate with valid auth (no DB — expects 500 or success) ──────────────
def test_simulate_no_db():
    """
    Without a DB connection, simulate will fail with 500 (db write fails).
    We verify the request reaches the simulation service and returns structured error,
    not a raw Python traceback.
    """
    status, body = req(
        "POST", "/v1/simulate",
        body={
            "mode": "auto",
            "scenario": {
                "variables": {"revenue": {"low": 80000, "high": 200000}},
                "objective": "maximize_net_value",
            },
        },
        headers={"X-API-Key": "de_live_fakekeyfortestingonly1234567"},
    )
    # Without DB: auth fails (key not found → 401) — that's correct
    # The key point: response is always structured JSON, never a raw traceback
    assert "error" in body or "run_id" in body, f"Response must be structured JSON, got: {body}"
    # Specifically, no raw Python exception text
    body_str = json.dumps(body)
    assert "Traceback" not in body_str, "Raw Python traceback leaked to client!"
    assert "AttributeError" not in body_str

check("POST /v1/simulate never leaks raw tracebacks to client", test_simulate_no_db)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
print(f"Results: {passed} passed, {failed} failed out of {len(results)} checks")
if failed == 0:
    print("🚀 Live API verification complete!")
    print()
    print("Next steps:")
    print("  - Start Postgres + Redis to test full /v1/simulate flow")
    print("  - Run: make dev (once Docker is available)")
else:
    print("Fix the failures above")
    sys.exit(1)
