"""
routers/playground.py — No-auth, rate-limited demo endpoint.

The activation layer. Someone lands on the docs, tries one request,
and immediately feels the value. No sign-up. No API key. Just works.

  POST /v1/playground

Rate limited: 10 requests / minute per IP. No auth required.

Failure contract (every body is the standard {"error": {code, message}} envelope):
  422 validation_error          — the body does not match PlaygroundRequest (FastAPI/Pydantic)
  422 playground_invalid_input  — a well-typed body whose `inputs` values the engine cannot model
  429 playground_rate_limit     — over 10 requests/minute from one IP
  503 playground_unavailable    — the algenta SDK is not importable in this deployment
  500 playground_error          — the engine itself raised
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from apps.api_server.services.public_url_policy import (
    request_origin_base_url,
    resolve_dashboard_url,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Playground"])

# In-memory IP rate limiting (resets on restart — fine for demo tier)
_ip_counts: dict[str, tuple[int, float]] = {}
_RATE_LIMIT = 10  # requests
_WINDOW_S = 60  # per minute


def _dashboard_upgrade_hint(request: Request) -> str:
    dashboard_url = resolve_dashboard_url(request_origin=request_origin_base_url(request))
    return f"{dashboard_url} — free tier: 500 simulations/month"


def _check_ip_rate(ip: str, *, upgrade_hint: str) -> None:
    now = time.monotonic()
    count, window_start = _ip_counts.get(ip, (0, now))
    if now - window_start > _WINDOW_S:
        count, window_start = 0, now
    count += 1
    _ip_counts[ip] = (count, window_start)
    if count > _RATE_LIMIT:
        remaining = int(_WINDOW_S - (now - window_start))
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "playground_rate_limit",
                    "message": (
                        f"Playground limit: {_RATE_LIMIT} requests/minute. Retry in {remaining}s."
                    ),
                    "upgrade": f"Get an API key at {upgrade_hint}",
                }
            },
        )


# ── SDK engine ────────────────────────────────────────────────────────────────

# The playground runs the public `algenta` SDK's decision / optimize / simulate / forecast paths
# in-process. Those paths are pure Python (stdlib math/random Monte Carlo): no API key, no DB, no
# Mojo worker, no network -- `mode="cloud"` is never passed, so algenta.privacy_profile is imported
# but its base-URL resolution never runs. The SDK is not pip-installed in this service; it lives in
# the monorepo at packages/algenta, and the API image copies that package to the same relative
# location (infra/docker/Dockerfile.api.prod), so that directory goes on sys.path first.
_SDK_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "algenta")
)


def _sdk_import(module: str, *names: str) -> tuple[Any, ...]:
    """Import ``names`` from an algenta SDK module, or raise 503 playground_unavailable.

    A missing SDK is a deployment defect -- neither a caller error nor an engine failure -- and
    it must be distinguishable as such. Until 2026-09-22 the production image shipped only
    runtime_library_contract.json under /app/packages/algenta/algenta; ``import algenta`` then
    resolved to that namespace-package shell and every playground call surfaced as an anonymous
    500 "No module named 'algenta.simple'". The image smoke
    (scripts/verify_api_image_mojo_server_mode.sh) now imports algenta.simple before any rollout.
    """
    if _SDK_PATH not in sys.path:
        sys.path.insert(0, _SDK_PATH)
    try:
        imported = __import__(module, fromlist=list(names))
        return tuple(getattr(imported, name) for name in names)
    except (ImportError, AttributeError) as exc:
        logger.error(
            "playground_sdk_unavailable", module=module, error=str(exc), sdk_path=_SDK_PATH
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "playground_unavailable",
                    "message": (
                        "The playground engine is not available in this deployment: the "
                        "algenta SDK could not be imported. Retry later, or use an API key "
                        "with /v1/simulate."
                    ),
                }
            },
        ) from exc


# ── Request / Response ────────────────────────────────────────────────────────

# Keyword parameters of algenta.simple.decision / optimize / simulate and algenta.decision.analyze.
# `inputs` are splatted into those calls as **kwargs, so a variable with one of these names either
# raised TypeError ("got multiple values for keyword argument 'runs'") -- a 500 -- or silently
# re-targeted the engine (mode=..., inputs=...) instead of being modelled. Reject them up front.
_RESERVED_INPUT_NAMES = frozenset(
    {
        "api_key",
        "base_url",
        "inputs",
        "iterations",
        "label",
        "mode",
        "objective",
        "risk_tolerance",
        "runs",
    }
)


class PlaygroundRequest(BaseModel):
    """
    Describe what you want to analyze. No statistics knowledge required.

    Modes:
      decision  → What should I do? Returns proceed/pause/reject + why
      optimize  → Find the best value. Returns optimal config + improvement
      simulate  → What's the range of outcomes? Returns distribution
      forecast  → What will happen? Returns future periods with CI

    Example:
      {
        "mode": "decision",
        "inputs": {"revenue": 120000, "cost": 70000},
        "runs": 1000
      }
    """

    mode: str = Field(
        "decision",
        description="What to run: decision, optimize, simulate, forecast",
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Your input variables as name → value (or name → {value, low, high})",
    )
    objective: str = Field(
        "maximize_value",
        description=(
            "What to optimize (for optimize mode): 'maximize profit', 'minimize cost', etc."
        ),
    )
    runs: int = Field(
        1000,
        ge=100,
        le=5000,
        description="Scenarios to evaluate (playground cap: 5,000 — upgrade for 1,000,000+)",
    )
    history: list[float] | None = Field(
        None,
        description="Historical values for forecast mode (most recent last, min 3)",
    )

    @field_validator("inputs")
    @classmethod
    def _reject_reserved_input_names(cls, inputs: dict[str, Any]) -> dict[str, Any]:
        reserved = sorted(name for name in inputs if name in _RESERVED_INPUT_NAMES)
        if reserved:
            raise ValueError(
                f"input name(s) {reserved} are reserved engine parameters; rename the variable(s)"
            )
        return inputs


class PlaygroundResponse(BaseModel):
    playground_id: str
    mode: str
    action: str
    value: float
    confidence: float
    why: list[str]
    details: dict[str, Any]
    latency_ms: float
    upgrade_hint: str


# ── Input coercion (422, not 500) ─────────────────────────────────────────────


def _invalid_input(name: str, value: Any, expected: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": "playground_invalid_input",
                "message": (
                    f"inputs[{name!r}] must be {expected}; got {type(value).__name__}: {value!r}"
                ),
            }
        },
    )


def _as_float(name: str, value: Any, raw: Any, expected: str) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise _invalid_input(name, value, expected) from exc


def _scalar_inputs(inputs: dict[str, Any]) -> dict[str, float]:
    """decision / simulate: name → number, or name → {"value": number, ...}."""
    expected = "a number or {value: number}"
    flat: dict[str, float] = {}
    for name, value in inputs.items():
        raw = value.get("value") if isinstance(value, dict) else value
        flat[name] = _as_float(name, value, raw, expected)
    return flat


def _range_inputs(inputs: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """optimize: name → [min, max], {"min", "max"}, or a point value widened to ±50%."""
    expected = "[min, max], {min: number, max: number}, a number, or {value: number}"
    ranges: dict[str, tuple[float, float]] = {}
    for name, value in inputs.items():
        if isinstance(value, list | tuple) and len(value) == 2:
            lo, hi = (_as_float(name, value, bound, expected) for bound in value)
        elif isinstance(value, dict) and "min" in value and "max" in value:
            lo = _as_float(name, value, value["min"], expected)
            hi = _as_float(name, value, value["max"], expected)
        else:
            raw = value.get("value", 100) if isinstance(value, dict) else value
            point = _as_float(name, value, raw, expected)
            lo, hi = point * 0.5, point * 1.5
        ranges[name] = (lo, hi)
    return ranges


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.post(
    "/v1/playground",
    response_model=PlaygroundResponse,
    summary="Try Algenta — no API key required",
    description=(
        "**No sign-up. No API key. Just try it.**\n\n"
        "Run a decision analysis, optimization, simulation, or forecast "
        "in one API call. Rate limited at 10 requests/minute per IP.\n\n"
        "Upgrade your configured dashboard for:\n"
        "- 500 simulations/month free\n"
        "- Up to 1,000,000 scenarios per request\n"
        "- All 12 engines\n"
    ),
)
async def playground(request: Request, payload: PlaygroundRequest) -> PlaygroundResponse:
    t0 = time.monotonic()

    # Rate limit by IP
    client_ip = request.client.host if request.client else "unknown"
    dashboard_hint = _dashboard_upgrade_hint(request)
    _check_ip_rate(client_ip, upgrade_hint=dashboard_hint)

    mode = payload.mode.lower()
    pg_id = str(uuid.uuid4())

    # Deployment defects (503) and caller mistakes (422) are named BEFORE the engine runs, so the
    # catch-all below only ever wraps a genuine engine exception.
    _decision, _optimize, _simulate = _sdk_import(
        "algenta.simple", "decision", "optimize", "simulate"
    )
    _forecast = _sdk_import("algenta.forecast", "predict")[0] if mode == "forecast" else None

    if mode == "optimize":
        variable_ranges = _range_inputs(payload.inputs) or {
            "price": (10.0, 200.0),
            "quantity": (100.0, 5000.0),
        }
    elif mode == "forecast":
        history = payload.history
        if not history or len(history) < 3:
            history = [80000.0, 85000.0, 90000.0, 95000.0, 100000.0]
    elif mode == "decision":
        flat_inputs = _scalar_inputs(payload.inputs) or {"value": 100000.0, "cost": 70000.0}
    else:  # simulate (default)
        flat_inputs = _scalar_inputs(payload.inputs) or {"revenue": 120000.0, "cost": 70000.0}

    try:
        if mode == "decision":
            result = _decision(runs=payload.runs, **flat_inputs)

        elif mode == "optimize":
            result = _optimize(
                payload.objective, iterations=min(payload.runs, 1000), **variable_ranges
            )

        elif mode == "forecast":
            fr = _forecast(history, horizon=6, metric="value")
            final = fr.periods[-1]
            result_val = fr.forecast_mean
            change = fr.total_change_pct
            trend = fr.periods[0].trend

            action_str = "growing" if change > 2 else ("declining" if change < -2 else "stable")
            return PlaygroundResponse(
                playground_id=pg_id,
                mode="forecast",
                action=action_str,
                value=round(result_val, 2),
                confidence=0.82,
                why=[
                    (
                        f"Trend: {trend} — {abs(change):.1f}% "
                        f"{'growth' if change > 0 else 'decline'} over 6 periods"
                    ),
                    f"Starting at {history[-1]:,.0f} → forecast {result_val:,.0f}",
                    f"Confidence interval at period 6: {final.lower:,.0f} – {final.upper:,.0f}",
                ],
                details={
                    "periods": [p.to_dict() for p in fr.periods],
                    "baseline": fr.baseline,
                    "total_change_pct": change,
                },
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                upgrade_hint=f"Get 1M+ scenario forecasts — {dashboard_hint}",
            )

        else:  # simulate (default)
            result = _simulate(runs=payload.runs, **flat_inputs)

    except Exception as exc:
        logger.warning("playground_error", mode=mode, error=str(exc), ip=client_ip)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "playground_error", "message": str(exc)}},
        ) from exc

    runs_used = payload.runs
    return PlaygroundResponse(
        playground_id=pg_id,
        mode=mode,
        action=result.action,
        value=result.value,
        confidence=result.confidence,
        why=result.why,
        details={
            **{k: v for k, v in result.details.items() if k != "label"},
            "scenarios_evaluated": runs_used,
        },
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
        upgrade_hint=(
            f"Playground cap: {runs_used:,} scenarios. Upgrade for 1,000,000+ — {dashboard_hint}"
        ),
    )
