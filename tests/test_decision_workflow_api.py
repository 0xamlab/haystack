"""DB-free HTTP tests for the Decision Workflow API (/v1/decision-cases…).

Builds a minimal FastAPI app with ONLY the decision_cases router and overrides the auth/DB/
service dependencies (in-memory repository, stub session) — so the full HTTP contract
(status codes, 202+poll, plan_hash/nonce approval, approve != execute) is exercised without
Postgres. The SQL repository itself is exercised by CI's DB-backed suite via the app wiring.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI

from apps.api_server.middleware.auth import get_current_org, require_verified_email
from apps.api_server.routers import decision_cases
from apps.api_server.services.decision_service import (
    DecisionService,
    InMemoryDecisionRepository,
)
from tests._asgi_client import SyncASGIClient

_ORG_A = uuid.uuid4()
_ORG_B = uuid.uuid4()


def _auth_ctx(org_id: uuid.UUID, role: str = "admin") -> dict[str, Any]:
    return {
        "org_id": org_id,
        "user_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
        "plan": "pro",
        "is_platform": False,
        "workspace_id": None,
        "role": role,
    }


class _StubSession:
    async def commit(self) -> None:  # the in-memory repo persists immediately
        return None


def _app(
    org_id: uuid.UUID = _ORG_A,
    shared_service: DecisionService | None = None,
    role: str = "admin",
) -> FastAPI:
    app = FastAPI()
    app.include_router(decision_cases.router)
    service = shared_service or DecisionService(InMemoryDecisionRepository())
    ctx = _auth_ctx(org_id, role=role)
    app.dependency_overrides[get_current_org] = lambda: ctx
    app.dependency_overrides[require_verified_email] = lambda: ctx
    app.dependency_overrides[decision_cases.get_db] = lambda: _StubSession()
    app.dependency_overrides[decision_cases.get_decision_service] = lambda: service
    return app


def _renewal_input(*, total_hours: float = 40, strategic_min: float = 4) -> dict[str, Any]:
    return {
        "accounts": [
            {"account_id": "A1", "name": "BigCo", "arr": 500000, "renewal_date": "2026-08-01", "health_score": 40, "segment": "standard"},
            {"account_id": "A3", "name": "SmallStrategic", "arr": 60000, "renewal_date": "2026-08-01", "health_score": 35, "segment": "strategic"},
            {"account_id": "A5", "name": "KeyStrategic", "arr": 90000, "renewal_date": "2026-08-01", "health_score": 50, "segment": "strategic"},
        ],
        "capacity": {"total_hours": total_hours},
        "constraints": {"strategic_min_hours": strategic_min, "allocation_step_hours": 1},
        "horizon_days": 90,
    }


def _create_body(**kw: Any) -> dict[str, Any]:
    return {
        "pack_id": "renewal_capacity_allocation",
        "title": "Q3 renewals",
        "pack_input": _renewal_input(**kw),
    }


def test_full_http_workflow() -> None:
    with SyncASGIClient(_app()) as client:
        # frame
        r = client.post("/v1/decision-cases", json=_create_body())
        assert r.status_code == 201, r.text
        case = r.json()
        assert case["current_revision_number"] == 1 and case["inputs_hash"]

        # analyze (202 + poll)
        r = client.post(f"/v1/decision-cases/{case['case_id']}/analysis-runs", json={})
        assert r.status_code == 202, r.text
        accepted = r.json()
        assert accepted["poll_url"].endswith(f"/v1/analysis-runs/{accepted['run_id']}")

        r = client.get(f"/v1/analysis-runs/{accepted['run_id']}")
        assert r.status_code == 200 and r.json()["status"] == "completed"
        assert r.json()["reproducibility_id"]

        # result + evidence
        r = client.get(f"/v1/analysis-runs/{accepted['run_id']}/result")
        assert r.status_code == 200
        result = r.json()
        assert result["status"] == "completed" and result["result"]["feasible"] is True

        r = client.get(f"/v1/analysis-runs/{accepted['run_id']}/evidence")
        assert r.status_code == 200 and r.json()["provenance"]

        # propose plan (returns plan_hash + single-use nonce)
        r = client.post(f"/v1/analysis-runs/{accepted['run_id']}/action-plans")
        assert r.status_code == 201, r.text
        plan = r.json()
        assert plan["lifecycle_state"] == "proposed" and plan["plan_hash"] and plan["nonce"]

        # execute before approve -> 409 (approve != execute)
        r = client.post(f"/v1/decision-plans/{plan['plan_id']}/execute")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "plan_not_approved"

        # approve with wrong hash -> 403
        r = client.post(
            f"/v1/decision-plans/{plan['plan_id']}/approve",
            json={"plan_hash": "0" * 64, "nonce": plan["nonce"]},
        )
        assert r.status_code == 403 and r.json()["detail"]["code"] == "plan_hash_mismatch"

        # approve correctly
        r = client.post(
            f"/v1/decision-plans/{plan['plan_id']}/approve",
            json={"plan_hash": plan["plan_hash"], "nonce": plan["nonce"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"

        # nonce is single-use: approving again -> 409 (already approved)
        r = client.post(
            f"/v1/decision-plans/{plan['plan_id']}/approve",
            json={"plan_hash": plan["plan_hash"], "nonce": plan["nonce"]},
        )
        assert r.status_code == 409 and r.json()["detail"]["code"] == "plan_not_approvable"

        # execute (nonce never re-exposed)
        r = client.post(f"/v1/decision-plans/{plan['plan_id']}/execute")
        assert r.status_code == 200, r.text
        executed = r.json()
        assert executed["lifecycle_state"] == "executed"
        assert executed["nonce"] is None and executed["receipt"]

        # outcome
        r = client.post(
            f"/v1/decision-cases/{case['case_id']}/outcomes",
            json={"run_id": accepted["run_id"], "actual_metrics": {"retained_arr": 400000}},
        )
        assert r.status_code == 201 and r.json()["delta"] is not None

        # refresh (202) reproduces
        r = client.post(f"/v1/decision-cases/{case['case_id']}/refresh", json={})
        assert r.status_code == 202


def test_reframe_creates_new_revision_and_invalidates_plan() -> None:
    with SyncASGIClient(_app()) as client:
        case = client.post("/v1/decision-cases", json=_create_body()).json()
        run = client.post(f"/v1/decision-cases/{case['case_id']}/analysis-runs", json={}).json()
        plan = client.post(f"/v1/analysis-runs/{run['run_id']}/action-plans").json()

        # material re-frame
        r = client.request(
            "PUT", f"/v1/decision-cases/{case['case_id']}", json=_create_body(total_hours=80)
        )
        assert r.status_code == 200 and r.json()["current_revision_number"] == 2

        # the stale plan can no longer be approved
        r = client.post(
            f"/v1/decision-plans/{plan['plan_id']}/approve",
            json={"plan_hash": plan["plan_hash"], "nonce": plan["nonce"]},
        )
        assert r.status_code == 409
        assert r.json()["detail"]["code"] in ("stale_plan", "plan_not_approvable")


def test_infeasible_framing_blocks_plan_with_409() -> None:
    with SyncASGIClient(_app()) as client:
        case = client.post("/v1/decision-cases", json=_create_body(strategic_min=20)).json()
        run = client.post(f"/v1/decision-cases/{case['case_id']}/analysis-runs", json={}).json()
        r = client.get(f"/v1/analysis-runs/{run['run_id']}/result")
        assert r.json()["result"]["feasible"] is False
        r = client.post(f"/v1/analysis-runs/{run['run_id']}/action-plans")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "no_feasible_solution"


def test_invalid_framing_is_422_and_unknown_pack_400() -> None:
    with SyncASGIClient(_app()) as client:
        bad = {"pack_id": "renewal_capacity_allocation", "title": "bad", "pack_input": {"accounts": [], "capacity": {"total_hours": 1}}}
        r = client.post("/v1/decision-cases", json=bad)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_framing"
        r = client.post("/v1/decision-cases", json={"pack_id": "nope", "title": "x", "pack_input": {}})
        assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_pack"


def test_viewer_role_cannot_approve_or_execute() -> None:
    # #320 review (HIGH): a viewer/service-role credential must not be able to self-approve.
    shared = DecisionService(InMemoryDecisionRepository())
    with SyncASGIClient(_app(_ORG_A, shared)) as admin:
        case = admin.post("/v1/decision-cases", json=_create_body()).json()
        run = admin.post(f"/v1/decision-cases/{case['case_id']}/analysis-runs", json={}).json()
        plan = admin.post(f"/v1/analysis-runs/{run['run_id']}/action-plans").json()
    with SyncASGIClient(_app(_ORG_A, shared, role="viewer")) as viewer:
        r = viewer.post(
            f"/v1/decision-plans/{plan['plan_id']}/approve",
            json={"plan_hash": plan["plan_hash"], "nonce": plan["nonce"]},
        )
        assert r.status_code == 403 and r.json()["detail"]["code"] == "insufficient_role"
    with SyncASGIClient(_app(_ORG_A, shared)) as admin:
        r = admin.post(
            f"/v1/decision-plans/{plan['plan_id']}/approve",
            json={"plan_hash": plan["plan_hash"], "nonce": plan["nonce"]},
        )
        assert r.status_code == 200
    with SyncASGIClient(_app(_ORG_A, shared, role="viewer")) as viewer:
        r = viewer.post(f"/v1/decision-plans/{plan['plan_id']}/execute")
        assert r.status_code == 403 and r.json()["detail"]["code"] == "insufficient_role"


def test_cross_org_isolation_over_http() -> None:
    shared = DecisionService(InMemoryDecisionRepository())
    with SyncASGIClient(_app(_ORG_A, shared)) as client_a:
        case = client_a.post("/v1/decision-cases", json=_create_body()).json()
        run = client_a.post(f"/v1/decision-cases/{case['case_id']}/analysis-runs", json={}).json()
    with SyncASGIClient(_app(_ORG_B, shared)) as client_b:
        assert client_b.get(f"/v1/decision-cases/{case['case_id']}").status_code == 404
        assert client_b.get(f"/v1/analysis-runs/{run['run_id']}").status_code == 404
        r = client_b.post(f"/v1/decision-cases/{case['case_id']}/analysis-runs", json={})
        assert r.status_code == 404
