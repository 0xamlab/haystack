"""Model-specific configuration schemas for simulation requests."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CorrelationSpec(BaseModel):
    model_config = ConfigDict(strict=False)
    variables: list[str] = Field(..., min_length=2, max_length=2)
    coefficient: float = Field(..., ge=-1.0, le=1.0)


class ScoringWeights(BaseModel):
    model_config = ConfigDict(strict=False)
    expected_value: float = Field(default=0.6, ge=0.0, le=1.0)
    downside_risk: float = Field(default=0.4, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> ScoringWeights:
        total = self.expected_value + self.downside_risk
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total:.3f}")
        return self


class DecisionNode(BaseModel):
    """
    A node in a multi-layered decision tree.

    Node types:
      decision  — represents a controllable choice (e.g. "Launch" vs "Don't Launch")
      chance    — represents an uncertain outcome with a probability (e.g. "Market Accepts")
      terminal  — leaf node; variables + objective_function evaluated here

    Each node can override any parent variable with a new distribution or scalar.
    Variable overrides cascade top-down: child inherits parent, then applies its own.
    """

    model_config = ConfigDict(strict=False)
    id: str = Field(..., min_length=1, max_length=200)
    type: str = Field(
        default="terminal",
        description="Node type: decision | chance | terminal",
    )
    name: str = Field(default="", max_length=500)
    probability: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Branch probability (for chance nodes). All siblings should sum to 1.0.",
    )
    condition: str | None = Field(
        None,
        max_length=500,
        description="Optional expression condition for this branch to be active",
    )
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Variable overrides for this branch. "
            "Scalar value → treated as fixed distribution. "
            "Dict → full VariableSpec override {distribution, params}."
        ),
    )
    objective_function: str | None = Field(
        None,
        max_length=1000,
        description="Expression override for this node. Inherits top-level if not set.",
    )
    branches: list[DecisionNode] = Field(
        default_factory=list,
        max_length=50,
        description="Child branches. Empty = terminal node.",
    )


DecisionNode.model_rebuild()


class DecisionTreeConfig(BaseModel):
    """
    Config for engine_type='decision_tree' — multi-layered decisions with branches.

    Example (2-level tree):
      nodes: [
        {
          id: "launch_decision", type: "decision", name: "Launch Product?",
          branches: [
            {
              id: "launch_yes", type: "chance", name: "Launch", probability: 1.0,
              branches: [
                { id: "accept", type: "terminal", name: "Market Accepts",
                  probability: 0.7, objective_function: "revenue - launch_cost" },
                { id: "reject", type: "terminal", name: "Market Rejects",
                  probability: 0.3, variables: {"revenue": 0},
                  objective_function: "-launch_cost" }
              ]
            }
          ]
        }
      ]
    """

    model_config = ConfigDict(strict=False)
    nodes: list[DecisionNode] = Field(
        ...,
        min_length=1,
        max_length=50,
        description=(
            "Root nodes of the decision tree. Multiple roots = parallel independent decisions."
        ),
    )
    max_depth: int = Field(default=10, ge=1, le=20, description="Maximum allowed tree depth")


class ScenarioItem(BaseModel):
    """A single named scenario for discrete scenario analysis."""

    model_config = ConfigDict(strict=False)
    name: str = Field(..., max_length=200)
    probability: float = Field(..., ge=0.0, le=1.0)
    variables: dict[str, float] = Field(default_factory=dict)
    objective_function: str | None = Field(None, max_length=500)


class ScenarioConfig(BaseModel):
    """Config for engine_type='scenario' — discrete weighted scenarios."""

    model_config = ConfigDict(strict=False)
    scenarios: list[ScenarioItem] = Field(..., min_length=1, max_length=50)


class BootstrapConfig(BaseModel):
    """Config for engine_type='bootstrap' — non-parametric resampling."""

    model_config = ConfigDict(strict=False)
    historical_data: list[float] = Field(..., min_length=2, max_length=100_000)
    statistic: str = Field(
        default="mean",
        description=(
            "Statistic to compute on each resample. "
            "One of: mean, median, std, variance, sum, min, max, sharpe, "
            "percentile_5, percentile_25, percentile_75, percentile_95, range, cv"
        ),
    )
    confidence_level: float = Field(default=0.95, ge=0.0, le=1.0)


class MCMCConfig(BaseModel):
    """Config for engine_type='mcmc' — Metropolis-Hastings Bayesian MCMC."""

    model_config = ConfigDict(strict=False)
    observed_data: list[float] = Field(..., min_length=2, max_length=100_000)
    parameter_priors: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Dict of param_name → {distribution, params}. "
            "Auto-inferred from data if empty. "
            "Example: {'mean': {'distribution': 'normal', 'params': "
            "{'mean': 500000, 'std': 100000}}}"
        ),
    )
    likelihood: str = Field(
        default="normal",
        description="Likelihood model: normal | lognormal | poisson",
    )
    chains: int = Field(default=4, ge=1, le=16)
    burn_in: int = Field(default=1000, ge=100, le=50_000)


class SensitivityConfig(BaseModel):
    """Config for engine_type='sensitivity' — sensitivity analysis."""

    model_config = ConfigDict(strict=False)
    method: str = Field(
        default="both",
        description="tornado | sobol | both",
    )


class ImportanceSamplingConfig(BaseModel):
    """
    Config for engine_type='importance_sampling' — exponential tilting for rare tail events.

    Use when you need accurate estimates of very low-probability events
    (e.g. 1-in-10,000 loss scenarios) without running millions of MC trials.

    The engine shifts sampling mass toward the target tail using exponential tilting
    (θ optimal tilt), then corrects back with likelihood ratio weights.
    Reports: tail_probability, tail_probability_se, cvar_tail, ESS, variance_reduction_factor.
    """

    model_config = ConfigDict(strict=False)
    target_threshold: float = Field(
        ...,
        description=(
            "The rare event level. E.g. -500000 for a $500k loss, or 2.5 for an extreme gain."
        ),
    )
    tail_direction: str = Field(
        default="lower",
        description=(
            "'lower' for loss events (outcome < threshold), 'upper' for "
            "extreme gains (outcome > threshold)."
        ),
    )
    tilt_variable: str | None = Field(
        default=None,
        description=(
            "Name of the normal-distributed variable to apply exponential "
            "tilting to. Auto-detects the highest-variance normal variable if "
            "omitted."
        ),
    )
    tilt_sigma: float = Field(
        default=0.0,
        description=(
            "Override the tilt parameter θ directly (0 = auto-compute from "
            "threshold). Advanced use only."
        ),
    )


class StochasticParam(BaseModel):
    """
    A simulation parameter that is itself stochastic (drawn fresh for each path).
    Use for uncertain drift, volatility, or any time-series parameter.
    """

    model_config = ConfigDict(strict=False)
    type: str = Field(
        default="fixed",
        description="fixed | normal | uniform | lognormal",
    )
    value: float = Field(default=0.0, description="Fixed value (for type='fixed')")
    mean: float = Field(default=0.0, description="Mean (for type='normal' or 'lognormal')")
    std: float = Field(default=0.0, description="Std dev (for type='normal' or 'lognormal')")
    low: float = Field(default=0.0, description="Lower bound (for type='uniform')")
    high: float = Field(default=0.0, description="Upper bound (for type='uniform')")


class TimeSeriesConfig(BaseModel):
    """
    Config for engine_type='time_series' — multi-horizon stochastic path simulation.

    Supported models:
      gbm        — Geometric Brownian Motion
      ou         — Ornstein-Uhlenbeck mean-reversion
      arithmetic — Arithmetic Brownian Motion
      compound   — Compound return
      custom     — Expression-driven path

    Granularities: ms, s, min, h, day, week, month, quarter, year
    """

    model_config = ConfigDict(strict=False)

    model: str = Field(
        default="gbm",
        description="Path model: gbm | ou | arithmetic | compound | custom",
    )
    initial_value: float = Field(
        ...,
        description="Starting value of the process (e.g. current stock price, balance, etc.)",
    )
    horizons: list[int] = Field(
        default=[1, 3, 6, 12],
        min_length=1,
        max_length=100,
        description=(
            "Time steps at which to record distributions. E.g. [1,3,6,12] for 1/3/6/12 months."
        ),
    )
    granularity: str = Field(
        default="month",
        description=(
            "Time unit per step. One of: ms, s, min, h, day, week, month, quarter, year. "
            "All drift/vol parameters assumed annualized unless granularity='custom'."
        ),
    )
    drift: StochasticParam | float = Field(
        default=0.0,
        description=(
            "Annualized drift / expected return. "
            "Float shorthand or StochasticParam for uncertain drift. "
            "GBM: annual log-return. OU: not used (use long_run_mean). Compound: annual return."
        ),
    )
    volatility: StochasticParam | float = Field(
        default=0.20,
        description="Annualized volatility (σ). Float or StochasticParam.",
    )
    autocorrelation: float = Field(
        default=0.0,
        ge=-0.99,
        le=0.99,
        description=(
            "AR(1) autocorrelation coefficient for innovations (0 = i.i.d., "
            ">0 = trending, <0 = mean-reverting noise)"
        ),
    )
    long_run_mean: float | None = Field(
        None,
        description="OU model: long-run mean (μ∞). Defaults to initial_value.",
    )
    mean_reversion_speed: float = Field(
        default=0.5,
        ge=0.0,
        description="OU model: speed of mean reversion (θ). Higher = faster pull to mean.",
    )
    path_expression: str | None = Field(
        None,
        max_length=500,
        description=(
            "Custom model: Python expression for next step value. "
            "Variables: value, t, dt, drift, vol, z, initial. "
            "Example: 'value * exp((drift - 0.5*vol**2)*dt + vol*dt**0.5*z)'"
        ),
    )
    fan_chart_percentiles: list[int] = Field(
        default=[5, 10, 25, 50, 75, 90, 95],
        min_length=1,
        max_length=20,
        description="Percentile levels to include in the fan chart output at each horizon.",
    )
    output_paths: bool = Field(
        default=False,
        description=(
            "Include sample path data in response (for fan chart visualization). Adds ~50 paths."
        ),
    )
    n_sample_paths: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of sample paths to include when output_paths=True.",
    )
