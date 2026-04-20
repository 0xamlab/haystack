from __future__ import annotations

from types import SimpleNamespace

import pyarrow as pa
import pytest
from fastapi import HTTPException

from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import query as query_router


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


@pytest.mark.asyncio
async def test_query_empty_source_returns_structured_400(app, client, monkeypatch) -> None:
    async def _fake_auth():  # type: ignore[no-untyped-def]
        return {
            "org_id": "org_a",
            "key_id": "k1",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        }

    async def _fake_redis() -> _RedisStub:
        return _RedisStub()

    async def _fake_load_profiled_source(*args, **kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(profile={}, arrow_table=None, row_count=0, ingest_mode="rows")

    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = _fake_redis
    monkeypatch.setattr("apps.api_server.routers.query._load_profiled_source", _fake_load_profiled_source)
    query_router._SOURCE_CACHE.clear()

    try:
        resp = await client.post(
            "/v1/query",
            json={
                "sources": [{"name": "empty", "csv": "revenue,cost\n"}],
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "sum",
            },
        )
    finally:
        app.dependency_overrides.clear()
        query_router._SOURCE_CACHE.clear()

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "empty_source"


@pytest.mark.asyncio
async def test_infer_schema_returns_structured_503_when_mojo_profiling_fails_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_load_profiled_source(*args, **kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            profile={
                "measure_total": {
                    "sample_values": ["10", "20"],
                    "strings": [],
                    "total_count": 2,
                    "fill_rate": 1.0,
                    "is_numeric": True,
                    "numeric": [10.0, 20.0],
                    "unique_count": 2,
                }
            },
            arrow_table=pa.table({"measure_total": [10, 20]}),
            row_count=2,
            ingest_mode="columnar",
        )

    async def _raise_profile(*_args, **_kwargs):
        raise query_router.MojoInstrumentationError(
            "column_profile",
            "Mojo column profiling failed while strict runtime fallbacks are disabled.",
        )

    monkeypatch.setattr(query_router, "_load_profiled_source", _fake_load_profiled_source)
    monkeypatch.setattr(query_router, "_call_mojo_column_profile", _raise_profile)
    query_router._SOURCE_CACHE.clear()

    with pytest.raises(HTTPException) as excinfo:
        await query_router.infer_schema(
            query_router.SchemaRequest(
                sources=[query_router.DataSource(name="strict_profile", csv="measure_total\n10\n20\n")]
            ),
            auth={"org_id": "org_a"},
        )

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail["error"]["code"] == "mojo_instrumentation_unavailable"


def test_df_cache_records_materializes_rows_only_once() -> None:
    class _FakeFrame:
        def __init__(self) -> None:
            self.calls = 0

        def to_dict(self, orient: str = "records"):  # type: ignore[no-untyped-def]
            assert orient == "records"
            self.calls += 1
            return [{"amount": 10.0}, {"amount": 20.0}]

    query_router._DF_CACHE.clear()
    frame = _FakeFrame()
    query_router._df_cache_put("src_rows", frame)

    cached = query_router._df_cache_get("src_rows")
    assert cached is not None

    first = query_router._df_cache_records("src_rows", cached)
    second = query_router._df_cache_records("src_rows", cached)

    assert first == [{"amount": 10.0}, {"amount": 20.0}]
    assert second == first
    assert frame.calls == 1
