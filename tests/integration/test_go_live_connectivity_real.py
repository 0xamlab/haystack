"""
Real go-live connectivity runner.

This is intentionally not a mocked smoke test.

What it does:
  1. Uses the real local Postgres + Redis stack.
  2. Seeds a real API key into the local database.
  3. Starts the real FastAPI server on localhost.
  4. Serves real dataset files over a local HTTP server.
  5. Exercises the real auth, registry, query, map, connector, and MCP paths.

Covered local data-connectivity paths:
  - records
  - csv
  - json_str
  - url (csv/json over HTTP)
  - excel_b64
  - parquet_b64
  - connection: sql
  - connection: rest_api
  - source_id reuse

Covered local API surfaces:
  - X-API-Key auth
  - Authorization: Bearer auth
  - /v1/sources register/list/get/graph/delete
  - /v1/query exact-spec execution
  - /v1/map via source_id
  - /v1/connectors create/test/browse/delete
  - /mcp/tools
  - warm parallel query fanout

Optional live external checks:
  - public s3 / gcs / azure_blob exact registration + query by default
  - public third-party REST example connectors (Fivetran + dlt) exact registration + query by default
  - custom s3 / gcs / azure_blob through source registration when env vars are set
  - snowflake / bigquery through connector /test when env vars are set

Run:
  PYTHONPATH=. python3 tests/integration/test_go_live_connectivity_real.py

Optional:
  PYTHONPATH=. python3 tests/integration/test_go_live_connectivity_real.py --parallel-tasks 16
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import math
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

os.environ.setdefault("ARROW_USER_SIMD_LEVEL", "NONE")

import httpx
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.integration.connector_validation_catalog import THIRD_PARTY_PUBLIC_CASES  # noqa: E402

TEST_FILES = ROOT / "test_files"
DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://angel:@localhost:5432/decision_engine")
DEFAULT_DB_URL_SYNC = os.environ.get("DATABASE_URL_SYNC", "postgresql://angel:@localhost:5432/decision_engine")
DEFAULT_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results: list[tuple[str, str, str]] = []
timings: list[tuple[str, float]] = []


def check(name: str, fn) -> Any:
    t0 = time.perf_counter()
    try:
        out = fn()
        elapsed = time.perf_counter() - t0
        results.append((PASS, name, ""))
        timings.append((name, elapsed))
        print(f"  {PASS} {name} ({elapsed:.3f}s)")
        return out
    except AssertionError as exc:
        elapsed = time.perf_counter() - t0
        results.append((FAIL, name, str(exc)))
        timings.append((name, elapsed))
        print(f"  {FAIL} {name}: {exc}")
        return None
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        results.append((FAIL, name, f"{type(exc).__name__}: {exc}"))
        timings.append((name, elapsed))
        print(f"  {FAIL} {name}: {type(exc).__name__}: {exc}")
        return None


def skip(name: str, reason: str) -> None:
    results.append((SKIP, name, reason))
    print(f"  {SKIP} {name}: {reason}")


def run_async(coro):
    return asyncio.run(coro)


def run_migrations(env: dict[str, str]) -> None:
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ROOT / "apps" / "api_server" / "alembic.ini"),
        "upgrade",
        "head",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Alembic upgrade failed:\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_log_tail(log_path: str | Path | None, *, lines: int = 40) -> str:
    if not log_path:
        return ""
    path = Path(log_path)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return ""
    tail = text.splitlines()[-lines:]
    return "\n".join(tail)


def wait_for_http(
    url: str,
    timeout: float = 45.0,
    *,
    proc: subprocess.Popen[str] | None = None,
    log_path: str | Path | None = None,
) -> None:
    start = time.monotonic()
    last_error = "no response"
    while time.monotonic() - start < timeout:
        if proc is not None:
            exit_code = proc.poll()
            if exit_code is not None:
                path = log_path or getattr(proc, "algenta_log_path", None)
                log_tail = _read_log_tail(path)
                detail = f"Process exited with code {exit_code}"
                if log_tail:
                    detail += f"\n--- process log tail ---\n{log_tail}"
                raise RuntimeError(
                    f"Timed out waiting for {url}: {detail}"
                )
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                return
            last_error = f"status {resp.status_code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    path = log_path or getattr(proc, "algenta_log_path", None)
    log_tail = _read_log_tail(path)
    detail = f"Timed out waiting for {url}: {last_error}"
    if log_tail:
        detail += f"\n--- process log tail ---\n{log_tail}"
    raise RuntimeError(detail)


def ensure_port_open(host: str, port: int, label: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect((host, port))
    print(f"  {PASS} preflight {label} reachable at {host}:{port}")


async def seed_api_key(database_url: str) -> tuple[str, str]:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models import (
        APIKey,
        Organization,
        OrgPlan,
        OrgStatus,
        User,
        UserRole,
        UserStatus,
    )
    from apps.api_server.services.auth_service import generate_api_key

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    slug = "go-live-connectivity"
    async with session_factory() as session:
        org_result = await session.execute(select(Organization).where(Organization.slug == slug))
        org = org_result.scalar_one_or_none()
        if org is None:
            org = Organization(
                name="Go Live Connectivity",
                slug=slug,
                plan=OrgPlan.DEVELOPER,
                status=OrgStatus.ACTIVE,
            )
            session.add(org)
            await session.flush()

        user_result = await session.execute(
            select(User).where(User.org_id == org.id).where(User.email == "golive@example.com")
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(
                org_id=org.id,
                email="golive@example.com",
                password_hash="local-go-live",
                name="Go Live",
                role=UserRole.OWNER,
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(user)
            await session.flush()

        raw_key, key_prefix, hashed_key = generate_api_key()
        api_key = APIKey(
            org_id=org.id,
            user_id=user.id,
            label="Go Live Connectivity",
            key_prefix=key_prefix,
            hashed_key=hashed_key,
        )
        session.add(api_key)
        await session.commit()

        org_id = str(org.id)

    await engine.dispose()
    return raw_key, org_id


def write_parquet_base64(records: list[dict[str, Any]]) -> str:
    from apps.api_server.services.columnar_loader import records_to_arrow_table

    table = records_to_arrow_table(records)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return base64.b64encode(buf.getvalue()).decode()


def start_static_data_server(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def start_api_server(port: int, sources_dir: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    proc_env = {
        **os.environ,
        **env,
        "PYTHONPATH": str(ROOT),
        "ALGENTA_SOURCES_DIR": str(sources_dir),
    }
    if "MOJO_POOL_SIZE" not in proc_env:
        requested_workers = proc_env.get("DE_MOJO_WORKERS", "").strip()
        if requested_workers:
            proc_env["MOJO_POOL_SIZE"] = requested_workers
    log_path = sources_dir.parent / f"api_server_{port}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api_server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(ROOT),
        env=proc_env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_handle.close()
    proc.algenta_log_path = str(log_path)
    return proc


def stop_process(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "null", "none", "n/a", "na"}:
        return None
    text = text.replace(",", "")
    for prefix in ("$", "£", "€", "¥"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    try:
        return float(text)
    except ValueError:
        return None


def choose_metric_column(schema: dict[str, Any], records: list[dict[str, Any]], aggregation: str = "sum") -> str:
    if aggregation == "count":
        columns = schema.get("columns", [])
        if not columns:
            raise AssertionError("No columns available for count aggregation")
        return columns[0]["name"]
    columns = schema.get("columns", [])
    preferred = [
        col["name"]
        for col in columns
        if col.get("is_numeric") and col.get("role") not in {"identifier", "time", "category"}
    ]
    fallback = [col["name"] for col in columns if col.get("is_numeric")]
    for name in preferred + fallback:
        if any(parse_number(row.get(name)) is not None for row in records):
            return name
    raise AssertionError("No usable numeric metric column found")


def compute_expected_aggregate(records: list[dict[str, Any]], column: str, aggregation: str) -> float:
    if aggregation == "count":
        return float(len(records))
    total = 0.0
    matched = 0
    for row in records:
        value = parse_number(row.get(column))
        if value is None:
            continue
        total += value
        matched += 1
    if matched == 0:
        raise AssertionError(f"No numeric values found for {column}")
    return total


def api_headers(api_key: str, *, bearer: bool = False) -> dict[str, str]:
    if bearer:
        return {"Authorization": f"Bearer {api_key}"}
    return {"X-API-Key": api_key}


def api_request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    api_key: str | None = None,
    bearer: bool = False,
    json_body: Any | None = None,
    expected_status: int | None = None,
) -> tuple[int, Any]:
    headers: dict[str, str] = {}
    if api_key:
        headers.update(api_headers(api_key, bearer=bearer))
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    resp = client.request(method, path, headers=headers, json=json_body, timeout=90.0)
    try:
        body: Any = resp.json()
    except Exception:
        body = resp.text
    if expected_status is not None:
        assert resp.status_code == expected_status, f"{path} expected {expected_status}, got {resp.status_code}: {body}"
    return resp.status_code, body


def create_sqlite_fixture(records: list[dict[str, Any]], path: Path) -> None:
    import pandas as pd

    df = pd.DataFrame(records)
    conn = sqlite3.connect(path)
    try:
        df.to_sql("backlog", conn, if_exists="replace", index=False)
    finally:
        conn.close()


def create_postgres_fixture(
    records: list[dict[str, Any]],
    database_url: str,
    *,
    schema: str,
    table: str,
) -> str:
    import pandas as pd
    from sqlalchemy import create_engine, text

    df = pd.DataFrame(records)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        df.to_sql(table, engine, schema=schema, if_exists="replace", index=False)
    finally:
        engine.dispose()
    return f"{schema}.{table}"


def build_data_directory(tmp_dir: Path) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], str, str]:
    from apps.api_server.services.data_coercion import parse_delimited_records

    backlog_csv_path = TEST_FILES / "Backlog.csv"
    backlog_csv = backlog_csv_path.read_text(encoding="utf-8-sig")
    backlog_records_full = parse_delimited_records(backlog_csv, delimiter=",", sniff=True)
    backlog_records_subset = backlog_records_full[:200]

    data_dir = tmp_dir / "http_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backlog_csv_path, data_dir / "backlog.csv")
    (data_dir / "backlog.json").write_text(json.dumps(backlog_records_subset), encoding="utf-8")
    (data_dir / "rest_payload.json").write_text(
        json.dumps({"data": {"items": backlog_records_subset}}),
        encoding="utf-8",
    )
    (data_dir / "health.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")

    return data_dir, backlog_records_full, backlog_records_subset, backlog_csv, write_parquet_base64(backlog_records_full)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_csv_text(text: str) -> list[dict[str, Any]]:
    from apps.api_server.services.data_coercion import parse_delimited_records

    return parse_delimited_records(text, delimiter=",", sniff=True)


def fetch_public_s3_records() -> list[dict[str, Any]]:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED), region_name="us-east-1")
    body = s3.get_object(Bucket="noaa-global-hourly-pds", Key="1901/02907099999.csv")["Body"].read()
    return _parse_csv_text(body.decode("utf-8", errors="replace"))


def fetch_public_gcs_records() -> list[dict[str, Any]]:
    from google.cloud import storage

    client = storage.Client.create_anonymous_client()
    body = client.bucket("cloud-samples-data").blob("bigquery/sample-transactions/transactions.csv").download_as_bytes()
    return _parse_csv_text(body.decode("utf-8", errors="replace"))


def fetch_public_azure_records() -> list[dict[str, Any]]:
    from azure.storage.blob import BlobClient

    from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

    body = BlobClient.from_blob_url(
        "https://azureopendatastorage.blob.core.windows.net/mlsamples/diabetes/part-00000-tid-6082354649623433283-5a3d3599-0872-4a3e-a027-bddf5f6d57ca-1951182-c000.snappy.parquet"
    ).download_blob().readall()
    initialize_pyarrow_parquet_runtime()
    table = pq.read_table(io.BytesIO(body))
    return table.to_pylist()


def fetch_records_via_connector(connection: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.api_server.connectors.base import ConnectorRegistry

    connector = ConnectorRegistry.create(str(connection["type"]), connection)
    return run_async(connector.fetch_data())


def register_and_query_case(
    client: httpx.Client,
    api_key: str,
    *,
    case_name: str,
    data_source: dict[str, Any],
    expected_records: list[dict[str, Any]],
    aggregation: str = "sum",
) -> dict[str, Any]:
    _, register_body = api_request(
        client,
        "POST",
        "/v1/sources/register",
        api_key=api_key,
        json_body={"source": {"name": case_name, **data_source}},
        expected_status=200,
    )
    source_id = register_body["source_id"]

    _, source_body = api_request(
        client,
        "GET",
        f"/v1/sources/{source_id}",
        api_key=api_key,
        expected_status=200,
    )
    schema = source_body["schema"]
    metric_column = choose_metric_column(schema, expected_records, aggregation)
    expected_value = compute_expected_aggregate(expected_records, metric_column, aggregation)

    _, query_body = api_request(
        client,
        "POST",
        "/v1/query",
        api_key=api_key,
        json_body={
            "source_name": case_name,
            "metric_column": metric_column,
            "aggregation": aggregation,
        },
        expected_status=200,
    )
    result = float(query_body["result"])
    assert math.isclose(result, expected_value, rel_tol=1e-9, abs_tol=1e-6), (
        f"{case_name} {aggregation} mismatch for {metric_column}: expected {expected_value}, got {result}"
    )
    return {
        "source_id": source_id,
        "metric_column": metric_column,
        "expected_value": expected_value,
        "aggregation": aggregation,
        "schema": schema,
    }


async def run_parallel_queries(
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
    count: int,
) -> tuple[int, float]:
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    limits = httpx.Limits(
        max_connections=max(64, count * 2),
        max_keepalive_connections=max(32, count),
    )

    async def _one(client: httpx.AsyncClient) -> tuple[int, dict[str, Any]]:
        resp = await client.post("/v1/query", headers=headers, json=payload, timeout=90.0)
        return resp.status_code, resp.json()

    start = time.perf_counter()
    async with httpx.AsyncClient(base_url=base_url, limits=limits) as client:
        results_local = await asyncio.gather(*(_one(client) for _ in range(count)))
    elapsed = time.perf_counter() - start
    success_count = sum(1 for status, _ in results_local if status == 200)
    return success_count, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Real go-live connectivity runner")
    parser.add_argument("--parallel-tasks", type=int, default=8, help="Parallel warm exact queries to run")
    parser.add_argument("--api-port", type=int, default=free_port(), help="Local API port")
    parser.add_argument("--data-port", type=int, default=free_port(), help="Local data-server port")
    args = parser.parse_args()

    print("\n" + "=" * 72)
    print("  GO-LIVE CONNECTIVITY — REAL LOCAL RUN")
    print("=" * 72)

    ensure_port_open("127.0.0.1", 5432, "Postgres")
    ensure_port_open("127.0.0.1", 6379, "Redis")
    migrated = check(
        "Apply database migrations to head",
        lambda: (
            run_migrations(
                {
                    "PYTHONPATH": str(ROOT),
                    "DATABASE_URL": DEFAULT_DB_URL,
                    "DATABASE_URL_SYNC": DEFAULT_DB_URL_SYNC,
                    "REDIS_URL": DEFAULT_REDIS_URL,
                }
            ),
            True,
        )[-1],
    )
    if migrated is None:
        raise RuntimeError("Database migrations failed")

    tmp_root = Path(tempfile.mkdtemp(prefix="algenta-golive-"))
    data_server = None
    api_server = None
    client = None

    try:
        seeded = check("Seed real local API key", lambda: run_async(seed_api_key(DEFAULT_DB_URL)))
        if not seeded:
            raise RuntimeError("Failed to seed API key")
        api_key, _org_id = seeded

        sources_dir = tmp_root / "sources"
        data_dir, backlog_records_full, backlog_records_subset, backlog_csv, backlog_parquet_b64 = build_data_directory(tmp_root)
        backlog_json_str = json.dumps(backlog_records_subset)

        sqlite_path = tmp_root / "backlog.db"
        create_sqlite_fixture(backlog_records_full, sqlite_path)
        postgres_table_label = create_postgres_fixture(
            backlog_records_subset,
            DEFAULT_DB_URL_SYNC,
            schema="aa_golive",
            table="data_connect_backlog",
        )

        xlsx_path = TEST_FILES / "Grayhill - Full Price Book - 01-01-24.xlsx"
        xlsx_b64 = base64.b64encode(xlsx_path.read_bytes()).decode()
        from apps.api_server.connectors.file_connector import FileConnector

        excel_records = check(
            "Load real Excel fixture for expected results",
            lambda: run_async(FileConnector({"file_type": "excel", "content": xlsx_b64}).fetch_data()),
        )
        if not excel_records:
            raise RuntimeError("Excel fixture could not be parsed")

        data_server = check(
            "Start local real-data HTTP server",
            lambda: start_static_data_server(data_dir, args.data_port),
        )
        wait_for_http(f"http://127.0.0.1:{args.data_port}/health.json")

        env = {
            "API_ENV": "development",
            "DATABASE_URL": DEFAULT_DB_URL,
            "DATABASE_URL_SYNC": DEFAULT_DB_URL_SYNC,
            "DATABASE_READ_REPLICA_URL": DEFAULT_DB_URL,
            "REDIS_URL": DEFAULT_REDIS_URL,
            "ALGENTA_SOURCES_DIR": str(sources_dir),
        }
        api_server = check(
            "Start local API server",
            lambda: start_api_server(args.api_port, sources_dir, env),
        )
        if api_server is None:
            raise RuntimeError("API server failed to start")
        wait_for_http(
            f"http://127.0.0.1:{args.api_port}/v1/health",
            timeout=90.0,
            proc=api_server,
            log_path=getattr(api_server, "algenta_log_path", None),
        )

        client = httpx.Client(base_url=f"http://127.0.0.1:{args.api_port}")

        check(
            "Local API key works through X-API-Key header",
            lambda: api_request(client, "GET", "/v1/sources", api_key=api_key, expected_status=200),
        )
        check(
            "Local API key works through Authorization Bearer",
            lambda: api_request(client, "GET", "/v1/sources", api_key=api_key, bearer=True, expected_status=200),
        )
        check(
            "Public MCP tool listing is mounted",
            lambda: api_request(client, "GET", "/mcp/tools", expected_status=200),
        )

        case_results: dict[str, dict[str, Any]] = {}

        local_cases = [
            ("RecordsBacklog", {"records": backlog_records_subset}, backlog_records_subset),
            ("CsvBacklog", {"csv": backlog_csv}, backlog_records_full),
            ("JsonBacklog", {"json_str": backlog_json_str}, backlog_records_subset),
            ("UrlCsvBacklog", {"url": f"http://127.0.0.1:{args.data_port}/backlog.csv"}, backlog_records_full),
            ("UrlJsonBacklog", {"url": f"http://127.0.0.1:{args.data_port}/backlog.json"}, backlog_records_subset),
            ("ExcelHospitality", {"excel_b64": xlsx_b64}, excel_records),
            ("ParquetBacklog", {"parquet_b64": backlog_parquet_b64}, backlog_records_full),
            (
                "SqliteBacklog",
                {
                    "connection": {
                        "type": "sql",
                        "connection_string": f"sqlite+pysqlite:///{sqlite_path}",
                        "query": "SELECT * FROM backlog",
                    }
                },
                backlog_records_full,
            ),
            (
                "RestBacklog",
                {
                    "connection": {
                        "type": "rest_api",
                        "url": f"http://127.0.0.1:{args.data_port}/rest_payload.json",
                        "data_path": "data.items",
                    }
                },
                backlog_records_subset,
            ),
        ]

        for case_name, source_payload, expected_records in local_cases:
            case_results[case_name] = check(
                f"Register + exact-query real source: {case_name}",
                lambda case_name=case_name, source_payload=source_payload, expected_records=expected_records: register_and_query_case(
                    client,
                    api_key,
                    case_name=case_name,
                    data_source=source_payload,
                    expected_records=expected_records,
                ),
            )

        missing_required = [name for name, result in case_results.items() if result is None]
        if missing_required:
            raise RuntimeError(f"Required source cases failed: {missing_required}")

        data_flow_file = check(
            "High-level /v1/data/connect file upload",
            lambda: api_request(
                client,
                "POST",
                "/v1/data/connect",
                api_key=api_key,
                json_body={
                    "connection_type": "file_upload",
                    "dataset_name": "BacklogDataset",
                    "description": "backlog upload",
                    "csv": backlog_csv,
                },
                expected_status=200,
            ),
        )
        data_dataset_id = None
        if data_flow_file is not None:
            _, data_body = data_flow_file
            assert data_body["status"] == "ready", data_body
            data_dataset_id = data_body["dataset_id"]
            check(
                "High-level /v1/data list includes uploaded dataset",
                lambda: api_request(client, "GET", "/v1/data", api_key=api_key, expected_status=200),
            )
            dataset_info = check(
                "High-level /v1/data/{dataset_id} returns schema",
                lambda: api_request(client, "GET", f"/v1/data/{data_dataset_id}", api_key=api_key, expected_status=200),
            )
            if dataset_info is not None:
                _, dataset_body = dataset_info
                schema = dataset_body["schema"]
                metric_column = choose_metric_column(schema, backlog_records_full)
                expected_sum = compute_expected_aggregate(backlog_records_full, metric_column, "sum")
                queried = check(
                    "High-level dataset_id query executes exact spec",
                    lambda: api_request(
                        client,
                        "POST",
                        "/v1/query",
                        api_key=api_key,
                        json_body={
                            "dataset_id": data_dataset_id,
                            "metric_column": metric_column,
                            "aggregation": "sum",
                        },
                        expected_status=200,
                    ),
                )
                if queried is not None:
                    _, query_body = queried
                    actual = query_body["result"]["value"] if isinstance(query_body.get("result"), dict) else query_body["result"]
                    assert math.isclose(actual, expected_sum, rel_tol=1e-9, abs_tol=1e-9), (actual, expected_sum, query_body)

        sqlite_connect = check(
            "High-level /v1/data/connect database auto-selects or returns choices",
            lambda: api_request(
                client,
                "POST",
                "/v1/data/connect",
                api_key=api_key,
                json_body={
                    "connection_type": "database",
                    "provider": "sqlite",
                    "dataset_name": "BacklogSqliteDataset",
                    "connection_name": "Backlog SQLite",
                    "connection_config": {"path": str(sqlite_path)},
                },
                expected_status=200,
            ),
        )
        sqlite_dataset_id = None
        if sqlite_connect is not None:
            _, sqlite_body = sqlite_connect
            assert sqlite_body["status"] in {"needs_selection", "ready"}, sqlite_body
            if sqlite_body["status"] == "ready":
                sqlite_dataset_id = sqlite_body["dataset_id"]
            else:
                assert sqlite_body["choices"], sqlite_body
                sqlite_resume = check(
                    "High-level /v1/data/connect resumes after database selection",
                    lambda: api_request(
                        client,
                        "POST",
                        "/v1/data/connect",
                        api_key=api_key,
                        json_body={
                            "connection_type": "database",
                            "dataset_name": "BacklogSqliteDataset",
                            "connection_id": sqlite_body["connection_id"],
                            "selection": sqlite_body["choices"][0]["selection"],
                        },
                        expected_status=200,
                    ),
                )
                if sqlite_resume is not None:
                    _, sqlite_ready = sqlite_resume
                    assert sqlite_ready["status"] == "ready", sqlite_ready
                    sqlite_dataset_id = sqlite_ready["dataset_id"]

        postgres_connect = check(
            "High-level /v1/data/connect Postgres returns explicit dataset choices",
            lambda: api_request(
                client,
                "POST",
                "/v1/data/connect",
                api_key=api_key,
                json_body={
                    "connection_type": "database",
                    "provider": "postgres",
                    "dataset_name": "BacklogPostgresDataset",
                    "connection_name": "Backlog Postgres",
                    "connection_config": {
                        "host": "localhost",
                        "port": 5432,
                        "database": "decision_engine",
                        "user": "angel",
                        "password": "",
                    },
                },
                expected_status=200,
            ),
        )
        postgres_dataset_id = None
        if postgres_connect is not None:
            _, postgres_body = postgres_connect
            assert postgres_body["status"] == "needs_selection", postgres_body
            target_choice = next(
                (
                    choice for choice in postgres_body.get("choices", [])
                    if (choice.get("selection") or {}).get("table") == postgres_table_label
                ),
                None,
            )
            assert target_choice is not None, (postgres_table_label, postgres_body.get("choices", [])[:10])
            postgres_resume = check(
                "High-level /v1/data/connect Postgres resumes after selecting fixture table",
                lambda: api_request(
                    client,
                    "POST",
                    "/v1/data/connect",
                    api_key=api_key,
                    json_body={
                        "connection_type": "database",
                        "dataset_name": "BacklogPostgresDataset",
                        "connection_id": postgres_body["connection_id"],
                        "selection": target_choice["selection"],
                    },
                    expected_status=200,
                ),
            )
            if postgres_resume is not None:
                _, postgres_ready = postgres_resume
                assert postgres_ready["status"] == "ready", postgres_ready
                assert postgres_ready["selection"] == target_choice["selection"], postgres_ready
                postgres_dataset_id = postgres_ready["dataset_id"]
                postgres_dataset = check(
                    "High-level /v1/data/{dataset_id} returns Postgres dataset schema",
                    lambda: api_request(
                        client,
                        "GET",
                        f"/v1/data/{postgres_dataset_id}",
                        api_key=api_key,
                        expected_status=200,
                    ),
                )
                if postgres_dataset is not None:
                    _, postgres_dataset_body = postgres_dataset
                    postgres_schema = postgres_dataset_body["schema"]
                    postgres_metric_column = choose_metric_column(postgres_schema, backlog_records_subset)
                    postgres_expected_sum = compute_expected_aggregate(backlog_records_subset, postgres_metric_column, "sum")
                    postgres_query = check(
                        "High-level dataset_id query executes exact spec for Postgres dataset",
                        lambda: api_request(
                            client,
                            "POST",
                            "/v1/query",
                            api_key=api_key,
                            json_body={
                                "dataset_id": postgres_dataset_id,
                                "metric_column": postgres_metric_column,
                                "aggregation": "sum",
                            },
                            expected_status=200,
                        ),
                    )
                    if postgres_query is not None:
                        _, postgres_query_body = postgres_query
                        actual = (
                            postgres_query_body["result"]["value"]
                            if isinstance(postgres_query_body.get("result"), dict)
                            else postgres_query_body["result"]
                        )
                        assert math.isclose(actual, postgres_expected_sum, rel_tol=1e-9, abs_tol=1e-9), (
                            actual,
                            postgres_expected_sum,
                            postgres_query_body,
                        )
                check(
                    "High-level /v1/data/{dataset_id}/refresh re-registers Postgres dataset",
                    lambda: api_request(
                        client,
                        "POST",
                        f"/v1/data/{postgres_dataset_id}/refresh",
                        api_key=api_key,
                        expected_status=200,
                    ),
                )

        api_dataset = check(
            "High-level /v1/data/connect API dataset",
            lambda: api_request(
                client,
                "POST",
                "/v1/data/connect",
                api_key=api_key,
                json_body={
                    "connection_type": "api",
                    "provider": "rest",
                    "dataset_name": "BacklogRestDataset",
                    "connection_name": "Backlog REST API",
                    "connection_config": {
                        "url": f"http://127.0.0.1:{args.data_port}/rest_payload.json",
                        "data_path": "data.items",
                    },
                },
                expected_status=200,
            ),
        )
        api_dataset_id = None
        if api_dataset is not None:
            _, api_dataset_body = api_dataset
            assert api_dataset_body["status"] == "ready", api_dataset_body
            api_dataset_id = api_dataset_body["dataset_id"]
            check(
                "High-level /v1/data/{dataset_id}/refresh re-registers API dataset",
                lambda: api_request(
                    client,
                    "POST",
                    f"/v1/data/{api_dataset_id}/refresh",
                    api_key=api_key,
                    expected_status=200,
                ),
            )

        csv_source_id = case_results["CsvBacklog"]["source_id"]
        mapped = check(
            "source_id path works through /v1/map",
            lambda: api_request(
                client,
                "POST",
                "/v1/map",
                api_key=api_key,
                json_body={
                    "sources": [{"name": "CsvBacklogById", "source_id": csv_source_id}],
                    "min_confidence": 0.5,
                    "include_statistics": True,
                },
                expected_status=200,
            ),
        )
        if mapped is not None:
            _status, map_body = mapped
            assert map_body["sources_analyzed"] == 1, map_body
            assert map_body["total_fields"] > 0, map_body

        listed = check(
            "List registered sources after live registrations",
            lambda: api_request(client, "GET", "/v1/sources", api_key=api_key, expected_status=200),
        )
        if listed is not None:
            list_status, list_body = listed
            assert list_body["count"] >= len(local_cases), list_body

        graphed = check(
            "Build live source graph across registered sources",
            lambda: api_request(client, "GET", "/v1/sources/graph", api_key=api_key, expected_status=200),
        )
        if graphed is not None:
            graph_status, graph_body = graphed
            assert graph_body["total_connections"] > 0, graph_body

        connector_ids: list[str] = []

        def create_connector(name: str, connector_type: str, config: dict[str, Any]) -> str:
            _, body = api_request(
                client,
                "POST",
                "/v1/connectors",
                api_key=api_key,
                json_body={"name": name, "connector_type": connector_type, "config": config},
                expected_status=201,
            )
            connector_id = body["id"]
            connector_ids.append(connector_id)
            return connector_id

        file_connector_id = check(
            "Create local file connector",
            lambda: create_connector(
                "Backlog File",
                "file",
                {"file_type": "csv", "file_path": str(TEST_FILES / "Backlog.csv")},
            ),
        )
        if file_connector_id:
            check(
                "Test local file connector",
                lambda: api_request(
                    client,
                    "POST",
                    f"/v1/connectors/{file_connector_id}/test",
                    api_key=api_key,
                    expected_status=200,
                ),
            )

        rest_connector_id = check(
            "Create local REST connector",
            lambda: create_connector(
                "Backlog REST",
                "rest",
                {"base_url": f"http://127.0.0.1:{args.data_port}", "health_path": "/rest_payload.json"},
            ),
        )
        if rest_connector_id:
            check(
                "Test local REST connector",
                lambda: api_request(
                    client,
                    "POST",
                    f"/v1/connectors/{rest_connector_id}/test",
                    api_key=api_key,
                    expected_status=200,
                ),
            )
            check(
                "Browse local REST connector",
                lambda: api_request(
                    client,
                    "GET",
                    f"/v1/connectors/{rest_connector_id}/browse",
                    api_key=api_key,
                    expected_status=200,
                ),
            )

        postgres_connector_id = check(
            "Create local Postgres connector",
            lambda: create_connector(
                "Local Postgres",
                "postgres",
                {
                    "host": "localhost",
                    "port": 5432,
                    "database": "decision_engine",
                    "user": "angel",
                    "password": "",
                },
            ),
        )
        if postgres_connector_id:
            check(
                "Test local Postgres connector",
                lambda: api_request(
                    client,
                    "POST",
                    f"/v1/connectors/{postgres_connector_id}/test",
                    api_key=api_key,
                    expected_status=200,
                ),
            )
            check(
                "Browse local Postgres connector",
                lambda: api_request(
                    client,
                    "GET",
                    f"/v1/connectors/{postgres_connector_id}/browse",
                    api_key=api_key,
                    expected_status=200,
                ),
            )

        use_default_public_s3 = not any(
            os.environ.get(name)
            for name in [
                "DE_TEST_S3_BUCKET",
                "DE_TEST_S3_KEY",
                "DE_TEST_S3_ACCESS_KEY_ID",
                "DE_TEST_S3_SECRET_ACCESS_KEY",
                "DE_TEST_S3_ENDPOINT_URL",
            ]
        )
        use_default_public_gcs = not any(
            os.environ.get(name)
            for name in [
                "DE_TEST_GCS_BUCKET",
                "DE_TEST_GCS_BLOB",
                "DE_TEST_GCS_CREDENTIALS",
                "DE_TEST_GCS_PROJECT_ID",
            ]
        )
        use_default_public_azure = not any(
            os.environ.get(name)
            for name in [
                "DE_TEST_AZURE_CONNECTION_STRING",
                "DE_TEST_AZURE_ACCOUNT_URL",
                "DE_TEST_AZURE_CONTAINER",
                "DE_TEST_AZURE_BLOB",
                "DE_TEST_AZURE_BLOB_URL",
            ]
        )

        optional_source_checks = [
            (
                "Live S3 source registration",
                {
                    "type": "s3",
                    "bucket": os.environ.get("DE_TEST_S3_BUCKET", "noaa-global-hourly-pds"),
                    "key": os.environ.get("DE_TEST_S3_KEY", "1901/02907099999.csv"),
                    "region": os.environ.get("DE_TEST_S3_REGION", "us-east-1"),
                    "aws_access_key_id": os.environ.get("DE_TEST_S3_ACCESS_KEY_ID", ""),
                    "aws_secret_access_key": os.environ.get("DE_TEST_S3_SECRET_ACCESS_KEY", ""),
                    "endpoint_url": os.environ.get("DE_TEST_S3_ENDPOINT_URL", ""),
                    "anonymous": _env_bool("DE_TEST_S3_ANONYMOUS", use_default_public_s3),
                    "file_type": os.environ.get("DE_TEST_S3_FILE_TYPE", "csv"),
                },
                fetch_public_s3_records if use_default_public_s3 else None,
            ),
            (
                "Live GCS source registration",
                {
                    "type": "gcs",
                    "bucket": os.environ.get("DE_TEST_GCS_BUCKET", "cloud-samples-data"),
                    "blob": os.environ.get("DE_TEST_GCS_BLOB", "bigquery/sample-transactions/transactions.csv"),
                    "credentials": os.environ.get("DE_TEST_GCS_CREDENTIALS", ""),
                    "project_id": os.environ.get("DE_TEST_GCS_PROJECT_ID", ""),
                    "anonymous": _env_bool("DE_TEST_GCS_ANONYMOUS", use_default_public_gcs),
                    "file_type": os.environ.get("DE_TEST_GCS_FILE_TYPE", "csv"),
                },
                fetch_public_gcs_records if use_default_public_gcs else None,
            ),
            (
                "Live Azure Blob source registration",
                {
                    "type": "azure_blob",
                    "connection_string": os.environ.get("DE_TEST_AZURE_CONNECTION_STRING", ""),
                    "account_url": os.environ.get("DE_TEST_AZURE_ACCOUNT_URL", "https://azureopendatastorage.blob.core.windows.net"),
                    "container": os.environ.get("DE_TEST_AZURE_CONTAINER", "mlsamples"),
                    "blob": os.environ.get(
                        "DE_TEST_AZURE_BLOB",
                        "diabetes/part-00000-tid-6082354649623433283-5a3d3599-0872-4a3e-a027-bddf5f6d57ca-1951182-c000.snappy.parquet",
                    ),
                    "blob_url": os.environ.get(
                        "DE_TEST_AZURE_BLOB_URL",
                        "https://azureopendatastorage.blob.core.windows.net/mlsamples/diabetes/part-00000-tid-6082354649623433283-5a3d3599-0872-4a3e-a027-bddf5f6d57ca-1951182-c000.snappy.parquet",
                    ),
                    "anonymous": _env_bool("DE_TEST_AZURE_ANONYMOUS", use_default_public_azure),
                    "file_type": os.environ.get("DE_TEST_AZURE_FILE_TYPE", "parquet"),
                },
                fetch_public_azure_records if use_default_public_azure else None,
            ),
        ]
        for label, connection, expected_loader in optional_source_checks:
            if connection["type"] == "s3" and not (connection.get("bucket") and connection.get("key")):
                skip(label, "live credentials/config not provided")
                continue
            if connection["type"] == "gcs" and not (connection.get("bucket") and connection.get("blob")):
                skip(label, "live credentials/config not provided")
                continue
            if connection["type"] == "azure_blob" and not (
                connection.get("blob_url")
                or (
                    (connection.get("connection_string") or connection.get("account_url"))
                    and connection.get("container")
                    and connection.get("blob")
                )
            ):
                skip(label, "live credentials/config not provided")
                continue
            expected_records = check(
                f"{label} fetch expected records",
                expected_loader or (lambda connection=connection: fetch_records_via_connector(connection)),
            )
            if not expected_records:
                continue
            check(
                label,
                lambda label=label, connection=connection, expected_records=expected_records: register_and_query_case(
                    client,
                    api_key,
                    case_name=label.replace(" ", ""),
                    data_source={"connection": connection},
                    expected_records=expected_records,
                ),
            )

        for case in THIRD_PARTY_PUBLIC_CASES:
            expected_records = check(
                f"{case.label} fetch expected records",
                case.load_expected_records,
            )
            if not expected_records:
                continue
            check(
                case.label,
                lambda case=case, expected_records=expected_records: register_and_query_case(
                    client,
                    api_key,
                    case_name=case.case_id,
                    data_source={"connection": case.build_connection()},
                    expected_records=expected_records,
                    aggregation=case.aggregation,
                ),
            )

        optional_connector_checks = [
            (
                "Snowflake connector /test",
                "snowflake",
                {
                    "account": os.environ.get("DE_TEST_SNOWFLAKE_ACCOUNT", ""),
                    "user": os.environ.get("DE_TEST_SNOWFLAKE_USER", ""),
                    "password": os.environ.get("DE_TEST_SNOWFLAKE_PASSWORD", ""),
                    "warehouse": os.environ.get("DE_TEST_SNOWFLAKE_WAREHOUSE", ""),
                    "database": os.environ.get("DE_TEST_SNOWFLAKE_DATABASE", ""),
                    "schema": os.environ.get("DE_TEST_SNOWFLAKE_SCHEMA", ""),
                },
            ),
            (
                "BigQuery connector /test",
                "bigquery",
                {
                    "project_id": os.environ.get("DE_TEST_BIGQUERY_PROJECT_ID", ""),
                    "service_account_json": os.environ.get("DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON", ""),
                },
            ),
        ]
        for label, connector_type, config in optional_connector_checks:
            if not any(config.values()):
                skip(label, "live credentials/config not provided")
                continue
            connector_id = check(label.replace("/test", "create"), lambda label=label, connector_type=connector_type, config=config: create_connector(label, connector_type, config))
            if connector_id:
                check(
                    label,
                    lambda connector_id=connector_id: api_request(
                        client,
                        "POST",
                        f"/v1/connectors/{connector_id}/test",
                        api_key=api_key,
                        expected_status=200,
                    ),
                )

        warm_case = case_results["CsvBacklog"]
        warm_payload = {
            "source_name": "CsvBacklog",
            "metric_column": warm_case["metric_column"],
            "aggregation": "sum",
        }
        check(
            "Warm exact query before fanout",
            lambda: api_request(client, "POST", "/v1/query", api_key=api_key, json_body=warm_payload, expected_status=200),
        )
        parallel_result = check(
            f"Parallel warm exact queries x{args.parallel_tasks}",
            lambda: run_async(
                run_parallel_queries(
                    f"http://127.0.0.1:{args.api_port}",
                    api_key,
                    warm_payload,
                    args.parallel_tasks,
                )
            ),
        )
        if parallel_result is not None:
            success_count, elapsed = parallel_result
            assert success_count == args.parallel_tasks, (success_count, elapsed)
            print(f"    parallel total={elapsed:.3f}s  avg={(elapsed / args.parallel_tasks):.3f}s/query")

        delete_target = case_results["JsonBacklog"]["source_id"]
        check(
            "Delete one registered source",
            lambda: api_request(client, "DELETE", f"/v1/sources/{delete_target}", api_key=api_key, expected_status=200),
        )
        check(
            "Deleted source is gone from registry",
            lambda: api_request(client, "GET", f"/v1/sources/{delete_target}", api_key=api_key, expected_status=404),
        )

        for dataset_id in [dataset_id for dataset_id in [data_dataset_id, sqlite_dataset_id, api_dataset_id] if dataset_id]:
            check(
                f"Disconnect high-level dataset {dataset_id[:8]}",
                lambda dataset_id=dataset_id: api_request(
                    client,
                    "DELETE",
                    f"/v1/data/{dataset_id}",
                    api_key=api_key,
                    expected_status=200,
                ),
            )

        for connector_id in connector_ids:
            check(
                f"Delete connector {connector_id[:8]}",
                lambda connector_id=connector_id: api_request(
                    client,
                    "DELETE",
                    f"/v1/connectors/{connector_id}",
                    api_key=api_key,
                    expected_status=204,
                ),
            )

    finally:
        if client is not None:
            client.close()
        stop_process(api_server)
        if api_server is not None:
            output = ""
            log_path = getattr(api_server, "algenta_log_path", None)
            if log_path:
                output = Path(log_path).read_text(encoding="utf-8", errors="replace")
            if output and any(icon == FAIL for icon, _, _ in results):
                print("\n── API server output (tail) ──")
                lines = output.splitlines()
                for line in lines[-40:]:
                    print(f"  │ {line}")
        if data_server is not None:
            data_server.shutdown()
            data_server.server_close()
        shutil.rmtree(tmp_root, ignore_errors=True)

    passed = sum(1 for icon, _, _ in results if icon == PASS)
    failed = sum(1 for icon, _, _ in results if icon == FAIL)
    skipped = sum(1 for icon, _, _ in results if icon == SKIP)

    print("\n" + "=" * 72)
    print(f"Passed:  {passed}")
    print(f"Failed:  {failed}")
    print(f"Skipped: {skipped}")
    if timings:
        slowest = sorted(timings, key=lambda item: item[1], reverse=True)[:10]
        print("Slowest:")
        for name, elapsed in slowest:
            print(f"  - {name}: {elapsed:.3f}s")
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
