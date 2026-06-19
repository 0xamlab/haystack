"""Request and response schemas for the simplified product API surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "AgentRunRequest",
    "AgentRunResponse",
    "AgentStep",
    "DecisionInput",
    "DecisionRequest",
    "DecisionResponse",
    "ForecastPeriod",
    "ForecastRequest",
    "ForecastResponse",
    "OptimizeConstraint",
    "OptimizeRequest",
    "OptimizeResponse",
    "OptimizeVariable",
    "RetrieveDocument",
    "RetrieveRequest",
    "RetrieveResponse",
    "RetrieveResult",
]


class DecisionInput(BaseModel):
    """A named input value with optional uncertainty range."""

    name: str = Field(..., description="Variable name, e.g. 'revenue'")
    value: float = Field(..., description="Expected / central value")
    low: float | None = Field(None, description="Pessimistic value (optional)")
    high: float | None = Field(None, description="Optimistic value (optional)")
    unit: str | None = Field(None, description="Unit label, e.g. 'USD'")


class DecisionRequest(BaseModel):
    """
    Ask Algenta: given these inputs and constraints, what should I do?

    Algenta tests thousands of possible outcomes and returns the optimal action
    with confidence, risk, and reasoning — no statistics knowledge required.
    """

    inputs: list[DecisionInput] = Field(
        ...,
        description="Business inputs with optional uncertainty ranges",
        examples=[
            [
                {"name": "revenue", "value": 120000, "low": 80000, "high": 180000, "unit": "USD"},
                {"name": "cost", "value": 70000, "low": 50000, "high": 100000, "unit": "USD"},
            ]
        ],
    )
    objective: str = Field(
        "maximize_value",
        description=(
            "What to optimize: maximize_value, minimize_risk, maximize_profit, minimize_cost"
        ),
    )
    risk_tolerance: str = Field(
        "medium",
        description="How much risk is acceptable: low, medium, high",
    )
    scenarios: int = Field(
        10000,
        ge=1000,
        le=1_000_000,
        description="How many scenarios to evaluate (more = higher confidence)",
    )
    engine: str = Field(
        "auto",
        description=(
            "Simulation engine. 'auto' (default) selects the best engine automatically "
            "based on your data shape. Options: monte_carlo, lhs, qmc_sobol, bootstrap, "
            "mcmc, importance_sampling, time_series, sensitivity"
        ),
    )
    label: str | None = Field(None, description="Optional label for this decision")


class DecisionResponse(BaseModel):
    decision_id: str
    action: str = Field(..., description="Recommended action: proceed, pause, reject, or custom")
    confidence: float = Field(..., description="Confidence in this recommendation (0–1)")
    reasoning: str = Field(..., description="Plain-English explanation")
    why: list[str] = Field(..., description="3 crisp reasons behind this recommendation")
    expected_outcome: float = Field(..., description="Expected value in your input units")
    downside_risk: float = Field(..., description="Value at 5th percentile (worst-case)")
    upside_potential: float = Field(..., description="Value at 95th percentile (best-case)")
    probability_of_loss: float = Field(..., description="Probability of negative outcome")
    scenarios_evaluated: int
    latency_ms: float


class AgentStep(BaseModel):
    step: int
    action: str
    tool: str | None = None
    result: str | None = None
    status: str = "completed"


class AgentRunRequest(BaseModel):
    """
    Give Algenta a task. It plans, executes tools, and returns a structured result.

    Drop-in replacement for LangChain / LangGraph agent workflows.
    """

    task: str = Field(..., description="What should the agent do?", min_length=5)
    context: dict[str, Any] | None = Field(None, description="Additional context or data")
    tools: list[str] | None = Field(
        None,
        description="Tools to make available: search, simulate, optimize, calculate, summarize",
    )
    max_steps: int = Field(10, ge=1, le=50, description="Maximum execution steps")
    output_format: str = Field("text", description="Output format: text, json, markdown")


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    result: str | dict[str, Any]
    steps: list[AgentStep]
    tools_used: list[str]
    latency_ms: float


class OptimizeVariable(BaseModel):
    name: str
    min: float
    max: float
    step: float | None = None
    unit: str | None = None


class OptimizeConstraint(BaseModel):
    expression: str = Field(..., description="e.g. 'margin > 0.2', 'cost < 50000'")
    required: bool = True


class OptimizeRequest(BaseModel):
    """
    Find the best value given inputs, constraints, and an objective.

    Use cases: pricing, routing, scheduling, resource allocation.
    No math required — just describe what you're optimizing.
    """

    objective: str = Field(
        ...,
        description=(
            "What to optimize, e.g. 'maximize profit', 'minimize cost', 'maximize throughput'"
        ),
    )
    variables: list[OptimizeVariable] = Field(
        ...,
        description="Variables to optimize with their allowed ranges",
    )
    constraints: list[OptimizeConstraint] = Field(
        default_factory=list,
        description="Business constraints that must be satisfied",
    )
    iterations: int = Field(1000, ge=100, le=100_000, description="Search iterations")
    engine: str = Field(
        "auto",
        description=(
            "Simulation engine. 'auto' selects the best engine automatically. "
            "Options: lhs (recommended for optimization), monte_carlo, qmc_sobol"
        ),
    )


class OptimizeResponse(BaseModel):
    optimization_id: str
    status: str
    optimal_values: dict[str, float]
    objective_value: float
    improvement_vs_midpoint: float = Field(
        ...,
        description="% improvement vs naive midpoint solution",
    )
    constraints_satisfied: bool
    iterations_run: int
    latency_ms: float


class RetrieveDocument(BaseModel):
    id: str | None = None
    content: str
    metadata: dict[str, Any] | None = None


class RetrieveRequest(BaseModel):
    """
    Search your knowledge base and get ranked, relevant results.

    Plug-and-play enterprise search and RAG pipeline.
    Pass documents inline or reference a connected collection.
    """

    query: str = Field(..., description="What are you looking for?", min_length=3)
    documents: list[RetrieveDocument] | None = Field(
        None, description="Documents to search (inline mode)"
    )
    collection_id: str | None = Field(None, description="ID of a connected data source to search")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")
    rerank: bool = Field(True, description="Apply cross-encoder reranking for higher accuracy")


class RetrieveResult(BaseModel):
    rank: int
    document_id: str | None
    content: str
    relevance_score: float
    snippet: str


class RetrieveResponse(BaseModel):
    retrieval_id: str
    query: str
    results: list[RetrieveResult]
    total_searched: int
    latency_ms: float


class ForecastRequest(BaseModel):
    """
    Forecast what will happen based on historical data and business drivers.

    Use cases: demand forecasting, revenue projection, capacity planning.
    """

    metric: str = Field(..., description="What you're forecasting, e.g. 'monthly_revenue'")
    history: list[float] = Field(
        ...,
        description="Historical values (most recent last)",
        min_length=3,
        max_length=1000,
    )
    horizon: int = Field(12, ge=1, le=120, description="How many periods ahead to forecast")
    seasonality: bool = Field(True, description="Account for seasonal patterns")
    confidence_level: float = Field(0.90, ge=0.5, le=0.99, description="Confidence interval width")


class ForecastPeriod(BaseModel):
    period: int
    forecast: float
    lower_bound: float
    upper_bound: float
    trend: str


class ForecastResponse(BaseModel):
    forecast_id: str
    metric: str
    baseline: float = Field(..., description="Most recent historical value")
    forecast_mean: float = Field(..., description="Expected value at end of horizon")
    total_change_pct: float = Field(..., description="Expected % change over horizon")
    periods: list[ForecastPeriod]
    scenarios_evaluated: int
    latency_ms: float
