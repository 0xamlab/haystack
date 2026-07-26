"""Active-node-cap enforcement — the device cap counts only RECENTLY-ACTIVE (heartbeating) nodes.

When ALGENTA_ENFORCE_ACTIVE_NODE_CAP is on, the per-key device cap is enforced against nodes that
have heartbeated within the active window, not every non-revoked device ever registered. So a
decommissioned / scaled-down node (its heartbeat lapses) automatically frees its slot — "I have 3
devices and want to drop 1" works without a manual revoke and without cheating the cap — while
running MORE than the cap CONCURRENTLY is still blocked. Default-DARK: with the flag off, the cap
counts all non-revoked devices exactly as before.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func
from sqlalchemy import update as sa_update

from apps.api_server.models.api_key import APIKey
from apps.api_server.models.device import DeviceStatus
from apps.api_server.models.usage_record import UsageRecord
from apps.api_server.services.auth_service import hash_api_key
from apps.api_server.services.device_service import (
    active_node_cap_enforced,
    active_node_window_seconds,
)
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403


def test_active_node_window_is_dynamic_and_env_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", raising=False)
    assert active_node_window_seconds() == 3 * 86_400  # default: 3 days
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "7200")
    assert active_node_window_seconds() == 7200
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "0")  # floored — never 0/negative
    assert active_node_window_seconds() == 60
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "garbage")  # invalid → default
    assert active_node_window_seconds() == 3 * 86_400


def test_active_node_cap_enforced_flag_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", raising=False)
    assert active_node_cap_enforced() is False  # default-dark
    for truthy in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", truthy)
        assert active_node_cap_enforced() is True
    for falsy in ("0", "false", "off", ""):
        monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", falsy)
        assert active_node_cap_enforced() is False


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


async def _age_heartbeat(device_id: str, *, seconds_ago: int) -> None:
    """Make a registered node look stale by backdating its last_heartbeat_at."""
    async with AsyncSessionLocal() as session:  # noqa: F405
        await session.execute(
            sa_update(DeviceRegistration)  # noqa: F405
            .where(DeviceRegistration.device_id == device_id)  # noqa: F405
            .values(last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=seconds_ago))  # noqa: F405
        )
        await session.commit()


async def _last_heartbeat(device_id: str):
    """Read a device's current last_heartbeat_at (to prove a withheld heartbeat did not refresh it).

    The test DB persists across runs, so the same device_id can exist under several (old) api keys;
    take the most-recently-created row, which is the one this run just registered.
    """
    async with AsyncSessionLocal() as session:  # noqa: F405
        result = await session.execute(
            select(DeviceRegistration.last_heartbeat_at)  # noqa: F405
            .where(DeviceRegistration.device_id == device_id)  # noqa: F405
            .order_by(DeviceRegistration.created_at.desc())  # noqa: F405
            .limit(1)
        )
        return result.scalars().first()


async def _key_ids(raw_key: str):
    """Resolve a raw API key to its (api_key_id, org_id) for direct DB assertions/seeding."""
    async with AsyncSessionLocal() as session:  # noqa: F405
        row = (
            await session.execute(
                select(APIKey).where(APIKey.hashed_key == hash_api_key(raw_key))  # noqa: F405
            )
        ).scalar_one()
        return row.id, row.org_id


async def _billing_units_for_key(raw_key: str) -> int:
    """Total billed units recorded under a key (to prove withheld heartbeats still reconcile usage)."""
    api_key_id, _ = await _key_ids(raw_key)
    async with AsyncSessionLocal() as session:  # noqa: F405
        total = (
            await session.execute(
                select(func.coalesce(func.sum(UsageRecord.billing_units), 0)).where(  # noqa: F405
                    UsageRecord.api_key_id == api_key_id
                )
            )
        ).scalar_one()
        return int(total or 0)


async def _seed_active_device(raw_key: str, device_id: str) -> None:
    """Insert an already-ACTIVE, freshly-heartbeating device directly (bypassing the register cap) to
    simulate a fleet that is already OVER the cap, e.g. the moment enforcement is flipped on."""
    api_key_id, org_id = await _key_ids(raw_key)
    async with AsyncSessionLocal() as session:  # noqa: F405
        session.add(
            DeviceRegistration(  # noqa: F405
                id=uuid.uuid4(),
                org_id=org_id,
                api_key_id=api_key_id,
                device_id=device_id,
                platform="linux",
                platform_version="6.8",
                hostname_hash="deadbeef" * 8,
                sdk_version="algenta-live/1.0.0",
                status=DeviceStatus.ACTIVE,  # noqa: F405
                last_heartbeat_at=datetime.now(UTC),  # noqa: F405
                heartbeat_count=1,
            )
        )
        await session.commit()


async def _register(client, key: str, device_id: str):
    return await client.post(
        "/v1/device/register", headers={"X-API-Key": key}, json=_payload(device_id)
    )


async def _runtime_key(client, owner_key: str, *, device_limit: int) -> str:
    create = await client.post(
        "/v1/api-keys",
        headers={"X-API-Key": owner_key},
        json={
            "label": "Runtime",
            "expires_at": "2028-05-19T00:00:00Z",
            "device_limit": device_limit,
        },
    )
    assert create.status_code == 201, create.text
    return create.json()["raw_key"]


@pytest.mark.anyio
async def test_stale_node_frees_its_slot_when_enforcement_on(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cap = 2. Two active nodes fill it; a third is blocked. When node-1's heartbeat lapses it stops
    counting, so a third node can register — the scaled-down node freed its slot automatically."""
    monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", "1")
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")  # 1h window for the test
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Node Cap Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)

        assert (await _register(client, key, "node-cap-device-0001")).status_code == 200
        assert (await _register(client, key, "node-cap-device-0002")).status_code == 200

        # Cap full — a third ACTIVE node is rejected, and the message reflects active enforcement.
        third = await _register(client, key, "node-cap-device-0003")
        assert third.status_code == 402, third.text
        assert "device_limit_reached" in third.text
        assert "currently active" in third.text

        # Node-1 is decommissioned: its heartbeat lapses past the window.
        await _age_heartbeat("node-cap-device-0001", seconds_ago=7200)

        # Now the third node registers — the stale node freed its slot without a manual revoke.
        third_again = await _register(client, key, "node-cap-device-0003")
        assert third_again.status_code == 200, third_again.text
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_default_dark_stale_node_still_counts_when_enforcement_off(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With enforcement OFF (default), the cap counts every non-revoked device regardless of
    heartbeat — a stale node still consumes its slot (today's behavior is unchanged)."""
    monkeypatch.delenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", raising=False)
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Node Cap Dark Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)

        assert (await _register(client, key, "dark-cap-device-0001")).status_code == 200
        assert (await _register(client, key, "dark-cap-device-0002")).status_code == 200
        await _age_heartbeat(
            "dark-cap-device-0001", seconds_ago=7200
        )  # stale, but enforcement is off

        # Still blocked: legacy semantics count all non-revoked devices. Message says "registered".
        third = await _register(client, key, "dark-cap-device-0003")
        assert third.status_code == 402, third.text
        assert "device_limit_reached" in third.text
        assert "registered" in third.text
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_register_revival_blocked_when_slot_reassigned(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale device whose slot was reassigned cannot re-register itself back while other live nodes
    fill the cap — the cap is a real concurrent ceiling, not a one-way registration gate."""
    monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", "1")
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Revival Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)
        assert (await _register(client, key, "revive-cap-device-0001")).status_code == 200
        assert (await _register(client, key, "revive-cap-device-0002")).status_code == 200

        # Node-1 decommissioned → slot freed → a replacement node-3 takes it.
        await _age_heartbeat("revive-cap-device-0001", seconds_ago=7200)
        assert (await _register(client, key, "revive-cap-device-0003")).status_code == 200

        # Node-1 tries to come back by re-registering while 2 & 3 are live — rejected (would be 3rd).
        revived = await _register(client, key, "revive-cap-device-0001")
        assert revived.status_code == 402, revived.text
        assert "device_limit_reached" in revived.text
        assert "slot was reassigned" in revived.text
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_heartbeat_withholds_slot_for_returning_stale_node(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A returning stale node's heartbeat must NOT silently grant it back the active slot when the
    cap is already full of other live nodes — it stays stale (its heartbeat is not refreshed)."""
    monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", "1")
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Heartbeat Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)
        assert (await _register(client, key, "hb-cap-device-000001")).status_code == 200
        assert (await _register(client, key, "hb-cap-device-000002")).status_code == 200

        await _age_heartbeat("hb-cap-device-000001", seconds_ago=7200)  # node-1 goes stale
        # node-3 takes the freed slot
        assert (await _register(client, key, "hb-cap-device-000003")).status_code == 200

        before = await _last_heartbeat("hb-cap-device-000001")
        hb = await client.post(
            "/v1/device/heartbeat",
            headers={"X-API-Key": key},
            json={"device_id": "hb-cap-device-000001", "usage": {}},
        )
        assert hb.status_code == 200, hb.text
        body = hb.json()
        assert body["status"] == "over_limit", body
        assert body["device_count"] == 2, body
        # The withheld heartbeat must NOT have refreshed node-1's clock (it stays stale).
        after = await _last_heartbeat("hb-cap-device-000001")
        assert after == before, (before, after)
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_bind_plane_stale_node_frees_slot_when_enforcement_on(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hosted-API binding path (the live work path, hit on every protected request) honors the
    active-node semantics: a decommissioned node frees its slot for a new device THERE too."""
    monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", "1")
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Bind Plane Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)
        a = await client.get("/v1/me", headers=_hosted_device_headers(key, "bind-cap-device-0001"))  # noqa: F405
        b = await client.get("/v1/me", headers=_hosted_device_headers(key, "bind-cap-device-0002"))  # noqa: F405
        assert a.status_code == 200 and b.status_code == 200, (a.text, b.text)

        # Cap full on the work path — a brand-new device's first request is blocked.
        c = await client.get("/v1/me", headers=_hosted_device_headers(key, "bind-cap-device-0003"))  # noqa: F405
        assert c.status_code == 402, c.text
        assert "device_limit_reached" in c.text

        # Decommission A → its slot frees on the bind plane too → C binds.
        await _age_heartbeat("bind-cap-device-0001", seconds_ago=7200)
        c_again = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(key, "bind-cap-device-0003"),  # noqa: F405
        )
        assert c_again.status_code == 200, c_again.text
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_bind_plane_revival_blocked_is_a_concurrent_ceiling(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The concurrent ceiling holds on the work path: once a stale node's slot is reassigned, the
    stale node's own requests are rejected when it returns — it cannot run alongside the full set."""
    monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", "1")
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Bind Ceiling Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)
        a = await client.get("/v1/me", headers=_hosted_device_headers(key, "ceil-cap-device-0001"))  # noqa: F405
        b = await client.get("/v1/me", headers=_hosted_device_headers(key, "ceil-cap-device-0002"))  # noqa: F405
        assert a.status_code == 200 and b.status_code == 200, (a.text, b.text)
        token_a = a.headers.get("X-Algenta-Device-Binding-Token", "")
        assert token_a

        # A goes stale; C (new device) takes the freed slot.
        await _age_heartbeat("ceil-cap-device-0001", seconds_ago=7200)
        c = await client.get("/v1/me", headers=_hosted_device_headers(key, "ceil-cap-device-0003"))  # noqa: F405
        assert c.status_code == 200, c.text

        # A returns (valid binding token) but B & C are live → A is rejected on the work path.
        a_back = await client.get(
            "/v1/me",
            headers=_hosted_device_headers(key, "ceil-cap-device-0001", binding_token=token_a),  # noqa: F405
        )
        assert a_back.status_code == 402, a_back.text
        assert "device_limit_reached" in a_back.text
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_bind_plane_default_dark_stale_still_counts(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flag off: the hosted-API binding cap counts all non-revoked devices, unchanged from before —
    a stale device still consumes its slot, so the 3rd device is blocked on the bind plane."""
    monkeypatch.delenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", raising=False)
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Bind Dark Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)
        a = await client.get("/v1/me", headers=_hosted_device_headers(key, "binddark-device-0001"))  # noqa: F405
        b = await client.get("/v1/me", headers=_hosted_device_headers(key, "binddark-device-0002"))  # noqa: F405
        assert a.status_code == 200 and b.status_code == 200, (a.text, b.text)
        await _age_heartbeat("binddark-device-0001", seconds_ago=7200)  # stale, but enforcement off

        c = await client.get("/v1/me", headers=_hosted_device_headers(key, "binddark-device-0003"))  # noqa: F405
        assert c.status_code == 402, c.text
        assert "device_limit_reached" in c.text
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_withheld_heartbeat_still_reconciles_usage(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A withheld (over-cap) heartbeat must still bill work already performed — only the active slot
    is withheld, never the usage record (otherwise an over-cap node's executions are lost forever).

    Usage billing only runs when metering is enabled (self-hosted ships with it OFF), so this
    metering-specific test opts it in explicitly."""
    monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", "1")
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")
    monkeypatch.setenv("ALGENTA_ENABLE_METERING", "true")
    from apps.api_server.config import get_settings

    get_settings.cache_clear()
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Usage Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)
        assert (await _register(client, key, "usage-cap-device-0001")).status_code == 200
        assert (await _register(client, key, "usage-cap-device-0002")).status_code == 200
        await _age_heartbeat("usage-cap-device-0001", seconds_ago=7200)
        assert (await _register(client, key, "usage-cap-device-0003")).status_code == 200

        before = await _billing_units_for_key(key)
        hb = await client.post(
            "/v1/device/heartbeat",
            headers={"X-API-Key": key},
            json={"device_id": "usage-cap-device-0001", "usage": {"executions_since_last_heartbeat": 7}},
        )
        assert hb.status_code == 200, hb.text
        assert hb.json()["status"] == "over_limit", hb.json()  # slot withheld
        after = await _billing_units_for_key(key)
        assert after - before == 7, (before, after)  # ...but the 7 executions were still billed
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405
        get_settings.cache_clear()  # don't leak metering=on into other tests


@pytest.mark.anyio
async def test_over_cap_fleet_keeps_running_nodes_and_blocks_only_new(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flipping enforcement on for a fleet that ALREADY exceeds the cap must not shed running nodes:
    a currently-active node's heartbeat is admitted (it keeps its slot), while a brand-new device is
    still blocked. The set then drains naturally as nodes go stale — no thundering-herd eviction."""
    monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", "1")
    monkeypatch.setenv("ALGENTA_ACTIVE_NODE_WINDOW_SECONDS", "3600")
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Over Cap Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key, device_limit=2)
        # Simulate a fleet of 3 already-active nodes under a cap of 2 (the flip-on-while-over case).
        for did in ("overcap-device-000001", "overcap-device-000002", "overcap-device-000003"):
            await _seed_active_device(key, did)

        # A currently-active node's heartbeat is ADMITTED (not evicted) — its clock is refreshed.
        before = await _last_heartbeat("overcap-device-000001")
        hb = await client.post(
            "/v1/device/heartbeat",
            headers={"X-API-Key": key},
            json={"device_id": "overcap-device-000001", "usage": {}},
        )
        assert hb.status_code == 200, hb.text
        after = await _last_heartbeat("overcap-device-000001")
        assert after is not None and before is not None and after > before, (before, after)

        # But a brand-NEW device is still blocked — the cap stops the set from growing further.
        new_dev = await _register(client, key, "overcap-new-device-0009")
        assert new_dev.status_code == 402, new_dev.text
        assert "device_limit_reached" in new_dev.text
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405
