from __future__ import annotations

import asyncio
import importlib
import sqlite3
import sys
import warnings
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.platform_contract import load_platform_contract_manifest
from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations,
)

# ruff: noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
TEST_FILES = ROOT / "test_files"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_manifest_models = importlib.import_module("algenta.runtime_model_manifest")

from algenta import Runtime
from algenta.runtime import (
    PlatformContractOutput,
    QueryBatchOutput,
    QueryOutput,
    QuerySqlReportOutput,
    QueryWithMetadataOutput,
    ResolveOutput,
    RuntimeAdminBenchmarksOutput,
    RuntimeAdminModulesOutput,
    RuntimeConfigurationError,
    RuntimeManifestOutput,
    RuntimeReleaseValidationOutput,
    RuntimeValidationError,
    SourceRegistration,
)

RuntimeMaturity = runtime_manifest_models.RuntimeMaturity
RuntimeBenchmarkBaseline = runtime_manifest_models.RuntimeBenchmarkBaseline
RuntimeBenchmarkClassCode = runtime_manifest_models.RuntimeBenchmarkClassCode
RuntimeBenchmarkMetric = runtime_manifest_models.RuntimeBenchmarkMetric
RuntimeEvaluationMethod = runtime_manifest_models.RuntimeEvaluationMethod
RuntimeReplayability = runtime_manifest_models.RuntimeReplayability
RuntimeRiskLevel = runtime_manifest_models.RuntimeRiskLevel
RuntimeSchedulerPolicy = runtime_manifest_models.RuntimeSchedulerPolicy
RuntimeSideEffectClass = runtime_manifest_models.RuntimeSideEffectClass
RuntimeSupportedChannel = runtime_manifest_models.RuntimeSupportedChannel
RuntimeAuxiliaryChannel = runtime_manifest_models.RuntimeAuxiliaryChannel
RuntimeFeatureFlagChannel = runtime_manifest_models.RuntimeFeatureFlagChannel
RuntimeDeploymentMode = runtime_manifest_models.RuntimeDeploymentMode
RuntimeEvaluationDimension = runtime_manifest_models.RuntimeEvaluationDimension
RuntimeExecutionStateField = runtime_manifest_models.RuntimeExecutionStateField
RuntimeExecutionValidityRule = runtime_manifest_models.RuntimeExecutionValidityRule
RuntimeExternalNondeterminismSource = (
    runtime_manifest_models.RuntimeExternalNondeterminismSource
)
RuntimeFailureCode = runtime_manifest_models.RuntimeFailureCode
RuntimeExecutionTransition = runtime_manifest_models.RuntimeExecutionTransition
RuntimeInvariantName = runtime_manifest_models.RuntimeInvariantName
RuntimeArtifactLineageStep = runtime_manifest_models.RuntimeArtifactLineageStep
RuntimeAdminEndpoint = runtime_manifest_models.RuntimeAdminEndpoint
RuntimeCapabilityField = runtime_manifest_models.RuntimeCapabilityField
RuntimeCapabilityRule = runtime_manifest_models.RuntimeCapabilityRule
RuntimeArtifactKind = runtime_manifest_models.RuntimeArtifactKind
RuntimeCompiledEngine = runtime_manifest_models.RuntimeCompiledEngine
RuntimeBenchmarkDiscoveryRule = runtime_manifest_models.RuntimeBenchmarkDiscoveryRule
RuntimeNonShippingRule = runtime_manifest_models.RuntimeNonShippingRule
RuntimeLayer = runtime_manifest_models.RuntimeLayer
RuntimeLineageNodeField = runtime_manifest_models.RuntimeLineageNodeField
RuntimeMemoryRegion = runtime_manifest_models.RuntimeMemoryRegion
RuntimeMemoryRule = runtime_manifest_models.RuntimeMemoryRule
RuntimeModuleId = runtime_manifest_models.RuntimeModuleId
RuntimeReleaseCondition = runtime_manifest_models.RuntimeReleaseCondition
RuntimeReleaseGateId = runtime_manifest_models.RuntimeReleaseGateId
RuntimeProofObligation = runtime_manifest_models.RuntimeProofObligation
RuntimePublicEndpoint = runtime_manifest_models.RuntimePublicEndpoint
RuntimeSignatureAlgorithm = runtime_manifest_models.RuntimeSignatureAlgorithm
RuntimeSignatureScope = runtime_manifest_models.RuntimeSignatureScope
RuntimeReleaseArtifact = runtime_manifest_models.RuntimeReleaseArtifact
RuntimeReleaseBlocker = runtime_manifest_models.RuntimeReleaseBlocker
RuntimeNondeterminismArtifact = runtime_manifest_models.RuntimeNondeterminismArtifact
RuntimeSchedulerInvariant = runtime_manifest_models.RuntimeSchedulerInvariant


def _platform_contract_payload() -> dict[str, object]:
    return deepcopy(load_platform_contract_manifest())


RuntimeSchedulerMaximizeObjective = runtime_manifest_models.RuntimeSchedulerMaximizeObjective
RuntimeSchedulerMinimizeObjective = runtime_manifest_models.RuntimeSchedulerMinimizeObjective
RuntimeSLOBudgetAppliesTo = runtime_manifest_models.RuntimeSLOBudgetAppliesTo
RuntimeSLOBudgetName = runtime_manifest_models.RuntimeSLOBudgetName
RuntimeFeatureFlagEndpoint = runtime_manifest_models.RuntimeFeatureFlagEndpoint
RuntimeThreatClass = runtime_manifest_models.RuntimeThreatClass
RuntimeThreatControl = runtime_manifest_models.RuntimeThreatControl
RuntimeThreatRule = runtime_manifest_models.RuntimeThreatRule

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


def _offline_license_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_text = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_text = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_text, public_text


