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

import hashlib
import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_SOURCES_DIR = Path(os.environ.get("ALGENTA_SOURCES_DIR", Path.home() / ".algenta" / "sources"))

_JOIN_KEY_NAME_TOKENS = frozenset({
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
})
_DIMENSION_JOIN_TOKENS = frozenset({
    "branch",
    "location",
    "merchant",
    "outlet",
    "restaurant",
    "site",
    "store",
})
_DIMENSION_JOIN_MODIFIER_TOKENS = frozenset({
    "as",
    "eats",
    "external",
    "local",
    "manager",
    "name",
    "per",
    "uber",
    "ubereats",
})
_GENERIC_JOIN_TOKENS = frozenset({
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
    "text",
    "time",
    "timestamp",
    "to",
    "type",
    "value",
})
_NON_JOINABLE_ROLES = frozenset({
    "derived_measure",
    "unit_measure",
    "component",
    "ratio",
})

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


def _normalized_sample(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _build_join_blocks(schema_meta: dict) -> list[dict[str, Any]]:
    planner_profile = schema_meta.get("planner_profile") or {}
    columns_meta = {
        str(col.get("name", "")): col
        for col in (schema_meta.get("columns") or [])
        if col.get("name")
    }

    blocks: list[dict[str, Any]] = []
    for col_name, prof in planner_profile.items():
        col_meta = columns_meta.get(col_name, {})
        role = str(col_meta.get("role", ""))
        is_numeric = bool(prof.get("is_numeric", col_meta.get("is_numeric", False)))
        fill_rate = float(prof.get("fill_rate", col_meta.get("fill_rate", 0.0)) or 0.0)
        total_count = int(prof.get("total_count", 0) or 0)
        unique_count = int(prof.get("unique_count", col_meta.get("cardinality", 0)) or 0)
        if fill_rate < 0.05 or total_count <= 0 or unique_count <= 1:
            continue
        key_like = _looks_like_entity_join_key(col_name)
        dimension_like = _looks_like_low_cardinality_dimension(col_name)
        if role in _NON_JOINABLE_ROLES and not key_like:
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

        blocks.append({
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
        })

    blocks.sort(key=lambda block: (block["joinability"], block["unique_count"]), reverse=True)
    return blocks[:24]


def _score_join_block_pair(left: dict[str, Any], right: dict[str, Any]) -> float:
    score = 0.0
    left_dimension_family = _dimension_join_family(str(left.get("name") or ""))
    right_dimension_family = _dimension_join_family(str(right.get("name") or ""))
    same_dimension_family = (
        bool(left_dimension_family)
        and left_dimension_family == right_dimension_family
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
) -> float:
    pair_scores: list[float] = []
    for left in left_blocks:
        for right in right_blocks:
            score = _score_join_block_pair(left, right)
            if score >= 4.0:
                pair_scores.append(score)
    if not pair_scores:
        return 0.0
    pair_scores.sort(reverse=True)
    return round(sum(pair_scores[:3]), 6)


def _org_dir(org_id: str) -> Path:
    d = _SOURCES_DIR / org_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str))


