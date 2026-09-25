"""Idempotent delete/cancel family — DB-free unit coverage.

Covers the two stores that need no Postgres:
  - delete_trigger (in-memory _TRIGGER_STORE router path)
  - cancel_agent_run (file-backed agent-run store under ALGENTA_RUNTIME_DIR)
plus the MCP-handler already_absent envelope and the annotation contract for the
whole family (9 idempotent delete/cancel tools keep idempotentHint=true; the 2
credential revocations flip to false and say so).

DB-backed siblings (delete_connector, disconnect_data, delete_decision,
delete_deployment, disable_skill, cancel_job, remove_team_member) are covered
end-to-end in tests/test_idempotent_delete_family_live.py, which needs the live
API + Postgres fixtures (CI).
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from algenta_mcp import registry as pkg_registry
from algenta_mcp.tools import triggers as pkg_triggers
from fastapi.responses import JSONResponse

from apps.api_server.routers import agent_runs as agent_run_router
from apps.api_server.routers import triggers as trigger_router
from apps.api_server.schemas.agent_runs import AgentRunCreateRequest
from apps.api_server.services import agent_run_service


def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_idempotent_delete_family",
        "key_id": "key_idempotent_delete_family",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


@pytest.fixture(autouse=True)
def _clean_trigger_store():
    trigger_router._TRIGGER_STORE.clear()
    yield
    trigger_router._TRIGGER_STORE.clear()


class _StubDB:
    async def commit(self) -> None:
        return None


# ── delete_trigger (in-memory store) ─────────────────────────────────────────


def _register_trigger(trigger_id: str) -> None:
    key = trigger_router._trigger_key(_fake_auth()["org_id"], trigger_id)
    trigger_router._TRIGGER_STORE[key] = {
        "trigger_id": trigger_id,
        "name": "watch",
        "status": "active",
        "condition": {},
    }


def test_delete_trigger_first_call_deletes_and_repeat_returns_already_absent() -> None:
    auth = _fake_auth()
    _register_trigger("trig-1")
    first = asyncio.run(trigger_router.delete_trigger("trig-1", auth=auth))
    assert first is None  # 204 path: real delete, no body
    assert not any(
        key.endswith("trig-1") for key in trigger_router._TRIGGER_STORE
    ), "the real delete must happen exactly once"

    second = asyncio.run(trigger_router.delete_trigger("trig-1", auth=auth))
    assert isinstance(second, JSONResponse)
    payload = json.loads(bytes(second.body))
    assert payload == {"trigger_id": "trig-1", "deleted": True, "already_absent": True}


def test_delete_trigger_never_existed_returns_already_absent() -> None:
    result = asyncio.run(trigger_router.delete_trigger("trig-ghost", auth=_fake_auth()))
    assert isinstance(result, JSONResponse)
    payload = json.loads(bytes(result.body))
    assert payload == {"trigger_id": "trig-ghost", "deleted": True, "already_absent": True}


# ── cancel_agent_run (file-backed store) with audit non-duplication ──────────


def test_cancel_agent_run_first_and_repeat_and_never_existed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    audit_calls: list[dict] = []

    async def _fake_write_audit_event(db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(agent_run_router, "write_audit_event", _fake_write_audit_event)
    monkeypatch.setattr(agent_run_router, "get_client_ip", lambda request: "127.0.0.1")

    auth = _fake_auth()
    created = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(task="Calculate the expected margin by region", start_paused=True),
            auth=auth,
        )
    )
    assert created.status == "paused"

    first = asyncio.run(
        agent_run_router.cancel_run(uuid.UUID(created.run_id), request=None, auth=auth, db=_StubDB())
    )
    assert first.status == "cancelled"
    assert len(audit_calls) == 1, "the real cancel records exactly one audit event"
    checkpoints_after_first = agent_run_service.get_agent_run_checkpoints(
        run_id=created.run_id, auth=auth
    ).total_checkpoints

    second = asyncio.run(
        agent_run_router.cancel_run(uuid.UUID(created.run_id), request=None, auth=auth, db=_StubDB())
    )
    assert isinstance(second, JSONResponse)
    payload = json.loads(bytes(second.body))
    assert payload["run_id"] == created.run_id
    assert payload["status"] == "cancelled"
    assert payload["already_absent"] is True
    assert len(audit_calls) == 1, "repeat must not double-record the audit event"
    checkpoints_after = agent_run_service.get_agent_run_checkpoints(
        run_id=created.run_id, auth=auth
    ).total_checkpoints
    assert checkpoints_after == checkpoints_after_first, "repeat must not write a new checkpoint"

    ghost = asyncio.run(
        agent_run_router.cancel_run(uuid.uuid4(), request=None, auth=auth, db=_StubDB())
    )
    assert isinstance(ghost, JSONResponse)
    ghost_payload = json.loads(bytes(ghost.body))
    assert ghost_payload["status"] == "cancelled"
    assert ghost_payload["already_absent"] is True
    assert len(audit_calls) == 1


# ── MCP handler envelope ─────────────────────────────────────────────────────


def test_mcp_delete_trigger_handler_surfaces_already_absent(monkeypatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):
        if method == "DELETE":
            return {"trigger_id": "trig-1", "deleted": True, "already_absent": True}
        raise AssertionError(method)

    monkeypatch.setattr(pkg_triggers, "api", _fake_api)
    out = json.loads(asyncio.run(pkg_triggers.delete_trigger_handler({"trigger_id": "trig-1"})))
    assert out == {"trigger_id": "trig-1", "deleted": True, "already_absent": True}


# ── family annotation contract ───────────────────────────────────────────────

IDEMPOTENT_FAMILY = [
    "delete_connector",
    "disconnect_data",
    "delete_decision",
    "delete_trigger",
    "delete_deployment",
    "disable_skill",
    "cancel_job",
    "cancel_agent_run",
    "remove_team_member",
]
REVOCATIONS = ["revoke_api_key", "revoke_device"]


def test_idempotent_delete_family_keeps_idempotent_hint() -> None:
    for name in IDEMPOTENT_FAMILY:
        annotations = pkg_registry.TOOLS[name]["spec"]["annotations"]
        assert annotations["idempotentHint"] is True, name
        assert annotations["destructiveHint"] is True, name
        assert "already_absent" in pkg_registry.TOOLS[name]["spec"]["description"], name


def test_credential_revocations_are_explicitly_not_idempotent() -> None:
    for name in REVOCATIONS:
        spec = pkg_registry.TOOLS[name]["spec"]
        assert spec["annotations"]["idempotentHint"] is False, name
        description = spec["description"].lower()
        assert "not_found" in description, name
        assert "no silent no-op" in description, name
