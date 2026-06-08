"""Tests for test_resolve_api_contract: query_dataset.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-3/tests/test_resolve_api_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_resolve_api_contract_helpers import *  # noqa: F401,F403


@pytest.mark.anyio
async def test_query_dataset_scoped_exact_path_uses_source_schema_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = pd.DataFrame({"amount": [10, 20], "customer": ["A", "B"]})
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
    schema_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "amount",
                "role": "derived_measure",
                "formula": "qty x price",
                "is_numeric": True,
                "magnitude": "medium",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
            {
                "name": "customer",
                "role": "category",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"derived_measure": 1, "category": 1},
    }
    source_revision_calls = {"count": 0}
    dataset_entry = _ready_entry("src_1", "Orders", schema_revision="schema_rev_1")

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("list_sources should not run for dataset-scoped exact queries")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, source_id: dataset_entry if source_id == "src_1" else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(AssertionError("org schema_revision should not run")),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: (
            source_revision_calls.__setitem__("count", source_revision_calls["count"] + 1)
            or "source_rev_1"
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: parquet_bytes,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    query_router._RESULT_CACHE.clear()
    query_router._SOURCE_CACHE.clear()
    query_router._DF_CACHE.clear()

    request_body = {
        "dataset_id": "src_1",
        "metric_column": "amount",
        "aggregation": "count",
    }
    first = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )
    second = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )

    assert first.result == 2.0
    assert second.result == 2.0
    assert any(step.startswith("Result cache HIT") for step in second.plan)
    assert source_revision_calls["count"] == 2


@pytest.mark.anyio
async def test_query_dataset_scoped_exact_path_uses_cached_source_schema_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = pd.DataFrame({"amount": [10, 20], "customer": ["A", "B"]})
    buf = io.BytesIO()
    data.to_parquet(buf, index=False)
    parquet_bytes = buf.getvalue()
    schema_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "amount",
                "role": "derived_measure",
                "formula": "qty x price",
                "is_numeric": True,
                "magnitude": "medium",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
            {
                "name": "customer",
                "role": "category",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"derived_measure": 1, "category": 1},
    }
    dataset_entry = _ready_entry("src_1", "Orders", schema_revision="schema_rev_1")
    dataset_entry["source_schema_revision"] = "source_rev_cached"
    captured_log_response: list[bool] = []
    original_build_query_response = query_router._build_query_response

    def _capture_build_query_response(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_log_response.append(bool(kwargs.get("log_response", True)))
        return original_build_query_response(*args, **kwargs)

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("list_sources should not run for dataset-scoped exact queries")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, source_id: dataset_entry if source_id == "src_1" else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(AssertionError("org schema_revision should not run")),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: (_ for _ in ()).throw(
            AssertionError("cached source schema revision should be used")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: parquet_bytes,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    monkeypatch.setattr(query_router, "_build_query_response", _capture_build_query_response)
    query_router._RESULT_CACHE.clear()
    query_router._SOURCE_CACHE.clear()
    query_router._DF_CACHE.clear()

    request_body = {
        "dataset_id": "src_1",
        "metric_column": "amount",
        "aggregation": "count",
    }
    first = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )
    second = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )

    assert first.result == 2.0
    assert second.result == 2.0
    assert any(step.startswith("Result cache HIT") for step in second.plan)
    assert captured_log_response[-1] is False


@pytest.mark.anyio
async def test_query_dataset_scoped_exact_count_uses_metadata_fast_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema_meta = {
        "row_count": 2,
        "columns": [
            {
                "name": "amount",
                "role": "derived_measure",
                "formula": "qty x price",
                "is_numeric": True,
                "magnitude": "medium",
                "semantic_type": "number",
                "fill_rate": 1.0,
            },
            {
                "name": "customer",
                "role": "category",
                "formula": None,
                "is_numeric": False,
                "magnitude": "small",
                "semantic_type": "text",
                "fill_rate": 1.0,
            },
        ],
        "roles_summary": {"derived_measure": 1, "category": 1},
    }
    dataset_entry = _ready_entry("src_1", "Orders", schema_revision="schema_rev_1")
    dataset_entry["source_schema_revision"] = "source_rev_cached"
    dataset_entry["row_count"] = 2

    monkeypatch.setattr(
        "apps.api_server.services.source_registry.list_sources",
        lambda org_id: (_ for _ in ()).throw(
            AssertionError("list_sources should not run for dataset-scoped exact queries")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_entry",
        lambda org_id, source_id: dataset_entry if source_id == "src_1" else None,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.schema_revision",
        lambda org_id: (_ for _ in ()).throw(AssertionError("org schema_revision should not run")),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.source_schema_revision",
        lambda org_id, source_id: (_ for _ in ()).throw(
            AssertionError("cached source schema revision should be used")
        ),
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_meta",
        lambda org_id, source_id: schema_meta,
    )
    monkeypatch.setattr(
        "apps.api_server.services.source_registry.get_source_parquet",
        lambda org_id, source_id: (_ for _ in ()).throw(
            AssertionError("metadata fast path should not load parquet")
        ),
    )
    query_router._RESULT_CACHE.clear()
    query_router._SOURCE_CACHE.clear()
    query_router._DF_CACHE.clear()

    request_body = {
        "dataset_id": "src_1",
        "metric_column": "amount",
        "aggregation": "count",
    }
    first = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )
    second = await query_router.query_sources(
        query_router.QueryRequest(**request_body),
        auth={
            "org_id": "org_resolve",
            "key_id": "key_resolve",
            "plan": "pro",
            "role": "owner",
            "email": "owner@example.com",
        },
    )

    assert first.result == 2.0
    assert any("metadata fast path" in step for step in first.plan)
    assert second.result == 2.0
    assert any(step.startswith("Result cache HIT") for step in second.plan)


