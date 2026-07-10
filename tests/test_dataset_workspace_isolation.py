"""Regression tests for #6 — workspace-partitioning of the on-disk dataset inventory.

Covers the load-bearing read gate (dataset_visible / dataset_in_workspace_scope), the
Option-A per-workspace source_id, the gated by-name wrapper, and the planner cache-key
workspace dimension. The acceptance oracle: a workspace-scoped caller never sees another
workspace's (or a legacy/unstamped) dataset, while an unscoped (org-wide) platform call sees all.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest

from apps.api_server.models.data_connector import (
    ConnectorStatus,
    ConnectorType,
    ConnectorVisibility,
    DataConnector,
)
from apps.api_server.services import data_visibility as dv
from apps.api_server.services.source_registration_scope import resolve_registration_scopes

WS_A = uuid.uuid4()
WS_B = uuid.uuid4()
ORG_UUID = uuid.uuid4()


def _auth(*, workspace_id=None, key_id="platform-key", user_id=None, role="member") -> dict:
    return {
        "org_id": "org-1",
        "user_id": user_id,
        "key_id": key_id,
        "role": role,
        "is_platform": True,
        "workspace_id": workspace_id,
    }


def _entry(*, workspace_id=None, owner_key_id="platform-key", visibility="private") -> dict:
    e = {"id": "ds1", "name": "Orders", "visibility": visibility, "owner_key_id": owner_key_id}
    if workspace_id is not None:
        e["workspace_id"] = str(workspace_id)
    return e


class _ScalarResult:
    def __init__(self, connector: DataConnector | None) -> None:
        self.connector = connector

    def scalar_one_or_none(self) -> DataConnector | None:
        return self.connector


class _FakeConnectorDb:
    def __init__(self, connector: DataConnector | None) -> None:
        self.connector = connector
        self.execute_count = 0
        self.expunged: list[DataConnector] = []

    async def execute(self, _statement: object) -> _ScalarResult:
        self.execute_count += 1
        return _ScalarResult(self.connector)

    def expunge(self, connector: DataConnector) -> None:
        self.expunged.append(connector)


def _connector(
    *,
    connector_id: uuid.UUID | None = None,
    connector_type: ConnectorType = ConnectorType.POSTGRES,
    owner_key_id: uuid.UUID | None = None,
) -> DataConnector:
    return DataConnector(
        id=connector_id or uuid.uuid4(),
        org_id=ORG_UUID,
        name="Connector",
        connector_type=connector_type,
        config_json="{}",
        status=ConnectorStatus.UNTESTED,
        visibility=ConnectorVisibility.PRIVATE.value,
        owner_key_id=owner_key_id,
    )


# ── dataset_in_workspace_scope truth table ────────────────────────────────────
def test_workspace_scope_none_auth_sees_everything() -> None:
    # Unscoped platform call (or pre-sub-tenancy key) → org-wide.
    assert dv.dataset_in_workspace_scope(_entry(workspace_id=WS_A), _auth(workspace_id=None))
    assert dv.dataset_in_workspace_scope(_entry(workspace_id=None), _auth(workspace_id=None))


def test_workspace_scope_match_and_mismatch() -> None:
    assert dv.dataset_in_workspace_scope(_entry(workspace_id=WS_A), _auth(workspace_id=WS_A))
    assert not dv.dataset_in_workspace_scope(_entry(workspace_id=WS_A), _auth(workspace_id=WS_B))


def test_workspace_scope_legacy_entry_invisible_to_scoped_caller() -> None:
    # Legacy entry (no workspace_id) must NOT leak to a workspace-scoped caller.
    assert not dv.dataset_in_workspace_scope(_entry(workspace_id=None), _auth(workspace_id=WS_A))


def test_workspace_scope_uuid_vs_str_coercion() -> None:
    # auth["workspace_id"] is a uuid.UUID; the entry stores the str form. The compare must coerce.
    entry = _entry(workspace_id=WS_A)  # stores str(WS_A)
    assert isinstance(entry["workspace_id"], str)
    assert dv.dataset_in_workspace_scope(entry, _auth(workspace_id=WS_A))  # UUID vs str → equal


# ── dataset_visible / dataset_manageable: workspace gate beats SHARED ──────────
def test_shared_dataset_is_workspace_bound_for_scoped_caller() -> None:
    shared_a = _entry(workspace_id=WS_A, visibility="shared")
    assert dv.dataset_visible(shared_a, _auth(workspace_id=WS_A))
    assert not dv.dataset_visible(shared_a, _auth(workspace_id=WS_B))  # gate beats shared
    assert dv.dataset_visible(shared_a, _auth(workspace_id=None))  # org-wide sees it


def test_shared_manageable_is_workspace_bound_even_for_admin() -> None:
    shared_a = _entry(workspace_id=WS_A, visibility="shared")
    assert not dv.dataset_manageable(shared_a, _auth(workspace_id=WS_B, role="admin"))


def test_private_dataset_owner_match_within_workspace() -> None:
    entry = _entry(workspace_id=WS_A, owner_key_id="k1", visibility="private")
    assert dv.dataset_visible(entry, _auth(workspace_id=WS_A, key_id="k1"))
    assert not dv.dataset_visible(entry, _auth(workspace_id=WS_B, key_id="k1"))  # wrong ws


# ── get_visible_connector cache contract ─────────────────────────────────────
@pytest.mark.anyio
async def test_get_visible_connector_does_not_cache_data_source_connectors() -> None:
    dv._CONNECTOR_CACHE.clear()
    key_id = uuid.uuid4()
    connector = _connector(owner_key_id=key_id)
    db = _FakeConnectorDb(connector)

    result = await dv.get_visible_connector(
        db,  # type: ignore[arg-type]
        connector.id,
        _auth(key_id=str(key_id)),
    )

    assert result is connector
    assert db.execute_count == 1
    assert db.expunged == []
    assert dv._CONNECTOR_CACHE == {}


@pytest.mark.anyio
async def test_get_visible_connector_caches_repository_read_connectors() -> None:
    dv._CONNECTOR_CACHE.clear()
    key_id = uuid.uuid4()
    connector = _connector(
        connector_type=ConnectorType.GITHUB_REPO,
        owner_key_id=key_id,
    )
    db = _FakeConnectorDb(connector)
    auth = _auth(key_id=str(key_id))

    first = await dv.get_visible_connector(db, connector.id, auth)  # type: ignore[arg-type]
    second = await dv.get_visible_connector(db, connector.id, auth)  # type: ignore[arg-type]

    assert first is connector
    assert second is connector
    assert db.execute_count == 1
    assert db.expunged == [connector]


@pytest.mark.anyio
async def test_get_visible_connector_for_update_bypasses_repository_cache() -> None:
    dv._CONNECTOR_CACHE.clear()
    connector_id = uuid.uuid4()
    key_id = uuid.uuid4()
    cached_connector = _connector(
        connector_id=connector_id,
        connector_type=ConnectorType.GITHUB_REPO,
        owner_key_id=key_id,
    )
    fresh_connector = _connector(
        connector_id=connector_id,
        connector_type=ConnectorType.GITHUB_REPO,
        owner_key_id=key_id,
    )
    auth = _auth(key_id=str(key_id))
    await dv.get_visible_connector(
        _FakeConnectorDb(cached_connector),  # type: ignore[arg-type]
        connector_id,
        auth,
    )
    db = _FakeConnectorDb(fresh_connector)

    result = await dv.get_visible_connector(
        db,  # type: ignore[arg-type]
        connector_id,
        auth,
        for_update=True,
    )

    assert result is fresh_connector
    assert db.execute_count == 1
    assert db.expunged == []


# ── get_visible_source_entry_by_name wrapper gates by workspace ────────────────
def test_get_visible_source_entry_by_name_gates_workspace(monkeypatch) -> None:
    entry = _entry(workspace_id=WS_A)
    monkeypatch.setattr(dv.sreg, "get_source_entry_by_name", lambda org_id, name: entry)
    assert dv.get_visible_source_entry_by_name("org-1", "Orders", _auth(workspace_id=WS_A)) == entry
    assert dv.get_visible_source_entry_by_name("org-1", "Orders", _auth(workspace_id=WS_B)) is None


# ── Option A: per-workspace source_id for identical content under one platform key ─
def test_resolve_registration_scopes_distinct_source_id_per_workspace() -> None:
    def sid(k: str) -> str:
        return hashlib.sha256(k.encode()).hexdigest()[:24]

    common = dict(
        cache_key="content-abc",
        visibility="private",
        auth_user_id=None,
        auth_key_id="platform-key",  # identical across workspaces (the leak premise)
        owner_user_id=None,
        owner_key_id=None,
        source_id_for_fn=sid,
    )
    _, _, _, id_a = resolve_registration_scopes(**common, workspace_id=str(WS_A))
    _, _, _, id_b = resolve_registration_scopes(**common, workspace_id=str(WS_B))
    _, _, _, id_none = resolve_registration_scopes(**common, workspace_id=None)
    assert id_a != id_b  # same content + same key, different workspace → distinct on-disk entry
    assert id_a != id_none and id_b != id_none


# ── planner cache key is workspace-distinct ───────────────────────────────────
def test_planner_auth_scope_key_workspace_distinct() -> None:
    from apps.api_server.routers.query_registry_planner import planner_auth_scope_key

    base = {"user_id": "u", "key_id": "k", "role": "member"}  # identical across workspaces
    a = planner_auth_scope_key({**base, "workspace_id": WS_A})
    b = planner_auth_scope_key({**base, "workspace_id": WS_B})
    none = planner_auth_scope_key(base)
    assert a != b  # platform key shares user/key/role → workspace must disambiguate
    assert a != none and b != none
