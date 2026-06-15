from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import account, control_plane, deployments, usage


def test_account_tool_specs_match_expected_contract() -> None:
    assert account.GET_ME_SPEC["name"] == "get_me"
    assert account.UPDATE_ME_SPEC["name"] == "update_me"
    assert account.GET_LIMITS_SPEC["name"] == "get_limits"
    assert account.LIST_DISTRIBUTIONS_SPEC["name"] == "list_distributions"
    assert account.LIST_TEMPLATES_SPEC["name"] == "list_templates"
    assert account.LIST_API_KEYS_SPEC["name"] == "list_api_keys"
    assert account.CREATE_API_KEY_SPEC["name"] == "create_api_key"
    assert account.REVOKE_API_KEY_SPEC["name"] == "revoke_api_key"
    assert account.CREATE_API_KEY_SPEC["inputSchema"]["required"] == ["label"]
    assert account.REVOKE_API_KEY_SPEC["inputSchema"]["required"] == ["key_id"]
    assert deployments.LIST_DEPLOYMENT_REGIONS_SPEC["name"] == "list_deployment_regions"
    assert deployments.GET_DEPLOYMENT_SPEC["name"] == "get_deployment"
    assert deployments.CREATE_DEPLOYMENT_SPEC["name"] == "create_deployment"
    assert deployments.GET_DEPLOYMENT_COST_SPEC["name"] == "get_deployment_cost"
    assert deployments.DELETE_DEPLOYMENT_SPEC["name"] == "delete_deployment"
    assert deployments.GET_DEPLOYMENT_COST_SPEC["inputSchema"]["required"] == ["deployment_id"]
    assert deployments.DELETE_DEPLOYMENT_SPEC["inputSchema"]["required"] == ["deployment_id"]
    assert control_plane.LIST_TEAM_MEMBERS_SPEC["name"] == "list_team_members"
    assert control_plane.INVITE_TEAM_MEMBER_SPEC["name"] == "invite_team_member"
    assert control_plane.UPDATE_TEAM_MEMBER_ROLE_SPEC["name"] == "update_team_member_role"
    assert control_plane.REMOVE_TEAM_MEMBER_SPEC["name"] == "remove_team_member"
    assert control_plane.LIST_DEVICES_SPEC["name"] == "list_devices"
    assert control_plane.REVOKE_DEVICE_SPEC["name"] == "revoke_device"
    assert control_plane.REVOKE_DEVICE_SPEC["inputSchema"]["required"] == ["registration_id"]
    assert control_plane.GET_AUDIT_LOGS_SPEC["name"] == "get_audit_logs"
    assert control_plane.GET_AUDIT_LOG_ARTIFACTS_SPEC["name"] == "get_audit_log_artifacts"
    assert control_plane.GET_EXECUTION_POLICY_SPEC["name"] == "get_execution_policy"
    assert (
        control_plane.LIST_EXECUTION_POLICY_SNAPSHOTS_SPEC["name"]
        == "list_execution_policy_snapshots"
    )
    assert control_plane.GET_BILLING_INFO_SPEC["name"] == "get_billing_info"
    assert control_plane.CREATE_BILLING_CHECKOUT_SPEC["name"] == "create_billing_checkout"
    assert control_plane.CREATE_BILLING_PORTAL_SPEC["name"] == "create_billing_portal"
    assert control_plane.REFRESH_CREDITS_SPEC["name"] == "refresh_credits"
    assert control_plane.INGEST_METERING_EVENTS_SPEC["name"] == "ingest_metering_events"
    assert control_plane.UPDATE_EXECUTION_POLICY_SPEC["name"] == "update_execution_policy"


