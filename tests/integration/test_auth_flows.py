"""
test_auth_flows.py — Auth flow coverage: verify, forgot-password, reset-password.

Covers the 3 auth endpoints missing from test_auth_security.py:
  GET  /auth/verify
  POST /auth/forgot-password
  POST /auth/reset-password

Two layers:
  Layer A — route structure / schema validation (no server)
  Layer B — live HTTP (requires running API server)

Run:
  DE_SKIP_API=1 python3 tests/integration/test_auth_flows.py
  python3 tests/integration/test_auth_flows.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []

pytestmark = pytest.mark.usefixtures("legacy_live_api_server")


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))


def post(path: str, body: dict, auth: bool = False) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {}
        return e.code, body


def get(path: str) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {}
        return e.code, body


# ── Layer A: Route schema checks ─────────────────────────────────────────────

def test_auth_router_importable():
    from apps.api_server.routers import auth as auth_router
    check("auth router importable", True)
    routes = {r.path for r in auth_router.router.routes}
    check("/auth/verify route registered",           "/auth/verify" in routes)
    check("/auth/forgot-password route registered",  "/auth/forgot-password" in routes)
    check("/auth/reset-password route registered",   "/auth/reset-password" in routes)
    check("/auth/signup route registered",           "/auth/signup" in routes)
    check("/auth/login route registered",            "/auth/login" in routes)


def test_auth_schemas_importable():
    try:
        import importlib

        importlib.import_module("apps.api_server.schemas.auth")
        check("auth schemas importable", True)
    except ImportError as e:
        check("auth schemas importable", False, str(e))


# ── Layer B: Live HTTP ───────────────────────────────────────────────────────

def test_verify_missing_token_400_or_422():
    status, body = get("/auth/verify")
    check(
        "GET /auth/verify (no token) → 400 or 422",
        status in (400, 422),
        f"got {status}",
    )


def test_verify_invalid_token_400_or_404():
    status, body = get("/auth/verify?token=completely-invalid-token-xyz")
    check(
        "GET /auth/verify (bad token) → 400 or 404",
        status in (400, 404, 422),
        f"got {status}: {body}",
    )


def test_forgot_password_invalid_email():
    status, body = post("/auth/forgot-password", {"email": "not-an-email"})
    check(
        "POST /auth/forgot-password (bad email) → 422",
        status == 422,
        f"got {status}",
    )


def test_forgot_password_unknown_email():
    status, body = post("/auth/forgot-password", {"email": "nobody_xyz_1234@example.com"})
    # Should return 200 (don't leak whether email exists) or 404
    check(
        "POST /auth/forgot-password (unknown email) → 200 or 404",
        status in (200, 404),
        f"got {status}: {body}",
    )


def test_forgot_password_missing_body():
    status, body = post("/auth/forgot-password", {})
    check(
        "POST /auth/forgot-password (empty body) → 422",
        status == 422,
        f"got {status}",
    )


def test_reset_password_invalid_token():
    status, body = post("/auth/reset-password", {
        "token": "invalid-reset-token-xyz",
        "new_password": "NewSecurePass123!",
    })
    check(
        "POST /auth/reset-password (bad token) → 400 or 404",
        status in (400, 404, 422),
        f"got {status}: {body}",
    )


def test_reset_password_missing_fields():
    status, body = post("/auth/reset-password", {})
    check(
        "POST /auth/reset-password (empty body) → 422",
        status == 422,
        f"got {status}",
    )


def test_reset_password_weak_password():
    status, body = post("/auth/reset-password", {
        "token": "some-token",
        "new_password": "abc",  # too short
    })
    check(
        "POST /auth/reset-password (weak password) → 400 or 422",
        status in (400, 422),
        f"got {status}",
    )


def test_verify_response_structure():
    """Verify the response has correct structure (even on error)."""
    status, body = get("/auth/verify?token=test-token-structure-check")
    check(
        "GET /auth/verify returns JSON body",
        isinstance(body, dict),
        str(body)[:100],
    )


# ── Runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 68)
    print("  AUTH FLOW TESTS")
    print("=" * 68)

    print("\n── Layer A: Route structure (no server) ────────────────────────\n")
    for fn in [test_auth_router_importable, test_auth_schemas_importable]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    print("\n── Layer B: Live HTTP ───────────────────────────────────────────\n")
    live = [
        test_verify_missing_token_400_or_422,
        test_verify_invalid_token_400_or_404,
        test_forgot_password_invalid_email,
        test_forgot_password_unknown_email,
        test_forgot_password_missing_body,
        test_reset_password_invalid_token,
        test_reset_password_missing_fields,
        test_reset_password_weak_password,
        test_verify_response_structure,
    ]
    if SKIP_API:
        print(f"  {SKIP}  Skipped (DE_SKIP_API=1)")
    else:
        for fn in live:
            try:
                fn()
            except urllib.error.URLError as e:
                print(f"  {SKIP}  {fn.__name__} — server unreachable ({e.reason})")
            except Exception as e:
                check(fn.__name__, False, f"{type(e).__name__}: {e}")

    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n{'=' * 68}")
    print(f"  {passed} passed  |  {failed} failed  |  {len(_results)} total")
    print(f"{'=' * 68}\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
