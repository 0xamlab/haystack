"""Real, end-to-end tests for Track C1: human-approval pause/resume on /v1/responses.

Exercises the NEW execute_capability_tools=True interception in apps/api_server/routers/llm.py
against the REAL, already-tested capability_plane approval gate (Track C1b,
apps/api_server/services/capability_plane/_execution.py) -- no new approval/plan/nonce
mechanism is invented here. The "model" step is faked (there is no real LLM configured in this
test environment) by monkeypatching create_utility_conversation_response to return a tool call,
exactly like the existing tests in tests/test_llm_api_router_responses_route.py do -- but the
capability execution/approval-gate step is 100% real: it hits the real Postgres test database via
the exact same execute_capability_service / approve_capability_execution_service functions the
HTTP routes call, using the same DB-backed fixture pattern as
tests/test_capability_plane_approval_gate.py and tests/test_capability_plane_api.py.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.models import Organization, OrgPlan, OrgStatus
from apps.api_server.models.capability_plane import (
    CapabilityExecutionPlan,
    CapabilityPlanLifecycleState,
)
from apps.api_server.routers import llm as llm_router
from apps.api_server.services.capability_plane import (
    CapabilityApprovalRequest,
    approve_capability_execution_service,
)
from apps.api_server.services.llm_api_service._creation import _store_response_history
from tests._test_llm_api_router_helpers import _provider_chat_model_descriptor


async def _noop_rate_limit(*, request: object, auth: object, redis_client: object) -> None:
    del request, auth, redis_client


async def _seed_org() -> str:
    async with AsyncSessionLocal() as session:
        org = Organization(
            name="LLM Capability Approval Test Org",
            slug=f"llm-capability-approval-{uuid4().hex[:12]}",
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


def _skill_manifest(capability_id: str, *, name: str, approval_required: bool) -> dict:
    """Same manifest shape as tests/test_capability_plane_approval_gate.py's _skill_manifest,
    parameterized on `name` so it can be made to match a model tool_call's function name."""
    return {
        "provider_id": "provider.skill_pack.algenta",
        "profile_id": "profile.skill_pack.user",
        "binding_name": f"LLM Gate Skill {capability_id}",
        "scope": "user",
        "execution_owner": "algenta_managed",
        "config": {
            "manifest": {
                "capabilities": [
                    {
                        "capability_id": capability_id,
                        "name": name,
                        "description": "A skill capability used to test /v1/responses' capability-tool gate.",
                        "kind": "skill",
                        "implementation_kind": "instruction_only",
                        "execution_owner": "algenta_managed",
                        "instruction": "Do the real gated thing.",
                        "tags": ["llm-gate-test"],
                        "approval_required": approval_required,
                    }
                ]
            }
        },
    }


async def _create_and_discover(
    client, capability_id: str, *, name: str, approval_required: bool
) -> str:
    create_response = await client.post(
        "/v1/capability-bindings",
        json=_skill_manifest(capability_id, name=name, approval_required=approval_required),
    )
    assert create_response.status_code == 201, create_response.text
    binding_id = create_response.json()["binding_id"]
    discover_response = await client.post(f"/v1/capability-bindings/{binding_id}/discover")
    assert discover_response.status_code == 200, discover_response.text
    assert discover_response.json()["capability_count"] == 1
    return binding_id


def _fake_tool_call_conversation(*, response_id: str, tool_name: str, tool_call_id: str = "call_1"):
    """Monkeypatch target for create_utility_conversation_response: simulates a model turn that
    calls exactly one tool (matching a real capability's name). Everything downstream of this
    (the capability_plane execute/approve/execute cycle) is real.

    Also stores conversation history under `response_id` via the REAL (private)
    _store_response_history -- the real create_utility_conversation_response always does this,
    and the Track C1 resume path's finalize_capability_approval_conversation depends on being
    able to load it back via previous_response_id, exactly like an ordinary
    function_call_output continuation would."""

    async def _fake(*, model_id: str, items: list[dict], previous_response_id: str | None, **_kw):
        del model_id, previous_response_id
        user_content = next(
            (item.get("content") for item in items if item.get("type") == "message"), ""
        )
        _store_response_history(
            response_id,
            [
                {"role": "user", "content": user_content},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {"name": tool_name, "arguments": "{}"},
                        }
                    ],
                },
            ],
        )
        return (
            _provider_chat_model_descriptor(),
            response_id,
            [
                SimpleNamespace(
                    index=0,
                    item_type="text",
                    text=None,
                    tokens=None,
                    token_count=0,
                    embedding=None,
                    provider=None,
                    provider_attempts=(),
                    tool_calls=(
                        SimpleNamespace(
                            id=tool_call_id,
                            function=SimpleNamespace(name=tool_name, arguments="{}"),
                        ),
                    ),
                    finish_reason="tool_calls",
                )
            ],
            10,
        )

    return _fake


