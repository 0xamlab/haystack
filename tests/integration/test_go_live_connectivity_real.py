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
  - tier 1 public third-party REST example connectors by default
  - tier 2 auth-required third-party REST examples when fixture credentials are set
  - custom s3 / gcs / azure_blob through source registration when env vars are set
  - tier 3 Redis / ClickHouse / Snowflake / BigQuery live validation when customer credentials are set

Run:
  python3 tests/integration/test_go_live_connectivity_real.py

Optional:
  python3 tests/integration/test_go_live_connectivity_real.py --parallel-tasks 16
"""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import ipaddress
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
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

os.environ.setdefault("ARROW_USER_SIMD_LEVEL", "NONE")

import httpx
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.go_live_secret_resolver import populate_go_live_test_env_from_keys_txt

populate_go_live_test_env_from_keys_txt()

from apps.api_server.services.connectors import (
    classify_connector_failure,
    test_connector_real_detailed,
)
from tests.go_live_behavior_contract import (
    P0_METRIC_BUDGETS,
    P1_METRIC_BUDGETS,
    build_distribution_sketch,
    distribution_sketch_within_tolerance,
    ensure_no_identity_duplicates,
    schema_fingerprint,
    strict_sample_hash,
    summarize_metric_series,
    within_row_count_tolerance,
)
from tests.integration.live_integration_artifacts import write_live_integration_summary

TEST_FILES = ROOT / "test_files"
DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://angel:@localhost:5432/decision_engine"
)
DEFAULT_DB_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC", "postgresql://angel:@localhost:5432/decision_engine"
)
DEFAULT_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
SUITE_NAME = "go_live_connectivity_real"
results: list[tuple[str, str, str]] = []
timings: list[tuple[str, float]] = []
behavior_case_summaries: list[dict[str, Any]] = []
behavior_p1_failures: list[str] = []
VALIDATION_TIERS = (
    "public_no_auth",
    "credentialed_example",
    "customer_credentials_required",
)


class ValidationSkipError(RuntimeError):
    """Raised when an external live validation case is blocked by environment policy."""


class LocalRedisBootstrapError(RuntimeError):
    """Raised when the local Redis dev bootstrap cannot be started safely."""


class LocalRedisBootstrap:
    def __init__(
        self,
        *,
        process: subprocess.Popen[Any],
        data_dir: Path,
        log_path: Path,
        host: str,
        port: int,
    ) -> None:
        self.process = process
        self.data_dir = data_dir
        self.log_path = log_path
        self.host = host
        self.port = port

    def stop(self) -> None:
        try:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        finally:
            shutil.rmtree(self.data_dir, ignore_errors=True)


def _emit(message: str = "") -> None:
    print(message, flush=True)


def check(name: str, fn) -> Any:
    t0 = time.perf_counter()
    _emit(f"  ... {name}")
    try:
        out = fn()
        elapsed = time.perf_counter() - t0
        results.append((PASS, name, ""))
        timings.append((name, elapsed))
        _emit(f"  {PASS} {name} ({elapsed:.3f}s)")
        return out
    except AssertionError as exc:
        elapsed = time.perf_counter() - t0
        results.append((FAIL, name, str(exc)))
        timings.append((name, elapsed))
        _emit(f"  {FAIL} {name} ({elapsed:.3f}s): {exc}")
        return None
    except ValidationSkipError as exc:
        elapsed = time.perf_counter() - t0
        results.append((SKIP, name, str(exc)))
        timings.append((name, elapsed))
        _emit(f"  {SKIP} {name} ({elapsed:.3f}s): {exc}")
        return None
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        results.append((FAIL, name, f"{type(exc).__name__}: {exc}"))
        timings.append((name, elapsed))
        _emit(f"  {FAIL} {name} ({elapsed:.3f}s): {type(exc).__name__}: {exc}")
        return None


def skip(name: str, reason: str) -> None:
    results.append((SKIP, name, reason))
    _emit(f"  {SKIP} {name}: {reason}")


def parse_selected_tiers(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    selected = tuple(tier.strip() for tier in raw.split(",") if tier.strip())
    unknown = sorted(set(selected) - set(VALIDATION_TIERS))
    if unknown:
        raise ValueError(
            f"Unknown validation tiers: {', '.join(unknown)}. "
            f"Expected one of: {', '.join(VALIDATION_TIERS)}"
        )
    return selected or None


def parse_selected_connectors(raw: str | None, cases) -> tuple[str, ...] | None:  # type: ignore[no-untyped-def]
    if raw is None:
        return None
    selected = tuple(connector.strip() for connector in raw.split(",") if connector.strip())
    valid_connectors = {str(case.connector_type) for case in cases}
    unknown = sorted(set(selected) - valid_connectors)
    if unknown:
        raise ValueError(
            f"Unknown connector types: {', '.join(unknown)}. "
            f"Expected one of: {', '.join(sorted(valid_connectors))}"
        )
    return selected or None


def filter_validation_cases_by_tiers(cases, selected_tiers: tuple[str, ...] | None):  # type: ignore[no-untyped-def]
    if selected_tiers is None:
        return tuple(cases)
    return tuple(case for case in cases if case.tier in selected_tiers)


def filter_validation_cases_by_connectors(
    cases,
    selected_connectors: tuple[str, ...] | None,
):  # type: ignore[no-untyped-def]
    if selected_connectors is None:
        return tuple(cases)
    return tuple(case for case in cases if str(case.connector_type) in selected_connectors)


def select_external_validation_cases(
    cases,
    *,
    selected_tiers: tuple[str, ...] | None,
    selected_connectors: tuple[str, ...] | None,
    skip_external_validation: bool,
):  # type: ignore[no-untyped-def]
    if skip_external_validation:
        return ()
    return filter_validation_cases_by_connectors(
        filter_validation_cases_by_tiers(cases, selected_tiers),
        selected_connectors,
    )


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
            f"Alembic upgrade failed:\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
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
                raise RuntimeError(f"Timed out waiting for {url}: {detail}")
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


def _parse_redis_endpoint(redis_url: str) -> tuple[str, int]:
    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise LocalRedisBootstrapError(
            f"Unsupported Redis URL scheme for go-live bootstrap: {redis_url}"
        )
    host = parsed.hostname
    if not host:
        raise LocalRedisBootstrapError(f"Redis URL must include a host: {redis_url}")
    return host, parsed.port or 6379


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _wait_for_port_open(
    host: str,
    port: int,
    *,
    label: str,
    timeout: float,
    proc: subprocess.Popen[Any] | None = None,
    log_path: str | Path | None = None,
) -> None:
    start = time.monotonic()
    last_error = ""
    while time.monotonic() - start < timeout:
        if proc is not None:
            exit_code = proc.poll()
            if exit_code is not None:
                log_tail = _read_log_tail(log_path)
                detail = f"{label} bootstrap exited with code {exit_code}"
                if log_tail:
                    detail += f"\n--- redis log tail ---\n{log_tail}"
                raise LocalRedisBootstrapError(detail)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                sock.connect((host, port))
            return
        except OSError as exc:
            last_error = str(exc)
            time.sleep(0.2)
    detail = f"Timed out waiting for {label} at {host}:{port}"
    if last_error:
        detail += f": {last_error}"
    log_tail = _read_log_tail(log_path)
    if log_tail:
        detail += f"\n--- redis log tail ---\n{log_tail}"
    raise LocalRedisBootstrapError(detail)


def ensure_local_redis_available(redis_url: str, *, label: str = "Redis") -> LocalRedisBootstrap | None:
    host, port = _parse_redis_endpoint(redis_url)
    try:
        ensure_port_open(host, port, label)
        return None
    except OSError as exc:
        if not _is_loopback_host(host):
            raise LocalRedisBootstrapError(
                f"{label} is unreachable at {host}:{port} and automatic bootstrap is "
                "allowed only for loopback Redis URLs"
            ) from exc

    redis_server = shutil.which("redis-server")
    if redis_server is None:
        raise LocalRedisBootstrapError(
            f"{label} is unreachable at {host}:{port} and redis-server is not installed"
        )

    data_dir = Path(tempfile.mkdtemp(prefix="algenta-golive-redis-"))
    log_path = data_dir / "redis.log"
    log_file = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [
                redis_server,
                "--save",
                "",
                "--appendonly",
                "no",
                "--bind",
                host,
                "--port",
                str(port),
                "--dir",
                str(data_dir),
                "--loglevel",
                "warning",
            ],
            cwd=str(ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception:
        log_file.close()
        shutil.rmtree(data_dir, ignore_errors=True)
        raise
    finally:
        log_file.close()

    try:
        _wait_for_port_open(
            host,
            port,
            label=label,
            timeout=15.0,
            proc=process,
            log_path=log_path,
        )
    except Exception:
        try:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        except Exception:
            if process.poll() is None:
                process.kill()
        shutil.rmtree(data_dir, ignore_errors=True)
        raise

    print(f"  {PASS} bootstrapped local {label} at {host}:{port}")
    return LocalRedisBootstrap(
        process=process,
        data_dir=data_dir,
        log_path=log_path,
        host=host,
        port=port,
    )


async def seed_api_key(database_url: str) -> tuple[str, str]:
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models import (
        APIKey,
        Deployment,
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

    async with session_factory() as session:
        slug_suffix = uuid.uuid4().hex[:12]
        org = Organization(
            name="Go Live Connectivity",
            slug=f"go-live-connectivity-{slug_suffix}",
            plan=OrgPlan.DEVELOPER,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.flush()

        user = User(
            org_id=org.id,
            email=f"golive+{slug_suffix}@example.com",
            password_hash="local-go-live",
            name="Go Live",
            role=UserRole.OWNER,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        session.add(user)
        await session.flush()

        await session.execute(delete(Deployment).where(Deployment.org_id == org.id))

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


def materialize_bigquery_service_account_json(tmp_root: Path) -> Path | None:
    raw = str(os.environ.get("DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON", "")).strip()
    if not raw:
        return None
    path = tmp_root / "bigquery_service_account.json"
    path.write_text(json.dumps(json.loads(raw)), encoding="utf-8")
    return path


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
            text = text[len(prefix) :]
    try:
        return float(text)
    except ValueError:
        return None


def choose_metric_column(
    schema: dict[str, Any], records: list[dict[str, Any]], aggregation: str = "sum"
) -> str:
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


def compute_expected_aggregate(
    records: list[dict[str, Any]], column: str, aggregation: str
) -> float:
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
        assert resp.status_code == expected_status, (
            f"{path} expected {expected_status}, got {resp.status_code}: {body}"
        )
    return resp.status_code, body


def timed_api_request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    api_key: str | None = None,
    bearer: bool = False,
    json_body: Any | None = None,
    expected_status: int | None = None,
) -> tuple[tuple[int, Any], float]:
    started = time.perf_counter()
    response = api_request(
        client,
        method,
        path,
        api_key=api_key,
        bearer=bearer,
        json_body=json_body,
        expected_status=expected_status,
    )
    return response, (time.perf_counter() - started) * 1000


def _timed_call(fn) -> tuple[Any, float]:
    started = time.perf_counter()
    value = fn()
    return value, (time.perf_counter() - started) * 1000


def _schema_columns_from_records(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    from apps.api_server.services.columnar_loader import records_to_arrow_table

    table = records_to_arrow_table(records)
    return [
        {
            "name": str(field.name),
            "physical_type": str(field.type),
        }
        for field in table.schema
    ]


def _schema_columns_from_connection(
    case,  # type: ignore[no-untyped-def]
    connection: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if case.connector_type == "s3":
        from apps.api_server.connectors.cloud_connector import S3Connector

        table = run_async(S3Connector(connection).fetch_table())
    elif case.connector_type == "gcs":
        from apps.api_server.connectors.cloud_connector import GCSConnector

        table = run_async(GCSConnector(connection).fetch_table())
    elif case.connector_type == "azure_blob":
        from apps.api_server.connectors.cloud_connector import AzureBlobConnector

        table = run_async(AzureBlobConnector(connection).fetch_table())
    elif case.connector_type == "rest_api":
        from apps.api_server.connectors.rest_connector import RESTConnector

        table = run_async(RESTConnector(connection).fetch_table())
    else:
        table = None

    if table is None:
        return _schema_columns_from_records(records)
    return [
        {
            "name": str(field.name),
            "physical_type": str(field.type),
        }
        for field in table.schema
    ]


def _schema_column_role(schema: dict[str, Any], column_name: str) -> str:
    for column in schema.get("columns", []):
        if str(column.get("name", "")) == column_name:
            return str(column.get("role", "") or "metric")
    return "metric"


def _assert_registered_schema_has_physical_types(schema: dict[str, Any], case_name: str) -> None:
    columns = schema.get("columns", [])
    assert columns, f"{case_name} registered schema has no columns"
    missing = [
        str(column.get("name", "") or "<unknown>")
        for column in columns
        if not str(column.get("physical_type", "") or "").strip()
    ]
    assert not missing, f"{case_name} schema missing physical_type for columns: {missing}"


def _negative_connection_for_case(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    connection = case.build_runtime_connection()
    custom_factory = getattr(case, "negative_connection_factory", None)
    if custom_factory is not None:
        return custom_factory(connection)
    probe = getattr(case, "negative_probe", "none")
    if probe == "invalid_path":
        if case.connector_type == "s3":
            connection["key"] = "__algenta_missing__/missing-object.csv"
        elif case.connector_type == "gcs":
            connection["blob"] = "__algenta_missing__/missing-object.csv"
        elif case.connector_type == "azure_blob":
            connection["blob"] = "__algenta_missing__/missing-object.csv"
            blob_url = str(connection.get("blob_url", "") or "").strip()
            if blob_url:
                connection["blob_url"] = blob_url.rstrip("/") + ".algenta-missing"
        elif case.connector_type == "rest_api":
            connection["url"] = (
                str(connection.get("url", "") or "").rstrip("/") + "/__algenta_missing__"
            )
        return connection
    if probe == "invalid_identifier":
        connection["url"] = (
            str(connection.get("url", "") or "").rstrip("/") + "/__algenta_invalid__"
        )
        return connection
    if probe == "invalid_auth":
        if case.connector_type == "rest_api":
            headers = dict(connection.get("headers", {}) or {})
            params = dict(connection.get("params", {}) or {})
            if "Authorization" in headers:
                headers["Authorization"] = "Bearer algenta-invalid-token"
            elif "api_key" in params:
                params["api_key"] = "algenta-invalid-token"
            else:
                headers["Authorization"] = "Bearer algenta-invalid-token"
            connection["headers"] = headers
            connection["params"] = params
            return connection
    raise AssertionError(f"Unsupported negative connection probe {probe!r} for {case.case_id}")


def _negative_connector_config_for_case(case) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    config = case.build_connector_config()
    probe = getattr(case, "negative_probe", "none")
    if probe != "invalid_auth":
        raise AssertionError(f"Unsupported negative connector probe {probe!r} for {case.case_id}")
    if case.connector_type == "redis":
        url = str(config.get("url", "") or config.get("connection_string", "") or "").strip()
        if not url:
            raise AssertionError(
                f"Redis connector negative auth probe requires url for {case.case_id}"
            )
        invalid_url = _with_invalid_redis_password(url)
        if invalid_url is None:
            return None
        config["url"] = invalid_url
        return config
    if case.connector_type == "clickhouse":
        config["password"] = "algenta-invalid-password"
        return config
    if case.connector_type == "elasticsearch":
        config["api_key"] = "algenta-invalid-key"
        return config
    if case.connector_type == "neo4j":
        config["password"] = "algenta-invalid-password"
        return config
    if case.connector_type == "snowflake":
        config["password"] = "algenta-invalid-password"
        return config
    if case.connector_type == "bigquery":
        config["service_account_json"] = json.dumps(
            {"type": "service_account", "project_id": "invalid"}
        )
        return config
    raise AssertionError(f"Unsupported connector negative auth probe for {case.connector_type}")


def _with_invalid_redis_password(connection_url: str) -> str | None:
    parsed = urlparse(connection_url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise AssertionError(
            f"Unsupported Redis DSN scheme for negative auth probe: {connection_url}"
        )
    if not parsed.hostname:
        raise AssertionError(f"Redis DSN requires host for negative auth probe: {connection_url}")
    if parsed.password is None and parsed.username is None:
        return None

    username = parsed.username or ""
    password = "algenta-invalid-password"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    auth = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    netloc = f"{auth}{host}"
    if parsed.port is not None:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def _fetch_budget_key(case, connection: dict[str, Any]) -> str:  # type: ignore[no-untyped-def]
    if case.connector_type == "rest_api":
        pagination = connection.get("pagination")
        if isinstance(pagination, dict) and pagination:
            return "fetch_ms.paginated_rest"
        return "fetch_ms.rest_single_dataset"
    if case.connector_type == "clickhouse":
        return "fetch_ms.clickhouse_cloud_fixture"
    if case.connector_type in {"snowflake", "bigquery"}:
        return "fetch_ms.warehouse_fixture"
    return "fetch_ms.object_single"


def _failure_response_budget_key(case) -> str:  # type: ignore[no-untyped-def]
    if case.connector_type == "neo4j":
        return "failure_response_ms.neo4j_connector_test"
    return "failure_response_ms"


def _external_policy_block_reason(case, message: str) -> str | None:  # type: ignore[no-untyped-def]
    normalized = message.strip().lower()
    if case.tier != "customer_credentials_required":
        return None
    if case.connector_type == "snowflake" and "network policy is required" in normalized:
        return (
            "Snowflake live validation blocked by account network policy; "
            "skipping external customer-credential case."
        )
    return None


def _append_case_p1_failure(summary: dict[str, Any], message: str) -> None:
    summary.setdefault("p1_failures", []).append(message)
    behavior_p1_failures.append(message)


def _run_rate_limit_probe(case) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    requests = int(getattr(case, "rate_limit_probe_requests", 0) or 0)
    if requests <= 0:
        return None
    outcomes: list[dict[str, Any]] = []
    for _ in range(requests):
        started = time.perf_counter()
        try:
            case.load_runtime_records_for_connection(case.build_runtime_connection())
            outcomes.append(
                {"status": "ok", "latency_ms": round((time.perf_counter() - started) * 1000, 3)}
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            error_type, recoverable = classify_connector_failure(message=str(exc), exception=exc)
            if error_type != "rate_limit":
                raise AssertionError(
                    f"{case.case_id} rate-limit probe failed with non-rate-limit error: "
                    f"{error_type}: {exc}"
                ) from exc
            outcomes.append(
                {
                    "status": "error",
                    "error_type": error_type,
                    "recoverable": recoverable,
                    "latency_ms": latency_ms,
                }
            )
    return {"requests": requests, "outcomes": outcomes}


def _run_negative_fetch_probe(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    negative_connection = _negative_connection_for_case(case)
    started = time.perf_counter()
    try:
        records = case.load_runtime_records_for_connection(negative_connection)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        error_type, recoverable = classify_connector_failure(message=str(exc), exception=exc)
        return {
            "error_type": error_type,
            "recoverable": recoverable,
            "failure_response_ms": latency_ms,
            "message": str(exc),
        }
    raise AssertionError(
        f"{case.case_id} negative probe unexpectedly succeeded with {len(records)} records"
    )


def _run_negative_connector_probe(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    if case.connector_type in {"snowflake", "bigquery", "clickhouse", "elasticsearch"}:
        config = _negative_connector_config_for_case(case)
    else:
        config = _negative_connection_for_case(case)
    outcome = run_async(test_connector_real_detailed(case.connector_type, config))
    assert outcome.success is False, outcome
    return {
        "error_type": outcome.error_type,
        "recoverable": outcome.recoverable,
        "failure_response_ms": float(outcome.latency_ms or 0.0),
        "message": outcome.message,
    }


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


def build_data_directory(
    tmp_dir: Path,
) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], str, str]:
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

    return (
        data_dir,
        backlog_records_full,
        backlog_records_subset,
        backlog_csv,
        write_parquet_base64(backlog_records_full),
    )


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


def _behavior_negative_expectations(case) -> set[str]:  # type: ignore[no-untyped-def]
    probe = getattr(case, "negative_probe", "none")
    if probe == "invalid_auth":
        return {"auth", "permission", "invalid_config"}
    if probe == "invalid_path":
        return {"not_found"}
    if probe == "invalid_identifier":
        return {"invalid_identifier", "not_found"}
    return set()


def _warm_behavior_connection(case, connection: dict[str, Any]) -> None:  # type: ignore[no-untyped-def]
    # Warm-path budgets should exclude one-time external DNS/TLS and parser cold-start cost.
    records = case.load_runtime_records_for_connection(connection)
    assert isinstance(records, list), f"{case.case_id} warmup did not return a record list"


def _server_connector_type_for_case(case) -> str:  # type: ignore[no-untyped-def]
    return {"azure_blob": "azure"}.get(str(case.connector_type), str(case.connector_type))


def _warm_server_connector_case(
    client: httpx.Client,
    api_key: str,
    *,
    case,
    connection: dict[str, Any],
    create_connector,
) -> None:
    connector_id = create_connector(
        f"{case.label} warmup",
        _server_connector_type_for_case(case),
        connection,
    )
    _, body = api_request(
        client,
        "POST",
        f"/v1/connectors/{connector_id}/test",
        api_key=api_key,
        expected_status=200,
    )
    assert body["success"] is True, body


def _warm_server_registration_case(
    client: httpx.Client,
    api_key: str,
    *,
    case,
    connection: dict[str, Any],
) -> None:
    _, register_body = api_request(
        client,
        "POST",
        "/v1/sources/register",
        api_key=api_key,
        json_body={"source": {"name": f"{case.case_id}__warmup", "connection": connection}},
        expected_status=200,
    )
    warm_source_id = str(register_body["source_id"])
    api_request(
        client,
        "DELETE",
        f"/v1/sources/{warm_source_id}",
        api_key=api_key,
        expected_status=200,
    )


def run_behavior_validation_case(
    client: httpx.Client,
    api_key: str,
    *,
    case,
    create_connector,
) -> dict[str, Any]:
    effective_validation_mode = case.effective_validation_mode()
    effective_behavior_mode = case.effective_behavior_mode()
    summary: dict[str, Any] = {
        "case_id": case.case_id,
        "label": case.label,
        "tier": case.tier,
        "connector_type": case.connector_type,
        "validation_mode": effective_validation_mode,
        "behavior_mode": effective_behavior_mode,
        "metrics": {},
        "p1_failures": [],
    }

    if effective_validation_mode == "connector_test_only":
        connector_id = create_connector(
            case.label, case.connector_type, case.build_connector_config()
        )
        (_, positive_body), positive_api_ms = timed_api_request(
            client,
            "POST",
            f"/v1/connectors/{connector_id}/test",
            api_key=api_key,
            expected_status=200,
        )
        if positive_body.get("success") is not True:
            error_type = str(positive_body.get("error_type") or "").strip()
            message = str(positive_body.get("message") or positive_body)
            skip_reason = _external_policy_block_reason(case, message)
            if skip_reason:
                raise ValidationSkipError(skip_reason)
            recoverable = positive_body.get("recoverable")
            detail = (
                f"{error_type}: {message}" if error_type and error_type != "unknown" else message
            )
            if recoverable is not None:
                detail += f" (recoverable={bool(recoverable)})"
            raise AssertionError(detail)
        assert positive_body.get("status") == "live", positive_body
        assert positive_body.get("error_type") is None, positive_body
        summary["metrics"] = {
            "connector_test_ms": round(positive_api_ms, 3),
        }
        if case.negative_probe != "none":
            negative_config = _negative_connector_config_for_case(case)
            if negative_config is not None:
                negative_connector_id = create_connector(
                    case.label + " negative",
                    case.connector_type,
                    negative_config,
                )
                (_, negative_body), negative_api_ms = timed_api_request(
                    client,
                    "POST",
                    f"/v1/connectors/{negative_connector_id}/test",
                    api_key=api_key,
                    expected_status=200,
                )
                assert negative_body["success"] is False, negative_body
                error_type = str(negative_body.get("error_type") or "")
                assert error_type, negative_body
                assert error_type != "unknown", negative_body
                assert error_type in _behavior_negative_expectations(case), negative_body
                summary["negative_probe"] = {
                    "error_type": error_type,
                    "recoverable": bool(negative_body.get("recoverable")),
                    "failure_response_ms": round(negative_api_ms, 3),
                    "failure_response_budget_key": _failure_response_budget_key(case),
                }
        behavior_case_summaries.append(summary)
        return summary

    connection = case.build_runtime_connection()
    try:
        _warm_behavior_connection(case, connection)
        _warm_server_connector_case(
            client,
            api_key,
            case=case,
            connection=connection,
            create_connector=create_connector,
        )
    except Exception as exc:
        skip_reason = _external_policy_block_reason(case, str(exc))
        if skip_reason:
            raise ValidationSkipError(skip_reason) from exc
        raise
    try:
        first_records, fetch_first_ms = _timed_call(
            lambda: case.load_runtime_records_for_connection(connection)
        )
        second_records, fetch_second_ms = _timed_call(
            lambda: case.load_runtime_records_for_connection(connection)
        )
    except Exception as exc:
        skip_reason = _external_policy_block_reason(case, str(exc))
        if skip_reason:
            raise ValidationSkipError(skip_reason) from exc
        raise
    assert first_records, f"{case.case_id} first live fetch returned zero records"
    assert second_records, f"{case.case_id} second live fetch returned zero records"

    first_schema_columns = _schema_columns_from_connection(case, connection, first_records)
    second_schema_columns = _schema_columns_from_connection(case, connection, second_records)
    first_fingerprint = schema_fingerprint(first_schema_columns)
    second_fingerprint = schema_fingerprint(second_schema_columns)
    assert first_fingerprint == second_fingerprint, (
        f"{case.case_id} schema fingerprint drifted between live fetches"
    )

    row_count_ok, row_count_message = within_row_count_tolerance(
        len(first_records),
        len(second_records),
        float(case.row_count_tolerance),
    )
    assert row_count_ok, f"{case.case_id} {row_count_message}"

    duplicate_ok, duplicate_message = ensure_no_identity_duplicates(
        first_records, case.identity_columns
    )
    assert duplicate_ok, f"{case.case_id} {duplicate_message}"
    duplicate_ok, duplicate_message = ensure_no_identity_duplicates(
        second_records, case.identity_columns
    )
    assert duplicate_ok, f"{case.case_id} {duplicate_message}"

    if case.value_drift_mode == "strict_sample_hash":
        first_hash = strict_sample_hash(first_records, case.identity_columns)
        second_hash = strict_sample_hash(second_records, case.identity_columns)
        assert first_hash == second_hash, (
            f"{case.case_id} immutable sample hash drifted between fetches"
        )
        summary["value_drift"] = {"mode": "strict_sample_hash", "passed": True}
    elif case.value_drift_mode == "distribution_sketch":
        first_sketch = build_distribution_sketch(first_records, case.identity_columns)
        second_sketch = build_distribution_sketch(second_records, case.identity_columns)
        sketch_ok, sketch_message = distribution_sketch_within_tolerance(
            first_sketch,
            second_sketch,
            float(case.row_count_tolerance),
        )
        if not sketch_ok:
            _append_case_p1_failure(summary, f"{case.case_id} value drift: {sketch_message}")
        summary["value_drift"] = {
            "mode": "distribution_sketch",
            "passed": sketch_ok,
            "message": sketch_message,
        }

    _warm_server_registration_case(
        client,
        api_key,
        case=case,
        connection=connection,
    )
    source_id: str | None = None
    try:
        (register_status, register_body), register_ms = timed_api_request(
            client,
            "POST",
            "/v1/sources/register",
            api_key=api_key,
            json_body={"source": {"name": case.case_id, "connection": connection}},
            expected_status=200,
        )
        del register_status
        source_id = str(register_body["source_id"])
        (_, source_body), source_get_ms = timed_api_request(
            client,
            "GET",
            f"/v1/sources/{source_id}",
            api_key=api_key,
            expected_status=200,
        )
        schema = source_body["schema"]
        _assert_registered_schema_has_physical_types(schema, case.case_id)
        registered_fingerprint = schema_fingerprint(schema.get("columns", []))
        assert registered_fingerprint == first_fingerprint, (
            f"{case.case_id} registered schema fingerprint differed from direct fetch fingerprint"
        )

        metric_column = choose_metric_column(schema, first_records, case.aggregation)
        metric_role = _schema_column_role(schema, metric_column)
        if case.aggregation == "count":
            expected_value = float(source_body["schema"].get("row_count", 0) or 0)
            assert expected_value > 0, f"{case.case_id} expected row_count anchor missing"
        else:
            expected_value = compute_expected_aggregate(
                first_records, metric_column, case.aggregation
            )

        resolve_payload = {
            "dataset_id": source_id,
            "metric": {"role": metric_role, "hint": metric_column},
            "aggregation": case.aggregation,
            "reject_on_ambiguity": True,
            "include_explanation": False,
        }

        first_query_started = time.perf_counter()
        (_, resolve_first_body), resolve_first_http_ms = timed_api_request(
            client,
            "POST",
            "/v1/resolve",
            api_key=api_key,
            json_body=resolve_payload,
            expected_status=200,
        )
        resolved_plan = resolve_first_body.get("resolved_plan")
        assert resolved_plan, (
            f"{case.case_id} did not return a resolved_plan: {resolve_first_body}"
        )
        resolve_first_ms = float(resolve_first_body.get("latency_ms") or resolve_first_http_ms)
        (_, query_first_body), query_first_http_ms = timed_api_request(
            client,
            "POST",
            "/v1/query",
            api_key=api_key,
            json_body={"resolved_plan": resolved_plan},
            expected_status=200,
        )
        query_first_ms = float(query_first_body.get("latency_ms") or query_first_http_ms)
        first_query_total_ms = (time.perf_counter() - first_query_started) * 1000
        result = float(query_first_body["result"])
        assert math.isclose(result, expected_value, rel_tol=1e-9, abs_tol=1e-6), (
            f"{case.case_id} {case.aggregation} mismatch for {metric_column}: "
            f"expected {expected_value}, got {result}"
        )

        (_, resolve_hit_body), resolve_hit_http_ms = timed_api_request(
            client,
            "POST",
            "/v1/resolve",
            api_key=api_key,
            json_body=resolve_payload,
            expected_status=200,
        )
        resolve_hit_ms = float(resolve_hit_body.get("latency_ms") or resolve_hit_http_ms)
        (_, query_second_body), exact_hit_http_ms = timed_api_request(
            client,
            "POST",
            "/v1/query",
            api_key=api_key,
            json_body={"resolved_plan": resolved_plan},
            expected_status=200,
        )
        exact_hit_ms = float(query_second_body.get("latency_ms") or exact_hit_http_ms)
        repeat_result = float(query_second_body["result"])
        assert math.isclose(repeat_result, expected_value, rel_tol=1e-9, abs_tol=1e-6), (
            f"{case.case_id} repeat {case.aggregation} mismatch for {metric_column}: "
            f"expected {expected_value}, got {repeat_result}"
        )

        total_request_ms = register_ms + first_query_total_ms
        fetch_budget_key = _fetch_budget_key(case, connection)
        fetch_budget = P1_METRIC_BUDGETS[fetch_budget_key]
        max_fetch_ms = max(fetch_first_ms, fetch_second_ms)
        if fetch_budget.p99 is not None and max_fetch_ms > fetch_budget.p99:
            _append_case_p1_failure(
                summary,
                (
                    f"{case.case_id} {fetch_budget_key} exceeded p99 budget: "
                    f"{max_fetch_ms:.3f}ms > {fetch_budget.p99:.3f}ms"
                ),
            )
        first_query_budget = P1_METRIC_BUDGETS["first_query_total_ms"]
        if first_query_budget.p99 is not None and first_query_total_ms > first_query_budget.p99:
            _append_case_p1_failure(
                summary,
                f"{case.case_id} first_query_total_ms exceeded p99 budget: "
                f"{first_query_total_ms:.3f}ms > {first_query_budget.p99:.3f}ms",
            )
        total_request_budget = P1_METRIC_BUDGETS["total_request_ms"]
        if total_request_budget.p99 is not None and total_request_ms > total_request_budget.p99:
            _append_case_p1_failure(
                summary,
                f"{case.case_id} total_request_ms exceeded p99 budget: "
                f"{total_request_ms:.3f}ms > {total_request_budget.p99:.3f}ms",
            )

        summary["metrics"] = {
            "fetch_ms": [round(fetch_first_ms, 3), round(fetch_second_ms, 3)],
            "fetch_budget_key": fetch_budget_key,
            "register_ms": round(register_ms, 3),
            "source_schema_get_ms": round(source_get_ms, 3),
            "resolve_ms": round(resolve_first_ms, 3),
            "resolve_hit_ms": round(resolve_hit_ms, 3),
            "query_ms": round(query_first_ms, 3),
            "exact_hit_ms": round(exact_hit_ms, 3),
            "first_query_total_ms": round(first_query_total_ms, 3),
            "total_request_ms": round(total_request_ms, 3),
        }
        summary["schema_fingerprint"] = {
            "direct": first_fingerprint,
            "registered": registered_fingerprint,
        }

        if case.negative_probe != "none":
            if case.connector_type in {
                "s3",
                "gcs",
                "azure_blob",
                "redis",
                "snowflake",
                "bigquery",
                "clickhouse",
                "elasticsearch",
            }:
                negative_probe = _run_negative_connector_probe(case)
            else:
                negative_probe = _run_negative_fetch_probe(case)
            assert negative_probe["error_type"] not in {None, "unknown"}, negative_probe
            assert negative_probe["error_type"] in _behavior_negative_expectations(case), negative_probe
            summary["negative_probe"] = negative_probe

        rate_limit_probe = _run_rate_limit_probe(case)
        if rate_limit_probe is not None:
            summary["rate_limit_probe"] = rate_limit_probe

        behavior_case_summaries.append(summary)
        return summary
    finally:
        if source_id is not None:
            try:
                api_request(
                    client,
                    "DELETE",
                    f"/v1/sources/{source_id}",
                    api_key=api_key,
                    expected_status=200,
                )
            except Exception as exc:
                if sys.exc_info()[0] is None:
                    raise
                print(f"  │ cleanup failed for {case.case_id} source {source_id}: {exc}")


def assert_behavior_sla_summary() -> None:
    metrics: dict[str, list[float]] = {
        "resolve_hit_ms": [],
        "exact_hit_ms": [],
        "failure_response_ms": [],
        "failure_response_ms.neo4j_connector_test": [],
        "total_request_ms": [],
        "first_query_total_ms": [],
        "fetch_ms.rest_single_dataset": [],
        "fetch_ms.object_single": [],
        "fetch_ms.warehouse_fixture": [],
        "fetch_ms.clickhouse_cloud_fixture": [],
        "fetch_ms.paginated_rest": [],
    }
    for summary in behavior_case_summaries:
        metric_values = summary.get("metrics", {})
        if "resolve_hit_ms" in metric_values:
            metrics["resolve_hit_ms"].append(float(metric_values["resolve_hit_ms"]))
        if "exact_hit_ms" in metric_values:
            metrics["exact_hit_ms"].append(float(metric_values["exact_hit_ms"]))
        if "total_request_ms" in metric_values:
            metrics["total_request_ms"].append(float(metric_values["total_request_ms"]))
        if "first_query_total_ms" in metric_values:
            metrics["first_query_total_ms"].append(float(metric_values["first_query_total_ms"]))
        fetch_budget_key = str(metric_values.get("fetch_budget_key", "") or "")
        if fetch_budget_key and "fetch_ms" in metric_values:
            metrics[fetch_budget_key].extend(float(value) for value in metric_values["fetch_ms"])
        negative_probe = summary.get("negative_probe")
        if (
            isinstance(negative_probe, dict)
            and negative_probe.get("failure_response_ms") is not None
        ):
            failure_budget_key = str(
                negative_probe.get("failure_response_budget_key", "failure_response_ms")
                or "failure_response_ms"
            )
            metrics[failure_budget_key].append(float(negative_probe["failure_response_ms"]))

    summary_payload = {
        "cases": behavior_case_summaries,
        "metrics": {},
        "p1_failures": sorted(set(behavior_p1_failures)),
    }
    p0_failures: list[str] = []
    for metric_name, budget in P0_METRIC_BUDGETS.items():
        metric_summary = summarize_metric_series(metrics.get(metric_name, []), budget)
        summary_payload["metrics"][metric_name] = metric_summary
        if metric_summary["count"] > 0 and not metric_summary["ok"]:
            p0_failures.append(
                f"{metric_name} exceeded {budget.severity} budget: "
                f"p95={metric_summary['p95']} p99={metric_summary['p99']}"
            )
    for metric_name in (
        "failure_response_ms.neo4j_connector_test",
        "total_request_ms",
        "first_query_total_ms",
        "fetch_ms.rest_single_dataset",
        "fetch_ms.object_single",
        "fetch_ms.warehouse_fixture",
        "fetch_ms.clickhouse_cloud_fixture",
        "fetch_ms.paginated_rest",
    ):
        budget = P1_METRIC_BUDGETS[metric_name]
        metric_summary = summarize_metric_series(metrics.get(metric_name, []), budget)
        summary_payload["metrics"][metric_name] = metric_summary
        if metric_summary["count"] > 0 and not metric_summary["ok"]:
            summary_payload["p1_failures"].append(
                f"{metric_name} exceeded {budget.severity} budget: "
                f"p95={metric_summary['p95']} p99={metric_summary['p99']}"
            )

    print("  Behavioral SLA summary:")
    print(json.dumps(summary_payload, indent=2, sort_keys=True))

    if summary_payload["p1_failures"]:
        print("  Behavioral SLA advisory (P1):")
        for message in sorted(set(summary_payload["p1_failures"])):
            print(f"    {message}")

    assert not p0_failures, "; ".join(p0_failures)


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
    from tests.integration.connector_validation_catalog import ALL_CONNECTOR_VALIDATION_CASES

    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Real go-live connectivity runner")
    parser.add_argument(
        "--parallel-tasks", type=int, default=8, help="Parallel warm exact queries to run"
    )
    parser.add_argument("--api-port", type=int, default=free_port(), help="Local API port")
    parser.add_argument("--data-port", type=int, default=free_port(), help="Local data-server port")
    parser.add_argument(
        "--tiers",
        help="Comma-separated tier filter for external connector validation cases.",
    )
    parser.add_argument(
        "--connector",
        help="Comma-separated connector filter for external connector validation cases.",
    )
    parser.add_argument(
        "--skip-external-validation",
        action="store_true",
        help="Run only the local connectivity coverage and skip tiered external connector validation cases.",
    )
    parser.add_argument(
        "--summary-name",
        default=SUITE_NAME,
        help="Artifact name to write for this connectivity run.",
    )
    args = parser.parse_args()
    selected_tiers = parse_selected_tiers(args.tiers)
    selected_connectors = parse_selected_connectors(args.connector, ALL_CONNECTOR_VALIDATION_CASES)

    print("\n" + "=" * 72)
    print("  GO-LIVE CONNECTIVITY — REAL LOCAL RUN")
    print("=" * 72)

    ensure_port_open("127.0.0.1", 5432, "Postgres")
    redis_bootstrap: LocalRedisBootstrap | None = None
    tmp_root: Path | None = None
    data_server = None
    api_server = None
    client = None

    try:
        redis_bootstrap = ensure_local_redis_available(DEFAULT_REDIS_URL)
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
        seeded = check("Seed real local API key", lambda: run_async(seed_api_key(DEFAULT_DB_URL)))
        if not seeded:
            raise RuntimeError("Failed to seed API key")
        api_key, _org_id = seeded

        sources_dir = tmp_root / "sources"
        data_dir, backlog_records_full, backlog_records_subset, backlog_csv, backlog_parquet_b64 = (
            build_data_directory(tmp_root)
        )
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
            lambda: run_async(
                FileConnector({"file_type": "excel", "content": xlsx_b64}).fetch_data()
            ),
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
        bigquery_credentials_path = materialize_bigquery_service_account_json(tmp_root)
        if bigquery_credentials_path is not None:
            env["GOOGLE_APPLICATION_CREDENTIALS"] = str(bigquery_credentials_path)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(bigquery_credentials_path)
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
            lambda: api_request(
                client, "GET", "/v1/sources", api_key=api_key, bearer=True, expected_status=200
            ),
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
            (
                "UrlCsvBacklog",
                {"url": f"http://127.0.0.1:{args.data_port}/backlog.csv"},
                backlog_records_full,
            ),
            (
                "UrlJsonBacklog",
                {"url": f"http://127.0.0.1:{args.data_port}/backlog.json"},
                backlog_records_subset,
            ),
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
                lambda case_name=case_name, source_payload=source_payload, expected_records=expected_records: (
                    register_and_query_case(
                        client,
                        api_key,
                        case_name=case_name,
                        data_source=source_payload,
                        expected_records=expected_records,
                    )
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
                lambda: api_request(
                    client, "GET", "/v1/data", api_key=api_key, expected_status=200
                ),
            )
            dataset_info = check(
                "High-level /v1/data/{dataset_id} returns schema",
                lambda: api_request(
                    client,
                    "GET",
                    f"/v1/data/{data_dataset_id}",
                    api_key=api_key,
                    expected_status=200,
                ),
            )
            if dataset_info is not None:
                _, dataset_body = dataset_info
                schema = dataset_body["schema"]
                metric_column = choose_metric_column(schema, backlog_records_full)
                expected_sum = compute_expected_aggregate(
                    backlog_records_full, metric_column, "sum"
                )
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
                    actual = (
                        query_body["result"]["value"]
                        if isinstance(query_body.get("result"), dict)
                        else query_body["result"]
                    )
                    assert math.isclose(actual, expected_sum, rel_tol=1e-9, abs_tol=1e-9), (
                        actual,
                        expected_sum,
                        query_body,
                    )

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
                    choice
                    for choice in postgres_body.get("choices", [])
                    if (choice.get("selection") or {}).get("table") == postgres_table_label
                ),
                None,
            )
            assert target_choice is not None, (
                postgres_table_label,
                postgres_body.get("choices", [])[:10],
            )
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
                    postgres_metric_column = choose_metric_column(
                        postgres_schema, backlog_records_subset
                    )
                    postgres_expected_sum = compute_expected_aggregate(
                        backlog_records_subset, postgres_metric_column, "sum"
                    )
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
                        assert math.isclose(
                            actual, postgres_expected_sum, rel_tol=1e-9, abs_tol=1e-9
                        ), (
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
            lambda: api_request(
                client, "GET", "/v1/sources/graph", api_key=api_key, expected_status=200
            ),
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
                {
                    "base_url": f"http://127.0.0.1:{args.data_port}",
                    "health_path": "/rest_payload.json",
                },
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

        selected_cases = select_external_validation_cases(
            ALL_CONNECTOR_VALIDATION_CASES,
            selected_tiers=selected_tiers,
            selected_connectors=selected_connectors,
            skip_external_validation=args.skip_external_validation,
        )
        for case in selected_cases:
            skip_reason = case.skip_reason()
            if skip_reason:
                skip(case.label, skip_reason)
                continue
            check(
                case.label,
                lambda case=case: run_behavior_validation_case(
                    client,
                    api_key,
                    case=case,
                    create_connector=create_connector,
                ),
            )

        check("Behavioral SLA summary", assert_behavior_sla_summary)

        warm_case = case_results["CsvBacklog"]
        warm_payload = {
            "source_name": "CsvBacklog",
            "metric_column": warm_case["metric_column"],
            "aggregation": "sum",
        }
        check(
            "Warm exact query before fanout",
            lambda: api_request(
                client,
                "POST",
                "/v1/query",
                api_key=api_key,
                json_body=warm_payload,
                expected_status=200,
            ),
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
            print(
                f"    parallel total={elapsed:.3f}s  avg={(elapsed / args.parallel_tasks):.3f}s/query"
            )

        delete_target = case_results["JsonBacklog"]["source_id"]
        check(
            "Delete one registered source",
            lambda: api_request(
                client,
                "DELETE",
                f"/v1/sources/{delete_target}",
                api_key=api_key,
                expected_status=200,
            ),
        )
        check(
            "Deleted source is gone from registry",
            lambda: api_request(
                client, "GET", f"/v1/sources/{delete_target}", api_key=api_key, expected_status=404
            ),
        )

        for dataset_id in [
            dataset_id
            for dataset_id in [data_dataset_id, sqlite_dataset_id, api_dataset_id]
            if dataset_id
        ]:
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
        if tmp_root is not None:
            shutil.rmtree(tmp_root, ignore_errors=True)
        if redis_bootstrap is not None:
            redis_bootstrap.stop()

    passed = sum(1 for icon, _, _ in results if icon == PASS)
    failed = sum(1 for icon, _, _ in results if icon == FAIL)
    skipped = sum(1 for icon, _, _ in results if icon == SKIP)

    print("\n" + "=" * 72)
    print(f"Passed:  {passed}")
    print(f"Failed:  {failed}")
    print(f"Skipped: {skipped}")
    if failed:
        print("Failed checks:")
        for _icon, name, detail in results:
            if _icon != FAIL:
                continue
            if detail:
                print(f"  - {name}: {detail}")
            else:
                print(f"  - {name}")
    if skipped:
        print("Skipped checks:")
        for _icon, name, detail in results:
            if _icon != SKIP:
                continue
            if detail:
                print(f"  - {name}: {detail}")
            else:
                print(f"  - {name}")
    if timings:
        slowest = sorted(timings, key=lambda item: item[1], reverse=True)[:10]
        print("Slowest:")
        for name, elapsed in slowest:
            print(f"  - {name}: {elapsed:.3f}s")
    print("=" * 72)
    artifact_path = write_live_integration_summary(
        args.summary_name,
        script="tests/integration/test_go_live_connectivity_real.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(results),
        elapsed_seconds=time.perf_counter() - started,
        details={
            "skipped": skipped,
            "failed_checks": [name for icon, name, _ in results if icon == FAIL],
            "skipped_checks": [
                {"name": name, "reason": detail}
                for icon, name, detail in results
                if icon == SKIP
            ],
            "parallel_tasks": args.parallel_tasks,
            "selected_tiers": list(selected_tiers or ()),
            "selected_connectors": list(selected_connectors or ()),
            "skip_external_validation": bool(args.skip_external_validation),
            "behavior_p1_failures": list(behavior_p1_failures),
        },
    )
    print(f"Summary artifact: {artifact_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
