from pathlib import Path

import pytest

from apps.api_server.routers import query as query_router
from apps.api_server.services import source_registry as reg
from apps.api_server.services.auto_planner import AutoPlanner


@pytest.mark.anyio
async def test_registry_planner_cache_reuses_planner_until_schema_revision_changes(monkeypatch):
    revisions = {"org_cache": "rev_a"}

    monkeypatch.setattr(reg, "_SOURCES_DIR", Path("/tmp/decision-engine-test-sources-cache"))
    monkeypatch.setattr(reg, "schema_revision", lambda org_id: revisions[org_id])
    monkeypatch.setattr(reg, "list_sources", lambda org_id: [])

    built: list[object] = []

    def _fake_from_registry(org_id: str, **_kwargs):
        planner = object()
        built.append(planner)
        return planner

    monkeypatch.setattr(AutoPlanner, "from_registry", _fake_from_registry)

    async with query_router._CACHE_LOCK:
        query_router._PLANNER_CACHE.clear()

    first, first_hit, first_rev = await query_router._get_registry_planner(
        "org_cache", llm_policy="never", auth=None
    )
    second, second_hit, second_rev = await query_router._get_registry_planner(
        "org_cache", llm_policy="never", auth=None
    )

    revisions["org_cache"] = "rev_b"
    third, third_hit, third_rev = await query_router._get_registry_planner(
        "org_cache", llm_policy="never", auth=None
    )

    assert first_hit is False
    assert second_hit is True
    assert third_hit is False
    assert first_rev == second_rev == "rev_a"
    assert third_rev == "rev_b"
    assert first is second
    assert third is not first
    assert len(built) == 2


@pytest.mark.anyio
async def test_registry_planner_cache_hits_scope_fast_path_without_listing_sources(monkeypatch):
    planner = object()

    async with query_router._CACHE_LOCK:
        query_router._PLANNER_CACHE.clear()
        query_router._PLANNER_CACHE[("org_scope", "never", "vis_hash")] = (
            query_router._CachedPlanner(
                planner=planner,
                schema_revision="rev_scope",
                llm_policy="never",
                # Compute via the real fn so this stays correct as the scope-key format
                # evolves (it now folds workspace_id into the 3rd slot).
                auth_scope_key=query_router._planner_auth_scope_key(
                    {"user_id": "user-1", "key_id": "key-1", "role": "member"}
                ),
            )
        )

    monkeypatch.setattr(reg, "schema_revision", lambda org_id: "rev_scope")

    def _list_sources_must_not_run(_org_id: str):  # type: ignore[no-untyped-def]
        raise AssertionError("scope fast-path should not list sources on a warm cache hit")

    monkeypatch.setattr(reg, "list_sources", _list_sources_must_not_run)

    cached, hit, schema_revision = await query_router._get_registry_planner(
        "org_scope",
        llm_policy="never",
        auth={
            "org_id": "org_scope",
            "user_id": "user-1",
            "key_id": "key-1",
            "role": "member",
        },
    )

    assert cached is planner
    assert hit is True
    assert schema_revision == "rev_scope"


@pytest.mark.anyio
async def test_incremental_registry_planner_update_reuses_cached_planner(monkeypatch):
    calls: list[dict[str, object]] = []

    class _FakePlanner:
        def refresh_registry_source(self, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)

    planner = _FakePlanner()

    async with query_router._CACHE_LOCK:
        query_router._PLANNER_CACHE.clear()
        query_router._PLANNER_CACHE[("org_inc", "never", "vis_hash")] = query_router._CachedPlanner(
            planner=planner,
            schema_revision="rev_old",
            llm_policy="never",
        )

    monkeypatch.setattr(reg, "schema_revision", lambda org_id: "rev_new")
    monkeypatch.setattr(
        reg,
        "list_sources",
        lambda org_id: [{"id": "src_new", "name": "Orders"}],
    )
    monkeypatch.setattr(
        "apps.api_server.services.data_visibility.filter_visible_datasets",
        lambda entries, auth: entries,
    )
    monkeypatch.setattr(
        "apps.api_server.services.data_visibility.visibility_hash",
        lambda entries: "vis_hash",
    )

    updated, schema_revision = await query_router._try_incremental_registry_planner_update(
        "org_inc",
        llm_policy="never",
        auth={"org_id": "org_inc"},
        source_id="src_new",
        source_name="Orders",
        schema_meta={"columns": [], "roles_summary": {}},
        source_schema_revision="src_rev_new",
        parquet_path=Path("/tmp/orders.parquet"),
        new_connections=[
            {"source_a_name": "Orders", "source_b_name": "Customers", "col_a": "id", "col_b": "id"}
        ],
    )

    assert updated is True
    assert schema_revision == "rev_new"
    assert len(calls) == 1
    assert calls[0]["source_id"] == "src_new"
    async with query_router._CACHE_LOCK:
        cached = query_router._PLANNER_CACHE[("org_inc", "never", "vis_hash")]
        assert cached.schema_revision == "rev_new"


