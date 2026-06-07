from __future__ import annotations

import uuid
from uuid import uuid4

import pytest

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models import Organization, OrgPlan, OrgStatus
from apps.api_server.models.data_connector import (
    ConnectorType,
    ConnectorVisibility,
    DataConnector,
)


async def _seed_org() -> str:
    async with AsyncSessionLocal() as session:
        org = Organization(
            name="Capability Plane Test Org",
            slug=f"capability-plane-{uuid4().hex[:12]}",
            plan=OrgPlan.PRO,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.commit()
        return str(org.id)


@pytest.mark.anyio
async def test_capability_plane_lists_seeded_providers_and_discovers_skill_binding(client) -> None:
    org_id = await _seed_org()

    async def _fake_auth() -> dict[str, str]:
        return {
            "org_id": org_id,
            "user_id": f"user-{uuid4().hex[:8]}",
            "key_id": f"key-{uuid4().hex[:8]}",
            "plan": "pro",
        }

    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        providers_response = await client.get("/v1/capability-providers")
        assert providers_response.status_code == 200
        provider_ids = {item["provider_id"] for item in providers_response.json()}
        assert "provider.data_connector.algenta" in provider_ids
        assert "provider.skill_pack.algenta" in provider_ids

        create_response = await client.post(
            "/v1/capability-bindings",
            json={
                "provider_id": "provider.skill_pack.algenta",
                "profile_id": "profile.skill_pack.user",
                "binding_name": "Escalation Skill",
                "scope": "user",
                "execution_owner": "algenta_managed",
                "config": {
                    "manifest": {
                        "capabilities": [
                            {
                                "capability_id": "cap.skill.escalation",
                                "name": "Escalation Skill",
                                "description": "Escalates production incidents.",
                                "kind": "skill",
                                "implementation_kind": "instruction_only",
                                "execution_owner": "algenta_managed",
                                "instruction": "Escalate to the on-call incident commander.",
                                "tags": ["incident", "escalation"],
                                "artifact_affinities": ["incident"],
                            }
                        ]
                    }
                },
            },
        )
        assert create_response.status_code == 201
        binding = create_response.json()

        discover_response = await client.post(
            f"/v1/capability-bindings/{binding['binding_id']}/discover"
        )
        assert discover_response.status_code == 200
        discovered = discover_response.json()
        assert discovered["capability_count"] == 1
        assert discovered["capabilities"][0]["kind"] == "skill"

        list_response = await client.get("/v1/capabilities", params=[("kinds", "skill")])
        assert list_response.status_code == 200
        capabilities = list_response.json()
        assert capabilities[0]["capability_id"] == "cap.skill.escalation"

        route_response = await client.post(
            "/v1/capabilities/route",
            json={
                "objective": "Escalate the production incident quickly",
                "kinds": ["skill"],
                "artifact_affinities": ["incident"],
            },
        )
        assert route_response.status_code == 200
        route_plan = route_response.json()
        assert route_plan["selected_capability_id"] == "cap.skill.escalation"
        assert route_plan["selected_provider_id"] == "provider.skill_pack.algenta"

        execute_response = await client.post(
            "/v1/capabilities/execute",
            json={"capability_id": "cap.skill.escalation"},
        )
        assert execute_response.status_code == 200
        execution = execute_response.json()
        assert execution["status"] == "succeeded"
        assert execution["output"]["instruction_text"] == "Escalate to the on-call incident commander."

        outcome_response = await client.post(
            "/v1/capabilities/outcomes",
            json={
                "capability_id": "cap.skill.escalation",
                "provider_id": "provider.skill_pack.algenta",
                "binding_id": binding["binding_id"],
                "success": True,
                "result_status": "completed",
                "confidence": 0.91,
            },
        )
        assert outcome_response.status_code == 201
        outcome = outcome_response.json()
        assert outcome["capability_id"] == "cap.skill.escalation"
        assert outcome["success"] is True
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_capability_plane_authorization_flow_completes_for_manifest_binding(client) -> None:
    org_id = await _seed_org()

    async def _fake_auth() -> dict[str, str]:
        return {
            "org_id": org_id,
            "user_id": f"user-{uuid4().hex[:8]}",
            "key_id": f"key-{uuid4().hex[:8]}",
            "plan": "pro",
        }

    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        create_response = await client.post(
            "/v1/capability-bindings",
            json={
                "provider_id": "provider.mcp.generic",
                "profile_id": "profile.mcp.workspace",
                "binding_name": "Customer MCP",
                "execution_owner": "client_managed",
                "config": {
                    "authorization_url": "https://auth.example.com/authorize",
                    "manifest": {"capabilities": []},
                },
            },
        )
        assert create_response.status_code == 201
        binding = create_response.json()

        start_response = await client.post(
            f"/v1/capability-bindings/{binding['binding_id']}/authorize/start",
            json={
                "redirect_uri": "https://customer.example.com/callback",
                "requested_scopes": ["tools.read"],
            },
        )
        assert start_response.status_code == 200
        started = start_response.json()
        assert started["binding_id"] == binding["binding_id"]
        assert started["provider_id"] == "provider.mcp.generic"
        assert "auth.example.com" in started["authorize_url"]

        complete_response = await client.post(
            f"/v1/capability-bindings/{binding['binding_id']}/authorize/complete",
            json={
                "session_id": started["session_id"],
                "authorization_code": "code-123",
                "state": "state-123",
            },
        )
        assert complete_response.status_code == 200
        completed = complete_response.json()
        assert completed["status"] == "completed"
        assert completed["binding_id"] == binding["binding_id"]

        binding_response = await client.get(
            f"/v1/capability-bindings/{binding['binding_id']}"
        )
        assert binding_response.status_code == 200
        persisted_binding = binding_response.json()
        assert persisted_binding["status"] == "ready"
        assert persisted_binding["authorized_at"] is not None
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_capability_plane_preview_discovery_rejects_invalid_manifest_enum(client) -> None:
    org_id = await _seed_org()

    async def _fake_auth() -> dict[str, str]:
        return {
            "org_id": org_id,
            "user_id": f"user-{uuid4().hex[:8]}",
            "key_id": f"key-{uuid4().hex[:8]}",
            "plan": "pro",
        }

    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        response = await client.post(
            "/v1/capability-bindings/discover",
            json={
                "provider_id": "provider.skill_pack.algenta",
                "profile_id": "profile.skill_pack.user",
                "scope": "user",
                "config": {
                    "manifest": {
                        "capabilities": [
                            {
                                "capability_id": "cap.skill.invalid",
                                "name": "Broken Skill",
                                "kind": "not_a_kind",
                            }
                        ]
                    }
                },
            },
        )
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "invalid_capability_manifest"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_preview_endpoints_reject_cross_tenant_connector_id(client) -> None:
    """Regression: the binding preview endpoints (test/discover) must NOT resolve a
    caller-supplied config.connector_id that belongs to another org or workspace.

    Before the fix, _connector_config_for_binding did a bare db.get(DataConnector, id)
    with no org/workspace scope — a cross-tenant / cross-org IDOR that decrypted and
    live-connected a victim's saved connector. The scoped lookup must 404 instead."""
    # Victim connector lives in org A / workspace A and holds a secret DSN.
    org_a = await _seed_org()
    ws_a = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        connector = DataConnector(
            org_id=uuid.UUID(org_a),
            workspace_id=ws_a,
            name="victim-connector",
            connector_type=ConnectorType.POSTGRES,
            config_json='{"connection_string": "postgres://victim:topsecret@db/x"}',
            visibility=ConnectorVisibility.PRIVATE.value,
        )
        session.add(connector)
        await session.commit()
        victim_id = str(connector.id)

    attack_body = {
        "provider_id": "provider.data_connector.algenta",
        "profile_id": "profile.data_connector.workspace",
        "scope": "workspace",
        "config": {"connector_id": victim_id},
    }

    # Attacker 1 — DIFFERENT ORG (no workspace scope).
    org_b = await _seed_org()

    async def _attacker_cross_org() -> dict:
        return {
            "org_id": org_b,
            "user_id": f"user-{uuid4().hex[:8]}",
            "key_id": f"key-{uuid4().hex[:8]}",
            "plan": "pro",
            "is_platform": False,
            "workspace_id": None,
        }

    app.dependency_overrides[get_current_org] = _attacker_cross_org
    try:
        for path in ("/v1/capability-bindings/discover", "/v1/capability-bindings/test"):
            resp = await client.post(path, json=attack_body)
            assert resp.status_code == 404, (path, resp.status_code, resp.text)
            assert "topsecret" not in resp.text  # victim config must never leak
    finally:
        app.dependency_overrides.pop(get_current_org, None)

    # Attacker 2 — SAME ORG A, DIFFERENT workspace B (platform key scoped to B).
    ws_b = uuid.uuid4()

    async def _attacker_cross_ws() -> dict:
        return {
            "org_id": org_a,
            "user_id": f"user-{uuid4().hex[:8]}",
            "key_id": f"key-{uuid4().hex[:8]}",
            "plan": "pro",
            "is_platform": True,
            "workspace_id": ws_b,
        }

    app.dependency_overrides[get_current_org] = _attacker_cross_ws
    try:
        for path in ("/v1/capability-bindings/discover", "/v1/capability-bindings/test"):
            resp = await client.post(path, json=attack_body)
            assert resp.status_code == 404, (path, resp.status_code, resp.text)
            assert "topsecret" not in resp.text
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.anyio
async def test_authorization_complete_rejects_cross_workspace(client) -> None:
    """Regression: completing a capability-binding authorization must enforce the
    binding's workspace, not just its org. complete_capability_authorization_service
    previously used a raw db.get(CapabilityBinding) (org-only); a sibling workspace
    (same org) could complete/mutate another workspace's binding auth. It now routes
    through _require_binding (org + workspace), so the cross-workspace caller 404s."""
    org_id = await _seed_org()
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    def _auth_for(ws: uuid.UUID):
        async def _fake() -> dict:
            return {
                "org_id": org_id,
                "user_id": f"user-{uuid4().hex[:8]}",
                "key_id": f"key-{uuid4().hex[:8]}",
                "plan": "pro",
                "is_platform": True,
                "workspace_id": ws,
            }

        return _fake

    binding_body = {
        "provider_id": "provider.mcp.generic",
        "profile_id": "profile.mcp.workspace",
        "binding_name": "Customer MCP A",
        "execution_owner": "client_managed",
        "config": {
            "authorization_url": "https://auth.example.com/authorize",
            "manifest": {"capabilities": []},
        },
    }
    complete_body = lambda sid: {  # noqa: E731
        "session_id": sid,
        "authorization_code": "code-x",
        "state": "state-x",
    }

    # Workspace A creates the binding + starts an authorization session.
    app.dependency_overrides[get_current_org] = _auth_for(ws_a)
    try:
        create = await client.post("/v1/capability-bindings", json=binding_body)
        assert create.status_code == 201, create.text
        binding_id = create.json()["binding_id"]
        start = await client.post(
            f"/v1/capability-bindings/{binding_id}/authorize/start",
            json={"redirect_uri": "https://c.example.com/cb", "requested_scopes": ["tools.read"]},
        )
        assert start.status_code == 200, start.text
        session_id = start.json()["session_id"]
    finally:
        app.dependency_overrides.pop(get_current_org, None)

    # Workspace B (same org) cannot complete workspace A's session.
    app.dependency_overrides[get_current_org] = _auth_for(ws_b)
    try:
        resp_b = await client.post(
            f"/v1/capability-bindings/{binding_id}/authorize/complete",
            json=complete_body(session_id),
        )
        assert resp_b.status_code == 404, resp_b.text
    finally:
        app.dependency_overrides.pop(get_current_org, None)

    # Workspace A can still complete its own.
    app.dependency_overrides[get_current_org] = _auth_for(ws_a)
    try:
        resp_a = await client.post(
            f"/v1/capability-bindings/{binding_id}/authorize/complete",
            json=complete_body(session_id),
        )
        assert resp_a.status_code == 200, resp_a.text
        assert resp_a.json()["status"] == "completed"
    finally:
        app.dependency_overrides.pop(get_current_org, None)
