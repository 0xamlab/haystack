from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
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
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _optional_integer(data: dict[str, Any], key: str, context: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _require_datetime_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_datetime_text(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class DecisionLogOutput:
    id: str
    org_id: str
    run_id: str | None
    context: str | None
    chosen_action: str
    options_considered: list[str] | None
    expected_value: float | None
    confidence: float | None
    rationale: str | None
    risk_p5: float | None
    risk_p95: float | None
    risk_pol: float | None
    request_hash: str | None
    result_hash: str | None
    policy_snapshot_id: str | None
    schema_snapshot_id: str | None
    manifest_version: str | None
    actual_outcome: float | None
    outcome_delta: float | None
    outcome_notes: str | None
    outcome_recorded_at: str | None
    executed_at: str | None
    execution_status: str | None
    execution_webhook_url: str | None
    execution_response_code: int | None
    created_at: str
    updated_at: str

    @classmethod
    def from_api(cls, payload: Any) -> DecisionLogOutput:
        context = "decision_log"
        data = coerce_payload_mapping(payload)
        raw_options = data.get("options_considered")
        if raw_options is not None:
            if not isinstance(raw_options, list) or not all(
                isinstance(item, str) and item for item in raw_options
            ):
                raise TypeError(f"{context}.options_considered must be a list of strings.")
        return cls(
            id=_require_string(data, "id", context),
            org_id=_require_string(data, "org_id", context),
            run_id=_optional_string(data, "run_id", context),
            context=_optional_string(data, "context", context),
            chosen_action=_require_string(data, "chosen_action", context),
            options_considered=raw_options,
            expected_value=_optional_number(data, "expected_value", context),
            confidence=_optional_number(data, "confidence", context),
            rationale=_optional_string(data, "rationale", context),
            risk_p5=_optional_number(data, "risk_p5", context),
            risk_p95=_optional_number(data, "risk_p95", context),
            risk_pol=_optional_number(data, "risk_pol", context),
            request_hash=_optional_string(data, "request_hash", context),
            result_hash=_optional_string(data, "result_hash", context),
            policy_snapshot_id=_optional_string(data, "policy_snapshot_id", context),
            schema_snapshot_id=_optional_string(data, "schema_snapshot_id", context),
            manifest_version=_optional_string(data, "manifest_version", context),
            actual_outcome=_optional_number(data, "actual_outcome", context),
            outcome_delta=_optional_number(data, "outcome_delta", context),
            outcome_notes=_optional_string(data, "outcome_notes", context),
            outcome_recorded_at=_optional_datetime_text(data, "outcome_recorded_at", context),
            executed_at=_optional_datetime_text(data, "executed_at", context),
            execution_status=_optional_string(data, "execution_status", context),
            execution_webhook_url=_optional_string(data, "execution_webhook_url", context),
            execution_response_code=_optional_integer(data, "execution_response_code", context),
            created_at=_require_datetime_text(data, "created_at", context),
            updated_at=_require_datetime_text(data, "updated_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DecisionListOutput:
    decisions: list[DecisionLogOutput] = field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 1
    pages: int = 1
    page_size: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> DecisionListOutput:
        context = "decision_list"
        data = coerce_payload_mapping(payload)
        raw_decisions = data.get("decisions")
        if not isinstance(raw_decisions, list):
            raise TypeError(f"{context}.decisions must be a list.")
        return cls(
            decisions=[DecisionLogOutput.from_api(item) for item in raw_decisions],
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
            page_size=_require_integer(data, "page_size", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "decisions": [item.to_dict() for item in self.decisions],
                "total": self.total,
                "page": self.page,
                "limit": self.limit,
                "pages": self.pages,
                "page_size": self.page_size,
            }
        )


@dataclass(frozen=True)
class ExecutionReceiptOutput:
    decision_id: str
    webhook_url: str
    execution_status: str
    response_code: int | None
    executed_at: str
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    payload_summary: dict[str, Any]
    safety_overridden: bool = False

    @classmethod
    def from_api(cls, payload: Any) -> ExecutionReceiptOutput:
        context = "execution_receipt"
        data = coerce_payload_mapping(payload)
        payload_summary = data.get("payload_summary")
        if not isinstance(payload_summary, dict):
            raise TypeError(f"{context}.payload_summary must be a mapping.")
        safety_overridden = data.get("safety_overridden", False)
        if not isinstance(safety_overridden, bool):
            raise TypeError(f"{context}.safety_overridden must be a boolean.")
        return cls(
            decision_id=_require_string(data, "decision_id", context),
            webhook_url=_require_string(data, "webhook_url", context),
            execution_status=_require_string(data, "execution_status", context),
            response_code=_optional_integer(data, "response_code", context),
            executed_at=_require_datetime_text(data, "executed_at", context),
            policy_snapshot_id=_require_string(data, "policy_snapshot_id", context),
            schema_snapshot_id=_require_string(data, "schema_snapshot_id", context),
            manifest_version=_require_string(data, "manifest_version", context),
            payload_summary=payload_summary,
            safety_overridden=safety_overridden,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
