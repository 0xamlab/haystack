from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apps.api_server.services.data_coercion import parse_delimited_records
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

_LOCAL_SOURCE_PRIORITY = {".parquet": 0, ".csv": 1}
_REGISTRY_SOURCE_ARTIFACT_CACHE_MAX = 512


@dataclass
class _CachedRegistrySourceArtifacts:
    nodes: dict[str, Any]
    profile: dict[str, dict[str, Any]]
    query_hints: list[dict[str, Any]]
    last_hit: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_hit = time.monotonic()


_REGISTRY_SOURCE_ARTIFACT_CACHE: dict[tuple[str, str, str], _CachedRegistrySourceArtifacts] = {}


def _registry_source_artifact_cache_get(
    key: tuple[str, str, str],
) -> _CachedRegistrySourceArtifacts | None:
    cached = _REGISTRY_SOURCE_ARTIFACT_CACHE.get(key)
    if cached is None:
        return None
    cached.touch()
    return cached


def _registry_source_artifact_cache_put(
    key: tuple[str, str, str],
    value: _CachedRegistrySourceArtifacts,
) -> _CachedRegistrySourceArtifacts:
    if len(_REGISTRY_SOURCE_ARTIFACT_CACHE) >= _REGISTRY_SOURCE_ARTIFACT_CACHE_MAX:
        oldest_key = min(
            _REGISTRY_SOURCE_ARTIFACT_CACHE.items(),
            key=lambda item: item[1].last_hit,
        )[0]
        _REGISTRY_SOURCE_ARTIFACT_CACHE.pop(oldest_key, None)
    _REGISTRY_SOURCE_ARTIFACT_CACHE[key] = value
    return value


def _load_csv(path: Path, max_rows: int = 3000) -> list[dict[str, Any]]:
    rng = random.Random(0)  # noqa: S311 - deterministic sampling, not security-sensitive
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8-sig", errors="replace") as file_obj:
        for index, row in enumerate(
            parse_delimited_records(file_obj.read(), delimiter=",", sniff=True)
        ):
            if max_rows <= 0 or len(rows) < max_rows:
                rows.append(row)
                continue
            chosen_index = rng.randint(0, index)
            if chosen_index < max_rows:
                rows[chosen_index] = row
    return rows


def _load_parquet(path: Path, max_rows: int = 3000) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("Local Parquet planning requires pyarrow to be installed.") from exc

    initialize_pyarrow_parquet_runtime()
    rng = random.Random(0)  # noqa: S311 - deterministic sampling, not security-sensitive
    rows: list[dict[str, Any]] = []
    seen = 0
    parquet_file = pq.ParquetFile(str(path))
    for batch in parquet_file.iter_batches():
        for row in batch.to_pylist():
            if max_rows <= 0 or len(rows) < max_rows:
                rows.append(row)
            else:
                chosen_index = rng.randint(0, seen)
                if chosen_index < max_rows:
                    rows[chosen_index] = row
            seen += 1
    return rows


def _load_records(path: Path, max_rows: int = 3000) -> list[dict[str, Any]]:
    ext = path.suffix.lower()
    if ext == ".csv":
        return _load_csv(path, max_rows=max_rows)
    if ext == ".parquet":
        return _load_parquet(path, max_rows=max_rows)
    raise ValueError(f"Unsupported local source extension: {ext}")


def _discover_local_source_map(data_dir: Path) -> dict[str, str]:
    if not data_dir.exists():
        return {}

    chosen: dict[str, Path] = {}
    for path in sorted(candidate for candidate in data_dir.iterdir() if candidate.is_file()):
        ext = path.suffix.lower()
        if ext not in _LOCAL_SOURCE_PRIORITY:
            continue
        existing = chosen.get(path.stem)
        if existing is None:
            chosen[path.stem] = path
            continue
        if _LOCAL_SOURCE_PRIORITY[ext] < _LOCAL_SOURCE_PRIORITY[existing.suffix.lower()]:
            chosen[path.stem] = path
    return {name: path.name for name, path in sorted(chosen.items())}


