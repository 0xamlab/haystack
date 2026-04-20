"""Response schemas — the Decision Envelope returned by all simulation endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PercentileSummary(BaseModel):
    """Percentile breakdown of simulation output distribution."""
    model_config = ConfigDict(strict=True)

    p5: float = Field(..., description="5th percentile (downside case)")
    p25: float = Field(..., description="25th percentile")
    p50: float = Field(..., description="Median")
    p75: float = Field(..., description="75th percentile")
    p95: float = Field(..., description="95th percentile (upside case)")


class MetricsSummary(BaseModel):
    """Core statistical metrics from the simulation."""
    model_config = ConfigDict(strict=True)

    expected_value: float = Field(..., description="Mean of the simulated distribution")
    median: float = Field(..., description="Median of the simulated distribution")
    std_deviation: float = Field(..., description="Standard deviation")
    variance: float = Field(..., description="Variance")
    probability_of_loss: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of scenarios with negative outcome"
    )
    var_95: float | None = Field(
        None, description="Value at Risk at 95% confidence (5th percentile loss)"
    )
    cvar_95: float | None = Field(
        None, description="Conditional VaR — average loss beyond VaR threshold"
    )


class RunMetadata(BaseModel):
    """Execution and billing metadata."""
    model_config = ConfigDict(strict=True)

    mode: str = Field(..., description="'auto' or 'expert'")
    seed: int | None = Field(None, description="Random seed used. Null if unseeded.")
    billing_units: int = Field(..., description="Number of billing units consumed")
    engine_version: str = Field(..., description="Mojo engine version that produced this result")


class DecisionEnvelope(BaseModel):
    """
    The full decision output returned by /v1/simulate, /v1/recommend, and /v1/score.

    Contains the recommended action, confidence, statistical metrics,
    percentile breakdown, and execution metadata.
    """
    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "example": {
                "run_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "status": "completed",
                "engine_version": "0.1.0",
                "recommended_action": "proceed",
                "confidence": 0.78,
                "rationale": (
                    "Expected net value is positive in 78% of simulated scenarios. "
                    "Downside risk is bounded by the cost floor."
                ),
                "metrics": {
                    "expected_value": 62400.0,
                    "median": 58200.0,
                    "std_deviation": 18300.0,
                    "variance": 334890000.0,
                    "probability_of_loss": 0.22,
                    "var_95": -12000.0,
                    "cvar_95": None,
                },
                "percentiles": {
                    "p5": 18000.0,
                    "p25": 44000.0,
                    "p50": 58200.0,
                    "p75": 78000.0,
                    "p95": 105000.0,
                },
                "scenarios_run": 10000,
                "execution_ms": 87,
                "metadata": {
                    "mode": "auto",
                    "seed": None,
                    "billing_units": 1,
                    "engine_version": "0.1.0",
                },
            }
        },
    )

    run_id: uuid.UUID = Field(..., description="Unique identifier for this simulation run")
    status: str = Field(default="completed", description="Run status")
    engine_version: str = Field(..., description="Version of the Mojo engine used")

    # Decision output
    recommended_action: str = Field(
        ...,
        description="'proceed', 'caution', 'reject', or custom label",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the recommendation (0–1)"
    )
    rationale: str = Field(..., description="Human-readable explanation of the recommendation")

    # Statistics
    metrics: MetricsSummary
    percentiles: PercentileSummary

    # Execution metadata
    scenarios_run: int = Field(..., description="Number of Monte Carlo iterations executed")
    execution_ms: int = Field(..., description="Wall-clock time for simulation in milliseconds")
    metadata: RunMetadata

    # Optional enrichment (populated by /recommend and /score endpoints)
    scenario_ranking: list[dict] | None = Field(
        None, description="Ranked list of scenarios (for /recommend)"
    )
    sensitivity_ranking: list[dict] | None = Field(
        None, description="Variables ranked by influence on outcome"
    )
    score: float | None = Field(
        None, ge=0.0, le=1.0, description="Decision score (for /score endpoint)"
    )
    score_breakdown: dict | None = Field(
        None, description="Breakdown of score components"
    )
    created_at: datetime | None = Field(None, description="Timestamp of run creation")
