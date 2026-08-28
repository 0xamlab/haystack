"""A named gate must arrive at the client as a name, not as prose.

THE DEFECT, observed live against a running engine before the fix. `decision_cases._http()` raises
`HTTPException(detail={"code": exc.code, "message": exc.message})` for each of the 17 codes it maps
-- plan_hash_mismatch, invalid_nonce, approval_expired, plan_not_approved, stale_plan and the rest.
The HTTPException handler only recognised a `detail` dict containing an "error" key, so those fell
through to the generic fallback:

    {"error": {"code": "http_error",
               "message": "{'code': 'plan_not_approved', 'message': \\"Plan is 'executed'...\\"}"}}

The HTTP status was correct (409 / 403). The machine-readable part was not: `code` said
`http_error`, and the real name was embedded in a Python dict repr inside a human-readable string.
A caller could only recover it by parsing prose -- which then breaks the moment the prose is
reworded, exactly when a caller is least likely to notice.

WHY IT MATTERS BEYOND TIDINESS. The whole proposition of a governed-execution layer is that a
refusal is legible: an agent framework has to distinguish "denied by policy" (do not retry, escalate
to a human) from "approval expired" (re-request approval) from "upstream timeout" (retry). Collapse
them all to `http_error` and the caller's only options are to retry blindly or give up. The
cross-framework conformance suite asserts named gates for scenarios 2, 5, 7 and 8, and could not
have done so against this wire format.

These tests drive the real router through the real flow; the assertions are on the response body a
client actually receives.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException

from apps.api_server.main import app as real_app
from apps.api_server.main import http_exception_handler
from apps.api_server.middleware.auth import get_current_org, require_verified_email
from apps.api_server.routers import decision_cases
from apps.api_server.services.decision_service import (
    DecisionService,
    InMemoryDecisionRepository,
)
from tests._asgi_client import SyncASGIClient

_ORG = uuid.uuid4()


def _auth_ctx() -> dict[str, Any]:
    return {
        "org_id": _ORG, "user_id": uuid.uuid4(), "key_id": uuid.uuid4(),
        "plan": "pro", "is_platform": False, "workspace_id": None, "role": "admin",
    }


class _StubSession:
    async def commit(self) -> None:
        return None


def _app() -> FastAPI:
    """The decision router wired to the REAL exception handler under test."""
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.include_router(decision_cases.router)
    service = DecisionService(InMemoryDecisionRepository())
    ctx = _auth_ctx()
    app.dependency_overrides[get_current_org] = lambda: ctx
    app.dependency_overrides[require_verified_email] = lambda: ctx
    app.dependency_overrides[decision_cases.get_db] = lambda: _StubSession()
    app.dependency_overrides[decision_cases.get_decision_service] = lambda: service
    return app


def _create_body() -> dict[str, Any]:
    return {
        "pack_id": "renewal_capacity_allocation",
        "title": "named-code probe",
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


def _proposed_plan(client: SyncASGIClient) -> dict[str, Any]:
    case = client.post("/v1/decision-cases", json=_create_body()).json()
    run = client.post(f"/v1/decision-cases/{case['case_id']}/analysis-runs", json={}).json()
    plan = client.post(f"/v1/analysis-runs/{run['run_id']}/action-plans").json()
    assert plan["plan_hash"] and plan["nonce"], plan
    return plan


def _code_of(resp: Any) -> str:
    body = resp.json()
    return (body.get("error") or {}).get("code", "")


# ── the named gates ─────────────────────────────────────────────────────────────────────────────


def test_executing_before_approval_names_the_gate() -> None:
    """Conformance scenario 2: denied by policy, with a name the caller can branch on."""
    with SyncASGIClient(_app()) as client:
        plan = _proposed_plan(client)
        r = client.post(f"/v1/decision-plans/{plan['plan_id']}/execute")
    assert r.status_code == 409
    assert _code_of(r) == "plan_not_approved", (
        f"expected the named gate, got {_code_of(r)!r} -- a caller cannot distinguish this from "
        "any other 409"
    )


def test_a_wrong_plan_hash_names_the_gate() -> None:
    """Conformance scenario 8: modified plan_hash rejected, by name."""
    with SyncASGIClient(_app()) as client:
        plan = _proposed_plan(client)
        r = client.post(
            f"/v1/decision-plans/{plan['plan_id']}/approve",
            json={"plan_hash": "0" * 64, "nonce": plan["nonce"]},
        )
    assert r.status_code == 403
    assert _code_of(r) == "plan_hash_mismatch"


def test_a_bad_nonce_names_the_gate() -> None:
    """Conformance scenario 7: the single-use challenge, refused by name."""
    with SyncASGIClient(_app()) as client:
        plan = _proposed_plan(client)
        r = client.post(
            f"/v1/decision-plans/{plan['plan_id']}/approve",
            json={"plan_hash": plan["plan_hash"], "nonce": "b" * 16},
        )
    assert r.status_code == 403
    assert _code_of(r) == "invalid_nonce"


def test_the_code_is_never_the_generic_placeholder_for_a_named_failure() -> None:
    """The regression itself: a named failure must not arrive as `http_error`."""
    with SyncASGIClient(_app()) as client:
        plan = _proposed_plan(client)
        r = client.post(f"/v1/decision-plans/{plan['plan_id']}/execute")
    assert _code_of(r) != "http_error", (
        "the named gate collapsed back to the generic code; callers are forced to string-match prose"
    )


def test_the_message_is_prose_not_a_python_dict_repr() -> None:
    """The old body embedded `{'code': ...}` inside the message. That must not come back."""
    with SyncASGIClient(_app()) as client:
        plan = _proposed_plan(client)
        r = client.post(f"/v1/decision-plans/{plan['plan_id']}/execute")
    message = (r.json().get("error") or {}).get("message", "")
    assert "'code':" not in message and not message.startswith("{"), (
        f"the message is a serialised dict, not a human sentence: {message!r}"
    )
    assert message, "a named failure must still carry a human-readable message"


def test_the_docs_url_points_at_the_specific_code() -> None:
    """A generic docs link for a specific failure sends the reader to the wrong page."""
    with SyncASGIClient(_app()) as client:
        plan = _proposed_plan(client)
        r = client.post(f"/v1/decision-plans/{plan['plan_id']}/execute")
    assert (r.json()["error"]["docs_url"]).endswith("/plan_not_approved")


def test_the_request_id_survives_the_named_branch() -> None:
    """Correlation must not be lost on the error path -- that is when it is needed most."""
    with SyncASGIClient(_app()) as client:
        plan = _proposed_plan(client)
        r = client.post(f"/v1/decision-plans/{plan['plan_id']}/execute")
    assert "request_id" in r.json()["error"]


# ── the shapes that must NOT change ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_an_already_enveloped_detail_is_still_passed_through(client) -> None:
    """Routers that already raise detail={"error": {...}} keep their exact body."""

    @real_app.get("/__test_enveloped_error")
    async def _probe() -> dict:  # pragma: no cover - registered for this test
        raise HTTPException(status_code=418, detail={"error": {"code": "teapot", "message": "no"}})

    try:
        r = await client.get("/__test_enveloped_error")
        assert r.status_code == 418
        assert r.json()["error"]["code"] == "teapot"
    finally:
        real_app.router.routes = [
            x for x in real_app.router.routes
            if getattr(x, "path", None) != "/__test_enveloped_error"
        ]


@pytest.mark.anyio
async def test_a_plain_string_detail_still_uses_the_generic_code(client) -> None:
    """The fallback is correct for an unnamed failure; only NAMED ones were being flattened."""

    @real_app.get("/__test_plain_error")
    async def _probe() -> dict:  # pragma: no cover - registered for this test
        raise HTTPException(status_code=400, detail="something went wrong")

    try:
        r = await client.get("/__test_plain_error")
        assert r.json()["error"]["code"] == "http_error"
        assert r.json()["error"]["message"] == "something went wrong"
    finally:
        real_app.router.routes = [
            x for x in real_app.router.routes
            if getattr(x, "path", None) != "/__test_plain_error"
        ]