def _profile_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not records:
        return {}
    profile: dict[str, dict[str, Any]] = {}
    total_rows = len(records)
    for field_name in records[0].keys():
        nums: list[float] = []
        strs: list[str] = []
        sample_numeric: list[float] = []
        sample_strings: list[str] = []
        unique_values: set[str] = set()
        non_empty = 0
        for record in records:
            value = record.get(field_name)
            if value is None:
                continue
            str_value = str(value).strip()
            if not str_value or str_value in {"?", "none", "null", "nan"}:
                continue
            non_empty += 1
            unique_values.add(str_value)
            if isinstance(value, int | float) and not isinstance(value, bool):
                float_value = float(value)
                nums.append(float_value)
                if len(sample_numeric) < 50:
                    sample_numeric.append(float_value)
            else:
                strs.append(str_value)
                if len(sample_strings) < 50:
                    sample_strings.append(str_value)
        mean = sum(nums) / len(nums) if nums else 0.0
        std = (
            math.sqrt(sum((item - mean) ** 2 for item in nums) / max(len(nums) - 1, 1))
            if nums
            else 0.0
        )
        profile[field_name] = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": len(nums) > len(strs),
            "sample_values": [str(value) for value in sample_numeric[:30]] + sample_strings[:30],
            "unique_count": len(unique_values),
            "total_count": len(nums) + len(strs),
            "fill_rate": round(non_empty / max(total_rows, 1), 4),
            "mean": mean,
            "std": std,
        }
    return profile


def _profiles_from_registry_meta(meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    row_count = int(meta.get("row_count", 0) or 0)
    planner_profile = meta.get("planner_profile") or {}
    if planner_profile:
        out: dict[str, dict[str, Any]] = {}
        for col, raw in planner_profile.items():
            is_numeric = bool(raw.get("is_numeric", False))
            samples = [str(value) for value in (raw.get("sample_values") or [])[:50]]
            strings = [str(value) for value in (raw.get("strings") or [])[:50]]
            if not strings and not is_numeric:
                strings = list(samples)
            total_count = int(raw.get("total_count", 0) or 0)
            fill_rate = float(raw.get("fill_rate", 1.0) or 1.0)
            if total_count <= 0 and row_count > 0:
                total_count = max(int(round(row_count * fill_rate)), 1 if fill_rate > 0 else 0)
            out[col] = {
                "is_numeric": is_numeric,
                "strings": strings,
                "sample_values": samples,
                "unique_count": int(raw.get("unique_count", 0) or 0),
                "total_count": total_count,
                "fill_rate": fill_rate,
                "mean": float(raw.get("mean", 0.0) or 0.0),
                "std": float(raw.get("std", 0.0) or 0.0),
            }
        return out

    fallback_out: dict[str, dict[str, Any]] = {}
    for col_meta in meta.get("columns", []):
        col_name = str(col_meta.get("name", "") or "")
        if not col_name:
            continue
        is_numeric = bool(col_meta.get("is_numeric", False))
        samples = [str(value) for value in (col_meta.get("samples") or [])[:50]]
        fill_rate = float(col_meta.get("fill_rate", 1.0) or 1.0)
        total_count = max(
            int(round(row_count * fill_rate)),
            1 if row_count and fill_rate > 0 else 0,
        )
        unique_count = int(col_meta.get("cardinality", 0) or 0)
        if unique_count <= 0 and samples:
            unique_count = len(set(samples))
        fallback_out[col_name] = {
            "is_numeric": is_numeric,
            "strings": [] if is_numeric else list(samples),
            "sample_values": samples,
            "unique_count": unique_count,
            "total_count": total_count,
            "fill_rate": fill_rate,
            "mean": float(col_meta.get("mean", 0.0) or 0.0),
            "std": 0.0,
        }
    return fallback_out


def _registry_source_artifacts_from_meta(
    *,
    org_id: str,
    source_id: str,
    schema_revision: str,
    meta: dict[str, Any],
    profiles_from_registry_meta_fn: Any | None = None,
) -> _CachedRegistrySourceArtifacts:
    cached = _registry_source_artifact_cache_get((org_id, source_id, schema_revision))
    if cached is not None:
        return cached

    from apps.api_server.routers.query import _graph_nodes_from_cached_meta

    query_hints = meta.get("query_hints", [])
    normalized_query_hints = query_hints if isinstance(query_hints, list) else []
    return _registry_source_artifact_cache_put(
        (org_id, source_id, schema_revision),
        _CachedRegistrySourceArtifacts(
            nodes=_graph_nodes_from_cached_meta(
                org_id=org_id,
                dataset_id=source_id,
                schema_revision=schema_revision,
                schema_meta=meta,
            ),
            profile=(profiles_from_registry_meta_fn or _profiles_from_registry_meta)(meta),
            query_hints=normalized_query_hints,
        ),
    )
