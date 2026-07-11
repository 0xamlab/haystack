"""Stripe → entitlements (P3c).

A subscription change recomputes the org's entitlement (audited); a CANCELLATION revokes ALL
the org's devices (→ CRL); a paid→paid DOWNGRADE revokes only devices beyond the new cap
(keeping the most-recently-active). Tested by driving _process_stripe_event directly (signature
verification + idempotency-ledger are covered by test_stripe_webhook_hardening.py).
"""

from __future__ import annotations

import types
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.api_key import APIKey
from apps.api_server.models.audit_event import AuditAction, AuditEvent
from apps.api_server.models.device import DeviceRegistration, DeviceStatus
from apps.api_server.models.organization import Organization, OrgPlan
from apps.api_server.routers import billing
from apps.api_server.services.device_service import _activation_id, build_revocation_payload
from tests._test_api_key_expiry_contract_helpers import _seed_api_key


async def _seed(plan: OrgPlan, customer_id: str, heartbeat_minutes: list[int | None]):
    """Seed an org (with stripe_customer_id) + N ACTIVE devices. Returns (org_id, [device_id])."""
    _raw, key_id = await _seed_api_key(
        label=f"p3c-{uuid.uuid4().hex[:6]}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        plan=plan,
    )
    device_ids: list[str] = []
    async with AsyncSessionLocal() as s:
        ak = (await s.execute(select(APIKey).where(APIKey.id == uuid.UUID(key_id)))).scalar_one()
        org = (
            await s.execute(select(Organization).where(Organization.id == ak.org_id))
        ).scalar_one()
        org.stripe_customer_id = customer_id
        for i, hb in enumerate(heartbeat_minutes):
            did = f"p3c-dev-{uuid.uuid4().hex}"
            device_ids.append(did)
            s.add(
                DeviceRegistration(
                    org_id=org.id,
                    api_key_id=ak.id,
                    device_id=did,
                    platform="linux",
                    platform_version="6.8",
                    hostname_hash="h" * 16,
                    sdk_version="x",
                    device_pubkey_thumbprint=f"ed25519:{i}",
                    status=DeviceStatus.ACTIVE,
                    last_heartbeat_at=(
                        datetime.now(UTC) - timedelta(minutes=hb) if hb is not None else None
                    ),
                    heartbeat_count=1,
                )
            )
        await s.commit()
        return str(org.id), device_ids


def _event(event_type: str, customer: str, **obj) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": event_type,
        "data": {"object": {"customer": customer, "id": f"sub_{uuid.uuid4().hex}", **obj}},
    }


async def _process(event: dict) -> None:
    async with AsyncSessionLocal() as s:
        await billing._process_stripe_event(s, event)
        await s.commit()


async def _statuses(org_id: str) -> dict[str, DeviceStatus]:
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(DeviceRegistration.device_id, DeviceRegistration.status).where(
                    DeviceRegistration.org_id == uuid.UUID(org_id)
                )
            )
        ).all()
        return dict(rows)


async def _org_plan(org_id: str) -> OrgPlan:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(Organization.plan).where(Organization.id == uuid.UUID(org_id)))
        ).scalar_one()


async def _audit_actions(org_id: str) -> list[str]:
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(AuditEvent.action).where(AuditEvent.org_id == uuid.UUID(org_id))
            )
        ).scalars().all()
        return list(rows)


# ── cancellation → revoke all + CRL + audit ────────────────────────────────────


@pytest.mark.anyio
async def test_cancel_revokes_all_devices_and_crl_lists_them() -> None:
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, device_ids = await _seed(OrgPlan.PRO, cus, [1, 2])
    await _process(_event("customer.subscription.deleted", cus))

    assert await _org_plan(org_id) == OrgPlan.FREE
    statuses = await _statuses(org_id)
    assert all(st == DeviceStatus.REVOKED for st in statuses.values())

    async with AsyncSessionLocal() as s:
        crl = await build_revocation_payload(s)
    listed = {e["activation_id"] for e in crl["revoked"]}
    for did in device_ids:
        assert _activation_id(org_id, did) in listed
    assert crl["version"] > 0


@pytest.mark.anyio
async def test_cancel_writes_entitlement_and_device_audit() -> None:
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, _ = await _seed(OrgPlan.PRO, cus, [1, 2, 3])
    await _process(_event("customer.subscription.deleted", cus))
    actions = await _audit_actions(org_id)
    assert AuditAction.ENTITLEMENT_REVOKED.value in actions
    assert AuditAction.DEVICE_REVOKED.value in actions


# ── paid→paid downgrade → revoke only the excess (keep most-recent) ─────────────


