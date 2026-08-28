"""A4: the execution receipt is a versioned, typed contract.

WHAT WAS WRONG. `ExecutionPlanResponse.receipt` was `dict[str, Any]`, built inline as three keys:

    plan.receipt = {"executed_at": ..., "prepared_artifacts": [...], "action_count": N}

and the only existing assertion about it was `assert executed["receipt"]` -- that it was truthy.
A receipt is what an operator, an auditor, or a partner's compliance review relies on to establish
that *this execution happened, under this plan, with this approval*. That makes its shape an
interface, and an unversioned interface cannot be changed without silently breaking whoever parses
it. So this file asserts the envelope, not merely its presence.

WHAT IS DELIBERATELY NULL. `policy_snapshot_hash` is declared but None on this path, because the
decision-plan path genuinely carries no policy snapshot (grep policy_snapshot across
apps/api_server/services/decision_service/ -> nothing). It is present so the shape is stable for
the surfaces that DO record policy evidence, and so a consumer's parser does not change when they
adopt it. Filling it with a plan hash would put a non-policy value in a field named for policy,
which on an evidence artifact is worse than a null: a null is legible, a mislabel is trusted.
There is a test asserting it stays None for exactly that reason.

The flow driven here is the real one -- real router, real DecisionService, real RequestIDMiddleware
-- through propose (plan_hash + single-use nonce) -> approve -> execute.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI

from apps.api_server.middleware.auth import get_current_org, require_verified_email
from apps.api_server.middleware.request_id import (
    REQUEST_ID_HEADER,
    TRACEPARENT_HEADER,
    RequestIDMiddleware,
)
from apps.api_server.routers import decision_cases
from apps.api_server.schemas.receipt import RECEIPT_VERSION, ExecutionReceipt
from apps.api_server.services.decision_service import (
    DecisionService,
    InMemoryDecisionRepository,
)
from tests._asgi_client import SyncASGIClient

_ORG = uuid.uuid4()

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
TRACEPARENT = f"00-{TRACE}-00f067aa0ba902b7-01"

# Every field the envelope promises. Named here so a removal is a test failure rather than a
# silently thinner receipt.
ENVELOPE_FIELDS = {
    "receipt_version", "status", "code", "retryable",
    "request_id", "trace_id", "idempotency_key",
    "execution_id", "plan_hash", "approval_state", "policy_snapshot_hash",
    "executed_at", "result",
}


def _auth_ctx(org_id: uuid.UUID) -> dict[str, Any]:
    return {
        "org_id": org_id,
        "user_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
        "plan": "pro",
        "is_platform": False,
        "workspace_id": None,
        "role": "admin",
    }


class _StubSession:
    async def commit(self) -> None:
        return None


def _app() -> FastAPI:
    """Real router + real service + the REAL request-id/trace middleware.

    The middleware is included deliberately: the correlation fields only reach the receipt if the
    middleware, the router's scope builder and the service all agree. Testing the service alone
    would assert plumbing that no request actually travels through.
    """
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(decision_cases.router)
    service = DecisionService(InMemoryDecisionRepository())
    ctx = _auth_ctx(_ORG)
    app.dependency_overrides[get_current_org] = lambda: ctx
    app.dependency_overrides[require_verified_email] = lambda: ctx
    app.dependency_overrides[decision_cases.get_db] = lambda: _StubSession()
    app.dependency_overrides[decision_cases.get_decision_service] = lambda: service
    return app


def _create_body() -> dict[str, Any]:
    return {
        "pack_id": "renewal_capacity_allocation",
        "title": "Q3 renewals",
        "pack_input": {
            "accounts": [
                {"account_id": "A1", "name": "BigCo", "arr": 500000,
                 "renewal_date": "2026-08-01", "health_score": 40, "segment": "standard"},
                {"account_id": "A5", "name": "KeyStrategic", "arr": 90000,
                 "renewal_date": "2026-08-01", "health_score": 50, "segment": "strategic"},
            ],
            "capacity": {"total_hours": 40},
            "constraints": {"strategic_min_hours": 4, "allocation_step_hours": 1},
            "horizon_days": 90,
        },
    }


def _execute(client: SyncASGIClient, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Drive the genuine governed flow and return the executed plan's receipt."""
    case = client.post("/v1/decision-cases", json=_create_body()).json()
    run = client.post(
        f"/v1/decision-cases/{case['case_id']}/analysis-runs", json={}
    ).json()
    plan = client.post(f"/v1/analysis-runs/{run['run_id']}/action-plans").json()
    assert plan["plan_hash"] and plan["nonce"], plan
    approved = client.post(
        f"/v1/decision-plans/{plan['plan_id']}/approve",
        json={"plan_hash": plan["plan_hash"], "nonce": plan["nonce"]},
    )
    assert approved.status_code == 200, approved.text
    r = client.post(f"/v1/decision-plans/{plan['plan_id']}/execute", headers=headers or {})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["receipt"], "execution produced no receipt"
    body["receipt"]["_plan_hash_from_plan"] = plan["plan_hash"]
    body["receipt"]["_plan_id"] = plan["plan_id"]
    return body["receipt"]


# ── the envelope ────────────────────────────────────────────────────────────────────────────────


def test_the_receipt_carries_every_envelope_field() -> None:
    with SyncApp() as client:
        receipt = _execute(client)
    present = set(receipt) - {"_plan_hash_from_plan", "_plan_id"}
    missing = ENVELOPE_FIELDS - present
    assert not missing, f"receipt is missing envelope fields: {sorted(missing)}"


