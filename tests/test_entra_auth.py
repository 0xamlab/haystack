"""DB-free tests for the Entra ID access-token verifier (services/entra_auth.py).

Crafts real RS256 tokens with a locally-generated key and monkeypatches the JWKS fetch, so
every trust rule is exercised offline: audience scoping (Graph/ARM tokens rejected), v2-only
issuer, tenant allowlist, client-app allowlist, expiry, delegated-vs-app principals, and the
fail-closed unconfigured posture.
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
    nonce: str | None = None,
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
    if nonce is not None:
        claims["nonce"] = nonce
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


def test_app_only_aud_is_bare_client_id_accepted_against_uri_config(_patch) -> None:
    # Verified against a REAL Entra token: an app-only (client-credentials) token's `aud` is the bare
    # client-id GUID, NOT the App ID URI. With ALGENTA_ENTRA_AUDIENCE="api://<id>" the gateway must
    # STILL accept it — otherwise every service / managed-identity caller (a Foundry agent, scheduled
    # eval, automated refresh) is rejected with wrong_audience.
    bare = AUDIENCE[len("api://") :]  # "algenta-gateway"
    principal = _verify(_token(aud=bare, scp=None, roles=["Decisions.Service"], idtyp="app"))
    assert principal.principal_type == "app"
    assert principal.roles == ("Decisions.Service",)


def test_delegated_uri_aud_accepted_against_bare_client_id_config(_patch) -> None:
    # Symmetric: configured with the bare client id, a delegated token carrying the App ID URI aud
    # (api://<id>) is accepted too. One ALGENTA_ENTRA_AUDIENCE serves both identity shapes.
    _patch.entra_audience = AUDIENCE[len("api://") :]  # configure the bare client id
    principal = _verify(_token(aud=AUDIENCE))  # token aud = "api://algenta-gateway"
    assert principal.tenant_id == TENANT


def test_accepted_audiences_expands_uri_and_bare_both_directions(_patch) -> None:
    from apps.api_server.services.entra_auth import _accepted_audiences

    assert _accepted_audiences(_patch) == ["api://algenta-gateway", "algenta-gateway"]
    _patch.entra_audience = "algenta-gateway"
    assert _accepted_audiences(_patch) == ["algenta-gateway", "api://algenta-gateway"]


def test_unrelated_audience_still_rejected(_patch) -> None:
    # The URI<->bare expansion must NOT broaden acceptance to any OTHER audience.
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(aud="api://some-other-api"))
    assert e.value.code == "wrong_audience"


def test_delegated_user_with_app_roles_but_no_scp_stays_user(_patch) -> None:
    # #321 review (HIGH): a delegated USER token under an app-role assignment carries roles +
    # no scp + no idtyp. It must classify as "user" (NOT "app") — the resolver would otherwise
    # grant it a service allowance.
    principal = _verify(_token(scp=None, roles=["App.Access"], idtyp=None))
    assert principal.principal_type == "user"
    assert principal.roles == ("App.Access",)


def test_id_token_without_scope_or_role_is_rejected(_patch) -> None:
    # #321 review: an ID token (no scp, no roles, no idtyp) replayed as an API bearer must be
    # refused even if its aud is the app's client id.
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(scp=None, roles=None, idtyp=None))
    assert e.value.code == "not_api_access_token"


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


# ── entra_authorization_server_issuers (RFC 9728 discovery) ────────────────────


def test_authorization_server_issuers_lists_the_configured_tenant(_patch) -> None:
    assert entra_auth.entra_authorization_server_issuers() == (
        f"https://login.microsoftonline.com/{TENANT}/v2.0",
    )


def test_authorization_server_issuers_includes_every_allowed_tenant(_patch) -> None:
    _patch.entra_allowed_tenants = OTHER_TENANT
    assert set(entra_auth.entra_authorization_server_issuers()) == {
        f"https://login.microsoftonline.com/{TENANT}/v2.0",
        f"https://login.microsoftonline.com/{OTHER_TENANT}/v2.0",
    }


def test_authorization_server_issuers_empty_when_unconfigured(_patch) -> None:
    _patch.entra_tenant_id = ""
    assert entra_auth.entra_authorization_server_issuers() == ()


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


# ── C2: an ID token replayed as a bearer is rejected via the OIDC-only `nonce` claim, even when it
#    carries an app-role `roles` claim (the case #356's bare-GUID audience widened) ─────────────────
def test_id_token_with_nonce_is_rejected_even_with_roles(_patch) -> None:
    with pytest.raises(EntraAuthError) as e:
        _verify(_token(scp=None, roles=["App.Admin"], idtyp=None, nonce="n-abc123"))
    assert e.value.code == "not_api_access_token"


def test_access_token_without_nonce_still_accepted(_patch) -> None:
    # regression: a genuine access token (no nonce) is unaffected by the nonce reject.
    principal = _verify(_token())  # default carries scp, no nonce
    assert principal.principal_type == "user"


# ── C1: an unknown-kid FLOOD forces at most ONE live JWKS refetch per cooldown (no egress amplification) ──
def test_unknown_kid_flood_forces_at_most_one_refetch(_patch, monkeypatch) -> None:
    from apps.api_server.services import entra_auth as ea

    ea._last_forced_jwks_refetch.clear()
    forced_calls = {"n": 0}

    async def counting_fetch(tenant_id: str, *, force: bool = False):
        if force:
            forced_calls["n"] += 1
        return _jwks()  # never contains the attacker's random kid

    monkeypatch.setattr(ea, "_fetch_jwks", counting_fetch)

    for _ in range(8):  # a flood of tokens bearing never-valid random kids
        with pytest.raises(EntraAuthError) as e:
            _verify(_token(kid=f"random-{uuid.uuid4().hex}"))
        assert e.value.code == "unknown_kid"
    assert forced_calls["n"] == 1, f"expected 1 forced refetch, got {forced_calls['n']}"


# ── signature/forgery: the unverified pre-reads (iss/aud/tid) may route, never admit ─────────────


def _b64url_json(obj: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def _tamper_signature(token: str) -> str:
    header, payload, sig = token.split(".")
    flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
    return f"{header}.{payload}.{flipped}"


def test_tampered_signature_is_rejected(_patch) -> None:
    with pytest.raises(EntraAuthError) as ei:
        _verify(_tamper_signature(_token()))
    assert ei.value.code == "invalid_token"


def test_tampered_payload_under_the_original_signature_is_rejected(_patch) -> None:
    # Change a claim (oid) but keep the genuine signature: the pre-read still sees an allowed
    # tenant (so routing and JWKS selection happen), and the verified decode then fails. A forged
    # claim can select a verifier or a key set, never become identity.
    token = _token(oid="victim-oid")
    header, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["oid"] = "attacker-oid"
    forged = f"{header}.{_b64url_json(claims)}.{sig}"
    assert looks_like_entra_token(forged)  # routing-grade pre-read still says "Entra"
    with pytest.raises(EntraAuthError) as ei:
        _verify(forged)
    assert ei.value.code == "invalid_token"


def test_token_signed_by_another_key_with_our_kid_is_rejected(_patch) -> None:
    # The attacker knows the tenant, audience and kid (all public) and signs with their own key.
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "aud": AUDIENCE,
        "sub": "subject-1",
        "tid": TENANT,
        "oid": str(uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + 600,
        "scp": "Decision.ReadWrite",
        "azp": "client-app-1",
    }
    forged = jwt.encode(claims, other, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(EntraAuthError) as ei:
        _verify(forged)
    assert ei.value.code == "invalid_token"


def test_unsigned_alg_none_token_is_rejected(_patch) -> None:
    now = int(time.time())
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "aud": AUDIENCE,
        "sub": "subject-1",
        "tid": TENANT,
        "oid": str(uuid.uuid4()),
        "iat": now,
        "exp": now + 600,
        "scp": "Decision.ReadWrite",
    }
    unsigned = f"{_b64url_json({'alg': 'none', 'typ': 'JWT', 'kid': KID})}.{_b64url_json(claims)}."
    assert looks_like_entra_token(unsigned)  # it routes here — and must die here
    with pytest.raises(EntraAuthError) as ei:
        _verify(unsigned)
    assert ei.value.code == "invalid_token"


def test_unreadable_payload_is_malformed_not_routed(_patch) -> None:
    header, _payload, sig = _token().split(".")
    garbage = f"{header}.!!not-base64url!!.{sig}"
    assert looks_like_entra_token(garbage) is False
    with pytest.raises(EntraAuthError) as ei:
        _verify(garbage)
    assert ei.value.code == "malformed_token"
