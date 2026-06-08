from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

from algenta.runtime_connector_definitions import (
    _CANONICAL_FILE_TYPES,
    _LOCAL_RUNTIME_CONNECTOR_TYPES,
    _flatten_connector_envelope,
    _is_canonical_connector_envelope,
    _strip_none_dict,
)
from algenta.runtime_errors import RuntimeValidationError
from algenta.runtime_source_naming import runtime_api_source_name

if TYPE_CHECKING:
    from types import ModuleType

_DIRECT_API_SOURCE_KEYS = frozenset(
    {
        "dataset_id",
        "source_id",
        "records",
        "csv",
        "json_str",
        "url",
        "excel_b64",
        "parquet_b64",
        "connection",
    }
)
_OBJECT_STORAGE_TYPES = frozenset({"s3", "gcs", "azure_blob"})
_SQL_PROVIDER_TYPES = frozenset(
    {
        "sql",
        "postgres",
        "postgresql",
        "mysql",
        "mssql",
        "sqlite",
        "snowflake",
        "bigquery",
    }
)


@cache
def _runtime_connection_sql_module() -> ModuleType:
    return import_module("algenta.runtime_connection_sql")


def normalize_local_runtime_source(source: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _normalized_connector_mapping(source)
    raw_type = _runtime_connector_type(normalized)
    if raw_type in _CANONICAL_FILE_TYPES:
        return _normalize_local_file_source(normalized, raw_type)
    if raw_type and raw_type not in _LOCAL_RUNTIME_CONNECTOR_TYPES:
        raise RuntimeValidationError(
            "unsupported_local_connector",
            (
                "Local Runtime.connect() supports local files and SQLite descriptors. "
                "Use Runtime(mode='api', api_key='...') for remote connectors."
            ),
            {"type": raw_type},
        )
    return normalized


def normalize_api_source_payload(
    source: Mapping[str, Any],
    *,
    explicit_name: str | None,
) -> dict[str, Any]:
    raw_source = _normalized_connector_mapping(source)
    payload = dict(raw_source)
    has_direct_source_keys = any(key in payload for key in _DIRECT_API_SOURCE_KEYS)
    payload["name"] = runtime_api_source_name(payload, explicit_name=explicit_name)
    if "connection" in payload and isinstance(payload["connection"], Mapping):
        payload["connection"] = normalize_runtime_connection(payload["connection"])
        return payload
    if has_direct_source_keys:
        return payload
    connection_payload = normalize_runtime_connection(raw_source)
    return {"name": payload["name"], "connection": connection_payload}


def normalize_runtime_connection(source: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _normalized_connector_mapping(source)
    raw_type = _runtime_connector_type(normalized)
    if raw_type in _CANONICAL_FILE_TYPES:
        return _normalize_file_connection(normalized)
    if raw_type in {"rest", "api"}:
        return _normalize_rest_connection(normalized)
    if raw_type in _OBJECT_STORAGE_TYPES:
        return _normalize_object_storage_connection(normalized, raw_type)
    if raw_type in _SQL_PROVIDER_TYPES:
        return _runtime_connection_sql_module().normalize_sql_connection(normalized, raw_type)
    if not raw_type:
        raise RuntimeValidationError(
            "missing_connection_type",
            (
                "API mode source descriptors require an explicit connector type "
                "or a direct source payload."
            ),
        )
    return _strip_none_dict(normalized)


def _normalized_connector_mapping(source: Mapping[str, Any]) -> dict[str, Any]:
    if _is_canonical_connector_envelope(source):
        return _flatten_connector_envelope(source)
    return _strip_none_dict(source)


def _runtime_connector_type(source: Mapping[str, Any]) -> str:
    return (
        str(source.get("type") or source.get("provider") or source.get("connection_type") or "")
        .strip()
        .lower()
    )


def _normalize_local_file_source(
    source: Mapping[str, Any],
    raw_type: str,
) -> dict[str, Any]:
    file_path = source.get("file_path") or source.get("path")
    if isinstance(file_path, str) and file_path.strip():
        return {"path": file_path.strip()}
    if source.get("records") is not None:
        return {"records": source["records"]}
    if raw_type in {"csv", "tsv"} and isinstance(source.get("csv"), str):
        return {"csv": source["csv"]}
    if raw_type == "json" and isinstance(source.get("json_str"), str):
        return {"json_str": source["json_str"]}
    raise RuntimeValidationError(
        "unsupported_local_connector",
        (
            "Local Runtime.connect() supports canonical file connectors only "
            "when they point to a local path or inline data."
        ),
        {"type": raw_type},
    )


def _normalize_file_connection(source: Mapping[str, Any]) -> dict[str, Any]:
    file_type = _file_connector_type(source)
    connection = {
        "type": "file",
        "file_type": file_type,
        "file_path": source.get("file_path") or source.get("path"),
        "delimiter": source.get("delimiter"),
        "json_path": source.get("json_path"),
        "sheet": source.get("sheet"),
    }
    if connection["file_path"]:
        return _strip_none_dict(connection)
    if file_type in {"csv", "tsv"} and source.get("csv") is not None:
        connection["content"] = source.get("csv")
        return _strip_none_dict(connection)
    if file_type == "json" and source.get("json_str") is not None:
        connection["content"] = source.get("json_str")
        return _strip_none_dict(connection)
    if file_type == "excel" and source.get("excel_b64") is not None:
        connection["content"] = source.get("excel_b64")
        return _strip_none_dict(connection)
    if file_type == "parquet" and source.get("parquet_b64") is not None:
        connection["content"] = source.get("parquet_b64")
        return _strip_none_dict(connection)
    raise RuntimeValidationError(
        "invalid_file_connector",
        ("File connectors require a local path or inline content matching their declared type."),
        {"type": file_type},
    )


def _normalize_rest_connection(source: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(source)
    normalized["type"] = "rest_api"
    normalized["url"] = _runtime_rest_url(normalized)
    normalized.pop("base_url", None)
    return _strip_none_dict(normalized)


def _normalize_object_storage_connection(
    source: Mapping[str, Any],
    raw_type: str,
) -> dict[str, Any]:
    normalized = dict(source)
    normalized["type"] = raw_type
    if "format" in normalized and "file_type" not in normalized:
        normalized["file_type"] = normalized.pop("format")
    return _strip_none_dict(normalized)


def _file_connector_type(source: Mapping[str, Any]) -> str:
    raw_type = str(source.get("type") or source.get("provider") or "").strip().lower()
    if raw_type in {"xlsx", "xls"}:
        return "excel"
    return raw_type


def _runtime_rest_url(source: Mapping[str, Any]) -> str:
    url_value = source.get("url")
    if isinstance(url_value, str) and url_value.strip():
        return url_value.strip()
    base_url = source.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise RuntimeValidationError(
            "missing_rest_url",
            "API mode REST descriptors require url or base_url.",
        )
    path = source.get("path")
    if not isinstance(path, str) or not path.strip():
        return base_url.rstrip("/")
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


__all__ = [
    "normalize_api_source_payload",
    "normalize_local_runtime_source",
    "normalize_runtime_connection",
]
