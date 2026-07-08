from __future__ import annotations

import math
import statistics
from functools import cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from .map_models import FieldMapping, MapResult

_ABBREVS = {
    "qty": "quantity",
    "qnty": "quantity",
    "amt": "amount",
    "amnt": "amount",
    "rev": "revenue",
    "revs": "revenue",
    "cst": "cost",
    "cust": "customer",
    "cus": "customer",
    "prc": "price",
    "num": "number",
    "no": "number",
    "nbr": "number",
    "dt": "date",
    "ts": "timestamp",
}

_SYNONYMS: dict[str, set[str]] = {
    "revenue": {"sales", "income", "receipts", "turnover"},
    "cost": {"expense", "expenditure", "spending", "payment"},
    "quantity": {"qty", "count", "units", "volume"},
    "price": {"rate", "unitprice", "unitcost"},
    "customer": {"client", "buyer", "account", "consumer"},
    "product": {"item", "sku", "article"},
    "date": {"timestamp", "datetime", "period"},
    "id": {"key", "identifier", "number", "code", "ref"},
}


@cache
def _map_models_module():
    return import_module("algenta.map_models")


@cache
def _map_parsing_module():
    return import_module("algenta.map_parsing")


def _normalize(value: str) -> str:
    normalized = value.lower().strip()
    for character in "_- ":
        normalized = normalized.replace(character, "")
    return _ABBREVS.get(normalized, normalized)


def _ngrams(value: str, n: int = 2) -> set[str]:
    padded = f"_{value}_"
    return {padded[index : index + n] for index in range(len(padded) - n + 1)}


def _dice(value_a: str, value_b: str) -> float:
    if value_a == value_b:
        return 1.0
    ngrams_a = _ngrams(value_a)
    ngrams_b = _ngrams(value_b)
    inter = len(ngrams_a & ngrams_b)
    return 2 * inter / (len(ngrams_a) + len(ngrams_b)) if (ngrams_a or ngrams_b) else 0.0


def _semantic_similarity(name_a: str, name_b: str) -> tuple[float, list[str]]:
    norm_a = _normalize(name_a)
    norm_b = _normalize(name_b)
    if norm_a == norm_b:
        return 1.0, ["exact name match"]
    reasons: list[str] = []
    score = 0.0
    bigram = _dice(norm_a, norm_b)
    if bigram > 0.5:
        score = max(score, bigram)
        reasons.append(f"string similarity ({bigram:.0%})")
    if norm_a in norm_b or norm_b in norm_a:
        score = max(score, 0.80)
        reasons.append("name substring match")
    for canonical, synonyms in _SYNONYMS.items():
        all_terms = synonyms | {canonical}
        if norm_a in all_terms and norm_b in all_terms:
            score = max(score, 0.88)
            reasons.append(f"semantic synonym ({canonical})")
            break
    return min(score, 1.0), reasons


def _profile_field(values: list[Any]) -> dict[str, Any]:
    numbers = [value for value in values if isinstance(value, int | float)]
    strings = [str(value) for value in values if not isinstance(value, int | float)]
    is_numeric = len(numbers) > len(strings)
    profile: dict[str, Any] = {
        "is_numeric": is_numeric,
        "numeric": numbers,
        "strings": strings,
        "unique_count": len({str(value) for value in values[:500]}),
        "total_count": len(values),
    }
    if numbers and len(numbers) > 1:
        float_numbers = [float(value) for value in numbers if math.isfinite(float(value))]
        if len(float_numbers) > 1:
            profile["mean"] = sum(float_numbers) / len(float_numbers)
            mean_value = profile["mean"]
            profile["std"] = math.sqrt(
                sum((value - mean_value) ** 2 for value in float_numbers) / (len(float_numbers) - 1)
            )
    return profile


def _stat_similarity(values_a: list[float], values_b: list[float]) -> float:
    if len(values_a) < 3 or len(values_b) < 3:
        return 0.0
    mean_a = statistics.mean(values_a)
    mean_b = statistics.mean(values_b)
    if mean_a > 0 and mean_b > 0:
        ratio = max(mean_a, mean_b) / max(min(mean_a, mean_b), 1)
        if ratio < 3:
            return 1 - (ratio - 1) / 2
    return 0.0


