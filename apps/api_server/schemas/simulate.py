"""Request schemas for simulation endpoints."""

import enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, model_validator

from apps.api_server.schemas.simulate_model_configs import (
    BootstrapConfig,
    CorrelationSpec,
    DecisionNode,
    DecisionTreeConfig,
    ImportanceSamplingConfig,
    MCMCConfig,
    ScenarioConfig,
    ScenarioItem,
    ScoringWeights,
    SensitivityConfig,
    StochasticParam,
    TimeSeriesConfig,
)

__all__ = [
    "AutoScenario",
    "AutoVariable",
    "BootstrapConfig",
    "CorrelationSpec",
    "DecisionNode",
    "DecisionTreeConfig",
    "DistributionParams",
    "DistributionType",
    "ExpertSimulation",
    "ImportanceSamplingConfig",
    "MCMCConfig",
    "ObjectiveType",
    "ScoringWeights",
    "ScenarioConfig",
    "ScenarioItem",
    "SensitivityConfig",
    "SimulateRequest",
    "SimulateRequestAuto",
    "SimulateRequestExpert",
    "SimulationModel",
    "StochasticParam",
    "TimeSeriesConfig",
    "UnitSpec",
    "VariableSpec",
]

# ── Distribution types ────────────────────────────────────────────────────────


class DistributionType(enum.StrEnum):
    """
    Universal distribution library — no restrictions on domain or data type.
    Applicable to any industry: finance, medical, manufacturing, aerospace,
    defense, energy, hospitality, insurance, pharma, supply chain, and more.
    """

    # Core (all industries)
    NORMAL = "normal"
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    LOGNORMAL = "lognormal"
    FIXED = "fixed"
    DISCRETE = "discrete"
    CATEGORICAL = "categorical"
    # Statistical
    BETA = "beta"
    EXPONENTIAL = "exponential"
    WEIBULL = "weibull"
    GAMMA = "gamma"
    PERT = "pert"
    BERNOULLI = "bernoulli"
    POISSON = "poisson"
    # Extended — universal
    STUDENT_T = "student_t"  # medical/finance: heavy-tailed
    CAUCHY = "cauchy"  # physics: resonance, fault lines
    LAPLACE = "laplace"  # signal processing, finance
    PARETO = "pareto"  # wealth, city sizes, failures
    GUMBEL = "gumbel"  # extreme events, floods, wind
    RAYLEIGH = "rayleigh"  # signal strength, aerospace
    ARCSINE = "arcsine"  # time-in-state, reliability
    LOGISTIC = "logistic"  # growth, epidemic curves
    HALFNORMAL = "halfnormal"  # always-positive measurements
    VONMISES = "vonmises"  # circular: wind direction, seasonality
    NEG_BINOMIAL = "neg_binomial"  # overdispersed counts
    HYPERGEOMETRIC = "hypergeometric"  # sampling without replacement
    NEGATIVE_BINOMIAL = "negative_binomial"  # alias


# ── Simulation model selector ─────────────────────────────────────────────────


class SimulationModel(enum.StrEnum):
    """Which simulation algorithm to use. ALL run natively in Mojo — zero Python bottlenecks."""

    MONTE_CARLO = "monte_carlo"  # standard MC (default) — parallel on all CPU cores
    QMC_SOBOL = "qmc_sobol"  # quasi-MC Sobol sequences — better low-run convergence
    LHS = "lhs"  # Latin Hypercube Sampling — stratified coverage
    BOOTSTRAP = "bootstrap"  # non-parametric bootstrap resampling
    SCENARIO = "scenario"  # discrete weighted scenario analysis
    SENSITIVITY = "sensitivity"  # tornado chart + first-order Sobol indices
    MCMC = "mcmc"  # Metropolis-Hastings Bayesian MCMC
    DECISION_TREE = "decision_tree"  # multi-branch decision trees
    TIME_SERIES = "time_series"  # GBM / OU / compound time-series paths
    COMPARE = "compare"  # N scenarios × M runs — zero Python overhead
    IMPORTANCE_SAMPLING = "importance_sampling"  # exponential tilting for rare tail events


# ── Objective types ───────────────────────────────────────────────────────────


