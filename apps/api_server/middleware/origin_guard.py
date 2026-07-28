"""Origin guard — reject requests that did not arrive through Cloudflare.

WHY THIS EXISTS
---------------
Every Cloudflare edge control we rely on (per-IP rate limits on device registration and license
minting, Full (Strict) origin validation, cache policy, the managed WAF ruleset) is bound to a
PROXIED HOSTNAME. The Fly apps also answer on their own public ``*.fly.dev`` names, which do not
traverse Cloudflare at all — so every one of those controls is optional for anyone who types the
origin hostname instead. Measured 2026-07-28:

    40 × POST https://api.telys.ai/v1/device/register              -> 429 from request 31 (limited)
    40 × POST https://algenta-control-plane.fly.dev/v1/device/...  -> 40 × 401, ZERO blocking
    GET  https://api.algenta.ai/metrics                            -> 403
    GET  https://algenta-control-plane.fly.dev/metrics             -> 200, 3662 bytes

The edge rules were not wrong; they were just skippable. This middleware makes "arrived via our
Cloudflare zone" a property the origin can actually check, by requiring a shared secret that only
the Cloudflare Transform Rule injects.

WHY A SHARED HEADER AND NOT mTLS
--------------------------------
Cloudflare Authenticated Origin Pulls is the canonical answer, but Fly terminates TLS at its own
proxy and does not surface the client certificate to the app, so the origin cannot verify it. An
IP allowlist is the other option and is worse: Cloudflare's ranges change, and behind Fly's proxy
the only client-IP signal is a forwardable header. A secret header is the mechanism Cloudflare
itself recommends when mTLS is unavailable.

FAILURE MODES THIS IS BUILT TO AVOID
------------------------------------
* Fly health checks hit ``GET /v1/health`` on the internal port every 15s and NEVER traverse
  Cloudflare. Guarding that path would fail health checks, roll the deploy back, and take the app
  down. ``_EXEMPT_PATHS`` therefore always allows the liveness/readiness probes.
* A misconfigured rollout could 403 all production traffic. Hence three modes and an off default:
  the middleware is INERT unless ``ORIGIN_GUARD_MODE`` is explicitly set, and ``log`` lets you
  confirm the header is arriving on real traffic BEFORE anything is rejected.

ROLLOUT (do not skip the log stage)
-----------------------------------
1. Generate a secret and set it on the app *and* in the Cloudflare Transform Rule:
       fly secrets set -a algenta-control-plane ORIGIN_SHARED_SECRET="$(openssl rand -hex 32)"
   The Cloudflare side lives in infra/cloudflare/telys/origin-guard.tf.
2. Deploy with ``ORIGIN_GUARD_MODE=log``. Watch logs for ``origin_guard.missing_header`` — a
   steady stream means the Transform Rule is not applying and you must NOT proceed.
3. When the only unguarded hits are from the ``*.fly.dev`` name, set ``ORIGIN_GUARD_MODE=enforce``.
4. Verify: ``api.telys.ai/v1/health`` 200 and ``algenta-control-plane.fly.dev/v1/device/register``
   403 with ``origin_guard_required``.

Rollback is a single ``fly secrets set ORIGIN_GUARD_MODE=log`` (or unset) — no redeploy of code.
"""

from __future__ import annotations

import hmac

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

#: Header the Cloudflare Transform Rule injects. Non-standard prefix so it cannot collide with a
#: header a client might legitimately send for another purpose.
ORIGIN_HEADER = "X-Origin-Auth"

#: Paths that must answer WITHOUT the header, because they are called off-Cloudflare by design.
#: Fly's health check is the load-bearing one: it runs against the machine's internal port, so if
#: it ever 403s the platform rolls the deploy back and the app goes down.
_EXEMPT_PATHS = frozenset({"/v1/health", "/v1/health/ready"})

MODE_OFF = "off"
MODE_LOG = "log"
MODE_ENFORCE = "enforce"
_VALID_MODES = frozenset({MODE_OFF, MODE_LOG, MODE_ENFORCE})


class OriginGuardMiddleware(BaseHTTPMiddleware):
    """Require the Cloudflare-injected shared secret on non-exempt requests.

    Inert unless BOTH a secret and a non-``off`` mode are configured, so adding this to the
    middleware stack is a no-op until someone deliberately turns it on.
    """

    def __init__(self, app: object, *, secret: str | None, mode: str = MODE_OFF) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._secret = (secret or "").strip()
        normalized = (mode or MODE_OFF).strip().lower()
        if normalized not in _VALID_MODES:
            # Never fail closed on a typo — an unrecognised mode silently disables the guard
            # rather than rejecting production traffic.
            logger.warning("origin_guard.invalid_mode", mode=mode, falling_back_to=MODE_OFF)
            normalized = MODE_OFF
        self._mode = normalized
        if self._mode != MODE_OFF and not self._secret:
            logger.warning(
                "origin_guard.no_secret_configured",
                mode=self._mode,
                detail="ORIGIN_GUARD_MODE set but ORIGIN_SHARED_SECRET empty; guard disabled",
            )
            self._mode = MODE_OFF
        self._active = self._mode != MODE_OFF
        if self._active:
            logger.info("origin_guard.enabled", mode=self._mode)

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if not self._active or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)  # type: ignore[operator]

        supplied = request.headers.get(ORIGIN_HEADER, "")
        # compare_digest, not ==, so a wrong-but-close header cannot be recovered by timing.
        if supplied and hmac.compare_digest(supplied, self._secret):
            return await call_next(request)  # type: ignore[operator]

        logger.warning(
            "origin_guard.missing_header" if not supplied else "origin_guard.bad_header",
            path=request.url.path,
            method=request.method,
            host=request.headers.get("host"),
            mode=self._mode,
            # cf-ray is present iff the request actually came through Cloudflare; its absence
            # alongside a missing header is the signature of a direct-to-origin request.
            cf_ray=request.headers.get("cf-ray"),
        )

        if self._mode == MODE_LOG:
            return await call_next(request)  # type: ignore[operator]

        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "origin_guard_required",
                    "message": (
                        "This API must be reached through its public hostname, not the origin "
                        "directly."
                    ),
                }
            },
        )
