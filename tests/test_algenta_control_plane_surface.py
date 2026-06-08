from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")

AlgentaClient = algenta.AlgentaClient
AuditLogOutput = algenta.AuditLogOutput
BillingInfoOutput = algenta.BillingInfoOutput
BillingSessionOutput = algenta.BillingSessionOutput
CreditRefreshOutput = algenta.CreditRefreshOutput
MeteringBatchOutput = algenta.MeteringBatchOutput
JobListOutput = algenta.JobListOutput
JobStatusOutput = algenta.JobStatusOutput
JobSubmitOutput = algenta.JobSubmitOutput
WebhookTestOutput = algenta.WebhookTestOutput
DeviceListOutput = algenta.DeviceListOutput
DeviceRevokeOutput = algenta.DeviceRevokeOutput
DistributionListOutput = algenta.DistributionListOutput
ExecutionPolicyOutput = algenta.ExecutionPolicyOutput
ExecutionPolicySnapshotListOutput = algenta.ExecutionPolicySnapshotListOutput
Runtime = algenta.Runtime
RuntimeValidationError = algenta.RuntimeValidationError
TeamInviteOutput = algenta.TeamInviteOutput
TeamListOutput = algenta.TeamListOutput
TeamRemoveOutput = algenta.TeamRemoveOutput
TeamRoleUpdateOutput = algenta.TeamRoleUpdateOutput
TemplateListOutput = algenta.TemplateListOutput


def _team_payload() -> list[dict[str, object]]:
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


def _audit_payload() -> dict[str, object]:
    return {
        "entries": [
            {
                "id": "audit_123",
                "timestamp": "2026-05-24T12:00:00Z",
                "actor_email": "owner@example.com",
                "action": "policy_update",
                "resource_type": "execution_policy",
                "resource_id": "org_123",
                "ip_address": "203.0.113.10",
                "result": "success",
                "content_hash": None,
                "metadata": {
                    "policy_snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
                    "schema_snapshot_id": "schema-v1",
                    "manifest_version": "runtime-manifest-v1",
                    "request_hash": "hash_123",
                },
            }
        ],
        "total": 1,
        "page": 1,
        "limit": 25,
        "pages": 1,
    }


def _device_payload() -> dict[str, object]:
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


def _policy_payload() -> dict[str, object]:
    return {
        "org_id": "org_123",
        "min_confidence": 0.75,
        "risk_floor": 9000.0,
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
        "accepted": 3,
        "billing_period": "2026-05",
    }


def _credit_refresh_payload() -> dict[str, object]:
    return {
        "credits_granted": 10000,
        "credits_issued_this_month": 40000,
        "monthly_limit": 500000,
        "monthly_remaining": 460000,
        "billing_period": "2026-05",
        "expires_at": 1_716_547_200.0,
        "refresh_after": 1_716_545_040.0,
        "server_time": 1_716_460_800.0,
    }


def _job_submit_payload() -> dict[str, object]:
    return {
        "job_id": "11111111-1111-1111-1111-111111111111",
        "run_id": "22222222-2222-2222-2222-222222222222",
        "status": "queued",
        "poll_url": "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
        "message": "Job submitted.",
    }


def _job_status_payload() -> dict[str, object]:
    return {
        "job_id": "11111111-1111-1111-1111-111111111111",
        "run_id": "22222222-2222-2222-2222-222222222222",
        "org_id": "33333333-3333-3333-3333-333333333333",
        "status": "queued",
        "queue_name": "default",
        "retry_count": 0,
        "callback_url": "https://example.com/hook",
        "callback_status": "pending",
        "error_message": None,
        "created_at": "2026-05-24T12:00:00Z",
        "started_at": None,
        "completed_at": None,
        "ttl_expires_at": "2026-05-25T12:00:00Z",
        "poll_url": "http://localhost:8000/v1/jobs/11111111-1111-1111-1111-111111111111",
    }


