from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

pytestmark = pytest.mark.anyio

decision_engine = importlib.import_module("decision_engine")

AsyncDecisionEngineClient = decision_engine.AsyncDecisionEngineClient
DecisionEngineClient = decision_engine.DecisionEngineClient
AuditLogResult = decision_engine.AuditLogResult
BillingInfoResult = decision_engine.BillingInfoResult
BillingSessionResult = decision_engine.BillingSessionResult
CreditRefreshResult = decision_engine.CreditRefreshResult
MeteringBatchResult = decision_engine.MeteringBatchResult
DeviceListResult = decision_engine.DeviceListResult
DeviceRevokeResult = decision_engine.DeviceRevokeResult
DistributionListResult = decision_engine.DistributionListResult
ExecutionPolicyResult = decision_engine.ExecutionPolicyResult
ExecutionPolicySnapshotListResult = decision_engine.ExecutionPolicySnapshotListResult
MeResult = decision_engine.MeResult
TeamInviteResult = decision_engine.TeamInviteResult
TeamListResult = decision_engine.TeamListResult
TeamRemoveResult = decision_engine.TeamRemoveResult
TeamRoleUpdateResult = decision_engine.TeamRoleUpdateResult
TemplateListResult = decision_engine.TemplateListResult


def _team_list_payload() -> list[dict[str, object]]:
    return [
        {
            "user_id": "user_123",
            "name": "Owner",
            "email": "owner@example.com",
            "role": "owner",
            "status": "active",
            "last_active": "2026-05-24T12:00:00Z",
        }
    ]


def _audit_logs_payload() -> dict[str, object]:
    return {
        "entries": [
            {
                "id": "audit_123",
                "timestamp": "2026-05-24T12:00:00Z",
                "actor_email": "owner@example.com",
                "action": "invite_member",
                "resource_type": "team_member",
                "resource_id": "user_456",
                "ip_address": "203.0.113.10",
                "result": "success",
                "metadata": {
                    "policy_snapshot_id": "policy-v1",
                    "schema_snapshot_id": "schema-v1",
                    "manifest_version": "runtime-manifest-v1",
                },
            }
        ],
        "total": 1,
        "page": 1,
        "limit": 25,
        "pages": 1,
    }


