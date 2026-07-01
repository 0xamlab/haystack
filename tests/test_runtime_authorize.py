"""GET /v1/runtime/authorize — the server-to-server gate the packages.telys.ai runtime host calls to validate a
self-service bundle download. A valid API key whose plan grants products.telys → 200 + entitlement; a plan
without the Telys runtime → 403. (API-key verification itself has its own tests; here we override the auth dep to
pin the entitlement logic.)
"""
from __future__ import annotations

from apps.api_server.middleware.auth import get_current_org


async def test_authorize_grants_telys_plan(client, app):
    app.dependency_overrides[get_current_org] = lambda: {
        "org_id": "o1",
        "user_id": "u1",
        "email": "dev@example.com",
        "plan": "telys_developer",
    }
    try:
        r = await client.get("/v1/runtime/authorize", headers={"authorization": "Bearer sk_key"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["authorized"] is True
        assert body["product"] == "telys"
        assert "local_runtime" in body["features"]
    finally:
        app.dependency_overrides.pop(get_current_org, None)


async def test_authorize_denies_free_plan(client, app):
    app.dependency_overrides[get_current_org] = lambda: {"org_id": "o1", "plan": "free"}
    try:
        r = await client.get("/v1/runtime/authorize", headers={"authorization": "Bearer sk_key"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_org, None)


async def test_authorize_denies_codna_only_plan(client, app):
    # A Codna plan (products {codna}, no telys) must not unlock the Telys runtime download.
    app.dependency_overrides[get_current_org] = lambda: {"org_id": "o1", "plan": "pro"}
    try:
        r = await client.get("/v1/runtime/authorize", headers={"authorization": "Bearer sk_key"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_org, None)
