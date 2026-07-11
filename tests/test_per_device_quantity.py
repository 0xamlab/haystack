"""Part 2 — per-device billing: the Stripe subscription quantity IS the licensed device count.

Covers the inversion end-to-end: the org ceiling (Organization.licensed_devices) drives the device
cap in plan_limits, the webhook syncs the quantity, checkout sends quantity=devices, and device
registration enforces the org-wide ceiling (incl. across multiple API keys) with the license JWT
carrying the purchased device_limit + active_node_limit. Per-seat plans (codna/telys) are untouched.
"""
from __future__ import annotations

import types
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.api_key import APIKey, APIKeyStatus
from apps.api_server.models.device import DeviceRegistration, DeviceStatus
from apps.api_server.models.organization import Organization, OrgPlan
from apps.api_server.routers import billing
from apps.api_server.services import plan_limits
from apps.api_server.services.auth_service import hash_api_key
from apps.api_server.services.device_service import register_device
from tests._test_api_key_expiry_contract_helpers import _RedisStub, _seed_api_key


# ── plan_limits: the org ceiling drives the device cap (per-device plans only) ───────
def test_is_per_device_plan() -> None:
    assert plan_limits.is_per_device_plan("algenta_pro")
    assert plan_limits.is_per_device_plan("algenta_team")
    assert not plan_limits.is_per_device_plan("team")  # codna = per-seat
    assert not plan_limits.is_per_device_plan("telys_team")  # telys = per-seat
    assert not plan_limits.is_per_device_plan("algenta_free")  # community = 1 device


def test_effective_device_limit_org_ceiling_overrides_static() -> None:
    # algenta_pro static devices=3; an org that licensed 10 devices can register 10.
    assert plan_limits.effective_device_limit("algenta_pro", None, org_ceiling=10) == 10
    # a per-key override still narrows within the org ceiling (sub-allocation).
    assert plan_limits.effective_device_limit("algenta_pro", 4, org_ceiling=10) == 4
    # 0 / missing ceiling → fall back to the static plan cap, never a lockout.
    assert plan_limits.effective_device_limit("algenta_pro", None, org_ceiling=0) == 3
    assert plan_limits.effective_device_limit("algenta_pro", None, org_ceiling=None) == 3
    # per-seat/other plans are byte-for-byte unchanged when no ceiling is passed.
    assert plan_limits.effective_device_limit("team", None) == plan_limits.device_limit("team")


def test_validate_api_key_device_limit_uses_org_ceiling() -> None:
    # a per-key override up to the org ceiling is accepted (even above the static plan cap of 3).
    assert plan_limits.validate_api_key_device_limit("algenta_pro", 8, org_ceiling=10) == 8
    with pytest.raises(ValueError):
        plan_limits.validate_api_key_device_limit("algenta_pro", 11, org_ceiling=10)


# ── webhook: subscription quantity → org.licensed_devices (per-device only) ──────────
def _event(event_type: str, customer: str, **obj) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": event_type,
        "data": {"object": {"customer": customer, "id": f"sub_{uuid.uuid4().hex}", **obj}},
    }


async def _seed_org(plan: OrgPlan, customer_id: str) -> str:
    _raw, key_id = await _seed_api_key(
        label=f"pd-{uuid.uuid4().hex[:6]}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=plan,
    )
    async with AsyncSessionLocal() as s:
        ak = (await s.execute(select(APIKey).where(APIKey.id == uuid.UUID(key_id)))).scalar_one()
        org = (await s.execute(select(Organization).where(Organization.id == ak.org_id))).scalar_one()
        org.stripe_customer_id = customer_id
        await s.commit()
        return str(org.id)


async def _org(org_id: str) -> Organization:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(Organization).where(Organization.id == uuid.UUID(org_id)))
        ).scalar_one()


async def _process(event: dict) -> None:
    async with AsyncSessionLocal() as s:
        await billing._process_stripe_event(s, event)
        await s.commit()


