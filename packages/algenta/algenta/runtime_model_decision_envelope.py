from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from algenta.runtime_model_common import coerce_payload_mapping, jsonable
from algenta.runtime_model_decision_plan import DecisionPlanOutput


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_identifier_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, UUID):
        return str(value)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_number(data: dict[str, Any], key: str, context: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    return _require_number(data, key, context)


def _optional_datetime_text(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_mapping(value: Any, context: str) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        return coerce_payload_mapping(value)
    except Exception as exc:  # noqa: BLE001
        raise TypeError(f"{context} must be a mapping.") from exc


def _optional_list_of_mappings(value: Any, context: str) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError(f"{context} must be a list.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        try:
            normalized.append(coerce_payload_mapping(item))
        except Exception as exc:  # noqa: BLE001
            raise TypeError(f"{context}.{index} must be a mapping.") from exc
    return normalized


@dataclass(frozen=True)
class MetricsSummaryOutput:
    expected_value: float
    median: float
    std_deviation: float
    variance: float
    probability_of_loss: float
    var_95: float | None = None
    cvar_95: float | None = None

    @classmethod
    def from_api(cls, payload: Any) -> MetricsSummaryOutput:
        context = "metrics"
        data = coerce_payload_mapping(payload)
        return cls(
            expected_value=_require_number(data, "expected_value", context),
            median=_require_number(data, "median", context),
            std_deviation=_require_number(data, "std_deviation", context),
            variance=_require_number(data, "variance", context),
            probability_of_loss=_require_number(data, "probability_of_loss", context),
            var_95=_optional_number(data, "var_95", context),
            cvar_95=_optional_number(data, "cvar_95", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class PercentileSummaryOutput:
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    p10: float | None = None
    p90: float | None = None
    p99: float | None = None

    @classmethod
    def from_api(cls, payload: Any) -> PercentileSummaryOutput:
        context = "percentiles"
        data = coerce_payload_mapping(payload)
        return cls(
            p5=_require_number(data, "p5", context),
            p25=_require_number(data, "p25", context),
            p50=_require_number(data, "p50", context),
            p75=_require_number(data, "p75", context),
            p95=_require_number(data, "p95", context),
            p10=_optional_number(data, "p10", context),
            p90=_optional_number(data, "p90", context),
            p99=_optional_number(data, "p99", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RunMetadataOutput:
    mode: str
    billing_units: int
    engine_version: str
    seed: int | None = None

    @classmethod
    def from_api(cls, payload: Any) -> RunMetadataOutput:
        context = "metadata"
        data = coerce_payload_mapping(payload)
        seed = data.get("seed")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise TypeError(f"{context}.seed must be an integer.")
        return cls(
            mode=_require_string(data, "mode", context),
            billing_units=_require_integer(data, "billing_units", context),
            engine_version=_require_string(data, "engine_version", context),
            seed=seed,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DecisionEnvelopeOutput:
    run_id: str
    status: str
    engine_version: str
    recommended_action: str
    confidence: float
    rationale: str
    metrics: MetricsSummaryOutput
    percentiles: PercentileSummaryOutput
    scenarios_run: int
    execution_ms: int
    metadata: RunMetadataOutput
    simulation_model: str | None = None
    engine_type: str | None = None
    simulation_class: str | None = None
    model_revision: str | None = None
    assumptions_hash: str | None = None
    validated_inputs: dict[str, Any] | None = None
    confidence_interval: dict[str, Any] | None = None
    request_id: str | None = None
    score: float | None = None
    score_breakdown: dict[str, Any] | None = None
    scenario_ranking: list[dict[str, Any]] | None = None
    sensitivity_ranking: list[dict[str, Any]] | None = None
    request_hash: str | None = None
    result_hash: str | None = None
    created_at: str | None = None
    decision_plan: DecisionPlanOutput | None = None

    @classmethod
    def from_api(cls, payload: Any) -> DecisionEnvelopeOutput:
        context = "decision_envelope"
        data = coerce_payload_mapping(payload)
        return cls(
            run_id=_require_identifier_text(data, "run_id", context),
            status=_require_string(data, "status", context),
            engine_version=_require_string(data, "engine_version", context),
            recommended_action=_require_string(data, "recommended_action", context),
            confidence=_require_number(data, "confidence", context),
            rationale=_require_string(data, "rationale", context),
            metrics=MetricsSummaryOutput.from_api(data.get("metrics")),
            percentiles=PercentileSummaryOutput.from_api(data.get("percentiles")),
            scenarios_run=_require_integer(data, "scenarios_run", context),
            execution_ms=_require_integer(data, "execution_ms", context),
            metadata=RunMetadataOutput.from_api(data.get("metadata")),
            simulation_model=_optional_string(data, "simulation_model", context),
            engine_type=_optional_string(data, "engine_type", context),
            simulation_class=_optional_string(data, "simulation_class", context),
            model_revision=_optional_string(data, "model_revision", context),
            assumptions_hash=_optional_string(data, "assumptions_hash", context),
            validated_inputs=_optional_mapping(
                data.get("validated_inputs"),
                f"{context}.validated_inputs",
            ),
            confidence_interval=_optional_mapping(
                data.get("confidence_interval"),
                f"{context}.confidence_interval",
            ),
            request_id=_optional_string(data, "request_id", context),
            score=_optional_number(data, "score", context),
            score_breakdown=_optional_mapping(
                data.get("score_breakdown"),
                f"{context}.score_breakdown",
            ),
            scenario_ranking=_optional_list_of_mappings(
                data.get("scenario_ranking"),
                f"{context}.scenario_ranking",
            ),
            sensitivity_ranking=_optional_list_of_mappings(
                data.get("sensitivity_ranking"),
                f"{context}.sensitivity_ranking",
            ),
            request_hash=_optional_string(data, "request_hash", context),
            result_hash=_optional_string(data, "result_hash", context),
            created_at=_optional_datetime_text(data, "created_at", context),
            decision_plan=(
                DecisionPlanOutput.from_api(data.get("decision_plan"))
                if data.get("decision_plan") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
