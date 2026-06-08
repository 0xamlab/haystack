from __future__ import annotations

from typing import Any

from . import sdk_defaults

DEFAULT_JOIN_PATH_HOPS = sdk_defaults.DEFAULT_JOIN_PATH_HOPS
MAX_JOIN_PATH_HOPS = sdk_defaults.MAX_JOIN_PATH_HOPS


def _normalize_max_join_hops(value: Any, field_path: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_path} must be an integer between 1 and {MAX_JOIN_PATH_HOPS}.")
    if value < 1 or value > MAX_JOIN_PATH_HOPS:
        raise ValueError(f"{field_path} must be between 1 and {MAX_JOIN_PATH_HOPS}.")
    return value


def _normalize_query_like_request(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    join_path = normalized.get("join_path")
    if isinstance(join_path, dict):
        join_path_payload = dict(join_path)
        max_hops = join_path_payload.get("max_hops", DEFAULT_JOIN_PATH_HOPS)
        max_hops = _normalize_max_join_hops(max_hops, "join_path.max_hops")
        join_path_payload["max_hops"] = max_hops
        edges = join_path_payload.get("edges")
        if isinstance(edges, list) and len(edges) > max_hops:
            raise ValueError(
                f"join_path.edges has {len(edges)} entries but join_path.max_hops={max_hops}."
            )
        normalized["join_path"] = join_path_payload
    constraints = normalized.get("constraints")
    if isinstance(constraints, dict) and "max_join_hops" in constraints:
        constraints_payload = dict(constraints)
        constraints_payload["max_join_hops"] = _normalize_max_join_hops(
            constraints_payload["max_join_hops"], "constraints.max_join_hops"
        )
        normalized["constraints"] = constraints_payload
    return normalized


def _merge_request_payload(
    payload: dict[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(payload or {})
    merged.update(kwargs)
    return _normalize_query_like_request(merged)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _request_source_set(request: dict[str, Any]) -> list[str]:
    values: list[str] = []

    source_name = request.get("source_name")
    if isinstance(source_name, str):
        values.append(source_name)

    join_source_name = request.get("join_source_name")
    if isinstance(join_source_name, str):
        values.append(join_source_name)

    sources = request.get("sources")
    if isinstance(sources, list):
        values.extend(
            source.get("name", "")
            for source in sources
            if isinstance(source, dict) and isinstance(source.get("name"), str)
        )

    join_path = request.get("join_path")
    if isinstance(join_path, dict):
        for key in ("base_source", "group_source"):
            value = join_path.get(key)
            if isinstance(value, str):
                values.append(value)
        edges = join_path.get("edges")
        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                for key in ("left_source", "right_source"):
                    value = edge.get(key)
                    if isinstance(value, str):
                        values.append(value)

    return _dedupe_strings(values)


def _split_resolved_sources(resolved_source: str | None) -> list[str]:
    if not resolved_source:
        return []
    return _dedupe_strings([part.strip() for part in resolved_source.split("⋈")])


__all__ = [
    "DEFAULT_JOIN_PATH_HOPS",
    "MAX_JOIN_PATH_HOPS",
    "_merge_request_payload",
    "_normalize_query_like_request",
    "_request_source_set",
    "_split_resolved_sources",
]
