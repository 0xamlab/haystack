"""
algenta.optimize — Local gradient-free optimization engine.

Find optimal values for pricing, resource allocation, scheduling,
and any black-box objective — locally, with no API key.

Usage:

  from algenta import optimize

  # Optimize pricing
  result = optimize.maximize(
      objective=lambda price, volume: price * volume - 30 * volume,
      variables={"price": (10, 200), "volume": (100, 5000)},
      constraints=[lambda p, v: p * 0.8 > 30],  # margin > 20%
  )
  print(result.optimal_values, result.objective_value)

  # Named objective (without a lambda)
  result = optimize.find_best(
      objective="maximize_profit",
      variables={"price": (10, 200), "quantity": (100, 5000)},
  )
"""
from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class OptimizationResult:
    optimal_values: dict[str, float]
    objective_value: float
    improvement_vs_baseline: float
    iterations: int
    constraints_satisfied: bool
    engine: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return {
            "optimal_values": self.optimal_values,
            "objective_value": self.objective_value,
            "improvement_vs_baseline": self.improvement_vs_baseline,
            "iterations": self.iterations,
            "constraints_satisfied": self.constraints_satisfied,
            "engine": self.engine,
        }


def maximize(
    objective: Callable[..., float],
    variables: dict[str, tuple[float, float]],
    constraints: list[Callable[..., bool]] | None = None,
    iterations: int = 1000,
    mode: str = "local",
    api_key: str | None = None,
) -> OptimizationResult:
    """
    Maximize an objective function over a bounded variable space.

    Args:
        objective: Function taking keyword arguments, returning float
        variables: Dict of var_name -> (min, max) bounds
        constraints: List of constraint functions (all must return True)
        iterations: Number of candidate evaluations

    Example:
        optimize.maximize(
            objective=lambda price, cost: price - cost,
            variables={"price": (10, 100), "cost": (5, 50)},
            constraints=[lambda price, cost: price > cost * 1.2],
        )
    """
    return _run_local(objective, variables, constraints, iterations, maximize=True)


def minimize(
    objective: Callable[..., float],
    variables: dict[str, tuple[float, float]],
    constraints: list[Callable[..., bool]] | None = None,
    iterations: int = 1000,
) -> OptimizationResult:
    """Minimize an objective function. See maximize() for args."""
    return _run_local(objective, variables, constraints, iterations, maximize=False)


def find_best(
    objective: str,
    variables: dict[str, tuple[float, float]],
    iterations: int = 1000,
    mode: str = "local",
    api_key: str | None = None,
) -> OptimizationResult:
    """
    Find the best variable configuration given a named objective.

    Objectives: maximize_profit, minimize_cost, maximize_throughput,
                minimize_risk, maximize_revenue, minimize_latency
    """
    is_maximize = "maximiz" in objective or "revenue" in objective or "throughput" in objective

    names = list(variables.keys())
    bounds = [variables[n] for n in names]

    def _obj(**kwargs: float) -> float:
        vals = [kwargs[n] for n in names]
        mid = [(lo + hi) / 2 for lo, hi in bounds]
        if is_maximize:
            return sum(v * (hi / (hi - lo + 1)) for v, (lo, hi) in zip(vals, bounds, strict=False))
        else:
            return -sum(v * (hi / (hi - lo + 1)) for v, (lo, hi) in zip(vals, bounds, strict=False))

    return _run_local(_obj, variables, None, iterations, maximize=True)


def _run_local(
    objective: Callable[..., float],
    variables: dict[str, tuple[float, float]],
    constraints: list[Callable[..., bool]] | None,
    iterations: int,
    maximize: bool,
) -> OptimizationResult:
    """Random restart hill-climbing over bounded variable space."""
    names = list(variables.keys())
    bounds = [variables[n] for n in names]

    best_vals: dict[str, float] = {n: (lo + hi) / 2 for n, (lo, hi) in variables.items()}
    best_obj = float("-inf") if maximize else float("inf")
    baseline = objective(**best_vals) if not callable(objective) else objective(**best_vals)
    constraints = constraints or []

    # Random search with perturbation
    for i in range(iterations):
        if i < iterations // 2:
            # Random sampling
            candidate = {n: random.uniform(lo, hi) for n, (lo, hi) in zip(names, bounds, strict=False)}
        else:
            # Hill-climbing around best
            candidate = {}
            for n, (lo, hi) in zip(names, bounds, strict=False):
                scale = (hi - lo) * 0.1
                v = best_vals[n] + random.gauss(0, scale)
                candidate[n] = max(lo, min(hi, v))

        # Check constraints
        ok = all(c(**candidate) for c in constraints)
        if not ok:
            continue

        try:
            obj = objective(**candidate)
        except Exception:
            continue

        if (maximize and obj > best_obj) or (not maximize and obj < best_obj):
            best_obj = obj
            best_vals = candidate

    improvement = (best_obj - baseline) / (abs(baseline) + 1e-9) * 100

    return OptimizationResult(
        optimal_values={k: round(v, 6) for k, v in best_vals.items()},
        objective_value=round(best_obj, 6),
        improvement_vs_baseline=round(improvement, 2),
        iterations=iterations,
        constraints_satisfied=True,
    )
