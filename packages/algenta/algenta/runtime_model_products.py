from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _require_bool(data: dict[str, Any], key: str, context: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{context}.{key} must be a boolean.")
    return value


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{context}.{key} must be a string when provided.")
    return value


@dataclass(frozen=True)
class ProductDecisionOutput:
    decision_id: str
    action: str
    confidence: float
    reasoning: str
    why: list[str] = field(default_factory=list)
    expected_outcome: float = 0.0
    downside_risk: float = 0.0
    upside_potential: float = 0.0
    probability_of_loss: float = 0.0
    scenarios_evaluated: int = 0
    latency_ms: float = 0.0

    @classmethod
    def from_api(cls, payload: Any) -> ProductDecisionOutput:
        context = "product_decision"
        data = coerce_payload_mapping(payload)
        raw_why = data.get("why")
        if not isinstance(raw_why, list) or not all(isinstance(item, str) for item in raw_why):
            raise TypeError(f"{context}.why must be a list of strings.")
        return cls(
            decision_id=_require_string(data, "decision_id", context),
            action=_require_string(data, "action", context),
            confidence=_require_number(data, "confidence", context),
            reasoning=_require_string(data, "reasoning", context),
            why=raw_why,
            expected_outcome=_require_number(data, "expected_outcome", context),
            downside_risk=_require_number(data, "downside_risk", context),
            upside_potential=_require_number(data, "upside_potential", context),
            probability_of_loss=_require_number(data, "probability_of_loss", context),
            scenarios_evaluated=_require_integer(data, "scenarios_evaluated", context),
            latency_ms=_require_number(data, "latency_ms", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ProductAgentStepOutput:
    step: int
    action: str
    tool: str | None = None
    result: str | None = None
    status: str = "completed"

    @classmethod
    def from_api(cls, payload: Any) -> ProductAgentStepOutput:
        context = "product_agent_step"
        data = coerce_payload_mapping(payload)
        return cls(
            step=_require_integer(data, "step", context),
            action=_require_string(data, "action", context),
            tool=_optional_string(data, "tool", context),
            result=_optional_string(data, "result", context),
            status=_require_string(data, "status", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ProductAgentRunOutput:
    run_id: str
    status: str
    result: str | dict[str, Any]
    steps: list[ProductAgentStepOutput] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    @classmethod
    def from_api(cls, payload: Any) -> ProductAgentRunOutput:
        context = "product_agent_run"
        data = coerce_payload_mapping(payload)
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list):
            raise TypeError(f"{context}.steps must be a list.")
        raw_tools = data.get("tools_used")
        if not isinstance(raw_tools, list) or not all(isinstance(item, str) for item in raw_tools):
            raise TypeError(f"{context}.tools_used must be a list of strings.")
        result = data.get("result")
        if not isinstance(result, (str, dict)):
            raise TypeError(f"{context}.result must be a string or object.")
        return cls(
            run_id=_require_string(data, "run_id", context),
            status=_require_string(data, "status", context),
            result=result,
            steps=[ProductAgentStepOutput.from_api(item) for item in raw_steps],
            tools_used=raw_tools,
            latency_ms=_require_number(data, "latency_ms", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "run_id": self.run_id,
                "status": self.status,
                "result": self.result,
                "steps": [step.to_dict() for step in self.steps],
                "tools_used": self.tools_used,
                "latency_ms": self.latency_ms,
            }
        )


@dataclass(frozen=True)
class ProductOptimizeOutput:
    optimization_id: str
    status: str
    optimal_values: dict[str, float] = field(default_factory=dict)
    objective_value: float = 0.0
    improvement_vs_midpoint: float = 0.0
    constraints_satisfied: bool = False
    iterations_run: int = 0
    latency_ms: float = 0.0

    @classmethod
    def from_api(cls, payload: Any) -> ProductOptimizeOutput:
        context = "product_optimize"
        data = coerce_payload_mapping(payload)
        raw_optimal_values = data.get("optimal_values")
        if not isinstance(raw_optimal_values, dict) or not all(
            isinstance(key, str) and isinstance(value, (int, float))
            for key, value in raw_optimal_values.items()
        ):
            raise TypeError(f"{context}.optimal_values must be a mapping of numbers.")
        return cls(
            optimization_id=_require_string(data, "optimization_id", context),
            status=_require_string(data, "status", context),
            optimal_values={key: float(value) for key, value in raw_optimal_values.items()},
            objective_value=_require_number(data, "objective_value", context),
            improvement_vs_midpoint=_require_number(data, "improvement_vs_midpoint", context),
            constraints_satisfied=_require_bool(data, "constraints_satisfied", context),
            iterations_run=_require_integer(data, "iterations_run", context),
            latency_ms=_require_number(data, "latency_ms", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ProductRetrieveHitOutput:
    rank: int
    document_id: str | None
    content: str
    relevance_score: float
    snippet: str

    @classmethod
    def from_api(cls, payload: Any) -> ProductRetrieveHitOutput:
        context = "product_retrieve_hit"
        data = coerce_payload_mapping(payload)
        return cls(
            rank=_require_integer(data, "rank", context),
            document_id=_optional_string(data, "document_id", context),
            content=_require_string(data, "content", context),
            relevance_score=_require_number(data, "relevance_score", context),
            snippet=_require_string(data, "snippet", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ProductRetrieveOutput:
    retrieval_id: str
    query: str
    results: list[ProductRetrieveHitOutput] = field(default_factory=list)
    total_searched: int = 0
    latency_ms: float = 0.0

    @classmethod
    def from_api(cls, payload: Any) -> ProductRetrieveOutput:
        context = "product_retrieve"
        data = coerce_payload_mapping(payload)
        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            raise TypeError(f"{context}.results must be a list.")
        return cls(
            retrieval_id=_require_string(data, "retrieval_id", context),
            query=_require_string(data, "query", context),
            results=[ProductRetrieveHitOutput.from_api(item) for item in raw_results],
            total_searched=_require_integer(data, "total_searched", context),
            latency_ms=_require_number(data, "latency_ms", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "retrieval_id": self.retrieval_id,
                "query": self.query,
                "results": [result.to_dict() for result in self.results],
                "total_searched": self.total_searched,
                "latency_ms": self.latency_ms,
            }
        )


@dataclass(frozen=True)
class ProductForecastPeriodOutput:
    period: int
    forecast: float
    lower_bound: float
    upper_bound: float
    trend: str

    @classmethod
    def from_api(cls, payload: Any) -> ProductForecastPeriodOutput:
        context = "product_forecast_period"
        data = coerce_payload_mapping(payload)
        return cls(
            period=_require_integer(data, "period", context),
            forecast=_require_number(data, "forecast", context),
            lower_bound=_require_number(data, "lower_bound", context),
            upper_bound=_require_number(data, "upper_bound", context),
            trend=_require_string(data, "trend", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ProductForecastOutput:
    forecast_id: str
    metric: str
    baseline: float
    forecast_mean: float
    total_change_pct: float
    periods: list[ProductForecastPeriodOutput] = field(default_factory=list)
    scenarios_evaluated: int = 0
    latency_ms: float = 0.0

    @classmethod
    def from_api(cls, payload: Any) -> ProductForecastOutput:
        context = "product_forecast"
        data = coerce_payload_mapping(payload)
        raw_periods = data.get("periods")
        if not isinstance(raw_periods, list):
            raise TypeError(f"{context}.periods must be a list.")
        return cls(
            forecast_id=_require_string(data, "forecast_id", context),
            metric=_require_string(data, "metric", context),
            baseline=_require_number(data, "baseline", context),
            forecast_mean=_require_number(data, "forecast_mean", context),
            total_change_pct=_require_number(data, "total_change_pct", context),
            periods=[ProductForecastPeriodOutput.from_api(item) for item in raw_periods],
            scenarios_evaluated=_require_integer(data, "scenarios_evaluated", context),
            latency_ms=_require_number(data, "latency_ms", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "forecast_id": self.forecast_id,
                "metric": self.metric,
                "baseline": self.baseline,
                "forecast_mean": self.forecast_mean,
                "total_change_pct": self.total_change_pct,
                "periods": [period.to_dict() for period in self.periods],
                "scenarios_evaluated": self.scenarios_evaluated,
                "latency_ms": self.latency_ms,
            }
        )
