from __future__ import annotations

import csv
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

# ruff: noqa: E402

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT),):
    if path not in sys.path:
        sys.path.insert(0, path)

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.routers import query as query_router
from apps.api_server.services import data_connection_service as dcs
from apps.api_server.services import source_registry as reg
from apps.api_server.services.connectors.tester import test_connector_real
from apps.mcp_server import client as mcp_client
from apps.mcp_server.tools import data, query
from tests.integration.runtime_live_db_helpers import (
    postgres_canonical_connector,
    postgres_connection_config,
    temporary_postgres_fixture,
)

REAL_MARCH_ORDERS = ROOT / "test_files" / "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"
PUBLIC_S3_CONNECTION = {
    "bucket": "1000genomes",
    "region": "us-east-1",
    "anonymous": True,
    "file_type": "tsv",
}
PUBLIC_S3_SELECTION = {"object_path": "20131219.populations.tsv"}
PUBLIC_REST_CONNECTION = {
    "url": "https://api.weather.gov/stations",
    "headers": {
        "User-Agent": "decision-engine-mcp-compat/1.0",
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


def _sum_csv_column(path: Path, column: str) -> float:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return sum(float(str(row[column] or "0").strip() or 0.0) for row in reader)


def _write_sqlite_fixture(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE orders (
                order_id TEXT,
                region TEXT,
                revenue REAL
            )
            """
        )
        connection.executemany(
            "INSERT INTO orders (order_id, region, revenue) VALUES (?, ?, ?)",
            [
                ("ord_1", "US", 100.0),
                ("ord_2", "US", 220.5),
                ("ord_3", "CA", 95.5),
            ],
        )
        connection.execute(
            """
            CREATE TABLE customers (
                customer_id TEXT,
                segment TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO customers (customer_id, segment) VALUES (?, ?)",
            [("c_1", "enterprise"), ("c_2", "mid-market")],
        )
        connection.commit()
    finally:
        connection.close()


def _postgres_fixture_rows() -> list[dict[str, object]]:
    return [
        {"order_id": "ord_1", "region": "US", "revenue": 100.0},
        {"order_id": "ord_2", "region": "US", "revenue": 220.5},
        {"order_id": "ord_3", "region": "CA", "revenue": 95.5},
    ]


def _result_value(body: dict[str, Any]) -> float:
    result = body["result"]
    if isinstance(result, dict):
        value = result.get("value")
    else:
        value = result
    return float(value)


def _count_metric_column(schema: dict[str, Any]) -> str:
    columns = schema.get("columns", [])
    if not columns:
        raise AssertionError("Schema returned no columns.")
    return str(columns[0]["name"])


@pytest.fixture
def fake_auth() -> dict[str, Any]:
    return {
        "org_id": "org_mcp_runtime",
        "role": "owner",
        "user_id": "u1",
        "key_id": "k1",
    }


@pytest.fixture
async def patched_mcp_runtime(app, monkeypatch, tmp_path: Path, fake_auth):
    app.dependency_overrides[get_current_org] = lambda: fake_auth
    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(reg, "_SOURCES_DIR", tmp_path / "sources")

    async with query_router._CACHE_LOCK:
        query_router._SOURCE_CACHE.clear()
        query_router._PLANNER_CACHE.clear()
        query_router._RESULT_CACHE.clear()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "Authorization": "Bearer de_test_runtime",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as client:

        async def _patched_api(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
            response = await getattr(client, method.lower())(path, **kwargs)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:  # pragma: no cover - debug aid
                raise RuntimeError(
                    f"API error {exc.response.status_code}: {exc.response.text}"
                ) from exc
            return response.json()

        monkeypatch.setattr(mcp_client, "api", _patched_api)
        monkeypatch.setattr(data, "api", _patched_api)
        monkeypatch.setattr(query, "api", _patched_api)
        yield
    app.dependency_overrides.clear()


def _install_live_connector_test(
    monkeypatch: pytest.MonkeyPatch,
    *,
    provider: str,
    connection_config: dict[str, Any],
) -> None:
    fake_connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value=provider),
        config_json=json.dumps(connection_config),
        visibility="private",
    )

    async def _fake_create_or_reuse_connector(**_: Any) -> Any:
        return fake_connector

    async def _fake_test_and_persist_connector(
        connector: Any,
        db: Any,
    ) -> tuple[bool, str, int]:
        del db
        return await test_connector_real(
            str(connector.connector_type.value),
            json.loads(str(connector.config_json)),
        )

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)


@pytest.mark.anyio
async def test_mcp_runtime_real_csv_connect_schema_query_flow(
    patched_mcp_runtime,
) -> None:
    expected_sum = _sum_csv_column(REAL_MARCH_ORDERS, "Sales (incl. tax)")
    csv_text = REAL_MARCH_ORDERS.read_text(encoding="utf-8")

    connected = json.loads(
        await data.connect_handler(
            {
                "connection_type": "file_upload",
                "dataset_name": "orders_detail",
                "csv": csv_text,
            }
        )
    )
    assert connected["status"] == "ready"
    dataset_id = connected["dataset_id"]
    assert connected["schema_summary"]["row_count"] == 6097

    listed = json.loads(await data.list_handler({}))
    assert any(item["dataset_id"] == dataset_id for item in listed["datasets"])

    schema = json.loads(await data.schema_handler({"dataset_id": dataset_id}))
    assert schema["dataset"]["dataset_name"] == "orders_detail"
    assert schema["schema"]["row_count"] == 6097

    queried = json.loads(
        await query.handler(
            {
                "dataset_id": dataset_id,
                "metric_column": "Sales (incl. tax)",
                "aggregation": "sum",
            }
        )
    )
    assert queried["validated"] is True
    assert queried["clarification_required"] is False
    assert queried["result_type"] == "scalar"
    assert queried["resolved_column"] == "Sales (incl. tax)"
    assert _result_value(queried) == pytest.approx(expected_sum)


@pytest.mark.anyio
async def test_mcp_runtime_real_csv_connect_via_canonical_connector(
    patched_mcp_runtime,
) -> None:
    expected_sum = _sum_csv_column(REAL_MARCH_ORDERS, "Sales (incl. tax)")

    connected = json.loads(
        await data.connect_handler(
            {
                "dataset_name": "orders_detail_connector",
                "connector": {
                    "type": "csv",
                    "location": {"path": str(REAL_MARCH_ORDERS)},
                    "options": {"delimiter": ","},
                },
            }
        )
    )
    assert connected["status"] == "ready"
    assert connected["schema_summary"]["row_count"] == 6097

    queried = json.loads(
        await query.handler(
            {
                "dataset_id": connected["dataset_id"],
                "metric_column": "Sales (incl. tax)",
                "aggregation": "sum",
            }
        )
    )
    assert queried["validated"] is True
    assert queried["result_type"] == "scalar"
    assert queried["resolved_column"] == "Sales (incl. tax)"
    assert _result_value(queried) == pytest.approx(expected_sum)


@pytest.mark.anyio
async def test_mcp_runtime_database_selection_resume_and_query_sqlite(
    patched_mcp_runtime,
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "orders.db"
    _write_sqlite_fixture(db_path)
    fake_connector = SimpleNamespace(
        id=uuid.uuid4(),
        connector_type=SimpleNamespace(value="sqlite"),
        config_json=json.dumps({"path": str(db_path)}),
        visibility="private",
    )

    async def _fake_create_or_reuse_connector(**_: Any) -> Any:
        return fake_connector

    async def _fake_test_and_persist_connector(*_: Any, **__: Any) -> tuple[bool, str, int]:
        return True, "ok", 1

    async def _fake_browse_connector_real_detailed(
        *_: Any, **__: Any
    ) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
        return (
            [
                {"id": "orders", "label": "orders", "selection": {"table": "orders"}},
                {
                    "id": "customers",
                    "label": "customers",
                    "selection": {"table": "customers"},
                },
            ],
            "choose a table",
            {
                "scope_noun": "catalog",
                "returned_count": 2,
                "count_kind": "exact",
                "matching_total_count": 2,
                "scope_total_count": 2,
                "more_available": False,
                "sampling_reason": None,
            },
        )

    async def _fake_get_visible_connector(*_: Any, **__: Any) -> Any:
        return fake_connector

    monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
    monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
    monkeypatch.setattr(dcs, "browse_connector_real_detailed", _fake_browse_connector_real_detailed)
    monkeypatch.setattr(dcs, "get_visible_connector", _fake_get_visible_connector)

    first = json.loads(
        await data.connect_handler(
            {
                "connection_type": "database",
                "provider": "sqlite",
                "dataset_name": "orders_sqlite",
                "connection_config": {"path": str(db_path)},
            }
        )
    )
    assert first["status"] == "needs_selection"
    assert first["connection_id"] == str(fake_connector.id)
    assert len(first["choices"]) == 2

    ready = json.loads(
        await data.connect_handler(
            {
                "connection_type": "database",
                "provider": "sqlite",
                "dataset_name": "orders_sqlite",
                "connection_id": first["connection_id"],
                "selection": first["choices"][0]["selection"],
            }
        )
    )
    assert ready["status"] == "ready"
    assert ready["schema_summary"]["row_count"] == 3

    queried = json.loads(
        await query.handler(
            {
                "dataset_id": ready["dataset_id"],
                "metric_column": "revenue",
                "aggregation": "sum",
            }
        )
    )
    assert queried["validated"] is True
    assert queried["result_type"] == "scalar"
    assert _result_value(queried) == pytest.approx(416.0)


@pytest.mark.anyio
async def test_mcp_runtime_database_query_postgres_via_canonical_connector(
    patched_mcp_runtime,
    monkeypatch,
) -> None:
    with temporary_postgres_fixture(
        _postgres_fixture_rows(),
        table="orders",
    ) as postgres_descriptor:
        connection_config = postgres_connection_config(postgres_descriptor["connection_string"])
        fake_connector = SimpleNamespace(
            id=uuid.uuid4(),
            connector_type=SimpleNamespace(value="postgres"),
            config_json=json.dumps(connection_config),
            visibility="private",
        )

        async def _fake_create_or_reuse_connector(**_: Any) -> Any:
            return fake_connector

        async def _fake_get_visible_connector(*_: Any, **__: Any) -> Any:
            return fake_connector

        async def _fake_test_and_persist_connector(*_: Any, **__: Any) -> tuple[bool, str, int]:
            return await test_connector_real(
                "postgres",
                connection_config,
            )

        monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
        monkeypatch.setattr(dcs, "get_visible_connector", _fake_get_visible_connector)
        monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)
        connector = postgres_canonical_connector(postgres_descriptor)

        ready = json.loads(
            await data.connect_handler(
                {
                    "dataset_name": "orders_postgres_canonical",
                    "connector": connector,
                }
            )
        )
        assert ready["status"] == "ready"
        assert ready["schema_summary"]["row_count"] == 3

        queried = json.loads(
            await query.handler(
                {
                    "dataset_id": ready["dataset_id"],
                    "metric_column": "revenue",
                    "aggregation": "sum",
                }
            )
        )
        assert queried["validated"] is True
        assert queried["result_type"] == "scalar"
        assert _result_value(queried) == pytest.approx(416.0)


@pytest.mark.anyio
async def test_mcp_runtime_database_selection_resume_and_query_postgres(
    patched_mcp_runtime,
    monkeypatch,
) -> None:
    with temporary_postgres_fixture(
        _postgres_fixture_rows(),
        table="orders",
    ) as postgres_descriptor:
        connection_config = postgres_connection_config(postgres_descriptor["connection_string"])
        fake_connector = SimpleNamespace(
            id=uuid.uuid4(),
            connector_type=SimpleNamespace(value="postgres"),
            config_json=json.dumps(connection_config),
            visibility="private",
        )

        async def _fake_create_or_reuse_connector(**_: Any) -> Any:
            return fake_connector

        async def _fake_get_visible_connector(*_: Any, **__: Any) -> Any:
            return fake_connector

        async def _fake_test_and_persist_connector(*_: Any, **__: Any) -> tuple[bool, str, int]:
            return await test_connector_real(
                "postgres",
                connection_config,
            )

        monkeypatch.setattr(dcs, "create_or_reuse_connector", _fake_create_or_reuse_connector)
        monkeypatch.setattr(dcs, "get_visible_connector", _fake_get_visible_connector)
        monkeypatch.setattr(dcs, "_test_and_persist_connector", _fake_test_and_persist_connector)

        first = json.loads(
            await data.connect_handler(
                {
                    "connection_type": "database",
                    "provider": "postgres",
                    "dataset_name": "orders_postgres",
                    "connection_config": connection_config,
                }
            )
        )
        assert first["status"] == "needs_selection"
        orders_choice = next(
            (
                choice
                for choice in first["choices"]
                if (choice.get("selection") or {}).get("table")
                == f"{postgres_descriptor['schema']}.{postgres_descriptor['table']}"
            ),
            None,
        )
        assert orders_choice is not None, "Postgres browse did not return the fixture table."

        ready = json.loads(
            await data.connect_handler(
                {
                    "connection_type": "database",
                    "provider": "postgres",
                    "dataset_name": "orders_postgres",
                    "connection_id": first["connection_id"],
                    "selection": orders_choice["selection"],
                }
            )
        )
        assert ready["status"] == "ready"
        assert ready["schema_summary"]["row_count"] == 3

        queried = json.loads(
            await query.handler(
                {
                    "dataset_id": ready["dataset_id"],
                    "metric_column": "revenue",
                    "aggregation": "sum",
                }
            )
        )
        assert queried["validated"] is True
        assert queried["result_type"] == "scalar"
        assert _result_value(queried) == pytest.approx(416.0)


@pytest.mark.anyio
async def test_mcp_runtime_public_rest_connect_and_count_query(
    patched_mcp_runtime,
    monkeypatch,
) -> None:
    _install_live_connector_test(
        monkeypatch,
        provider="rest",
        connection_config=PUBLIC_REST_CONNECTION,
    )

    connected = json.loads(
        await data.connect_handler(
            {
                "connection_type": "api",
                "provider": "rest",
                "dataset_name": "public_weather_stations",
                "connection_config": PUBLIC_REST_CONNECTION,
            }
        )
    )
    assert connected["status"] == "ready"
    assert connected["schema_summary"]["row_count"] > 0

    schema = json.loads(await data.schema_handler({"dataset_id": connected["dataset_id"]}))
    metric_column = _count_metric_column(schema["schema"])
    queried = json.loads(
        await query.handler(
            {
                "dataset_id": connected["dataset_id"],
                "metric_column": metric_column,
                "aggregation": "count",
            }
        )
    )
    assert queried["validated"] is True
    assert queried["result_type"] == "scalar"
    assert _result_value(queried) == pytest.approx(float(connected["schema_summary"]["row_count"]))


@pytest.mark.anyio
async def test_mcp_runtime_public_s3_connect_and_count_query(
    patched_mcp_runtime,
    monkeypatch,
) -> None:
    _install_live_connector_test(
        monkeypatch,
        provider="s3",
        connection_config=PUBLIC_S3_CONNECTION,
    )

    connected = json.loads(
        await data.connect_handler(
            {
                "connection_type": "object_storage",
                "provider": "s3",
                "dataset_name": "public_noaa_hourly_sample",
                "connection_config": PUBLIC_S3_CONNECTION,
                "selection": PUBLIC_S3_SELECTION,
            }
        )
    )
    assert connected["status"] == "ready"
    assert connected["schema_summary"]["row_count"] > 0

    schema = json.loads(await data.schema_handler({"dataset_id": connected["dataset_id"]}))
    metric_column = _count_metric_column(schema["schema"])
    queried = json.loads(
        await query.handler(
            {
                "dataset_id": connected["dataset_id"],
                "metric_column": metric_column,
                "aggregation": "count",
            }
        )
    )
    assert queried["validated"] is True
    assert queried["result_type"] == "scalar"
    assert _result_value(queried) == pytest.approx(float(connected["schema_summary"]["row_count"]))
