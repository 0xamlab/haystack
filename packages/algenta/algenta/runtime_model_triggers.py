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


def _require_bool(data: dict[str, Any], key: str, context: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{context}.{key} must be a boolean.")
    return value


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
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


def _require_datetime_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class TriggerConditionOutput:
    source_id: str
    metric_hint: str
    threshold: float
    direction: str
    aggregation: str

    @classmethod
    def from_api(cls, payload: Any) -> TriggerConditionOutput:
        context = "trigger.condition"
        data = coerce_payload_mapping(payload)
        return cls(
            source_id=_require_string(data, "source_id", context),
            metric_hint=_require_string(data, "metric_hint", context),
            threshold=_require_number(data, "threshold", context),
            direction=_require_string(data, "direction", context),
            aggregation=_require_string(data, "aggregation", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class TriggerSummaryOutput:
    trigger_id: str
    org_id: str
    name: str
    status: str
    condition: TriggerConditionOutput
    created_at: str
    description: str | None = None
    webhook_url: str | None = None
    execution_webhook_url: str | None = None
    auto_execute: bool = False
    last_checked_at: str | None = None
    last_fired_at: str | None = None
    last_result_summary: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> TriggerSummaryOutput:
        context = "trigger"
        data = coerce_payload_mapping(payload)
        return cls(
            trigger_id=_require_string(data, "trigger_id", context),
            org_id=_require_string(data, "org_id", context),
            name=_require_string(data, "name", context),
            status=_require_string(data, "status", context),
            condition=TriggerConditionOutput.from_api(data.get("condition")),
            created_at=_require_datetime_text(data, "created_at", context),
            description=_optional_string(data, "description", context),
            webhook_url=_optional_string(data, "webhook_url", context),
            execution_webhook_url=_optional_string(data, "execution_webhook_url", context),
            auto_execute=_require_bool(data, "auto_execute", context),
            last_checked_at=_optional_datetime_text(data, "last_checked_at", context),
            last_fired_at=_optional_datetime_text(data, "last_fired_at", context),
            last_result_summary=_optional_string(data, "last_result_summary", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                **asdict(self),
                "condition": self.condition.to_dict(),
            }
        )


@dataclass(frozen=True)
class TriggerListOutput:
    triggers: list[TriggerSummaryOutput] = field(default_factory=list)
    count: int = 0
    total: int = 0
    page: int = 1
    limit: int = 1
    pages: int = 1

    @classmethod
    def from_api(cls, payload: Any) -> TriggerListOutput:
        context = "triggers"
        data = coerce_payload_mapping(payload)
        raw_items = data.get("triggers")
        if not isinstance(raw_items, list):
            raise TypeError(f"{context}.triggers must be a list.")
        return cls(
            triggers=[TriggerSummaryOutput.from_api(item) for item in raw_items],
            count=_require_integer(data, "count", context),
            total=_require_integer(data, "total", context),
            page=_require_integer(data, "page", context),
            limit=_require_integer(data, "limit", context),
            pages=_require_integer(data, "pages", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "triggers": [item.to_dict() for item in self.triggers],
                "count": self.count,
                "total": self.total,
                "page": self.page,
                "limit": self.limit,
                "pages": self.pages,
            }
        )


@dataclass(frozen=True)
class TriggerFireOutput:
    trigger_id: str
    condition_met: bool
    fired: bool
    message: str
    simulation_run_id: str | None = None
    recommended_action: str | None = None
    expected_value: float | None = None
    confidence: float | None = None
    fired_at: str | None = None
    execution_status: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> TriggerFireOutput:
        context = "trigger_fire"
        data = coerce_payload_mapping(payload)
        return cls(
            trigger_id=_require_string(data, "trigger_id", context),
            condition_met=_require_bool(data, "condition_met", context),
            fired=_require_bool(data, "fired", context),
            message=_require_string(data, "message", context),
            simulation_run_id=_optional_string(data, "simulation_run_id", context),
            recommended_action=_optional_string(data, "recommended_action", context),
            expected_value=(
                _require_number(data, "expected_value", context)
                if data.get("expected_value") is not None
                else None
            ),
            confidence=(
                _require_number(data, "confidence", context)
                if data.get("confidence") is not None
                else None
            ),
            fired_at=_optional_datetime_text(data, "fired_at", context),
            execution_status=_optional_string(data, "execution_status", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class TriggerPauseOutput:
    trigger_id: str
    status: str

    @classmethod
    def from_api(cls, payload: Any) -> TriggerPauseOutput:
        context = "trigger_pause"
        data = coerce_payload_mapping(payload)
        return cls(
            trigger_id=_require_string(data, "trigger_id", context),
            status=_require_string(data, "status", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class TriggerDeleteOutput:
    trigger_id: str
    deleted: bool

    @classmethod
    def from_api(cls, payload: Any) -> TriggerDeleteOutput:
        context = "trigger_delete"
        data = coerce_payload_mapping(payload)
        return cls(
            trigger_id=_require_string(data, "trigger_id", context),
            deleted=_require_bool(data, "deleted", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
