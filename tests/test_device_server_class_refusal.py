"""Server-class deployment refusal — a machine reporting a hypervisor or container
runtime must NOT register under a desktop-class license (entitlement
deployment_class='desktop'); it is refused with an upgrade-to-Server pointer.
Server-class plans keep accepting them; legacy clients (no signals) are unaffected."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


def _payload(**signals: object) -> dict[str, object]:
    return {
        "device": {
            "device_id": "server-class-test-device-0001",
            "platform": "linux",
            "platform_version": "6.8",
            "hostname_hash": "deadbeef" * 8,
            "sdk_version": "algenta-live/1.0.0",
            **signals,
        }
    }


@pytest.mark.anyio
async def test_desktop_plan_refuses_container_and_vm(client, app) -> None:
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    # algenta_pro's entitlement is deployment_class='desktop'.
    key, _ = await _seed_api_key(  # noqa: F405
        label="Desktop Plan Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ALGENTA_PRO,  # noqa: F405
    )

    container = await client.post(
        "/v1/device/register", headers={"X-API-Key": key}, json=_payload(container=True)
    )
    assert container.status_code == 402
    body = container.json()
    detail = body.get("detail", body)
    assert (detail.get("error") or detail.get("detail", {}).get("error")) in (
        "server_deployment_requires_server_license",
        detail.get("error"),
    )
    assert "Server" in str(detail)

    vm = await client.post(
        "/v1/device/register", headers={"X-API-Key": key}, json=_payload(virtualization="kvm")
    )
    assert vm.status_code == 402

    # 'none' / absent signals register normally (legacy clients unaffected).
    bare = await client.post(
        "/v1/device/register", headers={"X-API-Key": key}, json=_payload(virtualization="none")
    )
    assert bare.status_code == 200


@pytest.mark.anyio
async def test_server_plan_accepts_server_class_machines(client, app) -> None:
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    # algenta_team's entitlement is deployment_class='server'.
    key, _ = await _seed_api_key(  # noqa: F405
        label="Server Plan Key",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ALGENTA_TEAM,  # noqa: F405
    )
    ok = await client.post(
        "/v1/device/register", headers={"X-API-Key": key}, json=_payload(container=True)
    )
    assert ok.status_code == 200
