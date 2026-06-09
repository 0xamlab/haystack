"""
Source registry — persistent per-org storage of registered data sources.

Layout on disk:
  {ALGENTA_SOURCES_DIR}/{org_id}/
    index.json             — { source_id: { id, name, registered_at, row_count, roles_summary } }
    connections.json       — [ { source_a, col_a, source_b, col_b, confidence, cardinality, ... } ]
    {source_id}.parquet    — source data with embedded algenta_schema Arrow metadata
    {source_id}.meta.json  — full schema metadata (fast read without loading Parquet)

Sources are content-keyed: same data → same ID, instant re-registration.
"""

from __future__ import annotations

import errno
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import structlog

from . import source_registry_ids as _ids
from . import source_registry_nodes as _nodes
from . import source_registry_persistence as _persistence
from . import source_registry_storage as _storage

logger = structlog.get_logger(__name__)

_SOURCES_DIR = Path(os.environ.get("ALGENTA_SOURCES_DIR", Path.home() / ".algenta" / "sources"))

_JOIN_KEY_NAME_TOKENS = frozenset(
    {
        "account",
        "code",
        "customer",
        "guid",
        "id",
        "identifier",
        "item",
        "key",
        "number",
        "order",
        "part",
        "product",
        "ref",
        "serial",
        "sku",
        "uuid",
        "vendor",
        "warehouse",
    }
)
_DIMENSION_JOIN_TOKENS = frozenset(
    {
        "branch",
        "location",
        "merchant",
        "outlet",
        "restaurant",
        "site",
        "store",
    }
)
_DIMENSION_JOIN_MODIFIER_TOKENS = frozenset(
    {
        "as",
        "eats",
        "external",
        "local",
        "manager",
        "name",
        "per",
        "uber",
        "ubereats",
    }
)
_GENERIC_JOIN_TOKENS = frozenset(
    {
        "a",
        "an",
        "and",
        "by",
        "class",
        "date",
        "desc",
        "description",
        "dim",
        "field",
        "group",
        "label",
        "line",
        "name",
        "no",
        "number",
        "record",
        "row",
        "source",
        "status",
        "synthetic",
        "text",
        "time",
        "timestamp",
        "to",
        "type",
        "value",
    }
)
_NON_JOINABLE_ROLES = frozenset(
    {
        "derived_measure",
        "unit_measure",
        "component",
        "ratio",
    }
)
_INTERNAL_JOIN_METADATA_PREFIX = "__"
_GENERIC_SURROGATE_JOIN_TOKENS = frozenset(
    {
        "inferred",
        "record",
        "row",
        "source",
        "synthetic",
    }
)
_GENERIC_SOURCE_ALIGNED_KEY_TOKENS = frozenset(
    {"code", "guid", "id", "identifier", "key", "number", "ref", "uuid"}
)
_SOURCE_ALIGNED_CANDIDATE_MIN_REFERENCED_UNIQUE_RATIO = 0.98
_SOURCE_ALIGNED_CANDIDATE_MIN_FILL_RATE = 0.25
_SOURCE_ALIGNED_CANDIDATE_BONUS = 5.0
_IMPLICIT_FALLBACK_SOURCES_DIR = Path(tempfile.gettempdir()) / "algenta-sources"
_WRITABLE_SOURCE_DIRS: set[Path] = set()

_SCHEMA_REVISION_CACHE: dict[str, tuple[tuple[Any, ...], str]] = {}
_SOURCE_SCHEMA_REVISION_CACHE: dict[tuple[str, str], tuple[tuple[Any, ...], str]] = {}
_SOURCE_META_CACHE: dict[
    tuple[str, str],
    tuple[tuple[Any, ...], dict[str, Any] | None],
] = {}
_SOURCE_ENTRY_CACHE: dict[
    tuple[str, str],
    tuple[tuple[Any, ...], dict[str, Any] | None],
] = {}
_SOURCE_ENTRY_BY_NAME_CACHE: dict[
    tuple[str, str],
    tuple[tuple[Any, ...], dict[str, Any] | None],
] = {}