@pytest.mark.anyio
async def test_incremental_registry_planner_update_migrates_single_org_cache_key(monkeypatch):
    calls: list[dict[str, object]] = []

    class _FakePlanner:
        def refresh_registry_source(self, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)

    async with query_router._CACHE_LOCK:
        query_router._PLANNER_CACHE.clear()
        query_router._PLANNER_CACHE[("org_move", "never", "old_vis_hash")] = (
            query_router._CachedPlanner(
                planner=_FakePlanner(),
                schema_revision="rev_old",
                llm_policy="never",
            )
        )

    monkeypatch.setattr(reg, "schema_revision", lambda org_id: "rev_new")
    monkeypatch.setattr(
        reg,
        "list_sources",
        lambda org_id: [{"id": "src_new", "name": "Orders"}],
    )
    monkeypatch.setattr(
        "apps.api_server.services.data_visibility.filter_visible_datasets",
        lambda entries, auth: entries,
    )
    monkeypatch.setattr(
        "apps.api_server.services.data_visibility.visibility_hash",
        lambda entries: "new_vis_hash",
    )

    updated, schema_revision = await query_router._try_incremental_registry_planner_update(
        "org_move",
        llm_policy="never",
        auth={"org_id": "org_move"},
        source_id="src_new",
        source_name="Orders",
        schema_meta={"columns": [], "roles_summary": {}},
        source_schema_revision="src_rev_new",
        parquet_path=Path("/tmp/orders.parquet"),
        new_connections=[],
    )

    assert updated is True
    assert schema_revision == "rev_new"
    assert len(calls) == 1
    async with query_router._CACHE_LOCK:
        assert ("org_move", "never", "old_vis_hash") not in query_router._PLANNER_CACHE
        assert ("org_move", "never", "new_vis_hash") in query_router._PLANNER_CACHE


@pytest.mark.anyio
async def test_incremental_registry_planner_update_keeps_hidden_planner_hot(monkeypatch):
    async with query_router._CACHE_LOCK:
        query_router._PLANNER_CACHE.clear()
        query_router._PLANNER_CACHE[("org_hidden", "never", "vis_hash")] = (
            query_router._CachedPlanner(
                planner=object(),
                schema_revision="rev_old",
                llm_policy="never",
            )
        )

    monkeypatch.setattr(reg, "schema_revision", lambda org_id: "rev_new")
    monkeypatch.setattr(
        reg,
        "list_sources",
        lambda org_id: [{"id": "src_existing", "name": "VisibleOrders"}],
    )
    monkeypatch.setattr(
        "apps.api_server.services.data_visibility.filter_visible_datasets",
        lambda entries, auth: entries,
    )
    monkeypatch.setattr(
        "apps.api_server.services.data_visibility.visibility_hash",
        lambda entries: "vis_hash",
    )

    updated, schema_revision = await query_router._try_incremental_registry_planner_update(
        "org_hidden",
        llm_policy="never",
        auth={"org_id": "org_hidden"},
        source_id="src_hidden",
        source_name="HiddenPrivateSource",
        schema_meta={"columns": [], "roles_summary": {}},
        source_schema_revision="src_rev_hidden",
        parquet_path=None,
        new_connections=[],
    )

    assert updated is True
    assert schema_revision == "rev_new"
    async with query_router._CACHE_LOCK:
        cached = query_router._PLANNER_CACHE[("org_hidden", "never", "vis_hash")]
        assert cached.schema_revision == "rev_new"
