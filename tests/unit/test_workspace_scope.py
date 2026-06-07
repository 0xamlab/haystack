"""Unit tests for workspace sub-tenancy scope helpers (Phase 1b)."""

import uuid

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.services.workspace_scope import (
    workspace_id_for_write,
    workspace_scope_clauses,
)


def test_scope_clauses_org_only_when_no_workspace() -> None:
    org = uuid.uuid4()
    clauses = workspace_scope_clauses(DataConnector, {"org_id": org})
    assert len(clauses) == 1
    assert clauses[0].left.name == "org_id"
    assert clauses[0].right.value == org


def test_scope_clauses_include_workspace_when_present() -> None:
    org = uuid.uuid4()
    ws = uuid.uuid4()
    clauses = workspace_scope_clauses(DataConnector, {"org_id": org, "workspace_id": ws})
    assert len(clauses) == 2
    by_col = {c.left.name: c.right.value for c in clauses}
    assert by_col == {"org_id": org, "workspace_id": ws}


def test_scope_clauses_treat_none_workspace_as_org_wide() -> None:
    org = uuid.uuid4()
    clauses = workspace_scope_clauses(DataConnector, {"org_id": org, "workspace_id": None})
    assert len(clauses) == 1
    assert clauses[0].left.name == "org_id"


def test_workspace_id_for_write() -> None:
    ws = uuid.uuid4()
    assert workspace_id_for_write({"org_id": uuid.uuid4(), "workspace_id": ws}) == ws
    assert workspace_id_for_write({"org_id": uuid.uuid4()}) is None
    assert workspace_id_for_write({"org_id": uuid.uuid4(), "workspace_id": None}) is None
