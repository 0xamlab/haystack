"""Provider normalization, browsing, and source-spec building for datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException

from apps.api_server.schemas.data_map import DataSource
from apps.api_server.services.connectors import normalize_type
from apps.api_server.services.data_connection_browse import (
    _DATABASE_TYPES,
    _browse_elasticsearch,
    _browse_postgres_compatible_sql,
    _browse_redis_detailed,
    _browse_sql,
    _build_database_connection_string,
    _clear_browse_result_cache,
    _clear_sync_browse_engine_cache,
    _sql_source_selection_query,
    _sql_source_selection_query_for_provider,
    browse_connector_real,
    browse_connector_real_detailed,
    strip_none,
    truthy,
)
from apps.api_server.services.data_connection_discovery import (
    _API_TYPES,
    _OBJECT_STORAGE_TYPES,
    build_discovery_metadata,
)
from apps.api_server.services.data_connection_discovery import (
    build_discovery_labels as _build_discovery_labels,
)

_BROAD_TYPES = {"database", "api", "object_storage", "file_upload"}
_REFRESHABLE_INLINE_FIELDS = {"url"}
__all__ = [
    "_build_database_connection_string",
    "_browse_elasticsearch",
    "_browse_postgres_compatible_sql",
    "_browse_redis_detailed",
    "_browse_sql",
    "_build_object_storage_connection",
    "_clear_browse_result_cache",
    "_clear_sync_browse_engine_cache",
    "_sql_source_selection_query",
    "_sql_source_selection_query_for_provider",
    "browse_connector_real",
    "browse_connector_real_detailed",
    "build_discovery_metadata",
    "build_discovery_labels",
    "build_source_spec",
    "normalize_connection_provider",
]
build_discovery_labels = _build_discovery_labels


def _infer_database_type(config: dict[str, Any]) -> str | None:
    connection_string = str(config.get("connection_string", "") or "")
    if connection_string:
        normalized = connection_string.lower()
        if normalized.startswith("postgresql") or normalized.startswith("postgres"):
            return "postgres"
        if normalized.startswith("mysql"):
            return "mysql"
        if normalized.startswith("mssql") or normalized.startswith("sqlserver"):
            return "mssql"
        if normalized.startswith("oracle"):
            return "oracle"
        if normalized.startswith("redshift"):
            return "redshift"
        if normalized.startswith("clickhouse"):
            return "clickhouse"
        if normalized.startswith("snowflake"):
            return "snowflake"
        if normalized.startswith("bigquery"):
            return "bigquery"
        if normalized.startswith("sqlite"):
            return "sqlite"
        if normalized.startswith(
            ("neo4j://", "neo4j+s://", "neo4j+ssc://", "bolt://", "bolt+s://", "bolt+ssc://")
        ):
            return "neo4j"
        if normalized.startswith(("redis://", "rediss://")):
            return "redis"
    provider = (
        str(config.get("provider", "") or config.get("database_type", "") or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    if provider:
        return normalize_type(provider)
    if any(key in config for key in ("account", "warehouse")):
        return "snowflake"
    if "project_id" in config:
        return "bigquery"
    if any(key in config for key in ("uri", "cypher", "query")) and (
        str(config.get("uri", "") or "").strip().lower().startswith(("neo4j", "bolt"))
        or "username" in config
        and "database" in config
    ):
        return "neo4j"
    if any(key in config for key in ("redis_url", "key_pattern", "keys")):
        return "redis"
    if any(key in config for key in ("api_key", "apiKey", "index")):
        return "elasticsearch"
    if "server" in config:
        return "mssql"
    if "service_name" in config or "wallet_location" in config:
        return "oracle"
    if "host" in config:
        return "postgres"
    return None


def _infer_object_storage_type(config: dict[str, Any]) -> str | None:
    provider = (
        str(config.get("provider", "") or config.get("storage_type", "") or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    if provider:
        return normalize_type(provider)
    if "connection_string" in config and "container" in config:
        return "azure"
    if "blob" in config:
        return "gcs"
    if "key" in config or "endpoint_url" in config:
        return "s3"
    return None


def normalize_connection_provider(
    connection_type: str,
    connection_config: dict[str, Any] | None,
    provider: str | None = None,
) -> tuple[str, str]:
    raw_type = (connection_type or "").strip().lower().replace("-", "_")
    cfg = connection_config or {}
    requested_provider = (provider or cfg.get("provider") or "").strip().lower().replace("-", "_")

    if raw_type in _BROAD_TYPES:
        if raw_type == "database":
            specific = (
                normalize_type(requested_provider)
                if requested_provider
                else (_infer_database_type(cfg) or "")
            )
            if specific not in _DATABASE_TYPES:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_connection_provider",
                            "message": (
                                "Database connections require provider one of postgres, mysql, "
                                "mssql, oracle, redshift, clickhouse, snowflake, bigquery, sqlite, "
                                "elasticsearch, neo4j, redis or a recognizable connection_string."
                            ),
                        }
                    },
                )
            return raw_type, specific
        if raw_type == "object_storage":
            specific = (
                normalize_type(requested_provider)
                if requested_provider
                else (_infer_object_storage_type(cfg) or "")
            )
            if specific not in _OBJECT_STORAGE_TYPES:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_connection_provider",
                            "message": (
                                "Object storage connections require provider one of s3, gcs, azure."
                            ),
                        }
                    },
                )
            return raw_type, specific
        if raw_type == "api":
            specific = normalize_type(requested_provider or "rest")
            if specific not in _API_TYPES:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_connection_provider",
                            "message": "API connections currently support provider rest.",
                        }
                    },
                )
            return raw_type, specific
        return raw_type, "file"

    specific = normalize_type(raw_type)
    if specific in _DATABASE_TYPES:
        return "database", specific
    if specific in _OBJECT_STORAGE_TYPES:
        return "object_storage", specific
    if specific in _API_TYPES:
        return "api", specific
    if specific in {"file", "file_upload"}:
        return "file_upload", "file"
    raise HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": "invalid_connection_type",
                "message": "Unsupported connection_type.",
            }
        },
    )


def _selection_value(
    selection: dict[str, Any],
    config: dict[str, Any],
    *keys: str,
) -> Any:
    for key in keys:
        if selection.get(key) not in (None, ""):
            return selection.get(key)
        if config.get(key) not in (None, ""):
            return config.get(key)
    return None


def _required_non_empty_string(
    value: Any,
    *,
    code: str,
    message: str,
) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": code, "message": message}},
        )
    return normalized


def _neo4j_identifier(value: str) -> str:
    normalized = _required_non_empty_string(
        value,
        code="invalid_selection",
        message="Neo4j selection values cannot be empty.",
    )
    return normalized.replace("`", "``")


def _build_elasticsearch_connection(
    config: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    index = _required_non_empty_string(
        _selection_value(selection, config, "index"),
        code="selection_required",
        message="Elasticsearch datasets require selection.index or connection_config.index.",
    )
    connection = strip_none(
        {
            "type": "elasticsearch",
            "url": config.get("url") or config.get("endpoint") or config.get("connection_string"),
            "api_key": config.get("api_key", config.get("apiKey", config.get("password"))),
            "index": index,
            "query": selection.get("query") or config.get("query"),
            "limit": config.get("limit") or config.get("size"),
            "include_hidden": config.get("include_hidden"),
        }
    )
    return connection


def _build_neo4j_connection(
    config: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    explicit_query = str(
        selection.get("cypher")
        or selection.get("query")
        or config.get("cypher")
        or config.get("query")
        or ""
    ).strip()
    parameters = dict(config.get("parameters") or {})
    limit = config.get("limit")
    if explicit_query:
        connection = strip_none(
            {
                "type": "neo4j",
                "uri": config.get("uri") or config.get("url") or config.get("connection_string"),
                "username": config.get("username", config.get("user")),
                "password": config.get("password"),
                "database": config.get("database", config.get("db")),
                "query": explicit_query,
                "parameters": parameters or None,
                "limit": limit,
            }
        )
        return connection

    label = _selection_value(selection, config, "label")
    relationship_type = _selection_value(selection, config, "relationship_type")
    if label not in (None, ""):
        escaped_label = _neo4j_identifier(str(label))
        query = f"MATCH (n:`{escaped_label}`) RETURN n LIMIT $limit"
    elif relationship_type not in (None, ""):
        escaped_relationship = _neo4j_identifier(str(relationship_type))
        query = f"MATCH ()-[r:`{escaped_relationship}`]->() RETURN r LIMIT $limit"
    else:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "selection_required",
                    "message": (
                        "Neo4j datasets require selection.label, selection.relationship_type, "
                        "or an explicit connection_config.query/cypher."
                    ),
                }
            },
        )
    auto_limit = int(limit or 1000)
    parameters = {"limit": auto_limit, **parameters}
    return strip_none(
        {
            "type": "neo4j",
            "uri": config.get("uri") or config.get("url") or config.get("connection_string"),
            "username": config.get("username", config.get("user")),
            "password": config.get("password"),
            "database": config.get("database", config.get("db")),
            "query": query,
            "parameters": parameters,
            "limit": auto_limit,
        }
    )


def _build_redis_connection(
    config: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    raw_keys = _selection_value(selection, config, "keys")
    if raw_keys in (None, ""):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "selection_required",
                    "message": "Redis datasets require selection.keys or connection_config.keys.",
                }
            },
        )
    if isinstance(raw_keys, str):
        keys = [item.strip() for item in raw_keys.split(",") if item.strip()]
    elif isinstance(raw_keys, list | tuple | set):
        keys = [str(item).strip() for item in raw_keys if str(item).strip()]
    else:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_selection",
                    "message": "Redis selection.keys must be an array or comma-separated string.",
                }
            },
        )
    if not keys:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "selection_required",
                    "message": "Redis datasets require at least one explicit key.",
                }
            },
        )
    return strip_none(
        {
            "type": "redis",
            "url": config.get("url") or config.get("redis_url") or config.get("connection_string"),
            "keys": keys,
            "value_max_items": config.get("value_max_items"),
        }
    )


def _build_object_storage_connection(
    provider: str,
    config: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    blob_url = str(config.get("blob_url", "") or "").strip()
    path = (
        selection.get("object_path")
        or config.get("object_path")
        or config.get("key")
        or config.get("blob")
    )
    if not path and blob_url:
        parsed = urlparse(blob_url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) > 1:
            path = "/".join(parts[1:])
    if not path:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "selection_required",
                    "message": "Object storage datasets require selection.object_path.",
                }
            },
        )
    if provider == "s3":
        bucket = config.get("bucket")
        if not bucket:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_connection_config",
                        "message": "s3 connections require bucket.",
                    }
                },
            )
        return strip_none(
            {
                "type": "s3",
                "bucket": bucket,
                "key": path,
                "file_type": config.get("file_type"),
                "region": config.get("region"),
                "anonymous": truthy(config.get("anonymous")) or None,
                "aws_access_key_id": config.get("access_key_id") or config.get("aws_access_key_id"),
                "aws_secret_access_key": (
                    config.get("secret_access_key") or config.get("aws_secret_access_key")
                ),
                "aws_session_token": config.get("session_token") or config.get("aws_session_token"),
                "endpoint_url": config.get("endpoint_url"),
                "json_path": config.get("json_path"),
            }
        )
    if provider == "gcs":
        bucket = config.get("bucket")
        if not bucket:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_connection_config",
                        "message": "gcs connections require bucket.",
                    }
                },
            )
        return strip_none(
            {
                "type": "gcs",
                "bucket": bucket,
                "blob": path,
                "file_type": config.get("file_type"),
                "anonymous": truthy(config.get("anonymous")) or None,
                "credentials": config.get("credentials") or config.get("service_account_json"),
                "project_id": config.get("project_id"),
                "json_path": config.get("json_path"),
            }
        )
    if provider in {"azure", "azure_blob"}:
        conn_str = config.get("connection_string")
        account_url = config.get("account_url")
        container = config.get("container")
        if not blob_url and (not container or not path):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_connection_config",
                        "message": ("azure connections require blob_url or container and blob."),
                    }
                },
            )
        if not blob_url and not (conn_str or account_url):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_connection_config",
                        "message": (
                            "azure connections require connection_string, account_url, or blob_url."
                        ),
                    }
                },
            )
        return strip_none(
            {
                "type": "azure_blob",
                "connection_string": conn_str,
                "account_url": account_url,
                "blob_url": blob_url,
                "container": container,
                "blob": path,
                "file_type": config.get("file_type"),
                "anonymous": truthy(config.get("anonymous")) or None,
                "json_path": config.get("json_path"),
            }
        )
    raise HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": "invalid_connection_provider",
                "message": f"Unsupported object storage provider '{provider}'.",
            }
        },
    )


def build_source_spec(
    *,
    dataset_name: str,
    connection_type: str,
    provider: str,
    connection_config: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    direct_payload: dict[str, Any],
) -> tuple[DataSource, bool, dict[str, Any] | None]:
    cfg = connection_config or {}
    sel = selection or {}

    def make_source(
        *,
        connection: dict[str, Any] | None = None,
        records: list[dict[str, Any]] | None = None,
        csv: str | None = None,
        json_str: str | None = None,
        url: str | None = None,
        excel_b64: str | None = None,
        parquet_b64: str | None = None,
        table: str | None = None,
    ) -> DataSource:
        return DataSource(
            name=dataset_name,
            dataset_id=None,
            source_id=None,
            records=records,
            csv=csv,
            json_str=json_str,
            url=url,
            excel_b64=excel_b64,
            parquet_b64=parquet_b64,
            connection=connection,
            table=table,
        )

    if connection_type == "database":
        if provider == "elasticsearch":
            source = make_source(connection=_build_elasticsearch_connection(cfg, sel))
            return source, True, None
        if provider == "neo4j":
            source = make_source(connection=_build_neo4j_connection(cfg, sel))
            return source, True, None
        if provider == "redis":
            source = make_source(connection=_build_redis_connection(cfg, sel))
            return source, True, None
        if provider == "oracle":
            sql_query = str(
                sel.get("sql_query") or cfg.get("sql_query") or cfg.get("query") or ""
            ).strip()
            table = str(sel.get("table") or cfg.get("table") or "").strip()
            if not sql_query and table:
                sql_query = _sql_source_selection_query_for_provider(table, provider=provider)
            if not sql_query:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "selection_required",
                            "message": (
                                "Database datasets require selection.table or selection.sql_query."
                            ),
                        }
                    },
                )
            connection = strip_none(
                {
                    "type": "oracle",
                    "connection_string": cfg.get("connection_string"),
                    "user": cfg.get("user", cfg.get("username")),
                    "password": cfg.get("password"),
                    "dsn": cfg.get("dsn", cfg.get("connect_descriptor")),
                    "host": cfg.get("host"),
                    "port": cfg.get("port"),
                    "service_name": cfg.get("service_name", cfg.get("database")),
                    "config_dir": cfg.get("config_dir", cfg.get("tns_admin")),
                    "wallet_location": cfg.get("wallet_location"),
                    "wallet_password": cfg.get("wallet_password"),
                    "query": sql_query,
                    "limit": cfg.get("limit"),
                    "fetch_batch_size": cfg.get("fetch_batch_size"),
                }
            )
            return make_source(connection=connection), True, None
        connection_string = _build_database_connection_string(provider, cfg)
        sql_query = str(
            sel.get("sql_query") or cfg.get("sql_query") or cfg.get("query") or ""
        ).strip()
        table = str(sel.get("table") or cfg.get("table") or "").strip()
        if not sql_query and table:
            sql_query = _sql_source_selection_query_for_provider(table, provider=provider)
        if not sql_query:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "selection_required",
                        "message": (
                            "Database datasets require selection.table or selection.sql_query."
                        ),
                    }
                },
            )
        connection: dict[str, Any] = {
            "type": "sql",
            "connection_string": connection_string,
            "query": sql_query,
        }
        if cfg.get("limit") is not None:
            connection["limit"] = cfg.get("limit")
        source = make_source(connection=connection)
        return source, True, None

    if connection_type == "api":
        url = str(sel.get("url") or cfg.get("url") or cfg.get("base_url") or "").strip()
        if not url:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "selection_required",
                        "message": "API datasets require url or selection.url.",
                    }
                },
            )
        headers = cfg.get("headers")
        if not headers and cfg.get("auth_type") == "bearer" and cfg.get("api_key"):
            headers = {"Authorization": f"Bearer {cfg['api_key']}"}
        elif not headers and cfg.get("auth_type") == "api_key" and cfg.get("api_key"):
            headers = {cfg.get("api_key_header", "X-API-Key"): cfg["api_key"]}
        source = make_source(
            connection=strip_none(
                {
                    "type": "rest_api",
                    "url": url,
                    "method": cfg.get("method", "GET"),
                    "headers": headers,
                    "params": cfg.get("params"),
                    "body": cfg.get("body"),
                    "timeout": cfg.get("timeout", 30),
                    "data_path": sel.get("data_path") or cfg.get("data_path"),
                }
            )
        )
        return source, True, None

    if connection_type == "object_storage":
        source = make_source(connection=_build_object_storage_connection(provider, cfg, sel))
        return source, True, None

    file_path = str(
        cfg.get("file_path")
        or cfg.get("path")
        or sel.get("path")
        or direct_payload.get("path")
        or ""
    ).strip()
    if file_path:
        file_type = (
            str(
                cfg.get("file_type")
                or cfg.get("format")
                or Path(file_path).suffix.lstrip(".")
                or "csv"
            )
            .strip()
            .lower()
        )
        if file_type in {"xlsx", "xls"}:
            file_type = "excel"
        source = make_source(
            connection=strip_none(
                {
                    "type": "file",
                    "file_type": file_type,
                    "file_path": file_path,
                    "delimiter": cfg.get("delimiter"),
                    "json_path": cfg.get("json_path"),
                    "sheet": cfg.get("sheet"),
                }
            )
        )
        return (
            source,
            True,
            {"direct": strip_none({"path": file_path, "file_type": file_type})},
        )

    source_payload = strip_none(
        {
            "records": direct_payload.get("records"),
            "csv": direct_payload.get("csv"),
            "json_str": direct_payload.get("json_str"),
            "url": direct_payload.get("url"),
            "excel_b64": direct_payload.get("excel_b64"),
            "parquet_b64": direct_payload.get("parquet_b64"),
        }
    )
    if not source_payload:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "no_data",
                    "message": (
                        "file_upload datasets require a file path or one of "
                        "records, csv, json_str, url, excel_b64, or parquet_b64."
                    ),
                }
            },
        )
    source = DataSource(name=dataset_name, **source_payload)
    refreshable = bool(_REFRESHABLE_INLINE_FIELDS & set(source_payload))
    stored_definition = (
        {"direct": strip_none({"url": source_payload.get("url")})} if refreshable else None
    )
    return source, refreshable, stored_definition