async def _load_plan_fields(plan_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        plan = await session.get(CapabilityExecutionPlan, uuid.UUID(plan_id))
        assert plan is not None, f"no CapabilityExecutionPlan row exists for plan_id={plan_id!r}"
        return {
            "lifecycle_state": plan.lifecycle_state,
            "capability_id": plan.capability_id,
            "plan_hash": plan.plan_hash,
            "nonce": plan.nonce,
        }


@pytest.mark.anyio
async def test_execute_capability_tools_defaults_false_and_is_fully_additive(client, monkeypatch) -> None:
    """Regression-safety property (most important one): a caller who never sets
    execute_capability_tools gets the exact same inert tool_call item as before -- even when its
    name happens to match a real capability in the org's own catalog."""
    org_id = await _seed_org()
    cap_id = f"cap.skill.llm-default-off.{uuid4().hex[:8]}"
    tool_name = f"tool_{uuid4().hex[:8]}"
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        await _create_and_discover(client, cap_id, name=tool_name, approval_required=False)
        monkeypatch.setattr(
            llm_router,
            "create_utility_conversation_response",
            _fake_tool_call_conversation(response_id="resp_default_off", tool_name=tool_name),
        )

        response = await client.post(
            "/v1/responses",
            json={
                "model": "provider.gpt-4o-mini",
                "input": [{"type": "message", "role": "user", "content": "do the thing"}],
                # execute_capability_tools intentionally omitted -- defaults to False.
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert body.get("approval_required") is None
        content = body["output"][0]["content"][0]
        assert content["tool_calls"] == [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": tool_name, "arguments": "{}"},
            }
        ]
        # The four new Track C1 fields are OMITTED entirely (not merely null) when unset -- the
        # exact same byte-identical-JSON-shape guarantee tests/test_llm_api_router_responses_route.py
        # verifies for the rest of this route.
        assert "capability_id" not in content
        assert "capability_status" not in content
        assert "capability_output" not in content
        assert "capability_error" not in content
        assert "approval_required" not in body
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_a_and_b_capability_tool_call_pauses_then_resumes_after_real_human_approval(
    client, monkeypatch
) -> None:
    """(a) execute_capability_tools=True + a tool call resolving to an approval_required
    capability returns response.approval_required with a REAL plan_id -- verified by directly
    querying the capability_plane execution-plan table for a lifecycle_state='proposed' row.
    (b) Approving that exact plan via the EXISTING, separate approve_capability_execution_service
    (simulating the human step) and resending with previous_response_id +
    capability_approval_continuation then actually executes, returning response.completed with
    real output -- verified by re-querying the DB for lifecycle_state='executed'."""
    org_id = await _seed_org()
    cap_id = f"cap.skill.llm-gate.{uuid4().hex[:8]}"
    tool_name = f"tool_{uuid4().hex[:8]}"
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth(org_id, role="admin")
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        await _create_and_discover(client, cap_id, name=tool_name, approval_required=True)
        monkeypatch.setattr(
            llm_router,
            "create_utility_conversation_response",
            _fake_tool_call_conversation(
                response_id="resp_gate_1", tool_name=tool_name, tool_call_id="call_gate_1"
            ),
        )

        # (a) -- propose.
        paused = await client.post(
            "/v1/responses",
            json={
                "model": "provider.gpt-4o-mini",
                "input": [{"type": "message", "role": "user", "content": "do the gated thing"}],
                "execute_capability_tools": True,
            },
        )
        assert paused.status_code == 200, paused.text
        paused_body = paused.json()
        assert paused_body["status"] == "approval_required"
        approval = paused_body["approval_required"]
        plan_id = approval["plan_id"]
        assert plan_id, "a real plan_id must be present"
        assert approval["plan_hash"]
        assert f"/v1/capability-executions/{plan_id}/approve" in approval["message"]
        content = paused_body["output"][0]["content"][0]
        assert content["capability_id"] == cap_id
        assert content["capability_status"] == "approval_required"
        # tool_calls is cleared once intercepted -- the call has been handled (paused), not left
        # inert for the caller to execute themselves.
        assert content["tool_calls"] is None

        plan_fields = await _load_plan_fields(plan_id)
        assert plan_fields["lifecycle_state"] == CapabilityPlanLifecycleState.PROPOSED.value
        assert plan_fields["capability_id"] == cap_id
        assert plan_fields["plan_hash"] == approval["plan_hash"]
        nonce = plan_fields["nonce"]
        assert nonce

        # A resume attempt before approval must NOT fake success.
        premature = await client.post(
            "/v1/responses",
            json={
                "model": "provider.gpt-4o-mini",
                "input": [
                    {"type": "capability_approval_continuation", "plan_id": plan_id}
                ],
                "previous_response_id": "resp_gate_1",
            },
        )
        assert premature.status_code == 200, premature.text
        premature_body = premature.json()
        assert premature_body["status"] == "approval_required"
        assert premature_body["approval_required"]["plan_id"] == plan_id

        # (b) -- the human approves, through the EXISTING, separate credentialed service call
        # (simulating a real human hitting POST /v1/capability-executions/{plan_id}/approve).
        async with AsyncSessionLocal() as approver_session:
            approval_response = await approve_capability_execution_service(
                approver_session,
                {
                    "org_id": org_id,
                    "user_id": "human-approver",
                    "key_id": "key-approver",
                    "plan": "pro",
                    "role": "admin",
                },
                plan_id,
                CapabilityApprovalRequest(plan_hash=approval["plan_hash"], nonce=nonce),
            )
            await approver_session.commit()
        assert approval_response.lifecycle_state == "approved"

        plan_fields_after_approve = await _load_plan_fields(plan_id)
        assert plan_fields_after_approve["lifecycle_state"] == CapabilityPlanLifecycleState.APPROVED.value

        # Resume: previous_response_id + capability_approval_continuation.
        resumed = await client.post(
            "/v1/responses",
            json={
                "model": "provider.gpt-4o-mini",
                "input": [
                    {"type": "capability_approval_continuation", "plan_id": plan_id}
                ],
                "previous_response_id": "resp_gate_1",
            },
        )
        assert resumed.status_code == 200, resumed.text
        resumed_body = resumed.json()
        assert resumed_body["status"] == "completed"
        assert resumed_body.get("approval_required") is None
        resumed_content = resumed_body["output"][0]["content"][0]
        assert resumed_content["capability_status"] == "succeeded"
        assert resumed_content["capability_output"]["instruction_text"] == "Do the real gated thing."
        assert resumed_content["capability_id"] == cap_id

        plan_fields_final = await _load_plan_fields(plan_id)
        assert plan_fields_final["lifecycle_state"] == CapabilityPlanLifecycleState.EXECUTED.value

        # Replaying the resume must NOT re-execute or fake a second success: the pause has
        # already been resolved (and the pending-approval bookkeeping cleared), so this is a
        # clear error, never a fake "completed" or a misleading "still approval_required".
        replay = await client.post(
            "/v1/responses",
            json={
                "model": "provider.gpt-4o-mini",
                "input": [
                    {"type": "capability_approval_continuation", "plan_id": plan_id}
                ],
                "previous_response_id": "resp_gate_1",
            },
        )
        assert replay.status_code == 422, replay.text
        assert replay.json()["error"]["code"] == "invalid_provider_request"

        plan_fields_unchanged = await _load_plan_fields(plan_id)
        assert plan_fields_unchanged["lifecycle_state"] == CapabilityPlanLifecycleState.EXECUTED.value
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_c_capability_without_approval_executes_in_one_round_trip(client, monkeypatch) -> None:
    """A capability with approval_required=False executes immediately on the FIRST call: real
    output, response.completed, no approval_required anywhere."""
    org_id = await _seed_org()
    cap_id = f"cap.skill.llm-nogate.{uuid4().hex[:8]}"
    tool_name = f"tool_{uuid4().hex[:8]}"
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        await _create_and_discover(client, cap_id, name=tool_name, approval_required=False)
        monkeypatch.setattr(
            llm_router,
            "create_utility_conversation_response",
            _fake_tool_call_conversation(response_id="resp_nogate_1", tool_name=tool_name),
        )

        response = await client.post(
            "/v1/responses",
            json={
                "model": "provider.gpt-4o-mini",
                "input": [{"type": "message", "role": "user", "content": "do the ungated thing"}],
                "execute_capability_tools": True,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert body.get("approval_required") is None
        content = body["output"][0]["content"][0]
        assert content["capability_id"] == cap_id
        assert content["capability_status"] == "succeeded"
        assert content["capability_output"]["instruction_text"] == "Do the real gated thing."
        assert content["tool_calls"] is None
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_tool_call_not_matching_any_capability_stays_inert(client, monkeypatch) -> None:
    """execute_capability_tools=True but the tool name does not resolve to any real capability
    in the org's catalog -- must keep returning the inert tool_call item exactly as before."""
    org_id = await _seed_org()
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        monkeypatch.setattr(
            llm_router,
            "create_utility_conversation_response",
            _fake_tool_call_conversation(
                response_id="resp_no_match", tool_name="not_a_real_capability_tool"
            ),
        )
        response = await client.post(
            "/v1/responses",
            json={
                "model": "provider.gpt-4o-mini",
                "input": [{"type": "message", "role": "user", "content": "do something"}],
                "execute_capability_tools": True,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        content = body["output"][0]["content"][0]
        assert "capability_id" not in content
        assert content["tool_calls"] == [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "not_a_real_capability_tool", "arguments": "{}"},
            }
        ]
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_f_streaming_capability_call_needing_approval_returns_existing_422_not_a_stream(
    client, monkeypatch
) -> None:
    """Streaming + a capability-backed tool call that resolves to approval_required must return
    the EXISTING typed 422 (model_capability_unsupported) -- never attempt to stream the pause."""
    org_id = await _seed_org()
    cap_id = f"cap.skill.llm-stream-gate.{uuid4().hex[:8]}"
    tool_name = f"tool_{uuid4().hex[:8]}"
    monkeypatch.setattr(llm_router, "_enforce_llm_api_rate_limit", _noop_rate_limit)
    app.dependency_overrides[get_current_org] = _fake_auth(org_id)
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        await _create_and_discover(client, cap_id, name=tool_name, approval_required=True)
        monkeypatch.setattr(
            llm_router,
            "create_utility_conversation_response",
            _fake_tool_call_conversation(response_id="resp_stream_gate", tool_name=tool_name),
        )

        response = await client.post(
            "/v1/responses",
            json={
                "model": "provider.gpt-4o-mini",
                "input": [{"type": "message", "role": "user", "content": "do the gated thing"}],
                "execute_capability_tools": True,
                "stream": True,
            },
        )
        assert response.status_code == 422, response.text
        assert "text/event-stream" not in response.headers.get("content-type", "")
        body = response.json()
        assert body["error"]["code"] == "model_capability_unsupported"
        assert body["error"]["details"]["required_capability"] == "streaming_tool_calls"
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_e_approve_capability_execution_service_is_never_referenced_by_the_new_llm_code() -> None:
    """Hard security invariant, proven MECHANICALLY (not just promised in prose): no code path
    added by Track C1 ever references approve_capability_execution_service by name -- the model
    can never approve its own pending plan. Approval only ever happens through the separate,
    credentialed POST /v1/capability-executions/{plan_id}/approve endpoint, outside any
    LLM-driven code path."""
    import inspect

    from apps.api_server.schemas import llm as llm_schemas
    from apps.api_server.services.llm_api_service import _creation

    scanned_sources = {
        "apps/api_server/routers/llm.py": inspect.getsource(llm_router),
        "apps/api_server/services/llm_api_service/_creation.py": inspect.getsource(_creation),
        "apps/api_server/schemas/llm.py": inspect.getsource(llm_schemas),
    }
    for path, source in scanned_sources.items():
        assert "approve_capability_execution_service" not in source, (
            f"{path} must never reference approve_capability_execution_service by name"
        )

    # Belt-and-suspenders: the router module's own namespace never binds that name either -- it
    # would have to, for any code path in it to be able to call it.
    assert not hasattr(llm_router, "approve_capability_execution_service")


@pytest.mark.anyio
async def test_responses_stream_approval_event_ends_cleanly() -> None:
    """Direct unit-level proof of the new forward-compatible SSE vocabulary (item 3 of the Track
    C1 spec): when _responses_stream is given an `approval`, it emits response.created +
    response.approval_required + [DONE] and nothing else -- no fake response.completed follows a
    pause, and the generator terminates cleanly (does not hang). Unreachable through the live
    router today (streaming + approval_required is refused with a 422 first, proven by
    test_f_streaming_capability_call_needing_approval_returns_existing_422_not_a_stream above),
    exactly like Track C1a's own tool_calls-streaming note documented on _responses_stream."""
    from apps.api_server.schemas.llm import EmbeddingUsageResponse, ResponseCapabilityApproval

    approval = ResponseCapabilityApproval(
        plan_id="11111111-1111-1111-1111-111111111111",
        plan_hash="a" * 32,
        message="Approve via POST /v1/capability-executions/.../approve.",
    )
    events = [
        event
        async for event in llm_router._responses_stream(
            response_id="resp_stream_approval",
            model_id="provider.gpt-4o-mini",
            items=[],
            usage=EmbeddingUsageResponse(prompt_tokens=0, total_tokens=0),
            provider_backend=None,
            provider_model_id=None,
            provider_attempts=[],
            approval=approval,
        )
    ]
    assert len(events) == 3
    assert '"type":"response.created"' in events[0]
    assert '"type":"response.approval_required"' in events[1]
    assert approval.plan_id in events[1]
    assert "data: [DONE]" in events[2]
    assert not any("response.completed" in event for event in events)
