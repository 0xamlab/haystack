"""Connector destination resolution and privacy-policy enforcement."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from apps.api_server.services.egress_guard import (
    EgressAuditContext,
    enforce_egress_sync,
    google_endpoint_url,
)

_SQL_DEFAULT_PORTS: dict[str, int] = {
    "clickhouse": 8123,
    "clickhouses": 8443,
    "http": 8123,
    "https": 8443,
    "mssql": 1433,
    "mysql": 3306,
    "oracle": 1521,
    "postgres": 5432,
    "postgresql": 5432,
    "redshift": 5432,
    "snowflake": 443,
}
_NEO4J_DEFAULT_PORTS: dict[str, int] = {
    "bolt": 7687,
    "bolt+s": 7687,
    "bolt+ssc": 7687,
    "neo4j": 7687,
    "neo4j+s": 7687,
    "neo4j+ssc": 7687,
}
_REDIS_DEFAULT_PORTS: dict[str, int] = {
    "redis": 6379,
    "rediss": 6380,
}


def _format_destination(host: str, port: int | None) -> str:
    normalized_host = host.strip()
    if not normalized_host:
        raise ValueError("Connector destination requires a non-empty host.")
    if ":" in normalized_host and not normalized_host.startswith("["):
        normalized_host = f"[{normalized_host}]"
    return f"{normalized_host}:{port}" if port else normalized_host


def _primary_scheme(raw_scheme: str) -> str:
    return raw_scheme.strip().lower().split("+", 1)[0]


def _parsed_host_destination(
    parsed: Any,
    *,
    default_port: int | None,
    error_message: str,
) -> str:
    host = parsed.hostname
    if not host:
        raise ValueError(error_message)
    return _format_destination(host, parsed.port or default_port)


def sql_connection_destination(connection_string: str) -> str | None:
    parsed = urlparse(connection_string)
    scheme = _primary_scheme(parsed.scheme)
    if scheme in {"", "sqlite"}:
        return None
    if scheme == "bigquery":
        return google_endpoint_url("bigquery.googleapis.com")
    if scheme == "snowflake":
        account = parsed.hostname
        if not account:
            raise ValueError("Snowflake connection string requires account host.")
        normalized_account = (
            account if "." in account else f"{account}.snowflakecomputing.com"
        )
        return _format_destination(
            normalized_account,
            parsed.port or _SQL_DEFAULT_PORTS["snowflake"],
        )
    if parsed.hostname:
        return _parsed_host_destination(
            parsed,
            default_port=_SQL_DEFAULT_PORTS.get(scheme),
            error_message="SQL connection string requires host.",
        )
    raise ValueError(f"Unsupported SQL connection string: {connection_string}")


def neo4j_settings_destination(settings: Mapping[str, str]) -> str:
    raw_uri = str(settings.get("uri", "") or "").strip()
    parsed = urlparse(raw_uri)
    scheme = _primary_scheme(parsed.scheme)
    host = str(settings.get("host", "") or "").strip() or parsed.hostname or ""
    if not host:
        raise ValueError("Neo4j settings require host.")
    return _format_destination(host, parsed.port or _NEO4J_DEFAULT_PORTS.get(scheme, 7687))


def redis_connection_destination(connection_url: str) -> str:
    parsed = urlparse(connection_url)
    scheme = _primary_scheme(parsed.scheme)
    return _parsed_host_destination(
        parsed,
        default_port=_REDIS_DEFAULT_PORTS.get(scheme, 6379),
        error_message="Redis connection string requires host.",
    )


def snowflake_account_destination(account: str, *, port: int | None = None) -> str:
    normalized_account = account.strip()
    if not normalized_account:
        raise ValueError("Snowflake account must be non-empty.")
    if "." not in normalized_account:
        normalized_account = f"{normalized_account}.snowflakecomputing.com"
    return _format_destination(normalized_account, port or _SQL_DEFAULT_PORTS["snowflake"])


def connector_host_destination(host: str, *, port: int | None = None) -> str:
    return _format_destination(host, port)


def enforce_connector_destination(
    destination: str | None,
    *,
    surface: str,
    audit_context: EgressAuditContext | None = None,
) -> None:
    if destination is None:
        return
    enforce_egress_sync(
        destination,
        surface=surface,
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=audit_context,
    )


def enforce_sql_connection_egress(
    connection_string: str,
    *,
    surface: str,
    audit_context: EgressAuditContext | None = None,
) -> None:
    enforce_connector_destination(
        sql_connection_destination(connection_string),
        surface=surface,
        audit_context=audit_context,
    )


def enforce_neo4j_settings_egress(
    settings: Mapping[str, str],
    *,
    surface: str,
    audit_context: EgressAuditContext | None = None,
) -> None:
    enforce_connector_destination(
        neo4j_settings_destination(settings),
        surface=surface,
        audit_context=audit_context,
    )


def enforce_redis_connection_egress(
    connection_url: str,
    *,
    surface: str,
    audit_context: EgressAuditContext | None = None,
) -> None:
    enforce_connector_destination(
        redis_connection_destination(connection_url),
        surface=surface,
        audit_context=audit_context,
    )


def connector_audit_context(config: Mapping[str, Any]) -> EgressAuditContext:
    from apps.api_server.services.egress_guard import audit_context_from_config

    return audit_context_from_config(config)
