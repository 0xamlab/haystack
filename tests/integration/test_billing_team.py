"""
test_billing_team.py — Coverage for billing portal/webhook + team role/delete endpoints.

Missing endpoints from existing test suite:
  POST /v1/billing/portal
  POST /v1/billing/webhook
  PATCH /v1/team/{user_id}/role
  DELETE /v1/team/{user_id}

Two layers:
  Layer A — router/schema imports (no server)
  Layer B — live HTTP (requires running API server)

Run:
  DE_SKIP_API=1 python3 tests/integration/test_billing_team.py
  python3 tests/integration/test_billing_team.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY  = os.environ.get("DE_API_KEY",  "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))


def req(method: str, path: str, body: dict | None = None, auth: bool = True,
        extra_headers: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["X-API-Key"] = API_KEY
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            b = json.loads(e.read())
        except Exception:
            b = {}
        return e.code, b


# ── Layer A: Router structure ─────────────────────────────────────────────────

def test_billing_router_importable():
    from apps.api_server.routers import billing
    routes = {r.path for r in billing.router.routes}
    check("billing router importable", True)
    check("/v1/billing/checkout registered",  "/v1/billing/checkout" in routes)
    check("/v1/billing/portal registered",    "/v1/billing/portal"   in routes)
    check("/v1/billing/info registered",      "/v1/billing/info"     in routes)
    check("/v1/billing/webhook registered",   "/v1/billing/webhook"  in routes)


def test_team_router_importable():
    from apps.api_server.routers import team
    routes = {r.path for r in team.router.routes}
    check("team router importable", True)
    check("/v1/team registered",              "/v1/team"                      in routes)
    check("/v1/team/invite registered",       "/v1/team/invite"               in routes)
    check("/v1/team/{user_id}/role registered", "/v1/team/{user_id}/role"     in routes)
    check("/v1/team/{user_id} DELETE registered", any(
        r.path == "/v1/team/{user_id}" and "DELETE" in r.methods
        for r in team.router.routes
    ))


# ── Layer B: Billing portal ───────────────────────────────────────────────────

def test_billing_portal_returns_url_or_error():
    """POST /v1/billing/portal — creates Stripe portal session or returns expected error."""
    status, body = req("POST", "/v1/billing/portal", {})
    check(
        "POST /v1/billing/portal → 200, 402, or 422",
        status in (200, 402, 422, 400),
        f"got {status}: {str(body)[:100]}",
    )
    if status == 200:
        check("billing/portal returns url", "url" in body or "portal_url" in body, str(body))


def test_billing_portal_no_auth_401():
    status, body = req("POST", "/v1/billing/portal", {}, auth=False)
    check("billing/portal without auth → 401 or 403", status in (401, 403), f"got {status}")


def test_billing_webhook_bad_signature_400():
    """POST /v1/billing/webhook — should reject invalid Stripe signatures."""
    status, body = req(
        "POST", "/v1/billing/webhook",
        body={"type": "checkout.session.completed", "data": {}},
        auth=False,
        extra_headers={"Stripe-Signature": "invalid-signature"},
    )
    check(
        "billing/webhook bad signature → 400 or 422",
        status in (400, 422),
        f"got {status}: {str(body)[:100]}",
    )


def test_billing_webhook_no_signature_400():
    """POST /v1/billing/webhook — no signature header."""
    status, body = req("POST", "/v1/billing/webhook", {"type": "test"}, auth=False)
    check(
        "billing/webhook no signature → 400 or 422",
        status in (400, 422),
        f"got {status}",
    )


def test_billing_webhook_is_public():
    """Billing webhook must NOT require API key auth (Stripe calls it)."""
    status, _ = req("POST", "/v1/billing/webhook", {}, auth=False)
    # Should not be 401/403 — it's rejected for other reasons (bad sig)
    check(
        "billing/webhook is publicly accessible (not 401/403)",
        status not in (401, 403),
        f"got {status}",
    )


# ── Layer B: Team role + delete ───────────────────────────────────────────────

def test_team_role_update_invalid_user():
    fake_id = str(uuid.uuid4())
    status, body = req("PATCH", f"/v1/team/{fake_id}/role", {"role": "viewer"})
    check(
        "PATCH /v1/team/{fake_id}/role → 404 or 422",
        status in (404, 422, 400),
        f"got {status}: {str(body)[:100]}",
    )


def test_team_role_update_invalid_role():
    fake_id = str(uuid.uuid4())
    status, body = req("PATCH", f"/v1/team/{fake_id}/role", {"role": "superadmin"})
    check(
        "PATCH role with invalid role → 422 or 404",
        status in (422, 404, 400),
        f"got {status}",
    )


def test_team_role_update_missing_body():
    fake_id = str(uuid.uuid4())
    status, body = req("PATCH", f"/v1/team/{fake_id}/role", {})
    check(
        "PATCH role with empty body → 422",
        status == 422,
        f"got {status}",
    )


def test_team_delete_invalid_user():
    fake_id = str(uuid.uuid4())
    status, body = req("DELETE", f"/v1/team/{fake_id}", None)
    check(
        "DELETE /v1/team/{fake_id} → 404 or 422",
        status in (404, 422, 400),
        f"got {status}: {str(body)[:100]}",
    )


def test_team_delete_no_auth():
    fake_id = str(uuid.uuid4())
    status, body = req("DELETE", f"/v1/team/{fake_id}", None, auth=False)
    check(
        "DELETE /v1/team/{id} without auth → 401 or 403",
        status in (401, 403),
        f"got {status}",
    )


def test_team_role_update_no_auth():
    fake_id = str(uuid.uuid4())
    status, body = req("PATCH", f"/v1/team/{fake_id}/role", {"role": "viewer"}, auth=False)
    check(
        "PATCH /v1/team/{id}/role without auth → 401 or 403",
        status in (401, 403),
        f"got {status}",
    )


# ── Runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 68)
    print("  BILLING + TEAM ENDPOINT TESTS")
    print("=" * 68)

    print("\n── Layer A: Router structure (no server) ────────────────────────\n")
    for fn in [test_billing_router_importable, test_team_router_importable]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    print("\n── Layer B: Live HTTP ────────────────────────────────────────────\n")
    live = [
        test_billing_portal_returns_url_or_error,
        test_billing_portal_no_auth_401,
        test_billing_webhook_bad_signature_400,
        test_billing_webhook_no_signature_400,
        test_billing_webhook_is_public,
        test_team_role_update_invalid_user,
        test_team_role_update_invalid_role,
        test_team_role_update_missing_body,
        test_team_delete_invalid_user,
        test_team_delete_no_auth,
        test_team_role_update_no_auth,
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