@pytest.mark.anyio
async def test_downgrade_revokes_only_excess(monkeypatch) -> None:
    monkeypatch.setattr(
        billing,
        "_get_settings",
        lambda: types.SimpleNamespace(
            stripe_price_pro="price_pro_test", stripe_price_developer="price_dev_test"
        ),
    )
    cus = f"cus_{uuid.uuid4().hex}"
    # 7 devices, device i heartbeated (i+1) min ago → device 0 newest, device 6 oldest.
    org_id, device_ids = await _seed(OrgPlan.TEAM, cus, [1, 2, 3, 4, 5, 6, 7])
    # subscription.updated → price maps to 'pro' (device_limit 5).
    await _process(
        _event(
            "customer.subscription.updated",
            cus,
            status="active",
            items={"data": [{"price": {"id": "price_pro_test"}}]},
        )
    )
    statuses = await _statuses(org_id)
    # 5 most-recently-active kept; the 2 oldest revoked.
    assert statuses[device_ids[5]] == DeviceStatus.REVOKED
    assert statuses[device_ids[6]] == DeviceStatus.REVOKED
    for did in device_ids[:5]:
        assert statuses[did] == DeviceStatus.ACTIVE
    assert AuditAction.DEVICE_REVOKED.value in await _audit_actions(org_id)


@pytest.mark.anyio
async def test_upgrade_revokes_nothing(monkeypatch) -> None:
    monkeypatch.setattr(
        billing,
        "_get_settings",
        lambda: types.SimpleNamespace(
            stripe_price_pro="price_pro_test", stripe_price_developer="price_dev_test"
        ),
    )
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, device_ids = await _seed(OrgPlan.PRO, cus, [1, 2])
    # 'pro' has device_limit 5 ≥ 2 devices → excess 0.
    await _process(
        _event(
            "customer.subscription.updated",
            cus,
            status="active",
            items={"data": [{"price": {"id": "price_pro_test"}}]},
        )
    )
    statuses = await _statuses(org_id)
    assert all(st == DeviceStatus.ACTIVE for st in statuses.values())
    actions = await _audit_actions(org_id)
    assert AuditAction.ENTITLEMENT_RECOMPUTE.value in actions
    assert AuditAction.DEVICE_REVOKED.value not in actions


# ── safety: unknown customer + cross-org isolation + idempotent revoke ──────────


@pytest.mark.anyio
async def test_updated_with_unknown_price_keeps_plan_and_revokes_nothing(monkeypatch) -> None:
    """A misconfigured/unknown price_id parses to 'free' — must NOT downgrade-and-revoke a
    paying customer. Plan is kept; cancellation only ever comes via subscription.deleted."""
    monkeypatch.setattr(
        billing,
        "_get_settings",
        lambda: types.SimpleNamespace(
            stripe_price_pro="price_pro_test", stripe_price_developer="price_dev_test"
        ),
    )
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, _ = await _seed(OrgPlan.PRO, cus, [1, 2])
    await _process(
        _event(
            "customer.subscription.updated",
            cus,
            status="active",
            items={"data": [{"price": {"id": "price_TOTALLY_UNKNOWN"}}]},
        )
    )
    assert await _org_plan(org_id) == OrgPlan.PRO  # NOT downgraded to free on a parse failure
    statuses = await _statuses(org_id)
    assert all(st == DeviceStatus.ACTIVE for st in statuses.values())  # nothing revoked


@pytest.mark.anyio
async def test_unknown_customer_revokes_nothing() -> None:
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, _ = await _seed(OrgPlan.PRO, cus, [1, 2])
    await _process(_event("customer.subscription.deleted", f"cus_does_not_exist_{uuid.uuid4().hex}"))
    statuses = await _statuses(org_id)
    assert all(st == DeviceStatus.ACTIVE for st in statuses.values())  # untouched


@pytest.mark.anyio
async def test_cancel_is_cross_org_isolated() -> None:
    cus_a = f"cus_{uuid.uuid4().hex}"
    cus_b = f"cus_{uuid.uuid4().hex}"
    org_a, _ = await _seed(OrgPlan.PRO, cus_a, [1, 2])
    org_b, _ = await _seed(OrgPlan.PRO, cus_b, [1, 2])
    await _process(_event("customer.subscription.deleted", cus_a))
    assert all(st == DeviceStatus.REVOKED for st in (await _statuses(org_a)).values())
    assert all(st == DeviceStatus.ACTIVE for st in (await _statuses(org_b)).values())  # B safe


@pytest.mark.anyio
async def test_cancel_is_idempotent() -> None:
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, _ = await _seed(OrgPlan.PRO, cus, [1, 2])
    await _process(_event("customer.subscription.deleted", cus))
    await _process(_event("customer.subscription.deleted", cus))  # re-deliver
    statuses = await _statuses(org_id)
    assert all(st == DeviceStatus.REVOKED for st in statuses.values())
    # The 2nd call revokes 0 (already revoked) → only ONE DEVICE_REVOKED audit row.
    device_revokes = [a for a in await _audit_actions(org_id) if a == AuditAction.DEVICE_REVOKED.value]
    assert len(device_revokes) == 1