class ObjectiveType(enum.StrEnum):
    MAXIMIZE_NET_VALUE = "maximize_net_value"
    MAXIMIZE_REVENUE = "maximize_revenue"
    MINIMIZE_COST = "minimize_cost"
    MINIMIZE_RISK = "minimize_risk"
    MAXIMIZE_SCORE = "maximize_score"


# ── Auto mode schemas ─────────────────────────────────────────────────────────


class AutoVariable(BaseModel):
    model_config = ConfigDict(strict=False)
    low: float = Field(..., description="Lower bound / pessimistic value")
    high: float = Field(..., description="Upper bound / optimistic value")
    description: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def high_must_exceed_low(self) -> "AutoVariable":
        if self.high <= self.low:
            raise ValueError("'high' must be greater than 'low'")
        return self


class AutoScenario(BaseModel):
    model_config = ConfigDict(strict=False)
    name: str | None = Field(None, max_length=200)
    variables: dict[str, AutoVariable] = Field(..., min_length=1, max_length=50)
    objective: ObjectiveType = Field(...)


# ── Expert mode schemas ───────────────────────────────────────────────────────


class DistributionParams(BaseModel):
    model_config = ConfigDict(strict=False, extra="allow")
    # Core params
    mean: float | None = None
    std: float | None = None
    low: float | None = None
    high: float | None = None
    mode: float | None = None
    value: float | None = None
    # Beta
    alpha: float | None = None
    beta: float | None = None
    # Exponential / Poisson
    rate: float | None = None
    lam: float | None = Field(None, alias="lambda")
    # Weibull / Gamma
    shape: float | None = None
    scale: float | None = None
    # PERT
    likely: float | None = None
    gamma: float | None = None
    # Bernoulli
    p: float | None = None
    # Discrete
    values: list[float] | None = None
    probabilities: list[float] | None = None


class VariableSpec(BaseModel):
    """
    A single simulation variable. No domain restrictions — works for any
    physical, financial, clinical, operational, or scientific measurement.
    """

    model_config = ConfigDict(strict=False)
    name: str = Field(..., min_length=1, max_length=500)
    distribution: DistributionType
    params: DistributionParams
    unit: str | None = Field(
        None,
        max_length=200,
        description="Short-hand unit string: 'USD', 'BTC', '%', 'bps', 'days', 'Pa', etc.",
    )
    unit_spec: "UnitSpec | None" = Field(
        None,
        description=(
            "Full unit specification with type, code, precision, scale, format, sim_scale. "
            "Supersedes 'unit' if both provided. "
            "Enables preprocessing (date→epoch, crypto satoshi→BTC), "
            "range validation, and formatted output."
        ),
    )
    description: str | None = Field(None, max_length=1000)
    domain_hint: str | None = Field(
        None,
        max_length=200,
        description=(
            "Optional domain hint e.g. 'time_to_failure', "
            "'patient_recovery_days', 'material_yield_strength'"
        ),
    )
    # For categorical distributions: map indices to label strings
    labels: list[str] | None = Field(
        None, description="For categorical/discrete: human-readable labels for each outcome index"
    )

    @model_validator(mode="after")
    def validate_params_for_distribution(self) -> "VariableSpec":
        p = self.params
        d = self.distribution
        if d == DistributionType.NORMAL:
            if p.mean is None or p.std is None:
                raise ValueError("Normal distribution requires 'mean' and 'std'")
            if p.std <= 0:
                raise ValueError("'std' must be positive for normal distribution")
        elif d == DistributionType.UNIFORM:
            if p.low is None or p.high is None:
                raise ValueError("Uniform distribution requires 'low' and 'high'")
            if p.high <= p.low:
                raise ValueError("'high' must exceed 'low' for uniform distribution")
        elif d == DistributionType.TRIANGULAR:
            if p.low is None or p.high is None or p.mode is None:
                raise ValueError("Triangular distribution requires 'low', 'high', and 'mode'")
            if not (p.low <= p.mode <= p.high):
                raise ValueError("Triangular mode must satisfy: low <= mode <= high")
        elif d == DistributionType.LOGNORMAL:
            if p.mean is None or p.std is None:
                raise ValueError("Lognormal distribution requires 'mean' and 'std'")
        elif d == DistributionType.FIXED:
            if p.value is None:
                raise ValueError("Fixed distribution requires 'value'")
        elif d == DistributionType.BETA:
            if p.alpha is None or p.beta is None:
                raise ValueError("Beta distribution requires 'alpha' and 'beta'")
        elif d == DistributionType.EXPONENTIAL:
            if p.rate is None:
                raise ValueError("Exponential distribution requires 'rate'")
        elif d in (DistributionType.WEIBULL, DistributionType.GAMMA):
            if p.shape is None or p.scale is None:
                raise ValueError(f"{d.value} distribution requires 'shape' and 'scale'")
        elif d == DistributionType.PERT:
            if p.low is None or p.high is None or p.likely is None:
                raise ValueError("PERT distribution requires 'low', 'high', and 'likely'")
        elif d == DistributionType.BERNOULLI:
            if p.p is None:
                raise ValueError("Bernoulli distribution requires 'p'")
        elif d == DistributionType.POISSON:
            if p.lam is None:
                raise ValueError("Poisson distribution requires 'lambda'")
        elif d == DistributionType.DISCRETE:
            if p.values is None or p.probabilities is None:
                raise ValueError("Discrete distribution requires 'values' and 'probabilities'")
        return self


