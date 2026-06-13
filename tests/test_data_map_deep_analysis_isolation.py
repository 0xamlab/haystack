"""Cross-tenant isolation: the deep-analysis store (_deep_store) is a process-global dict shared
across all orgs. GET /v1/map/{map_id} must serve ONLY the caller's org's analysis — keying by
map_id alone was an IDOR (any org could read any map_id). The store key is now org-scoped.
"""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi import HTTPException

from apps.api_server.routers import data_map as dm
from apps.api_server.services import data_map_deep_analysis as dmda
from apps.api_server.services.data_map_deep_analysis import deep_store_key


@pytest.fixture(autouse=True)
def _clear_store():
    dm._deep_store.clear()
    yield
    dm._deep_store.clear()


def test_deep_store_key_is_org_distinct():
    assert deep_store_key("orgA", "m") != deep_store_key("orgB", "m")


async def test_get_deep_analysis_is_org_scoped():
    org_a, org_b, map_id = str(uuid.uuid4()), str(uuid.uuid4()), "map_123"
    dm._deep_store[deep_store_key(org_a, map_id)] = {"map_id": map_id, "secret": "ORG_A_ONLY"}

    # Owner reads its own analysis.
    out = await dm.get_deep_analysis(map_id=map_id, auth={"org_id": org_a})  # type: ignore[arg-type]
    assert out["secret"] == "ORG_A_ONLY"

    # A different org cannot — 404 (existence not even probeable), never org A's data.
    with pytest.raises(HTTPException) as exc:
        await dm.get_deep_analysis(map_id=map_id, auth={"org_id": org_b})  # type: ignore[arg-type]
    assert exc.value.status_code == 404


async def test_writer_stores_under_the_org_scoped_key(monkeypatch):
    async def _fake_run(**kwargs):
        return {"map_id": kwargs["map_id"], "ok": True}

    monkeypatch.setattr(dmda, "run_deep_analysis", _fake_run)
    store: dict[str, dict] = {}
    _deep, pending = await dmda.run_or_schedule_deep_analysis(
        org_id="orgX",
        map_id="mapY",
        parsed_sources={},
        source_profiles=None,
        match_pairs=[],
        mappings=[],
        unified_schema={},
        deep_store=store,
        deep_budget_s=5.0,
        logger=logging.getLogger("test"),
        call_mojo_join_detect_fn=None,
        call_mojo_relation_detect_fn=None,
        call_mojo_field_map_fn=None,
        detect_derived_relationships_fn=None,
        normalize_fn=None,
    )
    assert pending is False
    # Stored under the org-scoped key only — never the bare map_id.
    assert list(store.keys()) == [deep_store_key("orgX", "mapY")]
    assert "mapY" not in store
