"""
algenta.simple — One-line magic entry points.

This is the activation layer. Someone reads a tweet, copies one line,
and immediately understands why Algenta exists.

  from algenta import decision, optimize, simulate

  decision("Should I launch this product?", revenue=120000, cost=70000)
  optimize("maximize profit", price=(10, 200), quantity=(100, 5000))
  simulate(revenue=100000, cost=70000, runs=50000)

No docs required. Output explains itself.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# ── Shared output ─────────────────────────────────────────────────────────────

@dataclass
class Result:
    """Universal result with self-explaining output."""
    action: str          # "proceed" | "optimize" | "value"
    value: float
    confidence: float    # 0–1
    why: list[str]       # 3 plain-English reasons
    details: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

    def __repr__(self) -> str:
        bar = "█" * int(self.confidence * 20) + "░" * (20 - int(self.confidence * 20))
        lines = [
            f"\n  Action:     {self.action.upper()}",
            f"  Value:      {self.value:,.2f}",
            f"  Confidence: [{bar}] {self.confidence:.0%}",
            "  Why:",
        ]
        for reason in self.why:
            lines.append(f"    → {reason}")
        if self.details:
            lines.append("  Details:")
            for k, v in self.details.items():
                if isinstance(v, float):
                    lines.append(f"    {k}: {v:,.2f}")
                else:
                    lines.append(f"    {k}: {v}")
        lines.append(f"  ({self.latency_ms:.0f}ms · {self.details.get('scenarios', 0):,} scenarios)")
        return "\n".join(lines) + "\n"


# ── Decision ──────────────────────────────────────────────────────────────────

class _Decision:
    """
    Natural language + numeric decision analysis.

    Usage:
      from algenta import decision

      decision("Should I launch this product?", revenue=120000, cost=70000)
      decision(revenue=120000, cost=70000, risk_tolerance="low")
      decision.analyze(inputs={"revenue": {"value": 120000, "low": 80000, "high": 180000}})
    """

    def __call__(
        self,
        label: str = "",
        risk_tolerance: str = "medium",
        runs: int = 10000,
        mode: str = "local",
        api_key: str | None = None,
        **named_values: float,
    ) -> Result:
        if mode == "cloud":
            from algenta.decision import _cloud_analyze
            d = _cloud_analyze(inputs=None, objective="maximize_value",
                               risk_tolerance=risk_tolerance, runs=runs,
                               api_key=api_key, **named_values)
            return Result(
                action=d.action, value=d.expected_outcome,
                confidence=d.confidence, why=self._make_why(d.action, d.confidence,
                    d.probability_of_loss, d.expected_outcome, d.downside_risk, d.upside_potential),
                details={
                    "scenarios": d.scenarios_evaluated,
                    "downside_p5": d.downside_risk,
                    "upside_p95": d.upside_potential,
                    "prob_of_loss": d.probability_of_loss,
                    "label": label,
                },
            )

        t0 = time.monotonic()
        from algenta.decision import analyze
        d = analyze(risk_tolerance=risk_tolerance, runs=runs, **named_values)

        why = self._make_why(d.action, d.confidence, d.probability_of_loss,
                             d.expected_outcome, d.downside_risk, d.upside_potential)

        return Result(
            action=d.action,
            value=round(d.expected_outcome, 2),
            confidence=round(d.confidence, 4),
            why=why,
            details={
                "scenarios": runs,
                "downside_p5": d.downside_risk,
                "upside_p95": d.upside_potential,
                "prob_of_loss": d.probability_of_loss,
                "label": label or "decision",
            },
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )

    def analyze(self, inputs: dict | None = None, **kw: Any) -> Result:
        from algenta.decision import analyze
        d = analyze(inputs=inputs, **kw)
        why = self._make_why(d.action, d.confidence, d.probability_of_loss,
                             d.expected_outcome, d.downside_risk, d.upside_potential)
        return Result(action=d.action, value=d.expected_outcome,
                      confidence=d.confidence, why=why,
                      details={"scenarios": d.scenarios_evaluated,
                               "downside_p5": d.downside_risk,
                               "upside_p95": d.upside_potential})

    @staticmethod
    def _make_why(action: str, conf: float, pol: float, ev: float,
                  p5: float, p95: float) -> list[str]:
        gain_loss_ratio = abs(p95 - ev) / (abs(ev - p5) + 1e-9)
        reasons = [
            f"Positive outcome in {1-pol:.0%} of scenarios (expected: {ev:,.0f})",
            f"Upside {p95:,.0f} vs downside {p5:,.0f} — gain/loss ratio {gain_loss_ratio:.1f}×",
        ]
        if action == "proceed":
            reasons.append(f"Risk within tolerance — confidence {conf:.0%}")
        elif action == "pause":
            reasons.append(f"Elevated risk ({pol:.0%} chance of loss) — reduce exposure before committing")
        else:
            reasons.append(f"Negative outcome too likely ({pol:.0%}) — reject or redesign")
        return reasons


# ── Optimize ──────────────────────────────────────────────────────────────────

class _Optimize:
    """
    Find the best value. Natural language objective, tuple bounds.

    Usage:
      from algenta import optimize

      optimize("maximize profit", price=(10, 200), quantity=(100, 5000))
      optimize("minimize cost", workers=(1, 20), machines=(0, 10))
      optimize.maximize(lambda p, q: p*q - 30*q, price=(10,200), quantity=(100,5000))
    """

    def __call__(
        self,
        objective: str,
        iterations: int = 1000,
        mode: str = "local",
        **variable_ranges: tuple[float, float],
    ) -> Result:
        t0 = time.monotonic()

        variables = {k: v for k, v in variable_ranges.items()
                     if isinstance(v, (tuple, list)) and len(v) == 2}

        from algenta.optimize import find_best
        res = find_best(objective, variables, iterations=iterations)

        is_max = "maximiz" in objective.lower() or "revenue" in objective.lower()
        direction = "maximizing" if is_max else "minimizing"
        best_var = max(res.optimal_values, key=lambda k: abs(res.optimal_values[k]))
        imp = res.improvement_vs_baseline

        why = [
            f"Best configuration found after {iterations:,} iterations",
            f"Optimal {best_var}: {res.optimal_values[best_var]:,.2f} ({direction})",
            f"{imp:+.1f}% vs midpoint baseline — all constraints satisfied",
        ]

        return Result(
            action="optimize",
            value=round(res.objective_value, 4),
            confidence=min(1.0, 0.6 + iterations / 5000),
            why=why,
            details={**{k: round(v, 4) for k, v in res.optimal_values.items()},
                     "improvement_pct": imp, "scenarios": iterations},
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )

    def maximize(self, fn: Any, iterations: int = 1000, **ranges: tuple[float, float]) -> Result:
        from algenta.optimize import maximize as _max
        res = _max(fn, ranges, iterations=iterations)
        return Result(
            action="optimize",
            value=res.objective_value,
            confidence=0.85,
            why=[
                f"Maximum found after {iterations:,} iterations",
                f"Objective value: {res.objective_value:,.4f}",
                f"{res.improvement_vs_baseline:+.1f}% improvement vs baseline",
            ],
            details={**res.optimal_values, "scenarios": iterations},
        )

    def minimize(self, fn: Any, iterations: int = 1000, **ranges: tuple[float, float]) -> Result:
        from algenta.optimize import minimize as _min
        res = _min(fn, ranges, iterations=iterations)
        return Result(
            action="optimize",
            value=res.objective_value,
            confidence=0.85,
            why=[
                f"Minimum found after {iterations:,} iterations",
                f"Objective value: {res.objective_value:,.4f}",
                f"{res.improvement_vs_baseline:+.1f}% improvement vs baseline",
            ],
            details={**res.optimal_values, "scenarios": iterations},
        )


# ── Simulate ──────────────────────────────────────────────────────────────────

class _Simulate:
    """
    Monte Carlo simulation. Pass named values, get back a distribution.

    Usage:
      from algenta import simulate

      simulate(revenue=120000, cost=70000, runs=50000)
      simulate.risk(revenue=120000, cost=70000)
      simulate.from_distributions([
          {"name": "revenue", "distribution": "normal", "mean": 120000, "std": 15000},
      ])
    """

    def __call__(self, runs: int = 10000, mode: str = "local",
                 api_key: str | None = None, **named_values: float) -> Result:
        t0 = time.monotonic()
        from algenta.simulate import risk
        r = risk(runs=runs, mode=mode, api_key=api_key, **named_values)

        pol = r.probability_of_loss
        ev  = r.expected_value
        action = "proceed" if pol < 0.2 else ("caution" if pol < 0.4 else "risk")

        why = [
            f"Expected outcome: {ev:,.0f} across {runs:,} scenarios",
            f"Probability of loss: {pol:.1%} (p5={r.percentile_5:,.0f}, p95={r.percentile_95:,.0f})",
            f"Std deviation: {r.std_deviation:,.0f} — {'stable' if r.std_deviation < abs(ev)*0.2 else 'volatile'} outcome",
        ]
        return Result(
            action=action, value=round(ev, 2), confidence=round(1.0 - pol, 4),
            why=why,
            details={
                "p5": r.percentile_5, "p25": r.percentile_25,
                "p50": r.percentile_50, "p75": r.percentile_75,
                "p95": r.percentile_95, "std": r.std_deviation,
                "scenarios": runs,
            },
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )

    def risk(self, runs: int = 10000, **named_values: float) -> Result:
        return self(**named_values, runs=runs)

    def from_distributions(self, variables: list[dict], runs: int = 10000) -> Result:
        from algenta.simulate import run as _run
        r = _run(variables, runs=runs)
        pol = r.probability_of_loss
        action = "proceed" if pol < 0.2 else ("caution" if pol < 0.4 else "risk")
        return Result(
            action=action, value=r.expected_value, confidence=1.0 - pol,
            why=[
                f"Expected outcome: {r.expected_value:,.0f} across {runs:,} scenarios",
                f"Probability of loss: {pol:.1%}",
                f"Range: {r.percentile_5:,.0f} (p5) → {r.percentile_95:,.0f} (p95)",
            ],
            details={"scenarios": runs, "std": r.std_deviation,
                     "p5": r.percentile_5, "p95": r.percentile_95},
        )


# Singletons — these ARE the top-level API
decision = _Decision()
optimize = _Optimize()
simulate = _Simulate()
