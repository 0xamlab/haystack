"""Canonical connector envelope normalization for runtime and MCP surfaces."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException

from apps.api_server.services.connectors import normalize_type

_CANONICAL_FILE_TYPES = {"csv", "tsv", "json", "excel", "xlsx", "xls", "parquet"}
_CANONICAL_DATABASE_TYPES = {
    "postgres",
    "postgresql",
    "mysql",
    "mssql",
    "oracle",
    "redshift",
    "clickhouse",
    "snowflake",
    "bigquery",
    "sqlite",
    "elasticsearch",
    "neo4j",
    "redis",
}
_CANONICAL_OBJECT_STORAGE_TYPES = {"s3", "gcs", "azure", "azure_blob"}
_CANONICAL_API_TYPES = {"rest", "rest_api", "api"}
_INLINE_PAYLOAD_FIELDS = {
    "records",
    "csv",
    "json_str",
    "url",
    "excel_b64",
    "parquet_b64",
}
_SECTION_KEYS = {"location", "auth", "options"}


def _http_error(code: str, message: str, *, details: dict[str, Any] | None = None) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


def _strip_none(data: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _merge_section(
    target: dict[str, Any],
    section: Any,
    *,
    section_name: str,
) -> None:
    if section is None:
        return
    if not isinstance(section, Mapping):
        raise _http_error(
            "invalid_connector",
            f"connector.{section_name} must be an object.",
            details={"section": section_name},
        )
    for key, value in section.items():
        if key in target and target[key] != value:
            raise _http_error(
                "connector_conflict",
                (f"Canonical connector fields must not define conflicting values for '{key}'."),
                details={"field": key, "section": section_name},
            )
        target[key] = value


def _normalize_rest_auth(flattened: dict[str, Any]) -> None:
    mode = str(flattened.pop("auth_mode", "") or "").strip().lower()
    if not mode or mode == "none":
        return

    headers = dict(flattened.get("headers") or {})
    if not isinstance(headers, dict):
        raise _http_error(
            "invalid_connector",
            "REST connector headers must be an object.",
            details={"field": "headers"},
        )

    if mode in {"token", "bearer", "oauth"}:
        token = flattened.pop("token", None) or flattened.pop("access_token", None)
        if token is None:
            token = flattened.get("api_key")
        if not isinstance(token, str) or not token.strip():
            raise _http_error(
                "invalid_connector_auth",
                "Bearer-style auth requires token, access_token, or api_key credentials.",
                details={"mode": mode},
            )
        headers.setdefault("Authorization", f"Bearer {token.strip()}")
    elif mode == "basic":
        username = flattened.pop("username", None) or flattened.get("user")
        password = flattened.pop("password", None)
        if not isinstance(username, str) or not isinstance(password, str):
            raise _http_error(
                "invalid_connector_auth",
                "Basic auth requires username/user and password credentials.",
                details={"mode": mode},
            )
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        headers.setdefault("Authorization", f"Basic {token}")
    elif mode == "api_key":
        api_key = flattened.get("api_key") or flattened.pop("token", None)
        header_name = flattened.pop("api_key_header", None) or flattened.pop("header", None)
        if not isinstance(api_key, str) or not api_key.strip():
            raise _http_error(
                "invalid_connector_auth",
                "API key auth requires api_key or token credentials.",
                details={"mode": mode},
            )
        if not isinstance(header_name, str) or not header_name.strip():
            header_name = "X-API-Key"
        headers.setdefault(header_name, api_key.strip())
    else:
        raise _http_error(
            "invalid_connector_auth",
            f"Unsupported connector auth mode '{mode}'.",
            details={"mode": mode},
        )

    flattened["headers"] = headers


def flatten_canonical_connector(connector: Mapping[str, Any]) -> dict[str, Any]:
    raw_type = connector.get("type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise _http_error(
            "invalid_connector",
            "Canonical connectors require a non-empty type.",
            details={"field": "type"},
        )

    flattened = {
        key: value
        for key, value in connector.items()
        if key not in _SECTION_KEYS and value is not None
    }
    flattened["type"] = normalize_type(raw_type.strip().lower().replace("-", "_"))

    _merge_section(flattened, connector.get("location"), section_name="location")
    auth = connector.get("auth")
    if auth is not None:
        if not isinstance(auth, Mapping):
            raise _http_error(
                "invalid_connector",
                "connector.auth must be an object.",
                details={"field": "auth"},
            )
        auth_mode = auth.get("mode")
        if auth_mode is not None:
            flattened["auth_mode"] = str(auth_mode).strip().lower()
        _merge_section(
            flattened,
            auth.get("credentials"),
            section_name="auth.credentials",
        )
        _merge_section(flattened, auth.get("headers"), section_name="auth.headers")
    _merge_section(flattened, connector.get("options"), section_name="options")

    if flattened["type"] in _CANONICAL_API_TYPES:
        _normalize_rest_auth(flattened)

    return _strip_none(flattened)


def normalize_connect_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    connector = normalized.pop("connector", None)
    if connector is None:
        return normalized
    if not isinstance(connector, Mapping):
        raise _http_error(
            "invalid_connector",
            "connector must be an object.",
            details={"field": "connector"},
        )

    flat = flatten_canonical_connector(connector)
    connector_type = str(flat.get("type", "")).strip().lower()
    connection_config = dict(normalized.get("connection_config") or {})
    if connection_config and not isinstance(connection_config, dict):
        raise _http_error(
            "invalid_connection_config",
            "connection_config must be an object.",
        )
    selection = dict(normalized.get("selection") or {})
    if selection and not isinstance(selection, dict):
        raise _http_error(
            "invalid_selection",
            "selection must be an object.",
        )

    if connector_type in _CANONICAL_FILE_TYPES:
        file_type = "excel" if connector_type in {"excel", "xlsx", "xls"} else connector_type
        normalized.setdefault("connection_type", "file_upload")
        normalized.setdefault("provider", "file")

        file_path = flat.get("file_path") or flat.get("path")
        if isinstance(file_path, str) and file_path.strip():
            connection_config.setdefault("file_type", file_type)
            connection_config.setdefault("file_path", file_path.strip())
            for key in ("delimiter", "json_path", "sheet"):
                if flat.get(key) is not None:
                    connection_config.setdefault(key, flat[key])
            normalized["connection_config"] = connection_config
            return normalized

        for field_name in _INLINE_PAYLOAD_FIELDS:
            if flat.get(field_name) is not None:
                normalized[field_name] = flat[field_name]
        if file_type == "csv" and flat.get("content") is not None and "csv" not in normalized:
            normalized["csv"] = flat["content"]
        if file_type == "json" and flat.get("content") is not None and "json_str" not in normalized:
            normalized["json_str"] = flat["content"]
        if (
            file_type == "excel"
            and flat.get("content") is not None
            and "excel_b64" not in normalized
        ):
            normalized["excel_b64"] = flat["content"]
        if (
            file_type == "parquet"
            and flat.get("content") is not None
            and "parquet_b64" not in normalized
        ):
            normalized["parquet_b64"] = flat["content"]
        if not any(normalized.get(field_name) is not None for field_name in _INLINE_PAYLOAD_FIELDS):
            raise _http_error(
                "invalid_connector",
                (
                    "File connectors require location.path/file_path or one of "
                    "records, csv, json_str, url, excel_b64, or parquet_b64."
                ),
                details={"type": connector_type},
            )
        return normalized

    if connector_type in _CANONICAL_DATABASE_TYPES:
        normalized["connection_type"] = "database"
        normalized["provider"] = "postgres" if connector_type == "postgresql" else connector_type
        for key, value in flat.items():
            if key in {"type", "table", "schema", "query"}:
                continue
            connection_config.setdefault(key, value)
        table_name = flat.get("table")
        schema_name = flat.get("schema")
        sql_query = flat.get("query")
        if isinstance(sql_query, str) and sql_query.strip():
            selection.setdefault("sql_query", sql_query.strip())
        elif isinstance(table_name, str) and table_name.strip():
            if isinstance(schema_name, str) and schema_name.strip():
                selection.setdefault("table", f"{schema_name.strip()}.{table_name.strip()}")
            else:
                selection.setdefault("table", table_name.strip())
        normalized["connection_config"] = connection_config
        if selection:
            normalized["selection"] = selection
        return normalized

    if connector_type in _CANONICAL_OBJECT_STORAGE_TYPES:
        normalized["connection_type"] = "object_storage"
        normalized["provider"] = "azure_blob" if connector_type == "azure" else connector_type
        for key, value in flat.items():
            if key in {"type", "key", "blob", "object_path"}:
                continue
            if key == "format":
                connection_config.setdefault("file_type", value)
                continue
            connection_config.setdefault(key, value)
        object_path = flat.get("object_path") or flat.get("key") or flat.get("blob")
        if isinstance(object_path, str) and object_path.strip():
            selection.setdefault("object_path", object_path.strip())
        normalized["connection_config"] = connection_config
        if selection:
            normalized["selection"] = selection
        return normalized

    if connector_type in _CANONICAL_API_TYPES:
        normalized["connection_type"] = "api"
        normalized["provider"] = "rest"
        for key, value in flat.items():
            if key in {"type", "url", "data_path"}:
                continue
            connection_config.setdefault(key, value)
        url = flat.get("url")
        if isinstance(url, str) and url.strip():
            connection_config.setdefault("url", url.strip())
        data_path = flat.get("data_path")
        if isinstance(data_path, str) and data_path.strip():
            connection_config.setdefault("data_path", data_path.strip())
        normalized["connection_config"] = connection_config
        return normalized

    raise _http_error(
        "invalid_connector",
        f"Unsupported canonical connector type '{connector_type}'.",
        details={"type": connector_type},
    )
