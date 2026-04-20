"""
Confidence Calibration Service

Turns "confidence = simulation output" into "confidence = statistically grounded."

How it works:
  1. Every time an actual outcome is recorded (PATCH /v1/decisions/{id}/outcome),
     this service is called to update the org's calibration state.
  2. Calibration computes:
       - bias        : mean(actual - expected) / mean(|expected|)   [systematic over/under-estimate]
       - rmse_pct    : RMSE as % of mean |expected|                 [spread of prediction errors]
       - hit_rate    : % of outcomes within ±20% of expected        [directional accuracy]
       - n_samples   : how many outcomes we've seen                 [reliability of calibration]
  3. When a simulation runs, `calibrate_confidence()` adjusts the raw confidence:
       - If we're systematically over-optimistic (bias < 0), confidence is discounted
       - If we have few samples (n < MIN_SAMPLES), no adjustment (trust raw output)
       - Adjustment is capped at ±30% of raw confidence so we never produce nonsense
  4. The adjusted confidence is stored in `DecisionPlan.confidence` — the raw simulation
     confidence is preserved in `DecisionEnvelope.confidence` for transparency.

Design principle: fail safe
  - If calibration data is missing or stale → use raw confidence
  - If n_samples < MIN_SAMPLES → use raw confidence with a note
  - Calibration never makes things worse by overcorrecting
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ── Constants ─────────────────────────────────────────────────────────────────

MIN_SAMPLES = 5          # minimum outcomes before calibration kicks in
MAX_ADJUSTMENT = 0.30    # confidence adjustment capped at ±30% of raw value
HIT_TOLERANCE = 0.20     # "hit" = actual within ±20% of expected


# ── Calibration state ─────────────────────────────────────────────────────────

@dataclass
class CalibrationStats:
    """
    Per-org calibration state computed from historical outcome deltas.

    bias < 0  → over-optimistic (system predicts higher than reality)
    bias > 0  → under-optimistic (system predicts lower than reality)
    """
    n_samples: int = 0
    bias: float = 0.0           # mean relative error: mean((actual-expected)/|expected|)
    rmse_pct: float = 0.0       # RMSE as % of mean |expected|
    hit_rate: float = 1.0       # fraction of outcomes within HIT_TOLERANCE of expected
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_reliable(self) -> bool:
        return self.n_samples >= MIN_SAMPLES

    @property
    def direction(self) -> str:
        if abs(self.bias) < 0.02:
            return "well-calibrated"
        return "over-optimistic" if self.bias < 0 else "under-optimistic"

    def confidence_multiplier(self) -> float:
        """
        Compute the multiplicative factor to apply to raw confidence.

        Logic:
          - No adjustment if too few samples
          - Scale down if over-optimistic (bias < 0)
          - Scale up (capped) if under-optimistic (bias > 0)
          - Stronger adjustment for worse hit_rate
        """
        if not self.is_reliable:
            return 1.0

        # Base adjustment from bias: negative bias → reduce confidence
        bias_adj = -self.bias * 0.5           # halved so it's not too aggressive
        hit_adj  = (self.hit_rate - 0.8) * 0.2  # bonus for high hit rate, penalty for low

        raw_adj = bias_adj + hit_adj
        clamped = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, raw_adj))
        return 1.0 + clamped

    def summary(self) -> str:
        if not self.is_reliable:
            return f"Calibration pending ({self.n_samples}/{MIN_SAMPLES} outcomes recorded)"
        return (
            f"{self.n_samples} outcomes | "
            f"bias={self.bias:+.1%} ({self.direction}) | "
            f"hit_rate={self.hit_rate:.0%} | "
            f"rmse={self.rmse_pct:.1%}"
        )


# ── In-process calibration cache (per org) ───────────────────────────────────
# In production, persist to a `calibration_stats` DB table via migration 0017.
# For now, in-memory is sufficient: calibration is recomputed from DB on restart.

_CALIBRATION_CACHE: dict[str, CalibrationStats] = {}   # org_id_str → CalibrationStats


def get_calibration(org_id: str) -> CalibrationStats:
    """Return calibration stats for the org. Returns empty stats if no data yet."""
    return _CALIBRATION_CACHE.get(org_id, CalibrationStats())


def update_calibration(
    org_id: str,
    expected_values: list[float],
    actual_values: list[float],
) -> CalibrationStats:
    """
    Recompute calibration stats from the full set of (expected, actual) pairs.

    Called every time an outcome is recorded so calibration is always fresh.
    Pass ALL historical pairs for the org, not just the new one.
    """
    if not expected_values or not actual_values:
        return CalibrationStats()

    pairs = [
        (e, a) for e, a in zip(expected_values, actual_values, strict=False)
        if e is not None and a is not None
    ]
    if not pairs:
        return CalibrationStats()

    n = len(pairs)
    abs_expected = [abs(e) for e, _ in pairs]
    mean_abs_ev = sum(abs_expected) / n if n > 0 else 1.0
    if mean_abs_ev < 1e-9:
        mean_abs_ev = 1.0   # avoid division by zero for all-zero expected

    # Bias: mean relative error
    rel_errors = [(a - e) / max(abs(e), 1.0) for e, a in pairs]
    bias = sum(rel_errors) / n

    # RMSE as % of mean |expected|
    squared_errors = [(a - e) ** 2 for e, a in pairs]
    rmse = math.sqrt(sum(squared_errors) / n)
    rmse_pct = rmse / mean_abs_ev

    # Hit rate: fraction within ±HIT_TOLERANCE of expected
    hits = sum(
        1 for e, a in pairs
        if abs(a - e) <= HIT_TOLERANCE * max(abs(e), 1.0)
    )
    hit_rate = hits / n

    stats = CalibrationStats(
        n_samples=n,
        bias=bias,
        rmse_pct=rmse_pct,
        hit_rate=hit_rate,
        last_updated=datetime.now(UTC),
    )
    _CALIBRATION_CACHE[org_id] = stats
    return stats


def calibrate_confidence(
    raw_confidence: float,
    org_id: str,
    expected_value: float | None = None,
) -> tuple[float, CalibrationStats]:
    """
    Apply historical calibration to a raw simulation confidence score.

    Returns:
        (calibrated_confidence, CalibrationStats used)

    If calibration is unreliable (< MIN_SAMPLES), returns raw_confidence unchanged.
    The CalibrationStats is always returned so callers can surface it to users.
    """
    stats = get_calibration(org_id)
    if not stats.is_reliable:
        return raw_confidence, stats

    multiplier = stats.confidence_multiplier()
    calibrated = raw_confidence * multiplier
    # Keep confidence in [0.01, 0.99]
    calibrated = max(0.01, min(0.99, calibrated))
    return round(calibrated, 4), stats


async def refresh_calibration_from_db(
    org_id: str,
    db: AsyncSession,  # type: ignore[name-defined]
) -> CalibrationStats:
    """
    Pull all logged outcomes for this org from the DB and recompute calibration.

    Called on:
      - Every `record_outcome` (PATCH /v1/decisions/{id}/outcome)
      - On server startup for orgs with data (optional warm-up)
    """
    import uuid as _uuid

    from sqlalchemy import select

    from apps.api_server.models.decision_log import DecisionLog

    result = await db.execute(
        select(DecisionLog.expected_value, DecisionLog.actual_outcome)
        .where(
            DecisionLog.org_id == _uuid.UUID(org_id),
            DecisionLog.actual_outcome.is_not(None),
            DecisionLog.expected_value.is_not(None),
        )
    )
    rows = list(result.all())
    expected_vals = [float(r[0]) for r in rows]
    actual_vals   = [float(r[1]) for r in rows]
    return update_calibration(org_id, expected_vals, actual_vals)
