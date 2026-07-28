"""Origin guard middleware — the Cloudflare edge is only worth something if it cannot be skipped.

Context: the Fly apps answer on their public ``*.fly.dev`` names, which never traverse Cloudflare,
so every edge rate limit / WAF rule / Full-Strict setting is optional for anyone who uses the origin
hostname. Measured 2026-07-28: 40 POSTs to ``algenta-control-plane.fly.dev/v1/device/register``
returned 40 × 401 with ZERO rate limiting, while the same burst through ``api.telys.ai`` was blocked
with 429 from request 31.

Two properties here are load-bearing and must never regress:

  * DEFAULT OFF — shipping the middleware must not change behaviour until someone deliberately
    enables it. A guard that fails closed on deploy would take down the shared auth/billing plane.
  * HEALTH EXEMPT — Fly probes ``GET /v1/health`` on the internal port every 15s and never goes
    through Cloudflare. If that 403s, Fly rolls the deploy back and the app is down.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api_server.middleware.origin_guard import ORIGIN_HEADER, OriginGuardMiddleware

SECRET = "s3cret-shared-with-the-cloudflare-transform-rule"


def _app(*, secret: str | None, mode: str) -> TestClient:
    app = FastAPI()

    @app.get("/v1/health")
    async def health() -> dict[str, str]:  # Fly liveness probe — never via Cloudflare
        return {"status": "ok"}

    @app.get("/v1/health/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/v1/device/register")
    async def register() -> dict[str, str]:  # the surface the edge rate limit protects
        return {"registered": "yes"}

    @app.get("/metrics")
    async def metrics() -> str:
        return "telys_requests_total 1"

    app.add_middleware(OriginGuardMiddleware, secret=secret, mode=mode)
    return TestClient(app)


# ── default-off: shipping this must be a no-op ───────────────────────────────────────────────────

def test_disabled_by_default_even_with_a_secret_present() -> None:
    """Setting only the secret must NOT start rejecting traffic — mode is the deliberate switch."""
    c = _app(secret=SECRET, mode="off")
    assert c.post("/v1/device/register").status_code == 200


def test_disabled_when_mode_set_but_secret_missing() -> None:
    """A half-configured rollout must fail OPEN, not take production down."""
    for mode in ("log", "enforce"):
        c = _app(secret=None, mode=mode)
        assert c.post("/v1/device/register").status_code == 200, mode


def test_unrecognised_mode_disables_rather_than_rejects() -> None:
    """A typo in ORIGIN_GUARD_MODE must not 403 every request."""
    c = _app(secret=SECRET, mode="enfroce")  # deliberate typo
    assert c.post("/v1/device/register").status_code == 200


# ── health exemption: the deploy-breaking case ───────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/v1/health", "/v1/health/ready"])
def test_health_probes_never_require_the_header(path: str) -> None:
    """Fly probes the machine internally; guarding these rolls back every deploy."""
    c = _app(secret=SECRET, mode="enforce")
    assert c.get(path).status_code == 200


# ── enforce: the actual fix ──────────────────────────────────────────────────────────────────────

def test_enforce_rejects_a_request_that_skipped_cloudflare() -> None:
    c = _app(secret=SECRET, mode="enforce")
    r = c.post("/v1/device/register")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "origin_guard_required"


def test_enforce_allows_a_request_carrying_the_cloudflare_header() -> None:
    c = _app(secret=SECRET, mode="enforce")
    r = c.post("/v1/device/register", headers={ORIGIN_HEADER: SECRET})
    assert r.status_code == 200


def test_enforce_rejects_a_wrong_secret() -> None:
    c = _app(secret=SECRET, mode="enforce")
    assert c.post("/v1/device/register", headers={ORIGIN_HEADER: "wrong"}).status_code == 403


def test_metrics_is_covered_by_the_guard() -> None:
    """/metrics answered 200 on the origin while api.algenta.ai returned 403 — close that."""
    c = _app(secret=SECRET, mode="enforce")
    assert c.get("/metrics").status_code == 403
    assert c.get("/metrics", headers={ORIGIN_HEADER: SECRET}).status_code == 200


# ── log mode: prove the header arrives before rejecting anything ─────────────────────────────────

def test_log_mode_observes_without_blocking() -> None:
    """The rollout stage that makes 'enforce' safe: nothing is rejected, misses are logged."""
    c = _app(secret=SECRET, mode="log")
    assert c.post("/v1/device/register").status_code == 200
    assert c.post("/v1/device/register", headers={ORIGIN_HEADER: SECRET}).status_code == 200