def _path_fingerprint(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return (0, 0)
    return (int(stat.st_mtime_ns), int(stat.st_size))


def _schema_stamp_path(org_dir: Path) -> Path:
    return org_dir / ".schema_revision.stamp"


def _touch_schema_stamp(org_dir: Path) -> None:
    _schema_stamp_path(org_dir).write_text(str(time.time_ns()))


def _source_meta_cache_key(org_id: str, source_id: str) -> tuple[str, str]:
    return (org_id, source_id)


def _source_entry_cache_key(org_id: str, source_id: str) -> tuple[str, str]:
    return (org_id, source_id)


def _set_source_meta_cache(org_id: str, source_id: str, meta: dict[str, Any] | None) -> None:
    d = _org_dir(org_id)
    path = d / f"{source_id}.meta.json"
    _SOURCE_META_CACHE[_source_meta_cache_key(org_id, source_id)] = (
        (_path_fingerprint(path),),
        meta,
    )


def _set_source_entry_cache(org_id: str, source_id: str, entry: dict[str, Any] | None) -> None:
    d = _org_dir(org_id)
    index_path = d / "index.json"
    _SOURCE_ENTRY_CACHE[_source_entry_cache_key(org_id, source_id)] = (
        (_path_fingerprint(index_path),),
        entry,
    )


def _clear_source_meta_cache(org_id: str, source_id: str) -> None:
    _SOURCE_META_CACHE.pop(_source_meta_cache_key(org_id, source_id), None)


def _clear_source_entry_cache(org_id: str, source_id: str) -> None:
    _SOURCE_ENTRY_CACHE.pop(_source_entry_cache_key(org_id, source_id), None)


# ── Public API ──────────────────────────────────────────────────────────────────


def source_id_for(content_key: str | None, *, path_key: str | None = None) -> str:
    """
    Deterministic source ID.
    content_key  — sha256 hex of the raw content bytes (inline sources)
    path_key     — type:name string (file/url/connection sources, no content hash)
    """
    raw = content_key or path_key or str(uuid.uuid4())
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def list_sources(org_id: str) -> list[dict]:
    """Return all registered sources for an org (from index.json)."""
    d = _org_dir(org_id)
    idx = _read_json(d / "index.json") or {}
    return list(idx.values())


def get_source_entry(org_id: str, source_id: str) -> dict | None:
    """Return one registry index entry for a source, or None if it does not exist."""
    d = _org_dir(org_id)
    index_path = d / "index.json"
    fingerprint = (_path_fingerprint(index_path),)
    cache_key = _source_entry_cache_key(org_id, source_id)
    cached = _SOURCE_ENTRY_CACHE.get(cache_key)
    if cached and cached[0] == fingerprint:
        return cached[1]

    idx = _read_json(index_path) or {}
    entry = idx.get(source_id)
    normalized = entry if isinstance(entry, dict) else None
    _SOURCE_ENTRY_CACHE[cache_key] = (fingerprint, normalized)
    return normalized


def get_source_entry_by_name(org_id: str, source_name: str) -> dict | None:
    """Return one registry index entry by source name, or None if it does not exist."""
    d = _org_dir(org_id)
    index_path = d / "index.json"
    fingerprint = (_path_fingerprint(index_path),)
    cache_key = (org_id, source_name)
    cached = _SOURCE_ENTRY_BY_NAME_CACHE.get(cache_key)
    if cached and cached[0] == fingerprint:
        return cached[1]

    idx = _read_json(index_path) or {}
    match = next(
        (
            entry
            for entry in idx.values()
            if isinstance(entry, dict) and str(entry.get("name") or "") == source_name
        ),
        None,
    )
    _SOURCE_ENTRY_BY_NAME_CACHE[cache_key] = (fingerprint, match)
    return match


def update_source_entry(org_id: str, source_id: str, updates: dict[str, Any]) -> dict | None:
    """Patch a registry index entry in place and return the updated value."""
    d = _org_dir(org_id)
    idx = _read_json(d / "index.json") or {}
    entry = idx.get(source_id)
    if not isinstance(entry, dict):
        return None
    entry.update(updates)
    idx[source_id] = entry
    _write_json(d / "index.json", idx)
    _touch_schema_stamp(d)
    return entry


def candidate_join_sources(
    org_id: str,
    source_id: str,
    schema_meta: dict,
    *,
    limit: int = 24,
    exhaustive_threshold: int = 24,
    min_score: float = 4.5,
) -> list[dict]:
    """
    Return likely join candidates for a newly registered source.

    This is the enterprise-scale blocker stage: avoid O(N^2) deep pair scans by
    first matching compact per-source join signatures from registry metadata.
    """
    existing = [entry for entry in list_sources(org_id) if entry.get("id") != source_id]
    if len(existing) <= exhaustive_threshold:
        return existing

    left_blocks = _build_join_blocks(schema_meta)
    if not left_blocks:
        return []

    scored: list[tuple[float, dict]] = []
    for entry in existing:
        right_blocks = entry.get("join_blocks") or []
        if not right_blocks:
            continue
        score = _score_candidate_source(left_blocks, right_blocks)
        if score >= min_score:
            scored.append((score, entry))

    scored.sort(key=lambda item: (item[0], item[1].get("row_count", 0)), reverse=True)
    return [entry for _score, entry in scored[:limit]]


def get_source_meta(org_id: str, source_id: str) -> dict | None:
    """Return full schema metadata for a source."""
    d = _org_dir(org_id)
    path = d / f"{source_id}.meta.json"
    fingerprint = (_path_fingerprint(path),)
    cache_key = _source_meta_cache_key(org_id, source_id)
    cached = _SOURCE_META_CACHE.get(cache_key)
    if cached and cached[0] == fingerprint:
        return cached[1]

    meta = _read_json(path)
    normalized = meta if isinstance(meta, dict) else None
    _SOURCE_META_CACHE[cache_key] = (fingerprint, normalized)
    return normalized


def update_source_meta(org_id: str, source_id: str, updates: dict[str, Any]) -> dict | None:
    """Patch a source metadata document in place and return the updated value."""
    d = _org_dir(org_id)
    path = d / f"{source_id}.meta.json"
    meta = _read_json(path)
    if not isinstance(meta, dict):
        return None
    meta.update(updates)
    _write_json(path, meta)
    _touch_schema_stamp(d)
    _set_source_meta_cache(org_id, source_id, meta)
    source_revision = source_schema_revision(org_id, source_id)
    idx = _read_json(d / "index.json") or {}
    entry = idx.get(source_id)
    if isinstance(entry, dict):
        entry["source_schema_revision"] = source_revision
        idx[source_id] = entry
        _write_json(d / "index.json", idx)
        _set_source_entry_cache(org_id, source_id, entry)
    return meta


def get_source_parquet(org_id: str, source_id: str) -> bytes | None:
    """Return raw Parquet bytes for a source, or None if not registered."""
    p = _org_dir(org_id) / f"{source_id}.parquet"
    return p.read_bytes() if p.exists() else None


def get_source_parquet_path(org_id: str, source_id: str) -> Path | None:
    """Return the on-disk Parquet path for a source, or None if not registered."""
    p = _org_dir(org_id) / f"{source_id}.parquet"
    return p if p.exists() else None


def get_connections(org_id: str) -> list[dict]:
    """Return all detected join connections for an org."""
    d = _org_dir(org_id)
    return _read_json(d / "connections.json") or []


def schema_revision(org_id: str) -> str:
    """
    Stable fingerprint for an org's registered schema graph.

    This changes when sources are added/re-registered/removed or when the
    connection graph changes. Query-time planner caches can key off this so
    they rebuild only when the customer's schema actually changes.
    """
    d = _org_dir(org_id)
    idx = _read_json(d / "index.json") or {}
    stamp_path = _schema_stamp_path(d)
    fingerprint = (
        _path_fingerprint(d / "index.json"),
        _path_fingerprint(d / "connections.json"),
        _path_fingerprint(stamp_path),
    )
    cached = _SCHEMA_REVISION_CACHE.get(org_id)
    if cached and cached[0] == fingerprint:
        return cached[1]
    conns = _read_json(d / "connections.json") or []

    sources = []
    for source_id, entry in sorted(idx.items(), key=lambda item: item[0]):
        meta = _read_json(d / f"{source_id}.meta.json") or {}
        semantic_aliases = meta.get("semantic_aliases") or {}
        query_hints = meta.get("query_hints") or {}
        sources.append(
            {
                "id": entry.get("id", ""),
                "name": entry.get("name", ""),
                "registered_at": entry.get("registered_at", ""),
                "row_count": entry.get("row_count", 0),
                "columns": entry.get("columns", 0),
                "roles_summary": entry.get("roles_summary", {}),
                "decision_mode": entry.get("decision_mode", ""),
                "join_blocks": entry.get("join_blocks", []),
                "semantic_aliases": semantic_aliases,
                "query_hints": query_hints,
            }
        )
    connections = sorted(
        [
            {
                "source_a": conn.get("source_a", ""),
                "source_b": conn.get("source_b", ""),
                "col_a": conn.get("col_a", ""),
                "col_b": conn.get("col_b", ""),
                "confidence": round(float(conn.get("confidence", 0.0)), 6),
                "cardinality": conn.get("cardinality", ""),
            }
            for conn in conns
        ],
        key=lambda conn: (
            conn["source_a"],
            conn["col_a"],
            conn["source_b"],
            conn["col_b"],
            conn["cardinality"],
        ),
    )

    payload = {"sources": sources, "connections": connections}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    revision = hashlib.sha256(raw).hexdigest()[:24]
    _SCHEMA_REVISION_CACHE[org_id] = (fingerprint, revision)
    return revision


def source_schema_revision(org_id: str, source_id: str) -> str:
    """
    Stable fingerprint for a single source's executable contents.

    This is cheaper than the org-wide schema revision and is safe for
    single-source exact queries that do not depend on cross-source joins.
    """
    d = _org_dir(org_id)
    fingerprint = (
        _path_fingerprint(d / f"{source_id}.meta.json"),
        _path_fingerprint(d / f"{source_id}.parquet"),
    )
    cache_key = (org_id, source_id)
    cached = _SOURCE_SCHEMA_REVISION_CACHE.get(cache_key)
    if cached and cached[0] == fingerprint:
        return cached[1]
    raw = json.dumps(
        {
            "meta": fingerprint[0],
            "parquet": fingerprint[1],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    revision = hashlib.sha256(raw).hexdigest()[:24]
    _SOURCE_SCHEMA_REVISION_CACHE[cache_key] = (fingerprint, revision)
    return revision


def register_source(
    org_id: str,
    source_id: str,
    name: str,
    parquet_bytes: bytes,
    schema_meta: dict,
    graph_nodes: dict,   # col → ColumnNode (serialized to dict)
    profile: dict,
    **entry_meta: Any,
) -> dict:
    """
    Persist a source to disk.
    Returns the index entry dict.
    """
    d = _org_dir(org_id)

    # Write Parquet
    (d / f"{source_id}.parquet").write_bytes(parquet_bytes)

    # Write full schema metadata
    _write_json(d / f"{source_id}.meta.json", schema_meta)
    _set_source_meta_cache(org_id, source_id, schema_meta)

    # Update index
    idx = _read_json(d / "index.json") or {}
    join_blocks = _build_join_blocks(schema_meta)
    source_revision = source_schema_revision(org_id, source_id)
    entry = {
        "id":            source_id,
        "name":          name,
        "registered_at": datetime.now(UTC).isoformat(),
        "row_count":     schema_meta.get("row_count", 0),
        "roles_summary": schema_meta.get("roles_summary", {}),
        "columns":       len(schema_meta.get("columns", [])),
        "source_schema_revision": source_revision,
        "join_blocks":   join_blocks,
    }
    for key, value in entry_meta.items():
        if value is not None:
            entry[key] = value
    idx[source_id] = entry
    _write_json(d / "index.json", idx)
    _set_source_entry_cache(org_id, source_id, entry)
    _touch_schema_stamp(d)

    logger.info("source_registered", org=org_id, source_id=source_id, name=name)
    return entry


def delete_source(org_id: str, source_id: str) -> bool:
    """Remove a source and all its connections. Returns True if existed."""
    d = _org_dir(org_id)
    existed = False
    for suffix in (".parquet", ".meta.json"):
        p = d / f"{source_id}{suffix}"
        if p.exists():
            p.unlink()
            existed = True

    idx = _read_json(d / "index.json") or {}
    if source_id in idx:
        del idx[source_id]
        _write_json(d / "index.json", idx)
        existed = True

    # Remove all connections involving this source
    conns = [c for c in get_connections(org_id)
             if c.get("source_a") != source_id and c.get("source_b") != source_id]
    _write_json(d / "connections.json", conns)
    if existed:
        _touch_schema_stamp(d)
        _clear_source_meta_cache(org_id, source_id)
        _set_source_entry_cache(org_id, source_id, None)

    if existed:
        logger.info("source_deleted", org=org_id, source_id=source_id)
    return existed


def upsert_connections(org_id: str, new_conns: list[dict]) -> None:
    """Merge new connections into connections.json, deduplicating by source pair + columns."""
    d = _org_dir(org_id)
    existing = _read_json(d / "connections.json") or []

    # Key: frozenset of (source_a, col_a, source_b, col_b)
    def _key(c: dict) -> tuple:
        return (c["source_a"], c["col_a"], c["source_b"], c["col_b"])

    seen = {_key(c) for c in existing}
    merged = list(existing)
    for c in new_conns:
        k = _key(c)
        if k not in seen:
            merged.append(c)
            seen.add(k)

    if len(merged) != len(existing):
        _write_json(d / "connections.json", merged)
        _touch_schema_stamp(d)


def get_connection_graph(org_id: str) -> dict[str, list[dict]]:
    """
    Return a graph keyed by source_id → list of connection dicts reachable from it.
    Used by the query engine to find join paths.
    """
    conns = get_connections(org_id)
    graph: dict[str, list[dict]] = {}
    for c in conns:
        for src, other_src, col, other_col in [
            (c["source_a"], c["source_b"], c["col_a"], c["col_b"]),
            (c["source_b"], c["source_a"], c["col_b"], c["col_a"]),
        ]:
            graph.setdefault(src, []).append({
                "to_source": other_src,
                "local_col": col,
                "remote_col": other_col,
                "confidence": c.get("confidence", 0.0),
                "cardinality": c.get("cardinality", "?"),
            })
    return graph


def load_all_into_cache(
    org_id: str,
    cache: dict,
    cache_lock: Any,
    cached_source_cls: type,
) -> int:
    """
    On server startup: load all registered sources for an org into the in-memory
    _SOURCE_CACHE so the first query after restart is fast.
    Returns number of sources loaded.
    """
    import json as _json


    d = _org_dir(org_id)
    idx = _read_json(d / "index.json") or {}
    loaded = 0

    for source_id, _entry in idx.items():
        parquet_path = d / f"{source_id}.parquet"
        meta_path    = d / f"{source_id}.meta.json"
        if not parquet_path.exists():
            continue
        try:
            parquet_bytes = parquet_path.read_bytes()
            schema_meta   = _read_json(meta_path) or {}
            _set_source_meta_cache(org_id, source_id, schema_meta)

            # Rebuild graph_nodes from meta (lightweight ColumnNode-like dicts).
            # _dict_to_node applies demotion rules (e.g. false-positive derived_measure
            # columns that are actually identifiers).  Patch schema_meta columns to
            # reflect the corrected roles so parquet_schema_meta stays in sync.
            graph_nodes: dict = {}
            corrected_cols = []
            for col in schema_meta.get("columns", []):
                node = _dict_to_node(col)
                graph_nodes[col["name"]] = node
                if col.get("role") != node.role:
                    corrected_cols.append((col["name"], col.get("role"), node.role))

            # Note: Step 3b (top-mean unit_measure → derived_measure promotion) is NOT
            # applied here for preloaded sources.  That step requires CV (std/mean) to
            # correctly distinguish aggregated totals from rates, but std is not stored
            # in .meta.json.  Using mean alone risks promoting the wrong column (e.g.
            # EXT_COST > EXT_PRICE in datasets where cost values are larger).
            # Step 3b runs correctly in build_schema_graph() during live registration
            # where raw numeric samples are available.  Re-register to apply it.

            if corrected_cols:
                # Rebuild schema_meta columns with corrected roles
                corrected_map = {n: r for n, _, r in corrected_cols}
                schema_meta = {
                    **schema_meta,
                    "columns": [
                        {**c, "role": corrected_map[c["name"]]} if c["name"] in corrected_map else c
                        for c in schema_meta.get("columns", [])
                    ],
                }

            entry_obj = cached_source_cls(
                parquet_bytes     = parquet_bytes,
                parquet_schema_meta = _json.dumps(schema_meta).encode(),
                profile           = {},   # not needed after initial profile
                mojo_profile      = {},
                relations         = schema_meta.get("formulas", []),
                graph_nodes       = graph_nodes,
                schema_meta       = schema_meta,
                mojo_profiling_status = schema_meta.get("mojo_profiling_status") or {},
                content_keyed     = True,  # disk sources are permanent
            )
            cache[source_id] = entry_obj
            loaded += 1
        except Exception as exc:
            logger.warning("source_cache_load_failed", source_id=source_id, error=str(exc))

    return loaded


def _dict_to_node(col: dict) -> Any:
    """Reconstruct a ColumnNode-like object from schema metadata dict."""
    # Import here to avoid circular imports
    from apps.api_server.routers.query import ColumnNode, _col_name_signals_id
    role = col.get("role", "metric")
    # Demote false-positive derived_measure from stale on-disk .meta.json files.
    # Mirror the same three rules as build_schema_graph() Step 2b so live and
    # preloaded sources are always consistent.
    if role == "derived_measure":
        if not col.get("formula"):                      # Rule 1: no formula proof
            role = "metric"
        elif _col_name_signals_id(col.get("name", "")):  # Rule 2: ID-like name
            role = "identifier"

    # Promote remaining metric numeric decimal columns to unit_measure.
    # This mirrors build_schema_graph() Step 2's "elif has_decimals" branch.
    # The top-mean promotion (metric→derived_measure, Step 3b) is done in
    # load_all_into_cache() AFTER all nodes are built, where full source context
    # is available to pick the highest-mean column correctly.
    if role == "metric" and col.get("is_numeric"):
        mean_val = col.get("mean", 0.0)
        # Decimal mean check: fractional part present → continuous decimal column
        mean_has_decimal = (mean_val > 0 and abs(mean_val - int(mean_val)) > 0.01)
        if mean_has_decimal:
            # rate/price/cost — may be further promoted to derived_measure below
            role = "unit_measure"

    node = ColumnNode(
        name            = col.get("name", ""),
        role            = role,
        formula         = col.get("formula"),
        mean            = col.get("mean", 0.0),
        std             = 0.0,
        is_numeric      = col.get("is_numeric", False),
        magnitude_class = col.get("magnitude", "medium"),
        semantic_type   = col.get("semantic_type") or "",
        confidence      = 0.55 if role == "unit_measure" and not col.get("formula") else 0.6,
    )
    return node
