"""A3 behavioral-matrix: real depth for approve_agent_run at the MCP layer.

Existing coverage of approve_agent_run (tests/test_mcp_llm_agent_tools.py's
test_mcp_llm_and_agent_specs_expose_required_fields and the request-forwarding parametrized
test elsewhere in that file) only proves the MCP tool forwards to
POST /v1/agent/runs/{id}/approve -- never that approving actually flips the run's real,
persisted state.

This test drives the REAL stack end to end:
  - a REAL live apps.api_server.main:app process (real Postgres for auth; agent runs themselves
    are file-backed under ALGENTA_RUNTIME_DIR, per apps/api_server/services/agent_run_service)
  - a REAL org + owner API key seeded directly in Postgres
  - the REAL MCP tools (apps.mcp_server.tools.agent_runs): create_agent_run_handler then
    approve_agent_run_handler, going over real HTTP via apps.mcp_server.client.request_overrides
  - a SEPARATE, independent verification path that does NOT go through the MCP tool at all:
    apps.api_server.services.agent_run_service.get_agent_run(...) called directly in-process,
    reading the same ALGENTA_RUNTIME_DIR the live server just wrote to. This is the exact real
    service function tests/test_agent_run_service.py already uses as its own ground truth for
    "did the state really change" -- reused here as the independent check, per the task's own
    request to verify via "whatever real API/DB path already exists in test fixtures elsewhere
    in this repo."

Nothing here mocks Algenta's own logic: the MCP tool, the FastAPI router, and the agent-run
service all run for real. The only external boundary in scope (auth against a real API key) is
also real.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from apps.mcp_server.client import request_overrides
from apps.mcp_server.tools import agent_runs
from tests._mcp_live_server_fixture import live_api_server, seed_owner_org_and_key

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module")
def runtime_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="a3-agent-runs-runtime-"))


@pytest.fixture(scope="module")
def live_server(runtime_dir: Path):
    with live_api_server(runtime_dir=runtime_dir) as base_url:
        yield base_url


@pytest.fixture(scope="module")
def owner_auth(live_server: str) -> tuple[str, str]:
    del live_server
    return asyncio.run(seed_owner_org_and_key("agent-runs"))


async def test_approve_agent_run_via_mcp_tool_really_changes_persisted_state(
    live_server: str,
    owner_auth: tuple[str, str],
    runtime_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_key, org_id = owner_auth

    # 1) Create a MANUAL-approval agent run through the real MCP tool over real HTTP.
    with request_overrides(api_key=owner_key, base_url=live_server):
        created = json.loads(
            await agent_runs.create_agent_run_handler(
                {
                    "task": "Find the most relevant market research documents",
                    "tools": ["search"],
                    "approval_mode": "manual",
                }
            )
        )
    run_id = created["run_id"]
    assert created["status"] == "requires_approval", created
    assert created["pending_action"] == "approve", created
    assert created["result"] is None

    # 2) SEPARATE, independent real check #1 (not through the MCP tool, not through HTTP):
    #    the real agent_run_service, reading the same on-disk runtime state the live server
    #    process just wrote.
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir))
    from apps.api_server.services import agent_run_service

    before = agent_run_service.get_agent_run(run_id=run_id, auth={"org_id": org_id})
    assert before.status == "requires_approval"
    assert before.pending_action == "approve"
    assert before.result is None

    # 3) Approve via the real MCP tool over real HTTP.
    with request_overrides(api_key=owner_key, base_url=live_server):
        approved = json.loads(await agent_runs.approve_agent_run_handler({"run_id": run_id}))
    assert approved["status"] == "completed", approved
    assert approved["pending_action"] is None

    # 4) SEPARATE, independent real check #2: re-fetch through agent_run_service directly and
    #    confirm the state genuinely changed on disk -- not just that the MCP call returned 200.
    after = agent_run_service.get_agent_run(run_id=run_id, auth={"org_id": org_id})
    assert after.status == "completed"
    assert after.pending_action is None
    assert after.tools_used == ["search"]
    assert after.result is not None

    # 5) And the real event log recorded the real approval transition (run_approved), matching
    #    tests/test_agent_run_service.py's own expected event sequence for this exact scenario.
    events = agent_run_service.get_agent_run_events(run_id=run_id, auth={"org_id": org_id})
    event_types = [event.event_type for event in events]
    assert "run_approved" in event_types, event_types
    assert event_types.index("run_approved") < event_types.index("run_completed")


async def test_approving_an_already_completed_run_is_rejected_for_real(
    live_server: str, owner_auth: tuple[str, str]
) -> None:
    """approve_agent_run on a run that is NOT waiting for approval is a real, existing error
    path (agent_run_service.approve_agent_run raises agent_run_invalid_state) -- confirm it
    surfaces through the real MCP tool too, not just a happy-path 200."""
    owner_key, _org_id = owner_auth

    with request_overrides(api_key=owner_key, base_url=live_server):
        created = json.loads(
            await agent_runs.create_agent_run_handler(
                {"task": "Summarize last quarter's incident reports", "approval_mode": "auto"}
            )
        )
        run_id = created["run_id"]
        assert created["status"] == "completed"  # auto mode: nothing pending

        from apps.mcp_server.errors import MCPAPIError

        with pytest.raises(MCPAPIError) as excinfo:
            await agent_runs.approve_agent_run_handler({"run_id": run_id})

    assert excinfo.value.status_code in (400, 409)
