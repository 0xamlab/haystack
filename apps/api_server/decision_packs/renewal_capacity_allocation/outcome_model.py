"""The lever→outcome response model for renewal capacity allocation.

This is the *domain product*: it maps a business lever (customer-success intervention
hours) to a business outcome (renewal probability). Generic simulation cannot do this;
the response curve is the net-new knowledge.

Honesty first:
  * The causal link is **confounded** — at-risk accounts historically get more attention,
    so naive correlation overstates effectiveness. Effectiveness is therefore an *explicit
    assumption* until calibrated against realized renewals.
  * The model is **deterministic and versioned** (:data:`MODEL_VERSION`). The LM never
    generates these numbers.
  * Inputs outside the model's validity range are **rejected** (:class:`DomainValidityError`)
    rather than silently extrapolated.

Baseline curve (health → baseline renewal probability): a smooth logistic-ish mapping of
the 0–100 health score into [0,1]. Uplift curve (hours → additional probability): a
saturating exponential with diminishing returns, so marginal value is monotonically
decreasing — which makes greedy marginal allocation optimal for the solver.
"""

from __future__ import annotations

import math

from .contract import InterventionAssumptions, Segment

__all__ = [
    "MODEL_VERSION",
    "MODEL_LIMITATIONS",
    "HEALTH_VALIDITY",
    "DomainValidityError",
    "baseline_probability_from_health",
    "estimated_probability",
    "marginal_uplift_arr",
]

MODEL_VERSION = "renewal_capacity_allocation.outcome_model@v0.1.0"

MODEL_LIMITATIONS = (
    "Effectiveness is an assumption, not a measured causal effect, unless calibration_status "
    "is 'calibrated'. The baseline curve maps a 0–100 health score to probability with a fixed "
    "shape and is not tenant-calibrated by default. Segment modifiers are priors. Do not present "
    "outputs as guaranteed retained ARR.",
)

# Validity range for the health score the baseline curve accepts.
HEALTH_VALIDITY = (0.0, 100.0)


class DomainValidityError(ValueError):
    """Raised when an input falls outside the model's declared validity range."""


def baseline_probability_from_health(health_score: float) -> float:
    """Map a 0–100 health score to a baseline renewal probability in [0,1].

    Fixed, documented shape: a logistic centered at health 50 with a spread that puts a
    health of 0 near ~0.15 and 100 near ~0.95. Deterministic and reproducible.
    """

    lo, hi = HEALTH_VALIDITY
    if not (lo <= health_score <= hi):
        raise DomainValidityError(
            f"health_score {health_score} outside validity range [{lo}, {hi}]"
        )
    # Logistic: center 50, slope chosen for a sensible spread across the range.
    k = 0.09
    raw = 1.0 / (1.0 + math.exp(-k * (health_score - 50.0)))
    # Rescale the logistic's [~0.011, ~0.989] envelope into a calibrated-ish [0.15, 0.95].
    lo_env = 1.0 / (1.0 + math.exp(-k * (0.0 - 50.0)))
    hi_env = 1.0 / (1.0 + math.exp(-k * (100.0 - 50.0)))
    scaled = (raw - lo_env) / (hi_env - lo_env)
    return 0.15 + scaled * (0.95 - 0.15)


def _uplift_fraction(hours: float, assumptions: InterventionAssumptions) -> float:
    """Fraction (0–1) of the achievable gap closed by ``hours`` — saturating, diminishing.

    ``1 - exp(-hours / tau)`` capped at ``max_useful_hours_per_account``. Concave and
    increasing in hours, so marginal value strictly decreases → greedy is optimal.
    """

    if hours <= 0:
        return 0.0
    usable = min(hours, assumptions.max_useful_hours_per_account)
    return 1.0 - math.exp(-usable / assumptions.saturation_hours)


def estimated_probability(
    *,
    baseline: float,
    hours: float,
    segment: Segment,
    assumptions: InterventionAssumptions,
) -> float:
    """Estimated renewal probability given baseline, allocated hours, and assumptions.

    ``baseline + min(uplift, headroom)`` where
    ``uplift = (1 - baseline) * effectiveness * segment_modifier * uplift_fraction(hours)`` and
    ``headroom = max(0, max_renewal_probability - baseline)``. The uplift (not the whole sum)
    is capped, so the result is **never below baseline** — intervention or zero hours can only
    hold or raise the renewal probability. With hours=0 this returns exactly ``baseline``.
    """

    if not (0.0 <= baseline <= 1.0):
        raise DomainValidityError(f"baseline probability {baseline} outside [0,1]")
    seg_mod = assumptions.segment_modifiers.get(segment, 1.0)
    if seg_mod < 0:
        raise DomainValidityError(f"segment_modifier {seg_mod} for {segment} is negative")
    gap = 1.0 - baseline
    headroom = max(0.0, assumptions.max_renewal_probability - baseline)
    uplift = gap * assumptions.effectiveness * seg_mod * _uplift_fraction(hours, assumptions)
    return baseline + min(uplift, headroom)


def marginal_uplift_arr(
    *,
    arr: float,
    baseline: float,
    current_hours: float,
    step_hours: float,
    segment: Segment,
    assumptions: InterventionAssumptions,
) -> float:
    """Expected-retained-ARR gain from adding ``step_hours`` on top of ``current_hours``.

    Non-negative and (because the uplift curve is concave) non-increasing in
    ``current_hours`` — the property the greedy solver relies on for optimality.
    """

    p0 = estimated_probability(
        baseline=baseline, hours=current_hours, segment=segment, assumptions=assumptions
    )
    p1 = estimated_probability(
        baseline=baseline,
        hours=current_hours + step_hours,
        segment=segment,
        assumptions=assumptions,
    )
    return arr * (p1 - p0)
