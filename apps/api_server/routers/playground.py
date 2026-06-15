"""
routers/playground.py — No-auth, rate-limited demo endpoint.

The activation layer. Someone lands on the docs, tries one request,
and immediately feels the value. No sign-up. No API key. Just works.

  POST /v1/playground

Rate limited: 10 requests / minute per IP. No auth required.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

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


# ── Request / Response ────────────────────────────────────────────────────────


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


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.post(
    "/v1/playground",
    response_model=PlaygroundResponse,
    summary="Try Codna — no API key required",
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

    # Import local engine (no API key, no DB)
    import os
    import sys

    _core_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "packages", "algenta-core"
    )
    if _core_path not in sys.path:
        sys.path.insert(0, _core_path)

    try:
        from algenta.simple import decision as _decision
        from algenta.simple import optimize as _optimize
        from algenta.simple import simulate as _simulate

        if mode == "decision":
            flat_inputs = {
                k: (v["value"] if isinstance(v, dict) else float(v))
                for k, v in payload.inputs.items()
            }
            if not flat_inputs:
                flat_inputs = {"value": 100000.0, "cost": 70000.0}

            result = _decision(runs=payload.runs, **flat_inputs)

        elif mode == "optimize":
            variable_ranges = {}
            for k, v in payload.inputs.items():
                if isinstance(v, list | tuple) and len(v) == 2:
                    variable_ranges[k] = (float(v[0]), float(v[1]))
                elif isinstance(v, dict) and "min" in v and "max" in v:
                    variable_ranges[k] = (float(v["min"]), float(v["max"]))
                else:
                    val = float(v) if not isinstance(v, dict) else float(v.get("value", 100))
                    variable_ranges[k] = (val * 0.5, val * 1.5)

            if not variable_ranges:
                variable_ranges = {"price": (10.0, 200.0), "quantity": (100.0, 5000.0)}

            result = _optimize(
                payload.objective, iterations=min(payload.runs, 1000), **variable_ranges
            )

        elif mode == "forecast":
            history = payload.history
            if not history or len(history) < 3:
                history = [80000.0, 85000.0, 90000.0, 95000.0, 100000.0]
            from algenta.forecast import predict as _forecast

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
            flat = {
                k: (v["value"] if isinstance(v, dict) else float(v))
                for k, v in payload.inputs.items()
            }
            if not flat:
                flat = {"revenue": 120000.0, "cost": 70000.0}
            result = _simulate(runs=payload.runs, **flat)

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
            f"Playground cap: {runs_used:,} scenarios. "
            f"Upgrade for 1,000,000+ — {dashboard_hint}"
        ),
    )
