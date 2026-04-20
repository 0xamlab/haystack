"""
Real connection testers for all supported connector types.

Each tester returns (success: bool, message: str, latency_ms: int).
All SDK imports are lazy so missing packages cause a clean error message.
"""
from __future__ import annotations

import json
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def _test_file(config: dict[str, Any]) -> tuple[bool, str, int]:
    """Test local/inline file connectivity by parsing the configured payload."""
    from apps.api_server.connectors.file_connector import FileConnector

    t0 = time.perf_counter()
    try:
        connector = FileConnector(config)
        data = await connector.fetch_data()
        ms = int((time.perf_counter() - t0) * 1000)
        source = config.get("file_path") or "inline payload"
        return True, f"File connector parsed {len(data)} records from {source}", ms
    except Exception as exc:
        return False, f"File connector failed: {exc}", 0


async def _test_postgres(config: dict[str, Any]) -> tuple[bool, str, int]:
    """Test PostgreSQL via asyncpg."""
    try:
        import asyncpg  # type: ignore[import]
    except ImportError:
        return False, "PostgreSQL connector requires asyncpg — run: pip install asyncpg", 0

    host     = config.get("host", "localhost")
    port     = int(config.get("port", 5432))
    database = config.get("database", "postgres")
    user     = config.get("user", "postgres")
    password = config.get("password", "")
    ssl_mode = config.get("ssl_mode", "prefer")

    t0 = time.perf_counter()
    try:
        ssl  = ssl_mode if ssl_mode in ("require", "verify-full") else None
        conn = await asyncpg.connect(
            host=host, port=port, database=database,
            user=user, password=password,
            ssl=ssl, timeout=8,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        ms = int((time.perf_counter() - t0) * 1000)
        return True, f"PostgreSQL connection successful ({host}:{port}/{database})", ms
    except Exception as exc:
        return False, f"PostgreSQL connection failed: {exc}", 0


async def _test_sqlite(config: dict[str, Any]) -> tuple[bool, str, int]:
    """Test SQLite reachability via the local SQL connector path."""
    import sqlite3

    connection_string = str(config.get("connection_string", "") or "")
    path = str(config.get("path", "") or "")
    if connection_string.startswith("sqlite:///"):
        path = connection_string.removeprefix("sqlite:///")
    elif connection_string.startswith("sqlite+pysqlite:///"):
        path = connection_string.removeprefix("sqlite+pysqlite:///")
    elif connection_string == "sqlite:///:memory:":
        path = ":memory:"

    if not path:
        return False, "SQLite connector requires path or connection_string", 0

    t0 = time.perf_counter()
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        ms = int((time.perf_counter() - t0) * 1000)
        return True, f"SQLite connection successful ({path})", ms
    except Exception as exc:
        return False, f"SQLite connection failed: {exc}", 0


async def _test_rest_api(config: dict[str, Any]) -> tuple[bool, str, int]:
    """Test REST API reachability via httpx."""
    import httpx

    base_url = config.get("base_url") or config.get("url", "")
    if not base_url:
        return False, "REST API: 'base_url' is required in connector config", 0

    auth_type = config.get("auth_type", "none")
    headers: dict[str, str] = {}

    if auth_type == "bearer":
        token = config.get("api_key") or config.get("token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key":
        header_name = config.get("api_key_header", "X-API-Key")
        api_key     = config.get("api_key", "")
        if api_key:
            headers[header_name] = api_key
    elif auth_type == "basic":
        import base64
        user    = config.get("username", "")
        pw      = config.get("password", "")
        encoded = base64.b64encode(f"{user}:{pw}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"

    health_path = config.get("health_path", "")
    test_url    = base_url.rstrip("/") + ("/" + health_path.lstrip("/") if health_path else "")

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(test_url, headers=headers)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code < 500:
            return True, f"REST API reachable ({resp.status_code}) — {test_url}", ms
        return False, f"REST API returned {resp.status_code}: {test_url}", ms
    except Exception as exc:
        return False, f"REST API unreachable: {exc}", 0


async def _test_s3(config: dict[str, Any]) -> tuple[bool, str, int]:
    try:
        import boto3  # type: ignore[import]

        from apps.api_server.connectors.cloud_connector import _s3_client_kwargs
    except ImportError:
        return False, "AWS S3 connector requires boto3 — run: pip install boto3", 0

    t0 = time.perf_counter()
    try:
        s3 = boto3.client("s3", **_s3_client_kwargs(config))
        bucket = config.get("bucket", "")
        key = config.get("key", "")
        if bucket:
            if key:
                s3.head_object(Bucket=bucket, Key=key)
            else:
                s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
            ms = int((time.perf_counter() - t0) * 1000)
            target = f"s3://{bucket}/{key}" if key else f"s3://{bucket}"
            return True, f"AWS S3 accessible: {target}", ms
        s3.list_buckets()
        ms = int((time.perf_counter() - t0) * 1000)
        return True, "AWS S3 accessible (no bucket specified)", ms
    except Exception as exc:
        return False, f"AWS S3 error: {exc}", 0


async def _test_azure_blob(config: dict[str, Any]) -> tuple[bool, str, int]:
    from apps.api_server.connectors.cloud_connector import AzureBlobConnector

    t0 = time.perf_counter()
    try:
        connector = AzureBlobConnector(config)
        ok, message = await connector.validate_connection()
        ms = int((time.perf_counter() - t0) * 1000)
        return ok, message, ms if ok else 0
    except Exception as exc:
        return False, f"Azure error: {exc}", 0


async def _test_gcs(config: dict[str, Any]) -> tuple[bool, str, int]:
    try:
        from google.cloud import storage as gcs_storage  # type: ignore[import]

        from apps.api_server.connectors.cloud_connector import _build_gcs_client
    except ImportError:
        return (
            False,
            "GCS connector requires google-cloud-storage — run: pip install google-cloud-storage",
            0,
        )

    t0 = time.perf_counter()
    try:
        client = _build_gcs_client(gcs_storage, config)
        bucket = config.get("bucket")
        blob = config.get("blob")
        if bucket:
            if blob:
                client.bucket(bucket).blob(blob).reload()
            else:
                list(client.bucket(bucket).list_blobs(max_results=1))
        ms = int((time.perf_counter() - t0) * 1000)
        target = f"gs://{bucket}/{blob}" if bucket and blob else (bucket or "default project")
        return True, f"Google Cloud Storage accessible: {target}", ms
    except Exception as exc:
        return False, f"GCS error: {exc}", 0


async def _test_bigquery(config: dict[str, Any]) -> tuple[bool, str, int]:
    try:
        from google.cloud import bigquery as bq  # type: ignore[import]
    except ImportError:
        return (
            False,
            "BigQuery connector requires google-cloud-bigquery — "
            "run: pip install google-cloud-bigquery",
            0,
        )

    import os
    import tempfile
    t0 = time.perf_counter()
    try:
        sa_json = config.get("service_account_json")
        if sa_json:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(json.loads(sa_json) if isinstance(sa_json, str) else sa_json, f)
                tmp = f.name
            client = bq.Client.from_service_account_json(tmp, project=config.get("project_id"))
            os.unlink(tmp)
        else:
            client = bq.Client(project=config.get("project_id"))
        list(client.list_datasets(max_results=1))
        ms = int((time.perf_counter() - t0) * 1000)
        return True, f"BigQuery accessible (project: {config.get('project_id')})", ms
    except Exception as exc:
        return False, f"BigQuery error: {exc}", 0


async def _test_snowflake(config: dict[str, Any]) -> tuple[bool, str, int]:
    try:
        import snowflake.connector  # type: ignore[import]
    except ImportError:
        return (
            False,
            "Snowflake connector requires snowflake-connector-python — "
            "run: pip install snowflake-connector-python",
            0,
        )

    t0 = time.perf_counter()
    try:
        conn = snowflake.connector.connect(
            account=config.get("account", ""), user=config.get("user", ""),
            password=config.get("password", ""), warehouse=config.get("warehouse"),
            database=config.get("database"), schema=config.get("schema"), login_timeout=8,
        )
        conn.cursor().execute("SELECT CURRENT_VERSION()")
        conn.close()
        ms = int((time.perf_counter() - t0) * 1000)
        return True, f"Snowflake connection successful ({config.get('account')})", ms
    except Exception as exc:
        return False, f"Snowflake error: {exc}", 0


# ─── Router ────────────────────────────────────────────────────────────────────

async def test_connector_real(
    connector_type: str,
    config: dict[str, Any],
) -> tuple[bool, str, int]:
    """Dispatch to the appropriate tester. Returns (success, message, latency_ms)."""
    ct = connector_type.lower().replace("-", "_")
    if ct in ("file", "file_upload"):
        return await _test_file(config)
    if ct in ("postgres", "postgresql"):
        return await _test_postgres(config)
    if ct == "sqlite":
        return await _test_sqlite(config)
    if ct in ("rest", "rest_api"):
        return await _test_rest_api(config)
    if ct == "s3":
        return await _test_s3(config)
    if ct in ("azure", "azure_blob"):
        return await _test_azure_blob(config)
    if ct == "gcs":
        return await _test_gcs(config)
    if ct == "bigquery":
        return await _test_bigquery(config)
    if ct == "snowflake":
        return await _test_snowflake(config)
    if ct == "redshift":
        return await _test_postgres(config)

    return False, (
        f"Connector type '{connector_type}' test not yet implemented. "
        "Please verify credentials manually."
    ), 0


test_connector_real.__test__ = False
