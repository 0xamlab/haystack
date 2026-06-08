"""Discovery labels and metadata derived from connector browse results."""

from __future__ import annotations

from typing import Any

from apps.api_server.services.connectors import normalize_type

_SQL_DATABASE_TYPES = {
    "postgres",
    "postgresql",
    "mysql",
    "mssql",
    "redshift",
    "clickhouse",
    "snowflake",
    "bigquery",
    "sqlite",
}
_OBJECT_STORAGE_TYPES = {"s3", "gcs", "azure", "azure_blob"}
_API_TYPES = {"rest", "rest_api"}
_REPOSITORY_TYPES = {"github_repo", "gitlab_repo", "bitbucket_repo", "local_repo", "repo_archive"}


def _safe_positive_int(raw_value: Any, *, default: int) -> int:
    if raw_value in (None, ""):
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def build_discovery_labels(
    connector_type: str,
    *,
    config: dict[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_type = normalize_type(connector_type)
    cfg = config or {}
    discovered_items = items or []
    provider_info = provider_metadata or {}
    count_kind = str(provider_info.get("count_kind", "") or "").strip().lower()
    sampled_override = count_kind == "sample" if count_kind in {"sample", "exact"} else None

    labels: dict[str, Any] = {
        "entity_noun": "dataset",
        "entity_noun_plural": "datasets",
        "row_noun": "row",
        "row_noun_plural": "rows",
        "rows_unavailable": False,
        "sampled": False,
    }

    if normalized_type in _SQL_DATABASE_TYPES:
        labels.update(
            {
                "entity_noun": "table",
                "entity_noun_plural": "tables",
                "row_noun": "row",
                "row_noun_plural": "rows",
            }
        )
        explicit_scope = bool(
            str(cfg.get("schema", "") or "").strip()
            or (normalized_type == "clickhouse" and str(cfg.get("database", "") or "").strip())
        )
        labels["sampled"] = (
            sampled_override
            if sampled_override is not None
            else not explicit_scope and len(discovered_items) >= 200 and len(discovered_items) > 0
        )
        return labels

    if normalized_type == "elasticsearch":
        labels.update(
            {
                "entity_noun": "index",
                "entity_noun_plural": "indices",
                "row_noun": "document",
                "row_noun_plural": "documents",
            }
        )
        browse_limit = _safe_positive_int(
            cfg.get("limit", cfg.get("size")),
            default=100,
        )
        labels["sampled"] = (
            sampled_override
            if sampled_override is not None
            else len(discovered_items) >= browse_limit and len(discovered_items) > 0
        )
        return labels

    if normalized_type == "redis":
        labels.update(
            {
                "entity_noun": "key",
                "entity_noun_plural": "keys",
                "row_noun": "value",
                "row_noun_plural": "values",
                "rows_unavailable": True,
            }
        )
        browse_limit = _safe_positive_int(cfg.get("limit"), default=100)
        labels["sampled"] = (
            sampled_override
            if sampled_override is not None
            else len(discovered_items) >= browse_limit and len(discovered_items) > 0
        )
        return labels

    if normalized_type == "neo4j":
        labels.update(
            {
                "entity_noun": "graph type",
                "entity_noun_plural": "graph types",
                "row_noun": "record",
                "row_noun_plural": "records",
                "rows_unavailable": True,
            }
        )
        browse_limit = _safe_positive_int(cfg.get("limit"), default=50)
        labels["sampled"] = (
            sampled_override
            if sampled_override is not None
            else len(discovered_items) >= browse_limit and len(discovered_items) > 0
        )
        return labels

    if normalized_type in _OBJECT_STORAGE_TYPES:
        labels.update(
            {
                "entity_noun": "object",
                "entity_noun_plural": "objects",
                "row_noun": "record",
                "row_noun_plural": "records",
                "rows_unavailable": True,
            }
        )
        labels["sampled"] = (
            sampled_override
            if sampled_override is not None
            else len(discovered_items) >= 100 and len(discovered_items) > 0
        )
        return labels

    if normalized_type in _API_TYPES:
        labels.update(
            {
                "entity_noun": "endpoint",
                "entity_noun_plural": "endpoints",
                "row_noun": "record",
                "row_noun_plural": "records",
                "rows_unavailable": True,
            }
        )
        return labels

    if normalized_type in _REPOSITORY_TYPES:
        labels.update(
            {
                "entity_noun": "repository entry",
                "entity_noun_plural": "repository entries",
                "row_noun": "line",
                "row_noun_plural": "lines",
                "rows_unavailable": True,
            }
        )
        labels["sampled"] = len(discovered_items) >= 100 and len(discovered_items) > 0
        return labels

    return labels


def _base_discovery_metadata(
    *,
    scope_noun: str,
    returned_count: int,
    count_kind: str,
    matching_total_count: int | None,
    scope_total_count: int | None,
    more_available: bool,
    sampling_reason: str | None,
) -> dict[str, Any]:
    return {
        "scope_noun": scope_noun,
        "returned_count": returned_count,
        "count_kind": count_kind,
        "matching_total_count": matching_total_count,
        "scope_total_count": scope_total_count,
        "more_available": more_available,
        "sampling_reason": sampling_reason,
    }


def build_discovery_metadata(
    connector_type: str,
    *,
    config: dict[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_type = normalize_type(connector_type)
    cfg = config or {}
    discovered_items = items or []
    provider_info = provider_metadata or {}
    returned_count = len(discovered_items)

    if normalized_type in _SQL_DATABASE_TYPES:
        explicit_scope = bool(
            str(cfg.get("schema", "") or "").strip()
            or (normalized_type == "clickhouse" and str(cfg.get("database", "") or "").strip())
        )
        sampled = not explicit_scope and returned_count >= 200 and returned_count > 0
        return _base_discovery_metadata(
            scope_noun="catalog",
            returned_count=returned_count,
            count_kind="sample" if sampled else "exact",
            matching_total_count=None if sampled else returned_count,
            scope_total_count=None if sampled else returned_count,
            more_available=sampled,
            sampling_reason="browse_limit" if sampled else None,
        )

    if normalized_type == "elasticsearch":
        browse_limit = _safe_positive_int(
            cfg.get("limit", cfg.get("size")),
            default=100,
        )
        sampled = returned_count >= browse_limit and returned_count > 0
        return _base_discovery_metadata(
            scope_noun="index catalog",
            returned_count=returned_count,
            count_kind="sample" if sampled else "exact",
            matching_total_count=None if sampled else returned_count,
            scope_total_count=None if sampled else returned_count,
            more_available=sampled,
            sampling_reason="browse_limit" if sampled else None,
        )

    if normalized_type == "redis":
        scan_exhausted = bool(provider_info.get("scan_exhausted"))
        keyspace_total_count = provider_info.get("keyspace_total_count")
        return _base_discovery_metadata(
            scope_noun="keyspace",
            returned_count=returned_count,
            count_kind="exact" if scan_exhausted else "sample",
            matching_total_count=returned_count if scan_exhausted else None,
            scope_total_count=_safe_positive_int(keyspace_total_count, default=0) or None,
            more_available=not scan_exhausted,
            sampling_reason=None if scan_exhausted else "keyspace_scan_limit",
        )

    if normalized_type == "neo4j":
        browse_limit = _safe_positive_int(cfg.get("limit"), default=50)
        sampled = returned_count >= browse_limit and returned_count > 0
        return _base_discovery_metadata(
            scope_noun="graph catalog",
            returned_count=returned_count,
            count_kind="sample" if sampled else "exact",
            matching_total_count=None if sampled else returned_count,
            scope_total_count=None if sampled else returned_count,
            more_available=sampled,
            sampling_reason="browse_limit" if sampled else None,
        )

    if normalized_type in _OBJECT_STORAGE_TYPES:
        sampled = returned_count >= 100 and returned_count > 0
        return _base_discovery_metadata(
            scope_noun="object listing",
            returned_count=returned_count,
            count_kind="sample" if sampled else "exact",
            matching_total_count=None if sampled else returned_count,
            scope_total_count=None if sampled else returned_count,
            more_available=sampled,
            sampling_reason="browse_limit" if sampled else None,
        )

    if normalized_type in _API_TYPES:
        return _base_discovery_metadata(
            scope_noun="endpoint catalog",
            returned_count=returned_count,
            count_kind="exact",
            matching_total_count=returned_count,
            scope_total_count=returned_count,
            more_available=False,
            sampling_reason=None,
        )

    if normalized_type in _REPOSITORY_TYPES:
        sampled = returned_count >= 100 and returned_count > 0
        return _base_discovery_metadata(
            scope_noun="repository tree",
            returned_count=returned_count,
            count_kind="sample" if sampled else "exact",
            matching_total_count=None if sampled else returned_count,
            scope_total_count=None if sampled else returned_count,
            more_available=sampled,
            sampling_reason="browse_limit" if sampled else None,
        )

    return _base_discovery_metadata(
        scope_noun="catalog",
        returned_count=returned_count,
        count_kind="exact",
        matching_total_count=returned_count,
        scope_total_count=returned_count,
        more_available=False,
        sampling_reason=None,
    )


__all__ = [
    "build_discovery_labels",
    "build_discovery_metadata",
]