def _write_sqlite_fixture(
    path: Path, rows: list[dict[str, object]], table_name: str = "orders"
) -> None:
    if not rows:
        raise ValueError("SQLite fixture requires at least one row.")
    columns = list(rows[0].keys())
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    schema = ", ".join(
        f'"{column}" REAL' if column == "revenue" else f'"{column}" TEXT' for column in columns
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


def _reload_runtime_trusted_time_module():
    module_name = "apps.runtime.trusted_time"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


REAL_MARCH_ORDERS = TEST_FILES / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
REAL_MARCH_FINANCIAL = TEST_FILES / "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"
REAL_MARCH_EMPTY = (
    TEST_FILES / "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv"
)
REAL_MARCH_INACCURATE = (
    TEST_FILES
    / "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv"
)
REAL_MARCH_RATINGS = (
    TEST_FILES
    / "3d9b2e55-c7ea-4e31-90ea-ca5797a69c2b_restaurant_rating_sku_local_2026-03-01_2026-03-31.csv"
)
REAL_LOCAL_PARQUET = TEST_FILES / ".algenta_cache" / "BookingsNew.parquet"
REAL_LOCAL_WORKBOOK = TEST_FILES / "QPL Price List_AAR_Expires 20241230.xlsx"
PUBLIC_S3_CONNECTION = {
    "type": "s3",
    "bucket": "1000genomes",
    "key": "20131219.populations.tsv",
    "region": "us-east-1",
    "anonymous": True,
    "format": "tsv",
}
PUBLIC_S3_SOURCE_REF = "s3://1000genomes/20131219.populations.tsv"
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
            raise AssertionError(
                f"Expected dict API response for {path}, received {type(payload)!r}"
            )
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


def test_runtime_api_client_shutdown_clears_global_mojo_pool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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

    plan = runtime.resolve(
        {"source_name": "orders", "metric": "revenue", "group_by": "product_line"}
    )
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
    plan = runtime.resolve(
        {"source_name": "orders", "metric": "revenue", "group_by": "product_line"}
    )

    verification = runtime.verify(plan)

    assert verification.valid is True
    assert verification.verified is True
    assert verification.resolved["metric_column"] == "revenue"


def test_runtime_local_query_with_metadata_derives_stable_metadata() -> None:
    runtime = Runtime()
    runtime.connect(_sample_rows(), name="orders")
    plan = runtime.resolve(
        {"source_name": "orders", "metric": "revenue", "group_by": "product_line"}
    )

    result = runtime.query_with_metadata(plan)

    assert isinstance(result, QueryWithMetadataOutput)
    assert isinstance(result.data, QueryOutput)
    assert result.data.result_type == "table"
    assert result.metadata.latency_ms == result.data.latency_ms
    assert result.headers == {}


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
    plan = runtime.resolve(
        {"source_name": registration.name, "metric": "revenue", "group_by": "product_line"}
    )
    result = runtime.query(plan)

    assert registration.status == "ready"
    assert registration.row_count == 3
    assert registration.name == "orders_orders"
    assert result.result[0]["product_line"] == "Electronics"
    assert result.result[0]["revenue"] == 43397221.0


def test_runtime_local_connect_sqlite_descriptor_supports_connection_string_and_query(
    tmp_path: Path,
) -> None:
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


def test_runtime_local_import_preview_uses_descriptor_origin_for_sqlite_sources(
    tmp_path: Path,
) -> None:
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


def test_runtime_local_import_bundle_preview_reports_successes_and_failures_for_real_march_corpus() -> (
    None
):
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


def test_runtime_local_hosted_limits_allow_key_bound_offline_execution_without_credit_file(
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
    future_expiry = datetime.now(UTC).timestamp() + 86_400
    token = _issue_license_jwt(
        device_id="device-runtime-keybound-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_runtime_test",
        api_key_expires_at=datetime.fromtimestamp(future_expiry, UTC),
    )
    license_mod._save_license(token)

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

    assert first.row_count > 0
    assert second.row_count > 0
    assert (tmp_path / "credits.json").exists() is False
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


def test_runtime_local_hosted_limits_recheck_offline_license_with_monotonic_time(
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
    trusted_time_mod = _reload_runtime_trusted_time_module()

    issued_at = 1_950_000_000
    wall_now = float(issued_at)
    monotonic_now = 10.0
    monkeypatch.setattr(trusted_time_mod.time, "time", lambda: wall_now)
    monkeypatch.setattr(trusted_time_mod.time, "monotonic", lambda: monotonic_now)

    token = _issue_license_jwt(
        device_id="device-runtime-monotonic-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_runtime_test",
        api_key_expires_at=datetime.fromtimestamp(issued_at + 1, UTC),
    )
    license_mod._save_license(token)
    trusted_time_mod.observe_time(float(issued_at), source="control-plane-register")
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
        monotonic_now = 10.0 + (14 * 86_400) + 5.0
        with pytest.raises(RuntimeConfigurationError, match="renew"):
            runtime.query(plan)

    assert first.row_count > 0
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


def test_runtime_local_self_hosted_private_profile_skips_hosted_license_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_DISABLE_CLOUD", "1")

    runtime = Runtime(api_key="de_live_private_key")
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
        side_effect=AssertionError("self_hosted private runtime must not hit hosted license flow"),
    ):
        result = runtime.query(plan)

    assert result.row_count > 0


def test_runtime_local_air_gapped_profile_requires_local_license(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)

    runtime = Runtime()
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

    with pytest.raises(RuntimeConfigurationError, match="local signed license"):
        runtime.query(plan)


def test_runtime_local_air_gapped_profile_accepts_offline_local_license(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "air_gapped")
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    private_key, public_key = _offline_license_keypair()
    monkeypatch.setenv("ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", public_key)

    token = jwt.encode(
        {
            "api_key_prefix": "offline",
            "device_id": "device-airgap-runtime",
            "plan": "enterprise",
            "device_limit": 0,
            "permitted_modules": ["*"],
            "issued_at": 1_900_000_000,
            "expires_at": 1_999_999_999,
            "key_expires_at": 1_999_999_999,
            "grace_days": 14,
            "iss": "algenta-offline-license",
            "sub": "device-license",
            "ver": 1,
        },
        private_key,
        algorithm="RS256",
    )
    runtime_license = _reload_runtime_license_module()
    runtime_license._save_license(token)

    runtime = Runtime()
    runtime.connect(REAL_MARCH_ORDERS, name="orders_detail")
    plan = runtime.resolve(
        {
            "source_name": "orders_detail",
            "metric": "Sales (incl. tax)",
            "group_by": "Order Channel",
        }
    )

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

    with pytest.raises(RuntimeConfigurationError, match="require an API key"):
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

    plan = runtime.resolve(
        {"source_name": "orders", "metric": "revenue", "group_by": "product_line"}
    )
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


def test_runtime_api_mode_exact_resolve_reuses_cached_source_schema_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    runtime._remember_api_registration(
        SourceRegistration(
            source_id="src_1",
            dataset_id="src_1",
            name="orders",
            status="ready",
            source_schema={"fields": ["amount", "customer"]},
            planner_schema_revision="planner_rev_1",
        )
    )

    class _FakeClient:
        def __init__(self) -> None:
            self.source_schema_calls = 0
            self.resolve_calls = 0

        def _request(self, method: str, path: str):  # type: ignore[no-untyped-def]
            assert method == "GET"
            assert path == "/v1/sources/src_1"
            self.source_schema_calls += 1
            return {"entry": {"source_schema_revision": "source_rev_1"}}

        def resolve(self, request: dict[str, object]) -> object:
            self.resolve_calls += 1
            raise AssertionError(
                f"exact runtime resolve should not hit client.resolve: {request!r}"
            )

    client = _FakeClient()
    monkeypatch.setattr(runtime, "_client", lambda: client)

    request = {
        "source_name": "orders",
        "metric": "amount",
        "group_by": "customer",
        "aggregation": "sum",
    }
    first = runtime.resolve(request)
    second = runtime.resolve(request)

    assert first.resolved_plan is not None
    assert second.resolved_plan is not None
    assert first.planner_mode == "runtime_exact_spec"
    assert second.planner_mode == "runtime_exact_spec"
    assert first.resolved_plan.schema_revision == "source_rev_1"
    assert second.resolved_plan.schema_revision == "source_rev_1"
    assert client.source_schema_calls == 1
    assert client.resolve_calls == 0


def test_runtime_api_mode_re_registration_invalidates_cached_source_schema_revision() -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    runtime._api_source_schema_revision_cache["src_1"] = "stale_rev"

    runtime._remember_api_registration(
        SourceRegistration(
            source_id="src_1",
            dataset_id="src_1",
            name="orders",
            status="ready",
            source_schema={"fields": ["amount", "customer"]},
            planner_schema_revision="planner_rev_2",
        )
    )

    assert runtime._api_source_schema_revision_cache == {}


def test_runtime_api_mode_fuzzy_resolve_skips_source_schema_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    runtime._remember_api_registration(
        SourceRegistration(
            source_id="src_1",
            dataset_id="src_1",
            name="orders",
            status="ready",
            source_schema={"fields": ["amount", "customer"]},
            planner_schema_revision="planner_rev_1",
        )
    )
    captured_resolve: list[dict[str, object]] = []

    class _FakeClient:
        def _request(self, method: str, path: str):  # type: ignore[no-untyped-def]
            raise AssertionError(
                f"fuzzy runtime resolve must not fetch source schema revision: {method} {path}"
            )

        def resolve(self, request: dict[str, object]) -> object:
            captured_resolve.append(request)
            return SimpleNamespace(
                model_dump=lambda: {
                    "resolved_plan": {
                        "source_name": "orders",
                        "metric_column": "amount",
                        "aggregation": "sum",
                        "group_column": "customer",
                        "schema_revision": "schema_123",
                        "constraints": {},
                        "order": "desc",
                    },
                    "confidence": 0.91,
                    "plan": ["Use source 'orders'."],
                    "explanation": ["Resolved fuzzy metric 'gross_revenue' to 'amount'."],
                    "latency_ms": 12.5,
                    "decision_path": "schema_match",
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
                    "resolved_column": "amount",
                    "resolved_role": "measure",
                    "candidates": [],
                    "source_scores": {"orders": 1.0},
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    resolved = runtime.resolve(
        {
            "source_name": "orders",
            "metric": "gross_revenue",
            "group_by": "customer",
            "aggregation": "sum",
        }
    )

    assert resolved.resolved_plan is not None
    assert resolved.planner_mode == "runtime"
    assert captured_resolve == [
        {
            "preferred_source": "orders",
            "allow_org_scope": True,
            "metric": {"role": "metric", "hint": "gross_revenue"},
            "group_by": ["customer"],
            "aggregation": "sum",
        }
    ]


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


def test_runtime_api_mode_query_metadata_batch_and_sql_report_use_typed_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    seen: dict[str, object] = {}

    class _FakeClient:
        def query_with_metadata(self, request: dict[str, object]) -> object:
            seen["query_with_metadata"] = request
            return SimpleNamespace(
                model_dump=lambda: {
                    "data": {
                        "result": {"value": 97.2},
                        "result_type": "scalar",
                        "confidence": 1.0,
                        "plan": ["Execute exact plan."],
                        "resolved_column": "otp_rate",
                        "resolved_role": "metric",
                        "resolved_source": "otp_events",
                        "row_count": 1,
                        "ambiguous": False,
                        "exact_spec": True,
                        "explanation": ["Executed deterministic query."],
                        "latency_ms": 12.3,
                        "decision_path": "exact_spec",
                        "plan_hash": "plan_otp",
                        "validated": True,
                        "deterministic_scope": "api_registered_source",
                        "confidence_source": "exact_execution",
                        "request_id": "req_query",
                    },
                    "metadata": {
                        "request_id": "req_query",
                        "latency_ms": 12.3,
                        "tokens_in": 120,
                        "tokens_out": 14,
                        "cost_usd": 0.0042,
                        "cache_hit": True,
                    },
                    "headers": {"x-request-id": "req_query"},
                }
            )

        def query_batch(self, request: dict[str, object]) -> object:
            seen["query_batch"] = request
            return SimpleNamespace(
                model_dump=lambda: {
                    "request_id": "req_batch",
                    "results": [
                        {
                            "key": "overall_otp",
                            "data": {
                                "result": {"value": 97.2},
                                "result_type": "scalar",
                                "confidence": 1.0,
                                "plan": ["Execute exact plan."],
                                "resolved_column": "otp_rate",
                                "resolved_role": "metric",
                                "resolved_source": "otp_events",
                                "row_count": 1,
                                "ambiguous": False,
                                "exact_spec": True,
                                "explanation": ["Executed deterministic query."],
                                "latency_ms": 12.3,
                                "decision_path": "exact_spec",
                                "plan_hash": "plan_otp",
                                "validated": True,
                                "deterministic_scope": "api_registered_source",
                                "confidence_source": "exact_execution",
                                "request_id": "req_batch_item",
                            },
                            "metadata": {
                                "request_id": "req_batch_item",
                                "latency_ms": 12.3,
                            },
                        },
                        {
                            "key": "avg_delay",
                            "error": {
                                "code": "metric_not_found",
                                "message": "Metric average_delay_minutes was not found.",
                                "details": {"metric": "average_delay_minutes"},
                            },
                        },
                    ],
                }
            )

        def query_sql_report(self, request: dict[str, object]) -> object:
            seen["query_sql_report"] = request
            return SimpleNamespace(
                model_dump=lambda: {
                    "columns": ["flight_month", "otp_rate_pct"],
                    "rows": [{"flight_month": "2026-04-01", "otp_rate_pct": 97.2}],
                    "row_count": 1,
                    "truncated": False,
                    "request_id": "req_report",
                    "latency_ms": 8.5,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with_metadata = runtime.query_with_metadata(
        {"dataset_id": "otp_events", "metric": {"role": "metric", "hint": "otp_rate"}}
    )
    batch = runtime.query_batch(
        {
            "defaults": {"dataset_id": "otp_events"},
            "queries": [
                {
                    "key": "overall_otp",
                    "request": {"metric": {"role": "metric", "hint": "otp_rate"}},
                },
                {
                    "key": "avg_delay",
                    "request": {
                        "metric": {"role": "metric", "hint": "average_delay_minutes"},
                    },
                },
            ],
        }
    )
    report = runtime.query_sql_report(
        {
            "sources": [{"dataset_id": "otp_events", "alias": "otp"}],
            "sql": "select flight_month, otp_rate_pct from otp",
            "max_rows": 100,
        }
    )

    assert isinstance(with_metadata, QueryWithMetadataOutput)
    assert with_metadata.metadata.tokens_in == 120
    assert with_metadata.headers["x-request-id"] == "req_query"
    assert isinstance(batch, QueryBatchOutput)
    assert batch.results[0].data is not None
    assert batch.results[1].error is not None
    assert batch.results[1].error.code == "metric_not_found"
    assert isinstance(report, QuerySqlReportOutput)
    assert report.columns == ["flight_month", "otp_rate_pct"]
    assert seen["query_with_metadata"] == {
        "dataset_id": "otp_events",
        "metric": {"role": "metric", "hint": "otp_rate"},
    }
    assert seen["query_batch"] == {
        "defaults": {"dataset_id": "otp_events"},
        "queries": [
            {"key": "overall_otp", "request": {"metric": {"role": "metric", "hint": "otp_rate"}}},
            {
                "key": "avg_delay",
                "request": {"metric": {"role": "metric", "hint": "average_delay_minutes"}},
            },
        ],
    }
    assert seen["query_sql_report"] == {
        "sources": [{"dataset_id": "otp_events", "alias": "otp"}],
        "sql": "select flight_month, otp_rate_pct from otp",
        "max_rows": 100,
    }


def test_runtime_api_mode_get_contract_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    expected_payload = _platform_contract_payload()

    class _FakeClient:
        def get_contract(self) -> object:
            return SimpleNamespace(model_dump=lambda: expected_payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    contract = runtime.get_contract()

    assert isinstance(contract, PlatformContractOutput)
    assert contract.primary_data_query_contract["api"]["contract_endpoint"] == "/v1/meta/contract"
    assert contract.primary_data_query_contract["mcp"]["contract_tool"] == "get_contract"
    assert_manifest_backed_integrations(contract.integrations)


def test_runtime_api_mode_get_contract_rejects_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def get_contract(self) -> object:
            def _payload() -> dict[str, object]:
                payload = _platform_contract_payload()
                payload["api_key_prefixes"] = {"live": "de_live_"}
                return payload

            return SimpleNamespace(model_dump=_payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()
    assert exc.value.code == "invalid_contract_payload"


def test_runtime_api_mode_get_contract_rejects_invalid_nested_contract_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def get_contract(self) -> object:
            def _payload() -> dict[str, object]:
                payload = _platform_contract_payload()
                payload["primary_data_query_contract"]["recommended_flows"].pop(
                    "machine_readable_contract"
                )
                return payload

            return SimpleNamespace(model_dump=_payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()
    assert exc.value.code == "invalid_contract_payload"


def test_runtime_api_mode_get_contract_rejects_invalid_typed_contract_model_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision_engine = importlib.import_module("decision_engine")
    typed_payload = decision_engine.PlatformContractResult.model_validate(
        _platform_contract_payload()
    ).model_copy(
        update={
            "defaults": {
                "read_only_default": "nope",
                "write_confirmation_required": True,
                "plan_limits": {},
            }
        }
    )
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def get_contract(self) -> object:
            return typed_payload

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
            runtime.get_contract()

    assert caught == []
    assert exc.value.code == "invalid_contract_payload"


def test_runtime_api_mode_get_contract_rejects_tuple_backed_contract_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def get_contract(self) -> object:
            payload = _platform_contract_payload()
            payload["compatibility"]["legacy_headers"] = ("X-Deprecated-Key",)
            return payload

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()

    assert exc.value.code == "invalid_contract_payload"
    assert exc.value.details["cause"] == "compatibility.legacy_headers"
    assert exc.value.validation_errors[0]["message"] == "must be a list of non-empty strings."


def test_runtime_api_mode_get_contract_normalizes_client_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeContractError(Exception):
        def __init__(self) -> None:
            super().__init__("OpenAPI contract fallback is missing x-primary-data-query-contract.")
            self.error_code = "contract_extension_missing"

    class _FakeClient:
        def get_contract(self) -> object:
            raise _FakeContractError()

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()
    assert exc.value.code == "invalid_contract_payload"
    assert exc.value.details["source_error_code"] == "contract_extension_missing"


def test_runtime_validation_error_exposes_field_errors_from_direct_details() -> None:
    exc = RuntimeValidationError(
        "invalid_runtime_contract_payload",
        "invalid signed payload",
        {
            "cause": "proof_matrix.0.status",
            "validation_errors": [
                {
                    "path": "proof_matrix.0.status",
                    "message": "Input should be a valid enum value",
                    "type": "enum",
                }
            ],
        },
    )

    assert exc.validation_errors == [
        {
            "path": "proof_matrix.0.status",
            "message": "Input should be a valid enum value",
            "type": "enum",
        }
    ]
    assert exc.field_errors == exc.validation_errors


def test_runtime_api_mode_get_contract_preserves_upstream_contract_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeContractError(Exception):
        def __init__(self) -> None:
            super().__init__(
                "OpenAPI contract fallback returned an invalid payload: "
                "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
            )
            self.error_code = "invalid_contract_payload"
            self.status_code = 0
            self.details = {
                "cause": "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
                "validation_errors": [
                    {
                        "path": (
                            "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
                        ),
                        "message": "Field required",
                        "type": "missing",
                    }
                ],
            }

    class _FakeClient:
        def get_contract(self) -> object:
            raise _FakeContractError()

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()
    assert exc.value.code == "invalid_contract_payload"
    assert exc.value.details["source_error_code"] == "invalid_contract_payload"
    assert exc.value.details["source_status_code"] == 0
    assert exc.value.details["source_error_details"] == {
        "cause": "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
        "validation_errors": [
            {
                "path": "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
                "message": "Field required",
                "type": "missing",
            }
        ],
    }
    assert exc.value.validation_errors[0]["path"] == (
        "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    )
    assert exc.value.field_errors[0]["path"] == (
        "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    )


@pytest.mark.parametrize(
    ("method_name", "client_method_name"),
    [
        ("get_runtime_manifest", "get_runtime_manifest"),
        ("get_runtime_modules", "get_runtime_modules"),
        ("get_runtime_benchmarks", "get_runtime_benchmarks"),
        ("get_runtime_release_validation", "get_runtime_release_validation"),
    ],
)
def test_runtime_api_mode_runtime_proof_surfaces_normalize_client_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    client_method_name: str,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeRuntimeProofError(Exception):
        def __init__(self) -> None:
            super().__init__("signed runtime proof payload is invalid")
            self.error_code = "invalid_runtime_contract_payload"

    class _FakeClient:
        def __getattr__(self, name: str):
            if name != client_method_name:
                raise AttributeError(name)

            def _raise_error() -> object:
                raise _FakeRuntimeProofError()

            return _raise_error

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc:
        getattr(runtime, method_name)()
    assert exc.value.code == "invalid_runtime_contract_payload"
    assert exc.value.details["source_error_code"] == "invalid_runtime_contract_payload"


@pytest.mark.parametrize(
    ("method_name", "client_method_name"),
    [
        ("get_runtime_manifest", "get_runtime_manifest"),
        ("get_runtime_modules", "get_runtime_modules"),
        ("get_runtime_benchmarks", "get_runtime_benchmarks"),
        ("get_runtime_release_validation", "get_runtime_release_validation"),
    ],
)
def test_runtime_api_mode_runtime_proof_surfaces_preserve_upstream_error_details(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    client_method_name: str,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeRuntimeProofError(Exception):
        def __init__(self) -> None:
            super().__init__(f"{method_name}.proof_matrix[0].status invalid")
            self.error_code = "invalid_runtime_contract_payload"
            self.status_code = 0
            self.details = {
                "cause": f"{method_name}.proof_matrix[0].status",
                "validation_errors": [
                    {
                        "path": f"{method_name}.proof_matrix[0].status",
                        "message": "Input should be a valid enum value",
                        "type": "enum",
                    }
                ],
            }

    class _FakeClient:
        def __getattr__(self, name: str):
            if name != client_method_name:
                raise AttributeError(name)

            def _raise_error() -> object:
                raise _FakeRuntimeProofError()

            return _raise_error

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc:
        getattr(runtime, method_name)()
    assert exc.value.code == "invalid_runtime_contract_payload"
    assert exc.value.details["source_error_code"] == "invalid_runtime_contract_payload"
    assert exc.value.details["source_status_code"] == 0
    assert exc.value.details["source_error_details"] == {
        "cause": f"{method_name}.proof_matrix[0].status",
        "validation_errors": [
            {
                "path": f"{method_name}.proof_matrix[0].status",
                "message": "Input should be a valid enum value",
                "type": "enum",
            }
        ],
    }
    assert exc.value.validation_errors[0]["path"] == f"{method_name}.proof_matrix[0].status"
    assert exc.value.field_errors[0]["path"] == f"{method_name}.proof_matrix[0].status"


def test_runtime_api_mode_get_runtime_manifest_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    manifest_payload = get_runtime_manifest().model_dump(mode="json")

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: manifest_payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    manifest = runtime.get_runtime_manifest()

    assert isinstance(manifest, RuntimeManifestOutput)
    assert manifest.shipping_contract.module_count == 22
    assert manifest.modules[0].name == "bpe_tokenizer"
    assert isinstance(manifest.modules[0].maturity, RuntimeMaturity)
    assert manifest.modules[0].maturity is RuntimeMaturity.channel_covered
    assert manifest.modules[0].public_supported_channels[0] is RuntimeSupportedChannel.python_sdk
    assert (
        manifest.modules[0].validated_auxiliary_channels[0]
        is RuntimeAuxiliaryChannel.daemon_client
    )
    assert (
        manifest.modules[0].feature_flag_channels[0]
        is RuntimeFeatureFlagChannel.http_api_feature_flag
    )
    assert manifest.system_invariants[0].name is RuntimeInvariantName.manifest_truth
    assert manifest.execution_model.state_fields[0] is RuntimeExecutionStateField.request
    assert manifest.execution_model.validity_rules[0] is RuntimeExecutionValidityRule.schema_valid
    assert (
        manifest.execution_model.allowed_transitions[0]
        is RuntimeExecutionTransition.model_call_started
    )
    assert (
        manifest.external_nondeterminism.sources[0]
        is RuntimeExternalNondeterminismSource.provider_responses
    )
    assert (
        manifest.external_nondeterminism.required_artifacts[0]
        is RuntimeNondeterminismArtifact.provider_response_record
    )
    assert manifest.external_nondeterminism.failure_codes[0] is RuntimeFailureCode.replay_mismatch
    assert manifest.artifact_lineage.artifact_flow[0] is RuntimeArtifactLineageStep.input
    assert manifest.artifact_lineage.required_node_fields[0] is RuntimeLineageNodeField.node_id
    assert manifest.capability_algebra.required_fields[0] is RuntimeCapabilityField.tool_name
    assert (
        manifest.capability_algebra.rules[0]
        is RuntimeCapabilityRule.mcp_tools_are_untrusted_by_default
    )
    assert manifest.modules[0].name is RuntimeModuleId.bpe_tokenizer
    assert manifest.modules[0].promotion_status.value == "shipping"
    assert isinstance(manifest.capability_algebra.enums.side_effect_class[0], RuntimeSideEffectClass)
    assert isinstance(manifest.capability_algebra.enums.risk_level[-1], RuntimeRiskLevel)
    assert manifest.capability_algebra.enums.risk_level[-1] is RuntimeRiskLevel.critical
    assert isinstance(manifest.capability_algebra.enums.replayability[0], RuntimeReplayability)
    assert manifest.modules[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert manifest.shipping_contract.runtime_core_layer is RuntimeLayer.mojo_llm_runtime_core
    assert (
        manifest.shipping_contract.benchmark_discovery_rule
        is RuntimeBenchmarkDiscoveryRule.shipping_llm_rollout_only
    )
    assert (
        manifest.benchmark_discovery_lane.non_shipping_rule
        is RuntimeNonShippingRule.broader_mojo_inventory_not_advertised
    )
    assert len(manifest.benchmark_discovery_lane.discovered_source_inventory) == (
        manifest.benchmark_discovery_lane.discovered_source_modules
    )
    assert sum(
        entry.public_function_count
        for entry in manifest.benchmark_discovery_lane.discovered_source_inventory
    ) == manifest.benchmark_discovery_lane.discovered_public_functions
    assert manifest.modules[0].name.value in {
        entry.import_path for entry in manifest.benchmark_discovery_lane.discovered_source_inventory
    }
    assert manifest.modules[0].proof_obligations[0] is RuntimeProofObligation.numerical_parity
    assert manifest.proof_matrix[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert isinstance(manifest.proof_matrix[0].status, RuntimeMaturity)
    assert manifest.proof_matrix[0].status is RuntimeMaturity.channel_covered
    assert manifest.proof_matrix[0].obligations[0] is RuntimeProofObligation.numerical_parity
    assert manifest.maturity[RuntimeModuleId.bpe_tokenizer] is RuntimeMaturity.channel_covered
    assert manifest.supported_channels[0] is RuntimeSupportedChannel.python_sdk
    assert manifest.validated_auxiliary_channels[0] is RuntimeAuxiliaryChannel.daemon_client
    assert (
        manifest.feature_flag_channels[0]
        is RuntimeFeatureFlagChannel.http_api_feature_flag
    )
    assert manifest.deployment_mode is RuntimeDeploymentMode.local_dev_daemon
    assert manifest.deployment_modes.current is RuntimeDeploymentMode.local_dev_daemon
    assert manifest.deployment_modes.supported_modes[0] is RuntimeDeploymentMode.saas
    assert manifest.benchmarking.classes[0].code is RuntimeBenchmarkClassCode.microkernel_latency
    assert any(
        entry.code is RuntimeBenchmarkClassCode.provider_routing_overhead
        and entry.description == "provider routing overhead"
        and entry.evidence_paths
        == [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ]
        for entry in manifest.benchmarking.classes
    )
    assert any(
        entry.code is RuntimeBenchmarkClassCode.checkpoint_replay_overhead
        and entry.description == "checkpoint and replay overhead"
        and entry.evidence_paths == []
        for entry in manifest.benchmarking.classes
    )
    assert manifest.benchmarking.required_metrics[0] is RuntimeBenchmarkMetric.p50
    assert manifest.benchmarking.baselines[-1] is RuntimeBenchmarkBaseline.algenta_mojo_native_path
    assert manifest.slo_budgets[0].name is RuntimeSLOBudgetName.runtime_manifest_load
    assert (
        manifest.slo_budgets[0].applies_to
        is RuntimeSLOBudgetAppliesTo.first_party_runtime_manifest_route
    )
    assert manifest.scheduler_model.policies[0] is RuntimeSchedulerPolicy.fifo
    assert manifest.scheduler_model.minimize[0] is RuntimeSchedulerMinimizeObjective.tail_latency
    assert (
        manifest.scheduler_model.maximize[0]
        is RuntimeSchedulerMaximizeObjective.gpu_or_cpu_utilization
    )
    assert (
        manifest.scheduler_model.invariants[0]
        is RuntimeSchedulerInvariant.no_request_starves_indefinitely
    )
    assert manifest.memory_model.regions[0] is RuntimeMemoryRegion.model_weights
    assert manifest.memory_model.rules[0] is RuntimeMemoryRule.kv_pages_are_tenant_scoped
    assert manifest.memory_model.failure_codes[0] is RuntimeFailureCode.kv_cache_exhausted
    assert manifest.evaluation_science.dimensions[0] is RuntimeEvaluationDimension.answer_correctness
    assert manifest.evaluation_science.methods[0] is RuntimeEvaluationMethod.bootstrap_confidence_intervals
    assert (
        manifest.evaluation_science.release_blockers[0]
        is RuntimeReleaseBlocker.replay_success_regression
    )
    assert manifest.typed_failures[0].code is RuntimeFailureCode.provider_timeout
    assert manifest.threat_model.threat_classes[0] is RuntimeThreatClass.prompt_injection
    assert manifest.threat_model.controls[0] is RuntimeThreatControl.tool_allowlists
    assert (
        manifest.threat_model.non_negotiable_rules[0]
        is RuntimeThreatRule.mcp_tools_are_untrusted_by_default
    )
    assert (
        manifest.release_artifact_bundle.required_artifacts[0]
        is RuntimeReleaseArtifact.signed_runtime_manifest
    )
    assert manifest.release_gates[0].gate is RuntimeReleaseGateId.gate_a
    assert manifest.immediate_implementation_sequence[0].pr == "PR 0"
    assert manifest.compiled_artifacts[0].kind is RuntimeArtifactKind.proof_bundle
    assert manifest.signature.algorithm is RuntimeSignatureAlgorithm.hmac_sha256
    assert manifest.signature.scope is RuntimeSignatureScope.control_plane_hmac_v1
    assert manifest.advertised_capabilities.runtime_modules[0] is RuntimeModuleId.bpe_tokenizer
    assert (
        manifest.advertised_capabilities.public_endpoints[0]
        is RuntimePublicEndpoint.meta_contract
    )
    assert (
        manifest.advertised_capabilities.admin_endpoints[0]
        is RuntimeAdminEndpoint.runtime_modules
    )
    assert (
        manifest.advertised_capabilities.feature_flag_endpoints[0]
        is RuntimeFeatureFlagEndpoint.libraries
    )
    assert manifest.to_dict()["supported_channels"][0] == "python_sdk"
    assert manifest.to_dict()["deployment_mode"] == "local_dev_daemon"
    assert manifest.to_dict()["maturity"]["bpe_tokenizer"] == "channel_covered"


def test_runtime_api_mode_get_runtime_modules_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_modules().model_dump(mode="json")

    class _FakeClient:
        def get_runtime_modules(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    modules = runtime.get_runtime_modules()

    assert isinstance(modules, RuntimeAdminModulesOutput)
    assert modules.summary.module_count == 22
    assert modules.modules[0].name == "bpe_tokenizer"
    assert modules.modules[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert modules.modules[0].maturity is RuntimeMaturity.channel_covered
    assert modules.modules[0].public_supported_channels[0] is RuntimeSupportedChannel.python_sdk
    assert modules.summary.maturity_counts[RuntimeMaturity.channel_covered] == 22
    assert modules.summary.layer_counts[RuntimeLayer.mojo_llm_runtime_core] == 22
    assert modules.proof_matrix[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert modules.modules[0].proof_obligations[0] is RuntimeProofObligation.numerical_parity
    assert modules.proof_matrix[0].obligations[0] is RuntimeProofObligation.numerical_parity
    assert modules.proof_matrix[0].status is RuntimeMaturity.channel_covered
    assert (
        modules.shipping_contract.benchmark_discovery_rule
        is RuntimeBenchmarkDiscoveryRule.shipping_llm_rollout_only
    )
    assert modules.to_dict()["modules"][0]["maturity"] == "channel_covered"


def test_runtime_api_mode_get_runtime_benchmarks_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    benchmarks = runtime.get_runtime_benchmarks()

    assert isinstance(benchmarks, RuntimeAdminBenchmarksOutput)
    assert benchmarks.module_benchmarks[0].name is RuntimeModuleId.bpe_tokenizer
    assert benchmarks.module_benchmarks[0].function_count > 0
    assert (
        benchmarks.benchmark_discovery_lane.non_shipping_rule
        is RuntimeNonShippingRule.broader_mojo_inventory_not_advertised
    )
    assert len(benchmarks.benchmark_discovery_lane.discovered_source_inventory) == (
        benchmarks.benchmark_discovery_lane.discovered_source_modules
    )
    assert sum(
        entry.public_function_count
        for entry in benchmarks.benchmark_discovery_lane.discovered_source_inventory
    ) == benchmarks.benchmark_discovery_lane.discovered_public_functions
    assert benchmarks.shipping_runtime_modules[0] is RuntimeModuleId.bpe_tokenizer
    assert benchmarks.shipping_runtime_function_counts[0] == benchmarks.module_benchmarks[0].function_count
    assert (
        benchmarks.shipping_runtime_benchmark_artifacts[0]
        == benchmarks.module_benchmarks[0].benchmark_artifact
    )
    assert (
        benchmarks.shipping_runtime_compiled_artifacts[0]
        == benchmarks.module_benchmarks[0].compiled_artifact
    )
    assert benchmarks.compiled_artifacts[0].kind is RuntimeArtifactKind.proof_bundle
    assert benchmarks.module_benchmarks[0].compiled_engine is RuntimeCompiledEngine.mojo
    assert (
        benchmarks.shipping_runtime_compiled_engines[0]
        == benchmarks.module_benchmarks[0].compiled_engine
    )
    assert benchmarks.evaluation_science.dimensions[0] is RuntimeEvaluationDimension.answer_correctness
    assert (
        benchmarks.quality_gate_benchmark_classes[0].code
        is RuntimeBenchmarkClassCode.checkpoint_replay_overhead
    )
    assert any(
        entry.code is RuntimeBenchmarkClassCode.decision_workflow_completion_latency
        and entry.description == "decision workflow completion latency"
        and entry.evidence_paths
        == [
            "build/repository_intelligence_benchmark.json",
            "benchmarks/repository_intelligence_benchmark.py",
            "tests/test_repository_intelligence_benchmark.py",
        ]
        for entry in benchmarks.quality_gate_benchmark_classes
    )
    assert {entry.code.value for entry in benchmarks.quality_gate_benchmark_classes} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert [entry.name.value for entry in benchmarks.quality_gate_slo_budgets] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert benchmarks.evaluation_summary.replay_gate_enabled is True
    assert benchmarks.evaluation_summary.tool_call_quality_gate_enabled is True
    assert benchmarks.evaluation_summary.rag_quality_gate_enabled is True
    assert benchmarks.evaluation_summary.decision_quality_gate_enabled is True
    assert benchmarks.shipping_runtime_max_cold_ms[0] == benchmarks.module_benchmarks[0].max_cold_ms
    assert benchmarks.shipping_runtime_max_warm_ms[0] == benchmarks.module_benchmarks[0].max_warm_ms
    assert benchmarks.shipping_runtime_max_hot_ms[0] == benchmarks.module_benchmarks[0].max_hot_ms
    assert (
        benchmarks.benchmarking.classes[0].code
        is RuntimeBenchmarkClassCode.microkernel_latency
    )
    assert any(
        entry.code is RuntimeBenchmarkClassCode.provider_routing_overhead
        and entry.description == "provider routing overhead"
        and entry.evidence_paths
        == [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ]
        for entry in benchmarks.benchmarking.classes
    )
    assert benchmarks.benchmarking.required_metrics[0] is RuntimeBenchmarkMetric.p50
    assert benchmarks.benchmarking.baselines[-1] is RuntimeBenchmarkBaseline.algenta_mojo_native_path
    assert (
        benchmarks.slo_budgets[0].applies_to
        is RuntimeSLOBudgetAppliesTo.first_party_runtime_manifest_route
    )
    assert benchmarks.signature.scope is RuntimeSignatureScope.control_plane_hmac_v1


def test_runtime_api_mode_get_runtime_release_validation_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_release_validation().model_dump(mode="json")

    class _FakeClient:
        def get_runtime_release_validation(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    validation = runtime.get_runtime_release_validation()

    assert isinstance(validation, RuntimeReleaseValidationOutput)
    assert validation.valid_release is True
    assert validation.conditions[0].condition is RuntimeReleaseCondition.manifest_listed
    assert validation.deployment_mode is RuntimeDeploymentMode.local_dev_daemon
    assert validation.deployment_mode_raw == "local_dev_daemon"
    assert validation.conditions[0].evidence_paths[0] == "/v1/runtime/manifest"


def test_runtime_api_mode_get_runtime_release_validation_rejects_boolean_coercion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["valid_release"] = "yes"
    payload["conditions"][0]["satisfied"] = "no"

    class _FakeClient:
        def get_runtime_release_validation(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_release_validation()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "conditions.0.satisfied"
    assert exc_info.value.validation_errors[0]["path"] == "conditions.0.satisfied"
    assert exc_info.value.field_errors[0]["message"] == "must be a boolean."


def test_runtime_api_mode_get_runtime_manifest_rejects_tuple_backed_supported_channels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"] = ("python_sdk", "typescript_sdk", "cli", "mcp")

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "supported_channels"
    assert exc_info.value.field_errors[0]["message"] == "must be a list."


def test_runtime_api_mode_get_runtime_manifest_rejects_duplicate_release_conditions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["formal_release_theorem"]["required_conditions"].append("manifest-listed")

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == (
        "formal_release_theorem.required_conditions"
    )
    assert exc_info.value.field_errors[0]["path"] == "formal_release_theorem.required_conditions"


def test_runtime_api_mode_get_runtime_manifest_rejects_duplicate_module_public_channels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["public_supported_channels"].append("python_sdk")

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "modules.0.public_supported_channels"
    assert exc_info.value.field_errors[0]["path"] == "modules.0.public_supported_channels"


def test_runtime_api_mode_get_runtime_manifest_rejects_duplicate_module_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["functions"].append(payload["modules"][0]["functions"][0])

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "modules.0.functions"
    assert exc_info.value.field_errors[0]["path"] == "modules.0.functions"


def test_runtime_api_mode_get_runtime_manifest_rejects_invalid_artifact_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["compiled_artifacts"][0]["kind"] = "ghost_bundle"

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "compiled_artifacts.0.kind"
    assert exc_info.value.field_errors[0]["path"] == "compiled_artifacts.0.kind"


def test_runtime_api_mode_get_runtime_manifest_rejects_invalid_benchmark_discovery_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )
    assert (
        exc_info.value.field_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )


def test_runtime_api_mode_get_runtime_manifest_rejects_benchmark_shipping_function_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_functions"] += 1

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == (
        "benchmark_discovery_lane.shipping_manifest_functions"
    )
    assert exc_info.value.field_errors[0]["path"] == (
        "benchmark_discovery_lane.shipping_manifest_functions"
    )


def test_runtime_api_mode_get_runtime_modules_rejects_duplicate_proof_matrix_layers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"].append(dict(payload["proof_matrix"][0]))

    class _FakeClient:
        def get_runtime_modules(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_modules()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "proof_matrix"
    assert exc_info.value.field_errors[0]["path"] == "proof_matrix"


def test_runtime_api_mode_get_runtime_modules_rejects_invalid_benchmark_discovery_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    class _FakeClient:
        def get_runtime_modules(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_modules()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )
    assert (
        exc_info.value.field_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )


def test_runtime_api_mode_get_runtime_modules_rejects_summary_function_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["function_count"] += 1

    class _FakeClient:
        def get_runtime_modules(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_modules()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "summary.function_count"
    assert exc_info.value.field_errors[0]["path"] == "summary.function_count"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_duplicate_benchmark_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmarking"]["classes"].append(dict(payload["benchmarking"]["classes"][0]))

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "benchmarking.classes"
    assert exc_info.value.field_errors[0]["path"] == "benchmarking.classes"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_function_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_function_counts"][0] += 1

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_function_counts.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_function_counts.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_module_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_modules"][0], payload["shipping_runtime_modules"][1] = (
        payload["shipping_runtime_modules"][1],
        payload["shipping_runtime_modules"][0],
    )

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_modules.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_modules.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_quality_gate_summary_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"]["benchmark_class_count"] += 1

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "evaluation_summary.benchmark_class_count"
    assert exc_info.value.field_errors[0]["path"] == "evaluation_summary.benchmark_class_count"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_missing_discovered_shipping_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    discovery_index = next(
        index
        for index, entry in enumerate(payload["benchmark_discovery_lane"]["discovered_source_inventory"])
        if entry["import_path"] == payload["module_benchmarks"][0]["name"]
    )
    replacement_import_path = f"{payload['module_benchmarks'][0]['name']}_shadow"
    payload["benchmark_discovery_lane"]["discovered_source_inventory"][discovery_index][
        "import_path"
    ] = replacement_import_path

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "benchmark_discovery_lane.discovered_source_inventory"
    )
    assert (
        exc_info.value.field_errors[0]["path"]
        == "benchmark_discovery_lane.discovered_source_inventory"
    )


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_benchmark_artifact_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_artifacts"][0], payload["shipping_runtime_benchmark_artifacts"][1] = (
        payload["shipping_runtime_benchmark_artifacts"][1],
        payload["shipping_runtime_benchmark_artifacts"][0],
    )

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_benchmark_artifacts.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_benchmark_artifacts.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_compiled_artifact_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_artifacts"][0] = "build/mismatched-runtime-compiled-artifact.json"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_artifacts.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_compiled_artifacts.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_compiled_engine_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_engines"][0] = "python_fallback"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_engines.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_compiled_engines.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_invalid_slo_budget_applies_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["slo_budgets"][0]["applies_to"] = "shadow_realm_lane"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "slo_budgets.0.applies_to"
    assert exc_info.value.field_errors[0]["path"] == "slo_budgets.0.applies_to"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_invalid_non_shipping_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "benchmark_discovery_lane.non_shipping_rule"
    )
    assert (
        exc_info.value.field_errors[0]["path"]
        == "benchmark_discovery_lane.non_shipping_rule"
    )


@pytest.mark.parametrize(
    ("shipping_field", "benchmark_field"),
    [
        ("shipping_runtime_max_cold_ms", "max_cold_ms"),
        ("shipping_runtime_max_warm_ms", "max_warm_ms"),
        ("shipping_runtime_max_hot_ms", "max_hot_ms"),
    ],
)
def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_latency_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    shipping_field: str,
    benchmark_field: str,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload[shipping_field][0] = payload["module_benchmarks"][0][benchmark_field] + 1.0

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == f"{shipping_field}.0"
    assert exc_info.value.field_errors[0]["path"] == f"{shipping_field}.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_duplicate_compiled_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["compiled_artifacts"].append(dict(payload["compiled_artifacts"][0]))

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "compiled_artifacts"
    assert exc_info.value.field_errors[0]["path"] == "compiled_artifacts"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_missing_compiled_artifact_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_artifact"] = "build/missing-runtime-benchmark.json"
    payload["shipping_runtime_compiled_artifacts"][0] = "build/missing-runtime-benchmark.json"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "module_benchmarks.0.compiled_artifact"
    assert exc_info.value.field_errors[0]["path"] == "module_benchmarks.0.compiled_artifact"


def test_runtime_api_mode_get_runtime_release_validation_rejects_duplicate_condition_evidence_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["evidence_paths"].append(payload["conditions"][0]["evidence_paths"][0])

    class _FakeClient:
        def get_runtime_release_validation(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_release_validation()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "conditions.0.evidence_paths"
    assert exc_info.value.field_errors[0]["path"] == "conditions.0.evidence_paths"


def test_runtime_api_mode_runtime_proof_surfaces_fail_closed_on_invalid_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import (
        get_runtime_admin_benchmarks,
        get_runtime_admin_modules,
        get_runtime_manifest,
        get_runtime_release_validation,
    )

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    invalid_manifest = get_runtime_manifest().model_dump(mode="json")
    invalid_manifest["maturity"]["bpe_tokenizer"] = "legendary"

    invalid_modules = get_runtime_admin_modules().model_dump(mode="json")
    invalid_modules["proof_matrix"][0]["status"] = "unknown_status"

    invalid_benchmarks = get_runtime_admin_benchmarks().model_dump(mode="json")
    invalid_benchmarks["module_benchmarks"][0]["compiled_engine"] = "warp_core"

    invalid_validation = get_runtime_release_validation().model_dump(mode="json")
    invalid_validation["conditions"][0]["condition"] = "teleport-validated"

    class _FakeClient:
        def __init__(self, payload: dict[str, object], method: str) -> None:
            self._payload = payload
            self._method = method

        def get_runtime_manifest(self) -> object:
            if self._method != "manifest":
                raise AssertionError("unexpected manifest call")
            return SimpleNamespace(model_dump=lambda: self._payload)

        def get_runtime_modules(self) -> object:
            if self._method != "modules":
                raise AssertionError("unexpected modules call")
            return SimpleNamespace(model_dump=lambda: self._payload)

        def get_runtime_benchmarks(self) -> object:
            if self._method != "benchmarks":
                raise AssertionError("unexpected benchmarks call")
            return SimpleNamespace(model_dump=lambda: self._payload)

        def get_runtime_release_validation(self) -> object:
            if self._method != "validation":
                raise AssertionError("unexpected validation call")
            return SimpleNamespace(model_dump=lambda: self._payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient(invalid_manifest, "manifest"))
    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as manifest_exc:
        runtime.get_runtime_manifest()
    assert manifest_exc.value.code == "invalid_runtime_contract_payload"

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient(invalid_modules, "modules"))
    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as modules_exc:
        runtime.get_runtime_modules()
    assert modules_exc.value.code == "invalid_runtime_contract_payload"

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient(invalid_benchmarks, "benchmarks"))
    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as benchmarks_exc:
        runtime.get_runtime_benchmarks()
    assert benchmarks_exc.value.code == "invalid_runtime_contract_payload"

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient(invalid_validation, "validation"))
    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as validation_exc:
        runtime.get_runtime_release_validation()
    assert validation_exc.value.code == "invalid_runtime_contract_payload"


def test_runtime_manifest_output_accepts_direct_producer_model_payload() -> None:
    from apps.runtime_manifest import get_runtime_manifest

    manifest = RuntimeManifestOutput.from_api(get_runtime_manifest())

    assert manifest.maturity[RuntimeModuleId.bpe_tokenizer] is RuntimeMaturity.channel_covered
    assert manifest.to_dict()["maturity"]["bpe_tokenizer"] == "channel_covered"


def test_runtime_admin_modules_output_accepts_direct_producer_model_payload() -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    modules = RuntimeAdminModulesOutput.from_api(get_runtime_admin_modules())

    assert modules.summary.maturity_counts[RuntimeMaturity.channel_covered] == 22
    assert modules.summary.layer_counts[RuntimeLayer.mojo_llm_runtime_core] == 22
    assert modules.to_dict()["summary"]["maturity_counts"]["channel_covered"] == 22
    assert modules.to_dict()["summary"]["layer_counts"]["mojo_llm_runtime_core"] == 22


def test_runtime_release_validation_output_accepts_direct_producer_model_payload() -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    validation = RuntimeReleaseValidationOutput.from_api(get_runtime_release_validation())

    assert validation.conditions[0].condition is RuntimeReleaseCondition.manifest_listed
    assert validation.to_dict()["conditions"][0]["condition"] == "manifest-listed"


def test_runtime_api_mode_real_public_s3_connect_resolve_query(
    runtime_api_client: _AsgiRuntimeApiClient,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test_runtime", base_url="http://test")
    runtime._api_client = runtime_api_client

    imported = runtime.import_preview(
        PUBLIC_S3_CONNECTION,
        name="noaa_hourly",
        source_ref=PUBLIC_S3_SOURCE_REF,
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
    assert f"Origin: {PUBLIC_S3_SOURCE_REF}" in imported.preview
    assert plan.resolved_plan is not None
    assert result.result_type == "scalar"
    assert _result_scalar_value(result.result) == pytest.approx(
        float(imported.registration.row_count)
    )


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


def test_runtime_api_mode_connect_recovers_row_count_from_source_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def register_source(
            self,
            source: dict[str, object],
            *,
            description: str | None = None,
        ) -> object:
            return SimpleNamespace(
                model_dump=lambda: {
                    "source_id": "src_rest_1",
                    "dataset_id": "src_rest_1",
                    "name": source.get("name"),
                    "status": "already_registered",
                    "source_schema": {
                        "source": "weather_stations",
                        "fields": ["id", "properties"],
                        "row_count": 500,
                    },
                    "planner_schema_revision": "schema_rest_1",
                    "latency_ms": 3.6,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    registration = runtime.connect(
        {
            "type": "rest",
            "base_url": "https://api.weather.gov",
            "path": "/stations",
            "method": "GET",
        },
        name="weather_stations",
    )

    assert registration.status == "already_registered"
    assert registration.row_count == 500


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
        source_refs=[
            "postgres://orders",
            "s3://algenta-public/orders/orders.csv",
            "https://example.com/api/orders",
        ],
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
    assert (
        seen[0]["connection"]["connection_string"]
        == "postgresql://analytics:secret@localhost:5432/orders"
    )
