"""A4: the execution receipt is a versioned, typed contract.

WHAT WAS WRONG, IN TWO LAYERS. Originally `ExecutionPlanResponse.receipt` was `dict[str, Any]`,
built inline as three keys (`plan.receipt = {"executed_at": ..., "prepared_artifacts": [...],
"action_count": N}`), and the only assertion about it anywhere was `assert executed["receipt"]` --
that it was truthy. The first fix (this file's original version) built a real, versioned
`ExecutionReceipt` object internally and stored it correctly -- but the HTTP layer still declared
`receipt: dict[str, Any] | None`, so the internal object flattened back to an opaque blob the
moment it crossed the wire. The OpenAPI spec published `receipt` as `additionalProperties: true`,
and FastAPI's response validation enforced nothing about its shape: a receipt missing every
required field would have serialized and returned 200 exactly like a correct one. Proven, not
assumed -- see test_an_untyped_receipt_field_would_accept_the_broken_shape below, which reverts
the type in-process and shows the old shape passing silently.

The second, follow-up fix types `ExecutionPlanResponse.receipt` as the real
`apps.api_server.schemas.receipt.ExecutionReceipt`, so the contract that was already correct
internally is now the contract on the wire, in the published spec, and under response validation.

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


# ── the wire type (follow-up: the receipt is typed on the response, not just internally) ────────


def test_the_published_spec_types_the_receipt_field_not_an_opaque_object() -> None:
    """`additionalProperties: true` was the actual, live shape of the OpenAPI contract.

    A generated client sees an untyped blob and a partner reading the spec cannot tell what a
    receipt contains -- exactly the failure mode A4 exists to close. Checked against the schema
    the running app actually publishes, not a hand-maintained copy of it.
    """
    from apps.api_server.main import app

    schema = app.openapi()
    receipt_field = schema["components"]["schemas"]["ExecutionPlanResponse"]["properties"]["receipt"]
    refs = [opt["$ref"] for opt in receipt_field.get("anyOf", []) if "$ref" in opt]
    assert refs == ["#/components/schemas/ExecutionReceipt"], (
        f"receipt field does not $ref the versioned ExecutionReceipt schema: {receipt_field}"
    )


def test_execution_receipt_and_decision_webhook_receipt_are_distinct_named_schemas() -> None:
    """Two unrelated concepts once shared the class name `ExecutionReceipt` in this codebase:

    this one (plan_hash/approval_state/execution_id -- governed plan execution) and
    `routers.decisions.DecisionWebhookReceipt` (policy_snapshot_id/webhook_url -- confirmation a
    logged decision's webhook fired). FastAPI disambiguates a genuine name collision safely (by
    fully-qualified module path), so nothing was ever broken by it -- but a partner reading two
    components both titled "ExecutionReceipt" in Swagger UI has no way to tell them apart. Fixed
    by renaming the unrelated one; this asserts the rename stuck and the collision cannot recur
    silently.
    """
    from apps.api_server.main import app

    schema = app.openapi()
    comp = schema["components"]["schemas"]
    assert "ExecutionReceipt" in comp, "the governed-execution receipt schema is missing"
    assert "DecisionWebhookReceipt" in comp, "the webhook-delivery receipt schema is missing"
    assert set(comp["ExecutionReceipt"]["required"]) == {"status", "execution_id"}
    assert "webhook_url" in comp["DecisionWebhookReceipt"]["properties"], (
        "DecisionWebhookReceipt no longer looks like the webhook-delivery receipt -- check the "
        "rename did not also change what routers.decisions returns"
    )


def test_an_untyped_receipt_field_would_accept_the_broken_shape() -> None:
    """Proves the OLD type had no teeth, by reverting to it in-process and showing it stays silent.

    Without this, "the field is now typed" is a claim about source code, not about behaviour. This
    constructs the exact old 3-key shape (executed_at/prepared_artifacts/action_count, no status,
    no execution_id) against a locally-redefined dict[str, Any] response model and confirms it
    validates -- the failure mode this whole fix closes, demonstrated rather than asserted.
    """
    from typing import Any as _Any

    from pydantic import BaseModel as _BaseModel

    class _OldShapeResponse(_BaseModel):
        receipt: dict[str, _Any] | None = None

    old_shaped_receipt = {
        "executed_at": "2026-01-01T00:00:00Z",
        "prepared_artifacts": [],
        "action_count": 0,
    }
    _OldShapeResponse(receipt=old_shaped_receipt)  # must NOT raise -- that is the bug being proven

    class _NewShapeResponse(_BaseModel):
        receipt: ExecutionReceipt | None = None

    try:
        _NewShapeResponse(receipt=old_shaped_receipt)
    except Exception:
        pass
    else:
        raise AssertionError(
            "the real ExecutionReceipt type accepted the old, pre-A4 receipt shape -- the "
            "required fields (status, execution_id) are not actually enforced"
        )


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
