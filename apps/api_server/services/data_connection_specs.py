"""Provider normalization, browsing, and source-spec building for datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException

from apps.api_server.routers.data_map import DataSource
from apps.api_server.services.connectors import normalize_type

_BROAD_TYPES = {"database", "api", "object_storage", "file_upload"}
_DATABASE_TYPES = {
    "postgres",
    "postgresql",
    "mysql",
    "mssql",
    "redshift",
    "snowflake",
    "bigquery",
    "sqlite",
}
_OBJECT_STORAGE_TYPES = {"s3", "gcs", "azure", "azure_blob"}
_API_TYPES = {"rest", "rest_api"}
_REFRESHABLE_INLINE_FIELDS = {"url"}


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
        if normalized.startswith("redshift"):
            return "redshift"
        if normalized.startswith("snowflake"):
            return "snowflake"
        if normalized.startswith("bigquery"):
            return "bigquery"
        if normalized.startswith("sqlite"):
            return "sqlite"
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
    if "server" in config:
        return "mssql"
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
                                "mssql, redshift, snowflake, bigquery, sqlite or a "
                                "recognizable connection_string."
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


def strip_none(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, int | float):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _build_database_connection_string(provider: str, config: dict[str, Any]) -> str:
    if config.get("connection_string"):
        return str(config["connection_string"])

    host = str(config.get("host", "localhost"))
    port = config.get("port")
    database = str(config.get("database", ""))
    user = str(config.get("user", config.get("username", "")))
    password = str(config.get("password", ""))

    if provider in {"postgres", "redshift"}:
        port_value = int(port or 5432)
        return f"postgresql://{user}:{password}@{host}:{port_value}/{database}"
    if provider == "mysql":
        port_value = int(port or 3306)
        return f"mysql+pymysql://{user}:{password}@{host}:{port_value}/{database}"
    if provider == "mssql":
        port_value = int(port or 1433)
        driver = str(config.get("driver", "ODBC Driver 18 for SQL Server"))
        return (
            f"mssql+pyodbc://{user}:{password}@{host}:{port_value}/{database}"
            f"?driver={driver.replace(' ', '+')}"
        )
    if provider == "sqlite":
        path = str(config.get("path", ""))
        if not path:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "missing_connection_string",
                        "message": ("sqlite connections require path or connection_string."),
                    }
                },
            )
        if path == ":memory:":
            return "sqlite:///:memory:"
        return f"sqlite:///{path}"
    if provider == "snowflake":
        account = str(config.get("account", ""))
        warehouse = str(config.get("warehouse", ""))
        schema = str(config.get("schema", ""))
        if not (account and user and password and database):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "missing_connection_string",
                        "message": (
                            "snowflake connections require connection_string or "
                            "account/user/password/database."
                        ),
                    }
                },
            )
        suffix = f"/{database}"
        if schema:
            suffix += f"/{schema}"
        query = f"?warehouse={warehouse}" if warehouse else ""
        return f"snowflake://{user}:{password}@{account}{suffix}{query}"
    if provider == "bigquery":
        project_id = str(config.get("project_id", ""))
        if not project_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "missing_connection_string",
                        "message": (
                            "bigquery connections require connection_string or project_id."
                        ),
                    }
                },
            )
        return f"bigquery://{project_id}"
    raise HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": "invalid_connection_provider",
                "message": f"Unsupported database provider '{provider}'.",
            }
        },
    )


def _sql_source_selection_query(table_name: str) -> str:
    parts = [part.strip().strip('"') for part in table_name.split(".") if part.strip()]
    if not parts:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_selection",
                    "message": "selection.table cannot be empty.",
                }
            },
        )
    quoted = ".".join(f'"{part}"' for part in parts)
    return f"SELECT * FROM {quoted}"  # noqa: S608 - identifiers are stripped and quoted


async def _browse_sql(
    config: dict[str, Any],
    *,
    provider: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    connection_string = _build_database_connection_string(
        provider or _infer_database_type(config) or "postgres",
        config,
    )
    try:
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.ext.asyncio import create_async_engine
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"SQL browsing requires SQLAlchemy: {exc}") from exc

    system_schemas = {"information_schema", "pg_catalog", "pg_toast", "sys", "sqlite_master"}

    def _collect(sync_conn: Any) -> list[dict[str, Any]]:
        inspector = inspect(sync_conn)
        items: list[dict[str, Any]] = []
        for schema in inspector.get_schema_names():
            if schema in system_schemas:
                continue
            for table_name in inspector.get_table_names(schema=schema):
                label = f"{schema}.{table_name}" if schema and schema != "main" else table_name
                items.append(
                    {
                        "id": label,
                        "label": label,
                        "kind": "table",
                        "selection": {"table": label},
                        "schema": schema,
                        "name": table_name,
                    }
                )
                if len(items) >= 200:
                    return items
            for view_name in inspector.get_view_names(schema=schema):
                label = f"{schema}.{view_name}" if schema and schema != "main" else view_name
                items.append(
                    {
                        "id": label,
                        "label": label,
                        "kind": "view",
                        "selection": {"table": label},
                        "schema": schema,
                        "name": view_name,
                    }
                )
                if len(items) >= 200:
                    return items
        return items

    if any(
        marker in connection_string
        for marker in ("+asyncpg", "+aiosqlite", "+asyncmy", "+aiomysql", "+aioodbc")
    ):
        engine = create_async_engine(connection_string, pool_pre_ping=True)
        try:
            async with engine.connect() as conn:
                items = await conn.run_sync(_collect)
        finally:
            await engine.dispose()
    else:
        import asyncio

        def _sync_browse() -> list[dict[str, Any]]:
            engine = create_engine(connection_string, pool_pre_ping=True)
            try:
                with engine.connect() as conn:
                    return _collect(conn)
            finally:
                engine.dispose()

        items = await asyncio.to_thread(_sync_browse)

    return items, f"Found {len(items)} browsable database objects"


async def browse_connector_real(
    connector_type: str,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    ct = normalize_type(connector_type)
    if ct in _DATABASE_TYPES:
        return await _browse_sql(config, provider=ct)
    if ct == "s3":
        import boto3  # type: ignore[import]

        from apps.api_server.connectors.cloud_connector import _s3_client_kwargs

        bucket = str(config.get("bucket", ""))
        if not bucket:
            return [], "S3 browse requires bucket"
        s3 = boto3.client("s3", **_s3_client_kwargs(config))
        resp = s3.list_objects_v2(Bucket=bucket, MaxKeys=100)
        items = [
            {
                "id": obj["Key"],
                "label": obj["Key"],
                "kind": "object",
                "selection": {"object_path": obj["Key"]},
                "size": obj.get("Size"),
            }
            for obj in resp.get("Contents", [])
        ]
        return items, f"Found {len(items)} objects in s3://{bucket}"
    if ct == "gcs":
        import asyncio

        from google.cloud import storage as gcs_storage  # type: ignore[import]

        from apps.api_server.connectors.cloud_connector import _build_gcs_client

        bucket = str(config.get("bucket", ""))
        if not bucket:
            return [], "GCS browse requires bucket"

        def _sync() -> list[dict[str, Any]]:
            client = _build_gcs_client(gcs_storage, config)
            return [
                {
                    "id": blob.name,
                    "label": blob.name,
                    "kind": "object",
                    "selection": {"object_path": blob.name},
                }
                for blob in client.bucket(bucket).list_blobs(max_results=100)
            ]

        items = await asyncio.to_thread(_sync)
        return items, f"Found {len(items)} objects in gs://{bucket}"
    if ct in {"azure", "azure_blob"}:
        import asyncio

        from azure.storage.blob import BlobServiceClient  # type: ignore[import]

        container = str(config.get("container", ""))
        if not container:
            return [], "Azure browse requires container"

        def _sync() -> list[dict[str, Any]]:
            connection_string = str(config.get("connection_string", "") or "")
            account_url = str(config.get("account_url", "") or "")
            if connection_string:
                service = BlobServiceClient.from_connection_string(connection_string)
            elif account_url:
                service = BlobServiceClient(account_url=account_url, credential=None)
            else:
                raise RuntimeError("Azure browse requires connection_string or account_url")
            client = service.get_container_client(container)
            items: list[dict[str, Any]] = []
            for blob in client.list_blobs(
                name_starts_with=config.get("prefix"),
                results_per_page=100,
            ):
                items.append(
                    {
                        "id": blob.name,
                        "label": blob.name,
                        "kind": "object",
                        "selection": {"object_path": blob.name},
                    }
                )
                if len(items) >= 100:
                    break
            return items

        items = await asyncio.to_thread(_sync)
        return items, f"Found {len(items)} blobs in azure://{container}"
    if ct == "rest":
        url = str(config.get("url") or config.get("base_url") or "")
        if not url:
            return [], "REST browse requires url or base_url"
        choice = {
            "id": url,
            "label": url,
            "kind": "endpoint",
            "selection": strip_none({"url": url, "data_path": config.get("data_path")}),
        }
        return [choice], "REST endpoints use the configured URL directly"
    return [], f"Browse not implemented for '{ct}'"


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

    if connection_type == "database":
        connection_string = _build_database_connection_string(provider, cfg)
        sql_query = str(
            sel.get("sql_query") or cfg.get("sql_query") or cfg.get("query") or ""
        ).strip()
        table = str(sel.get("table") or cfg.get("table") or "").strip()
        if not sql_query and table:
            sql_query = _sql_source_selection_query(table)
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
        source = DataSource(
            name=dataset_name,
            connection={
                "type": "sql",
                "connection_string": connection_string,
                "query": sql_query,
                "limit": cfg.get("limit", 10000),
            },
        )
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
        source = DataSource(
            name=dataset_name,
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
            ),
        )
        return source, True, None

    if connection_type == "object_storage":
        source = DataSource(
            name=dataset_name,
            connection=_build_object_storage_connection(provider, cfg, sel),
        )
        return source, True, None

    file_path = str(
        cfg.get("file_path")
        or cfg.get("path")
        or sel.get("path")
        or direct_payload.get("path")
        or ""
    ).strip()
    if file_path:
        file_type = str(
            cfg.get("file_type")
            or cfg.get("format")
            or Path(file_path).suffix.lstrip(".")
            or "csv"
        ).strip().lower()
        if file_type in {"xlsx", "xls"}:
            file_type = "excel"
        source = DataSource(
            name=dataset_name,
            connection=strip_none(
                {
                    "type": "file",
                    "file_type": file_type,
                    "file_path": file_path,
                    "delimiter": cfg.get("delimiter"),
                    "json_path": cfg.get("json_path"),
                    "sheet": cfg.get("sheet"),
                }
            ),
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
