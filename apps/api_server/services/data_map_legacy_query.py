from __future__ import annotations

import re
import statistics
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException

from apps.api_server.schemas.data_map import DataSource, _LegacyQueryRequest, _LegacyQueryResponse

_AGG_KEYWORDS: dict[str, str] = {
    "total": "sum",
    "sum": "sum",
    "aggregate": "sum",
    "average": "mean",
    "avg": "mean",
    "mean": "mean",
    "count": "count",
    "number of": "count",
    "how many": "count",
    "max": "max",
    "maximum": "max",
    "highest": "max",
    "top": "max",
    "min": "min",
    "minimum": "min",
    "lowest": "min",
}

_METRIC_KEYWORDS: dict[str, list[str]] = {
    "revenue": [
        "revenue",
        "sales",
        "income",
        "receipts",
        "turnover",
        "ext_price",
        "extprice",
        "extended_price",
        "total_price",
    ],
    "cost": [
        "cost",
        "expense",
        "expenditure",
        "spending",
        "ext_cost",
        "extcost",
        "extended_cost",
        "total_cost",
    ],
    "quantity": ["quantity", "qty", "units", "volume"],
    "price": ["price", "rate", "unit_price", "unitprice", "list_price"],
    "amount": ["amount", "total", "value"],
    "profit": ["profit", "margin", "net"],
    "count": ["count", "number"],
}

_GROUP_PREPOSITIONS = ["by ", "per ", "for each ", "grouped by ", "group by "]

LoadSourceFn = Callable[[DataSource, str | None], Awaitable[list[dict[str, Any]]]]
SemanticSimilarityFn = Callable[[str, str], tuple[float, list[str]]]


def _parse_query_intent(query: str) -> dict[str, Any]:
    """Parse a natural-language query into an execution intent."""
    normalized_query = query.lower().strip()
    intent: dict[str, Any] = {
        "aggregation": "sum",
        "metric_hint": None,
        "group_hint": None,
        "limit": None,
        "confidence": 0.5,
    }

    for keyword, aggregation in _AGG_KEYWORDS.items():
        if keyword in normalized_query:
            intent["aggregation"] = aggregation
            intent["confidence"] = min(intent["confidence"] + 0.2, 1.0)
            break

    top_match = re.search(r"\btop\s+(\d+)\b", normalized_query)
    if top_match:
        intent["limit"] = int(top_match.group(1))
        intent["aggregation"] = "sum"

    for canonical, terms in _METRIC_KEYWORDS.items():
        if any(term in normalized_query for term in terms):
            intent["metric_hint"] = canonical
            intent["confidence"] = min(intent["confidence"] + 0.2, 1.0)
            break

    for preposition in _GROUP_PREPOSITIONS:
        if preposition in normalized_query:
            after = normalized_query.split(preposition, 1)[1].strip()
            group_word = re.split(r"[\s,]", after)[0].rstrip("s")
            intent["group_hint"] = group_word
            intent["confidence"] = min(intent["confidence"] + 0.15, 1.0)
            break

    return intent


def _find_best_field(
    records: list[dict[str, Any]],
    hint: str | None,
    *,
    numeric_only: bool,
    semantic_similarity_fn: SemanticSimilarityFn,
) -> str | None:
    """Find the best matching field name in records given a hint."""
    if not records:
        return None

    fields = list(records[0].keys())
    if not fields:
        return None

    if numeric_only:

        def _is_num(field_name: str) -> bool:
            values = [records[index].get(field_name) for index in range(min(10, len(records)))]
            return any(isinstance(value, int | float) for value in values)

        candidate_fields = [field_name for field_name in fields if _is_num(field_name)]
    else:
        candidate_fields = fields

    if not candidate_fields:
        return None

    if hint is None:
        return candidate_fields[0]

    best_field = None
    best_score = -1.0
    for field_name in candidate_fields:
        score, _ = semantic_similarity_fn(field_name, hint)
        for canonical, terms in _METRIC_KEYWORDS.items():
            if hint in terms or hint == canonical:
                for term in terms:
                    synonym_score, _ = semantic_similarity_fn(field_name, term)
                    score = max(score, synonym_score)
        if score > best_score:
            best_score = score
            best_field = field_name
    return best_field


