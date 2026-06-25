"""Install/registration rate-limit — abuse protection on NEW device installs (not usage).

A brand-new device registration is capped per rolling hour (dynamic per plan; global override via
ALGENTA_DEVICE_INSTALLS_PER_HOUR). Re-registering an EXISTING device (license refresh) is never
rate-limited. This is distinct from the device CAP (device_limit_reached) — it stops scripted
hammering of the register endpoint, not concurrent device count.
"""

from __future__ import annotations

import pytest

from apps.api_server.services.device_service import installs_per_hour
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


def test_installs_per_hour_is_dynamic_and_env_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALGENTA_DEVICE_INSTALLS_PER_HOUR", raising=False)
    assert installs_per_hour("enterprise") == 0  # unlimited
    assert installs_per_hour("pro") == 100
    monkeypatch.setenv("ALGENTA_DEVICE_INSTALLS_PER_HOUR", "5")
    assert installs_per_hour("enterprise") == 5  # global override wins over the per-plan default
    assert installs_per_hour("pro") == 5


def _payload(device_id: str) -> dict[str, object]:
    return {
        "device": {
            "device_id": device_id,
            "platform": "linux",
            "platform_version": "6.8",
            "hostname_hash": "deadbeef" * 8,
            "sdk_version": "algenta-live/1.0.0",
        }
    }


@pytest.mark.anyio
async def test_install_rate_limit_caps_new_devices_but_not_refreshes(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_DEVICE_INSTALLS_PER_HOUR", "2")  # tiny budget for the test
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Install RL Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        # device_limit high so the CAP (402) never fires — we're testing the install RATE (429).
        create = await client.post(
            "/v1/api-keys",
            headers={"X-API-Key": owner_key},
            json={"label": "Runtime", "expires_at": "2028-05-19T00:00:00Z", "device_limit": 10},
        )
        assert create.status_code == 201
        runtime_key = create.json()["raw_key"]

        # Two brand-new devices register fine (within budget = 2).
        for did in ("install-rl-device-0001", "install-rl-device-0002"):
            ok = await client.post(
                "/v1/device/register", headers={"X-API-Key": runtime_key}, json=_payload(did)
            )
            assert ok.status_code == 200, ok.text

        # A third brand-new device trips the install rate-limit.
        third = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_payload("install-rl-device-0003"),
        )
        assert third.status_code == 429, third.text
        assert "device_registration_rate_limited" in third.text

        # Re-registering an EXISTING device (refresh) is NOT rate-limited.
        refresh = await client.post(
            "/v1/device/register",
            headers={"X-API-Key": runtime_key},
            json=_payload("install-rl-device-0001"),
        )
        assert refresh.status_code == 200, refresh.text
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405
