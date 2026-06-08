from __future__ import annotations

import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from apps.api_server.schemas.data_map import SchemaField

SourceFieldProfile = dict[str, Any]
SourceProfile = dict[str, SourceFieldProfile]
SourceProfiles = dict[str, SourceProfile]
SemanticSimilarityFn = Callable[[str, str], tuple[float, list[str]]]
FieldMapFn = Callable[[dict[str, list[float]]], Awaitable[dict[str, Any] | None]]


@dataclass
class UnifiedSchemaBuildResult:
    unified_schema: dict[str, SchemaField]
    all_fields_seen: set[str]


def build_source_profiles(
    parsed_sources: dict[str, list[dict[str, Any]]],
) -> SourceProfiles:
    source_profiles: SourceProfiles = {}
    for src_name, records in parsed_sources.items():
        if not records:
            continue
        profile: SourceProfile = {}
        n_recs = len(records)
        step = max(1, n_recs // 50)

        for field in records[0].keys():
            numeric_vals: list[float] = []
            string_vals: list[str] = []
            seen_n: set[float] = set()
            seen_s: set[str] = set()

            for idx in range(0, n_recs, step):
                value = records[idx].get(field)
                if value is None:
                    continue
                try:
                    numeric_value = float(value)
                    if numeric_value not in seen_n:
                        seen_n.add(numeric_value)
                        numeric_vals.append(numeric_value)
                except (TypeError, ValueError):
                    string_value = str(value)
                    if string_value not in seen_s:
                        seen_s.add(string_value)
                        string_vals.append(string_value)

            all_numeric: list[float] = []
            all_strings: list[str] = []
            for record in records[:2000]:
                value = record.get(field)
                if value is None:
                    continue
                try:
                    all_numeric.append(float(value))
                except (TypeError, ValueError):
                    all_strings.append(str(value))

            field_profile: SourceFieldProfile = {
                "numeric": all_numeric,
                "strings": all_strings,
                "is_numeric": len(all_numeric) > len(all_strings),
                "unique_count": len({str(v) for v in (all_numeric or all_strings)[:200]}),
                "total_count": len(all_numeric) + len(all_strings),
                "sample_values": [str(v) for v in numeric_vals[:100]] + string_vals[:100],
            }
            if all_numeric:
                numeric_count = len(all_numeric)
                mean = sum(all_numeric) / numeric_count
                field_profile["mean"] = mean
                field_profile["std"] = math.sqrt(
                    sum((value - mean) ** 2 for value in all_numeric) / max(numeric_count - 1, 1)
                )
                field_profile["min"] = min(all_numeric)
                field_profile["max"] = max(all_numeric)
            profile[field] = field_profile

        source_profiles[src_name] = profile

    return source_profiles


async def build_unified_schema(
    source_profiles: SourceProfiles,
    source_mojo_profiles: dict[str, dict[str, Any]],
    *,
    semantic_similarity_fn: SemanticSimilarityFn,
    call_mojo_field_map_fn: FieldMapFn,
) -> UnifiedSchemaBuildResult:
    unified: dict[str, SchemaField] = {}
    all_fields_seen: set[str] = set()

    for src_name, profile in source_profiles.items():
        mojo_profiles = source_mojo_profiles.get(src_name, {}).get("profiles", {})
        numeric_arrays = {
            field: info["numeric"]
            for field, info in profile.items()
            if info["is_numeric"] and info["numeric"]
        }
        mojo_field_result = await call_mojo_field_map_fn(numeric_arrays) if numeric_arrays else None

        for field, info in profile.items():
            canonical = field
            for existing_key in unified:
                similarity, _reasons = semantic_similarity_fn(field, existing_key)
                if similarity > 0.85:
                    canonical = existing_key
                    break

            if canonical not in unified:
                polarity = 0
                distribution = None
                unit = None

                mojo_profile = mojo_profiles.get(field, {})
                if mojo_profile:
                    polarity = mojo_profile.get("polarity", 0)
                    distribution = mojo_profile.get("distribution") or None
                    unit = mojo_profile.get("unit_hint") or None
                elif mojo_field_result and field in mojo_field_result.get(
                    "field_analysis",
                    {},
                ):
                    field_analysis = mojo_field_result["field_analysis"][field]
                    polarity = field_analysis.get("polarity", 0)
                    distribution = field_analysis.get("distribution")
                    unit = field_analysis.get("unit", "") or None

                unified[canonical] = SchemaField(
                    name=canonical,
                    sources=[src_name],
                    distribution=distribution,
                    unit=unit,
                    polarity=polarity,
                    sample_values=(
                        info["numeric"][:3] if info["is_numeric"] else info["strings"][:3]
                    ),
                )
            elif src_name not in unified[canonical].sources:
                unified[canonical].sources.append(src_name)

            all_fields_seen.add(canonical)

    return UnifiedSchemaBuildResult(
        unified_schema=unified,
        all_fields_seen=all_fields_seen,
    )