# ── Universal unit specification ──────────────────────────────────────────────


class UnitSpec(BaseModel):
    """
    Universal unit specification — supports any numeric domain.

    Short-hand strings also accepted anywhere a UnitSpec is expected:
      "USD"        → currency/USD (2 decimal places)
      "BTC"        → crypto/BTC (8 decimal places, satoshi-aware)
      "ETH"        → crypto/ETH (18 decimals, wei-aware)
      "%"          → percentage (scale × 100 for display)
      "bps"        → basis points (scale × 10,000 for display)
      "days"       → duration in days
      "Pa" / "kg"  → SI unit (scientific notation for tiny/huge values)
      "probability" → strictly [0,1] validated
      "count"      → non-negative integer-like

    Full dict form:
      {
        "type": "currency",      # unit category
        "code": "USD",           # unit identifier
        "precision": 2,          # display decimal places (None = auto)
        "scale": 1.0,            # multiply raw value for display (e.g. 100 for 0→1 % → 0→100%)
        "format": "compact",     # standard | compact | scientific
        "base_unit": "satoshi",  # sub-unit label (informational)
        "sim_scale": 1.0         # divide input by this before simulation
      }
    """

    model_config = ConfigDict(strict=False, extra="allow")

    type: str = Field(
        default="raw",
        description=(
            "Unit category: currency | crypto | date | duration | percentage | "
            "bps | scientific | si | count | probability | custom | raw"
        ),
    )
    code: str = Field(
        default="",
        max_length=50,
        description="Unit identifier: ISO 4217 currency, crypto ticker, SI symbol, etc.",
    )
    precision: int | None = Field(
        None,
        ge=0,
        le=18,
        description="Display decimal places. None = auto-inferred from type/code.",
    )
    scale: float = Field(
        default=1.0,
        description="Multiply raw simulation output by this for display (e.g. 100 for percentage).",
    )
    format: str = Field(
        default="standard",
        description="Display format: standard | compact ($1.2M) | scientific (1.23e-9)",
    )
    base_unit: str = Field(
        default="",
        max_length=50,
        description="Sub-unit label (informational). E.g. 'satoshi' for BTC, 'wei' for ETH.",
    )
    sim_scale: float = Field(
        default=1.0,
        description=(
            "Divide input params by this before simulation. "
            "E.g. sim_scale=1e8 if BTC inputs are in satoshis, converts to whole BTC for Mojo."
        ),
    )

    @classmethod
    def from_shorthand(cls, value: str) -> "UnitSpec":
        """Create from a short-hand string (e.g. 'USD', 'BTC', '%', 'days')."""
        from apps.api_server.services.unit_service import UnitSpec as _UnitSvc

        svc = _UnitSvc.from_raw(value)
        return cls(
            type=svc.type,
            code=svc.code,
            precision=svc.precision,
            scale=svc.scale,
            format=svc.format,
            base_unit=svc.base_unit,
            sim_scale=svc.sim_scale,
        )


