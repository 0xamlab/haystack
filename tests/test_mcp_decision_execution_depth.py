"""A3 behavioral-matrix: real depth for execute_decision at the MCP layer.

Existing coverage (tests/test_mcp_llm_agent_tools.py) only checks that execute_decision_handler
FORWARDS the right HTTP method/path/body — the downstream ``api()`` call is monkeypatched to a
fake that returns a canned dict, so nothing is proven about what actually comes back once a real
decision is really executed against the real router + real DB + real execution-policy service.

These tests drive the REAL stack end to end:
  - a REAL live apps.api_server.main:app process (real Postgres, migrated schema)
  - a REAL org + owner API key seeded directly in Postgres
  - the REAL MCP tool handlers (apps.mcp_server.tools.decisions), going over real HTTP via
    apps.mcp_server.client.request_overrides (no mocking of Algenta's own client/server logic)
  - a REAL execution-policy gate check (apps.api_server.services.execution_policy_service),
    exercised for real -- not monkeypatched
  - the ONE genuinely external boundary stubbed: the customer's downstream webhook endpoint,
    stood in for by a real loopback HTTP server (tests/_webhook_receiver.py) -- the same boundary
    tests/test_decisions_api.py already stubs (there via async_http_request; here by actually
    listening on the wire, since this suite wants the real HTTP round trip end to end)

Covers:
  1. Receipt correctness: execute_decision_handler's real response really carries every real
     ExecutionReceipt field (decision_id, execution_status, response_code, executed_at,
     policy_snapshot_id, schema_snapshot_id, manifest_version, payload_summary,
     safety_overridden) with real values, and the webhook really received the payload.
  2. Idempotency: a second execute_decision call for the same decision_id is really blocked by
     the real already_executed/idempotency gate (real 409, real error code/shape surfaced through
     apps.mcp_server.errors.MCPAPIError); force=true really bypasses ONLY that gate (confidence /
     risk_floor gates still apply -- force does not touch them).
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from apps.mcp_server.client import request_overrides
from apps.mcp_server.errors import MCPAPIError
from apps.mcp_server.tools import decisions
from tests._mcp_live_server_fixture import live_api_server, seed_owner_org_and_key
from tests._webhook_receiver import webhook_receiver

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module")
def live_server():
    runtime_dir = Path(tempfile.mkdtemp(prefix="a3-decisions-runtime-"))
    with live_api_server(runtime_dir=runtime_dir) as base_url:
        yield base_url


@pytest.fixture(scope="module")
def owner_auth(live_server: str) -> tuple[str, str]:
    del live_server  # ordering only: DB schema is migrated before we insert into it
    return asyncio.run(seed_owner_org_and_key("decisions"))


@pytest.fixture()
def webhook():
    with webhook_receiver() as (url, received):
        yield url, received


async def _log_real_decision(
    *, base_url: str, owner_key: str, confidence: float, chosen_action: str = "expand"
) -> str:
    with request_overrides(api_key=owner_key, base_url=base_url):
        body = json.loads(
            await decisions.log_decision_handler(
                {
                    "chosen_action": chosen_action,
                    "context": "A3 execution-depth test",
                    "expected_value": 128000.0,
                    "confidence": confidence,
                }
            )
        )
    decision_id = body["decision_id"]
    assert decision_id, f"log_decision_handler did not return a decision_id: {body}"
    return str(decision_id)


async def test_execute_decision_returns_real_receipt_fields(
    live_server: str, owner_auth: tuple[str, str], webhook: tuple[str, list[dict]]
) -> None:
    owner_key, _org_id = owner_auth
    webhook_url, received = webhook

    decision_id = await _log_real_decision(base_url=live_server, owner_key=owner_key, confidence=0.9)

    with request_overrides(api_key=owner_key, base_url=live_server):
        receipt = json.loads(
            await decisions.execute_decision_handler(
                {
                    "decision_id": decision_id,
                    "webhook_url": webhook_url,
                    "timeout_seconds": 10,
                }
            )
        )

    # Every real ExecutionReceipt field, with real (not placeholder) values.
    assert receipt["decision_id"] == decision_id
    assert receipt["webhook_url"] == webhook_url
    assert receipt["execution_status"] == "delivered", receipt
    assert receipt["response_code"] == 200
    assert receipt["executed_at"], "executed_at must be a real timestamp"
    assert receipt["policy_snapshot_id"].startswith("execution-policy-v1")
    assert receipt["schema_snapshot_id"], "schema_snapshot_id must be populated from the real runtime manifest"
    assert receipt["manifest_version"], "manifest_version must be populated from the real runtime manifest"
    assert receipt["payload_summary"] == {
        "chosen_action": "expand",
        "expected_value": 128000.0,
        "confidence": 0.9,
    }
    assert receipt["safety_overridden"] is False

    # The webhook genuinely received the decision payload (real network round trip).
    assert len(received) == 1, received
    sent = received[0]["payload"]
    assert sent["event"] == "decision.execute"
    assert sent["decision_id"] == decision_id
    assert sent["decision"]["chosen_action"] == "expand"
    assert sent["decision"]["confidence"] == 0.9
    assert sent["integrity"]["policy_snapshot_id"] == receipt["policy_snapshot_id"]
    assert sent["integrity"]["schema_snapshot_id"] == receipt["schema_snapshot_id"]


async def test_execute_decision_second_call_blocked_by_real_idempotency_gate(
    live_server: str, owner_auth: tuple[str, str], webhook: tuple[str, list[dict]]
) -> None:
    owner_key, _org_id = owner_auth
    webhook_url, received = webhook
    decision_id = await _log_real_decision(base_url=live_server, owner_key=owner_key, confidence=0.9)

    with request_overrides(api_key=owner_key, base_url=live_server):
        first = json.loads(
            await decisions.execute_decision_handler(
                {"decision_id": decision_id, "webhook_url": webhook_url}
            )
        )
        assert first["execution_status"] == "delivered"
        assert len(received) == 1

        with pytest.raises(MCPAPIError) as excinfo:
            await decisions.execute_decision_handler(
                {"decision_id": decision_id, "webhook_url": webhook_url}
            )

    err = excinfo.value
    assert err.status_code == 409
    assert err.error_code == "execution_blocked_idempotency"
    # The real gate/detail shape from execution_policy_service.check_execution_gates, surfaced
    # through the real HTTPException detail -> the API's response-contract middleware normalizes
    # it to a top-level "error" key -> apps.mcp_server.client's structured-error parsing.
    inner_error = err.payload["error"]
    assert inner_error["gate"] == "idempotency"
    assert "force=true" in inner_error["override_hint"].lower() or "force" in inner_error["override_hint"].lower()
    # Blocked before dispatch: the webhook did NOT receive a second delivery.
    assert len(received) == 1, "idempotency gate must block before the webhook is re-hit"


async def test_execute_decision_force_bypasses_idempotency_but_not_confidence_gate(
    live_server: str, owner_auth: tuple[str, str], webhook: tuple[str, list[dict]]
) -> None:
    """force=true re-executes an already-delivered decision (idempotency gate only). It does
    NOT double as override_safety: a separately-logged low-confidence decision is still blocked
    by the confidence gate even with force=true, proving the two flags gate independently -- the
    real, already-established execute_decision contract (apps/api_server/services/
    execution_policy_service.py's own docstring: "force: bypass the idempotency gate only")."""
    owner_key, _org_id = owner_auth
    webhook_url, received = webhook

    # -- force bypasses idempotency --
    decision_id = await _log_real_decision(base_url=live_server, owner_key=owner_key, confidence=0.9)
    with request_overrides(api_key=owner_key, base_url=live_server):
        first = json.loads(
            await decisions.execute_decision_handler(
                {"decision_id": decision_id, "webhook_url": webhook_url}
            )
        )
        assert first["execution_status"] == "delivered"

        # Without force, this decision_id is now blocked (sanity check on the same fixture state).
        with pytest.raises(MCPAPIError) as blocked:
            await decisions.execute_decision_handler(
                {"decision_id": decision_id, "webhook_url": webhook_url}
            )
        assert blocked.value.error_code == "execution_blocked_idempotency"

        # With force=true, the SAME decision_id re-executes successfully.
        second = json.loads(
            await decisions.execute_decision_handler(
                {"decision_id": decision_id, "webhook_url": webhook_url, "force": True}
            )
        )
        assert second["execution_status"] == "delivered"
        assert second["safety_overridden"] is False  # force != override_safety
    assert len(received) == 2, "exactly the two successful deliveries (first + forced re-execute)"

    # -- force does NOT bypass the confidence gate on a fresh (never-executed) low-confidence
    #    decision: idempotency isn't even in play here (already_executed=False), so this isolates
    #    that force's bypass is scoped to the idempotency check alone. --
    low_confidence_id = await _log_real_decision(
        base_url=live_server, owner_key=owner_key, confidence=0.1, chosen_action="pause"
    )
    with request_overrides(api_key=owner_key, base_url=live_server):
        with pytest.raises(MCPAPIError) as confidence_blocked:
            await decisions.execute_decision_handler(
                {"decision_id": low_confidence_id, "webhook_url": webhook_url, "force": True}
            )
        assert confidence_blocked.value.error_code == "execution_blocked_confidence"

        # override_safety (a DIFFERENT flag) is what actually bypasses the confidence gate.
        overridden = json.loads(
            await decisions.execute_decision_handler(
                {
                    "decision_id": low_confidence_id,
                    "webhook_url": webhook_url,
                    "override_safety": True,
                }
            )
        )
        assert overridden["execution_status"] == "delivered"
        assert overridden["safety_overridden"] is True
    assert len(received) == 3
