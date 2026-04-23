from __future__ import annotations

import asyncio
import importlib
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# ruff: noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
TEST_FILES = ROOT / "test_files"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from algenta import Runtime
from algenta.runtime import (
    QueryOutput,
    ResolveOutput,
    RuntimeConfigurationError,
    RuntimeValidationError,
    SourceRegistration,
)

from apps.api_server.config import get_settings
from apps.api_server.db.session import get_db
from apps.api_server.main import app as fastapi_app
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.routers import query as query_router
from apps.api_server.services import source_registry as reg
from apps.api_server.services.device_service import _issue_license_jwt
from tests._asgi_client import SyncASGIClient


def _sample_rows() -> list[dict[str, object]]:
    return [
        {"product_line": "Electronics", "revenue": 42193221, "region": "US"},
        {"product_line": "Apparel", "revenue": 28114992, "region": "US"},
        {"product_line": "Electronics", "revenue": 1204000, "region": "CA"},
    ]


def _write_sqlite_fixture(path: Path, rows: list[dict[str, object]], table_name: str = "orders") -> None:
    if not rows:
        raise ValueError("SQLite fixture requires at least one row.")
    columns = list(rows[0].keys())
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    schema = ", ".join(
        f'"{column}" REAL' if column == "revenue" else f'"{column}" TEXT'
        for column in columns
    )
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})'
    connection = sqlite3.connect(path)
    try:
        connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.execute(f'CREATE TABLE "{table_name}" ({schema})')
        connection.executemany(
            insert_sql,
            [tuple(row[column] for column in columns) for row in rows],
        )
        connection.commit()
    finally:
        connection.close()


