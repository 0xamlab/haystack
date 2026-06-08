from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from algenta.map_matching import _normalize
from algenta.map_query import _AGG_KEYWORDS, _METRIC_SYNONYMS

_RAW_TEXT_GROUP_RE = re.compile(r"\b(?:by|per|grouped by|group by|for each)\s+([a-zA-Z0-9_ ]+)")


def stable_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def normalize_text(value: str | None) -> str:
    return _normalize(value or "")


def parse_raw_text(raw_text: str) -> dict[str, Any]:
    text = raw_text.lower().strip()
    parsed: dict[str, Any] = {}
    for keyword, aggregation in _AGG_KEYWORDS.items():
        if keyword in text:
            parsed["aggregation"] = aggregation
            break
    for canonical, terms in _METRIC_SYNONYMS.items():
        if any(term in text for term in terms):
            parsed["metric"] = canonical
            break
    group_match = _RAW_TEXT_GROUP_RE.search(text)
    if group_match:
        parsed["group_by"] = group_match.group(1).strip()
    return parsed


def resolve_aggregation(request: Mapping[str, Any]) -> str:
    if isinstance(request.get("aggregation"), str):
        return request["aggregation"].lower().strip()
    raw_text = request.get("raw_text")
    if isinstance(raw_text, str):
        parsed = parse_raw_text(raw_text)
        if isinstance(parsed.get("aggregation"), str):
            return parsed["aggregation"]
    return "sum"


def merge_runtime_request(
    request: Mapping[str, Any] | None,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(request or {})
    merged.update(dict(overrides or {}))
    raw_text = merged.get("raw_text")
    if isinstance(raw_text, str):
        parsed = parse_raw_text(raw_text)
        for key, value in parsed.items():
            merged.setdefault(key, value)
    return merged


def intent_signature(source_name: str, request: Mapping[str, Any], schema_revision: str) -> str:
    normalized = {
        "source_name": source_name,
        "schema_revision": schema_revision,
        "metric": normalize_text(str(request.get("metric", ""))),
        "group_by": normalize_text(str(request.get("group_by", ""))),
        "aggregation": resolve_aggregation(request),
        "limit": int(request["limit"]) if request.get("limit") is not None else None,
        "order": str(request.get("order", "desc")).lower(),
        "constraints": request.get("constraints") or {},
        "filter": request.get("filter") or {},
    }
    return stable_hash(normalized)


def plan_hash(plan: Any) -> str:
    return stable_hash(plan.to_dict())
