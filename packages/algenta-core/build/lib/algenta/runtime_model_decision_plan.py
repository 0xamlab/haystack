from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _optional_number(data: dict[str, Any], key: str, context: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    return _require_number(data, key, context)


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise TypeError(f"{context}.{key} must be a list of non-empty strings.")
    return [str(item) for item in value]


def _optional_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    if key not in data:
        return []
    return _require_string_list(data, key, context)


@dataclass(frozen=True)
class TokenReductionMetricsOutput:
    raw_repo_token_estimate: int
    evidence_bundle_token_count: int
    reduction_ratio: float

    @classmethod
    def from_api(cls, payload: Any) -> TokenReductionMetricsOutput:
        context = "repository_analysis.token_reduction_metrics"
        data = coerce_payload_mapping(payload)
        raw_repo_token_estimate = data.get("raw_repo_token_estimate")
        if isinstance(raw_repo_token_estimate, bool) or not isinstance(
            raw_repo_token_estimate,
            int,
        ):
            raise TypeError(f"{context}.raw_repo_token_estimate must be an integer.")
        evidence_bundle_token_count = data.get("evidence_bundle_token_count")
        if isinstance(evidence_bundle_token_count, bool) or not isinstance(
            evidence_bundle_token_count, int
        ):
            raise TypeError(f"{context}.evidence_bundle_token_count must be an integer.")
        return cls(
            raw_repo_token_estimate=raw_repo_token_estimate,
            evidence_bundle_token_count=evidence_bundle_token_count,
            reduction_ratio=_require_number(data, "reduction_ratio", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryAnalysisOutput:
    root_cause: str
    planner_model_id: str = ""
    planner_execution_mode: str = ""
    planner_provider_backend: str | None = None
    candidate_fixes: list[str] = field(default_factory=list)
    impacted_services: list[str] = field(default_factory=list)
    impacted_symbols: list[str] = field(default_factory=list)
    likely_failing_tests: list[str] = field(default_factory=list)
    rollback_complexity: str = ""
    blast_radius: str = ""
    workspace_evidence_refs: list[str] = field(default_factory=list)
    generated_patch_ref: str | None = None
    patch_impact_report_ref: str | None = None
    token_reduction_metrics: TokenReductionMetricsOutput = field(
        default_factory=lambda: TokenReductionMetricsOutput(
            raw_repo_token_estimate=0,
            evidence_bundle_token_count=0,
            reduction_ratio=1.0,
        )
    )

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryAnalysisOutput:
        context = "repository_analysis"
        data = coerce_payload_mapping(payload)
        return cls(
            root_cause=_require_string(data, "root_cause", context),
            planner_model_id=_require_string(data, "planner_model_id", context),
            planner_execution_mode=_require_string(data, "planner_execution_mode", context),
            planner_provider_backend=_optional_string(data, "planner_provider_backend", context),
            candidate_fixes=_optional_string_list(data, "candidate_fixes", context),
            impacted_services=_optional_string_list(data, "impacted_services", context),
            impacted_symbols=_optional_string_list(data, "impacted_symbols", context),
            likely_failing_tests=_optional_string_list(data, "likely_failing_tests", context),
            rollback_complexity=_require_string(data, "rollback_complexity", context),
            blast_radius=_require_string(data, "blast_radius", context),
            workspace_evidence_refs=_optional_string_list(data, "workspace_evidence_refs", context),
            generated_patch_ref=_optional_string(data, "generated_patch_ref", context),
            patch_impact_report_ref=_optional_string(data, "patch_impact_report_ref", context),
            token_reduction_metrics=TokenReductionMetricsOutput.from_api(
                data.get("token_reduction_metrics")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RiskProfileOutput:
    p5: float
    p95: float
    probability_of_loss: float
    var_95: float | None = None

    @classmethod
    def from_api(cls, payload: Any) -> RiskProfileOutput:
        context = "risk"
        data = coerce_payload_mapping(payload)
        return cls(
            p5=_require_number(data, "p5", context),
            p95=_require_number(data, "p95", context),
            probability_of_loss=_require_number(data, "probability_of_loss", context),
            var_95=_optional_number(data, "var_95", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DecisionOptionOutput:
    name: str
    rank: int
    expected_value: float
    risk: RiskProfileOutput
    score: float | None = None

    @classmethod
    def from_api(cls, payload: Any) -> DecisionOptionOutput:
        context = "options.item"
        data = coerce_payload_mapping(payload)
        rank = data.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int):
            raise TypeError(f"{context}.rank must be an integer.")
        return cls(
            name=_require_string(data, "name", context),
            rank=rank,
            expected_value=_require_number(data, "expected_value", context),
            risk=RiskProfileOutput.from_api(data.get("risk")),
            score=_optional_number(data, "score", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DecisionPlanOutput:
    recommended_action: str
    confidence: float
    expected_value: float
    risk: RiskProfileOutput
    options: list[DecisionOptionOutput] = field(default_factory=list)
    rationale: str = ""
    integrity: dict[str, Any] | None = None
    calibration: str | None = None
    repository_analysis: RepositoryAnalysisOutput | None = None

    @classmethod
    def from_api(cls, payload: Any) -> DecisionPlanOutput:
        context = "decision_plan"
        data = coerce_payload_mapping(payload)
        raw_options = data.get("options") or []
        if not isinstance(raw_options, list):
            raise TypeError(f"{context}.options must be a list.")
        integrity = data.get("integrity")
        if integrity is not None and not isinstance(integrity, dict):
            raise TypeError(f"{context}.integrity must be a mapping.")
        calibration = data.get("calibration")
        if calibration is not None and (not isinstance(calibration, str) or not calibration):
            raise TypeError(f"{context}.calibration must be a non-empty string.")
        repository_analysis = data.get("repository_analysis")
        if repository_analysis is not None and not isinstance(repository_analysis, dict):
            raise TypeError(f"{context}.repository_analysis must be a mapping.")
        return cls(
            recommended_action=_require_string(data, "recommended_action", context),
            confidence=_require_number(data, "confidence", context),
            expected_value=_require_number(data, "expected_value", context),
            risk=RiskProfileOutput.from_api(data.get("risk")),
            options=[DecisionOptionOutput.from_api(item) for item in raw_options],
            rationale=_require_string(data, "rationale", context),
            integrity=integrity,
            calibration=calibration,
            repository_analysis=(
                RepositoryAnalysisOutput.from_api(repository_analysis)
                if repository_analysis is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