def _agg_vals(values: list[float], aggregation: str) -> float:
    if not values:
        return 0.0
    if aggregation == "sum":
        return sum(values)
    if aggregation == "mean":
        return statistics.mean(values)
    if aggregation == "max":
        return max(values)
    if aggregation == "min":
        return min(values)
    if aggregation == "count":
        return float(len(values))
    return sum(values)


def _execute_query(
    records: list[dict[str, Any]],
    *,
    metric_field: str | None,
    group_field: str | None,
    aggregation: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Execute a simple aggregate query on row records."""
    if not records:
        return []

    if not group_field:
        if not metric_field:
            return [{"count": len(records)}]
        values: list[float] = []
        for record in records:
            raw_value = record.get(metric_field)
            if isinstance(raw_value, int | float):
                values.append(float(raw_value))
        if not values:
            return [{"result": None}]
        result_value = _agg_vals(values, aggregation)
        return [{metric_field: round(result_value, 4), "count": len(values)}]

    groups: dict[Any, list[float]] = {}
    for record in records:
        group_key = record.get(group_field, "__unknown__")
        raw_value = record.get(metric_field) if metric_field else 1.0
        value = float(raw_value) if isinstance(raw_value, int | float) else 1.0
        groups.setdefault(group_key, []).append(value)

    result_rows: list[dict[str, Any]] = []
    for group_key, values in groups.items():
        aggregated = _agg_vals(values, aggregation)
        result_row: dict[str, Any] = {group_field: group_key, "count": len(values)}
        if metric_field:
            result_row[metric_field] = round(aggregated, 4)
        result_rows.append(result_row)

    if metric_field:
        result_rows.sort(key=lambda row: row.get(metric_field, 0), reverse=True)

    if limit:
        result_rows = result_rows[:limit]

    return result_rows


async def execute_legacy_query(
    payload: _LegacyQueryRequest,
    *,
    org_id: str,
    load_source_fn: LoadSourceFn,
    semantic_similarity_fn: SemanticSimilarityFn,
) -> _LegacyQueryResponse:
    """Execute the legacy natural-language query helper through injected loaders."""
    started_at = time.monotonic()

    all_records: list[dict[str, Any]] = []
    for source in payload.sources:
        all_records.extend(await load_source_fn(source, org_id))

    if not all_records:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "no_data", "message": "No records found"}},
        )

    intent = _parse_query_intent(payload.query)
    aggregation = intent["aggregation"]
    metric_hint = intent["metric_hint"]
    group_hint = intent["group_hint"]
    limit = intent.get("limit") or payload.limit

    metric_field = _find_best_field(
        all_records,
        metric_hint,
        numeric_only=True,
        semantic_similarity_fn=semantic_similarity_fn,
    )
    group_field = (
        _find_best_field(
            all_records,
            group_hint,
            numeric_only=False,
            semantic_similarity_fn=semantic_similarity_fn,
        )
        if group_hint
        else None
    )

    if group_field and metric_field and group_field == metric_field:
        group_field = None

    result = _execute_query(
        all_records,
        metric_field=metric_field,
        group_field=group_field,
        aggregation=aggregation,
        limit=limit,
    )

    plan_parts: list[str] = []
    if metric_field:
        plan_parts.append(f"{aggregation}({metric_field})")
    else:
        plan_parts.append("count(records)")
    if group_field:
        plan_parts.append(f"group by {group_field}")
    if limit and group_field:
        plan_parts.append(f"limit {limit}")
    query_plan = " -> ".join(plan_parts) if plan_parts else "scan all records"

    confidence = intent["confidence"]
    if metric_field:
        confidence = min(confidence + 0.1, 1.0)
    if group_field:
        confidence = min(confidence + 0.1, 1.0)

    return _LegacyQueryResponse(
        query=payload.query,
        result=result[: payload.limit],
        row_count=len(result),
        query_plan=query_plan,
        metric_field=metric_field,
        group_field=group_field,
        aggregation=aggregation,
        confidence=round(confidence, 3),
        latency_ms=round((time.monotonic() - started_at) * 1000, 1),
    )