@pytest.mark.anyio
async def test_subscription_quantity_syncs_licensed_devices_for_algenta(monkeypatch) -> None:
    monkeypatch.setattr(
        billing,
        "_get_settings",
        lambda: types.SimpleNamespace(stripe_price_algenta_team="price_at"),
    )
    cus = f"cus_{uuid.uuid4().hex}"
    org_id = await _seed_org(OrgPlan.ALGENTA_TEAM, cus)
    await _process(
        _event(
            "customer.subscription.updated",
            cus,
            status="active",
            items={"data": [{"price": {"id": "price_at"}, "quantity": 20}]},
        )
    )
    assert (await _org(org_id)).licensed_devices == 20  # licensed device count = Stripe quantity


@pytest.mark.anyio
async def test_per_seat_plan_leaves_licensed_devices_zero(monkeypatch) -> None:
    monkeypatch.setattr(
        billing,
        "_get_settings",
        lambda: types.SimpleNamespace(stripe_price_team="price_t"),
    )
    cus = f"cus_{uuid.uuid4().hex}"
    org_id = await _seed_org(OrgPlan.TEAM, cus)  # codna per-seat
    await _process(
        _event(
            "customer.subscription.updated",
            cus,
            status="active",
            items={"data": [{"price": {"id": "price_t"}, "quantity": 20}]},
        )
    )
    org = await _org(org_id)
    assert org.seats == 20  # per-seat: quantity = seats
    assert org.licensed_devices == 0  # NOT a device count for per-seat plans


# ── registration: the org-wide licensed ceiling is enforced, incl. across API keys ──
def _dev_info(i: int) -> dict:
    return {
        "device_id": f"pd-dev-{uuid.uuid4().hex}",
        "platform": "linux",
        "platform_version": "6.8",
        "hostname_hash": "h" * 16,
        "sdk_version": "1.0",
        "device_pubkey_thumbprint": f"ed25519:{i}",
    }


async def _set_licensed_devices(org_id: str, n: int) -> None:
    async with AsyncSessionLocal() as s:
        org = (
            await s.execute(select(Organization).where(Organization.id == uuid.UUID(org_id)))
        ).scalar_one()
        org.licensed_devices = n
        await s.commit()


