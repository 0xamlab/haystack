from __future__ import annotations

import re
import statistics
from pathlib import Path
from typing import Any

from .map_matching import _semantic_similarity
from .map_parsing import _parse_source

_AGG_KEYWORDS: dict[str, str] = {
    "total": "sum",
    "sum": "sum",
    "average": "mean",
    "avg": "mean",
    "mean": "mean",
    "count": "count",
    "number of": "count",
    "how many": "count",
    "max": "max",
    "maximum": "max",
    "highest": "max",
    "min": "min",
    "minimum": "min",
    "lowest": "min",
}

_METRIC_SYNONYMS: dict[str, list[str]] = {
    "revenue": [
        "revenue",
        "sales",
        "income",
        "receipts",
        "ext_price",
        "extprice",
        "extended_price",
        "total_price",
        "invoice_amount",
    ],
    "cost": [
        "cost",
        "expense",
        "spending",
        "ext_cost",
        "extcost",
        "extended_cost",
        "total_cost",
        "expenditure",
    ],
    "quantity": ["quantity", "qty", "units", "volume"],
    "price": ["price", "unit_price", "unitprice", "rate", "list_price"],
    "amount": ["amount", "total", "value"],
    "profit": ["profit", "margin", "net"],
    "count": ["count", "number"],
}


def query_data(
    query: str,
    *sources: str | Path | list[dict[str, Any]],
    names: list[str] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    del names
    all_records: list[dict[str, Any]] = []
    for source in sources:
        all_records.extend(_parse_source(source))

    if not all_records:
        return []

    query_text = query.lower()

    aggregation = "sum"
    for keyword, candidate in _AGG_KEYWORDS.items():
        if keyword in query_text:
            aggregation = candidate
            break

    top_entity_match = re.search(r"\btop\s+(\d+)\s+(\w+)\s+by\s+(\w+)", query_text)
    if top_entity_match:
        limit = int(top_entity_match.group(1))
        group_hint_raw = top_entity_match.group(2).rstrip("s")
        metric_word = top_entity_match.group(3)
        aggregation = "sum"
        metric_hint = None
        for canonical, terms in _METRIC_SYNONYMS.items():
            if metric_word in terms or metric_word == canonical:
                metric_hint = canonical
                break
        metric_hint = metric_hint or metric_word
        group_hint = group_hint_raw
        fields = list(all_records[0].keys()) if all_records else []
        metric_field = _best_field(fields, all_records, metric_hint, numeric_only=True)
        group_field = _best_field(fields, all_records, group_hint, numeric_only=False)
        if group_field == metric_field:
            group_field = None
        return _execute(all_records, metric_field, group_field, aggregation, limit)

    top_match = re.search(r"\btop\s+(\d+)\b", query_text)
    if top_match:
        limit = int(top_match.group(1))
        aggregation = "sum"

    metric_hint = None
    for canonical, terms in _METRIC_SYNONYMS.items():
        if any(term in query_text for term in terms):
            metric_hint = canonical
            break

    group_hint = None
    for prefix in ["by ", "per ", "for each ", "group by ", "grouped by "]:
        if prefix in query_text:
            after = query_text.split(prefix, 1)[1].strip()
            group_hint = re.split(r"[\s,]", after)[0].rstrip("s")
            break

    fields = list(all_records[0].keys()) if all_records else []
    metric_field = _best_field(fields, all_records, metric_hint, numeric_only=True)
    group_field = (
        _best_field(fields, all_records, group_hint, numeric_only=False) if group_hint else None
    )
    if group_field == metric_field:
        group_field = None
    return _execute(all_records, metric_field, group_field, aggregation, limit)


def _best_field(
    fields: list[str],
    records: list[dict[str, Any]],
    hint: str | None,
    *,
    numeric_only: bool,
) -> str | None:
    if hint is None:
        candidates = [field for field in fields if _is_numeric_field(field, records)]
        if not numeric_only:
            candidates = fields
        return candidates[0] if candidates else None
    best_field = None
    best_score = -1.0
    for field in fields:
        if numeric_only and not _is_numeric_field(field, records):
            continue
        score, _ = _semantic_similarity(field, hint)
        for canonical, terms in _METRIC_SYNONYMS.items():
            if hint in terms or hint == canonical:
                for term in terms:
                    term_score, _ = _semantic_similarity(field, term)
                    score = max(score, term_score)
        if score > best_score:
            best_score = score
            best_field = field
    return best_field


def _is_numeric_field(field_name: str, records: list[dict[str, Any]]) -> bool:
    count = len(records)
    if count == 0:
        return False
    step = max(1, count // 50)
    for index in range(0, count, step):
        if isinstance(records[index].get(field_name), int | float):
            return True
    return False


def _execute(
    records: list[dict[str, Any]],
    metric_field: str | None,
    group_field: str | None,
    aggregation: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not group_field:
        if not metric_field:
            return [{"count": len(records)}]
        values = [
            record[metric_field]
            for record in records
            if isinstance(record.get(metric_field), int | float)
        ]
        return [{metric_field: round(_agg(values, aggregation), 4), "count": len(values)}]

    groups: dict[Any, list[float]] = {}
    for record in records:
        group_key = record.get(group_field, "__unknown__")
        value = (
            float(record.get(metric_field, 1))
            if metric_field and isinstance(record.get(metric_field), int | float)
            else 1.0
        )
        groups.setdefault(group_key, []).append(value)

    rows: list[dict[str, Any]] = []
    for group_key, values in groups.items():
        row: dict[str, Any] = {group_field: group_key}
        if metric_field:
            row[metric_field] = round(_agg(values, aggregation), 4)
        row["count"] = len(values)
        rows.append(row)

    if metric_field:
        rows.sort(key=lambda row: row.get(metric_field, 0), reverse=True)
    return rows[:limit]


def _agg(values: list[float], aggregation: str) -> float:
    if not values:
        return 0.0
    aggregation_fn = {
        "sum": sum,
        "mean": statistics.mean,
        "max": max,
        "min": min,
        "count": lambda items: float(len(items)),
    }.get(aggregation, sum)
    return aggregation_fn(values)