def map_data(
    *sources: str | Path | list[dict[str, Any]],
    names: list[str] | None = None,
    min_confidence: float = 0.5,
) -> MapResult:
    map_models = _map_models_module()
    map_parsing = _map_parsing_module()
    field_mapping_cls = map_models.FieldMapping
    map_result_cls = map_models.MapResult
    parsed: dict[str, list[dict[str, Any]]] = {}
    for index, source in enumerate(sources):
        label = (
            names[index] if names and index < len(names) else None
        ) or map_parsing._source_name(source, index)
        parsed[label] = map_parsing._parse_source(source)

    profiles: dict[str, dict[str, dict[str, Any]]] = {}
    for source_name, records in parsed.items():
        if not records:
            continue
        profile: dict[str, dict[str, Any]] = {}
        for field_name in records[0].keys():
            values = [record.get(field_name) for record in records[:2000] if field_name in record]
            profile[field_name] = _profile_field(values)
        profiles[source_name] = profile

    mappings: list[FieldMapping] = []
    source_names = list(profiles.keys())
    for index, source_a in enumerate(source_names):
        for source_b in source_names[index + 1 :]:
            for field_a, info_a in profiles[source_a].items():
                for field_b, info_b in profiles[source_b].items():
                    score, reasons = _semantic_similarity(field_a, field_b)
                    if score >= 1.0:
                        match_type = "exact"
                    elif score > 0.5:
                        match_type = "semantic"
                    else:
                        match_type = "no_match"

                    if (
                        info_a["is_numeric"]
                        and info_b["is_numeric"]
                        and info_a["numeric"]
                        and info_b["numeric"]
                    ):
                        stat_score = _stat_similarity(info_a["numeric"], info_b["numeric"])
                        if stat_score > 0.3:
                            score = min(score + stat_score * 0.3, 1.0)
                            reasons.append(f"similar distribution ({stat_score:.0%})")
                            if match_type == "no_match":
                                match_type = "statistical"

                    if score >= min_confidence and reasons:
                        mappings.append(
                            field_mapping_cls(
                                source_field=field_a,
                                source=source_a,
                                target_field=field_b,
                                target=source_b,
                                confidence=round(score, 3),
                                reason=reasons[:3],
                                match_type=match_type,
                            )
                        )

    mappings.sort(key=lambda item: item.confidence, reverse=True)

    unified_schema: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_name, profile in profiles.items():
        for field_name, info in profile.items():
            normalized = _normalize(field_name)
            if normalized not in seen:
                seen.add(normalized)
                unified_schema.append(
                    {
                        "name": field_name,
                        "sources": [source_name],
                        "is_numeric": info["is_numeric"],
                        "unique_count": info["unique_count"],
                        "total_count": info["total_count"],
                    }
                )
                continue
            for unified in unified_schema:
                if (
                    _normalize(unified["name"]) == normalized
                    and source_name not in unified["sources"]
                ):
                    unified["sources"].append(source_name)
                    break

    join_keys: list[dict[str, Any]] = []
    for source_name, profile in profiles.items():
        for field_name, info in profile.items():
            unique_ratio = info["unique_count"] / max(info["total_count"], 1)
            if unique_ratio <= 0.85:
                continue
            for mapping in mappings:
                is_source_match = (
                    mapping.source == source_name and mapping.source_field == field_name
                )
                is_target_match = (
                    mapping.target == source_name and mapping.target_field == field_name
                )
                if not (is_source_match or is_target_match):
                    continue
                join_keys.append(
                    {
                        "field": field_name,
                        "source": source_name,
                        "maps_to": (
                            mapping.target_field if is_source_match else mapping.source_field
                        ),
                        "in_source": mapping.target if is_source_match else mapping.source,
                        "confidence": mapping.confidence,
                    }
                )
                break

    numeric_metric_fields = sum(
        1
        for profile in profiles.values()
        for field_name, info in profile.items()
        if info["is_numeric"]
        and not any(
            keyword in _normalize(field_name) for keyword in {"id", "key", "number", "code"}
        )
    )
    return map_result_cls(
        sources_analyzed=len(parsed),
        total_fields=len(seen),
        mappings=mappings,
        unified_schema=unified_schema,
        join_keys=join_keys,
        simulation_ready=numeric_metric_fields >= 2,
    )
