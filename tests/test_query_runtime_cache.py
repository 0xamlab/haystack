from pathlib import Path

import pytest

from apps.api_server.routers import query as query_router
from apps.api_server.services import source_registry as reg
from apps.api_server.services.auto_planner import AutoPlanner


@pytest.mark.asyncio
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

    first, first_hit, first_rev = await query_router._get_registry_planner("org_cache", llm_policy="never")
    second, second_hit, second_rev = await query_router._get_registry_planner("org_cache", llm_policy="never")

    revisions["org_cache"] = "rev_b"
    third, third_hit, third_rev = await query_router._get_registry_planner("org_cache", llm_policy="never")

    assert first_hit is False
    assert second_hit is True
    assert third_hit is False
    assert first_rev == second_rev == "rev_a"
    assert third_rev == "rev_b"
    assert first is second
    assert third is not first
    assert len(built) == 2
