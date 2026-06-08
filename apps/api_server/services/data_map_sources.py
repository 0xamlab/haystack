from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

from fastapi import HTTPException

from apps.api_server.services.columnar_loader import (
    delimited_text_to_arrow_table,
    records_to_arrow_table,
)
from apps.api_server.services.data_coercion import parse_delimited_records
from apps.api_server.services.egress_guard import EgressAuditContext, urllib_open
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.source_artifact_cache import (
    load_cached_arrow_table,
    source_content_artifact_key,
    store_cached_arrow_table,
)

TextRecordParser = Callable[[str], list[dict[str, Any]]]
UrlReader = Callable[[str], tuple[str, str]]
UrlFetcher = Callable[[str], list[dict[str, Any]]]
RegisteredSourceTableLoader = Callable[[str, str | None], Any]
DelimitedTableLoader = Callable[..., Any]


class DataSourceLike(Protocol):
    name: str
    dataset_id: str | None
    source_id: str | None
    records: list[dict[str, Any]] | None
    csv: str | None
    json_str: str | None
    url: str | None
    excel_b64: str | None
    parquet_b64: str | None
    connection: dict[str, Any] | None
    table: str | None


def parse_csv_records(text: str) -> list[dict[str, Any]]:
    """Parse CSV text into list of dicts, auto-converting numerics."""
    return parse_delimited_records(text, delimiter=",", sniff=True)


