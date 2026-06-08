from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


def org_dir(sources_dir: Path, org_id: str) -> Path:
    directory = sources_dir / org_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str))


def path_fingerprint(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return (0, 0)
    return (int(stat.st_mtime_ns), int(stat.st_size))


def schema_stamp_path(org_dir: Path) -> Path:
    return org_dir / ".schema_revision.stamp"


def touch_schema_stamp(org_dir: Path) -> None:
    schema_stamp_path(org_dir).write_text(str(time.time_ns()))


def schema_stamp_value(org_dir: Path) -> str:
    stamp_path = schema_stamp_path(org_dir)
    try:
        return stamp_path.read_text().strip()
    except OSError:
        return ""


def source_meta_cache_key(org_id: str, source_id: str) -> tuple[str, str]:
    return (org_id, source_id)


def source_entry_cache_key(org_id: str, source_id: str) -> tuple[str, str]:
    return (org_id, source_id)


def set_source_meta_cache(
    *,
    org_id: str,
    source_id: str,
    meta: dict[str, Any] | None,
    org_dir: Path,
    cache: dict[tuple[str, str], tuple[tuple[tuple[int, int]], dict[str, Any] | None]],
    path_fingerprint_fn: Callable[[Path], tuple[int, int]],
    cache_key_fn: Callable[[str, str], tuple[str, str]],
) -> None:
    path = org_dir / f"{source_id}.meta.json"
    cache[cache_key_fn(org_id, source_id)] = ((path_fingerprint_fn(path),), meta)


def set_source_entry_cache(
    *,
    org_id: str,
    source_id: str,
    entry: dict[str, Any] | None,
    org_dir: Path,
    cache: dict[tuple[str, str], tuple[tuple[tuple[int, int]], dict[str, Any] | None]],
    path_fingerprint_fn: Callable[[Path], tuple[int, int]],
    cache_key_fn: Callable[[str, str], tuple[str, str]],
) -> None:
    index_path = org_dir / "index.json"
    cache[cache_key_fn(org_id, source_id)] = ((path_fingerprint_fn(index_path),), entry)


def clear_source_meta_cache(
    *,
    org_id: str,
    source_id: str,
    cache: dict[tuple[str, str], tuple[tuple[tuple[int, int]], dict[str, Any] | None]],
    cache_key_fn: Callable[[str, str], tuple[str, str]],
) -> None:
    cache.pop(cache_key_fn(org_id, source_id), None)


def clear_source_entry_cache(
    *,
    org_id: str,
    source_id: str,
    cache: dict[tuple[str, str], tuple[tuple[tuple[int, int]], dict[str, Any] | None]],
    cache_key_fn: Callable[[str, str], tuple[str, str]],
) -> None:
    cache.pop(cache_key_fn(org_id, source_id), None)
