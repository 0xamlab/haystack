from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import capability_plane


@pytest.mark.anyio
async def test_list_capability_providers_handler_uses_capability_plane_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path) == ("GET", "/v1/capability-providers")
        assert kwargs == {}
        return [{"provider_id": "provider.mcp.generic"}]

    monkeypatch.setattr(capability_plane, "api", _fake_api)

    raw = await capability_plane.list_capability_providers_handler({})
    payload = json.loads(raw)

    assert payload == [{"provider_id": "provider.mcp.generic"}]


@pytest.mark.anyio
async def test_discover_capability_binding_handler_supports_saved_and_preview_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str, dict[str, object]]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen.append((method, path, kwargs))
        return {"ok": True, "path": path}

    monkeypatch.setattr(capability_plane, "api", _fake_api)

    preview_raw = await capability_plane.discover_capability_binding_handler(
        {
            "provider_id": "provider.skill_pack.algenta",
            "profile_id": "profile.skill_pack.user",
            "config": {"manifest": {"capabilities": []}},
        }
    )
    saved_raw = await capability_plane.discover_capability_binding_handler(
        {"binding_id": "binding-123"}
    )

    assert json.loads(preview_raw)["path"] == "/v1/capability-bindings/discover"
    assert json.loads(saved_raw)["path"] == "/v1/capability-bindings/binding-123/discover"
    assert seen == [
        (
            "POST",
            "/v1/capability-bindings/discover",
            {
                "json": {
                    "provider_id": "provider.skill_pack.algenta",
                    "profile_id": "profile.skill_pack.user",
                    "config": {"manifest": {"capabilities": []}},
                }
            },
        ),
        ("POST", "/v1/capability-bindings/binding-123/discover", {}),
    ]


@pytest.mark.anyio
async def test_enable_skill_handler_creates_binding_then_discovers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str, dict[str, object]]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen.append((method, path, kwargs))
        if (method, path) == ("POST", "/v1/capability-bindings"):
            return {"binding_id": "binding-skill-1"}
        if (method, path) == ("POST", "/v1/capability-bindings/binding-skill-1/discover"):
            return {"binding_id": "binding-skill-1", "capability_count": 1}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(capability_plane, "api", _fake_api)

    raw = await capability_plane.enable_skill_handler(
        {
            "skill_name": "Escalation Skill",
            "instruction": "Escalate immediately.",
            "tags": ["incident"],
        }
    )
    payload = json.loads(raw)

    assert payload["binding_id"] == "binding-skill-1"
    assert payload["capability_count"] == 1
    assert seen[0][0:2] == ("POST", "/v1/capability-bindings")
    create_payload = seen[0][2]["json"]
    assert create_payload["provider_id"] == "provider.skill_pack.algenta"
    assert create_payload["profile_id"] == "profile.skill_pack.user"
    assert create_payload["config"]["manifest"]["capabilities"][0]["kind"] == "skill"


def test_capability_plane_mcp_tool_specs_lock_execution_ownership_language() -> None:
    route_spec = capability_plane.ROUTE_CAPABILITIES_SPEC
    execute_spec = capability_plane.EXECUTE_CAPABILITY_SPEC

    assert "authoritative execution_owner" in route_spec["description"]
    assert "algenta_managed capability" in execute_spec["description"]
    assert "client_managed routes must execute in the customer app or adapter path" in execute_spec["description"]


@pytest.mark.anyio
async def test_execute_capability_handler_posts_to_capability_plane_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str, dict[str, object]]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        seen.append((method, path, kwargs))
        return {
            "execution_session_id": "exec-123",
            "capability_id": "cap.skill.escalation",
            "execution_owner": "algenta_managed",
            "status": "succeeded",
        }

    monkeypatch.setattr(capability_plane, "api", _fake_api)

    raw = await capability_plane.execute_capability_handler(
        {
            "capability_id": "cap.skill.escalation",
            "binding_id": "binding-123",
            "input": {"objective": "Escalate incident"},
        }
    )
    payload = json.loads(raw)

    assert payload["execution_session_id"] == "exec-123"
    assert payload["execution_owner"] == "algenta_managed"
    assert seen == [
        (
            "POST",
            "/v1/capabilities/execute",
            {
                "json": {
                    "capability_id": "cap.skill.escalation",
                    "binding_id": "binding-123",
                    "input": {"objective": "Escalate incident"},
                }
            },
        )
    ]