@pytest.mark.anyio
async def test_account_handlers_forward_canonical_api_routes(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path, kwargs.get("json")))
        if (method, path) == ("GET", "/v1/me"):
            return {"email": "owner@example.com", "org_id": "org_123"}
        if (method, path) == ("PATCH", "/v1/me"):
            return {
                "user": {"email": "owner@example.com", "name": "Mission Ops"},
                "org": {"name": "Mission Control"},
            }
        if (method, path) == ("GET", "/v1/limits"):
            return {"plan": "enterprise", "simulations_per_month": "unlimited"}
        if (method, path) == ("GET", "/v1/distributions"):
            return [
                {
                    "name": "normal",
                    "description": "Normal distribution.",
                    "required_params": ["mean", "std"],
                    "optional_params": [],
                    "example": {"mean": 100, "std": 12},
                }
            ]
        if (method, path) == ("GET", "/v1/templates"):
            return [
                {
                    "id": "product-launch",
                    "name": "Product Launch Decision",
                    "category": "business",
                    "description": "Compare launch scenarios.",
                    "example_request": {"mode": "auto"},
                }
            ]
        if (method, path) == ("GET", "/v1/api-keys"):
            return [
                {
                    "id": "key_1",
                    "label": "Mission Runtime Key",
                    "key_prefix": "de_live_abcd",
                    "device_limit": 2,
                    "status": "active",
                }
            ]
        if (method, path) == ("POST", "/v1/api-keys"):
            return {
                "id": "key_2",
                "label": "Mission Rotation Key",
                "key_prefix": "de_live_efgh",
                "device_limit": 3,
                "raw_key": "de_live_efgh_secret_value",
            }
        if (method, path) == ("DELETE", "/v1/api-keys/key_2"):
            return {}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(account, "api", _fake_api)

    me = json.loads(await account.get_me_handler({}))
    updated = json.loads(await account.update_me_handler({"name": "Mission Ops", "org_name": "Mission Control"}))
    limits = json.loads(await account.get_limits_handler({}))
    distributions = json.loads(await account.list_distributions_handler({}))
    templates = json.loads(await account.list_templates_handler({}))
    listed = json.loads(await account.list_api_keys_handler({}))
    created = json.loads(
        await account.create_api_key_handler(
            {
                "label": "Mission Rotation Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 3,
            }
        )
    )
    revoked = json.loads(await account.revoke_api_key_handler({"key_id": "key_2"}))

    assert me["email"] == "owner@example.com"
    assert updated["org"]["name"] == "Mission Control"
    assert limits["plan"] == "enterprise"
    assert distributions["distributions"][0]["name"] == "normal"
    assert templates["templates"][0]["id"] == "product-launch"
    assert listed["api_keys"][0]["label"] == "Mission Runtime Key"
    assert created["raw_key"] == "de_live_efgh_secret_value"
    assert revoked == {"key_id": "key_2", "revoked": True}
    assert calls == [
        ("GET", "/v1/me", None),
        ("PATCH", "/v1/me", {"name": "Mission Ops", "org_name": "Mission Control"}),
        ("GET", "/v1/limits", None),
        ("GET", "/v1/distributions", None),
        ("GET", "/v1/templates", None),
        ("GET", "/v1/api-keys", None),
        (
            "POST",
            "/v1/api-keys",
            {
                "label": "Mission Rotation Key",
                "expires_at": "2028-05-19T00:00:00Z",
                "device_limit": 3,
            },
        ),
        ("DELETE", "/v1/api-keys/key_2", None),
    ]


@pytest.mark.anyio
async def test_account_handlers_validate_arguments() -> None:
    with pytest.raises(ValueError, match="does not accept arguments"):
        await account.get_me_handler({"extra": True})
    with pytest.raises(ValueError, match="requires name and or org_name"):
        await account.update_me_handler({})
    with pytest.raises(ValueError, match="does not accept arguments"):
        await account.list_distributions_handler({"extra": True})
    with pytest.raises(ValueError, match="does not accept arguments"):
        await account.list_templates_handler({"extra": True})
    with pytest.raises(ValueError, match="requires a non-empty label"):
        await account.create_api_key_handler({})
    with pytest.raises(ValueError, match="device_limit"):
        await account.create_api_key_handler({"label": "Mission", "device_limit": -1})
    with pytest.raises(ValueError, match="requires a non-empty key_id"):
        await account.revoke_api_key_handler({})


