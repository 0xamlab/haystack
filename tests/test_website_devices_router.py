"""Website/dashboard self-service device management — GET/DELETE /account/devices (Supabase auth).

The Supabase verifier + org resolver have their own tests; here we pin the dashboard contract against
the REAL device store: a signed-in user can list their org's devices (with seat/active info) and
revoke one to free a seat, can only ever touch their OWN org's devices, and the surface is inert
(503) until Supabase is configured / 401 without a bearer.
"""

from __future__ import annotations

import uuid

import pytest

from apps.api_server.models.api_key import APIKey
from apps.api_server.services import byok_org_resolver, supabase_auth
from apps.api_server.services.auth_service import hash_api_key
from tests._test_api_key_expiry_contract_helpers import *  # noqa: F401,F403

_IDENT = {"supabase_uid": "sb-uuid-octocat", "github_user_id": 583231, "github_login": "octocat", "email": "octocat@example.com", "provider": "github"}
_BEARER = {"Authorization": "Bearer JWT"}


class _Org:
    def __init__(self, org_id: uuid.UUID) -> None:
        self.id = org_id


async def _org_id_for(raw_key: str) -> uuid.UUID:
    async with AsyncSessionLocal() as session:  # noqa: F405
        return (
            await session.execute(select(APIKey.org_id).where(APIKey.hashed_key == hash_api_key(raw_key)))  # noqa: F405
        ).scalar_one()


def _stub_supabase(monkeypatch: pytest.MonkeyPatch, *, configured: bool = True, org: _Org | None = None) -> None:
    monkeypatch.setattr(supabase_auth, "supabase_configured", lambda: configured)

    async def _verify(_token: str) -> dict:
        return {"verified": True}

    monkeypatch.setattr(supabase_auth, "verify_supabase_jwt", _verify)
    monkeypatch.setattr(supabase_auth, "extract_identity", lambda _claims: _IDENT)
    monkeypatch.setattr(supabase_auth, "extract_github_identity", lambda _claims: _IDENT)

    async def _resolve(_db, *, supabase_uid=None, email=None, github_user_id=None, github_login=None, redis=None, selected_org_id=None, auto_provision=False):  # noqa: ANN001
        return org

    monkeypatch.setattr(byok_org_resolver, "resolve_org_for_supabase_user", _resolve)


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


async def _runtime_key(client, owner_key: str) -> str:
    r = await client.post(
        "/v1/api-keys",
        headers={"X-API-Key": owner_key},
        json={"label": "rt", "expires_at": "2028-05-19T00:00:00Z", "device_limit": 5},
    )
    assert r.status_code == 201, r.text
    return r.json()["raw_key"]


@pytest.mark.anyio
async def test_dashboard_lists_and_revokes_own_devices(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    owner_key, _ = await _seed_api_key(  # noqa: F405
        label="Dash Owner",
        expires_at=datetime.now(UTC) + timedelta(days=30),  # noqa: F405
        plan=OrgPlan.ENTERPRISE,  # noqa: F405
    )
    try:
        key = await _runtime_key(client, owner_key)
        for did in ("dash-device-aaaaaa01", "dash-device-bbbbbb02"):
            assert (
                await client.post("/v1/device/register", headers={"X-API-Key": key}, json=_payload(did))
            ).status_code == 200
        org = _Org(await _org_id_for(key))
        _stub_supabase(monkeypatch, org=org)

        # The dashboard lists the user's devices with seat/active info.
        listed = await client.get("/account/devices", headers=_BEARER)
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert body["total"] == 2 and body["active"] == 2, body
        assert all("active" in d for d in body["devices"]), body
        assert listed.headers.get("Cache-Control") == "no-store"

        # The user revokes one device to free a seat — self-service.
        target = body["devices"][0]["id"]
        revoked = await client.request("DELETE", f"/account/devices/{target}", headers=_BEARER)
        assert revoked.status_code == 200 and revoked.json()["revoked"] is True, revoked.text

        after = (await client.get("/account/devices", headers=_BEARER)).json()
        assert after["total"] == 1, after
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_dashboard_cannot_touch_another_orgs_device(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    # Org A owns a device; the dashboard caller resolves to a DIFFERENT org B.
    owner_a, _ = await _seed_api_key(  # noqa: F405
        label="Org A", expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ENTERPRISE  # noqa: F405
    )
    owner_b, _ = await _seed_api_key(  # noqa: F405
        label="Org B", expires_at=datetime.now(UTC) + timedelta(days=30), plan=OrgPlan.ENTERPRISE  # noqa: F405
    )
    try:
        key_a = await _runtime_key(client, owner_a)
        assert (
            await client.post(
                "/v1/device/register", headers={"X-API-Key": key_a}, json=_payload("victim-device-00001")
            )
        ).status_code == 200
        # Find org A's device registration id (via org A's own dashboard view).
        _stub_supabase(monkeypatch, org=_Org(await _org_id_for(key_a)))
        a_devices = (await client.get("/account/devices", headers=_BEARER)).json()["devices"]
        victim_id = a_devices[0]["id"]

        # Now the caller is org B — revoking org A's device id must 404 (org-scoped), not succeed.
        _stub_supabase(monkeypatch, org=_Org(await _org_id_for(key_b := await _runtime_key(client, owner_b))))
        assert key_b  # (created under org B; ensures org B exists)
        cross = await client.request("DELETE", f"/account/devices/{victim_id}", headers=_BEARER)
        assert cross.status_code == 404, cross.text

        # Org A's device is untouched.
        _stub_supabase(monkeypatch, org=_Org(await _org_id_for(key_a)))
        assert (await client.get("/account/devices", headers=_BEARER)).json()["total"] == 1
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405


@pytest.mark.anyio
async def test_dashboard_requires_bearer_and_configured_supabase(
    client, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_stub = _RedisStub()  # noqa: F405

    async def _fake_redis() -> object:
        return redis_stub

    app.dependency_overrides[get_redis] = _fake_redis  # noqa: F405
    try:
        # Configured but no bearer -> 401.
        _stub_supabase(monkeypatch, configured=True, org=_Org(uuid.uuid4()))
        assert (await client.get("/account/devices")).status_code == 401
        # Not configured -> 503 (inert), even with a bearer.
        _stub_supabase(monkeypatch, configured=False, org=_Org(uuid.uuid4()))
        assert (await client.get("/account/devices", headers=_BEARER)).status_code == 503
    finally:
        app.dependency_overrides.pop(get_redis, None)  # noqa: F405