# ── product-namespaced Community downgrade (anti-pay-once-leave target fix) ──────


@pytest.mark.anyio
async def test_algenta_cancel_downgrades_to_algenta_free_not_free() -> None:
    """A cancelled paid Algenta org must land on the free-forever Community tier `algenta_free`
    (1 device, keeps the newest) — NOT the generic cloud-only `free` whose entitlement has an empty
    products dict and would strip the engine grant entirely. This is the downgrade-target fix."""
    cus = f"cus_{uuid.uuid4().hex}"
    # device 0 heartbeated most recently (newest) → survives the re-cap to 1 device.
    org_id, device_ids = await _seed(OrgPlan.ALGENTA_PRO, cus, [1, 2, 3])
    await _process(_event("customer.subscription.deleted", cus))

    assert await _org_plan(org_id) == OrgPlan.ALGENTA_FREE  # NOT OrgPlan.FREE
    statuses = await _statuses(org_id)
    assert statuses[device_ids[0]] == DeviceStatus.ACTIVE  # free-forever node kept
    assert statuses[device_ids[1]] == DeviceStatus.REVOKED
    assert statuses[device_ids[2]] == DeviceStatus.REVOKED
    actions = await _audit_actions(org_id)
    assert AuditAction.ENTITLEMENT_REVOKED.value in actions
    assert AuditAction.DEVICE_REVOKED.value in actions


@pytest.mark.anyio
async def test_telys_cancel_downgrades_to_telys_developer() -> None:
    """Same product-namespaced downgrade for Telys: cancel lands on telys_developer, not generic free."""
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, device_ids = await _seed(OrgPlan.TELYS_PRO, cus, [1, 2])
    await _process(_event("customer.subscription.deleted", cus))
    assert await _org_plan(org_id) == OrgPlan.TELYS_DEVELOPER
    statuses = await _statuses(org_id)
    assert statuses[device_ids[0]] == DeviceStatus.ACTIVE  # 1-node Community tier keeps newest
    assert statuses[device_ids[1]] == DeviceStatus.REVOKED


# ── dunning-exhausted delinquency downgrades; transient past_due does NOT ────────


@pytest.mark.anyio
async def test_delinquent_unpaid_downgrades_to_community() -> None:
    """Dunning exhausted (subscription status `unpaid`) downgrades to the product Community tier
    BEFORE the eventual delete — so a delinquent monthly subscriber loses paid entitlement within
    ~one cycle instead of weeks later when Stripe finally cancels."""
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, device_ids = await _seed(OrgPlan.ALGENTA_PRO, cus, [1, 2, 3])  # algenta_pro cap 3
    await _process(_event("customer.subscription.updated", cus, status="unpaid"))
    assert await _org_plan(org_id) == OrgPlan.ALGENTA_FREE
    statuses = await _statuses(org_id)
    # re-capped to the 1-node Community tier: newest kept, the rest revoked.
    assert statuses[device_ids[0]] == DeviceStatus.ACTIVE
    assert statuses[device_ids[1]] == DeviceStatus.REVOKED
    assert statuses[device_ids[2]] == DeviceStatus.REVOKED
    assert AuditAction.ENTITLEMENT_REVOKED.value in await _audit_actions(org_id)


@pytest.mark.anyio
async def test_past_due_keeps_plan_and_does_not_downgrade(monkeypatch) -> None:
    """`past_due` is inside Stripe's retry window (a transient decline that may recover) — it must
    NOT downgrade a paying customer to Community. Only terminal dunning states (unpaid/canceled/
    incomplete_expired) do; a genuine cancellation still arrives as subscription.deleted."""
    monkeypatch.setattr(
        billing,
        "_get_settings",
        lambda: types.SimpleNamespace(stripe_price_algenta_pro="price_algenta_pro_test"),
    )
    cus = f"cus_{uuid.uuid4().hex}"
    org_id, _ = await _seed(OrgPlan.ALGENTA_PRO, cus, [1, 2])
    # per-device plan: quantity=3 licensed devices → the 2 active devices stay within the cap.
    await _process(
        _event(
            "customer.subscription.updated",
            cus,
            status="past_due",
            items={"data": [{"price": {"id": "price_algenta_pro_test"}, "quantity": 3}]},
        )
    )
    assert await _org_plan(org_id) == OrgPlan.ALGENTA_PRO  # kept — past_due is not terminal
    statuses = await _statuses(org_id)
    assert all(st == DeviceStatus.ACTIVE for st in statuses.values())
