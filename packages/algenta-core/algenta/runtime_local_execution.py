from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from algenta.map_matching import _normalize, _semantic_similarity
from algenta.map_query import _METRIC_SYNONYMS, _execute, _is_numeric_field
from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError


@dataclass(frozen=True)
class LocalSource:
    name: str
    records: list[dict[str, Any]]
    fields: tuple[str, ...]
    schema_revision: str
    dataset_id: str
    numeric_fields: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RankedFieldMatch:
    field: str
    score: float
    reasons: tuple[str, ...]
    is_numeric: bool


@dataclass(frozen=True)
class LocalExecutionResult:
    value: Any
    result_type: str
    row_count: int
    plan_steps: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LocalFilterCondition:
    column: str
    op: str
    value: Any | None = None
    values: tuple[Any, ...] = field(default_factory=tuple)


_FILTER_SUPPORTED_OPS = frozenset({"eq", "in", "gt", "gte", "lt", "lte", "is_null", "is_not_null"})
_FILTER_NUMERIC_OPS = frozenset({"gt", "gte", "lt", "lte"})
_FILTER_NULL_OPS = frozenset({"is_null", "is_not_null"})
_FILTER_TRUE_VALUES = frozenset({"1", "true", "t", "yes", "y"})
_FILTER_FALSE_VALUES = frozenset({"0", "false", "f", "no", "n"})
_LOCAL_TIME_FIELD_CUES = ("date", "time", "timestamp", "month", "day", "year")


def select_local_source(
    local_sources: Mapping[str, LocalSource],
    request: Mapping[str, Any],
) -> LocalSource:
    requested_name = request.get("source_name") or request.get("dataset_id")
    if isinstance(requested_name, str):
        if requested_name in local_sources:
            return local_sources[requested_name]
        for source in local_sources.values():
            if source.dataset_id == requested_name:
                return source
        raise RuntimeValidationError(
            "unknown_source",
            "Requested source is not connected to this runtime.",
            {"requested": requested_name, "available": sorted(local_sources)},
        )
    if len(local_sources) == 1:
        return next(iter(local_sources.values()))
    if not local_sources:
        raise RuntimeConfigurationError(
            "source_required",
            "No local sources are connected. Call Runtime.connect(...) before resolve/query.",
        )
    raise RuntimeValidationError(
        "source_required",
        "Multiple local sources are connected. Provide source_name or dataset_id.",
        {"available": sorted(local_sources)},
    )


def rank_local_fields(
    source: LocalSource,
    hint: str,
    *,
    numeric_only: bool,
) -> list[RankedFieldMatch]:
    ranked: list[RankedFieldMatch] = []
    canonical_hint = _canonical_metric_hint(hint)
    hint_terms = {
        _normalize_text(canonical_hint),
        *{_normalize_text(term) for term in _METRIC_SYNONYMS.get(canonical_hint, [])},
    }

    for field_name in source.fields:
        is_numeric = field_name in source.numeric_fields
        if numeric_only and not is_numeric:
            continue
        score, reasons = _semantic_similarity(field_name, hint)
        normalized_field = _normalize_text(field_name)
        if normalized_field in hint_terms:
            score = max(score, 1.0)
            reasons = [*reasons, "canonical synonym match"]
        if is_exact_field_match(field_name, hint):
            score = 1.0
            reasons = ["exact field match"]
        normalized_phrase = _normalize_text(hint.replace(" ", "_"))
        if not numeric_only and " " in hint and normalized_phrase == normalized_field:
            score = max(score, 0.95)
            reasons = [*reasons, "normalized phrase match"]
        ranked.append(
            RankedFieldMatch(
                field=field_name,
                score=round(score, 4),
                reasons=tuple(reasons or ["schema similarity"]),
                is_numeric=is_numeric,
            )
        )

    ranked.sort(key=lambda item: (item.score, item.field), reverse=True)
    return ranked


