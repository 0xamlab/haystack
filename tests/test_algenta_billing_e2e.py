"""End-to-end: an Algenta paid upgrade lands on org.plan, enforces per-device, and lapses to Community.

Chains the whole anti-pay-once-leave + per-device flow in one test, with algenta billing ON:
  checkout.completed(metadata.org_id, plan=algenta_pro)  -> org.plan = algenta_pro
  subscription.updated(algenta_pro price, quantity=3)     -> licensed_devices = 3
  register 3 devices                                      -> OK; a 4th is refused (org-wide ceiling)
  issued license JWT                                      -> plan + device_limit=3 + active_node_limit=3
  subscription.deleted                                    -> downgrades to Community (algenta_free),
                                                            re-caps devices to 1 (no lockout, non-'free')
"""
from __future__ import annotations

import types
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.api_key import APIKey
from apps.api_server.models.device import DeviceRegistration, DeviceStatus
from apps.api_server.models.organization import Organization, OrgPlan
from apps.api_server.routers import billing
from apps.api_server.services.device_service import register_device
from apps.api_server.services.product_registry import product_flag
from tests._test_api_key_expiry_contract_helpers import _seed_api_key

_ALGENTA_PRO_PRICE = "price_algenta_pro_e2e"


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


async def _org(org_id: str) -> Organization:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(Organization).where(Organization.id == uuid.UUID(org_id)))
        ).scalar_one()


def _dev(i: int) -> dict:
    return {
        "device_id": f"e2e-device-{uuid.uuid4().hex}",
        "platform": "linux",
        "platform_version": "6.8",
        "hostname_hash": "h" * 16,
        "sdk_version": "1.0",
        "device_pubkey_thumbprint": f"ed25519:{i}",
    }


def test_algenta_billing_flag_is_on() -> None:
    # Go-live sanity: the product-level billing gate is open for algenta (credential gate still applies).
    assert product_flag("algenta", "billing", default=True) is True


@pytest.mark.anyio
async def test_algenta_paid_upgrade_enforces_then_lapses_to_community(monkeypatch) -> None:
    monkeypatch.setattr(
        billing,
        "_get_settings",
        lambda: types.SimpleNamespace(stripe_price_algenta_pro=_ALGENTA_PRO_PRICE),
    )
    cus = f"cus_{uuid.uuid4().hex}"
    raw_key, key_id = await _seed_api_key(
        label="e2e", expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ALGENTA_FREE
    )
    async with AsyncSessionLocal() as s:
        org = (
            await s.execute(
                select(Organization).where(
                    Organization.id
                    == (
                        await s.execute(select(APIKey.org_id).where(APIKey.id == uuid.UUID(key_id)))
                    ).scalar_one()
                )
            )
        ).scalar_one()
        org_id = str(org.id)
        org.stripe_customer_id = cus
        await s.commit()

    # 1) Checkout completes → the paid plan lands on org.plan (the webhook is the writer).
    await _process(
        _event(
            "checkout.session.completed",
            cus,
            metadata={"org_id": org_id, "plan": "algenta_pro"},
            subscription=f"sub_{uuid.uuid4().hex}",
        )
    )
    assert (await _org(org_id)).plan == OrgPlan.ALGENTA_PRO

    # 2) Subscription quantity (=3 devices) syncs the licensed device count.
    await _process(
        _event(
            "customer.subscription.updated",
            cus,
            status="active",
            items={"data": [{"price": {"id": _ALGENTA_PRO_PRICE}, "quantity": 3}]},
        )
    )
    assert (await _org(org_id)).licensed_devices == 3

    # 3) Enforcement: exactly 3 devices register; the 4th is refused by the org-wide licensed ceiling.
    last_result = None
    async with AsyncSessionLocal() as s:
        for i in range(3):
            last_result = await register_device(raw_key, _dev(i), s)
            await s.commit()
    assert last_result is not None
    # The 4th device is refused — here by the per-key gate (all devices are on one key), capped at the
    # licensed count of 3. The org-WIDE ceiling across multiple keys is covered by test_per_device_quantity.
    with pytest.raises(ValueError, match="limit reached"):
        async with AsyncSessionLocal() as s:
            await register_device(raw_key, _dev(99), s)
            await s.commit()

    # 4) The issued license carries the paid plan + the purchased caps (online + offline census).
    claims = jwt.decode(last_result["license_token"], options={"verify_signature": False})
    assert claims["plan"] == "algenta_pro"
    assert claims["device_limit"] == 3
    assert claims["active_node_limit"] == 3

    # 5) Cancellation → downgrade to Community (algenta_free, NOT generic 'free'), devices re-capped to 1.
    await _process(_event("customer.subscription.deleted", cus))
    assert (await _org(org_id)).plan == OrgPlan.ALGENTA_FREE
    async with AsyncSessionLocal() as s:
        active = (
            await s.execute(
                select(DeviceRegistration).where(
                    DeviceRegistration.org_id == uuid.UUID(org_id),
                    DeviceRegistration.status == DeviceStatus.ACTIVE,
                )
            )
        ).scalars().all()
    assert len(active) == 1  # the free-forever device survives; the rest revoked
