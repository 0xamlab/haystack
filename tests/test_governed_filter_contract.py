# ruff: noqa: I001
from __future__ import annotations

import io
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
ALGENTA_CORE = ROOT / "packages" / "algenta"
for path in (str(ROOT), str(PYTHON_SDK), str(ALGENTA_CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)

redis_connector_module = importlib.import_module("apps.api_server.connectors.redis_connector")
auth_module = importlib.import_module("apps.api_server.middleware.auth")
query_router = importlib.import_module("apps.api_server.routers.query")
query_contract = importlib.import_module("apps.api_server.routers.query_contract")
decision_engine = importlib.import_module("decision_engine")
runtime_module = importlib.import_module("algenta.runtime")
runtime_local_execution = importlib.import_module("algenta.runtime_local_execution")
RedisConnector = redis_connector_module.RedisConnector
get_current_org = auth_module.get_current_org
get_redis = auth_module.get_redis
FilterConditionSpec = query_contract.FilterConditionSpec
ClientQueryFilterCondition = decision_engine.QueryFilterCondition
ClientQueryFilterSpec = decision_engine.QueryFilterSpec
RuntimeQueryFilterCondition = runtime_module.QueryFilterCondition
RuntimeQueryFilterSpec = runtime_module.QueryFilterSpec
LocalSource = runtime_local_execution.LocalSource
execute_local_plan = runtime_local_execution.execute_local_plan
infer_numeric_fields = runtime_local_execution.infer_numeric_fields


class _RedisStub:
    async def incr(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return 1

    async def expire(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def get(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return b"0"

    async def set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def setex(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def incrby(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return 1

    async def ping(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return True

    async def hgetall(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return {}

    async def hset(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def aclose(self) -> None:
        return None


def _ready_entry(
    source_id: str,
    name: str,
    schema_revision: str = "source_rev_redis",
) -> dict[str, str]:
    return {
        "id": source_id,
        "name": name,
        "schema_revision": schema_revision,
        "decision_mode": "deterministic_only",
        "visibility": "private",
        "owner_key_id": "key_filter",
    }


def _parquet_bytes(rows: list[dict[str, object]]) -> bytes:
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_parquet(buffer, index=False)
    return buffer.getvalue()


def _schema_meta(rows: list[dict[str, object]]) -> dict[str, object]:
    first = rows[0]
    columns = []
    for name, value in first.items():
        is_numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        columns.append(
            {
                "name": name,
                "role": "base_measure" if is_numeric else "category",
                "formula": None,
                "is_numeric": is_numeric,
                "magnitude": "small",
                "semantic_type": "number" if is_numeric else "text",
                "fill_rate": 1.0,
            }
        )
    return {
        "row_count": len(rows),
        "columns": columns,
        "roles_summary": {
            "base_measure": sum(1 for column in columns if column["is_numeric"]),
            "category": sum(1 for column in columns if not column["is_numeric"]),
        },
    }


def _redis_rows() -> list[dict[str, object]]:
    class _FakePipeline:
        def __init__(self, client: _FakeRedisClient) -> None:  # type: ignore[name-defined]
            self._client = client
            self._operations: list[tuple[str, str]] = []

        def get(self, key: str) -> None:
            self._operations.append(("get", key))

        def type(self, key: str) -> None:
            self._operations.append(("type", key))

        def ttl(self, key: str) -> None:
            self._operations.append(("ttl", key))

        def execute(self, raise_on_error: bool = True) -> list[object]:
            responses: list[object] = []
            for op, key in self._operations:
                if op == "get":
                    try:
                        responses.append(self._client.get(key))
                    except Exception as exc:
                        if raise_on_error:
                            raise
                        responses.append(exc)
                elif op == "type":
                    responses.append(self._client.type(key))
                elif op == "ttl":
                    responses.append(self._client.ttl(key))
                else:  # pragma: no cover - defensive
                    raise AssertionError(f"Unexpected pipeline op: {op}")
            return responses

    class _FakeRedisClient:
        def get(self, key: str) -> str:
            if key != "greeting":
                raise TypeError("WRONGTYPE")
            return '{"message":"hello"}'

        def type(self, key: str) -> str:
            return {
                "profile": "hash",
                "events": "list",
            }.get(key, "string")

        def ttl(self, key: str) -> int:
            return {"greeting": 30, "profile": 60, "events": 120}[key]

        def hgetall(self, key: str) -> dict[str, str]:
            assert key == "profile"
            return {"user_id": "42", "status": "active"}

        def llen(self, key: str) -> int:
            assert key == "events"
            return 3

        def lrange(self, key: str, _start: int, _end: int) -> list[str]:
            assert key == "events"
            return ["created", "processed"]

        def pipeline(self, transaction: bool = False) -> _FakePipeline:
            assert transaction is False
            return _FakePipeline(self)

    return RedisConnector._materialize_key_records(
        _FakeRedisClient(),
        ["greeting", "profile", "events"],
        value_max_items=2,
    )


def test_backend_filter_condition_spec_enforces_scalar_and_list_contract() -> None:
    valid = FilterConditionSpec.model_validate(
        {"dimension_hint": "status", "op": "eq", "value": "completed"}
    )
    assert valid.dimension_hint == "status"

    with pytest.raises(ValidationError, match="requires column or dimension_hint"):
        FilterConditionSpec.model_validate({"op": "eq", "value": "completed"})

    with pytest.raises(ValidationError, match="op='in' does not accept value"):
        FilterConditionSpec.model_validate(
            {"dimension_hint": "status", "op": "in", "value": "completed"}
        )

    with pytest.raises(ValidationError, match="op='in' requires non-empty values"):
        FilterConditionSpec.model_validate({"dimension_hint": "status", "op": "in", "values": []})

    with pytest.raises(ValidationError, match="null checks do not accept value or values"):
        FilterConditionSpec.model_validate(
            {"dimension_hint": "resolved_at", "op": "is_not_null", "value": "2026-01-01"}
        )


def test_public_python_filter_models_enforce_same_contract() -> None:
    client_condition = ClientQueryFilterCondition(
        dimension_hint="status",
        op="eq",
        value="completed",
    )
    assert client_condition.dimension_hint == "status"

    client_filter = ClientQueryFilterSpec(
        conditions=[client_condition],
    )
    assert client_filter.conditions[0].op == "eq"

    runtime_condition = RuntimeQueryFilterCondition(
        dimension_hint="status",
        op="eq",
        value="completed",
    )
    runtime_filter = RuntimeQueryFilterSpec(conditions=[runtime_condition])
    assert runtime_filter.conditions == (runtime_condition,)

    with pytest.raises(ValidationError, match="does not accept values"):
        ClientQueryFilterCondition(
            dimension_hint="status",
            op="eq",
            value="completed",
            values=["completed"],
        )

    with pytest.raises(ValueError, match="requires non-empty values"):
        RuntimeQueryFilterCondition(
            dimension_hint="status",
            op="in",
        )


@pytest.mark.anyio
async def test_query_and_local_runtime_match_on_redis_normalized_records(
    app,
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _redis_rows()
    schema_meta = _schema_meta(rows)
    parquet_bytes = _parquet_bytes(rows)

    async def _fake_auth():  # type: ignore[no-untyped-def]
        return {
            "org_id": "org_filter",
            "key_id": "key_filter",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        }

    async def _fake_redis() -> _RedisStub:
        return _RedisStub()

    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = _fake_redis

    try:
        monkeypatch.setattr(
            "apps.api_server.services.source_registry.get_source_entry_by_name",
            lambda org_id, source_name: (
                _ready_entry("src_redis", "RedisSnapshot")
                if source_name == "RedisSnapshot"
                else None
            ),
        )
        monkeypatch.setattr(
            "apps.api_server.services.source_registry.source_schema_revision",
            lambda org_id, source_id: "source_rev_redis",
        )
        # _resolved_plan_current_schema_revision falls through to org-wide
        # schema_revision when no visible_entries / dataset_id is supplied
        # (tenant-safe path). Stub that too so the resolved_plan's
        # schema_revision matches what the validator computes.
        monkeypatch.setattr(
            "apps.api_server.services.source_registry.schema_revision",
            lambda org_id: "source_rev_redis",
        )
        monkeypatch.setattr(
            "apps.api_server.services.source_registry.get_source_parquet",
            lambda org_id, source_id: parquet_bytes,
        )
        monkeypatch.setattr(
            "apps.api_server.services.source_registry.get_source_meta",
            lambda org_id, source_id: schema_meta,
        )

        filter_spec = {
            "conditions": [
                {"dimension_hint": "value type", "op": "in", "values": ["hash", "list"]},
                {"dimension_hint": "item count", "op": "gte", "value": 2},
                {"dimension_hint": "value json", "op": "is_not_null"},
            ]
        }
        response = await client.post(
            "/v1/query",
            json={
                "resolved_plan": {
                    "source_name": "RedisSnapshot",
                    "metric_column": "item_count",
                    "aggregation": "sum",
                    "filter": filter_spec,
                    "schema_revision": "source_rev_redis",
                }
            },
        )

        assert response.status_code == 200
        body = response.json()

        fields = tuple(rows[0].keys())
        local_source = LocalSource(
            name="RedisSnapshot",
            records=rows,
            fields=fields,
            schema_revision="source_rev_redis",
            dataset_id="ds_redis",
            numeric_fields=infer_numeric_fields(rows, fields),
        )
        local_result = execute_local_plan(
            local_source,
            SimpleNamespace(
                source_name="RedisSnapshot",
                metric_column="item_count",
                group_column=None,
                aggregation="sum",
                limit=None,
                schema_revision="source_rev_redis",
                filter=filter_spec,
            ),
        )

        assert body["result"] == 5
        assert local_result.value == 5
        assert any("Filter `value_type in ['hash', 'list']`" in step for step in body["plan"])
        assert any(
            "Filter 'value_type in ['hash', 'list']'" in step for step in local_result.plan_steps
        )
    finally:
        app.dependency_overrides.clear()
        query_router._RESOLVE_CACHE.clear()
        query_router._RESULT_CACHE.clear()
        query_router._SOURCE_CACHE.clear()
        query_router._GRAPH_NODE_CACHE.clear()
        query_router._DATASET_EXACT_COLUMN_CACHE.clear()
        query_router._DF_CACHE.clear()