async def _add_api_key(org_id: str) -> str:
    """Add a SECOND API key to an existing org; returns the raw key."""
    raw = f"de_live_{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as s:
        org = (
            await s.execute(select(Organization).where(Organization.id == uuid.UUID(org_id)))
        ).scalar_one()
        user_id = (
            await s.execute(select(APIKey.user_id).where(APIKey.org_id == org.id).limit(1))
        ).scalar_one()
        s.add(
            APIKey(
                org_id=org.id,
                user_id=user_id,
                label=f"pd-2nd-{uuid.uuid4().hex[:6]}",
                key_prefix=raw[:12],
                hashed_key=hash_api_key(raw),
                status=APIKeyStatus.ACTIVE,
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
        )
        await s.commit()
    return raw


@pytest.mark.anyio
async def test_register_enforces_org_wide_licensed_ceiling_across_keys() -> None:
    """A per-device org licensed for 2 devices can register 2 total — even split across two API
    keys — and the 3rd is refused (the org-wide count, not a per-key count, is the true ceiling)."""
    cus = f"cus_{uuid.uuid4().hex}"
    raw_key, key_id = await _seed_api_key(
        label="pd-ceiling", expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ALGENTA_PRO
    )
    async with AsyncSessionLocal() as s:
        org_id = str(
            (await s.execute(select(APIKey.org_id).where(APIKey.id == uuid.UUID(key_id)))).scalar_one()
        )
    await _set_licensed_devices(org_id, 2)
    raw_key2 = await _add_api_key(org_id)

    async with AsyncSessionLocal() as s:
        r1 = await register_device(raw_key, _dev_info(1), s)
        await s.commit()
    assert r1 is not None
    async with AsyncSessionLocal() as s:
        r2 = await register_device(raw_key2, _dev_info(2), s)  # 2nd device, DIFFERENT key
        await s.commit()
    assert r2 is not None
    # 3rd device (back on key 1) exceeds the org-wide licensed count of 2 → refused.
    with pytest.raises(ValueError, match="[Ll]icensed device limit reached"):
        async with AsyncSessionLocal() as s:
            await register_device(raw_key, _dev_info(3), s)
            await s.commit()


async def _runtime_key(client, owner_key: str, device_limit: int) -> str:
    r = await client.post(
        "/v1/api-keys",
        headers={"X-API-Key": owner_key},
        json={"label": "rt", "expires_at": "2028-05-19T00:00:00Z", "device_limit": device_limit},
    )
    assert r.status_code == 201, r.text
    return r.json()["raw_key"]


def _reg_payload(device_id: str) -> dict:
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
async def test_live_register_endpoint_enforces_org_wide_ceiling_across_keys(client, app) -> None:
    """The LIVE POST /v1/device/register endpoint (not just the service helper) must enforce the
    org-wide licensed ceiling across MULTIPLE API keys — the anti-cheat that stops an org registering
    more devices than it pays for by spreading them over keys."""
    from apps.api_server.middleware.auth import get_redis

    async def _fake_redis() -> object:
        return _RedisStub()

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, key_id = await _seed_api_key(
        label="pd-live", expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ALGENTA_PRO
    )
    async with AsyncSessionLocal() as s:
        org_id = str(
            (await s.execute(select(APIKey.org_id).where(APIKey.id == uuid.UUID(key_id)))).scalar_one()
        )
    await _set_licensed_devices(org_id, 2)  # licensed for exactly 2 devices
    try:
        k1 = await _runtime_key(client, owner_key, device_limit=3)  # per-key cap 3 (static algenta_pro)
        k2 = await _runtime_key(client, owner_key, device_limit=3)
        # 2 devices, one per key — within the org ceiling of 2.
        assert (await client.post("/v1/device/register", headers={"X-API-Key": k1}, json=_reg_payload("pd-live-device-0001"))).status_code == 200
        assert (await client.post("/v1/device/register", headers={"X-API-Key": k2}, json=_reg_payload("pd-live-device-0002"))).status_code == 200
        # 3rd device (per-key count is only 1 on k1, so per-key would pass) → org-wide ceiling refuses.
        third = await client.post("/v1/device/register", headers={"X-API-Key": k1}, json=_reg_payload("pd-live-device-0003"))
        assert third.status_code == 402, third.text
        assert "licensed_device_limit_reached" in third.text, third.text
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_live_register_enforces_static_ceiling_when_unsynced(client, app) -> None:
    """Even with licensed_devices=0 (webhook not yet fired), a per-device org is bounded ORG-WIDE at
    the static plan cap (algenta_pro=3) across keys — no multi-key sprawl window before the sync."""
    from apps.api_server.middleware.auth import get_redis

    async def _fake_redis() -> object:
        return _RedisStub()

    app.dependency_overrides[get_redis] = _fake_redis
    owner_key, _ = await _seed_api_key(
        label="pd-unsynced", expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ALGENTA_PRO
    )
    # licensed_devices left at 0 (unsynced) → org-wide ceiling falls back to static algenta_pro=3.
    try:
        k1 = await _runtime_key(client, owner_key, device_limit=3)
        k2 = await _runtime_key(client, owner_key, device_limit=3)
        assert (await client.post("/v1/device/register", headers={"X-API-Key": k1}, json=_reg_payload("unsynced-device-0001"))).status_code == 200
        assert (await client.post("/v1/device/register", headers={"X-API-Key": k1}, json=_reg_payload("unsynced-device-0002"))).status_code == 200
        assert (await client.post("/v1/device/register", headers={"X-API-Key": k2}, json=_reg_payload("unsynced-device-0003"))).status_code == 200
        # 4th device across keys exceeds the static org-wide cap of 3 → refused (no multi-key sprawl).
        fourth = await client.post("/v1/device/register", headers={"X-API-Key": k2}, json=_reg_payload("unsynced-device-0004"))
        assert fourth.status_code == 402, fourth.text
        assert "licensed_device_limit_reached" in fourth.text, fourth.text
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.anyio
async def test_license_jwt_carries_purchased_device_and_node_limits() -> None:
    """The issued license reflects the PURCHASED device count (org ceiling), not the static tier
    default — both device_limit (online gate) and active_node_limit (offline node_broker census)."""
    key_raw, key_id = await _seed_api_key(
        label="pd-jwt", expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ALGENTA_TEAM
    )
    async with AsyncSessionLocal() as s:
        org_id = str(
            (await s.execute(select(APIKey.org_id).where(APIKey.id == uuid.UUID(key_id)))).scalar_one()
        )
    await _set_licensed_devices(org_id, 12)  # above the static algenta_team devices=10
    async with AsyncSessionLocal() as s:
        result = await register_device(key_raw, _dev_info(1), s)
        await s.commit()
    assert result is not None
    assert result["device_limit"] == 12  # org ceiling, not the static 10
    claims = jwt.decode(result["license_token"], options={"verify_signature": False})
    assert claims["device_limit"] == 12
    assert claims["active_node_limit"] == 12  # offline census cap = purchased device count


@pytest.mark.anyio
async def test_register_falls_back_to_static_cap_when_unsynced() -> None:
    """licensed_devices=0 (webhook not yet fired) → enforcement uses the static plan cap, never a
    lockout. algenta_pro static devices=3, so a 4th device is refused by the per-key/static cap."""
    key_raw, key_id = await _seed_api_key(
        label="pd-fallback", expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ALGENTA_PRO
    )
    # licensed_devices left at its default 0 (unsynced).
    async with AsyncSessionLocal() as s:
        for i in range(3):  # static cap is 3 → all OK
            await register_device(key_raw, _dev_info(i), s)
            await s.commit()
    with pytest.raises(ValueError, match="[Dd]evice limit reached"):
        async with AsyncSessionLocal() as s:
            await register_device(key_raw, _dev_info(99), s)
            await s.commit()


# ── B2: subscription resolves the org by metadata org_id when stripe_customer_id isn't set yet ──────
@pytest.mark.anyio
async def test_subscription_resolves_org_by_metadata_when_customer_unset(monkeypatch) -> None:
    # subscription.created can fire BEFORE checkout.session.completed persists stripe_customer_id
    # (Stripe gives no ordering guarantee). The handler must resolve the org via the subscription's
    # stamped metadata org_id, sync licensed_devices, and backfill the customer id — else a buyer of
    # N > plan-default devices is silently capped at the default.
    monkeypatch.setattr(
        billing, "_get_settings",
        lambda: types.SimpleNamespace(stripe_price_algenta_pro="price_ap"),
    )
    _raw, key_id = await _seed_api_key(
        label=f"pd-nocus-{uuid.uuid4().hex[:6]}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ALGENTA_PRO,
    )
    async with AsyncSessionLocal() as s:
        ak = (await s.execute(select(APIKey).where(APIKey.id == uuid.UUID(key_id)))).scalar_one()
        org_id = str(ak.org_id)  # NOTE: this org has NO stripe_customer_id yet
    cus = f"cus_{uuid.uuid4().hex}"  # a customer id not on any org
    await _process(
        _event(
            "customer.subscription.created", cus, status="active",
            items={"data": [{"price": {"id": "price_ap"}, "quantity": 7}]},
            metadata={"org_id": org_id, "plan": "algenta_pro"},
        )
    )
    org = await _org(org_id)
    assert org.licensed_devices == 7          # synced via the metadata fallback
    assert org.stripe_customer_id == cus      # backfilled for future customer-id lookups


# ── B4: the org-wide count honors the active-node-cap window (a stale node frees its org slot) ──────
@pytest.mark.anyio
async def test_active_org_device_count_honors_active_window(monkeypatch) -> None:
    from apps.api_server.services import device_service as ds

    _raw, key_id = await _seed_api_key(
        label=f"pd-win-{uuid.uuid4().hex[:6]}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=OrgPlan.ALGENTA_PRO,
    )
    async with AsyncSessionLocal() as s:
        ak = (await s.execute(select(APIKey).where(APIKey.id == uuid.UUID(key_id)))).scalar_one()
        org_id, akid = ak.org_id, ak.id
        # one FRESH device + one STALE device (heartbeat well outside the active window)
        s.add(DeviceRegistration(
            id=uuid.uuid4(), org_id=org_id, api_key_id=akid, device_id="fresh-" + uuid.uuid4().hex,
            platform="linux", status=DeviceStatus.ACTIVE, last_heartbeat_at=datetime.now(UTC), heartbeat_count=1,
        ))
        s.add(DeviceRegistration(
            id=uuid.uuid4(), org_id=org_id, api_key_id=akid, device_id="stale-" + uuid.uuid4().hex,
            platform="linux", status=DeviceStatus.ACTIVE,
            last_heartbeat_at=datetime.now(UTC) - timedelta(days=30), heartbeat_count=1,
        ))
        await s.commit()
    # enforcement OFF → counts both non-revoked (legacy)
    monkeypatch.delenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", raising=False)
    async with AsyncSessionLocal() as s:
        assert await ds._active_org_device_count(org_id, s) == 2
    # enforcement ON → the stale node no longer counts (its org slot is freed)
    monkeypatch.setenv("ALGENTA_ENFORCE_ACTIVE_NODE_CAP", "1")
    async with AsyncSessionLocal() as s:
        assert await ds._active_org_device_count(org_id, s) == 1


# ── B1: hosted-API device binding enforces the ORG-WIDE licensed ceiling across MULTIPLE keys ───────
@pytest.mark.anyio
async def test_hosted_bind_enforces_org_wide_ceiling_across_keys() -> None:
    from starlette.requests import Request

    from apps.api_server.services import device_service as ds

    def _bind_req(device_id: str) -> Request:
        return Request({
            "type": "http", "method": "GET", "path": "/v1/simulate", "query_string": b"",
            "headers": [(ds.HOSTED_DEVICE_ID_HEADER.lower().encode(), device_id.encode()),
                        (b"x-algenta-platform", b"linux"),
                        (b"x-algenta-hostname-hash", b"h" * 16)],
        })

    async def _bind(key_id, device_id):
        auth = {"key_id": key_id, "device_limit_configured": True, "device_limit": 5}
        async with AsyncSessionLocal() as s:
            res = await ds.bind_hosted_api_device(_bind_req(device_id), auth, s)
            await s.commit()
            return res

    # org licensed for 2 devices, TWO api keys (each per-key limit 5 — so per-key never trips first)
    _raw1, key1 = await _seed_api_key(
        label=f"pd-b1-{uuid.uuid4().hex[:6]}",
        expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ALGENTA_PRO,
    )
    async with AsyncSessionLocal() as s:
        ak = (await s.execute(select(APIKey).where(APIKey.id == uuid.UUID(key1)))).scalar_one()
        org_id = str(ak.org_id)
        ak.device_limit = 5
        await s.commit()
    await _set_licensed_devices(org_id, 2)
    raw2 = await _add_api_key(org_id)
    async with AsyncSessionLocal() as s:
        ak2 = (await s.execute(select(APIKey).where(APIKey.key_prefix == raw2[:12]))).scalar_one()
        ak2.device_limit = 5  # per-key cap high so the ORG ceiling (2) is what trips, not the per-key
        key2 = str(ak2.id)
        await s.commit()

    # device 1 via key1, device 2 via key2 → both OK (org count 0→1→2)
    assert (await _bind(uuid.UUID(key1), "dev-one-" + uuid.uuid4().hex))["binding_token"]
    assert (await _bind(uuid.UUID(key2), "dev-two-" + uuid.uuid4().hex))["binding_token"]
    # device 3 via key1 → org ceiling (2) hit, though key1's per-key count (1) is under its limit (5)
    with pytest.raises(ds.DeviceBindingError) as exc:
        await _bind(uuid.UUID(key1), "dev-three-" + uuid.uuid4().hex)
    assert exc.value.code == "licensed_device_limit_reached"
