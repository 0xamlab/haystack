"""Shared imports + helpers for test_algenta_runtime_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-3/tests/test_algenta_runtime.py during modularization.
"""
# ruff: noqa: F401

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

ROOT = Path(__file__).resolve().parents[1]

ALGENTA_CORE = ROOT / "packages" / "algenta"

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



__all__ = [
    "annotations",
    "asyncio",
    "importlib",
    "sqlite3",
    "sys",
    "warnings",
    "deepcopy",
    "UTC",
    "datetime",
    "Path",
    "SimpleNamespace",
    "patch",
    "jwt",
    "pytest",
    "serialization",
    "rsa",
    "load_platform_contract_manifest",
    "assert_manifest_backed_integrations",
    "ROOT",
    "ALGENTA_CORE",
    "PYTHON_SDK",
    "TEST_FILES",
    "runtime_manifest_models",
    "Runtime",
    "PlatformContractOutput",
    "QueryBatchOutput",
    "QueryOutput",
    "QuerySqlReportOutput",
    "QueryWithMetadataOutput",
    "ResolveOutput",
    "RuntimeAdminBenchmarksOutput",
    "RuntimeAdminModulesOutput",
    "RuntimeConfigurationError",
    "RuntimeManifestOutput",
    "RuntimeReleaseValidationOutput",
    "RuntimeValidationError",
    "SourceRegistration",
    "RuntimeMaturity",
    "RuntimeBenchmarkBaseline",
    "RuntimeBenchmarkClassCode",
    "RuntimeBenchmarkMetric",
    "RuntimeEvaluationMethod",
    "RuntimeReplayability",
    "RuntimeRiskLevel",
    "RuntimeSchedulerPolicy",
    "RuntimeSideEffectClass",
    "RuntimeSupportedChannel",
    "RuntimeAuxiliaryChannel",
    "RuntimeFeatureFlagChannel",
    "RuntimeDeploymentMode",
    "RuntimeEvaluationDimension",
    "RuntimeExecutionStateField",
    "RuntimeExecutionValidityRule",
    "RuntimeExternalNondeterminismSource",
    "RuntimeFailureCode",
    "RuntimeExecutionTransition",
    "RuntimeInvariantName",
    "RuntimeArtifactLineageStep",
    "RuntimeAdminEndpoint",
    "RuntimeCapabilityField",
    "RuntimeCapabilityRule",
    "RuntimeArtifactKind",
    "RuntimeCompiledEngine",
    "RuntimeBenchmarkDiscoveryRule",
    "RuntimeNonShippingRule",
    "RuntimeLayer",
    "RuntimeLineageNodeField",
    "RuntimeMemoryRegion",
    "RuntimeMemoryRule",
    "RuntimeModuleId",
    "RuntimeReleaseCondition",
    "RuntimeReleaseGateId",
    "RuntimeProofObligation",
    "RuntimePublicEndpoint",
    "RuntimeSignatureAlgorithm",
    "RuntimeSignatureScope",
    "RuntimeReleaseArtifact",
    "RuntimeReleaseBlocker",
    "RuntimeNondeterminismArtifact",
    "RuntimeSchedulerInvariant",
    "_platform_contract_payload",
    "RuntimeSchedulerMaximizeObjective",
    "RuntimeSchedulerMinimizeObjective",
    "RuntimeSLOBudgetAppliesTo",
    "RuntimeSLOBudgetName",
    "RuntimeFeatureFlagEndpoint",
    "RuntimeThreatClass",
    "RuntimeThreatControl",
    "RuntimeThreatRule",
    "get_settings",
    "get_db",
    "fastapi_app",
    "get_current_org",
    "query_router",
    "reg",
    "_issue_license_jwt",
    "SyncASGIClient",
    "_sample_rows",
    "_offline_license_keypair",
    "_write_sqlite_fixture",
    "_write_parquet_fixture",
    "_write_excel_fixture",
    "_reload_runtime_license_module",
    "_reload_runtime_credits_module",
    "_reload_runtime_trusted_time_module",
    "REAL_MARCH_ORDERS",
    "REAL_MARCH_FINANCIAL",
    "REAL_MARCH_EMPTY",
    "REAL_MARCH_INACCURATE",
    "REAL_MARCH_RATINGS",
    "REAL_LOCAL_PARQUET",
    "REAL_LOCAL_WORKBOOK",
    "PUBLIC_S3_CONNECTION",
    "PUBLIC_S3_SOURCE_REF",
    "PUBLIC_REST_CONNECTION",
    "_FakeDB",
    "_override_db",
    "_clear_runtime_api_caches",
    "_AsgiRuntimeApiClient",
    "runtime_api_client",
    "_result_scalar_value",
    "_registration_metric_field",
]
