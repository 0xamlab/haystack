"""Deterministic discovery helpers for dataset listing surfaces."""

from __future__ import annotations

from typing import Any


def normalize_discovery_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def discovery_dataset_id(entry: dict[str, Any]) -> str:
    return str(entry.get("dataset_id") or entry.get("id") or "").strip()


def discovery_dataset_name(entry: dict[str, Any]) -> str:
    return str(
        entry.get("dataset_name")
        or entry.get("name")
        or entry.get("source_name")
        or discovery_dataset_id(entry)
    ).strip()


def discovery_dataset_status(entry: dict[str, Any]) -> str:
    status = str(entry.get("status") or "").strip()
    return status or "ready"


def discovery_source_names(entry: dict[str, Any]) -> list[str]:
    source_names = entry.get("source_names")
    if isinstance(source_names, list):
        normalized = [str(item).strip() for item in source_names if str(item).strip()]
        if normalized:
            return normalized
    fallback = str(entry.get("source_name") or entry.get("name") or "").strip()
    return [fallback] if fallback else []


def _search_match_rank(candidate: str, search: str) -> int:
    if not candidate or not search:
        return 0
    if candidate == search:
        return 3
    if candidate.startswith(search):
        return 2
    if search in candidate:
        return 1
    return 0


def discovery_search_rank(entry: dict[str, Any], search: str | None) -> int:
    normalized_search = normalize_discovery_text(search)
    if not normalized_search:
        return 0
    candidates = [
        discovery_dataset_id(entry),
        discovery_dataset_name(entry),
        *discovery_source_names(entry),
    ]
    return max(
        (
            _search_match_rank(normalize_discovery_text(candidate), normalized_search)
            for candidate in candidates
        ),
        default=0,
    )


def filter_discovery_entries(
    entries: list[dict[str, Any]],
    *,
    search: str | None = None,
    status: str | None = None,
    source_name: str | None = None,
) -> list[dict[str, Any]]:
    normalized_status = normalize_discovery_text(status)
    normalized_source_name = normalize_discovery_text(source_name)
    normalized_search = normalize_discovery_text(search)

    matched: list[tuple[int, dict[str, Any]]] = []
    for entry in entries:
        if normalized_status and discovery_dataset_status(entry).lower() != normalized_status:
            continue
        if normalized_source_name:
            source_matches = {
                normalize_discovery_text(candidate) for candidate in discovery_source_names(entry)
            }
            if normalized_source_name not in source_matches:
                continue
        if normalized_search:
            rank = discovery_search_rank(entry, normalized_search)
            if rank <= 0:
                continue
            matched.append((rank, entry))
            continue
        matched.append((0, entry))

    if not normalized_search:
        return [entry for _rank, entry in matched]

    matched.sort(
        key=lambda item: (
            -item[0],
            normalize_discovery_text(discovery_dataset_name(item[1])),
            normalize_discovery_text(discovery_dataset_id(item[1])),
        )
    )
    return [entry for _rank, entry in matched]


__all__ = [
    "discovery_dataset_id",
    "discovery_dataset_name",
    "discovery_dataset_status",
    "discovery_source_names",
    "filter_discovery_entries",
    "normalize_discovery_text",
]