@pytest.mark.anyio
async def test_deployment_handlers_forward_canonical_api_routes(monkeypatch) -> None:
    calls: list[tuple[str, str, object]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path, kwargs.get("json")))
        if (method, path) == ("GET", "/v1/deployments/regions"):
            return {
                "providers": [
                    {
                        "id": "algenta_shared",
                        "name": "Codna Managed",
                        "regions": [
                            {
                                "id": "algenta-shared",
                                "label": "Codna Shared",
                                "location": "Global",
                            }
                        ],
                    }
                ]
            }
        if (method, path) == ("GET", "/v1/deployments"):
            return {
                "deployment_id": "dep_123",
                "provider": "algenta_shared",
                "region": "algenta-shared",
                "status": "requested",
            }
        if (method, path) == ("POST", "/v1/deployments"):
            return {
                "deployment_id": "dep_123",
                "provider": "aws",
                "region": "us-east-1",
                "status": "requested",
                "billing_markup_pct": 25.0,
            }
        if (method, path) == ("GET", "/v1/deployments/dep_123/cost"):
            return {
                "deployment_id": "dep_123",
                "provider": "algenta_shared",
                "region": "algenta-shared",
                "year": 2026,
                "month": 5,
                "cost_usd_month": 12.5,
                "billable_cost_usd_month": 15.0,
                "billing_markup_pct": 20.0,
                "last_updated": "2026-05-24T12:30:00Z",
            }
        if (method, path) == ("DELETE", "/v1/deployments/dep_123"):
            return {"status": "deprovisioning", "deployment_id": "dep_123"}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(deployments, "api", _fake_api)

    regions = json.loads(await deployments.list_deployment_regions_handler({}))
    current = json.loads(await deployments.get_deployment_handler({}))
    created = json.loads(
        await deployments.create_deployment_handler(
            {
                "provider": "aws",
                "region": "us-east-1",
                "config": {"instance_type": "c7g.large"},
                "billing_markup_pct": 25.0,
            }
        )
    )
    cost = json.loads(await deployments.get_deployment_cost_handler({"deployment_id": "dep_123"}))
    deleted = json.loads(await deployments.delete_deployment_handler({"deployment_id": "dep_123"}))

    assert regions["providers"][0]["id"] == "algenta_shared"
    assert current["deployment_id"] == "dep_123"
    assert created["provider"] == "aws"
    assert created["billing_markup_pct"] == 25.0
    assert cost["cost_usd_month"] == 12.5
    assert deleted == {"status": "deprovisioning", "deployment_id": "dep_123"}
    assert calls == [
        ("GET", "/v1/deployments/regions", None),
        ("GET", "/v1/deployments", None),
        (
            "POST",
            "/v1/deployments",
            {
                "provider": "aws",
                "region": "us-east-1",
                "config": {"instance_type": "c7g.large"},
                "billing_markup_pct": 25.0,
            },
        ),
        ("GET", "/v1/deployments/dep_123/cost", None),
        ("DELETE", "/v1/deployments/dep_123", None),
    ]


@pytest.mark.anyio
async def test_deployment_handlers_validate_arguments() -> None:
    with pytest.raises(ValueError, match="does not accept arguments"):
        await deployments.list_deployment_regions_handler({"extra": True})
    with pytest.raises(ValueError, match="does not accept arguments"):
        await deployments.get_deployment_handler({"extra": True})
    with pytest.raises(ValueError, match="provider"):
        await deployments.create_deployment_handler({"provider": 7})
    with pytest.raises(ValueError, match="region"):
        await deployments.create_deployment_handler({"region": 7})
    with pytest.raises(ValueError, match="config"):
        await deployments.create_deployment_handler({"config": []})
    with pytest.raises(ValueError, match="billing_markup_pct"):
        await deployments.create_deployment_handler({"billing_markup_pct": True})
    with pytest.raises(ValueError, match="billing_markup_pct"):
        await deployments.create_deployment_handler({"billing_markup_pct": "25"})
    with pytest.raises(ValueError, match="deployment_id"):
        await deployments.get_deployment_cost_handler({})
    with pytest.raises(ValueError, match="deployment_id"):
        await deployments.get_deployment_cost_handler({"deployment_id": ""})
    with pytest.raises(ValueError, match="deployment_id"):
        await deployments.delete_deployment_handler({"deployment_id": ""})


