"""DB-free tests for the Entra ID access-token verifier (services/entra_auth.py).

Crafts real RS256 tokens with a locally-generated key and monkeypatches the JWKS fetch, so
every trust rule is exercised offline: audience scoping (Graph/ARM tokens rejected), v2-only
issuer, tenant allowlist, client-app allowlist, expiry, delegated-vs-app principals, and the
fail-closed unconfigured posture.
"""

from __future__ import annotations

import asyncio
import base64
import time
import uuid
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKSet

from apps.api_server.services import entra_auth
from apps.api_server.services.entra_auth import (
    EntraAuthError,
    looks_like_entra_token,
    verify_entra_token,
)

TENANT = str(uuid.uuid4())
OTHER_TENANT = str(uuid.uuid4())
AUDIENCE = "api://algenta-gateway"
KID = "test-kid-1"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64url_uint(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _jwks() -> PyJWKSet:
    pub = _PRIVATE_KEY.public_key().public_numbers()
    return PyJWKSet.from_dict(
        {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "kid": KID,
                    "n": _b64url_uint(pub.n),
                    "e": _b64url_uint(pub.e),
                }
            ]
        }
    )


class _Settings:
    entra_tenant_id = TENANT
    entra_audience = AUDIENCE
    entra_allowed_tenants: str | None = None
    entra_allowed_client_apps: str | None = None


def _token(
    *,
    tid: str = TENANT,
    aud: str = AUDIENCE,
    iss: str | None = None,
    oid: str | None = None,
    exp_delta: int = 600,
    scp: str | None = "Decision.ReadWrite",
    roles: list[str] | None = None,
    idtyp: str | None = None,
    azp: str | None = "client-app-1",
    kid: str = KID,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": iss if iss is not None else f"https://login.microsoftonline.com/{tid}/v2.0",
        "aud": aud,
        "sub": "subject-1",
        "tid": tid,
        "oid": oid if oid is not None else str(uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + exp_delta,
        "preferred_username": "user@contoso.com",
        "name": "Test User",
    }
    if scp is not None:
        claims["scp"] = scp
    if roles is not None:
        claims["roles"] = roles
    if idtyp is not None:
        claims["idtyp"] = idtyp
    if azp is not None:
        claims["azp"] = azp
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch):
    settings = _Settings()
    monkeypatch.setattr(entra_auth, "get_settings", lambda: settings)

    async def fake_fetch(tenant_id: str, *, force: bool = False) -> PyJWKSet:
        return _jwks()

    monkeypatch.setattr(entra_auth, "_fetch_jwks", fake_fetch)
    entra_auth._jwks_cache.clear()
    yield settings


def _verify(token: str):
    return asyncio.run(verify_entra_token(token))


def test_valid_delegated_token_yields_user_principal(_patch) -> None:
    principal = _verify(_token())
    assert principal.tenant_id == TENANT
    assert principal.principal_type == "user"
    assert "Decision.ReadWrite" in principal.scopes
    assert principal.client_app_id == "client-app-1"
    assert principal.principal_ref.startswith(f"entra:{TENANT}:")


def test_app_only_token_yields_app_principal(_patch) -> None:
    principal = _verify(_token(scp=None, roles=["Decision.Analyst"], idtyp="app"))
    assert principal.principal_type == "app"
    assert principal.roles == ("Decision.Analyst",)


def test_graph_token_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(aud="https://graph.microsoft.com"))
    assert e.value.code == "wrong_resource_token"


def test_graph_appid_audience_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(aud="00000003-0000-0000-c000-000000000000"))
    assert e.value.code == "wrong_resource_token"


def test_arm_token_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(aud="https://management.azure.com"))
    assert e.value.code == "wrong_resource_token"


def test_other_app_audience_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(aud="api://some-other-api"))
    assert e.value.code == "wrong_audience"


def test_v1_issuer_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(iss=f"https://sts.windows.net/{TENANT}/"))
    assert e.value.code == "wrong_issuer"


def test_foreign_tenant_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(tid=OTHER_TENANT))
    assert e.value.code == "tenant_not_allowed"


def test_allowlisted_extra_tenant_is_accepted(_patch) -> None:
    _patch.entra_allowed_tenants = OTHER_TENANT
    principal = _verify(_token(tid=OTHER_TENANT))
    assert principal.tenant_id == OTHER_TENANT


def test_expired_token_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(exp_delta=-120))
    assert e.value.code == "token_expired"


def test_client_app_allowlist_is_enforced(_patch) -> None:
    _patch.entra_allowed_client_apps = "expected-app"
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(azp="client-app-1"))
    assert e.value.code == "client_app_not_allowed"
    _patch.entra_allowed_client_apps = "client-app-1"
    assert _verify(_token(azp="client-app-1")).client_app_id == "client-app-1"


def test_missing_oid_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(oid=""))
    assert e.value.code == "missing_oid"


def test_unknown_kid_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(kid="rotated-away"))
    assert e.value.code == "unknown_kid"


def test_unconfigured_gateway_fails_closed(_patch) -> None:
    _patch.entra_tenant_id = ""
    with pytest.raises(EntraAuthError) as e:
        _verify(_token())
    assert e.value.code == "not_configured"


def test_looks_like_entra_token_routing(_patch) -> None:
    assert looks_like_entra_token(_token()) is True
    assert looks_like_entra_token("algenta_sk_notajwt") is False
    other = jwt.encode({"iss": "https://example.com"}, "secret", algorithm="HS256")
    assert looks_like_entra_token(other) is False
    v1 = _token(iss=f"https://sts.windows.net/{TENANT}/")
    assert looks_like_entra_token(v1) is True  # routed to the verifier, which rejects it
    # substring-spoof: the Entra host as a path segment of a hostile issuer must NOT route
    spoof = _token(iss=f"https://evil.example/login.microsoftonline.com/{TENANT}/v2.0")
    assert looks_like_entra_token(spoof) is False
    at_spoof = _token(iss=f"https://login.microsoftonline.com.evil.example/{TENANT}/v2.0")
    assert looks_like_entra_token(at_spoof) is False