def _device_list_payload() -> dict[str, object]:
    return {
        "devices": [
            {
                "id": "reg_123",
                "device_id": "device_12...",
                "platform": "macos",
                "platform_version": "15.5",
                "sdk_version": "1.0.0",
                "status": "active",
                "api_key_label": "Primary SDK Key",
                "api_key_prefix": "de_live_",
                "registered_at": "2026-05-24T11:00:00Z",
                "last_heartbeat_at": "2026-05-24T12:00:00Z",
                "heartbeat_count": 3,
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


def _execution_policy_payload() -> dict[str, object]:
    return {
        "org_id": "org_123",
        "min_confidence": 0.7,
        "risk_floor": 12_500.0,
        "require_calibration": True,
        "allow_reexecution": False,
        "snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
        "content_hash": "abcd1234" * 8,
        "schema_revision": "execution-policy-v1",
        "revision": 2,
        "previous_snapshot_id": "execution-policy-v1-r1:1111222233334444",
        "created_at": "2026-05-24T12:00:00Z",
        "updated_at": "2026-05-24T12:00:00Z",
    }


def _billing_info_payload() -> dict[str, object]:
    return {
        "plan": "enterprise",
        "stripe_customer_id": "cus_123",
        "subscription_status": "active",
        "current_period_end": "2026-06-30T00:00:00Z",
    }


def _metering_payload() -> dict[str, object]:
    return {
        "accepted": 2,
        "billing_period": "2026-05",
    }


def _credit_refresh_payload() -> dict[str, object]:
    return {
        "credits_granted": 10000,
        "credits_issued_this_month": 25000,
        "monthly_limit": 500000,
        "monthly_remaining": 475000,
        "billing_period": "2026-05",
        "expires_at": 1_716_547_200.0,
        "refresh_after": 1_716_545_040.0,
        "server_time": 1_716_460_800.0,
    }


def _me_payload() -> dict[str, object]:
    return {
        "user": {
            "id": "user_123",
            "email": "owner@example.com",
            "name": "Mission Ops",
            "role": "owner",
            "email_verified": True,
            "created_at": "2026-05-24T12:00:00Z",
        },
        "org": {
            "id": "org_123",
            "name": "Mission Control",
            "slug": "mission-control",
            "plan": "enterprise",
            "status": "active",
            "created_at": "2026-05-24T11:00:00Z",
        },
    }


def _distributions_payload() -> list[dict[str, object]]:
    return [
        {
            "name": "normal",
            "description": "Normal distribution.",
            "required_params": ["mean", "std"],
            "optional_params": [],
            "example": {"mean": 100.0, "std": 12.0},
        }
    ]


def _templates_payload() -> list[dict[str, object]]:
    return [
        {
            "id": "product-launch",
            "name": "Product Launch Decision",
            "category": "business",
            "description": "Compare launch scenarios.",
            "example_request": {"mode": "auto"},
        }
    ]


def test_sync_client_control_plane_methods_return_typed_models(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DecisionEngineClient(api_key="de_test_sync", base_url="https://example.test")
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path, kwargs))
        if (method, path) == ("PATCH", "/v1/me"):
            return _me_payload()
        if (method, path) == ("GET", "/v1/team"):
            return _team_list_payload()
        if (method, path) == ("GET", "/v1/billing/info"):
            return _billing_info_payload()
        if (method, path) == ("GET", "/v1/distributions"):
            return _distributions_payload()
        if (method, path) == ("GET", "/v1/templates"):
            return _templates_payload()
        if (method, path) == ("POST", "/v1/metering"):
            return _metering_payload()
        if (method, path) == ("POST", "/v1/team/invite"):
            return {"message": "Invitation sent.", "invite_id": "invite_123"}
        if (method, path) == ("PATCH", "/v1/team/user_123/role"):
            return {"message": "Role updated.", "user_id": "user_123"}
        if (method, path) == ("DELETE", "/v1/team/user_123"):
            return {}
        if (method, path) == ("POST", "/v1/billing/checkout"):
            return {"url": "https://billing.example/checkout/session_123"}
        if (method, path) == ("POST", "/v1/billing/portal"):
            return {"url": "https://billing.example/portal/session_123"}
        if (method, path) == ("POST", "/v1/credits/refresh"):
            return _credit_refresh_payload()
        if (method, path) == ("GET", "/v1/device/list"):
            return _device_list_payload()
        if (method, path) == ("DELETE", "/v1/device/reg_123"):
            return {"revoked": True, "registration_id": "reg_123"}
        if (method, path) == ("GET", "/v1/audit-logs"):
            return _audit_logs_payload()
        if (method, path) == ("GET", "/v1/audit-logs/artifacts"):
            payload = _audit_logs_payload()
            payload["entries"][0]["content_hash"] = "content_hash_1"
            return payload
        if (method, path) == ("GET", "/v1/execution/policy"):
            return _execution_policy_payload()
        if (method, path) == ("GET", "/v1/execution/policy/snapshots"):
            return {"org_id": "org_123", "data": [_execution_policy_payload()], "total_snapshots": 1}
        if (method, path) == ("PATCH", "/v1/execution/policy"):
            return {
                **_execution_policy_payload(),
                "min_confidence": kwargs["json"]["min_confidence"],
                "allow_reexecution": kwargs["json"]["allow_reexecution"],
                "snapshot_id": "execution-policy-v1-r3:fedcfedcfedcfedc",
                "revision": 3,
            }
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(client, "_request", fake_request)

    me = client.update_me(name="Mission Ops", org_name="Mission Control")
    team = client.list_team_members(page=1, limit=50)
    invited = client.invite_team_member(email="new@example.com", role="admin")
    role_updated = client.update_team_member_role("user_123", role="viewer")
    removed = client.remove_team_member("user_123")
    billing_info = client.get_billing_info()
    distributions = client.distributions()
    templates = client.templates()
    checkout = client.create_billing_checkout(plan="pro")
    portal = client.create_billing_portal()
    refreshed = client.refresh_credits(
        device_id="device_ops_123",
        billing_period="2026-05",
        credits_used=321,
    )
    metering = client.ingest_metering_events(
        device_id="device_ops_123",
        events=[
            {"event_type": "query", "latency_ms": 12.5, "success": True},
            {"module": "pricing", "timestamp": 1_716_547_200.0},
        ],
    )
    devices = client.list_devices(page=1, limit=25)
    revoked = client.revoke_device("reg_123")
    logs = client.get_audit_logs(page=1, limit=25)
    artifacts = client.get_audit_log_artifacts(
        page=1,
        limit=5,
        actor_email="owner@example.com",
        action="invite_member",
        resource_type="team_member",
        result="success",
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="hash_123",
        content_hash="content_hash_1",
    )
    filtered_logs = client.get_audit_logs(
        page=2,
        limit=10,
        actor_email="owner@example.com",
        action="invite_member",
        resource_type="team_member",
        result="success",
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="hash_123",
    )
    policy = client.get_execution_policy()
    snapshots = client.list_execution_policy_snapshots()
    updated = client.update_execution_policy(min_confidence=0.85, allow_reexecution=True)

    assert isinstance(me, MeResult)
    assert me.org.slug == "mission-control"
    assert isinstance(team, TeamListResult)
    assert team.total == 1
    assert team.members[0].email == "owner@example.com"
    assert isinstance(invited, TeamInviteResult)
    assert invited.invite_id == "invite_123"
    assert isinstance(role_updated, TeamRoleUpdateResult)
    assert role_updated.user_id == "user_123"
    assert isinstance(removed, TeamRemoveResult)
    assert removed.removed is True
    assert isinstance(billing_info, BillingInfoResult)
    assert billing_info.plan == "enterprise"
    assert isinstance(distributions, DistributionListResult)
    assert distributions.distributions[0].name == "normal"
    assert isinstance(templates, TemplateListResult)
    assert templates.templates[0].id == "product-launch"
    assert isinstance(checkout, BillingSessionResult)
    assert checkout.url.endswith("session_123")
    assert isinstance(portal, BillingSessionResult)
    assert portal.url.endswith("session_123")
    assert isinstance(refreshed, CreditRefreshResult)
    assert refreshed.credits_granted == 10000
    assert refreshed.monthly_remaining == 475000
    assert isinstance(metering, MeteringBatchResult)
    assert metering.accepted == 2
    assert isinstance(devices, DeviceListResult)
    assert devices.device_count == 1
    assert devices.devices[0].device_id == "device_12..."
    assert devices.devices[0].api_key_label == "Primary SDK Key"
    assert isinstance(revoked, DeviceRevokeResult)
    assert revoked.registration_id == "reg_123"
    assert isinstance(logs, AuditLogResult)
    assert logs.entries[0].resource_type == "team_member"
    assert logs.entries[0].metadata["policy_snapshot_id"] == "policy-v1"
    assert isinstance(artifacts, AuditLogResult)
    assert artifacts.entries[0].content_hash == "content_hash_1"
    assert isinstance(filtered_logs, AuditLogResult)
    assert filtered_logs.entries[0].metadata["manifest_version"] == "runtime-manifest-v1"
    assert isinstance(policy, ExecutionPolicyResult)
    assert policy.min_confidence == 0.7
    assert policy.snapshot_id == "execution-policy-v1-r2:abcd1234abcd1234"
    assert isinstance(snapshots, ExecutionPolicySnapshotListResult)
    assert snapshots.total_snapshots == 1
    assert updated.allow_reexecution is True
    assert updated.min_confidence == 0.85
    assert calls == [
        ("PATCH", "/v1/me", {"json": {"name": "Mission Ops", "org_name": "Mission Control"}}),
        ("GET", "/v1/team", {"params": {"page": 1, "limit": 50}}),
        ("POST", "/v1/team/invite", {"json": {"email": "new@example.com", "role": "admin"}}),
        ("PATCH", "/v1/team/user_123/role", {"json": {"role": "viewer"}}),
        ("DELETE", "/v1/team/user_123", {}),
        ("GET", "/v1/billing/info", {}),
        ("GET", "/v1/distributions", {}),
        ("GET", "/v1/templates", {}),
        ("POST", "/v1/billing/checkout", {"json": {"plan": "pro"}}),
        ("POST", "/v1/billing/portal", {"json": {}}),
        (
            "POST",
            "/v1/credits/refresh",
            {
                "json": {
                    "device_id": "device_ops_123",
                    "billing_period": "2026-05",
                    "credits_used": 321,
                }
            },
        ),
        (
            "POST",
            "/v1/metering",
            {
                "json": {
                    "device_id": "device_ops_123",
                    "events": [
                        {"event_type": "query", "latency_ms": 12.5, "success": True},
                        {"module": "pricing", "timestamp": 1_716_547_200.0},
                    ],
                }
            },
        ),
        ("GET", "/v1/device/list", {"params": {"page": 1, "limit": 25}}),
        ("DELETE", "/v1/device/reg_123", {}),
        ("GET", "/v1/audit-logs", {"params": {"page": 1, "limit": 25}}),
        (
            "GET",
            "/v1/audit-logs/artifacts",
            {
                "params": {
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
            },
        ),
        (
            "GET",
            "/v1/audit-logs",
            {
                "params": {
                    "page": 2,
                    "limit": 10,
                    "actor_email": "owner@example.com",
                    "action": "invite_member",
                    "resource_type": "team_member",
                    "result": "success",
                    "policy_snapshot_id": "policy-v1",
                    "schema_snapshot_id": "schema-v1",
                    "manifest_version": "runtime-manifest-v1",
                    "request_hash": "hash_123",
                }
            },
        ),
        ("GET", "/v1/execution/policy", {}),
        ("GET", "/v1/execution/policy/snapshots", {}),
        (
            "PATCH",
            "/v1/execution/policy",
            {"json": {"min_confidence": 0.85, "allow_reexecution": True}},
        ),
    ]


async def test_async_client_control_plane_methods_return_typed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="https://example.test")
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path, kwargs))
        if (method, path) == ("PATCH", "/v1/me"):
            return _me_payload()
        if (method, path) == ("GET", "/v1/team"):
            return _team_list_payload()
        if (method, path) == ("GET", "/v1/billing/info"):
            return _billing_info_payload()
        if (method, path) == ("GET", "/v1/distributions"):
            return _distributions_payload()
        if (method, path) == ("GET", "/v1/templates"):
            return _templates_payload()
        if (method, path) == ("POST", "/v1/metering"):
            return _metering_payload()
        if (method, path) == ("POST", "/v1/team/invite"):
            return {"message": "Invitation sent.", "invite_id": "invite_123"}
        if (method, path) == ("PATCH", "/v1/team/user_123/role"):
            return {"message": "Role updated.", "user_id": "user_123"}
        if (method, path) == ("DELETE", "/v1/team/user_123"):
            return {}
        if (method, path) == ("POST", "/v1/billing/checkout"):
            return {"url": "https://billing.example/checkout/session_123"}
        if (method, path) == ("POST", "/v1/billing/portal"):
            return {"url": "https://billing.example/portal/session_123"}
        if (method, path) == ("POST", "/v1/credits/refresh"):
            return _credit_refresh_payload()
        if (method, path) == ("GET", "/v1/device/list"):
            return _device_list_payload()
        if (method, path) == ("DELETE", "/v1/device/reg_123"):
            return {"revoked": True, "registration_id": "reg_123"}
        if (method, path) == ("GET", "/v1/audit-logs"):
            return _audit_logs_payload()
        if (method, path) == ("GET", "/v1/audit-logs/artifacts"):
            payload = _audit_logs_payload()
            payload["entries"][0]["content_hash"] = "content_hash_1"
            return payload
        if (method, path) == ("GET", "/v1/execution/policy"):
            return _execution_policy_payload()
        if (method, path) == ("GET", "/v1/execution/policy/snapshots"):
            return {"org_id": "org_123", "data": [_execution_policy_payload()], "total_snapshots": 1}
        if (method, path) == ("PATCH", "/v1/execution/policy"):
            return {
                **_execution_policy_payload(),
                "risk_floor": kwargs["json"]["risk_floor"],
                "snapshot_id": "execution-policy-v1-r3:fedcfedcfedcfedc",
                "revision": 3,
            }
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(client, "_request", fake_request)

    me = await client.update_me(org_name="Mission Control")
    team = await client.list_team_members()
    invited = await client.invite_team_member(email="new@example.com")
    role_updated = await client.update_team_member_role("user_123", role="admin")
    removed = await client.remove_team_member("user_123")
    billing_info = await client.get_billing_info()
    distributions = await client.distributions()
    templates = await client.templates()
    checkout = await client.create_billing_checkout()
    portal = await client.create_billing_portal()
    refreshed = await client.refresh_credits(
        device_id="device_async_123",
        billing_period="2026-05",
    )
    metering = await client.ingest_metering_events(
        device_id="device_async_123",
        events=[{"event_type": "sync", "latency_ms": 7.0, "success": True}],
    )
    devices = await client.list_devices(limit=10)
    revoked = await client.revoke_device("reg_123")
    logs = await client.get_audit_logs(limit=10)
    artifacts = await client.get_audit_log_artifacts(
        actor_email="owner@example.com",
        action="invite_member",
        resource_type="team_member",
        result="success",
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="hash_123",
        content_hash="content_hash_1",
    )
    filtered_logs = await client.get_audit_logs(
        actor_email="owner@example.com",
        action="invite_member",
        resource_type="team_member",
        result="success",
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="hash_123",
    )
    policy = await client.get_execution_policy()
    snapshots = await client.list_execution_policy_snapshots()
    updated = await client.update_execution_policy(risk_floor=5000.0)

    assert isinstance(me, MeResult)
    assert me.user.email == "owner@example.com"
    assert isinstance(team, TeamListResult)
    assert team.members[0].role == "owner"
    assert isinstance(invited, TeamInviteResult)
    assert invited.invite_id == "invite_123"
    assert isinstance(role_updated, TeamRoleUpdateResult)
    assert role_updated.user_id == "user_123"
    assert isinstance(removed, TeamRemoveResult)
    assert removed.user_id == "user_123"
    assert isinstance(billing_info, BillingInfoResult)
    assert billing_info.subscription_status == "active"
    assert isinstance(distributions, DistributionListResult)
    assert distributions.distributions[0].required_params == ["mean", "std"]
    assert isinstance(templates, TemplateListResult)
    assert templates.templates[0].category == "business"
    assert isinstance(checkout, BillingSessionResult)
    assert checkout.url.endswith("session_123")
    assert isinstance(portal, BillingSessionResult)
    assert portal.url.endswith("session_123")
    assert isinstance(refreshed, CreditRefreshResult)
    assert refreshed.credits_issued_this_month == 25000
    assert isinstance(metering, MeteringBatchResult)
    assert metering.billing_period == "2026-05"
    assert isinstance(devices, DeviceListResult)
    assert devices.limit == 25
    assert isinstance(revoked, DeviceRevokeResult)
    assert revoked.revoked is True
    assert isinstance(logs, AuditLogResult)
    assert logs.limit == 25
    assert logs.entries[0].metadata["schema_snapshot_id"] == "schema-v1"
    assert isinstance(artifacts, AuditLogResult)
    assert artifacts.entries[0].content_hash == "content_hash_1"
    assert isinstance(filtered_logs, AuditLogResult)
    assert filtered_logs.entries[0].metadata["policy_snapshot_id"] == "policy-v1"
    assert isinstance(policy, ExecutionPolicyResult)
    assert isinstance(snapshots, ExecutionPolicySnapshotListResult)
    assert snapshots.data[0].revision == 2
    assert updated.risk_floor == 5000.0
    assert calls == [
        ("PATCH", "/v1/me", {"json": {"org_name": "Mission Control"}}),
        ("GET", "/v1/team", {"params": None}),
        ("POST", "/v1/team/invite", {"json": {"email": "new@example.com", "role": "member"}}),
        ("PATCH", "/v1/team/user_123/role", {"json": {"role": "admin"}}),
        ("DELETE", "/v1/team/user_123", {}),
        ("GET", "/v1/billing/info", {}),
        ("GET", "/v1/distributions", {}),
        ("GET", "/v1/templates", {}),
        ("POST", "/v1/billing/checkout", {"json": {}}),
        ("POST", "/v1/billing/portal", {"json": {}}),
        (
            "POST",
            "/v1/credits/refresh",
            {
                "json": {
                    "device_id": "device_async_123",
                    "billing_period": "2026-05",
                    "credits_used": 0,
                }
            },
        ),
        (
            "POST",
            "/v1/metering",
            {
                "json": {
                    "device_id": "device_async_123",
                    "events": [{"event_type": "sync", "latency_ms": 7.0, "success": True}],
                }
            },
        ),
        ("GET", "/v1/device/list", {"params": {"limit": 10}}),
        ("DELETE", "/v1/device/reg_123", {}),
        ("GET", "/v1/audit-logs", {"params": {"page": 1, "limit": 10}}),
        (
            "GET",
            "/v1/audit-logs/artifacts",
            {
                "params": {
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
                    "content_hash": "content_hash_1",
                }
            },
        ),
        (
            "GET",
            "/v1/audit-logs",
            {
                "params": {
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
            },
        ),
        ("GET", "/v1/execution/policy", {}),
        ("GET", "/v1/execution/policy/snapshots", {}),
        ("PATCH", "/v1/execution/policy", {"json": {"risk_floor": 5000.0}}),
    ]


def test_control_plane_validation_fails_closed() -> None:
    client = DecisionEngineClient(api_key="de_test_sync", base_url="https://example.test")

    with pytest.raises(ValueError):
        client.list_team_members(page=0)
    with pytest.raises(ValueError):
        client.invite_team_member(email="not-an-email")
    with pytest.raises(ValueError):
        client.update_me()
    with pytest.raises(ValueError):
        client.update_team_member_role("user_123", role="superadmin")
    with pytest.raises(ValueError):
        client.remove_team_member("")
    with pytest.raises(ValueError):
        client.create_billing_checkout(plan="enterprise")
    with pytest.raises(ValueError):
        client.refresh_credits(device_id="", billing_period="2026-05")
    with pytest.raises(ValueError):
        client.refresh_credits(device_id="device_123", billing_period="202605")
    with pytest.raises(ValueError):
        client.refresh_credits(device_id="device_123", billing_period="2026-13")
    with pytest.raises(TypeError):
        client.refresh_credits(  # type: ignore[arg-type]
            device_id="device_123",
            billing_period="2026-05",
            credits_used=1.5,
        )
    with pytest.raises(ValueError):
        client.ingest_metering_events(device_id="", events=[{}])
    with pytest.raises(ValueError):
        client.ingest_metering_events(device_id="device_123", events=[])
    with pytest.raises(ValueError):
        client.ingest_metering_events(
            device_id="device_123",
            events=[{"event_type": "query", "unexpected": True}],
        )
    with pytest.raises(ValueError):
        client.list_devices(limit=0)
    with pytest.raises(ValueError):
        client.revoke_device("")
    with pytest.raises(ValueError):
        client.get_audit_logs(limit=0)
    with pytest.raises(ValueError):
        client.get_audit_logs(actor_email="   ")
    with pytest.raises(ValueError):
        client.get_audit_log_artifacts(content_hash="   ")
    with pytest.raises(ValueError):
        client.update_execution_policy()
    with pytest.raises(TypeError):
        client.update_execution_policy(require_calibration="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        client.update_execution_policy(min_confidence=1.1)


async def test_async_control_plane_validation_fails_closed() -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="https://example.test")

    with pytest.raises(ValueError):
        await client.list_team_members(page=0)
    with pytest.raises(ValueError):
        await client.invite_team_member(email="not-an-email")
    with pytest.raises(ValueError):
        await client.update_me()
    with pytest.raises(ValueError):
        await client.update_team_member_role("user_123", role="superadmin")
    with pytest.raises(ValueError):
        await client.remove_team_member("")
    with pytest.raises(ValueError):
        await client.create_billing_checkout(plan="enterprise")
    with pytest.raises(ValueError):
        await client.refresh_credits(device_id="", billing_period="2026-05")
    with pytest.raises(ValueError):
        await client.refresh_credits(device_id="device_123", billing_period="202605")
    with pytest.raises(ValueError):
        await client.refresh_credits(device_id="device_123", billing_period="2026-13")
    with pytest.raises(TypeError):
        await client.refresh_credits(  # type: ignore[arg-type]
            device_id="device_123",
            billing_period="2026-05",
            credits_used=1.5,
        )
    with pytest.raises(ValueError):
        await client.ingest_metering_events(device_id="", events=[{}])
    with pytest.raises(ValueError):
        await client.ingest_metering_events(device_id="device_123", events=[])
    with pytest.raises(ValueError):
        await client.ingest_metering_events(
            device_id="device_123",
            events=[{"event_type": "query", "unexpected": True}],
        )
    with pytest.raises(ValueError):
        await client.list_devices(limit=0)
    with pytest.raises(ValueError):
        await client.revoke_device("")
    with pytest.raises(ValueError):
        await client.get_audit_logs(limit=0)
    with pytest.raises(ValueError):
        await client.get_audit_logs(actor_email="   ")
    with pytest.raises(ValueError):
        await client.get_audit_log_artifacts(content_hash="   ")
    with pytest.raises(ValueError):
        await client.update_execution_policy()
    with pytest.raises(TypeError):
        await client.update_execution_policy(require_calibration="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await client.update_execution_policy(min_confidence=1.1)