def parse_json_records(text: str) -> list[dict[str, Any]]:
    """Parse a JSON array string into list of dicts."""
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if isinstance(data, dict):
        for key in ("data", "records", "rows", "results", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON source must be an array of objects")
    return [row for row in data if isinstance(row, dict)]


def read_url_text(
    url: str,
    *,
    audit_context: EgressAuditContext | None = None,
) -> tuple[str, str]:
    """Fetch a text URL once and return ``(body, content_type)``."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL sources must use http or https.")
    request = urllib.request.Request(url, headers={"User-Agent": "algenta/1.0"})  # noqa: S310
    with urllib_open(
        request,
        timeout=15,
        surface="data_map_source_url",
        explicit_configured=True,
        egress_class="customer_connector",
        audit_context=audit_context,
        urlopen_fn=urllib.request.urlopen,
    ) as response:  # noqa: S310
        raw = response.read().decode("utf-8", errors="replace")
        content_type = response.headers.get("Content-Type", "")
    return raw, content_type


def fetch_url_records(
    url: str,
    *,
    parse_csv_fn: TextRecordParser = parse_csv_records,
    parse_json_records_fn: TextRecordParser = parse_json_records,
    read_url_text_fn: UrlReader = read_url_text,
) -> list[dict[str, Any]]:
    """Fetch URL and auto-detect CSV vs JSON."""
    raw, content_type = read_url_text_fn(url)
    if "json" in content_type or url.rstrip("/").endswith(".json"):
        return parse_json_records_fn(raw)
    return parse_csv_fn(raw)


def load_registered_source_table(source_id: str, org_id: str | None) -> Any:
    """Load a registered source from the org registry as a columnar table."""
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "missing_org_context",
                    "message": (f"Source '{source_id}' uses source_id and requires org context."),
                }
            },
        )

    from apps.api_server.services import source_registry as source_registry

    parquet_path = source_registry.get_source_parquet_path(org_id, source_id)
    if parquet_path is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "unknown_source_id",
                    "message": (f"Registered source '{source_id}' was not found for this org."),
                }
            },
        )

    import pyarrow.parquet as pq

    initialize_pyarrow_parquet_runtime()
    return pq.read_table(parquet_path)


def _invalid_connection_error(source_name: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": {
                "code": "invalid_connection",
                "message": (f"Source '{source_name}': connection dict must have a 'type' key"),
            }
        },
    )


def _use_connection_error(source_name: str) -> HTTPException:
    message = (
        f"Source '{source_name}': use a SQL connection with an explicit query instead of table."
    )
    return HTTPException(
        status_code=400,
        detail={"error": {"code": "use_connection", "message": message}},
    )


def _empty_source_error(source_name: str) -> HTTPException:
    message = (
        f"Source '{source_name}' has no data. Provide one of: records, csv, json_str, "
        "excel_b64, parquet_b64, url, or connection."
    )
    return HTTPException(
        status_code=400,
        detail={"error": {"code": "empty_source", "message": message}},
    )


def _load_error(source_name: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": {
                "code": "load_error",
                "message": f"Source '{source_name}' failed to load: {exc}",
            }
        },
    )


def _create_connector(source_name: str, connection: dict[str, Any]) -> Any:
    conn_type = connection.get("type", "")
    if not conn_type:
        raise _invalid_connection_error(source_name)
    from apps.api_server.connectors import ConnectorRegistry

    return ConnectorRegistry.create(conn_type, connection)


async def load_source_records(
    src: DataSourceLike,
    *,
    org_id: str | None = None,
    parse_csv_fn: TextRecordParser = parse_csv_records,
    parse_json_records_fn: TextRecordParser = parse_json_records,
    fetch_url_fn: UrlFetcher = fetch_url_records,
    load_registered_source_table_fn: RegisteredSourceTableLoader = load_registered_source_table,
) -> list[dict[str, Any]]:
    """Normalize any supported source type to row records."""
    try:
        registered_id = src.dataset_id or src.source_id
        if registered_id:
            table = load_registered_source_table_fn(registered_id, org_id)
            return [dict(row) for row in table.to_pylist()]

        if src.records is not None:
            return src.records

        if src.csv:
            return parse_csv_fn(src.csv)

        if src.json_str:
            return parse_json_records_fn(src.json_str)

        if src.excel_b64:
            from apps.api_server.connectors import FileConnector

            connector = FileConnector({"file_type": "excel", "content": src.excel_b64})
            return await connector.fetch_data()

        if src.parquet_b64:
            from apps.api_server.connectors import FileConnector

            connector = FileConnector({"file_type": "parquet", "content": src.parquet_b64})
            return await connector.fetch_data()

        if src.url:
            return fetch_url_fn(src.url)

        if src.connection:
            connector = _create_connector(src.name, src.connection)
            return await connector.fetch_data()

        if src.table:
            raise _use_connection_error(src.name)

        raise _empty_source_error(src.name)
    except HTTPException:
        raise
    except Exception as exc:
        raise _load_error(src.name, exc) from exc


async def load_source_table(
    src: DataSourceLike,
    *,
    org_id: str | None = None,
    parse_json_records_fn: TextRecordParser = parse_json_records,
    read_url_text_fn: UrlReader = read_url_text,
    load_registered_source_table_fn: RegisteredSourceTableLoader = load_registered_source_table,
    delimited_text_to_arrow_table_fn: DelimitedTableLoader = delimited_text_to_arrow_table,
) -> Any:
    """Load a source through the columnar fast path when possible."""
    try:
        registered_id = src.dataset_id or src.source_id
        if registered_id:
            return load_registered_source_table_fn(registered_id, org_id)

        artifact_cache_key = source_content_artifact_key(src)
        if artifact_cache_key is not None:
            cached_table = load_cached_arrow_table(artifact_cache_key)
            if cached_table is not None:
                return cached_table

        table = None

        if src.records is not None:
            table = records_to_arrow_table(src.records)

        elif src.csv:
            try:
                table = delimited_text_to_arrow_table_fn(src.csv, delimiter=",", sniff=True)
            except Exception:
                return None

        elif src.json_str:
            table = records_to_arrow_table(parse_json_records_fn(src.json_str))

        elif src.excel_b64:
            from apps.api_server.connectors import FileConnector

            connector = FileConnector({"file_type": "excel", "content": src.excel_b64})
            table = await connector.fetch_table()
            if table is None:
                return None

        elif src.parquet_b64:
            from apps.api_server.connectors import FileConnector

            connector = FileConnector({"file_type": "parquet", "content": src.parquet_b64})
            table = await connector.fetch_table()
            if table is None:
                return None

        elif src.url:
            raw, content_type = read_url_text_fn(src.url)
            if "json" in content_type or src.url.rstrip("/").endswith(".json"):
                table = records_to_arrow_table(parse_json_records_fn(raw))
            else:
                try:
                    table = delimited_text_to_arrow_table_fn(
                        raw,
                        delimiter=",",
                        sniff=True,
                    )
                except Exception:
                    return None

        elif src.connection:
            connector = _create_connector(src.name, src.connection)
            table = await connector.fetch_table()
            if table is None:
                return None

        elif src.table:
            raise _use_connection_error(src.name)

        if table is None:
            raise _empty_source_error(src.name)

        if artifact_cache_key is not None:
            store_cached_arrow_table(artifact_cache_key, table)

        return table
    except HTTPException:
        raise
    except Exception as exc:
        raise _load_error(src.name, exc) from exc
