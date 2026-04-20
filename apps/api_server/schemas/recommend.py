"""Request/response schemas for /v1/recommend, /v1/score, /v1/batch, /v1/compare."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from apps.api_server.schemas.response import DecisionEnvelope, DecisionPlan
from apps.api_server.schemas.simulate import (
    SimulateRequest,
)

# ─── /v1/recommend ────────────────────────────────────────────────────────────

class NamedAction(BaseModel):
    """A named simulation scenario for comparison."""
    model_config = ConfigDict(strict=False)

    name: str = Field(..., min_length=1, max_length=200)
    request: SimulateRequest


class RecommendRequest(BaseModel):
    """Request body for /v1/recommend — compare 2-10 named actions."""
    model_config = ConfigDict(strict=False)

    actions: list[NamedAction] = Field(..., min_length=2, max_length=10)
    runs: Annotated[int, Field(ge=100, le=100_000)] = Field(default=10_000)
    seed: Annotated[int, Field(ge=0)] | None = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "actions": [
                    {
                        "name": "launch_product_a",
                        "request": {
                            "mode": "auto",
                            "scenario": {
                                "variables": {"revenue": {"low": 80000, "high": 200000}},
                                "objective": "maximize_net_value",
                            },
                        },
                    },
                    {
                        "name": "launch_product_b",
                        "request": {
                            "mode": "auto",
                            "scenario": {
                                "variables": {"revenue": {"low": 50000, "high": 300000}},
                                "objective": "maximize_net_value",
                            },
                        },
                    },
                ],
                "runs": 10000,
            }
        }
    )


class ActionResult(BaseModel):
    """Result for a single action in a recommend response."""
    name: str
    rank: int
    envelope: DecisionEnvelope
    expected_value: float
    probability_of_loss: float
    score: float


class RecommendResponse(BaseModel):
    """Response from /v1/recommend."""
    recommended_action: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str
    action_results: list[ActionResult]
    total_actions: int
    decision_plan: DecisionPlan | None = Field(
        None,
        description=(
            "Structured decision summary with all ranked options. "
            "Best entry point for LLMs and dashboards — contains recommended_action, "
            "expected_value, risk (p5/p95/PoL), all options ranked, rationale, and integrity hashes."
        ),
    )


# ─── /v1/score ────────────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    """Request body for /v1/score."""
    model_config = ConfigDict(strict=False)

    request: SimulateRequest
    scoring_weights: dict[str, float] | None = Field(
        default=None,
        description="Custom scoring weights. Keys: 'expected_value', 'downside_risk'. Must sum to 1.0.",
    )


class ScoreResponse(BaseModel):
    """Response from /v1/score — DecisionEnvelope with score breakdown."""
    envelope: DecisionEnvelope
    score: float = Field(..., ge=0.0, le=1.0)
    score_breakdown: dict[str, float]


# ─── /v1/batch ────────────────────────────────────────────────────────────────

class BatchRequest(BaseModel):
    """Request body for /v1/batch."""
    model_config = ConfigDict(strict=False)

    items: list[SimulateRequest] = Field(..., min_length=1, max_length=100)


class BatchItemResult(BaseModel):
    """Result for one item in a batch."""
    index: int
    success: bool
    envelope: DecisionEnvelope | None = None
    error: str | None = None


class BatchResponse(BaseModel):
    """Response from /v1/batch."""
    total: int
    succeeded: int
    failed: int
    results: list[BatchItemResult]


# ─── /v1/compare ──────────────────────────────────────────────────────────────

class NamedScenario(BaseModel):
    """A named scenario for side-by-side comparison."""
    model_config = ConfigDict(strict=False)

    name: str = Field(..., min_length=1, max_length=200)
    request: SimulateRequest


class CompareRequest(BaseModel):
    """Request body for /v1/compare."""
    model_config = ConfigDict(strict=False)

    scenarios: list[NamedScenario] = Field(..., min_length=2, max_length=10)
    runs: Annotated[int, Field(ge=100, le=100_000)] = Field(default=10_000)
    seed: Annotated[int, Field(ge=0)] | None = Field(default=None)


class ComparisonDelta(BaseModel):
    """Delta between a scenario and the best scenario."""
    expected_value_delta: float
    probability_of_loss_delta: float
    score_delta: float


class ScenarioComparison(BaseModel):
    """One scenario in the comparison table."""
    name: str
    envelope: DecisionEnvelope
    delta_vs_best: ComparisonDelta


class CompareResponse(BaseModel):
    """Response from /v1/compare."""
    winner: str
    margin: ComparisonDelta
    scenarios: list[ScenarioComparison]