def _looks_like_entity_join_key(name: str) -> bool:
    lowered = name.lower()
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    if tokens & _JOIN_KEY_NAME_TOKENS:
        return True
    return any(token in lowered for token in ("_id", "_key", "_code", "_ref", "_uuid", "_guid"))


def _is_generic_surrogate_join_key(name: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
    if not tokens:
        return False
    if not tokens & _GENERIC_SURROGATE_JOIN_TOKENS:
        return False
    if not (
        tokens & _JOIN_KEY_NAME_TOKENS
        or any(
            token in name.lower() for token in ("_id", "_key", "_code", "_ref", "_uuid", "_guid")
        )
    ):
        return False
    non_generic = {
        token
        for token in tokens
        if token not in _JOIN_KEY_NAME_TOKENS
        and token not in _GENERIC_JOIN_TOKENS
        and token not in _GENERIC_SURROGATE_JOIN_TOKENS
    }
    return not non_generic


def _looks_like_low_cardinality_dimension(name: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
    if not tokens & _DIMENSION_JOIN_TOKENS:
        return False
    return bool(_dimension_join_family(name))


def _dimension_join_family(name: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
    families = {"store" for token in tokens if token in _DIMENSION_JOIN_TOKENS}
    if len(families) != 1:
        return ""
    non_dimension = {
        token
        for token in tokens
        if token not in _DIMENSION_JOIN_TOKENS
        and token not in _DIMENSION_JOIN_MODIFIER_TOKENS
        and token not in _GENERIC_JOIN_TOKENS
    }
    if len(non_dimension) > 1:
        return ""
    return next(iter(families))


def _join_tokens(name: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", name.lower()) if token]


def _canonical_source_tokens(name: str) -> set[str]:
    tokens = set(_join_tokens(name))
    expanded = set(tokens)
    for token in tokens:
        if len(token) > 4 and token.endswith("ies"):
            expanded.add(f"{token[:-3]}y")
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            expanded.add(token[:-1])
    return expanded


def _source_aligned_foreign_key_flags(
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
) -> tuple[bool, bool, bool]:
    left_tokens = set(_join_tokens(left_key))
    right_tokens = set(_join_tokens(right_key))
    left_source_tokens = _canonical_source_tokens(left_source)
    right_source_tokens = _canonical_source_tokens(right_source)
    bare_left_id = bool(left_tokens) and left_tokens <= _GENERIC_SOURCE_ALIGNED_KEY_TOKENS
    bare_right_id = bool(right_tokens) and right_tokens <= _GENERIC_SOURCE_ALIGNED_KEY_TOKENS
    left_to_right_overlap = len(left_tokens & right_source_tokens) / max(
        len(right_source_tokens),
        1,
    )
    right_to_left_overlap = len(right_tokens & left_source_tokens) / max(
        len(left_source_tokens),
        1,
    )
    foreign_key_to_right = bare_right_id and left_to_right_overlap >= 0.5
    foreign_key_to_left = bare_left_id and right_to_left_overlap >= 0.5
    generic_bare_id_pair = bare_left_id and bare_right_id
    return foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair


_TRAILING_ZERO_FLOAT_RE = re.compile(r"[-+]?\d{1,64}\.0{1,64}")


def _normalized_sample(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    # Bound input length before regex match to defang any worst-case backtracking
    # path flagged by py/polynomial-redos on '\d+\.0+'-shaped patterns.
    if len(text) <= 130 and _TRAILING_ZERO_FLOAT_RE.fullmatch(text):
        text = text.split(".", 1)[0]
    text = re.sub(r"\s+", " ", text)
    return text


def _build_join_blocks(schema_meta: dict[str, Any]) -> list[dict[str, Any]]:
    planner_profile = schema_meta.get("planner_profile") or {}
    columns_meta = {
        str(col.get("name", "")): col
        for col in (schema_meta.get("columns") or [])
        if col.get("name")
    }

    blocks: list[dict[str, Any]] = []
    for col_name, prof in planner_profile.items():
        if str(col_name).startswith(_INTERNAL_JOIN_METADATA_PREFIX):
            continue
        if _is_generic_surrogate_join_key(str(col_name)):
            continue
        col_meta = columns_meta.get(col_name, {})
        key_like = _looks_like_entity_join_key(col_name)
        role = str(col_meta.get("role", ""))
        is_numeric = bool(prof.get("is_numeric", col_meta.get("is_numeric", False)))
        fill_rate = float(prof.get("fill_rate", col_meta.get("fill_rate", 0.0)) or 0.0)
        total_count = int(prof.get("total_count", 0) or 0)
        unique_count = int(prof.get("unique_count", col_meta.get("cardinality", 0)) or 0)
        if fill_rate < 0.05 or total_count <= 0 or (unique_count <= 1 and not key_like):
            continue
        dimension_like = _looks_like_low_cardinality_dimension(col_name)
        if role in _NON_JOINABLE_ROLES and not key_like:
            continue
        if role == "time" and not key_like and not dimension_like:
            continue
        if is_numeric and not key_like and role not in {"identifier", "time", "text"}:
            continue

        unique_ratio = unique_count / max(total_count, 1)
        if not key_like and not dimension_like and unique_count <= 3 and unique_ratio < 0.10:
            continue

        tokens = _join_tokens(col_name)
        core_tokens = [token for token in tokens if token not in _GENERIC_JOIN_TOKENS]
        if not core_tokens:
            core_tokens = tokens[-2:] if len(tokens) >= 2 else tokens
        tail = (
            "_".join(core_tokens[-2:])
            if len(core_tokens) >= 2
            else (core_tokens[0] if core_tokens else "")
        )

        sample_values = (prof.get("sample_values") or col_meta.get("samples") or [])[:8]
        samples = [
            normalized
            for normalized in (_normalized_sample(value) for value in sample_values)
            if normalized and normalized not in {"none", "null", "nan", "n/a", "na", "?"}
        ]
        joinability = (
            (1.2 if key_like else 0.0)
            + (0.35 if dimension_like else 0.0)
            + (0.7 if role == "identifier" else 0.0)
            + min(unique_ratio, 1.0) * 0.8
            + min(fill_rate, 1.0) * 0.2
        )
        if not key_like and not dimension_like and unique_ratio < 0.02:
            joinability -= 0.6

        blocks.append(
            {
                "name": col_name,
                "norm": "".join(tokens),
                "tokens": tokens[:6],
                "core_tokens": core_tokens[:4],
                "tail": tail,
                "key_like": key_like,
                "role": role,
                "is_numeric": is_numeric,
                "unique_count": unique_count,
                "unique_ratio": round(unique_ratio, 6),
                "fill_rate": round(fill_rate, 4),
                "samples": samples,
                "joinability": round(max(joinability, 0.0), 6),
            }
        )

    blocks.sort(key=lambda block: (block["joinability"], block["unique_count"]), reverse=True)
    return blocks[:24]


def _score_join_block_pair(left: dict[str, Any], right: dict[str, Any]) -> float:
    score = 0.0
    left_dimension_family = _dimension_join_family(str(left.get("name") or ""))
    right_dimension_family = _dimension_join_family(str(right.get("name") or ""))
    same_dimension_family = (
        bool(left_dimension_family) and left_dimension_family == right_dimension_family
    )
    if left.get("norm") and left.get("norm") == right.get("norm"):
        score += 6.0

    left_tokens = set(left.get("core_tokens") or left.get("tokens") or [])
    right_tokens = set(right.get("core_tokens") or right.get("tokens") or [])
    if left_tokens and right_tokens:
        token_jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        score += token_jaccard * 4.0
    else:
        token_jaccard = 0.0

    if left.get("tail") and left.get("tail") == right.get("tail"):
        score += 2.0
    if left.get("key_like") and right.get("key_like"):
        score += 1.5
    if left.get("role") and left.get("role") == right.get("role"):
        score += 0.6

    unique_gap = abs(float(left.get("unique_ratio", 0.0)) - float(right.get("unique_ratio", 0.0)))
    score += max(0.0, 1.0 - unique_gap * 2.0)

    left_samples = set(left.get("samples") or [])
    right_samples = set(right.get("samples") or [])
    if left_samples and right_samples:
        sample_overlap = len(left_samples & right_samples)
        if sample_overlap:
            score += 2.0 + min(sample_overlap, 3) * 0.5

    if not left.get("key_like") and not right.get("key_like") and not same_dimension_family:
        if (
            token_jaccard < 0.34
            and left.get("unique_count", 0) <= 5
            and right.get("unique_count", 0) <= 5
        ):
            score -= 2.0
        if (
            float(left.get("unique_ratio", 0.0)) < 0.05
            and float(right.get("unique_ratio", 0.0)) < 0.05
        ):
            score -= 1.0

    return round(score, 6)


def _score_candidate_source(
    left_blocks: list[dict[str, Any]],
    right_blocks: list[dict[str, Any]],
    *,
    left_source_name: str | None = None,
    right_source_name: str | None = None,
) -> float:
    pair_scores: list[float] = []
    for left in left_blocks:
        for right in right_blocks:
            score = _score_join_block_pair(left, right)
            if left_source_name and right_source_name:
                left_name = str(left.get("name") or "")
                right_name = str(right.get("name") or "")
                foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair = (
                    _source_aligned_foreign_key_flags(
                        left_source_name,
                        right_source_name,
                        left_name,
                        right_name,
                    )
                )
                if not generic_bare_id_pair and foreign_key_to_right != foreign_key_to_left:
                    if foreign_key_to_right:
                        referenced = right
                        foreign = left
                    else:
                        referenced = left
                        foreign = right
                    referenced_unique_ratio = float(referenced.get("unique_ratio") or 0.0)
                    foreign_fill_rate = float(foreign.get("fill_rate") or 0.0)
                    referenced_fill_rate = float(referenced.get("fill_rate") or 0.0)
                    if (
                        referenced_unique_ratio
                        >= _SOURCE_ALIGNED_CANDIDATE_MIN_REFERENCED_UNIQUE_RATIO
                        and foreign_fill_rate >= _SOURCE_ALIGNED_CANDIDATE_MIN_FILL_RATE
                        and referenced_fill_rate >= _SOURCE_ALIGNED_CANDIDATE_MIN_FILL_RATE
                        and (
                            bool(foreign.get("key_like"))
                            or str(foreign.get("role") or "") == "identifier"
                            or _looks_like_entity_join_key(str(foreign.get("name") or ""))
                        )
                    ):
                        score += _SOURCE_ALIGNED_CANDIDATE_BONUS
            if score >= 4.0:
                pair_scores.append(score)
    if not pair_scores:
        return 0.0
    pair_scores.sort(reverse=True)
    return round(sum(pair_scores[:3]), 6)


def _is_sources_dir_write_error(exc: OSError) -> bool:
    return getattr(exc, "errno", None) in {errno.EACCES, errno.EPERM, errno.EROFS}


def _org_dir_for_base(sources_dir: Path, org_id: str) -> Path:
    directory = _storage.org_dir(sources_dir, org_id)
    if sources_dir not in _WRITABLE_SOURCE_DIRS:
        with tempfile.TemporaryFile(dir=directory):
            pass
        _WRITABLE_SOURCE_DIRS.add(sources_dir)
    return directory


def _org_dir(org_id: str) -> Path:
    global _SOURCES_DIR
    try:
        return _org_dir_for_base(_SOURCES_DIR, org_id)
    except OSError as exc:
        if os.environ.get("ALGENTA_SOURCES_DIR") or not _is_sources_dir_write_error(exc):
            raise
        fallback_dir = _org_dir_for_base(_IMPLICIT_FALLBACK_SOURCES_DIR, org_id)
        if _SOURCES_DIR != _IMPLICIT_FALLBACK_SOURCES_DIR:
            logger.warning(
                "source_registry_default_dir_unwritable",
                configured=str(_SOURCES_DIR),
                fallback=str(_IMPLICIT_FALLBACK_SOURCES_DIR),
                error=str(exc),
            )
            _SOURCES_DIR = _IMPLICIT_FALLBACK_SOURCES_DIR
        return fallback_dir


def _read_json(path: Path) -> Any:
    return _storage.read_json(path)


def _write_json(path: Path, data: Any) -> None:
    _storage.write_json(path, data)


def _path_fingerprint(path: Path) -> tuple[int, int]:
    return _storage.path_fingerprint(path)


def _schema_stamp_path(org_dir: Path) -> Path:
    return _storage.schema_stamp_path(org_dir)


def _touch_schema_stamp(org_dir: Path) -> None:
    _storage.touch_schema_stamp(org_dir)


def _schema_stamp_value(org_dir: Path) -> str:
    return _storage.schema_stamp_value(org_dir)


def _source_meta_cache_key(org_id: str, source_id: str) -> tuple[str, str]:
    return _storage.source_meta_cache_key(org_id, source_id)


def _source_entry_cache_key(org_id: str, source_id: str) -> tuple[str, str]:
    return _storage.source_entry_cache_key(org_id, source_id)


def _set_source_meta_cache(org_id: str, source_id: str, meta: dict[str, Any] | None) -> None:
    _storage.set_source_meta_cache(
        org_id=org_id,
        source_id=source_id,
        meta=meta,
        org_dir=_org_dir(org_id),
        cache=_SOURCE_META_CACHE,
        path_fingerprint_fn=_path_fingerprint,
        cache_key_fn=_source_meta_cache_key,
    )


def _set_source_entry_cache(org_id: str, source_id: str, entry: dict[str, Any] | None) -> None:
    _storage.set_source_entry_cache(
        org_id=org_id,
        source_id=source_id,
        entry=entry,
        org_dir=_org_dir(org_id),
        cache=_SOURCE_ENTRY_CACHE,
        path_fingerprint_fn=_path_fingerprint,
        cache_key_fn=_source_entry_cache_key,
    )


def _clear_source_meta_cache(org_id: str, source_id: str) -> None:
    _storage.clear_source_meta_cache(
        org_id=org_id,
        source_id=source_id,
        cache=_SOURCE_META_CACHE,
        cache_key_fn=_source_meta_cache_key,
    )


def _clear_source_entry_cache(org_id: str, source_id: str) -> None:
    _storage.clear_source_entry_cache(
        org_id=org_id,
        source_id=source_id,
        cache=_SOURCE_ENTRY_CACHE,
        cache_key_fn=_source_entry_cache_key,
    )


# ── Public API ──────────────────────────────────────────────────────────────────


def source_id_for(content_key: str | None, *, path_key: str | None = None) -> str:
    return _ids.source_id_for(content_key, path_key=path_key)


def list_sources(org_id: str) -> list[dict[str, Any]]:
    """Return all registered sources for an org (from index.json)."""
    return _persistence.list_sources(
        org_id=org_id,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
    )


def get_source_entry(org_id: str, source_id: str) -> dict[str, Any] | None:
    """Return one registry index entry for a source, or None if it does not exist."""
    return _persistence.get_source_entry(
        org_id=org_id,
        source_id=source_id,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        path_fingerprint_fn=_path_fingerprint,
        source_entry_cache=_SOURCE_ENTRY_CACHE,
        source_entry_cache_key_fn=_source_entry_cache_key,
    )


def get_source_entry_by_name(org_id: str, source_name: str) -> dict[str, Any] | None:
    """Return one registry index entry by source name, or None if it does not exist."""
    return _persistence.get_source_entry_by_name(
        org_id=org_id,
        source_name=source_name,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        path_fingerprint_fn=_path_fingerprint,
        source_entry_by_name_cache=_SOURCE_ENTRY_BY_NAME_CACHE,
    )


def update_source_entry(
    org_id: str,
    source_id: str,
    updates: dict[str, Any],
    *,
    touch_schema: bool = True,
) -> dict[str, Any] | None:
    """Patch a registry index entry in place and return the updated value."""
    return _persistence.update_source_entry(
        org_id=org_id,
        source_id=source_id,
        updates=updates,
        touch_schema=touch_schema,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        write_json_fn=_write_json,
        set_source_entry_cache_fn=_set_source_entry_cache,
        touch_schema_stamp_fn=_touch_schema_stamp,
        schema_revision_cache=_SCHEMA_REVISION_CACHE,
    )


def candidate_join_sources(
    org_id: str,
    source_id: str,
    schema_meta: dict[str, Any],
    *,
    source_name: str | None = None,
    limit: int = 24,
    exhaustive_threshold: int = 24,
    min_score: float = 4.5,
) -> list[dict[str, Any]]:
    """
    Return likely join candidates for a newly registered source.

    This is the enterprise-scale blocker stage: avoid O(N^2) deep pair scans by
    first matching compact per-source join signatures from registry metadata.
    """
    return _persistence.candidate_join_sources(
        org_id=org_id,
        source_id=source_id,
        schema_meta=schema_meta,
        source_name=source_name,
        limit=limit,
        exhaustive_threshold=exhaustive_threshold,
        min_score=min_score,
        list_sources_fn=list_sources,
        build_join_blocks_fn=_build_join_blocks,
        score_candidate_source_fn=_score_candidate_source,
    )


def get_source_meta(org_id: str, source_id: str) -> dict[str, Any] | None:
    """Return full schema metadata for a source."""
    return _persistence.get_source_meta(
        org_id=org_id,
        source_id=source_id,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        path_fingerprint_fn=_path_fingerprint,
        source_meta_cache=_SOURCE_META_CACHE,
        source_meta_cache_key_fn=_source_meta_cache_key,
    )


def update_source_meta(
    org_id: str,
    source_id: str,
    updates: dict[str, Any],
    *,
    touch_schema: bool = True,
) -> dict[str, Any] | None:
    """Patch a source metadata document in place and return the updated value."""
    return _persistence.update_source_meta(
        org_id=org_id,
        source_id=source_id,
        updates=updates,
        touch_schema=touch_schema,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        write_json_fn=_write_json,
        set_source_meta_cache_fn=_set_source_meta_cache,
        set_source_entry_cache_fn=_set_source_entry_cache,
        touch_schema_stamp_fn=_touch_schema_stamp,
        source_schema_revision_fn=source_schema_revision,
        schema_revision_cache=_SCHEMA_REVISION_CACHE,
    )


def get_source_parquet(org_id: str, source_id: str) -> bytes | None:
    """Return raw Parquet bytes for a source, or None if not registered."""
    return _persistence.get_source_parquet(
        org_id=org_id,
        source_id=source_id,
        org_dir_fn=_org_dir,
    )


def get_source_parquet_path(org_id: str, source_id: str) -> Path | None:
    """Return the on-disk Parquet path for a source, or None if not registered."""
    return _persistence.get_source_parquet_path(
        org_id=org_id,
        source_id=source_id,
        org_dir_fn=_org_dir,
    )


def get_connections(org_id: str) -> list[dict[str, Any]]:
    """Return all detected join connections for an org."""
    return _persistence.get_connections(
        org_id=org_id,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
    )


def schema_revision(org_id: str) -> str:
    """
    Stable fingerprint for an org's registered schema graph.

    This changes when sources are added/re-registered/removed or when the
    connection graph changes. Query-time planner caches can key off this so
    they rebuild only when the customer's schema actually changes.
    """
    return _persistence.schema_revision(
        org_id=org_id,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        path_fingerprint_fn=_path_fingerprint,
        schema_stamp_path_fn=_schema_stamp_path,
        schema_stamp_value_fn=_schema_stamp_value,
        schema_revision_cache=_SCHEMA_REVISION_CACHE,
    )


def source_schema_revision(org_id: str, source_id: str) -> str:
    """
    Stable fingerprint for a single source's executable contents.

    This is cheaper than the org-wide schema revision and is safe for
    single-source exact queries that do not depend on cross-source joins.
    """
    return _persistence.source_schema_revision(
        org_id=org_id,
        source_id=source_id,
        org_dir_fn=_org_dir,
        path_fingerprint_fn=_path_fingerprint,
        source_schema_revision_cache=_SOURCE_SCHEMA_REVISION_CACHE,
    )


def register_source(
    org_id: str,
    source_id: str,
    name: str,
    parquet_bytes: bytes,
    schema_meta: dict[str, Any],
    graph_nodes: dict[str, Any],  # col → ColumnNode (serialized to dict)
    profile: dict[str, Any],
    **entry_meta: Any,
) -> dict[str, Any]:
    """
    Persist a source to disk.
    Returns the index entry dict.
    """
    del graph_nodes, profile
    return _persistence.register_source(
        org_id=org_id,
        source_id=source_id,
        name=name,
        parquet_bytes=parquet_bytes,
        schema_meta=schema_meta,
        entry_meta=entry_meta,
        org_dir_fn=_org_dir,
        write_json_fn=_write_json,
        read_json_fn=_read_json,
        set_source_meta_cache_fn=_set_source_meta_cache,
        build_join_blocks_fn=_build_join_blocks,
        source_schema_revision_fn=source_schema_revision,
        set_source_entry_cache_fn=_set_source_entry_cache,
        touch_schema_stamp_fn=_touch_schema_stamp,
        logger=logger,
    )


def delete_source(org_id: str, source_id: str) -> bool:
    """Remove a source and all its connections. Returns True if existed."""
    return _persistence.delete_source(
        org_id=org_id,
        source_id=source_id,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        write_json_fn=_write_json,
        get_connections_fn=get_connections,
        touch_schema_stamp_fn=_touch_schema_stamp,
        clear_source_meta_cache_fn=_clear_source_meta_cache,
        set_source_entry_cache_fn=_set_source_entry_cache,
        logger=logger,
    )


def upsert_connections(org_id: str, new_conns: list[dict[str, Any]]) -> None:
    """Merge new connections into connections.json, deduplicating by source pair + columns."""
    _persistence.upsert_connections(
        org_id=org_id,
        new_conns=new_conns,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        write_json_fn=_write_json,
        touch_schema_stamp_fn=_touch_schema_stamp,
    )


def get_connection_graph(org_id: str) -> dict[str, list[dict[str, Any]]]:
    """
    Return a graph keyed by source_id → list of connection dicts reachable from it.
    Used by the query engine to find join paths.
    """
    return _persistence.get_connection_graph(
        org_id=org_id,
        get_connections_fn=get_connections,
    )


def load_all_into_cache(
    org_id: str,
    cache: dict[str, Any],
    cache_lock: Any,
    cached_source_cls: type,
) -> int:
    """
    On server startup: load all registered sources for an org into the in-memory
    _SOURCE_CACHE so the first query after restart is fast.
    Returns number of sources loaded.
    """
    del cache_lock
    return _persistence.load_all_into_cache(
        org_id=org_id,
        cache=cache,
        cached_source_cls=cached_source_cls,
        org_dir_fn=_org_dir,
        read_json_fn=_read_json,
        set_source_meta_cache_fn=_set_source_meta_cache,
        dict_to_node_fn=_dict_to_node,
        logger=logger,
    )


def _dict_to_node(col: dict[str, Any]) -> Any:
    return _nodes.dict_to_node(col)