def _job_list_payload() -> dict[str, object]:
    return {
        "jobs": [_job_status_payload()],
        "total": 1,
        "page": 1,
        "limit": 25,
        "pages": 1,
    }


def _job_result_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "recommended_action": "proceed",
        "confidence": 0.84,
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


class _FakeDecisionEngineClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(self, call_name: str, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append((call_name, args, kwargs))
        return {"name": call_name, "args": list(args), "kwargs": kwargs}

    def list_team_members(self, *, page=None, limit=None):
        return self._record("list_team_members", page=page, limit=limit)

    def update_me(self, *, name=None, org_name=None):
        return self._record("update_me", name=name, org_name=org_name)

    def invite_team_member(self, *, email=None, role="member"):
        return self._record("invite_team_member", email=email, role=role)

    def update_team_member_role(self, user_id, *, role):
        return self._record("update_team_member_role", user_id, role=role)

    def remove_team_member(self, user_id):
        return self._record("remove_team_member", user_id)

    def get_billing_info(self):
        return self._record("get_billing_info")

    def distributions(self):
        return self._record("distributions")

    def templates(self):
        return self._record("templates")

    def create_billing_checkout(self, *, plan=None):
        return self._record("create_billing_checkout", plan=plan)

    def create_billing_portal(self):
        return self._record("create_billing_portal")

    def refresh_credits(self, *, device_id=None, billing_period=None, credits_used=0):
        return self._record(
            "refresh_credits",
            device_id=device_id,
            billing_period=billing_period,
            credits_used=credits_used,
        )

    def ingest_metering_events(self, *, device_id=None, events=None):
        return self._record("ingest_metering_events", device_id=device_id, events=events)

    def list_devices(self, *, page=None, limit=None):
        return self._record("list_devices", page=page, limit=limit)

    def revoke_device(self, registration_id):
        return self._record("revoke_device", registration_id)

    def get_audit_logs(self, **kwargs):
        return self._record("get_audit_logs", **kwargs)

    def get_audit_log_artifacts(self, **kwargs):
        return self._record("get_audit_log_artifacts", **kwargs)

    def get_execution_policy(self):
        return self._record("get_execution_policy")

    def list_execution_policy_snapshots(self):
        return self._record("list_execution_policy_snapshots")

    def update_execution_policy(self, **kwargs):
        return self._record("update_execution_policy", **kwargs)

    def submit_job(self, request=None, callback_url=None, **kwargs):
        return self._record("submit_job", request, callback_url=callback_url, **kwargs)

    def get_job(self, job_id):
        return self._record("get_job", job_id)

    def get_job_result(self, job_id):
        return self._record("get_job_result", job_id)

    def list_jobs(self, *, page=1, limit=25, status=None):
        return self._record("list_jobs", page=page, limit=limit, status=status)

    def cancel_job(self, job_id):
        return self._record("cancel_job", job_id)

    def test_webhook_delivery(self, callback_url):
        return self._record("test_webhook_delivery", callback_url)

    def poll_job(self, job_id, *, timeout=300.0, poll_interval=2.0):
        return self._record(
            "poll_job",
            job_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )


class _ModelLike:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def model_dump(self) -> dict[str, object]:
        return dict(self.payload)


class _PlainDataDecisionEngineClient(_FakeDecisionEngineClient):
    def me(self):
        return _ModelLike({"user": {"id": "user_123"}, "org": {"id": "org_123"}})

    def update_me(self, *, name=None, org_name=None):
        return _ModelLike({"user": {"name": name}, "org": {"name": org_name}})

    def limits(self):
        return _ModelLike({"max_simulations_per_month": 5000, "jobs_enabled": True})

    def create_api_key(self, label=None, *, name=None, expires_at=None, device_limit=None):
        return _ModelLike(
            {
                "id": "key_123",
                "label": name or label,
                "key_prefix": "de_live_",
                "raw_key": "de_live_secret",
                "device_limit": device_limit,
            }
        )

    def revoke_api_key(self, key_id):
        return _ModelLike({})


class _FakeRuntimeApiClient:
    def me(self):
        return {
            "user": {
                "id": "user_123",
                "email": "owner@example.com",
                "name": "Mission Ops",
                "role": "owner",
                "email_verified": True,
                "created_at": "2026-05-24T11:00:00Z",
            },
            "org": {
                "id": "org_123",
                "name": "Mission Control",
                "slug": "mission-control",
                "plan": "enterprise",
                "status": "active",
                "created_at": "2026-05-24T10:00:00Z",
            },
        }

    def list_team_members(self, *, page=None, limit=None):
        assert page == 1
        assert limit == 50
        return _team_payload()

    def update_me(self, *, name=None, org_name=None):
        assert name == "Mission Ops"
        assert org_name == "Mission Control"
        return {
            "user": {
                "id": "user_123",
                "email": "owner@example.com",
                "name": "Mission Ops",
                "role": "owner",
                "email_verified": True,
                "created_at": "2026-05-24T11:00:00Z",
            },
            "org": {
                "id": "org_123",
                "name": "Mission Control",
                "slug": "mission-control",
                "plan": "enterprise",
                "status": "active",
                "created_at": "2026-05-24T10:00:00Z",
            },
        }

    def invite_team_member(self, *, email=None, role="member"):
        assert email == "new@example.com"
        assert role == "admin"
        return {"message": "Invitation sent.", "invite_id": "invite_123"}

    def update_team_member_role(self, user_id, *, role):
        assert user_id == "user_123"
        assert role == "viewer"
        return {"message": "Role updated.", "user_id": user_id}

    def remove_team_member(self, user_id):
        assert user_id == "user_123"
        return {}

    def get_billing_info(self):
        return _billing_info_payload()

    def distributions(self):
        return _distributions_payload()

    def templates(self):
        return _templates_payload()

    def create_billing_checkout(self, *, plan=None):
        assert plan == "pro"
        return {"url": "https://billing.example/checkout/session_123"}

    def create_billing_portal(self):
        return {"url": "https://billing.example/portal/session_123"}

    def refresh_credits(self, *, device_id=None, billing_period=None, credits_used=0):
        assert device_id == "device_runtime_123"
        assert billing_period == "2026-05"
        assert credits_used == 21
        return _credit_refresh_payload()

    def ingest_metering_events(self, *, device_id=None, events=None):
        assert device_id == "device_runtime_123"
        assert events == [{"event_type": "query", "latency_ms": 4.0, "success": True}]
        return _metering_payload()

    def list_devices(self, *, page=None, limit=None):
        assert page == 1
        assert limit == 25
        return _device_payload()

    def revoke_device(self, registration_id):
        assert registration_id == "reg_123"
        return {"revoked": True, "registration_id": registration_id}

    def get_audit_logs(
        self,
        *,
        page=1,
        limit=25,
        actor_email=None,
        action=None,
        resource_type=None,
        result=None,
        policy_snapshot_id=None,
        schema_snapshot_id=None,
        manifest_version=None,
        request_hash=None,
    ):
        assert page == 1
        assert limit == 20
        assert actor_email == "owner@example.com"
        assert action == "policy_update"
        assert resource_type == "execution_policy"
        assert result == "success"
        assert policy_snapshot_id == "execution-policy-v1-r2:abcd1234abcd1234"
        assert schema_snapshot_id == "schema-v1"
        assert manifest_version == "runtime-manifest-v1"
        assert request_hash == "hash_123"
        return _audit_payload()

    def get_audit_log_artifacts(
        self,
        *,
        page=1,
        limit=25,
        actor_email=None,
        action=None,
        resource_type=None,
        result=None,
        policy_snapshot_id=None,
        schema_snapshot_id=None,
        manifest_version=None,
        request_hash=None,
        content_hash=None,
    ):
        assert page == 1
        assert limit == 5
        assert actor_email == "owner@example.com"
        assert action == "policy_update"
        assert resource_type == "execution_policy"
        assert result == "success"
        assert policy_snapshot_id == "execution-policy-v1-r2:abcd1234abcd1234"
        assert schema_snapshot_id == "schema-v1"
        assert manifest_version == "runtime-manifest-v1"
        assert request_hash == "hash_123"
        assert content_hash == "content_hash_1"
        payload = _audit_payload()
        payload["entries"][0]["content_hash"] = "content_hash_1"
        return payload

    def get_execution_policy(self):
        return _policy_payload()

    def list_execution_policy_snapshots(self):
        return {"org_id": "org_123", "data": [_policy_payload()], "total_snapshots": 1}

    def update_execution_policy(self, **kwargs):
        return {**_policy_payload(), **{k: v for k, v in kwargs.items() if v is not None}}

    def submit_job(self, request=None, callback_url=None, **kwargs):
        assert request == {"mode": "auto", "scenario": {"variables": {"x": {"low": 1, "high": 2}}}}
        assert callback_url == "https://example.com/hook"
        assert kwargs == {}
        return _job_submit_payload()

    def get_job(self, job_id):
        assert job_id == "job_123"
        return _job_status_payload()

    def get_job_result(self, job_id):
        assert job_id == "job_123"
        return _job_result_payload()

    def list_jobs(self, *, page=1, limit=25, status=None):
        assert page == 1
        assert limit == 25
        assert status == "queued"
        return _job_list_payload()

    def cancel_job(self, job_id):
        assert job_id == "job_123"
        return {**_job_status_payload(), "status": "cancelled"}

    def test_webhook_delivery(self, callback_url):
        assert callback_url == "https://example.com/webhook"
        return {"success": True, "status_code": 200, "message": "delivered"}

    def poll_job(self, job_id, *, timeout=300.0, poll_interval=2.0):
        assert job_id == "job_123"
        assert timeout == 30.0
        assert poll_interval == 0.5
        return _job_result_payload()


def test_algenta_client_control_plane_methods_delegate_to_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = type("FakeDecisionEngineModule", (), {"DecisionEngineClient": _FakeDecisionEngineClient})
    client_module = importlib.import_module("algenta.client")
    monkeypatch.setattr(client_module, "import_module", lambda name: fake_module)

    client = AlgentaClient(api_key="de_test", base_url="http://localhost:8000")

    assert client.update_me(name="Mission Ops", org_name="Mission Control")["name"] == "update_me"
    assert client.list_team_members(page=2, limit=25)["name"] == "list_team_members"
    assert client.invite_team_member(email="new@example.com", role="admin")["name"] == "invite_team_member"
    assert client.update_team_member_role("user_123", role="viewer")["name"] == "update_team_member_role"
    assert client.remove_team_member("user_123")["name"] == "remove_team_member"
    assert client.get_billing_info()["name"] == "get_billing_info"
    assert client.distributions()["name"] == "distributions"
    assert client.templates()["name"] == "templates"
    assert client.create_billing_checkout(plan="pro")["name"] == "create_billing_checkout"
    assert client.create_billing_portal()["name"] == "create_billing_portal"
    assert (
        client.refresh_credits(
            device_id="device_cloud_123",
            billing_period="2026-05",
            credits_used=11,
        )["name"]
        == "refresh_credits"
    )
    assert (
        client.ingest_metering_events(
            device_id="device_cloud_123",
            events=[{"event_type": "query", "latency_ms": 4.0, "success": True}],
        )["name"]
        == "ingest_metering_events"
    )
    assert client.list_devices(page=1, limit=25)["name"] == "list_devices"
    assert client.revoke_device("reg_123")["name"] == "revoke_device"
    assert (
        client.get_audit_logs(
            limit=50,
            action="policy_update",
            policy_snapshot_id="execution-policy-v1-r2:abcd1234abcd1234",
        )["name"]
        == "get_audit_logs"
    )
    assert (
        client.get_audit_log_artifacts(
            limit=5,
            action="policy_update",
            policy_snapshot_id="execution-policy-v1-r2:abcd1234abcd1234",
            content_hash="content_hash_1",
        )["name"]
        == "get_audit_log_artifacts"
    )
    assert client.get_execution_policy()["name"] == "get_execution_policy"
    assert client.list_execution_policy_snapshots()["name"] == "list_execution_policy_snapshots"
    assert (
        client.update_execution_policy(min_confidence=0.8, allow_reexecution=True)["name"]
        == "update_execution_policy"
    )
    assert client.submit_job({"mode": "auto"}, callback_url="https://example.com/hook")["name"] == "submit_job"
    assert client.get_job("job_123")["name"] == "get_job"
    assert client.get_job_result("job_123")["name"] == "get_job_result"
    assert client.list_jobs(page=2, limit=10, status="queued")["name"] == "list_jobs"
    assert client.cancel_job("job_123")["name"] == "cancel_job"
    assert client.test_webhook_delivery("https://example.com/webhook")["name"] == "test_webhook_delivery"
    assert client.poll_job("job_123", timeout=30.0, poll_interval=0.5)["name"] == "poll_job"

    sdk_client = client._sdk_client()
    assert sdk_client.calls == [
        ("update_me", (), {"name": "Mission Ops", "org_name": "Mission Control"}),
        ("list_team_members", (), {"page": 2, "limit": 25}),
        ("invite_team_member", (), {"email": "new@example.com", "role": "admin"}),
        ("update_team_member_role", ("user_123",), {"role": "viewer"}),
        ("remove_team_member", ("user_123",), {}),
        ("get_billing_info", (), {}),
        ("distributions", (), {}),
        ("templates", (), {}),
        ("create_billing_checkout", (), {"plan": "pro"}),
        ("create_billing_portal", (), {}),
        (
            "refresh_credits",
            (),
            {
                "device_id": "device_cloud_123",
                "billing_period": "2026-05",
                "credits_used": 11,
            },
        ),
        (
            "ingest_metering_events",
            (),
            {
                "device_id": "device_cloud_123",
                "events": [{"event_type": "query", "latency_ms": 4.0, "success": True}],
            },
        ),
        ("list_devices", (), {"page": 1, "limit": 25}),
        ("revoke_device", ("reg_123",), {}),
        (
            "get_audit_logs",
            (),
            {
                "page": 1,
                "limit": 50,
                "actor_email": None,
                "action": "policy_update",
                "resource_type": None,
                "result": None,
                "policy_snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
                "schema_snapshot_id": None,
                "manifest_version": None,
                "request_hash": None,
            },
        ),
        (
            "get_audit_log_artifacts",
            (),
            {
                "page": 1,
                "limit": 5,
                "actor_email": None,
                "action": "policy_update",
                "resource_type": None,
                "result": None,
                "policy_snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
                "schema_snapshot_id": None,
                "manifest_version": None,
                "request_hash": None,
                "content_hash": "content_hash_1",
            },
        ),
        ("get_execution_policy", (), {}),
        ("list_execution_policy_snapshots", (), {}),
        (
            "update_execution_policy",
            (),
            {"min_confidence": 0.8, "risk_floor": None, "require_calibration": None, "allow_reexecution": True},
        ),
        ("submit_job", ({"mode": "auto"},), {"callback_url": "https://example.com/hook"}),
        ("get_job", ("job_123",), {}),
        ("get_job_result", ("job_123",), {}),
        ("list_jobs", (), {"page": 2, "limit": 10, "status": "queued"}),
        ("cancel_job", ("job_123",), {}),
        ("test_webhook_delivery", ("https://example.com/webhook",), {}),
        ("poll_job", ("job_123",), {"timeout": 30.0, "poll_interval": 0.5}),
    ]


def test_algenta_client_account_bridge_converts_sdk_models_to_plain_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = type("FakeDecisionEngineModule", (), {"DecisionEngineClient": _PlainDataDecisionEngineClient})
    client_module = importlib.import_module("algenta.client")
    monkeypatch.setattr(client_module, "import_module", lambda name: fake_module)

    client = AlgentaClient(api_key="de_test", base_url="http://localhost:8000")

    assert client.me() == {"user": {"id": "user_123"}, "org": {"id": "org_123"}}
    assert client.update_me(name="Mission Ops", org_name="Mission Control") == {
        "user": {"name": "Mission Ops"},
        "org": {"name": "Mission Control"},
    }
    assert client.limits() == {"max_simulations_per_month": 5000, "jobs_enabled": True}
    assert client.create_api_key(name="ops-key", device_limit=2) == {
        "id": "key_123",
        "label": "ops-key",
        "key_prefix": "de_live_",
        "raw_key": "de_live_secret",
        "device_limit": 2,
    }
    assert client.revoke_api_key("key_123") == {}


def test_algenta_runtime_control_plane_methods_return_typed_outputs() -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")
    runtime._api_client = _FakeRuntimeApiClient()

    current = runtime.me()
    me = runtime.update_me(name="Mission Ops", org_name="Mission Control")
    team = runtime.list_team_members(page=1, limit=50)
    invited = runtime.invite_team_member(email="new@example.com", role="admin")
    role_updated = runtime.update_team_member_role("user_123", role="viewer")
    removed = runtime.remove_team_member("user_123")
    billing_info = runtime.get_billing_info()
    distributions = runtime.distributions()
    templates = runtime.templates()
    checkout = runtime.create_billing_checkout(plan="pro")
    portal = runtime.create_billing_portal()
    refreshed = runtime.refresh_credits(
        device_id="device_runtime_123",
        billing_period="2026-05",
        credits_used=21,
    )
    metering = runtime.ingest_metering_events(
        device_id="device_runtime_123",
        events=[{"event_type": "query", "latency_ms": 4.0, "success": True}],
    )
    devices = runtime.list_devices(page=1, limit=25)
    revoked = runtime.revoke_device("reg_123")
    logs = runtime.get_audit_logs(
        limit=20,
        actor_email="owner@example.com",
        action="policy_update",
        resource_type="execution_policy",
        result="success",
        policy_snapshot_id="execution-policy-v1-r2:abcd1234abcd1234",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="hash_123",
    )
    artifacts = runtime.get_audit_log_artifacts(
        limit=5,
        actor_email="owner@example.com",
        action="policy_update",
        resource_type="execution_policy",
        result="success",
        policy_snapshot_id="execution-policy-v1-r2:abcd1234abcd1234",
        schema_snapshot_id="schema-v1",
        manifest_version="runtime-manifest-v1",
        request_hash="hash_123",
        content_hash="content_hash_1",
    )
    policy = runtime.get_execution_policy()
    snapshots = runtime.list_execution_policy_snapshots()
    updated = runtime.update_execution_policy(min_confidence=0.9, allow_reexecution=True)

    assert isinstance(current, dict)
    assert current["org"]["name"] == "Mission Control"
    assert isinstance(me, dict)
    assert me["user"]["name"] == "Mission Ops"
    assert me["org"]["name"] == "Mission Control"
    assert isinstance(team, TeamListOutput)
    assert team.members[0].email == "owner@example.com"
    assert isinstance(invited, TeamInviteOutput)
    assert invited.invite_id == "invite_123"
    assert isinstance(role_updated, TeamRoleUpdateOutput)
    assert role_updated.user_id == "user_123"
    assert isinstance(removed, TeamRemoveOutput)
    assert removed.removed is True
    assert isinstance(billing_info, BillingInfoOutput)
    assert billing_info.plan == "enterprise"
    assert isinstance(distributions, DistributionListOutput)
    assert distributions.distributions[0].name == "normal"
    assert isinstance(templates, TemplateListOutput)
    assert templates.templates[0].id == "product-launch"
    assert isinstance(checkout, BillingSessionOutput)
    assert checkout.url.endswith("session_123")
    assert isinstance(portal, BillingSessionOutput)
    assert portal.url.endswith("session_123")
    assert isinstance(refreshed, CreditRefreshOutput)
    assert refreshed.credits_granted == 10000
    assert isinstance(metering, MeteringBatchOutput)
    assert metering.accepted == 3
    assert isinstance(devices, DeviceListOutput)
    assert devices.device_count == 1
    assert devices.devices[0].device_id == "device_12..."
    assert devices.devices[0].api_key_prefix == "de_live_"
    assert isinstance(revoked, DeviceRevokeOutput)
    assert revoked.registration_id == "reg_123"
    assert isinstance(logs, AuditLogOutput)
    assert logs.entries[0].resource_type == "execution_policy"
    assert logs.entries[0].metadata["policy_snapshot_id"] == "execution-policy-v1-r2:abcd1234abcd1234"
    assert isinstance(artifacts, AuditLogOutput)
    assert artifacts.entries[0].content_hash == "content_hash_1"
    assert isinstance(policy, ExecutionPolicyOutput)
    assert policy.min_confidence == 0.75
    assert isinstance(snapshots, ExecutionPolicySnapshotListOutput)
    assert snapshots.total_snapshots == 1
    assert updated.min_confidence == 0.9
    assert updated.allow_reexecution is True


def test_algenta_runtime_job_methods_return_typed_outputs() -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")
    runtime._api_client = _FakeRuntimeApiClient()

    submitted = runtime.submit_job(
        {"mode": "auto", "scenario": {"variables": {"x": {"low": 1, "high": 2}}}},
        callback_url="https://example.com/hook",
    )
    status = runtime.get_job("job_123")
    result = runtime.get_job_result("job_123")
    listed = runtime.list_jobs(status="queued")
    cancelled = runtime.cancel_job("job_123")
    webhook = runtime.test_webhook_delivery("https://example.com/webhook")
    polled = runtime.poll_job("job_123", timeout=30.0, poll_interval=0.5)

    assert isinstance(submitted, JobSubmitOutput)
    assert submitted.status == "queued"
    assert submitted.poll_url.endswith(submitted.job_id)
    assert isinstance(status, JobStatusOutput)
    assert status.queue_name == "default"
    assert status.callback_status == "pending"
    assert result["recommended_action"] == "proceed"
    assert isinstance(listed, JobListOutput)
    assert listed.total == 1
    assert listed.jobs[0].job_id == status.job_id
    assert isinstance(cancelled, JobStatusOutput)
    assert cancelled.status == "cancelled"
    assert isinstance(webhook, WebhookTestOutput)
    assert webhook.status_code == 200
    assert polled["status"] == "completed"


def test_algenta_runtime_control_plane_fails_closed_on_invalid_payload() -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")

    class _BrokenClient:
        def get_execution_policy(self):
            return {"org_id": "org_123", "min_confidence": "high"}

    runtime._api_client = _BrokenClient()

    with pytest.raises(RuntimeValidationError) as exc_info:
        runtime.get_execution_policy()
    assert exc_info.value.code == "invalid_runtime_api_payload"


def test_algenta_runtime_job_methods_fail_closed_on_invalid_payload() -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")

    class _BrokenClient:
        def get_job(self, job_id):
            return {"job_id": "job_123", "status": "queued"}

    runtime._api_client = _BrokenClient()

    with pytest.raises(RuntimeValidationError) as exc_info:
        runtime.get_job("job_123")
    assert exc_info.value.code == "invalid_runtime_api_payload"
