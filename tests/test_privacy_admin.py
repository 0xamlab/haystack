from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org
from tests._asgi_client import SyncASGIClient


def _fake_auth() -> dict[str, object]:
    return {"org_id": uuid.uuid4(), "key_id": uuid.uuid4(), "plan": "enterprise"}


def test_admin_egress_policy_endpoint_returns_effective_policy() -> None:
    payload = {
        "deployment_mode": "self_hosted",
        "disable_cloud": True,
        "disable_telemetry": True,
        "telemetry_mode": "local_audit",
        "metering_mode": "local_audit",
        "require_local_license": False,
        "control_plane_url": "",
        "allow_outbound_network": False,
        "egress_allowlist": [],
        "algenta_owned_hosts": ["api.codna.ai"],
        "algenta_owned_suffixes": [".codna.ai"],
        "vendor_telemetry_hosts": ["sentry.io"],
        "private_host_suffixes": [".internal", ".localhost"],
        "privacy_registry": {
            "algenta_owned_hosts": ["api.codna.ai"],
            "algenta_owned_suffixes": [".codna.ai"],
            "vendor_telemetry_hosts": ["sentry.io"],
            "private_host_suffixes": [".internal", ".localhost"],
        },
        "algenta_cloud_enabled": False,
        "vendor_telemetry_enabled": False,
        "customer_connector_egress_enabled": False,
        "undeclared_public_egress_allowed": False,
        "mandatory_heartbeat_enabled": False,
        "metering_flush_enabled": False,
        "algenta_owned_host_patterns": ["api.codna.ai"],
        "vpc_mode_note": "vpc remains managed.",
    }
    app.dependency_overrides[get_current_org] = _fake_auth
    try:
        with (
            patch("apps.api_server.routers.meta.get_egress_policy_payload", new=AsyncMock(return_value=payload)),
            SyncASGIClient(app) as client,
        ):
            response = client.get("/v1/admin/egress-policy")
        assert response.status_code == 200
        body = response.json()
        assert body["deployment_mode"] == "self_hosted"
        assert body["algenta_cloud_enabled"] is False
        assert body["privacy_registry"]["algenta_owned_suffixes"] == [".codna.ai"]
        assert body["vendor_telemetry_hosts"] == ["sentry.io"]
    finally:
        app.dependency_overrides.clear()


def test_admin_egress_log_endpoint_returns_paginated_entries() -> None:
    auth = _fake_auth()
    payload = {
        "entries": [
            {
                "surface": "deployment_router",
                "egress_class": "operator_service",
                "destination_host_hash": "abc123",
                "destination_host_redacted": "internal-host",
                "decision": "allow",
                "reason": "destination_allowlisted",
                "timestamp": "2026-05-24T12:00:00Z",
                "deployment_mode": "self_hosted",
                "service_name": "api-server",
                "request_id": "req_123",
            }
        ],
        "total": 3,
        "page": 2,
        "limit": 1,
        "pages": 3,
    }
    app.dependency_overrides[get_current_org] = lambda: auth
    try:
        with (
            patch("apps.api_server.routers.meta.list_egress_events", new=AsyncMock(return_value=payload)),
            SyncASGIClient(app) as client,
        ):
            response = client.get("/v1/admin/egress-log?page=2&limit=1")
        assert response.status_code == 200
        body = response.json()
        assert body["page"] == 2
        assert body["limit"] == 1
        assert body["entries"][0]["decision"] == "allow"
    finally:
        app.dependency_overrides.clear()


def test_admin_privacy_report_endpoint_returns_buyer_facing_fields() -> None:
    auth = _fake_auth()
    payload = {
        "deployment_mode": "air_gapped",
        "algenta_cloud_enabled": False,
        "vendor_telemetry_enabled": False,
        "customer_connector_egress_enabled": True,
        "undeclared_public_egress_allowed": False,
        "local_license_required": True,
        "local_license_active": True,
        "mandatory_heartbeat_enabled": False,
        "metering_flush_enabled": False,
        "telemetry_mode": "local_audit",
        "metering_mode": "local_audit",
        "algenta_owned_egress_count_24h": 0,
        "blocked_egress_attempt_count_24h": 2,
        "last_outbound_request_at": "2026-05-24T12:00:00Z",
        "last_algenta_owned_egress_at": None,
    }
    app.dependency_overrides[get_current_org] = lambda: auth
    try:
        with (
            patch("apps.api_server.routers.meta.get_privacy_report", new=AsyncMock(return_value=payload)),
            SyncASGIClient(app) as client,
        ):
            response = client.get("/v1/admin/privacy-report")
        assert response.status_code == 200
        body = response.json()
        assert body["deployment_mode"] == "air_gapped"
        assert body["local_license_active"] is True
        assert body["blocked_egress_attempt_count_24h"] == 2
    finally:
        app.dependency_overrides.clear()
