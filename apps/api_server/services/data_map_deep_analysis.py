from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from apps.api_server.schemas.data_map import FieldMapping, SchemaField

SourceProfiles = dict[str, dict[str, dict[str, Any]]]
JoinDetectFn = Callable[
    [str, str, dict[str, dict[str, Any]], float],
    Awaitable[dict[str, Any] | None],
]
RelationDetectFn = Callable[[str, dict[str, list[float]]], Awaitable[dict[str, Any] | None]]
FieldMapFn = Callable[[dict[str, list[float]]], Awaitable[dict[str, Any] | None]]
DetectDerivedRelationshipsFn = Callable[..., list[dict[str, Any]]]
NormalizeFn = Callable[[str], str]


def deep_store_key(org_id: str, map_id: str) -> str:
    """Cross-tenant guard: the deep-analysis store is a process-global dict shared across all orgs,
    so its key MUST include the owning org — otherwise GET /v1/map/{map_id} would serve any org's
    analysis by map_id (IDOR). Writer and reader must build the key the same way."""
    return f"{org_id}:{map_id}"


def _empty_deep_analysis(map_id: str) -> dict[str, Any]:
    return {
        "map_id": map_id,
        "join_keys": [],
        "derived_relationships": [],
        "simulation_ready": False,
        "simulation_payload": None,
    }