def _write_parquet_fixture(path: Path, rows: list[dict[str, object]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


def _write_excel_fixture(path: Path, rows: list[dict[str, object]]) -> None:
    from openpyxl import Workbook

    if not rows:
        raise ValueError("Excel fixture requires at least one row.")
    workbook = Workbook()
    worksheet = workbook.active
    headers = list(rows[0].keys())
    worksheet.append(headers)
    for row in rows:
        worksheet.append([row.get(header) for header in headers])
    workbook.save(path)
    workbook.close()


def _reload_runtime_license_module():
    module_name = "apps.runtime.license"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def _reload_runtime_credits_module():
    module_name = "apps.runtime.credits"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


REAL_MARCH_ORDERS = (
    TEST_FILES / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
)
REAL_MARCH_FINANCIAL = (
    TEST_FILES / "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"
)
REAL_MARCH_EMPTY = (
    TEST_FILES / "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv"
)
REAL_MARCH_INACCURATE = (
    TEST_FILES / "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv"
)
REAL_MARCH_RATINGS = (
    TEST_FILES / "3d9b2e55-c7ea-4e31-90ea-ca5797a69c2b_restaurant_rating_sku_local_2026-03-01_2026-03-31.csv"
)
REAL_LOCAL_PARQUET = TEST_FILES / ".algenta_cache" / "BookingsNew.parquet"
REAL_LOCAL_WORKBOOK = TEST_FILES / "QPL Price List_AAR_Expires 20241230.xlsx"
PUBLIC_S3_CONNECTION = {
    "type": "s3",
    "bucket": "noaa-global-hourly-pds",
    "key": "1901/02907099999.csv",
    "region": "us-east-1",
    "anonymous": True,
    "format": "csv",
}
PUBLIC_REST_CONNECTION = {
    "type": "rest",
    "base_url": "https://api.weather.gov",
    "path": "/stations",
    "method": "GET",
    "headers": {
        "User-Agent": "algenta-runtime-compat/1.0",
        "Accept": "application/geo+json",
    },
    "params": {"state": "CO"},
    "data_path": "features",
    "timeout": 60,
}


class _FakeDB:
    async def commit(self) -> None:
        return None


async def _override_db():
    yield _FakeDB()


async def _clear_runtime_api_caches() -> None:
    async with query_router._CACHE_LOCK:
        query_router._SOURCE_CACHE.clear()
        query_router._PLANNER_CACHE.clear()
        query_router._RESULT_CACHE.clear()


class _AsgiRuntimeApiClient:
    def __init__(self, test_client: SyncASGIClient) -> None:
        self._client = test_client

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        response = self._client.request(method, path, json=json_body)
        if response.status_code >= 400:
            detail = response.json().get("detail")
            error = detail.get("error", {}) if isinstance(detail, dict) else {}
            raise RuntimeValidationError(
                str(error.get("code") or "api_runtime_error"),
                str(error.get("message") or response.text),
                {"status_code": response.status_code},
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise AssertionError(f"Expected dict API response for {path}, received {type(payload)!r}")
        return payload

    def register_source(
        self,
        source: dict[str, object],
        *,
        description: str | None = None,
    ) -> dict[str, object]:
        body: dict[str, object] = {"source": source}
        if description is not None:
            body["description"] = description
        return self._request("POST", "/v1/sources/register", json_body=body)

    def resolve(self, request: dict[str, object]) -> dict[str, object]:
        return self._request("POST", "/v1/resolve", json_body=request)

    def query(self, request: dict[str, object]) -> dict[str, object]:
        return self._request("POST", "/v1/query", json_body=request)

    def verify(self, request: dict[str, object]) -> dict[str, object]:
        return self._request("POST", "/v1/verify", json_body=request)


@pytest.fixture
def runtime_api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _AsgiRuntimeApiClient:
    fake_auth = {
        "org_id": "org_runtime_api",
        "role": "owner",
        "user_id": "u1",
        "key_id": "k1",
    }
    fastapi_app.dependency_overrides[get_current_org] = lambda: fake_auth
    fastapi_app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(reg, "_SOURCES_DIR", tmp_path / "sources")
    asyncio.run(_clear_runtime_api_caches())
    with SyncASGIClient(
        fastapi_app,
        headers={
            "Authorization": "Bearer de_test_runtime",
            "Content-Type": "application/json",
        },
        manage_lifespan=True,
        raise_app_exceptions=False,
    ) as client:
        yield _AsgiRuntimeApiClient(client)
    asyncio.run(_clear_runtime_api_caches())
    fastapi_app.dependency_overrides.clear()


def _result_scalar_value(result: object) -> float:
    if isinstance(result, dict):
        return float(result.get("value"))
    return float(result)


def test_runtime_api_client_shutdown_clears_global_mojo_pool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from apps.api_server.compute.mojo_pool import MojoEngineError, get_pool_sync

    fake_auth = {
        "org_id": "org_runtime_api",
        "role": "owner",
        "user_id": "u1",
        "key_id": "k1",
    }
    fastapi_app.dependency_overrides[get_current_org] = lambda: fake_auth
    fastapi_app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(reg, "_SOURCES_DIR", tmp_path / "sources")
    asyncio.run(_clear_runtime_api_caches())

    with SyncASGIClient(
        fastapi_app,
        headers={
            "Authorization": "Bearer de_test_runtime",
            "Content-Type": "application/json",
        },
        manage_lifespan=True,
        raise_app_exceptions=False,
    ):
        mojo_pool = getattr(fastapi_app.state, "mojo_pool", None)
        if mojo_pool is not None:
            assert get_pool_sync().running is True
        else:
            with pytest.raises(MojoEngineError, match="Mojo pool not initialized"):
                get_pool_sync()

    with pytest.raises(MojoEngineError, match="Mojo pool not initialized"):
        get_pool_sync()
    assert getattr(fastapi_app.state, "mojo_pool", None) is None
    assert getattr(fastapi_app.state, "redis", None) is None

    asyncio.run(_clear_runtime_api_caches())
    fastapi_app.dependency_overrides.clear()


def _registration_metric_field(registration: SourceRegistration) -> str:
    fields = registration.source_schema.get("fields", []) if registration.source_schema else []
    if not fields and registration.source_schema:
        fields = [
            str(column.get("name"))
            for column in registration.source_schema.get("columns", [])
            if isinstance(column, dict) and isinstance(column.get("name"), str)
        ]
    if not fields:
        raise AssertionError("Registration returned no queryable schema fields.")
    return str(fields[0])


def test_runtime_local_resolve_query_happy_path() -> None:
    runtime = Runtime()
    registration = runtime.connect(_sample_rows(), name="orders")

    plan = runtime.resolve({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert isinstance(plan, ResolveOutput)
    assert plan.resolved_plan is not None
    assert plan.resolved_plan.metric_column == "revenue"
    assert plan.resolved_plan.group_column == "product_line"
    assert isinstance(result, QueryOutput)
    assert result.result_type == "table"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_verify_happy_path() -> None:
    runtime = Runtime()
    runtime.connect(_sample_rows(), name="orders")
    plan = runtime.resolve({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})

    verification = runtime.verify(plan)

    assert verification.valid is True
    assert verification.verified is True
    assert verification.resolved["metric_column"] == "revenue"


def test_runtime_local_import_preview_and_query_real_csv_file() -> None:
    runtime = Runtime()

    imported = runtime.import_preview(
        REAL_MARCH_ORDERS,
        name="orders_detail",
        source_ref=REAL_MARCH_ORDERS.name,
    )
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )
    result = runtime.query(plan)

    assert imported.registration.row_count == 6097
    assert imported.registration.name == "orders_detail"
    assert "Algenta Source Import" in imported.preview
    assert "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states" in imported.preview
    assert plan.resolved_plan is not None
    assert plan.resolved_plan.metric_column == "Sales (incl. tax)"
    assert plan.resolved_plan.group_column == "Order Channel"
    assert result.result_type == "table"
    assert result.row_count > 0


def test_runtime_local_connect_real_csv_skips_alias_header_row() -> None:
    runtime = Runtime()

    registration = runtime.connect(REAL_MARCH_FINANCIAL, name="orders_financial")

    assert registration.row_count == 2026


def test_runtime_local_connect_rejects_real_empty_export() -> None:
    runtime = Runtime()

    with pytest.raises(RuntimeValidationError, match="empty"):
        runtime.connect(REAL_MARCH_EMPTY, name="store_pause")


def test_runtime_local_connect_sqlite_descriptor_happy_path(tmp_path: Path) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())

    runtime = Runtime()
    registration = runtime.connect(
        {
            "provider": "sqlite",
            "path": str(db_path),
            "table": "orders",
        }
    )
    plan = runtime.resolve({"source_name": registration.name, "metric": "revenue", "group_by": "product_line"})
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 3
    assert registration.name == "orders_orders"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_connect_sqlite_descriptor_supports_connection_string_and_query(tmp_path: Path) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())

    runtime = Runtime()
    registration = runtime.connect(
        {
            "type": "sqlite",
            "connection_string": f"sqlite+pysqlite:///{db_path}",
            "query": "SELECT product_line, revenue FROM orders WHERE region = 'US'",
        },
    )

    assert registration.status == "ready"
    assert registration.row_count == 2
    assert registration.name == "orders_query"


def test_runtime_local_connect_parquet_file_happy_path(tmp_path: Path) -> None:
    parquet_path = tmp_path / "orders.parquet"
    _write_parquet_fixture(parquet_path, _sample_rows())

    runtime = Runtime()
    registration = runtime.connect(parquet_path, name="orders_parquet")
    plan = runtime.resolve(
        {"source_name": registration.name, "metric": "revenue", "group_by": "product_line"}
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 3
    assert registration.name == "orders_parquet"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_connect_excel_file_happy_path(tmp_path: Path) -> None:
    workbook_path = tmp_path / "orders.xlsx"
    _write_excel_fixture(workbook_path, _sample_rows())

    runtime = Runtime()
    registration = runtime.connect(workbook_path, name="orders_excel")
    plan = runtime.resolve(
        {"source_name": registration.name, "metric": "revenue", "group_by": "product_line"}
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 3
    assert registration.name == "orders_excel"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_import_preview_uses_descriptor_origin_for_sqlite_sources(tmp_path: Path) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())
    runtime = Runtime()

    imported = runtime.import_preview(
        {
            "provider": "sqlite",
            "path": str(db_path),
            "table": "orders",
        },
    )

    assert imported.registration.name == "orders_orders"
    assert imported.preview.startswith(" █████╗")
    assert f"{db_path.name}#orders" in imported.preview


def test_runtime_local_connect_sqlite_descriptor_requires_table_or_query(tmp_path: Path) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())
    runtime = Runtime()

    with pytest.raises(RuntimeValidationError, match="table or query"):
        runtime.connect({"provider": "sqlite", "path": str(db_path)})


def test_runtime_local_import_bundle_preview_reports_successes_and_failures_for_real_march_corpus() -> None:
    runtime = Runtime()

    bundle = runtime.import_bundle_preview(
        [
            REAL_MARCH_ORDERS,
            REAL_MARCH_FINANCIAL,
            REAL_MARCH_INACCURATE,
            REAL_MARCH_RATINGS,
            REAL_MARCH_EMPTY,
        ],
        source_refs=[
            REAL_MARCH_ORDERS.name,
            REAL_MARCH_FINANCIAL.name,
            REAL_MARCH_INACCURATE.name,
            REAL_MARCH_RATINGS.name,
            REAL_MARCH_EMPTY.name,
        ],
    )

    assert len(bundle.registrations) == 4
    assert len(bundle.failures) == 1
    assert bundle.failures[0].code == "empty_source"
    assert bundle.failures[0].source_ref == REAL_MARCH_EMPTY.name
    assert "Algenta Source Bundle" in bundle.preview
    assert "Imported: 4 | Failures: 1" in bundle.preview
    assert "orders_financial" in bundle.preview or REAL_MARCH_FINANCIAL.stem in bundle.preview
    assert "Shared fields:" in bundle.preview


def test_runtime_local_import_bundle_preview_supports_mixed_csv_and_sqlite_sources(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path, _sample_rows())
    runtime = Runtime()

    bundle = runtime.import_bundle_preview(
        [
            REAL_MARCH_ORDERS,
            {
                "provider": "sqlite",
                "path": str(db_path),
                "table": "orders",
            },
            REAL_MARCH_EMPTY,
        ],
        source_refs=[
            REAL_MARCH_ORDERS.name,
            "orders.db#orders",
            REAL_MARCH_EMPTY.name,
        ],
    )

    assert len(bundle.registrations) == 2
    assert len(bundle.failures) == 1
    assert bundle.registrations[0].name == "united_states"
    assert bundle.registrations[1].name == "orders_orders"
    assert bundle.failures[0].code == "empty_source"
    assert "Imported: 2 | Failures: 1" in bundle.preview
    assert "orders_orders" in bundle.preview


def test_runtime_local_hosted_limits_work_offline_with_stored_license(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license_module()
    credits_mod = _reload_runtime_credits_module()
    token = _issue_license_jwt(
        device_id="device-runtime-offline-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_runtime_test",
    )
    license_mod._save_license(token)
    credits_mod.get_store().initialize_sync(credits_granted=2, billing_period="2026-04")

    runtime = Runtime(api_key="de_live_test_key")
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch.object(
        license_mod,
        "_exchange_api_key_for_license",
        side_effect=AssertionError("stored offline license must not hit control plane"),
    ):
        first = runtime.query(plan)
        second = runtime.query(plan)
        with pytest.raises(RuntimeValidationError, match="quota"):
            runtime.query(plan)

    state = credits_mod.get_store()._read()
    assert first.row_count > 0
    assert second.row_count > 0
    assert state is not None
    assert state.credits_remaining == 0
    get_settings.cache_clear()


def test_runtime_local_hosted_limits_block_first_time_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.delenv("LICENSE_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    get_settings.cache_clear()

    license_mod = _reload_runtime_license_module()
    _reload_runtime_credits_module()

    runtime = Runtime(api_key="de_live_test_key")
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch.object(license_mod, "_exchange_api_key_for_license", return_value=None):
        with pytest.raises(RuntimeConfigurationError, match="control plane"):
            runtime.query(plan)
    get_settings.cache_clear()


def test_runtime_local_without_enforced_limits_skips_runtime_license_path() -> None:
    runtime = Runtime()
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with patch(
        "apps.runtime.license.load_license",
        side_effect=AssertionError("plain local runtime must not load hosted license"),
    ):
        result = runtime.query(plan)

    assert result.row_count > 0


def test_runtime_local_requires_connected_source() -> None:
    runtime = Runtime()

    with pytest.raises(RuntimeConfigurationError, match="No local sources are connected"):
        runtime.resolve({"metric": "revenue"})


def test_runtime_query_rejects_schema_revision_mismatch() -> None:
    runtime = Runtime()
    runtime.connect(_sample_rows(), name="orders")
    plan = runtime.resolve({"source_name": "orders", "metric": "revenue"})
    assert plan.resolved_plan is not None
    tampered_plan = plan.resolved_plan.to_dict()
    tampered_plan["schema_revision"] = "stale"

    with pytest.raises(RuntimeValidationError, match="schema_revision"):
        runtime.query(tampered_plan)


def test_runtime_api_mode_requires_sdk_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)
    runtime = Runtime(mode="api")

    with pytest.raises(RuntimeConfigurationError, match="API mode requires an API key"):
        runtime.resolve({"metric": "revenue"})


def test_runtime_api_mode_wraps_direct_client(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    captured_verify: dict[str, object] | None = None
    captured_query: dict[str, object] | None = None

    class _FakeClient:
        def resolve(self, request: dict[str, object]) -> object:
            assert request == {
                "preferred_source": "orders",
                "allow_org_scope": True,
                "metric": {"role": "metric", "hint": "revenue"},
                "group_by": ["product_line"],
            }
            return SimpleNamespace(
                model_dump=lambda: {
                    "resolved_plan": {
                        "source_name": "orders",
                        "metric_column": "revenue",
                        "aggregation": "sum",
                        "group_column": "product_line",
                        "schema_revision": "schema_123",
                        "constraints": {},
                        "order": "desc",
                    },
                    "confidence": 1.0,
                    "plan": ["Use source 'orders'."],
                    "explanation": ["Resolved metric 'revenue' to 'revenue'."],
                    "latency_ms": 12.5,
                    "decision_path": "exact_spec",
                    "schema_revision": "schema_123",
                    "validated": True,
                    "deterministic_scope": "api_registered_source",
                    "confidence_source": "schema_match",
                    "clarification_required": False,
                    "rejection_reason": None,
                    "request_id": "req_123",
                    "intent_signature": "intent_123",
                    "plan_hash": "plan_123",
                    "source_set": ["orders"],
                    "join_path": [],
                    "planner_mode": "runtime",
                    "resolved_source": "orders",
                    "resolved_column": "revenue",
                    "resolved_role": "measure",
                    "candidates": [],
                        "source_scores": {"orders": 1.0},
                }
            )

        def verify(self, request: dict[str, object]) -> object:
            nonlocal captured_verify
            captured_verify = request
            return SimpleNamespace(
                model_dump=lambda: {
                    "valid": True,
                    "errors": [],
                    "suggestions": [],
                    "resolved": {"source_name": "orders"},
                    "latency_ms": 1.0,
                    "verified": True,
                    "request_id": "req_verify",
                    "schema_revision": "schema_123",
                    "plan_hash": "plan_123",
                    "verification_mode": "assist",
                    "rejection_reason": None,
                }
            )

        def query(self, request: dict[str, object]) -> object:
            nonlocal captured_query
            captured_query = request
            assert request["resolved_plan"]["metric_column"] == "revenue"
            return SimpleNamespace(
                model_dump=lambda: {
                    "result": [{"product_line": "Electronics", "revenue": 100.0}],
                    "result_type": "table",
                    "confidence": 1.0,
                    "plan": ["Execute exact plan."],
                    "resolved_column": "revenue",
                    "resolved_role": "measure",
                    "resolved_source": "orders",
                    "row_count": 1,
                    "ambiguous": False,
                    "exact_spec": True,
                    "explanation": ["Executed deterministic query."],
                    "latency_ms": 4.2,
                    "decision_path": "exact_spec",
                    "plan_hash": "plan_123",
                    "validated": True,
                    "deterministic_scope": "api_registered_source",
                    "confidence_source": "exact_execution",
                    "schema_revision": "schema_123",
                    "candidates": [],
                    "source_scores": {"orders": 1.0},
                    "clarification_required": False,
                    "rejection_reason": None,
                    "request_id": "req_123",
                    "source_set": ["orders"],
                    "join_path": [],
                    "planner_mode": "runtime",
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    plan = runtime.resolve({"source_name": "orders", "metric": "revenue", "group_by": "product_line"})
    verified = runtime.verify(plan)
    result = runtime.query(plan)

    assert plan.resolved_plan is not None
    assert verified.valid is True
    assert result.result[0]["revenue"] == 100.0
    assert captured_verify is not None
    assert captured_verify["resolved_plan"]["source_name"] == "orders"
    assert captured_verify["resolved_plan"]["metric_column"] == "revenue"
    assert captured_verify["resolved_plan"]["group_column"] == "product_line"
    assert captured_verify["resolved_plan"]["schema_revision"] == "schema_123"
    assert captured_verify["resolved_plan"]["aggregation"] == "sum"
    assert captured_verify["resolved_plan"]["constraints"] == {}
    assert captured_verify["resolved_plan"]["order"] == "desc"
    assert captured_query == captured_verify


def test_runtime_api_mode_real_public_rest_connect_resolve_verify_query(
    runtime_api_client: _AsgiRuntimeApiClient,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test_runtime", base_url="http://test")
    runtime._api_client = runtime_api_client

    registration = runtime.connect(PUBLIC_REST_CONNECTION, name="weather_stations")
    assert registration.status == "registered"
    assert registration.row_count is not None
    assert registration.row_count > 0

    plan = runtime.resolve(
        {
            "source_name": registration.name,
            "metric": _registration_metric_field(registration),
            "aggregation": "count",
        }
    )
    verification = runtime.verify(plan)
    result = runtime.query(plan)

    assert plan.resolved_plan is not None
    assert plan.validated is True
    assert verification.valid is True
    assert result.validated is True
    assert result.result_type == "scalar"
    assert _result_scalar_value(result.result) == pytest.approx(float(registration.row_count))


def test_runtime_api_mode_real_public_s3_connect_resolve_query(
    runtime_api_client: _AsgiRuntimeApiClient,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test_runtime", base_url="http://test")
    runtime._api_client = runtime_api_client

    imported = runtime.import_preview(
        PUBLIC_S3_CONNECTION,
        name="noaa_hourly",
        source_ref="s3://noaa-global-hourly-pds/1901/02907099999.csv",
    )
    plan = runtime.resolve(
        {
            "source_name": imported.registration.name,
            "metric": _registration_metric_field(imported.registration),
            "aggregation": "count",
        }
    )
    result = runtime.query(plan)

    assert imported.registration.status == "registered"
    assert imported.registration.row_count is not None
    assert imported.registration.row_count > 0
    assert "Algenta Source Import" in imported.preview
    assert "Origin: s3://noaa-global-hourly-pds/1901/02907099999.csv" in imported.preview
    assert plan.resolved_plan is not None
    assert result.result_type == "scalar"
    assert _result_scalar_value(result.result) == pytest.approx(float(imported.registration.row_count))


@pytest.mark.parametrize(
    ("source_descriptor", "expected_name"),
    [
        (
            {
                "type": "postgres",
                "connection_string": "postgresql://analytics:secret@localhost:5432/orders",
                "schema": "public",
                "table": "orders",
            },
            "orders_pg",
        ),
        (
            {
                "type": "mysql",
                "connection_string": "mysql://analytics:secret@localhost:3306/orders",
                "database": "orders",
                "table": "orders",
            },
            "orders_mysql",
        ),
        (
            {
                "type": "s3",
                "bucket": "algenta-public",
                "key": "orders/orders.csv",
                "format": "csv",
            },
            "orders_s3",
        ),
        (
            {
                "type": "rest",
                "base_url": "https://example.com/api",
                "path": "/orders",
                "method": "GET",
            },
            "orders_rest",
        ),
    ],
)
def test_runtime_api_mode_connect_passes_connector_descriptor_through(
    monkeypatch: pytest.MonkeyPatch,
    source_descriptor: dict[str, object],
    expected_name: str,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    captured: dict[str, object] = {}

    class _FakeClient:
        def register_source(
            self,
            source: dict[str, object],
            *,
            description: str | None = None,
        ) -> object:
            captured["source"] = source
            captured["description"] = description
            return SimpleNamespace(
                model_dump=lambda: {
                    "source_id": "src_pg_1",
                    "dataset_id": "src_pg_1",
                    "name": expected_name,
                    "status": "ready",
                    "source_schema": {"fields": ["order_id", "revenue"]},
                    "planner_schema_revision": "schema_pg_1",
                    "latency_ms": 3.4,
                    "row_count": 120,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    registration = runtime.connect(
        source_descriptor,
        name=expected_name,
        description=f"Primary {expected_name} source",
    )

    assert registration.name == expected_name
    assert captured["description"] == f"Primary {expected_name} source"
    normalized_source = captured["source"]
    assert isinstance(normalized_source, dict)
    assert normalized_source["name"] == expected_name
    connection = normalized_source.get("connection")
    assert isinstance(connection, dict)
    if source_descriptor["type"] in {"postgres", "mysql"}:
        assert connection["type"] == "sql"
        assert connection["provider"] == source_descriptor["type"]
        assert connection["connection_string"] == source_descriptor["connection_string"]
        if source_descriptor["type"] == "postgres":
            assert connection["query"] == "SELECT * FROM public.orders"
        else:
            assert connection["query"] == "SELECT * FROM orders"
    elif source_descriptor["type"] == "s3":
        assert connection == {
            "type": "s3",
            "bucket": "algenta-public",
            "key": "orders/orders.csv",
            "file_type": "csv",
        }
    else:
        assert connection["type"] == "rest_api"
        assert connection["url"] == "https://example.com/api/orders"
        assert connection["method"] == "GET"
        assert connection["path"] == "/orders"


def test_runtime_local_connect_accepts_canonical_csv_connector(tmp_path: Path) -> None:
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("product_line,revenue\nElectronics,10\nApparel,20\n", encoding="utf-8")
    runtime = Runtime()

    registration = runtime.connect(
        {
            "type": "csv",
            "location": {"path": str(csv_path)},
            "options": {"delimiter": ","},
        },
        name="orders_detail",
    )
    plan = runtime.resolve(
        {
            "source_name": registration.name,
            "metric": "revenue",
            "aggregation": "count",
        }
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 2
    assert plan.resolved_plan is not None
    assert float(_result_scalar_value(result.result)) == 2.0


def test_runtime_local_connect_rejects_remote_canonical_connector() -> None:
    runtime = Runtime()

    with pytest.raises(RuntimeValidationError) as exc:
        runtime.connect(
            {
                "type": "postgres",
                "location": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "orders",
                    "schema": "public",
                    "table": "orders",
                },
                "auth": {
                    "credentials": {
                        "user": "analytics",
                        "password": "secret",
                    }
                },
            },
            name="orders_pg",
        )

    assert exc.value.code == "unsupported_local_connector"


@pytest.mark.parametrize(
    ("source_descriptor", "expected_connection"),
    [
        (
            {
                "type": "postgres",
                "location": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "orders",
                    "schema": "public",
                    "table": "orders",
                },
                "auth": {
                    "credentials": {
                        "user": "analytics",
                        "password": "secret",
                    }
                },
            },
            {
                "type": "sql",
                "provider": "postgres",
                "connection_string": "postgresql://analytics:secret@localhost:5432/orders",
                "schema": "public",
                "table": "orders",
                "query": "SELECT * FROM public.orders",
            },
        ),
        (
            {
                "type": "s3",
                "location": {"bucket": "algenta-public", "key": "orders/orders.csv"},
                "options": {"format": "csv"},
            },
            {
                "type": "s3",
                "bucket": "algenta-public",
                "key": "orders/orders.csv",
                "file_type": "csv",
            },
        ),
        (
            {
                "type": "rest",
                "location": {"base_url": "https://example.com/api", "path": "/orders"},
                "auth": {"mode": "token", "credentials": {"token": "secret-token"}},
                "options": {"method": "GET"},
            },
            {
                "type": "rest_api",
                "url": "https://example.com/api/orders",
                "path": "/orders",
                "method": "GET",
                "headers": {"Authorization": "Bearer secret-token"},
            },
        ),
        (
            {
                "type": "csv",
                "location": {"path": str(REAL_MARCH_ORDERS)},
                "options": {"delimiter": ","},
            },
            {
                "type": "file",
                "file_type": "csv",
                "file_path": str(REAL_MARCH_ORDERS),
                "delimiter": ",",
            },
        ),
    ],
)
def test_runtime_api_mode_accepts_canonical_connector_envelope(
    monkeypatch: pytest.MonkeyPatch,
    source_descriptor: dict[str, object],
    expected_connection: dict[str, object],
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    captured: dict[str, object] = {}

    class _FakeClient:
        def register_source(
            self,
            source: dict[str, object],
            *,
            description: str | None = None,
        ) -> object:
            captured["source"] = source
            captured["description"] = description
            return SimpleNamespace(
                model_dump=lambda: {
                    "source_id": "src_1",
                    "dataset_id": "src_1",
                    "name": "canonical_source",
                    "status": "ready",
                    "source_schema": {"fields": ["order_id", "revenue"]},
                    "planner_schema_revision": "schema_1",
                    "latency_ms": 2.1,
                    "row_count": 3,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    registration = runtime.connect(
        source_descriptor,
        name="canonical_source",
        description="Canonical source",
    )

    assert registration.name == "canonical_source"
    assert captured["description"] == "Canonical source"
    normalized_source = captured["source"]
    assert isinstance(normalized_source, dict)
    assert normalized_source["name"] == "canonical_source"
    assert normalized_source["connection"] == expected_connection


def test_runtime_api_mode_import_bundle_preview_supports_mixed_connector_descriptors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    seen: list[dict[str, object]] = []

    class _FakeClient:
        def register_source(
            self,
            source: dict[str, object],
            *,
            description: str | None = None,
        ) -> object:
            seen.append(source)
            connection = source.get("connection")
            if isinstance(connection, dict) and connection.get("type") == "rest_api":
                raise RuntimeValidationError(
                    "upstream_validation_failed",
                    "REST source rejected by hosted connector validation.",
                    {"source": connection.get("url")},
                )
            return SimpleNamespace(
                model_dump=lambda: {
                    "source_id": f"src_{len(seen)}",
                    "dataset_id": f"src_{len(seen)}",
                    "name": source.get("name"),
                    "status": "ready",
                    "source_schema": {"fields": ["order_id", "revenue", "store_name"]},
                    "planner_schema_revision": f"schema_{len(seen)}",
                    "latency_ms": 3.4,
                    "row_count": 120,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    bundle = runtime.import_bundle_preview(
        [
            {
                "type": "postgres",
                "location": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "orders",
                    "schema": "public",
                    "table": "orders",
                },
                "auth": {
                    "credentials": {
                        "user": "analytics",
                        "password": "secret",
                    }
                },
            },
            {
                "type": "s3",
                "bucket": "algenta-public",
                "key": "orders/orders.csv",
                "format": "csv",
            },
            {
                "type": "rest",
                "base_url": "https://example.com/api",
                "path": "/orders",
                "method": "GET",
            },
        ],
        names=["orders_pg", "orders_s3", "orders_rest"],
        source_refs=["postgres://orders", "s3://algenta-public/orders/orders.csv", "https://example.com/api/orders"],
    )

    assert len(bundle.registrations) == 2
    assert len(bundle.failures) == 1
    assert bundle.failures[0].code == "upstream_validation_failed"
    assert "Algenta Source Bundle" in bundle.preview
    assert "Imported: 2 | Failures: 1" in bundle.preview
    assert "orders_pg" in bundle.preview
    assert "orders_s3" in bundle.preview
    assert "orders_rest: upstream_validation_failed" in bundle.preview
    assert [entry["name"] for entry in seen] == ["orders_pg", "orders_s3", "orders_rest"]
    assert [entry["connection"]["type"] for entry in seen] == ["sql", "s3", "rest_api"]
    assert seen[0]["connection"]["connection_string"] == "postgresql://analytics:secret@localhost:5432/orders"