# Resolve forward reference now that UnitSpec is defined
VariableSpec.model_rebuild()


class ExpertSimulation(BaseModel):
    """
    Universal simulation specification. No restrictions on domain, variable count,
    or expression complexity. Works for any industry and data type.

    objective_function — complete function reference:
      Arithmetic:   +, -, *, /, ^ (power), % (mod)
      Standard:     sqrt(x), exp(x), ln(x), log(x), log10(x), log2(x), log1p(x),
                    expm1(x), abs(x), floor(x), ceil(x), round(x)
      Min/Max:      min(a,b), max(a,b), clip(v,lo,hi)
      Conditional:  if(cond>0, then_val, else_val)
      Trigonometry: sin(x), cos(x), tan(x), asin(x), acos(x), atan(x)
                    atan2(y,x), sinh(x), cosh(x), tanh(x)
      Special:      erf(x), erfc(x), gamma(x), lgamma(x), sign(x), hypot(a,b)
      Statistical:  norm_cdf(x), norm_pdf(x), norm_ppf(p),
                    t_cdf(x, df), chi2_cdf(x, df), logistic(x), logit(x)
      Combinatorics: factorial(n), comb(n,k), perm(n,k)
      Sequences:    fibonacci(n), fib(n), fib_ratio(n) = F(n)/F(n-1)
      Financial:    npv(rate,cf0,cf1,...), pmt(rate,n,pv), fv(rate,n,pmt,pv),
                    pv(rate,n,pmt), annuity(rate,n), duration(rate,n)
      Constants:    c (speed of light), G (gravity), g (9.81 m/s²),
                    kB (Boltzmann), NA (Avogadro), R (gas), pi, e, phi
      Multi-output: separate objectives with | e.g. "net_profit | risk_score | irr"
      Variables:    any variable name from the variables list as a symbol

    Examples:
      "revenue - cost"
      "max(0, sales * margin - fixed_cost)"
      "npv(0.1, -capex, cf1, cf2, cf3, cf4, cf5)"
      "norm_cdf((mu - threshold) / sigma)"
      "mass * g * height"            # kinetic/potential energy
      "fibonacci(growth_stage)"      # Fibonacci growth model
      "revenue - cost | revenue / cost | norm_cdf(revenue - target)"  # multi-output
    """

    model_config = ConfigDict(strict=False)
    variables: list[VariableSpec] = Field(..., min_length=1)  # no upper limit
    correlations: list[CorrelationSpec] = Field(default_factory=list)
    objective_function: str | None = Field(
        None,
        description=(
            "Expression evaluated each scenario. Supports all math functions. "
            "Multi-output: separate with | pipe character. "
            "Example: 'revenue - cost | (revenue - cost) / revenue * 100 | min(cash_flow, 0)'"
        ),
    )
    scoring: ScoringWeights = Field(default_factory=ScoringWeights)
    # Domain metadata (informational — does not affect simulation)
    domain: str | None = Field(
        None,
        max_length=200,
        description=(
            "Industry/domain hint: finance, medical, manufacturing, aerospace, defense, etc."
        ),
    )
    domain_template: str | None = Field(
        None, max_length=200, description="Name of predefined domain template used (for reference)"
    )
    output_labels: list[str] | None = Field(
        None, description="Labels for multi-output objectives (matches | separator count)"
    )
    output_units: list[str] | None = Field(
        None, description="Physical/currency units for each output. E.g. ['USD', '%', 'years']"
    )
    output_unit_specs: "list[UnitSpec] | None" = Field(
        None,
        description=(
            "Full UnitSpec per output objective (matches | separator count). "
            "Enables formatted_result in the response with currency symbols, "
            "compact notation ($1.2M), scientific notation (1.23e-9 Pa), etc. "
            "Example: [{'type':'currency','code':'USD','format':'compact'}, {'type':'percentage'}]"
        ),
    )


# ── Request models ────────────────────────────────────────────────────────────


