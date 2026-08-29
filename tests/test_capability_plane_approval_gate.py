"""DB-backed tests for the capability_plane approval gate (Track C1b).

Exercises execute_capability_service's propose/approve/execute workflow for a capability
whose catalog entry has approval_required=True -- mirroring DecisionService's own
propose/approve/execute pattern (services/decision_service/service.py + its test file,
tests/test_decision_service.py) -- plus the zero-behavior-change guarantee for the (by far
most common) approval_required=False default path.

Uses the real Postgres test database (see tests/conftest.py) rather than an in-memory
repository: unlike DecisionService, capability_plane services operate directly on an
AsyncSession/ORM models, so there is no swappable in-memory repository to unit test against.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models import Organization, OrgPlan, OrgStatus


async def _seed_org() -> str:
    async with AsyncSessionLocal() as session:
        org = Organization(
            name="Capability Approval Gate Test Org",
            slug=f"capability-approval-gate-{uuid4().hex[:12]}",
            plan=OrgPlan.PRO,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.commit()
        return str(org.id)


def _fake_auth(org_id: str, *, role: str = "admin"):
    async def _auth() -> dict[str, str]:
        return {
            "org_id": org_id,
            "user_id": f"user-{uuid4().hex[:8]}",
            "key_id": f"key-{uuid4().hex[:8]}",
            "plan": "pro",
            "role": role,
        }

    return _auth


def _skill_manifest(
    capability_id: str, *, approval_required: bool, instruction: str = "Do the gated thing."
) -> dict:
    return {
        "provider_id": "provider.skill_pack.algenta",
        "profile_id": "profile.skill_pack.user",
        "binding_name": f"Gate Skill {capability_id}",
        "scope": "user",
        "execution_owner": "algenta_managed",
        "config": {
            "manifest": {
                "capabilities": [
                    {
                        "capability_id": capability_id,
                        "name": "Gate Skill",
                        "description": "A skill capability used to test the approval gate.",
                        "kind": "skill",
                        "implementation_kind": "instruction_only",
                        "execution_owner": "algenta_managed",
                        "instruction": instruction,
                        "tags": ["gate-test"],
                        "approval_required": approval_required,
                    }
                ]
            }
        },
    }


async def _create_and_discover(
    client, capability_id: str, *, approval_required: bool
) -> str:
    create_response = await client.post(
        "/v1/capability-bindings",
        json=_skill_manifest(capability_id, approval_required=approval_required),
    )
    assert create_response.status_code == 201, create_response.text
    binding_id = create_response.json()["binding_id"]
    discover_response = await client.post(f"/v1/capability-bindings/{binding_id}/discover")
    assert discover_response.status_code == 200, discover_response.text
    assert discover_response.json()["capability_count"] == 1
    return binding_id


async def _propose(client, capability_id: str) -> dict:
    resp = await client.post("/v1/capabilities/execute", json={"capability_id": capability_id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "started"
    assert body["output"] is None and body["error"] is None
    assert body["plan_id"] and body["plan_hash"] and body["nonce"]
    assert body["receipt"]["status"] == "approval_required"
    return body


async def _set_plan_created_at(plan_id: str, created_at: datetime) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "UPDATE capability_execution_plans SET created_at = :created_at WHERE id = :id"
            ),
            {"created_at": created_at, "id": plan_id},
        )
        await session.commit()


@pytest.mark.anyio
async def test_approval_required_false_executes_directly_with_no_gate_fields(client) -> None:
    """Zero-behavior-change regression: the (overwhelmingly common) default path must be
    completely unaffected by the gate -- immediate execution, no plan_id/nonce/receipt."""
    org_id = await _seed_org()
    cap_id = f"cap.skill.no-gate.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=False)
        resp = await client.post("/v1/capabilities/execute", json={"capability_id": cap_id})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "succeeded"
        assert body["output"]["instruction_text"] == "Do the gated thing."
        assert body["plan_id"] is None
        assert body["nonce"] is None
        assert body["plan_hash"] is None
        assert body["receipt"] is None
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_approval_required_true_blocks_until_approved_then_executes(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.gated.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
        plan_id = proposed["plan_id"]

        # executing before approval is refused (approve != execute)
        premature = await client.post(
            "/v1/capabilities/execute", json={"capability_id": cap_id, "plan_id": plan_id}
        )
        assert premature.status_code == 409
        assert premature.json()["error"]["code"] == "plan_not_approved"

        approve = await client.post(
            f"/v1/capability-executions/{plan_id}/approve",
            json={"plan_hash": proposed["plan_hash"], "nonce": proposed["nonce"]},
        )
        assert approve.status_code == 200, approve.text
        approval = approve.json()
        assert approval["lifecycle_state"] == "approved"
        assert approval["plan_id"] == plan_id

        execute = await client.post(
            "/v1/capabilities/execute", json={"capability_id": cap_id, "plan_id": plan_id}
        )
        assert execute.status_code == 200, execute.text
        executed = execute.json()
        assert executed["status"] == "succeeded"
        assert executed["output"]["instruction_text"] == "Do the gated thing."
        assert executed["plan_id"] == plan_id
        assert executed["receipt"]["status"] == "executed"
        assert executed["nonce"] is None  # never re-exposed after propose

        # the plan is now terminal: a second execute call is refused
        replay = await client.post(
            "/v1/capabilities/execute", json={"capability_id": cap_id, "plan_id": plan_id}
        )
        assert replay.status_code == 409
        assert replay.json()["error"]["code"] == "plan_not_approved"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_plan_id_rejected_for_a_capability_that_does_not_require_approval(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.ungated.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=False)
        resp = await client.post(
            "/v1/capabilities/execute",
            json={"capability_id": cap_id, "plan_id": str(uuid4())},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "plan_id_not_applicable"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_approve_requires_matching_plan_hash_and_nonce(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.badfingerprint.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
        plan_id = proposed["plan_id"]

        bad_hash = await client.post(
            f"/v1/capability-executions/{plan_id}/approve",
            json={"plan_hash": "0" * 64, "nonce": proposed["nonce"]},
        )
        assert bad_hash.status_code == 403
        assert bad_hash.json()["error"]["code"] == "plan_hash_mismatch"

        bad_nonce = await client.post(
            f"/v1/capability-executions/{plan_id}/approve",
            json={"plan_hash": proposed["plan_hash"], "nonce": "wrongnonce"},
        )
        assert bad_nonce.status_code == 403
        assert bad_nonce.json()["error"]["code"] == "invalid_nonce"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_approval_nonce_is_single_use(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.singleuse.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
        plan_id = proposed["plan_id"]
        approve_payload = {"plan_hash": proposed["plan_hash"], "nonce": proposed["nonce"]}

        first = await client.post(
            f"/v1/capability-executions/{plan_id}/approve", json=approve_payload
        )
        assert first.status_code == 200, first.text

        second = await client.post(
            f"/v1/capability-executions/{plan_id}/approve", json=approve_payload
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "plan_not_approvable"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_approval_nonce_ttl_expires(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.expired.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
        plan_id = proposed["plan_id"]

        # Backdate the plan's created_at past the 24h nonce TTL -- a leaked propose response
        # must not be approvable after that window.
        await _set_plan_created_at(plan_id, datetime(2000, 1, 1, tzinfo=UTC))

        expired = await client.post(
            f"/v1/capability-executions/{plan_id}/approve",
            json={"plan_hash": proposed["plan_hash"], "nonce": proposed["nonce"]},
        )
        assert expired.status_code == 403
        assert expired.json()["error"]["code"] == "approval_expired"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_idempotent_approval_replay_returns_same_result(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.idempotent.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
        plan_id = proposed["plan_id"]
        payload = {
            "plan_hash": proposed["plan_hash"],
            "nonce": proposed["nonce"],
            "idempotency_key": "gate-key-1",
        }

        first = await client.post(f"/v1/capability-executions/{plan_id}/approve", json=payload)
        assert first.status_code == 200, first.text
        second = await client.post(f"/v1/capability-executions/{plan_id}/approve", json=payload)
        assert second.status_code == 200, second.text
        assert first.json() == second.json()
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_idempotency_key_reuse_for_a_different_plan_is_rejected(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.idempotentconflict.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        p1 = await _propose(client, cap_id)
        r1 = await client.post(
            f"/v1/capability-executions/{p1['plan_id']}/approve",
            json={
                "plan_hash": p1["plan_hash"],
                "nonce": p1["nonce"],
                "idempotency_key": "shared-key",
            },
        )
        assert r1.status_code == 200, r1.text

        p2 = await _propose(client, cap_id)
        r2 = await client.post(
            f"/v1/capability-executions/{p2['plan_id']}/approve",
            json={
                "plan_hash": p2["plan_hash"],
                "nonce": p2["nonce"],
                "idempotency_key": "shared-key",
            },
        )
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "idempotency_key_conflict"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_stale_plan_rejected_after_capability_redefinition(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.stale.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        binding_id = await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
        plan_id = proposed["plan_id"]

        # The capability's discovered definition changes (a re-discovery) between propose and
        # approve -- the manifest_hash snapshot no longer matches.
        update = await client.patch(
            f"/v1/capability-bindings/{binding_id}",
            json={
                "config": _skill_manifest(
                    cap_id,
                    approval_required=True,
                    instruction="A materially different instruction.",
                )["config"]
            },
        )
        assert update.status_code == 200, update.text
        redis = await client.post(f"/v1/capability-bindings/{binding_id}/discover")
        assert redis.status_code == 200, redis.text

        stale = await client.post(
            f"/v1/capability-executions/{plan_id}/approve",
            json={"plan_hash": proposed["plan_hash"], "nonce": proposed["nonce"]},
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "stale_capability_plan"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_approval_requires_admin_role(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.rolegate.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id, role="admin")
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
    finally:
        app.dependency_overrides.pop(get_current_org, None)

    app.dependency_overrides[get_current_org] = _fake_auth(org_id, role="viewer")
    try:
        denied = await client.post(
            f"/v1/capability-executions/{proposed['plan_id']}/approve",
            json={"plan_hash": proposed["plan_hash"], "nonce": proposed["nonce"]},
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "insufficient_role"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_concurrent_double_approve_single_winner(client) -> None:
    # Two concurrent approve calls for the SAME plan, but with distinct bodies/headers so the
    # generic write-conflict middleware (apps/api_server/middleware/idempotency.py, keyed by a
    # hash of the request body) does not itself short-circuit the second request -- this test
    # is about capability_plane's OWN compare-and-set, not that unrelated outer layer.
    org_id = await _seed_org()
    cap_id = f"cap.skill.concurrentapprove.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
        plan_id = proposed["plan_id"]

        responses = await asyncio.gather(
            client.post(
                f"/v1/capability-executions/{plan_id}/approve",
                json={
                    "plan_hash": proposed["plan_hash"],
                    "nonce": proposed["nonce"],
                    "idempotency_key": "race-a",
                },
            ),
            client.post(
                f"/v1/capability-executions/{plan_id}/approve",
                json={
                    "plan_hash": proposed["plan_hash"],
                    "nonce": proposed["nonce"],
                    "idempotency_key": "race-b",
                },
            ),
        )
        statuses = sorted(r.status_code for r in responses)
        assert statuses == [200, 409]
        loser = next(r for r in responses if r.status_code == 409)
        assert loser.json()["error"]["code"] == "plan_not_approvable"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_concurrent_double_execute_single_winner(client) -> None:
    org_id = await _seed_org()
    cap_id = f"cap.skill.concurrentexecute.{uuid4().hex[:8]}"
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    try:
        await _create_and_discover(client, cap_id, approval_required=True)
        proposed = await _propose(client, cap_id)
        plan_id = proposed["plan_id"]
        approve = await client.post(
            f"/v1/capability-executions/{plan_id}/approve",
            json={"plan_hash": proposed["plan_hash"], "nonce": proposed["nonce"]},
        )
        assert approve.status_code == 200, approve.text

        # Same body on both calls, so distinguish them to the outer write-conflict middleware
        # via distinct Idempotency-Key headers -- both must reach execute_capability_service
        # concurrently for this to actually exercise the plan's own compare-and-set transition.
        exec_payload = {"capability_id": cap_id, "plan_id": plan_id}
        responses = await asyncio.gather(
            client.post(
                "/v1/capabilities/execute",
                json=exec_payload,
                headers={"Idempotency-Key": "exec-race-a"},
            ),
            client.post(
                "/v1/capabilities/execute",
                json=exec_payload,
                headers={"Idempotency-Key": "exec-race-b"},
            ),
        )
        statuses = sorted(r.status_code for r in responses)
        assert statuses == [200, 409]
        winner = next(r for r in responses if r.status_code == 200)
        assert winner.json()["status"] == "succeeded"
        loser = next(r for r in responses if r.status_code == 409)
        assert loser.json()["error"]["code"] == "plan_not_approved"
    finally:
        app.dependency_overrides.pop(get_current_org, None)
