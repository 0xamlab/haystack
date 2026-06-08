"""
Engine auto-selector — picks the best simulation engine from input data characteristics.

Called whenever engine="auto" is passed to any product API or template endpoint.
Heuristics are deterministic and fast (~0ms) — no ML, no network calls.

Engine capabilities:
  monte_carlo          — general purpose, high sample count, any distribution
  lhs                  — Latin Hypercube: faster convergence, high-dimensional problems
  qmc_sobol            — Quasi-Monte Carlo: best for smooth functions, variance reduction
  bootstrap            — resampling from empirical data, CI estimation
  sensitivity          — which variable drives outcomes most (requires sensitivity_config)
  mcmc                 — Bayesian posterior estimation (requires mcmc_config)
  importance_sampling  — rare event / tail risk analysis (requires importance_sampling_config)
  time_series          — temporal models: GBM, OU, AR(1) (requires time_series_config)
  scenario             — discrete named scenarios (requires scenario_config)
  decision_tree        — branching decisions (requires decision_tree_config)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EngineSelection:
    engine: str
    reason: str
    confidence: float  # 0–1, how certain we are this is the right engine


def _has_time_structure(variables: list[dict[str, Any]]) -> bool:
    """True when any variable name hints at a temporal sequence."""
    time_keywords = {
        "period",
        "month",
        "year",
        "quarter",
        "week",
        "day",
        "horizon",
        "t0",
        "t1",
        "step",
        "lag",
        "series",
        "growth",
        "drift",
        "volatility",
        "gbm",
        "ou",
        "time",
        "trend",
        "forecast",
        "arima",
        "seasonal",
    }
    for v in variables:
        name = v.get("name", "").lower()
        desc = v.get("description", "").lower()
        if any(kw in name or kw in desc for kw in time_keywords):
            return True
        # Also check if distribution is GBM-style
        if v.get("distribution", "") in ("gbm", "ou", "ar1"):
            return True
    return False


def _has_rare_event_focus(variables: list[dict[str, Any]], objective: str) -> bool:
    """True when the analysis is clearly about tail risk or rare events."""
    # Use longer, less ambiguous keywords to avoid false positives on common names like "var0"
    tail_keywords = {
        "value_at_risk",
        "cvar",
        "tail_risk",
        "rare_event",
        "extreme_loss",
        "catastroph",
        "black_swan",
        "loss_given_default",
        "bankruptcy",
        "failure_rate",
        "crash_risk",
        "stress_test",
        "prob_default",
    }
    # Short keywords checked only in objective function (more controlled context)
    short_tail_obj = {"tail", "extreme", "worst_case", "downside_only", "credit_risk"}
    obj_lower = objective.lower()
    if any(kw in obj_lower for kw in tail_keywords | short_tail_obj):
        return True
    for v in variables:
        name = v.get("name", "").lower()
        if any(kw in name for kw in tail_keywords):
            return True
    return False


def _all_fixed(variables: list[dict[str, Any]]) -> bool:
    """True when all variables are fixed (no uncertainty) — degenerate case."""
    return all(v.get("distribution", "") == "fixed" for v in variables)


def _is_high_dimensional(variables: list[dict[str, Any]]) -> bool:
    """True when there are many interacting stochastic variables."""
    stochastic = [v for v in variables if v.get("distribution", "") != "fixed"]
    return len(stochastic) >= 6


def _has_empirical_data(variables: list[dict[str, Any]]) -> bool:
    """True when variable params include raw samples (empirical/bootstrap input)."""
    for v in variables:
        dist = v.get("distribution", "")
        params = v.get("params", {})
        if dist in ("empirical", "bootstrap", "kde") or "samples" in params or "data" in params:
            return True
    return False


def _sensitivity_requested(objective: str, variables: list[dict[str, Any]]) -> bool:
    """True when the user is clearly asking 'which variable matters most'."""
    keywords = {
        "sensitivity",
        "elasticity",
        "tornado",
        "importance",
        "which variable",
        "most impact",
        "driver",
        "contribution",
    }
    return any(kw in objective.lower() for kw in keywords)


def select_engine(
    variables: list[dict[str, Any]],
    runs: int,
    objective: str = "",
    mode_hint: str = "",
) -> EngineSelection:
    """
    Select the optimal simulation engine based on data characteristics.

    Args:
        variables: List of variable specs (name, distribution, params, description).
        runs: Number of scenarios requested.
        objective: Objective function string or high-level goal description.
        mode_hint: Optional user hint ('decision', 'optimize', 'forecast', 'simulate').

    Returns:
        EngineSelection with engine name, reason, and confidence.
    """
    # Degenerate: all fixed → no uncertainty, any engine works but MC is fine
    if _all_fixed(variables):
        return EngineSelection(
            engine="monte_carlo",
            reason="All variables are fixed — Monte Carlo with no randomness",
            confidence=0.9,
        )

    # Time-series structure → time_series engine
    if _has_time_structure(variables) or mode_hint == "forecast":
        return EngineSelection(
            engine="time_series",
            reason="Temporal variables detected — using time-series engine (GBM/OU model)",
            confidence=0.85,
        )

    # Empirical / bootstrap data → bootstrap engine
    if _has_empirical_data(variables):
        return EngineSelection(
            engine="bootstrap",
            reason="Empirical samples detected — using bootstrap resampling for CI estimation",
            confidence=0.90,
        )

    # Rare event / tail risk focus → importance sampling
    if _has_rare_event_focus(variables, objective):
        return EngineSelection(
            engine="importance_sampling",
            reason=(
                "Tail-risk focus detected; importance sampling concentrates "
                "samples in the rare-event region"
            ),
            confidence=0.80,
        )

    # Sensitivity analysis explicitly requested
    if _sensitivity_requested(objective, variables):
        return EngineSelection(
            engine="sensitivity",
            reason=(
                "Sensitivity analysis requested; identifying which variable drives outcomes most"
            ),
            confidence=0.85,
        )

    # High-dimensional optimization → LHS (better space coverage than pure MC)
    if _is_high_dimensional(variables) or mode_hint == "optimize":
        return EngineSelection(
            engine="lhs",
            reason=(
                f"High-dimensional problem ({len(variables)} variables); "
                "LHS provides better space coverage"
            ),
            confidence=0.80,
        )

    # Large run counts → QMC Sobol for variance reduction
    if runs >= 50_000:
        return EngineSelection(
            engine="qmc_sobol",
            reason=(
                f"Large sample count ({runs:,}); Sobol quasi-random "
                "sequences reduce variance faster than Monte Carlo"
            ),
            confidence=0.75,
        )

    # Default: Monte Carlo — robust, works everywhere
    return EngineSelection(
        engine="monte_carlo",
        reason="General-purpose analysis — Monte Carlo with high scenario count",
        confidence=0.70,
    )