def test_the_receipt_is_versioned() -> None:
    """Without a version a consumer cannot tell an old receipt from a new one."""
    with SyncApp() as client:
        receipt = _execute(client)
    assert receipt["receipt_version"] == RECEIPT_VERSION
    assert isinstance(receipt["receipt_version"], str), (
        "version must be a string so a future '2.1' needs no schema change"
    )


def test_a_successful_execution_reports_executed_and_not_retryable() -> None:
    with SyncApp() as client:
        receipt = _execute(client)
    assert receipt["status"] == "executed"
    assert receipt["code"] is None
    assert receipt["retryable"] is False, (
        "a completed execution must not invite a retry -- re-running it is exactly what the "
        "execute-once guarantee exists to prevent"
    )


def test_the_receipt_binds_to_the_approved_plan_hash() -> None:
    """The approval was bound to this hash, so the evidence must name it."""
    with SyncApp() as client:
        receipt = _execute(client)
    assert receipt["plan_hash"] == receipt["_plan_hash_from_plan"]
    assert receipt["approval_state"] == "approved"


def test_the_execution_id_is_distinct_from_the_plan_and_unique_per_execution() -> None:
    """The plan is what was authorised; execution_id is the act. They are not the same thing.

    The `!= plan_id` assertion is the load-bearing one and was missing at first: because each run
    of _execute creates a fresh plan, the uniqueness check alone passed even when execution_id was
    literally plan.id. Mutation-checked -- aliasing them now fails here. A test whose name claims
    more than its assertions check is worse than no test, because the name is what gets trusted.
    """
    with SyncApp() as client:
        first = _execute(client)
        second = _execute(client)
    uuid.UUID(first["execution_id"])  # parses
    assert first["execution_id"] != first["_plan_id"], (
        "execution_id is just the plan id; it then cannot distinguish the authorisation from the "
        "act, and a replayed execution would be indistinguishable from the original"
    )
    assert first["execution_id"] != second["execution_id"], (
        "two executions shared an execution_id; the field cannot then identify an act"
    )


def test_policy_snapshot_hash_is_null_not_invented() -> None:
    """This path has no policy snapshot. An honest null beats a mislabelled hash."""
    with SyncApp() as client:
        receipt = _execute(client)
    assert receipt["policy_snapshot_hash"] is None, (
        "policy_snapshot_hash was populated on a path that carries no policy snapshot -- a value "
        "in a field named for policy evidence will be read as policy evidence"
    )


# ── correlation ─────────────────────────────────────────────────────────────────────────────────


def test_the_receipt_records_the_request_that_produced_it() -> None:
    with SyncApp() as client:
        receipt = _execute(client, headers={REQUEST_ID_HEADER: "req_a4_probe"})
    assert receipt["request_id"] == "req_a4_probe"


def test_the_receipt_joins_the_callers_trace() -> None:
    """One agent turn can yield several receipts; the trace is what reassembles them."""
    with SyncApp() as client:
        receipt = _execute(client, headers={TRACEPARENT_HEADER: TRACEPARENT})
    assert receipt["trace_id"] == TRACE


def test_the_idempotency_key_is_echoed_when_supplied() -> None:
    """So a retry can be matched to the outcome of its original."""
    with SyncApp() as client:
        receipt = _execute(client, headers={"Idempotency-Key": "idem-a4-001"})
    assert receipt["idempotency_key"] == "idem-a4-001"


def test_an_absent_idempotency_key_is_null_not_empty_string() -> None:
    with SyncApp() as client:
        receipt = _execute(client)
    assert receipt["idempotency_key"] is None


# ── backwards compatibility ─────────────────────────────────────────────────────────────────────


def test_the_original_receipt_keys_survive_under_result() -> None:
    """Adding an envelope must not strip what an existing consumer already reads."""
    with SyncApp() as client:
        receipt = _execute(client)
    result = receipt["result"]
    assert set(result) >= {"executed_at", "prepared_artifacts", "action_count"}, (
        f"the pre-existing receipt keys were dropped: {result}"
    )
    assert result["action_count"] == len(result["prepared_artifacts"])


# ── the model itself ────────────────────────────────────────────────────────────────────────────


def test_the_stored_form_is_json_safe() -> None:
    """asyncpg cannot adapt uuid/datetime inside JSONB; a receipt that fails to persist is none."""
    import json

    r = ExecutionReceipt(status="executed", execution_id=uuid.uuid4())
    json.dumps(r.to_stored())  # raises if a uuid/datetime leaked through


def test_a_denial_can_be_expressed_with_a_code_and_retryability() -> None:
    """The envelope has to describe refusals, not just successes."""
    r = ExecutionReceipt(
        status="denied", code="plan_hash_mismatch", retryable=False,
        execution_id=uuid.uuid4(),
    )
    stored = r.to_stored()
    assert stored["status"] == "denied"
    assert stored["code"] == "plan_hash_mismatch"
    assert stored["retryable"] is False


class SyncApp:
    """Context manager wrapping the shared app+client construction."""

    def __enter__(self) -> SyncASGIClient:
        self._c = SyncASGIClient(_app())
        return self._c.__enter__()

    def __exit__(self, *exc: object) -> None:
        self._c.__exit__(*exc)