def _build_join_columns(
    source_profiles: SourceProfiles,
    src_a: str,
    src_b: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for src_name in (src_a, src_b):
        for field, info in source_profiles[src_name].items():
            all_values = [str(value) for value in info["numeric"][:100]] + info["strings"][:100]
            unique_ratio = info["unique_count"] / max(info["total_count"], 1)
            result[f"{src_name}.{field}"] = {
                "values": all_values[:200],
                "unique_ratio": unique_ratio,
                "sample_size": info["total_count"],
            }
    return result


def _build_relation_columns(
    parsed_sources: dict[str, list[dict[str, Any]]],
    source_profiles: SourceProfiles,
    src_name: str,
) -> dict[str, list[float]]:
    profile = source_profiles.get(src_name, {})
    numeric_fields = [field for field, info in profile.items() if info["is_numeric"]]
    records = parsed_sources.get(src_name, [])
    sample_count = min(len(records), 500)
    result: dict[str, list[float]] = {}
    for field in numeric_fields:
        values: list[float] = []
        for index in range(sample_count):
            value = records[index].get(field, 0)
            try:
                values.append(float(value) if value else 0.0)
            except (TypeError, ValueError):
                values.append(0.0)
        result[field] = values
    return result


async def _build_simulation_payload(
    parsed_sources: dict[str, list[dict[str, Any]]],
    unified_schema: dict[str, SchemaField],
    *,
    normalize_fn: NormalizeFn,
    call_mojo_field_map_fn: FieldMapFn,
) -> tuple[bool, dict[str, Any] | None]:
    metric_fields = [
        field
        for field, schema in unified_schema.items()
        if schema.distribution
        and schema.distribution != "fixed"
        and not any(
            keyword in normalize_fn(field) for keyword in {"id", "key", "number", "code", "ref"}
        )
    ]
    if not metric_fields:
        return False, None

    primary_records = list(parsed_sources.values())[0] if parsed_sources else []
    primary_numeric = {
        field: [
            float(record.get(field, 0))
            for record in primary_records[:2000]
            if isinstance(record.get(field), int | float)
        ]
        for field in metric_fields
    }
    mojo_result = await call_mojo_field_map_fn(primary_numeric) if primary_numeric else None
    if not mojo_result or not mojo_result.get("variables"):
        return False, None

    return True, {
        "mode": "expert",
        "simulation_model": mojo_result.get("engine", "monte_carlo"),
        "runs": 10000,
        "simulation": {
            "variables": mojo_result["variables"],
            "objective_function": mojo_result["objective_function"],
        },
    }


async def run_deep_analysis(
    *,
    map_id: str,
    parsed_sources: dict[str, list[dict[str, Any]]],
    source_profiles: SourceProfiles,
    match_pairs: list[tuple[str, str]],
    mappings: list[FieldMapping],
    unified_schema: dict[str, SchemaField],
    call_mojo_join_detect_fn: JoinDetectFn,
    call_mojo_relation_detect_fn: RelationDetectFn,
    call_mojo_field_map_fn: FieldMapFn,
    detect_derived_relationships_fn: DetectDerivedRelationshipsFn,
    normalize_fn: NormalizeFn,
) -> dict[str, Any]:
    join_results = await asyncio.gather(
        *[
            call_mojo_join_detect_fn(
                src_a,
                src_b,
                _build_join_columns(source_profiles, src_a, src_b),
                0.4,
            )
            for src_a, src_b in match_pairs
        ]
    )

    join_keys: list[dict[str, Any]] = []
    for (src_a, src_b), join_result in zip(match_pairs, join_results, strict=False):
        if join_result and "join_keys" in join_result:
            join_keys.extend(join_result["join_keys"])
            continue

        for src_name in (src_a, src_b):
            for field, info in source_profiles[src_name].items():
                unique_ratio = info["unique_count"] / max(info["total_count"], 1)
                if unique_ratio <= 0.85:
                    continue
                for mapping in mappings:
                    if (mapping.source == src_name and mapping.source_field == field) or (
                        mapping.target == src_name and mapping.target_field == field
                    ):
                        join_keys.append(
                            {
                                "field": field,
                                "source": src_name,
                                "mapped_to": (
                                    mapping.target_field
                                    if mapping.source == src_name
                                    else mapping.source_field
                                ),
                                "in_source": (
                                    mapping.target if mapping.source == src_name else mapping.source
                                ),
                                "confidence": mapping.confidence,
                            }
                        )
                        break

    relation_inputs = [
        (src_name, _build_relation_columns(parsed_sources, source_profiles, src_name))
        for src_name in parsed_sources
    ]
    relation_results = await asyncio.gather(
        *[call_mojo_relation_detect_fn(src_name, columns) for src_name, columns in relation_inputs]
    )

    derived_relationships: list[dict[str, Any]] = []
    for (src_name, _columns), relation_result in zip(
        relation_inputs,
        relation_results,
        strict=False,
    ):
        if relation_result and "relationships" in relation_result:
            for relationship in relation_result["relationships"]:
                relationship["source"] = src_name
            derived_relationships.extend(relation_result["relationships"])
            continue

        profile = source_profiles.get(src_name, {})
        numeric_fields = [field for field, info in profile.items() if info["is_numeric"]]
        derived_relationships.extend(
            detect_derived_relationships_fn(
                parsed_sources[src_name],
                numeric_fields,
                source=src_name,
            )
        )
    derived_relationships.sort(key=lambda relationship: relationship["confidence"], reverse=True)

    simulation_ready, simulation_payload = await _build_simulation_payload(
        parsed_sources,
        unified_schema,
        normalize_fn=normalize_fn,
        call_mojo_field_map_fn=call_mojo_field_map_fn,
    )

    return {
        "map_id": map_id,
        "join_keys": join_keys,
        "derived_relationships": derived_relationships,
        "simulation_ready": simulation_ready,
        "simulation_payload": simulation_payload,
    }


async def run_or_schedule_deep_analysis(
    *,
    org_id: str,
    map_id: str,
    parsed_sources: dict[str, list[dict[str, Any]]],
    source_profiles: SourceProfiles,
    match_pairs: list[tuple[str, str]],
    mappings: list[FieldMapping],
    unified_schema: dict[str, SchemaField],
    deep_store: dict[str, dict[str, Any]],
    deep_budget_s: float,
    logger: Any,
    call_mojo_join_detect_fn: JoinDetectFn,
    call_mojo_relation_detect_fn: RelationDetectFn,
    call_mojo_field_map_fn: FieldMapFn,
    detect_derived_relationships_fn: DetectDerivedRelationshipsFn,
    normalize_fn: NormalizeFn,
) -> tuple[dict[str, Any], bool]:
    deep_task = asyncio.create_task(
        run_deep_analysis(
            map_id=map_id,
            parsed_sources=parsed_sources,
            source_profiles=source_profiles,
            match_pairs=match_pairs,
            mappings=mappings,
            unified_schema=unified_schema,
            call_mojo_join_detect_fn=call_mojo_join_detect_fn,
            call_mojo_relation_detect_fn=call_mojo_relation_detect_fn,
            call_mojo_field_map_fn=call_mojo_field_map_fn,
            detect_derived_relationships_fn=detect_derived_relationships_fn,
            normalize_fn=normalize_fn,
        )
    )

    try:
        deep_analysis = await asyncio.wait_for(
            asyncio.shield(deep_task),
            timeout=deep_budget_s,
        )
        deep_store[deep_store_key(org_id, map_id)] = deep_analysis
        return deep_analysis, False
    except TimeoutError:

        async def _persist_deep() -> None:
            try:
                result = await deep_task
                deep_store[deep_store_key(org_id, map_id)] = result
            except Exception as exc:
                logger.debug("deep_analysis_error", map_id=map_id, error=str(exc))

        asyncio.create_task(_persist_deep())
        return _empty_deep_analysis(map_id), True