@pytest.mark.anyio
async def test_control_plane_handlers_forward_canonical_api_routes(monkeypatch) -> None:
    calls: list[tuple[str, str, object, object]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path, kwargs.get("json"), kwargs.get("params")))
        if (method, path) == ("GET", "/v1/team"):
            return [
                {
                    "user_id": "user_1",
                    "name": "Owner",
                    "email": "owner@example.com",
                    "role": "owner",
                    "status": "active",
                    "last_active": None,
                }
            ]
        if (method, path) == ("POST", "/v1/team/invite"):
            return {"message": "Invitation sent.", "invite_id": "invite_123"}
        if (method, path) == ("PATCH", "/v1/team/user_1/role"):
            return {"message": "Role updated.", "user_id": "user_1"}
        if (method, path) == ("DELETE", "/v1/team/user_1"):
            return {}
        if (method, path) == ("GET", "/v1/billing/info"):
            return {
                "plan": "enterprise",
                "stripe_customer_id": "cus_123",
                "subscription_status": "active",
                "current_period_end": "2026-06-30T00:00:00Z",
            }
        if (method, path) == ("POST", "/v1/billing/checkout"):
            return {"url": "https://billing.example/checkout/session_123"}
        if (method, path) == ("POST", "/v1/billing/portal"):
            return {"url": "https://billing.example/portal/session_123"}
        if (method, path) == ("POST", "/v1/credits/refresh"):
            return {
                "credits_granted": 10000,
                "credits_issued_this_month": 25000,
                "monthly_limit": 500000,
                "monthly_remaining": 475000,
                "billing_period": "2026-05",
                "expires_at": 1716547200,
                "refresh_after": 1716545040,
                "server_time": 1716460800,
            }
        if (method, path) == ("POST", "/v1/metering"):
            return {"accepted": 2, "billing_period": "2026-05"}
        if (method, path) == ("GET", "/v1/device/list"):
            return {
                "devices": [
                    {
                        "id": "reg_123",
                        "org_id": "org_123",
                        "api_key_id": "key_123",
                        "device_id": "device_123456789012",
                        "platform": "macos",
                        "platform_version": "15.5",
                        "hostname_hash": "host_hash",
                        "sdk_version": "1.0.0",
                        "status": "active",
                        "last_heartbeat_at": "2026-05-24T12:00:00Z",
                        "heartbeat_count": 3,
                        "created_at": "2026-05-24T11:00:00Z",
                        "updated_at": "2026-05-24T12:00:00Z",
                    }
                ],
                "device_count": 1,
                "total": 1,
                "page": 1,
                "limit": 25,
                "pages": 1,
                "device_limit": 2,
                "plan": "enterprise",
            }
        if (method, path) == ("DELETE", "/v1/device/reg_123"):
            return {"revoked": True, "registration_id": "reg_123"}
        if (method, path) == ("GET", "/v1/audit-logs"):
            return {
                "entries": [
                    {
                        "id": "evt_1",
                        "timestamp": "2026-05-24T12:30:00Z",
                        "actor_email": "owner@example.com",
                        "action": "invite_member",
                        "resource_type": "team_member",
                        "resource_id": "user_2",
                        "ip_address": "203.0.113.11",
                        "result": "success",
                        "metadata": {
                            "policy_snapshot_id": "policy-v1",
                            "schema_snapshot_id": "schema-v1",
                        },
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 25,
                "pages": 1,
            }
        if (method, path) == ("GET", "/v1/audit-logs/artifacts"):
            return {
                "entries": [
                    {
                        "id": "evt_1",
                        "timestamp": "2026-05-24T12:30:00Z",
                        "actor_email": "owner@example.com",
                        "action": "invite_member",
                        "resource_type": "team_member",
                        "resource_id": "user_2",
                        "ip_address": "203.0.113.11",
                        "result": "success",
                        "content_hash": "content_hash_1",
                        "metadata": {
                            "policy_snapshot_id": "policy-v1",
                            "schema_snapshot_id": "schema-v1",
                        },
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 5,
                "pages": 1,
            }
        if (method, path) == ("GET", "/v1/execution/policy"):
            return {
                "org_id": "org_123",
                "min_confidence": 0.75,
                "risk_floor": 25000.0,
                "require_calibration": True,
                "allow_reexecution": False,
                "snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
                "revision": 2,
                "updated_at": "2026-05-24T12:30:00Z",
            }
        if (method, path) == ("GET", "/v1/execution/policy/snapshots"):
            return {
                "org_id": "org_123",
                "data": [
                    {
                        "org_id": "org_123",
                        "min_confidence": 0.75,
                        "risk_floor": 25000.0,
                        "require_calibration": True,
                        "allow_reexecution": False,
                        "snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
                        "revision": 2,
                        "updated_at": "2026-05-24T12:30:00Z",
                    }
                ],
                "total_snapshots": 1,
            }
        if (method, path) == ("PATCH", "/v1/execution/policy"):
            return {
                "org_id": "org_123",
                "min_confidence": 0.8,
                "risk_floor": 15000.0,
                "require_calibration": False,
                "allow_reexecution": True,
                "snapshot_id": "execution-policy-v1-r3:fedcfedcfedcfedc",
                "revision": 3,
                "updated_at": "2026-05-24T12:35:00Z",
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(control_plane, "api", _fake_api)

    team = json.loads(await control_plane.list_team_members_handler({"page": 1, "limit": 50}))
    invited = json.loads(
        await control_plane.invite_team_member_handler({"email": "new@example.com", "role": "admin"})
    )
    updated_member = json.loads(
        await control_plane.update_team_member_role_handler({"user_id": "user_1", "role": "viewer"})
    )
    removed_member = json.loads(await control_plane.remove_team_member_handler({"user_id": "user_1"}))
    billing = json.loads(await control_plane.get_billing_info_handler({}))
    checkout = json.loads(await control_plane.create_billing_checkout_handler({"plan": "pro"}))
    portal = json.loads(await control_plane.create_billing_portal_handler({}))
    refreshed = json.loads(
        await control_plane.refresh_credits_handler(
            {
                "device_id": "device_mcp_123",
                "billing_period": "2026-05",
                "credits_used": 9,
            }
        )
    )
    metering = json.loads(
        await control_plane.ingest_metering_events_handler(
            {
                "device_id": "device_mcp_123",
                "events": [{"event_type": "query", "latency_ms": 3.5, "success": True}],
            }
        )
    )
    devices = json.loads(await control_plane.list_devices_handler({"page": 1, "limit": 25}))
    revoked = json.loads(await control_plane.revoke_device_handler({"registration_id": "reg_123"}))
    logs = json.loads(
        await control_plane.get_audit_logs_handler(
            {
                "page": 1,
                "limit": 25,
                "actor_email": "owner@example.com",
                "action": "invite_member",
                "resource_type": "team_member",
                "result": "success",
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "manifest_version": "runtime-manifest-v1",
                "request_hash": "hash_123",
            }
        )
    )
    artifacts = json.loads(
        await control_plane.get_audit_log_artifacts_handler(
            {
                "page": 1,
                "limit": 5,
                "actor_email": "owner@example.com",
                "action": "invite_member",
                "resource_type": "team_member",
                "result": "success",
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "manifest_version": "runtime-manifest-v1",
                "request_hash": "hash_123",
                "content_hash": "content_hash_1",
            }
        )
    )
    policy = json.loads(await control_plane.get_execution_policy_handler({}))
    snapshots = json.loads(await control_plane.list_execution_policy_snapshots_handler({}))
    updated = json.loads(
        await control_plane.update_execution_policy_handler(
            {
                "min_confidence": 0.8,
                "risk_floor": 15000.0,
                "require_calibration": False,
                "allow_reexecution": True,
            }
        )
    )

    assert team[0]["email"] == "owner@example.com"
    assert invited["invite_id"] == "invite_123"
    assert updated_member["user_id"] == "user_1"
    assert removed_member == {"removed": True, "user_id": "user_1"}
    assert billing["plan"] == "enterprise"
    assert checkout["url"].endswith("session_123")
    assert portal["url"].endswith("session_123")
    assert refreshed["credits_granted"] == 10000
    assert metering["accepted"] == 2
    assert devices["device_count"] == 1
    assert devices["devices"][0]["device_id"] == "device_123456789012"
    assert revoked == {"revoked": True, "registration_id": "reg_123"}
    assert logs["entries"][0]["action"] == "invite_member"
    assert logs["entries"][0]["metadata"]["policy_snapshot_id"] == "policy-v1"
    assert artifacts["entries"][0]["content_hash"] == "content_hash_1"
    assert policy["min_confidence"] == 0.75
    assert snapshots["total_snapshots"] == 1
    assert updated["allow_reexecution"] is True
    assert calls == [
        ("GET", "/v1/team", None, {"page": 1, "limit": 50}),
        ("POST", "/v1/team/invite", {"email": "new@example.com", "role": "admin"}, None),
        ("PATCH", "/v1/team/user_1/role", {"role": "viewer"}, None),
        ("DELETE", "/v1/team/user_1", None, None),
        ("GET", "/v1/billing/info", None, None),
        ("POST", "/v1/billing/checkout", {"plan": "pro"}, None),
        ("POST", "/v1/billing/portal", {}, None),
        (
            "POST",
            "/v1/credits/refresh",
            {
                "device_id": "device_mcp_123",
                "billing_period": "2026-05",
                "credits_used": 9,
            },
            None,
        ),
        (
            "POST",
            "/v1/metering",
            {
                "device_id": "device_mcp_123",
                "events": [{"event_type": "query", "latency_ms": 3.5, "success": True}],
            },
            None,
        ),
        ("GET", "/v1/device/list", None, {"page": 1, "limit": 25}),
        ("DELETE", "/v1/device/reg_123", None, None),
        (
            "GET",
            "/v1/audit-logs",
            None,
            {
                "page": 1,
                "limit": 25,
                "actor_email": "owner@example.com",
                "action": "invite_member",
                "resource_type": "team_member",
                "result": "success",
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "manifest_version": "runtime-manifest-v1",
                "request_hash": "hash_123",
            },
        ),
        (
            "GET",
            "/v1/audit-logs/artifacts",
            None,
            {
                "page": 1,
                "limit": 5,
                "actor_email": "owner@example.com",
                "action": "invite_member",
                "resource_type": "team_member",
                "result": "success",
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "manifest_version": "runtime-manifest-v1",
                "request_hash": "hash_123",
                "content_hash": "content_hash_1",
            },
        ),
        ("GET", "/v1/execution/policy", None, None),
        ("GET", "/v1/execution/policy/snapshots", None, None),
        (
            "PATCH",
            "/v1/execution/policy",
            {
                "min_confidence": 0.8,
                "risk_floor": 15000.0,
                "require_calibration": False,
                "allow_reexecution": True,
            },
            None,
        ),
    ]


@pytest.mark.anyio
async def test_control_plane_handlers_validate_arguments() -> None:
    with pytest.raises(ValueError, match="page must be a positive integer"):
        await control_plane.list_team_members_handler({"page": 0})
    with pytest.raises(ValueError, match="valid email"):
        await control_plane.invite_team_member_handler({"email": "invalid"})
    with pytest.raises(ValueError, match="user_id"):
        await control_plane.update_team_member_role_handler({"role": "admin"})
    with pytest.raises(ValueError, match="role"):
        await control_plane.update_team_member_role_handler(
            {"user_id": "user_1", "role": "superadmin"}
        )
    with pytest.raises(ValueError, match="user_id"):
        await control_plane.remove_team_member_handler({})
    with pytest.raises(ValueError, match="does not accept arguments"):
        await control_plane.get_billing_info_handler({"extra": True})
    with pytest.raises(ValueError, match="plan"):
        await control_plane.create_billing_checkout_handler({"plan": "enterprise"})
    with pytest.raises(ValueError, match="does not accept arguments"):
        await control_plane.create_billing_portal_handler({"extra": True})
    with pytest.raises(ValueError, match="device_id"):
        await control_plane.refresh_credits_handler({"billing_period": "2026-05"})
    with pytest.raises(ValueError, match="billing_period"):
        await control_plane.refresh_credits_handler({"device_id": "device_123", "billing_period": "202605"})
    with pytest.raises(ValueError, match="month must be between 01 and 12"):
        await control_plane.refresh_credits_handler(
            {"device_id": "device_123", "billing_period": "2026-13"}
        )
    with pytest.raises(ValueError, match="credits_used"):
        await control_plane.refresh_credits_handler(
            {"device_id": "device_123", "billing_period": "2026-05", "credits_used": -1}
        )
    with pytest.raises(ValueError, match="device_id"):
        await control_plane.ingest_metering_events_handler({"events": [{}]})
    with pytest.raises(ValueError, match="events list"):
        await control_plane.ingest_metering_events_handler(
            {"device_id": "device_123", "events": []}
        )
    with pytest.raises(ValueError, match="unsupported fields"):
        await control_plane.ingest_metering_events_handler(
            {"device_id": "device_123", "events": [{"event_type": "query", "unexpected": True}]}
        )
    with pytest.raises(ValueError, match="limit must be a positive integer"):
        await control_plane.list_devices_handler({"limit": 0})
    with pytest.raises(ValueError, match="registration_id"):
        await control_plane.revoke_device_handler({})
    with pytest.raises(ValueError, match="limit must be a positive integer"):
        await control_plane.get_audit_logs_handler({"limit": 0})
    with pytest.raises(ValueError, match="actor_email must be a non-empty string"):
        await control_plane.get_audit_logs_handler({"actor_email": "   "})
    with pytest.raises(ValueError, match="content_hash must be a non-empty string"):
        await control_plane.get_audit_log_artifacts_handler({"content_hash": "   "})
    with pytest.raises(ValueError, match="does not accept arguments"):
        await control_plane.get_execution_policy_handler({"extra": True})
    with pytest.raises(ValueError, match="does not accept arguments"):
        await control_plane.list_execution_policy_snapshots_handler({"extra": True})
    with pytest.raises(ValueError, match="requires at least one update field"):
        await control_plane.update_execution_policy_handler({})
    with pytest.raises(ValueError, match="min_confidence"):
        await control_plane.update_execution_policy_handler({"min_confidence": "0.7"})
    with pytest.raises(ValueError, match="risk_floor"):
        await control_plane.update_execution_policy_handler({"risk_floor": "10"})
    with pytest.raises(ValueError, match="require_calibration"):
        await control_plane.update_execution_policy_handler({"require_calibration": "yes"})
    with pytest.raises(ValueError, match="allow_reexecution"):
        await control_plane.update_execution_policy_handler({"allow_reexecution": "no"})


@pytest.mark.anyio
async def test_get_usage_handler_uses_canonical_usage_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((method, path))
        return {
            "billing_period": "2026-05",
            "simulations_run": 120,
            "quota_limit": 1000,
            "quota_used_pct": 12.0,
            "api_calls": 340,
            "plan": "enterprise",
        }

    monkeypatch.setattr(usage, "api", _fake_api)
    payload = json.loads(await usage.handler({}))

    assert payload["simulations_used"] == 120
    assert payload["simulations_limit"] == 1000
    assert payload["pct_used"] == 12.0
    assert payload["api_calls"] == 340
    assert calls == [("GET", "/v1/usage")]
