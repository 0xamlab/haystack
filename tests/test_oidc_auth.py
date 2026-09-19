"""DB-free tests for the generic-OIDC access-token verifier (services/oidc_auth.py).

Crafts real RS256 tokens with a locally-generated key and monkeypatches the JWKS fetch, so
every trust rule is exercised offline: audience scoping, exact-issuer match, client-app
allowlist, expiry, user-vs-app principal classification, roles extraction (top-level and
Keycloak's realm_access.roles shape), the nonce/ID-token reject, and the fail-closed
unconfigured posture.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKSet

from apps.api_server.services import oidc_auth
from apps.api_server.services.oidc_auth import (
    OidcAuthError,
    looks_like_oidc_token,
    verify_oidc_token,
)

ISSUER = "https://idp.example.com/realms/acme"
OTHER_ISSUER = "https://idp.example.com/realms/other"
AUDIENCE = "algenta-gateway"
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
    oidc_issuer = ISSUER
    oidc_audience = AUDIENCE
    oidc_jwks_url = "https://idp.example.com/realms/acme/protocol/openid-connect/certs"
    oidc_allowed_client_apps: str | None = None
    oidc_auto_provision = False


def _token(
    *,
    iss: str | None = None,
    aud: str = AUDIENCE,
    sub: str | None = None,
    exp_delta: int = 600,
    scope: str | None = "decisions.read",
    roles: list[str] | None = None,
    realm_roles: list[str] | None = None,
    azp: str | None = "client-app-1",
    client_id: str | None = None,
    kid: str = KID,
    nonce: str | None = None,
    preferred_username: str = "user@acme.example",
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": iss if iss is not None else ISSUER,
        "aud": aud,
        "sub": sub if sub is not None else "subject-1",
        "iat": now,
        "exp": now + exp_delta,
        "preferred_username": preferred_username,
        "name": "Test User",
    }
    if scope is not None:
        claims["scope"] = scope
    if roles is not None:
        claims["roles"] = roles
    if realm_roles is not None:
        claims["realm_access"] = {"roles": realm_roles}
    if azp is not None:
        claims["azp"] = azp
    if client_id is not None:
        claims["client_id"] = client_id
    if nonce is not None:
        claims["nonce"] = nonce
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch):
    settings = _Settings()
    monkeypatch.setattr(oidc_auth, "get_settings", lambda: settings)

    async def fake_fetch(*, force: bool = False) -> PyJWKSet:
        return _jwks()

    monkeypatch.setattr(oidc_auth, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(oidc_auth, "_jwks_cache", None)
    monkeypatch.setattr(oidc_auth, "_last_forced_jwks_refetch", 0.0)
    yield settings


def _verify(token: str):
    return asyncio.run(verify_oidc_token(token))


def test_valid_user_token_yields_user_principal(_patch) -> None:
    principal = _verify(_token())
    assert principal.issuer == ISSUER
    assert principal.subject == "subject-1"
    assert principal.principal_type == "user"
    assert "decisions.read" in principal.scopes
    assert principal.client_id == "client-app-1"
    assert principal.principal_ref == f"oidc:{ISSUER}:subject-1"


def test_client_credentials_token_yields_app_principal(_patch) -> None:
    # client-credentials (machine-to-machine) shape: sub == azp/client_id, no scope required.
    principal = _verify(_token(sub="svc-client", azp="svc-client", scope=None))
    assert principal.principal_type == "app"
    assert principal.client_id == "svc-client"


def test_keycloak_service_account_token_yields_app_principal(_patch) -> None:
    # Regression (found via a live Keycloak container, not synthetic tokens): Keycloak's own
    # client-credentials grant mints a dedicated service-account USER whose sub is its own UUID —
    # NEVER equal to azp/client_id — so the sub==client_id check alone misclassifies it as "user".
    # Keycloak always names that user "service-account-<client-id>"; that's the real signal.
    principal = _verify(
        _token(
            sub="90b2e441-f049-41bf-b467-9ce85b36a24d",
            azp="algenta-gateway",
            scope="profile email",
            realm_roles=["default-roles-acme", "offline_access", "uma_authorization"],
            preferred_username="service-account-algenta-gateway",
        )
    )
    assert principal.principal_type == "app"
    assert principal.subject == "90b2e441-f049-41bf-b467-9ce85b36a24d"
    assert principal.client_id == "algenta-gateway"


def test_keycloak_shaped_but_human_username_stays_user(_patch) -> None:
    # The service-account-prefix check must not overreach: a real end-user token with the same
    # sub != client_id shape but an ordinary preferred_username stays classified as "user".
    principal = _verify(
        _token(
            sub="90b2e441-f049-41bf-b467-9ce85b36a24d",
            azp="algenta-gateway",
            scope="profile email",
            realm_roles=["default-roles-acme"],
            preferred_username="jane.doe@acme.example",
        )
    )
    assert principal.principal_type == "user"


def test_wrong_audience_is_rejected(_patch) -> None:
    with pytest.raises(OidcAuthError) as e:
        _verify(_token(aud="some-other-api"))
    assert e.value.code == "wrong_audience"


def test_wrong_issuer_is_rejected(_patch) -> None:
    with pytest.raises(OidcAuthError) as e:
        _verify(_token(iss=OTHER_ISSUER))
    assert e.value.code == "wrong_issuer"


def test_expired_token_is_rejected(_patch) -> None:
    with pytest.raises(OidcAuthError) as e:
        _verify(_token(exp_delta=-120))
    assert e.value.code == "token_expired"


def test_client_app_allowlist_is_enforced(_patch) -> None:
    _patch.oidc_allowed_client_apps = "expected-app"
    with pytest.raises(OidcAuthError) as e:
        _verify(_token(azp="client-app-1"))
    assert e.value.code == "client_app_not_allowed"
    _patch.oidc_allowed_client_apps = "client-app-1"
    assert _verify(_token(azp="client-app-1")).client_id == "client-app-1"


def test_missing_subject_is_rejected(_patch) -> None:
    with pytest.raises(OidcAuthError) as e:
        _verify(_token(sub=""))
    assert e.value.code == "missing_subject"


def test_unknown_kid_is_rejected(_patch) -> None:
    with pytest.raises(OidcAuthError) as e:
        _verify(_token(kid="rotated-away"))
    assert e.value.code == "unknown_kid"


def test_unconfigured_gateway_fails_closed(_patch) -> None:
    _patch.oidc_issuer = ""
    with pytest.raises(OidcAuthError) as e:
        _verify(_token())
    assert e.value.code == "not_configured"


# ── oidc_authorization_server_issuer (RFC 9728 discovery) ──────────────────────


def test_authorization_server_issuer_is_the_configured_issuer(_patch) -> None:
    assert oidc_auth.oidc_authorization_server_issuer() == ISSUER


def test_authorization_server_issuer_none_when_unconfigured(_patch) -> None:
    _patch.oidc_issuer = ""
    assert oidc_auth.oidc_authorization_server_issuer() is None


def test_looks_like_oidc_token_routing(_patch) -> None:
    assert looks_like_oidc_token(_token()) is True
    assert looks_like_oidc_token("algenta_sk_notajwt") is False
    other = jwt.encode({"iss": "https://example.com"}, "secret", algorithm="HS256")
    assert looks_like_oidc_token(other) is False
    wrong_realm = _token(iss=OTHER_ISSUER)
    assert looks_like_oidc_token(wrong_realm) is False  # different issuer, not routed
    # substring-spoof: the configured issuer as a path segment of a hostile issuer must NOT route
    spoof = _token(iss=f"https://evil.example/{ISSUER}")
    assert looks_like_oidc_token(spoof) is False
    at_spoof = _token(iss=ISSUER + ".evil.example")
    assert looks_like_oidc_token(at_spoof) is False


def test_id_token_with_nonce_is_rejected(_patch) -> None:
    with pytest.raises(OidcAuthError) as e:
        _verify(_token(nonce="n-abc123"))
    assert e.value.code == "not_api_access_token"


def test_access_token_without_nonce_still_accepted(_patch) -> None:
    principal = _verify(_token())  # default carries scope, no nonce
    assert principal.principal_type == "user"


def test_no_scope_no_role_not_client_credentials_is_rejected(_patch) -> None:
    # An ID-token-shaped bearer with no scope/role and sub != azp must be refused.
    with pytest.raises(OidcAuthError) as e:
        _verify(_token(scope=None, roles=None))
    assert e.value.code == "not_api_access_token"


def test_roles_extraction_top_level(_patch) -> None:
    principal = _verify(_token(scope=None, roles=["decisions.admin"]))
    assert principal.roles == ("decisions.admin",)


def test_roles_extraction_realm_access_shape(_patch) -> None:
    principal = _verify(_token(scope=None, realm_roles=["decisions.viewer"]))
    assert principal.roles == ("decisions.viewer",)


def test_unknown_kid_flood_forces_at_most_one_refetch(_patch, monkeypatch) -> None:
    forced_calls = {"n": 0}

    async def counting_fetch(*, force: bool = False):
        if force:
            forced_calls["n"] += 1
        return _jwks()  # never contains the attacker's random kid

    monkeypatch.setattr(oidc_auth, "_fetch_jwks", counting_fetch)

    for _ in range(8):  # a flood of tokens bearing never-valid random kids
        with pytest.raises(OidcAuthError) as e:
            _verify(_token(kid=f"random-{uuid.uuid4().hex}"))
        assert e.value.code == "unknown_kid"
    assert forced_calls["n"] == 1, f"expected 1 forced refetch, got {forced_calls['n']}"


# ── signature/forgery: the unverified iss pre-read may route, never admit ────────────────────────


def _b64url_json(obj: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def _tamper_signature(token: str) -> str:
    header, payload, sig = token.split(".")
    flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
    return f"{header}.{payload}.{flipped}"


def test_tampered_signature_is_rejected(_patch) -> None:
    with pytest.raises(OidcAuthError) as ei:
        _verify(_tamper_signature(_token()))
    assert ei.value.code == "invalid_token"


def test_tampered_payload_under_the_original_signature_is_rejected(_patch) -> None:
    token = _token(sub="victim")
    header, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["sub"] = "attacker"
    forged = f"{header}.{_b64url_json(claims)}.{sig}"
    assert looks_like_oidc_token(forged)  # routing-grade pre-read still matches the issuer
    with pytest.raises(OidcAuthError) as ei:
        _verify(forged)
    assert ei.value.code == "invalid_token"


def test_token_signed_by_another_key_with_our_kid_is_rejected(_patch) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "subject-1", "iat": now, "exp": now + 600,
              "scope": "decisions.read", "azp": "client-app-1"}
    forged = jwt.encode(claims, other, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(OidcAuthError) as ei:
        _verify(forged)
    assert ei.value.code == "invalid_token"


def test_unsigned_alg_none_token_is_rejected(_patch) -> None:
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "subject-1", "iat": now, "exp": now + 600,
              "scope": "decisions.read"}
    unsigned = f"{_b64url_json({'alg': 'none', 'typ': 'JWT', 'kid': KID})}.{_b64url_json(claims)}."
    assert looks_like_oidc_token(unsigned)
    with pytest.raises(OidcAuthError) as ei:
        _verify(unsigned)
    assert ei.value.code == "invalid_token"


def test_unreadable_payload_is_not_routed_and_is_rejected(_patch) -> None:
    header, _payload, sig = _token().split(".")
    garbage = f"{header}.!!not-base64url!!.{sig}"
    assert looks_like_oidc_token(garbage) is False
    with pytest.raises(OidcAuthError) as ei:
        _verify(garbage)
    assert ei.value.code == "malformed_token"  # dies in the header/payload load, before any key
