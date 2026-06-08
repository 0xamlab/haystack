from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

from algenta.runtime_errors import RuntimeValidationError

SQL_PROVIDER_TYPES = frozenset(
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
_SQL_DSN_SCHEMES = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mysql": "mysql",
    "mssql": "mssql",
    "redshift": "redshift",
}
_SQL_DEFAULT_PORTS = {
    "postgres": 5432,
    "postgresql": 5432,
    "mysql": 3306,
    "mssql": 1433,
    "redshift": 5439,
}


def normalize_sql_connection(source: Mapping[str, Any], raw_type: str) -> dict[str, Any]:
    normalized = dict(source)
    provider = raw_type if raw_type != "sql" else str(source.get("provider") or "").strip().lower()
    normalized["type"] = "sql"
    if provider and provider != "sql":
        normalized["provider"] = provider
    normalized["connection_string"] = _runtime_sql_connection_string(provider or "sql", normalized)
    for key in ("host", "port", "database", "user", "username", "password"):
        normalized.pop(key, None)
    normalized["query"] = _runtime_sql_query(normalized)
    return {key: value for key, value in normalized.items() if value is not None}


def _runtime_sql_connection_string(provider: str, source: Mapping[str, Any]) -> str:
    connection_string = source.get("connection_string")
    if isinstance(connection_string, str) and connection_string.strip():
        return connection_string.strip()
    if provider in _SQL_DSN_SCHEMES:
        host_value = source.get("host")
        database_value = source.get("database")
        if (
            isinstance(host_value, str)
            and host_value.strip()
            and isinstance(database_value, str)
            and database_value.strip()
        ):
            username_value = source.get("user") or source.get("username")
            password_value = source.get("password")
            if password_value is not None and not isinstance(password_value, str):
                raise RuntimeValidationError(
                    "invalid_sql_descriptor",
                    "Database connector password must be a string when provided.",
                    {"field": "password", "provider": provider},
                )
            if username_value is not None and not isinstance(username_value, str):
                raise RuntimeValidationError(
                    "invalid_sql_descriptor",
                    "Database connector user must be a string when provided.",
                    {"field": "user", "provider": provider},
                )
            if password_value is not None and not username_value:
                raise RuntimeValidationError(
                    "invalid_sql_descriptor",
                    (
                        "Database connector password requires user/username when "
                        "building a connection_string."
                    ),
                    {"field": "password", "provider": provider},
                )
            host = host_value.strip()
            database = database_value.strip()
            port_value = source.get("port")
            if port_value is None:
                port = _SQL_DEFAULT_PORTS[provider]
            else:
                try:
                    port = int(port_value)
                except (TypeError, ValueError) as exc:
                    raise RuntimeValidationError(
                        "invalid_sql_descriptor",
                        "Database connector port must be an integer when provided.",
                        {"field": "port", "provider": provider},
                    ) from exc
            credentials = ""
            if isinstance(username_value, str) and username_value.strip():
                credentials = quote(username_value.strip(), safe="")
                if isinstance(password_value, str):
                    credentials = f"{credentials}:{quote(password_value, safe='')}"
                credentials = f"{credentials}@"
            return (
                f"{_SQL_DSN_SCHEMES[provider]}://"
                f"{credentials}{host}:{port}/{quote(database, safe='')}"
            )
    if provider != "sqlite":
        raise RuntimeValidationError(
            "missing_connection_string",
            (
                "API mode database descriptors require connection_string or a "
                "structured host/database descriptor."
            ),
            {"provider": provider},
        )
    path_value = source.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise RuntimeValidationError(
            "missing_connection_string",
            "SQLite API descriptors require path or connection_string.",
            {"provider": provider},
        )
    return f"sqlite+pysqlite:///{Path(path_value.strip())}"


def _runtime_sql_query(source: Mapping[str, Any]) -> str:
    query_value = source.get("query")
    if isinstance(query_value, str) and query_value.strip():
        return query_value.strip()
    table = _sql_identifier(source.get("table"), field_name="table")
    schema_value = source.get("schema")
    if schema_value is None:
        return f"SELECT * FROM {table}"  # noqa: S608 - identifier is validated above
    schema = _sql_identifier(schema_value, field_name="schema")
    return f"SELECT * FROM {schema}.{table}"  # noqa: S608 - identifiers are validated above


def _sql_identifier(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeValidationError(
            "invalid_sql_descriptor",
            f"API mode SQL descriptors require a non-empty {field_name}.",
            {"field": field_name},
        )
    normalized = value.strip()
    if not re.fullmatch(r"^[A-Za-z_][A-Za-z0-9_$]*$", normalized):
        raise RuntimeValidationError(
            "invalid_sql_identifier",
            (
                "API mode SQL descriptors only auto-build queries for simple "
                "schema/table identifiers. Provide an explicit query for "
                "advanced SQL."
            ),
            {"field": field_name, "value": normalized},
        )
    return normalized


__all__ = ["SQL_PROVIDER_TYPES", "normalize_sql_connection"]