class SimulateRequestAuto(BaseModel):
    """Auto-mode simulation request — minimal setup, engine infers distributions."""

    model_config = ConfigDict(
        strict=False,
        json_schema_extra={
            "example": {
                "mode": "auto",
                "simulation_model": "monte_carlo",
                "scenario": {
                    "name": "Product launch decision",
                    "variables": {
                        "revenue": {"low": 80000, "high": 200000},
                        "cost": {"low": 40000, "high": 90000},
                    },
                    "objective": "maximize_net_value",
                },
                "runs": 10000,
            }
        },
    )

    mode: Literal["auto"]
    scenario: AutoScenario
    runs: Annotated[int, Field(ge=100, le=100_000)] = Field(default=10_000)
    seed: Annotated[int, Field(ge=0)] | None = Field(default=None)
    simulation_model: SimulationModel = Field(
        default=SimulationModel.MONTE_CARLO,
        description="Simulation algorithm. All run natively in Mojo.",
    )
    # Model-specific configs (only required for respective simulation_model)
    bootstrap_config: BootstrapConfig | None = None
    scenario_config: ScenarioConfig | None = None
    sensitivity_config: SensitivityConfig | None = None


class SimulateRequestExpert(BaseModel):
    """Expert-mode simulation request — full distribution and objective control."""

    model_config = ConfigDict(
        strict=False,
        json_schema_extra={
            "example": {
                "mode": "expert",
                "simulation_model": "monte_carlo",
                "simulation": {
                    "variables": [
                        {
                            "name": "revenue",
                            "distribution": "lognormal",
                            "params": {"mean": 11.5, "std": 0.4},
                        },
                        {
                            "name": "cost",
                            "distribution": "triangular",
                            "params": {"low": 40000, "mode": 60000, "high": 90000},
                        },
                    ],
                    "objective_function": "revenue - cost",
                    "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
                },
                "runs": 50000,
                "seed": 42,
            }
        },
    )

    mode: Literal["expert"]
    simulation: ExpertSimulation
    runs: Annotated[int, Field(ge=100, le=1_000_000)] = Field(default=10_000)
    seed: Annotated[int, Field(ge=0)] | None = Field(default=None)
    simulation_model: SimulationModel = Field(
        default=SimulationModel.MONTE_CARLO,
        description="Simulation algorithm. All run natively in Mojo.",
    )
    # Model-specific configs
    bootstrap_config: BootstrapConfig | None = None
    scenario_config: ScenarioConfig | None = None
    mcmc_config: MCMCConfig | None = None
    sensitivity_config: SensitivityConfig | None = None
    importance_sampling_config: ImportanceSamplingConfig | None = Field(
        None,
        description=(
            "Config for engine_type='importance_sampling' — exponential tilting "
            "for rare tail events. "
            "Required when simulation_model='importance_sampling'. "
            "Provides unbiased tail probability and CVaR estimates with "
            "100–10,000× fewer samples than brute-force MC."
        ),
    )
    decision_tree_config: DecisionTreeConfig | None = Field(
        None,
        description="Config for engine_type='decision_tree' — multi-layered branching decisions.",
    )
    time_series_config: TimeSeriesConfig | None = Field(
        None,
        description=(
            "Config for engine_type='time_series' — multi-horizon stochastic path simulation. "
            "Models: GBM (stocks/crypto), OU (rates/spreads), arithmetic, compound, custom. "
            "Granularities: ms, s, min, h, day, week, month, quarter, year."
        ),
    )
    include_charts: bool = Field(
        default=False,
        description=(
            "Include pre-computed Vega-Lite chart specs in the response. "
            "When true, adds 'charts' dict with histogram, CDF, tornado (if sensitivity), "
            "fan_chart (if time_series). Ready to pass to vega-embed for instant rendering. "
            "Adds ~5ms to response time."
        ),
    )
    include_histogram: bool = Field(
        default=False,
        description=(
            "Include pre-computed 50-bin histogram data (lighter than full chart spec). "
            "Adds 'histogram_data' to response. Useful for quick distribution preview."
        ),
    )


SimulateRequest = Annotated[
    SimulateRequestAuto | SimulateRequestExpert,
    Discriminator("mode"),
]
