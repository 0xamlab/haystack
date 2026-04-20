"""Request schemas for simulation endpoints."""
import enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DistributionType(str, enum.Enum):
    NORMAL = "normal"
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    LOGNORMAL = "lognormal"
    FIXED = "fixed"


class ObjectiveType(str, enum.Enum):
    MAXIMIZE_NET_VALUE = "maximize_net_value"
    MAXIMIZE_REVENUE = "maximize_revenue"
    MINIMIZE_COST = "minimize_cost"
    MINIMIZE_RISK = "minimize_risk"
    MAXIMIZE_SCORE = "maximize_score"


# ─── Auto Mode ────────────────────────────────────────────────────────────────

class AutoVariable(BaseModel):
    """Simplified variable definition for auto mode — just low/high bounds."""
    model_config = ConfigDict(strict=True)

    low: float = Field(..., description="Lower bound / pessimistic value")
    high: float = Field(..., gt=0, description="Upper bound / optimistic value")
    description: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def high_must_exceed_low(self) -> "AutoVariable":
        if self.high <= self.low:
            raise ValueError("'high' must be greater than 'low'")
        return self


class AutoScenario(BaseModel):
    """Auto mode scenario — minimal input, engine infers distributions."""
    model_config = ConfigDict(strict=True)

    name: str | None = Field(None, max_length=200, description="Optional scenario label")
    variables: dict[str, AutoVariable] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Named variables with low/high bounds",
    )
    objective: ObjectiveType = Field(
        ...,
        description="Optimization objective — determines scoring method",
    )


class SimulateRequestAuto(BaseModel):
    """Simulation request in auto mode — no domain knowledge required."""
    model_config = ConfigDict(strict=True)

    mode: Literal["auto"]
    scenario: AutoScenario
    runs: Annotated[int, Field(ge=100, le=100_000)] = Field(
        default=10_000,
        description="Number of Monte Carlo simulation iterations",
    )
    seed: Annotated[int, Field(ge=0)] | None = Field(
        default=None,
        description="Random seed for reproducible results. Null = random seed.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "auto",
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
        }
    )


# ─── Expert Mode ──────────────────────────────────────────────────────────────

class DistributionParams(BaseModel):
    """Distribution-specific parameters."""
    model_config = ConfigDict(strict=True, extra="allow")

    # Normal / Lognormal
    mean: float | None = None
    std: float | None = None
    # Uniform
    low: float | None = None
    high: float | None = None
    # Triangular
    mode: float | None = None
    # Fixed
    value: float | None = None


class VariableSpec(BaseModel):
    """Full variable specification for expert mode."""
    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=100)
    distribution: DistributionType
    params: DistributionParams
    unit: str | None = Field(None, max_length=50, description="Optional unit label (e.g. USD)")

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
        return self


class CorrelationSpec(BaseModel):
    """Correlation between two named variables."""
    model_config = ConfigDict(strict=True)

    variables: list[str] = Field(..., min_length=2, max_length=2)
    coefficient: float = Field(..., ge=-1.0, le=1.0)


class ScoringWeights(BaseModel):
    """Custom scoring weights for the decision score calculation."""
    model_config = ConfigDict(strict=True)

    expected_value: float = Field(default=0.6, ge=0.0, le=1.0)
    downside_risk: float = Field(default=0.4, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> "ScoringWeights":
        total = self.expected_value + self.downside_risk
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total:.3f}")
        return self


class ExpertSimulation(BaseModel):
    """Full expert-mode simulation specification."""
    model_config = ConfigDict(strict=True)

    variables: list[VariableSpec] = Field(..., min_length=1, max_length=500)
    correlations: list[CorrelationSpec] = Field(default_factory=list)
    objective_function: str | None = Field(
        None,
        max_length=500,
        description="Expression string using variable names (e.g. 'revenue - cost')",
    )
    scoring: ScoringWeights = Field(default_factory=ScoringWeights)


class SimulateRequestExpert(BaseModel):
    """Simulation request in expert mode — full control over distributions."""
    model_config = ConfigDict(strict=True)

    mode: Literal["expert"]
    simulation: ExpertSimulation
    runs: Annotated[int, Field(ge=100, le=1_000_000)] = Field(default=10_000)
    seed: Annotated[int, Field(ge=0)] | None = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "expert",
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
        }
    )


# ─── Union request type ───────────────────────────────────────────────────────

SimulateRequest = SimulateRequestAuto | SimulateRequestExpert
