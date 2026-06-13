"""Service-key (is_service) visibility allowance — the agent's engine-callback key.

A service key gets a NARROW, org-scoped allowance to READ repository connectors (so the agent can
run its /v1 callbacks) and nothing else: not other orgs' connectors, not data-source connectors,
and never management. These are pure-function checks (no DB), guarding the allowance in
apps/api_server/services/data_visibility.py against regression / accidental widening.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api_server.middleware.rbac import forbid_service_key
from apps.api_server.models.data_connector import ConnectorType, ConnectorVisibility
from apps.api_server.services.data_visibility import (
    _REPO_CONNECTOR_TYPES,
    connector_manageable,
    connector_visible,
)
from apps.api_server.services.repository_intelligence_repository_source import (
    REPOSITORY_CONNECTOR_TYPES,
)

ORG = uuid.uuid4()
OTHER_ORG = uuid.uuid4()


def _conn(
    *,
    org_id: uuid.UUID,
    ctype: str,
    visibility: str = ConnectorVisibility.PRIVATE.value,
    owner_user_id: str | None = None,
    owner_key_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        org_id=org_id,
        connector_type=ctype,
        visibility=visibility,
        owner_user_id=owner_user_id,
        owner_key_id=owner_key_id,
    )


def _auth(*, org_id: uuid.UUID, is_service: bool = False, role: str = "viewer") -> dict:
    return {
        "org_id": org_id,
        "user_id": None,
        "key_id": uuid.uuid4(),
        "role": role,
        "is_service": is_service,
    }


def test_service_key_sees_every_own_org_repo_connector_kind() -> None:
    # Includes local_repo / repo_archive — the self-hosted agent path, not just the SaaS git hosts.
    for ctype in (
        ConnectorType.GITHUB_REPO.value,
        ConnectorType.GITLAB_REPO.value,
        ConnectorType.BITBUCKET_REPO.value,
        ConnectorType.LOCAL_REPO.value,
        ConnectorType.REPO_ARCHIVE.value,
    ):
        conn = _conn(org_id=ORG, ctype=ctype)
        assert connector_visible(conn, _auth(org_id=ORG, is_service=True)) is True


def test_repo_type_allowlist_matches_canonical_set() -> None:
    # Drift guard: the visibility allowlist must equal the engine's canonical repository-type set,
    # or local_repo/repo_archive (or a future repo kind) would silently 404 the agent callback.
    assert _REPO_CONNECTOR_TYPES == REPOSITORY_CONNECTOR_TYPES


def test_service_key_cannot_see_other_orgs_repo_connector() -> None:
    conn = _conn(org_id=OTHER_ORG, ctype=ConnectorType.GITHUB_REPO.value)
    assert connector_visible(conn, _auth(org_id=ORG, is_service=True)) is False


def test_service_key_cannot_see_data_source_connector() -> None:
    # A non-repository connector (e.g. a postgres data source with credentials) is out of scope.
    conn = _conn(org_id=ORG, ctype=ConnectorType.POSTGRES.value)
    assert connector_visible(conn, _auth(org_id=ORG, is_service=True)) is False


def test_service_key_can_never_manage_a_connector() -> None:
    conn = _conn(org_id=ORG, ctype=ConnectorType.GITHUB_REPO.value)
    assert connector_manageable(conn, _auth(org_id=ORG, is_service=True)) is False


def test_non_service_key_behaviour_unchanged() -> None:
    # A normal (non-service) viewer that doesn't own a PRIVATE repo connector still can't see it —
    # the allowance must not leak to ordinary keys.
    conn = _conn(
        org_id=ORG,
        ctype=ConnectorType.GITHUB_REPO.value,
        owner_user_id=str(uuid.uuid4()),
        owner_key_id=str(uuid.uuid4()),
    )
    assert connector_visible(conn, _auth(org_id=ORG, is_service=False)) is False


def test_shared_connector_still_visible_to_service_key() -> None:
    # SHARED short-circuits before the allowance, so it is unaffected by is_service.
    conn = _conn(
        org_id=ORG,
        ctype=ConnectorType.POSTGRES.value,
        visibility=ConnectorVisibility.SHARED.value,
    )
    assert connector_visible(conn, _auth(org_id=ORG, is_service=True)) is True


def test_forbid_service_key_blocks_writes_but_allows_normal_keys() -> None:
    # /apply (external write) calls forbid_service_key: a service key is 403'd, a normal key passes.
    with pytest.raises(HTTPException) as exc:
        forbid_service_key(_auth(org_id=ORG, is_service=True), "repository apply")
    assert exc.value.status_code == 403
    # A normal (non-service) key is a no-op (returns None, does not raise).
    assert forbid_service_key(_auth(org_id=ORG, is_service=False), "repository apply") is None
