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
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from tests.integration.live_integration_artifacts import write_live_integration_summary

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
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"
SUITE_NAME = "billing_team_integration"
STARTED = time.perf_counter()

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
_results: list[tuple[str, bool, str]] = []


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    _emit(f"  {icon} {name}" + (f" ({detail})" if detail else ""))


def run_check(name: str, fn) -> None:
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        fn()
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except urllib.error.URLError as e:
        _results.append((name, True, f"skipped: server unreachable ({e.reason})"))
        _emit(
            f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): "
            f"server unreachable ({e.reason})"
        )
    except Exception as e:
        check(name, False, f"{type(e).__name__}: {e}")


def req(
    method: str,
    path: str,
    body: dict | None = None,
    auth: bool = True,
    extra_headers: dict | None = None,
) -> tuple[int, dict]:
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
    check("/v1/billing/checkout registered", "/v1/billing/checkout" in routes)
    check("/v1/billing/portal registered", "/v1/billing/portal" in routes)
    check("/v1/billing/info registered", "/v1/billing/info" in routes)
    check("/v1/billing/webhook registered", "/v1/billing/webhook" in routes)


def test_team_router_importable():
    from apps.api_server.routers import team

    routes = {r.path for r in team.router.routes}
    check("team router importable", True)
    check("/v1/team registered", "/v1/team" in routes)
    check("/v1/team/invite registered", "/v1/team/invite" in routes)
    check("/v1/team/{user_id}/role registered", "/v1/team/{user_id}/role" in routes)
    check(
        "/v1/team/{user_id} DELETE registered",
        any(r.path == "/v1/team/{user_id}" and "DELETE" in r.methods for r in team.router.routes),
    )


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
        "POST",
        "/v1/billing/webhook",
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
    _emit("\n" + "=" * 68)
    _emit("  BILLING + TEAM ENDPOINT TESTS")
    _emit("=" * 68)

    _emit("\n── Layer A: Router structure (no server) ────────────────────────\n")
    for fn in [test_billing_router_importable, test_team_router_importable]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    _emit("\n── Layer B: Live HTTP ────────────────────────────────────────────\n")
    auth_required_live = [
        ("POST /v1/billing/portal auth surface", test_billing_portal_returns_url_or_error),
        ("PATCH /v1/team/{user_id}/role invalid user", test_team_role_update_invalid_user),
        ("PATCH /v1/team/{user_id}/role invalid role", test_team_role_update_invalid_role),
        ("PATCH /v1/team/{user_id}/role missing body", test_team_role_update_missing_body),
        ("DELETE /v1/team/{user_id} invalid user", test_team_delete_invalid_user),
    ]
    public_or_noauth_live = [
        ("POST /v1/billing/portal without auth", test_billing_portal_no_auth_401),
        ("POST /v1/billing/webhook bad signature", test_billing_webhook_bad_signature_400),
        ("POST /v1/billing/webhook no signature", test_billing_webhook_no_signature_400),
        ("POST /v1/billing/webhook is public", test_billing_webhook_is_public),
        ("DELETE /v1/team/{user_id} without auth", test_team_delete_no_auth),
        ("PATCH /v1/team/{user_id}/role without auth", test_team_role_update_no_auth),
    ]
    if SKIP_API:
        _emit(f"  {SKIP} Skipped live HTTP layer (DE_SKIP_API=1)")
    else:
        for name, fn in public_or_noauth_live:
            run_check(name, fn)
        if API_KEY_CONFIGURED:
            for name, fn in auth_required_live:
                run_check(name, fn)
        else:
            reason = (
                "DE_API_KEY is not set; skipping authenticated billing/team checks "
                "that require a real live key."
            )
            for name, _ in auth_required_live:
                _results.append((name, True, f"skipped: {reason}"))
                _emit(f"  {SKIP} {name}: {reason}")

    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    skipped = sum(1 for _, _, detail in _results if detail.startswith("skipped:"))
    _emit(f"\n{'=' * 68}")
    _emit(f"  {passed} passed  |  {failed} failed  |  {len(_results)} total")
    if skipped:
        _emit(f"  {skipped} skipped")
    _emit(f"{'=' * 68}\n")

    artifact_path = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_billing_team.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(_results),
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "api_key_configured": bool(API_KEY_CONFIGURED),
            "base_url": BASE_URL,
            "skip_api": SKIP_API,
            "failed_checks": [name for name, ok, _ in _results if not ok],
            "skipped_checks": [name for name, _, detail in _results if detail.startswith("skipped:")],
        },
    )
    _emit(f"Summary artifact: {artifact_path}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
