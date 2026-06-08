from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping

_FILTER_SUPPORTED_OPS = frozenset({"eq", "in", "gt", "gte", "lt", "lte", "is_null", "is_not_null"})
_FILTER_NULL_OPS = frozenset({"is_null", "is_not_null"})


def _normalize_optional_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


@dataclass(frozen=True)
class QueryFilterCondition:
    op: str
    column: str | None = None
    dimension_hint: str | None = None
    value: Any | None = None
    values: tuple[Any, ...] | None = None

    def __post_init__(self) -> None:
        op = str(self.op).strip()
        if not op:
            raise ValueError("filter condition op is required")
        if op not in _FILTER_SUPPORTED_OPS:
            raise ValueError(f"Unsupported filter operator '{op}'.")
        column = _normalize_optional_text(self.column)
        dimension_hint = _normalize_optional_text(self.dimension_hint)
        if column is None and dimension_hint is None:
            raise ValueError("filter condition requires column or dimension_hint")
        values = tuple(self.values) if self.values is not None else None
        if op == "in":
            if self.value is not None:
                raise ValueError("filter condition op='in' does not accept value")
            if not values:
                raise ValueError("filter condition op='in' requires non-empty values")
        elif op in _FILTER_NULL_OPS:
            if self.value is not None or values is not None:
                raise ValueError("filter condition null checks do not accept value or values")
        else:
            if values is not None:
                raise ValueError(f"filter condition op='{op}' does not accept values")
            if self.value is None:
                raise ValueError(f"filter condition op='{op}' requires value")
        object.__setattr__(self, "op", op)
        object.__setattr__(self, "column", column)
        object.__setattr__(self, "dimension_hint", dimension_hint)
        object.__setattr__(self, "values", values)

    @classmethod
    def from_api(cls, payload: Any) -> QueryFilterCondition:
        data = coerce_payload_mapping(payload)
        raw_values = data.get("values")
        return cls(
            op=str(data["op"]),
            column=data.get("column"),
            dimension_hint=data.get("dimension_hint"),
            value=data.get("value"),
            values=tuple(raw_values) if isinstance(raw_values, (list, tuple)) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.values is not None:
            data["values"] = list(self.values)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(frozen=True)
class QueryFilterSpec:
    time_filter: str | None = None
    conditions: tuple[QueryFilterCondition, ...] = ()

    def __post_init__(self) -> None:
        normalized_time_filter = _normalize_optional_text(self.time_filter)
        normalized_conditions: list[QueryFilterCondition] = []
        for condition in self.conditions or ():
            if isinstance(condition, QueryFilterCondition):
                normalized_conditions.append(condition)
            else:
                normalized_conditions.append(QueryFilterCondition.from_api(condition))
        object.__setattr__(self, "time_filter", normalized_time_filter)
        object.__setattr__(self, "conditions", tuple(normalized_conditions))

    @classmethod
    def from_api(cls, payload: Any) -> QueryFilterSpec:
        data = coerce_payload_mapping(payload)
        raw_conditions = data.get("conditions")
        conditions = tuple(
            QueryFilterCondition.from_api(item) for item in raw_conditions if isinstance(item, dict)
        )
        return cls(time_filter=data.get("time_filter"), conditions=conditions)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.time_filter is not None:
            payload["time_filter"] = self.time_filter
        if self.conditions:
            payload["conditions"] = [condition.to_dict() for condition in self.conditions]
        return payload


@dataclass(frozen=True)
class ResolvedPlan:
    source_name: str
    metric_column: str
    aggregation: str
    group_column: str | None = None
    join_path: dict[str, Any] | None = None
    filter: QueryFilterSpec | None = None
    limit: int | None = None
    order: str = "desc"
    constraints: dict[str, Any] = field(default_factory=dict)
    schema_revision: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> ResolvedPlan:
        data = coerce_payload_mapping(payload)
        return cls(
            source_name=data["source_name"],
            metric_column=data["metric_column"],
            aggregation=data["aggregation"],
            group_column=data.get("group_column"),
            join_path=data.get("join_path"),
            filter=QueryFilterSpec.from_api(data["filter"]) if data.get("filter") else None,
            limit=data.get("limit"),
            order=data.get("order", "desc"),
            constraints=data.get("constraints") or {},
            schema_revision=data["schema_revision"],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.filter is not None:
            data["filter"] = self.filter.to_dict()
        return data