def infer_numeric_fields(
    records: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> frozenset[str]:
    return frozenset(field_name for field_name in fields if _is_numeric_field(field_name, records))


def build_local_candidates(
    source: LocalSource,
    ranked: list[RankedFieldMatch],
    role: str,
) -> list[dict[str, Any]]:
    return [
        {
            "source": source.name,
            "column": item.field,
            "role": role,
            "confidence": item.score,
            "notes": list(item.reasons),
            "score_components": {"schema_similarity": item.score},
        }
        for item in ranked[:5]
    ]


def validate_local_plan(
    local_sources: Mapping[str, LocalSource],
    plan: Any,
) -> LocalSource:
    if plan.source_name not in local_sources:
        raise RuntimeValidationError(
            "unknown_source",
            "Query plan references a source that is not connected to this runtime.",
            {"source_name": plan.source_name},
        )
    source = local_sources[plan.source_name]
    if plan.schema_revision != source.schema_revision:
        raise RuntimeValidationError(
            "schema_revision_mismatch",
            "Query plan schema_revision does not match the connected source.",
            {"expected": source.schema_revision, "received": plan.schema_revision},
        )
    return source


def execute_local_plan(source: LocalSource, plan: Any) -> LocalExecutionResult:
    filtered_records = source.records
    plan_steps: list[str] = []
    filter_spec = _coerce_filter_spec(plan)
    time_filter = filter_spec.get("time_filter")
    if isinstance(time_filter, str) and time_filter.strip():
        time_field = _find_local_time_field(source)
        time_window = _time_range(time_filter.strip())
        if time_field is not None and time_window is not None:
            before = len(filtered_records)
            lower_bound, upper_bound = time_window
            filtered_records = [
                row
                for row in filtered_records
                if (parsed := _parse_date(row.get(time_field))) is not None
                and lower_bound <= parsed <= upper_bound
            ]
            plan_steps.append(
                f"Time filter '{time_filter.strip()}' on '{time_field}': "
                f"{before}->{len(filtered_records)} rows."
            )
        else:
            plan_steps.append("No time-like field found. time_filter skipped.")

    resolved_filter_conditions = _resolve_local_filter_conditions(source, filter_spec)
    filtered_records, filter_steps = _apply_local_filter_conditions(
        filtered_records,
        resolved_filter_conditions,
    )
    plan_steps.extend(filter_steps)

    result_rows = _execute(
        filtered_records,
        plan.metric_column,
        plan.group_column,
        plan.aggregation,
        plan.limit or 100,
    )
    if plan.group_column:
        return LocalExecutionResult(
            value=result_rows,
            result_type="table",
            row_count=len(result_rows),
            plan_steps=tuple(plan_steps),
        )
    scalar_row = result_rows[0] if result_rows else {}
    return LocalExecutionResult(
        value=scalar_row.get(plan.metric_column),
        result_type="scalar",
        row_count=1 if scalar_row else 0,
        plan_steps=tuple(plan_steps),
    )


def collect_local_plan_errors(
    local_sources: Mapping[str, LocalSource],
    plan: Any,
) -> list[str]:
    source = local_sources.get(plan.source_name)
    errors: list[str] = []
    if source is None:
        errors.append(f"Source '{plan.source_name}' is not connected.")
        return errors
    if plan.schema_revision != source.schema_revision:
        errors.append("schema_revision mismatch")
    if plan.metric_column not in source.fields:
        errors.append(f"Metric column '{plan.metric_column}' is missing.")
    if plan.group_column and plan.group_column not in source.fields:
        errors.append(f"Group column '{plan.group_column}' is missing.")
    try:
        _resolve_local_filter_conditions(source, _coerce_filter_spec(plan))
    except RuntimeValidationError as exc:
        errors.append(str(exc))
    return errors


def local_plan_steps(
    *,
    source_name: str,
    metric_column: str,
    aggregation: str,
    group_column: str | None,
    filter_steps: list[str] | None = None,
) -> list[str]:
    return [
        f"Use source '{source_name}'.",
        f"Aggregate '{metric_column}' with '{aggregation}'.",
        *([f"Group by '{group_column}'."] if group_column else []),
        *(filter_steps or []),
    ]


def _coerce_filter_spec(plan: Any) -> dict[str, Any]:
    raw_filter = getattr(plan, "filter", None)
    if isinstance(raw_filter, Mapping):
        return dict(raw_filter)
    if hasattr(raw_filter, "to_dict"):
        return dict(raw_filter.to_dict())
    if hasattr(raw_filter, "__dict__"):
        return dict(vars(raw_filter))
    if hasattr(raw_filter, "items"):
        return dict(raw_filter.items())
    return {}


def _time_range(filter_name: str) -> tuple[date, date] | None:
    today = date.today()
    if filter_name == "last_month":
        last_day_previous_month = today.replace(day=1) - timedelta(days=1)
        return last_day_previous_month.replace(day=1), last_day_previous_month
    if filter_name == "this_month":
        return today.replace(day=1), today
    if filter_name == "last_year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if filter_name == "this_year":
        return date(today.year, 1, 1), today
    if filter_name == "last_quarter":
        start_this_quarter = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        end_last_quarter = start_this_quarter - timedelta(days=1)
        start_last_quarter = date(
            end_last_quarter.year,
            ((end_last_quarter.month - 1) // 3) * 3 + 1,
            1,
        )
        return start_last_quarter, end_last_quarter
    if filter_name == "this_quarter":
        start_this_quarter = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        return start_this_quarter, today
    return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%Y-%m"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _find_local_time_field(source: LocalSource) -> str | None:
    best_field = None
    best_score = -1
    for field_name in source.fields:
        normalized_field = _normalize_text(field_name)
        sample_matches = sum(
            1 for row in source.records[:25] if _parse_date(row.get(field_name)) is not None
        )
        if sample_matches == 0:
            continue
        cue_bonus = sum(1 for cue in _LOCAL_TIME_FIELD_CUES if cue in normalized_field)
        score = sample_matches + cue_bonus
        if score > best_score:
            best_score = score
            best_field = field_name
    return best_field


def _filter_number_like(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _filter_boolean_like(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, float) and math.isfinite(value) and value in {0.0, 1.0}:
        return bool(int(value))
    if value is None:
        return None
    normalized = str(value).strip().casefold()
    if normalized in _FILTER_TRUE_VALUES:
        return True
    if normalized in _FILTER_FALSE_VALUES:
        return False
    return None


def _filter_value_is_nullish(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        normalized = value.strip().casefold()
        return normalized in {"", "none", "null", "nan"}
    if isinstance(value, float):
        try:
            return not math.isfinite(value)
        except (TypeError, ValueError):
            return True
    return False


def _filter_value_equals(row_value: Any, expected: Any) -> bool:
    row_bool = _filter_boolean_like(row_value)
    expected_bool = _filter_boolean_like(expected)
    if row_bool is not None and expected_bool is not None:
        return row_bool is expected_bool

    row_number = _filter_number_like(row_value)
    expected_number = _filter_number_like(expected)
    if row_number is not None and expected_number is not None:
        return row_number == expected_number

    row_text = None if _filter_value_is_nullish(row_value) else str(row_value).strip().casefold()
    expected_text = None if _filter_value_is_nullish(expected) else str(expected).strip().casefold()
    if row_text is None or expected_text is None:
        return False
    return row_text == expected_text


def _sample_boolean_field(source: LocalSource, field_name: str) -> bool:
    observed = 0
    for row in source.records[:50]:
        value = row.get(field_name)
        if _filter_value_is_nullish(value):
            continue
        observed += 1
        if _filter_boolean_like(value) is None:
            return False
    return observed > 0


def _field_match_score(field_name: str, normalized_hint: str) -> tuple[float, bool]:
    normalized_field = _normalize_text(field_name)
    if not normalized_field or not normalized_hint:
        return 0.0, False
    if normalized_field == normalized_hint:
        return 1.0, True
    if normalized_field.startswith(normalized_hint) or normalized_hint.startswith(normalized_field):
        return 0.95, False
    if normalized_hint in normalized_field or normalized_field in normalized_hint:
        return 0.9, False

    field_tokens = set(normalized_field.split())
    hint_tokens = set(normalized_hint.split())
    if not field_tokens or not hint_tokens:
        return 0.0, False
    overlap_forward = len(field_tokens & hint_tokens) / len(field_tokens)
    overlap_backward = len(field_tokens & hint_tokens) / len(hint_tokens)
    return round((overlap_forward + overlap_backward) / 2, 4), False


def _preferred_filter_value_type(condition: Mapping[str, Any]) -> str | None:
    op = str(condition.get("op", "eq"))
    if op in _FILTER_NUMERIC_OPS:
        return "numeric"
    if op in _FILTER_NULL_OPS:
        return None
    values = condition.get("values")
    if op == "in" and isinstance(values, list):
        if values and all(_filter_boolean_like(value) is not None for value in values):
            return "boolean"
        if values and all(_filter_number_like(value) is not None for value in values):
            return "numeric"
        return None
    value = condition.get("value")
    if _filter_boolean_like(value) is not None:
        return "boolean"
    if _filter_number_like(value) is not None:
        return "numeric"
    return None


def _resolve_local_filter_column(source: LocalSource, condition: Mapping[str, Any]) -> str:
    raw_column = condition.get("column")
    if isinstance(raw_column, str) and raw_column.strip():
        normalized_column = _normalize_text(raw_column)
        for field_name in source.fields:
            if _normalize_text(field_name) == normalized_column:
                return field_name
        raise RuntimeValidationError(
            "invalid_filter_condition",
            f"Filter column '{raw_column}' is not present on source '{source.name}'.",
        )

    raw_hint = condition.get("dimension_hint")
    if not isinstance(raw_hint, str) or not raw_hint.strip():
        raise RuntimeValidationError(
            "invalid_filter_condition",
            "Filter condition requires column or dimension_hint.",
        )

    normalized_hint = _normalize_text(raw_hint)
    preferred_type = _preferred_filter_value_type(condition)
    candidates: list[tuple[float, bool, str]] = []
    for field_name in source.fields:
        lexical_score, exact_match = _field_match_score(field_name, normalized_hint)
        if lexical_score <= 0:
            continue
        is_numeric = field_name in source.numeric_fields
        is_boolean = _sample_boolean_field(source, field_name)
        suitability = 0.0
        if preferred_type == "numeric":
            suitability = 0.35 if is_numeric else -0.25
        elif preferred_type == "boolean":
            if is_boolean:
                suitability = 0.35
            elif is_numeric:
                suitability = -0.10
        elif str(condition.get("op", "eq")) in {"eq", "in"}:
            suitability = 0.10 if not is_numeric else -0.08
        overall_score = round(lexical_score + suitability, 4)
        if overall_score < 0.60 and not exact_match:
            continue
        candidates.append((overall_score, exact_match, field_name))

    if not candidates:
        raise RuntimeValidationError(
            "invalid_filter_condition",
            f"Filter dimension_hint '{raw_hint}' did not resolve on source '{source.name}'.",
        )
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    best_score, best_exact, best_field = candidates[0]
    if len(candidates) > 1 and not best_exact and candidates[1][0] >= best_score - 0.05:
        ambiguous = ", ".join(candidate[2] for candidate in candidates[:3])
        raise RuntimeValidationError(
            "invalid_filter_condition",
            f"Filter dimension_hint '{raw_hint}' is ambiguous on source '{source.name}': "
            f"{ambiguous}.",
        )
    if preferred_type == "numeric" and best_field not in source.numeric_fields:
        raise RuntimeValidationError(
            "invalid_filter_condition",
            f"Filter column '{best_field}' on source '{source.name}' is not numeric.",
        )
    return best_field


def _resolve_local_filter_conditions(
    source: LocalSource,
    filter_spec: Mapping[str, Any],
) -> list[LocalFilterCondition]:
    raw_conditions = filter_spec.get("conditions")
    if not isinstance(raw_conditions, list):
        return []
    resolved: list[LocalFilterCondition] = []
    for raw_condition in raw_conditions:
        if not isinstance(raw_condition, Mapping):
            raise RuntimeValidationError(
                "invalid_filter_condition",
                "Filter conditions must be objects.",
            )
        op = str(raw_condition.get("op", "")).strip()
        if not op:
            raise RuntimeValidationError(
                "invalid_filter_condition",
                "Filter condition op is required.",
            )
        if op not in _FILTER_SUPPORTED_OPS:
            raise RuntimeValidationError(
                "invalid_filter_condition",
                f"Unsupported filter operator '{op}'.",
            )
        value = raw_condition.get("value")
        raw_values = raw_condition.get("values")
        values = tuple(raw_values or ()) if isinstance(raw_values, (list, tuple)) else None
        if op == "in":
            if value is not None:
                raise RuntimeValidationError(
                    "invalid_filter_condition",
                    "filter condition op='in' does not accept value",
                )
            if not values:
                raise RuntimeValidationError(
                    "invalid_filter_condition",
                    "filter condition op='in' requires non-empty values",
                )
        elif op in _FILTER_NULL_OPS:
            if value is not None or raw_values is not None:
                raise RuntimeValidationError(
                    "invalid_filter_condition",
                    "filter condition null checks do not accept value or values",
                )
        else:
            if raw_values is not None:
                raise RuntimeValidationError(
                    "invalid_filter_condition",
                    f"filter condition op='{op}' does not accept values",
                )
            if value is None:
                raise RuntimeValidationError(
                    "invalid_filter_condition",
                    f"filter condition op='{op}' requires value",
                )
        resolved_column = _resolve_local_filter_column(source, raw_condition)
        resolved.append(
            LocalFilterCondition(
                column=resolved_column,
                op=op,
                value=value,
                values=values,
            )
        )
    return resolved


def _row_matches_filter_condition(row: Mapping[str, Any], condition: LocalFilterCondition) -> bool:
    row_value = row.get(condition.column)
    if condition.op == "eq":
        return _filter_value_equals(row_value, condition.value)
    if condition.op == "in":
        return any(_filter_value_equals(row_value, value) for value in condition.values)
    if condition.op == "gt":
        row_number = _filter_number_like(row_value)
        expected_number = _filter_number_like(condition.value)
        return (
            row_number is not None and expected_number is not None and row_number > expected_number
        )
    if condition.op == "gte":
        row_number = _filter_number_like(row_value)
        expected_number = _filter_number_like(condition.value)
        return (
            row_number is not None and expected_number is not None and row_number >= expected_number
        )
    if condition.op == "lt":
        row_number = _filter_number_like(row_value)
        expected_number = _filter_number_like(condition.value)
        return (
            row_number is not None and expected_number is not None and row_number < expected_number
        )
    if condition.op == "lte":
        row_number = _filter_number_like(row_value)
        expected_number = _filter_number_like(condition.value)
        return (
            row_number is not None and expected_number is not None and row_number <= expected_number
        )
    if condition.op == "is_null":
        return _filter_value_is_nullish(row_value)
    if condition.op == "is_not_null":
        return not _filter_value_is_nullish(row_value)
    raise RuntimeValidationError(
        "invalid_filter_condition",
        f"Unsupported filter operator '{condition.op}'.",
    )


def _apply_local_filter_conditions(
    records: list[dict[str, Any]],
    conditions: list[LocalFilterCondition],
) -> tuple[list[dict[str, Any]], list[str]]:
    filtered_records = records
    plan_steps: list[str] = []
    for condition in conditions:
        before = len(filtered_records)
        filtered_records = [
            row for row in filtered_records if _row_matches_filter_condition(row, condition)
        ]
        if condition.op in _FILTER_NULL_OPS:
            description = f"{condition.column} {condition.op}"
        else:
            rhs = list(condition.values) if condition.op == "in" else condition.value
            description = f"{condition.column} {condition.op} {rhs!r}"
        plan_steps.append(f"Filter '{description}': {before}->{len(filtered_records)} rows.")
    return filtered_records, plan_steps


def is_exact_field_match(field_name: str, hint: str) -> bool:
    return _normalize_text(field_name) == _normalize_text(hint)


def _normalize_text(value: str | None) -> str:
    return _normalize(value or "")


def _canonical_metric_hint(hint: str) -> str:
    normalized_hint = _normalize_text(hint)
    for canonical, terms in _METRIC_SYNONYMS.items():
        normalized_terms = {_normalize_text(canonical), *(_normalize_text(term) for term in terms)}
        if normalized_hint in normalized_terms:
            return canonical
    return hint
