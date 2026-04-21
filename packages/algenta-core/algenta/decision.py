"""
algenta.decision — Local decision analysis engine.

Given inputs and uncertainty, evaluates thousands of scenarios and
returns the optimal action with confidence and plain-English reasoning.

Usage:

  from algenta import decision

  # Simple: what should I do?
  result = decision.analyze(
      revenue=120000, cost=70000,
      risk_tolerance="medium",
  )
  print(result.action, result.confidence, result.reasoning)

  # With uncertainty ranges
  result = decision.analyze(
      inputs={
          "revenue": {"value": 120000, "low": 80000, "high": 180000},
          "cost":    {"value": 70000,  "low": 50000, "high": 100000},
      },
      objective="maximize_profit",
      runs=50000,
  )

  # Cloud for high-stakes decisions
  result = decision.analyze(..., mode="cloud", api_key="de_live_...")
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from algenta._contract import DEFAULT_BASE_URL
from algenta.simulate import _box_muller, _summarize, _triangular_sample


@dataclass
class DecisionResult:
    action: str            # "proceed" | "pause" | "reject"
    confidence: float      # 0–1
    reasoning: str
    expected_outcome: float
    downside_risk: float   # p5
    upside_potential: float  # p95
    probability_of_loss: float
    scenarios_evaluated: int
    engine: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "expected_outcome": self.expected_outcome,
            "downside_risk": self.downside_risk,
            "upside_potential": self.upside_potential,
            "probability_of_loss": self.probability_of_loss,
            "scenarios_evaluated": self.scenarios_evaluated,
            "engine": self.engine,
        }


_RISK_THRESHOLDS = {"low": 0.05, "medium": 0.15, "high": 0.30}


def analyze(
    inputs: dict[str, Any] | None = None,
    objective: str = "maximize_value",
    risk_tolerance: str = "medium",
    runs: int = 10000,
    mode: str = "local",
    api_key: str | None = None,
    **named_values: float,
) -> DecisionResult:
    """
    Analyze a decision given inputs and constraints.

    Pass named float values (simple) or an inputs dict with uncertainty ranges.

    Examples:
      decision.analyze(revenue=100000, cost=70000)
      decision.analyze(inputs={"revenue": {"value": 100000, "low": 80000, "high": 140000}})
    """
    if mode == "cloud":
        return _cloud_analyze(inputs=inputs, objective=objective, risk_tolerance=risk_tolerance,
                               runs=runs, api_key=api_key, **named_values)

    # Build sample spec from inputs
    specs: list[tuple[str, float, float | None, float | None]] = []
    if inputs:
        for name, spec in inputs.items():
            if isinstance(spec, dict):
                val = spec.get("value", spec.get("mean", 0))
                lo  = spec.get("low",  spec.get("min"))
                hi  = spec.get("high", spec.get("max"))
            else:
                val, lo, hi = float(spec), None, None
            specs.append((name, val, lo, hi))
    for name, val in named_values.items():
        specs.append((name, val, None, None))

    if not specs:
        raise ValueError("Provide at least one input variable")

    # Monte Carlo
    values: list[float] = []
    for _ in range(runs):
        total = 0.0
        for _name, val, lo, hi in specs:
            if lo is not None and hi is not None:
                s = _triangular_sample(lo, val, hi)
            else:
                s = _box_muller(val, abs(val) * 0.15)
            total += s
        values.append(total)

    sim = _summarize(values)
    pol = sim.probability_of_loss
    ev = sim.expected_value
    p5, p95 = sim.percentile_5, sim.percentile_95
    conf = max(0.0, 1.0 - pol * 2)

    threshold = _RISK_THRESHOLDS.get(risk_tolerance, 0.15)
    if pol > 0.5:
        action = "reject"
        reasoning = (
            f"Negative outcome likely in {pol:.0%} of {runs:,} scenarios. "
            f"Expected outcome: {ev:,.0f}. Too risky to proceed."
        )
    elif pol > threshold:
        action = "pause"
        reasoning = (
            f"Outcome is positive but risk is elevated: {pol:.0%} chance of loss. "
            f"Expected: {ev:,.0f}. Consider reducing exposure or improving inputs."
        )
    else:
        action = "proceed"
        reasoning = (
            f"Positive outcome in {1-pol:.0%} of {runs:,} scenarios. "
            f"Expected: {ev:,.0f}. Risk within {risk_tolerance} tolerance."
        )

    return DecisionResult(
        action=action,
        confidence=round(conf, 4),
        reasoning=reasoning,
        expected_outcome=round(ev, 4),
        downside_risk=round(p5, 4),
        upside_potential=round(p95, 4),
        probability_of_loss=round(pol, 4),
        scenarios_evaluated=runs,
    )


def _cloud_analyze(inputs: dict[str, Any] | None, objective: str, risk_tolerance: str,
                   runs: int, api_key: str | None, base_url: str = DEFAULT_BASE_URL,
                   **named_values: float) -> DecisionResult:
    try:
        import httpx
    except ImportError:
        raise ImportError("Cloud mode requires: pip install algenta-core[cloud]") from None

    if not api_key:
        import os
        api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
    if not api_key:
        raise ValueError("Cloud mode requires an API key")

    # Build API payload
    api_inputs = []
    if inputs:
        for name, spec in inputs.items():
            if isinstance(spec, dict):
                api_inputs.append({
                    "name": name,
                    "value": spec.get("value", 0),
                    "low": spec.get("low"),
                    "high": spec.get("high"),
                })
            else:
                api_inputs.append({"name": name, "value": float(spec)})
    for name, val in named_values.items():
        api_inputs.append({"name": name, "value": val})

    payload = {
        "inputs": api_inputs,
        "objective": objective,
        "risk_tolerance": risk_tolerance,
        "scenarios": runs,
    }
    resp = httpx.post(
        f"{base_url}/v1/decision",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return DecisionResult(
        action=data.get("action", "unknown"),
        confidence=data.get("confidence", 0),
        reasoning=data.get("reasoning", ""),
        expected_outcome=data.get("expected_outcome", 0),
        downside_risk=data.get("downside_risk", 0),
        upside_potential=data.get("upside_potential", 0),
        probability_of_loss=data.get("probability_of_loss", 0),
        scenarios_evaluated=data.get("scenarios_evaluated", runs),
        engine="cloud",
    )
