from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from algenta.map_parsing import _source_name
from algenta.runtime_connector_definitions import (
    _flatten_connector_envelope,
    _is_canonical_connector_envelope,
)

_UUID_FILE_PREFIX_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[_-]+",
    re.IGNORECASE,
)
_SQLITE_CONNECTION_STRING_RE = re.compile(
    r"^sqlite(?:\+pysqlite)?:///(.+)$",
    re.IGNORECASE,
)


def runtime_source_name(source: Any, idx: int) -> str:
    if isinstance(source, Mapping) and _is_canonical_connector_envelope(source):
        source = _flatten_connector_envelope(source)
    name = _source_name(source, idx)
    if isinstance(source, str | Path):
        trimmed = _UUID_FILE_PREFIX_RE.sub("", name)
        return trimmed or name
    return name


def unique_runtime_source_name(
    source: Any,
    idx: int,
    existing_names: set[str],
    explicit_name: str | None = None,
) -> str:
    if explicit_name:
        return explicit_name

    primary = runtime_source_name(source, idx)
    if primary not in existing_names:
        return primary

    original = _source_name(source, idx)
    if original not in existing_names:
        return original

    counter = 2
    candidate = f"{primary}_{counter}"
    while candidate in existing_names:
        counter += 1
        candidate = f"{primary}_{counter}"
    return candidate


def runtime_api_source_name(
    source: Mapping[str, Any],
    *,
    explicit_name: str | None,
) -> str:
    if explicit_name:
        return explicit_name
    name_value = source.get("name")
    if isinstance(name_value, str) and name_value.strip():
        return name_value.strip()
    return runtime_source_name(dict(source), 0)


def source_ref_label(source: Any, idx: int) -> str:
    if isinstance(source, Mapping) and _is_canonical_connector_envelope(source):
        source = _flatten_connector_envelope(source)
    if isinstance(source, str | Path):
        return Path(source).name
    if isinstance(source, Mapping):
        path_value = source.get("path")
        if isinstance(path_value, str | Path) and str(path_value).strip():
            base_name = Path(path_value).name
            return _label_with_sql_suffix(base_name, source)
        connection_string = source.get("connection_string")
        if isinstance(connection_string, str) and connection_string.strip():
            sqlite_path = _sqlite_path_from_connection_string(connection_string)
            if sqlite_path is not None:
                return _label_with_sql_suffix(Path(sqlite_path).name, source)
            return _label_with_sql_suffix(connection_string, source)
        provider = str(source.get("provider") or source.get("type") or "").strip()
        if provider:
            return provider
    return f"source_{idx + 1}"


def _label_with_sql_suffix(label: str, source: Mapping[str, Any]) -> str:
    table_name = source.get("table")
    if isinstance(table_name, str) and table_name.strip():
        return f"{label}#{table_name.strip()}"
    if isinstance(source.get("query"), str):
        return f"{label}#query"
    return label


def _sqlite_path_from_connection_string(connection_string: str) -> str | None:
    match = _SQLITE_CONNECTION_STRING_RE.match(connection_string.strip())
    if match is None:
        return None
    return match.group(1)


__all__ = [
    "runtime_api_source_name",
    "runtime_source_name",
    "source_ref_label",
    "unique_runtime_source_name",
]
