"""GET /v1/products/{product}/whoami — the caller-scoped CLI-login diagnosis (routers/account.py).

The device-count probe is best-effort ("diagnostics must never 500"), and when it fails the
client must get a generic message plus a correlation id — never the exception text, which can
carry driver messages, hostnames, file paths or stack detail. The full text is logged server-side
under that correlation id.
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from apps.api_server.models.api_key import APIKey
from apps.api_server.models.identity_org_link import IdentityOrgLink
from apps.api_server.models.organization import OrgPlan
from apps.api_server.services import device_service, website_identity
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403

_SECRET_MARKERS = ("db.internal", "/srv/secret", "OperationalError", "password=hunter2")


async def _seed_linked_identity() -> tuple[str, UUID]:
    _raw_key, api_key_id = await _seed_api_key(  # noqa: F405
        label="Whoami Diag", expires_at=None, plan=OrgPlan.ALGENTA_SERVER
    )
    supabase_uid = f"sb-{uuid4().hex}"
    async with AsyncSessionLocal() as session:  # noqa: F405
        org_id = (
            await session.execute(select(APIKey.org_id).where(APIKey.id == UUID(api_key_id)))
        ).scalar_one()
        session.add(IdentityOrgLink(supabase_uid=supabase_uid, org_id=org_id))
        await session.commit()
    return supabase_uid, org_id


@pytest.mark.anyio
async def test_device_count_failure_is_generic_with_correlation_id(client, monkeypatch) -> None:
    supabase_uid, org_id = await _seed_linked_identity()

    async def fake_verify_identity(authorization):  # noqa: ARG001
        return {"supabase_uid": supabase_uid, "email": "diag@example.com", "provider": "github"}

    async def exploding_list_devices(*_a, **_k):
        raise RuntimeError(
            'psycopg2.OperationalError: connection to server at "db.internal" failed '
            "(password=hunter2) while reading /srv/secret/devices.sql"
        )

    monkeypatch.setattr(website_identity, "verify_identity", fake_verify_identity)
    monkeypatch.setattr(device_service, "list_devices_with_activity", exploding_list_devices)

    resp = await client.get(
        "/v1/products/algenta/whoami", headers={"Authorization": "Bearer diag-token"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supabase_uid"] == supabase_uid
    assert body["resolved_org_id"] == str(org_id)
    assert body["device_count"] is None

    error = body["device_count_error"]
    assert re.fullmatch(r"device lookup failed; correlation id [A-Za-z0-9_-]{8,}", error), error
    for marker in _SECRET_MARKERS:
        assert marker not in resp.text, marker


@pytest.mark.anyio
async def test_device_count_success_still_reports_a_number(client, monkeypatch) -> None:
    supabase_uid, _org_id = await _seed_linked_identity()

    async def fake_verify_identity(authorization):  # noqa: ARG001
        return {"supabase_uid": supabase_uid, "email": "diag@example.com", "provider": "github"}

    monkeypatch.setattr(website_identity, "verify_identity", fake_verify_identity)

    resp = await client.get(
        "/v1/products/algenta/whoami", headers={"Authorization": "Bearer diag-token"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["device_count"] == 0
    assert "device_count_error" not in body
