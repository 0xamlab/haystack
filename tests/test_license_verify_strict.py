"""Strict JOSE license verifier (apps/runtime/license_verify.py).

Covers plan §9 cryptographic gates: alg=none, RS/HS algorithm confusion, wrong issuer/
audience/product (cross-product replay), unknown kid, missing kid, token-supplied key URLs,
missing required claims, bad signature, key rotation (old+new kid), and size bounds.
"""
from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.runtime import license_verify as lv


def _keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    return priv, pub


@pytest.fixture(scope="module")
def keys() -> dict:
    p1, pub1 = _keypair()
    p2, pub2 = _keypair()
    p_evil, _ = _keypair()
    return {
        "priv1": p1,
        "priv2": p2,
        "priv_evil": p_evil,
        "bundle": {"kid1": pub1, "kid2": pub2},
    }


def _claims(**overrides) -> dict:
    now = int(time.time())
    base = {
        "iss": "https://license.algenta.ai",
        "aud": "algenta-runtime",
        "sub": "device-license",
        "jti": "lic-123",
        "iat": now,
        "nbf": now - 10,
        "exp": now + 86400,
        "schema_version": 1,
        "product": "algenta",
        "edition": "server",
        "license_scope": "deployment",
        "deployment_class": "server",
    }
    base.update(overrides)
    return base


def _token(priv: str, *, kid: str = "kid1", typ: str = lv.LICENSE_TYP, alg: str = "RS256",
           headers: dict | None = None, **claim_overrides) -> str:
    h = {"typ": typ, "kid": kid}
    if headers:
        h.update(headers)
    return jwt.encode(_claims(**claim_overrides), priv, algorithm=alg, headers=h)


def _verify(token: str, keys: dict, **kw):
    return lv.verify_license_token(
        token, expected_product="algenta", trust_bundle=keys["bundle"], **kw
    )


# ── happy path ───────────────────────────────────────────────────────────────


def test_valid_token_verifies(keys) -> None:
    v = _verify(_token(keys["priv1"]), keys)
    assert v.kid == "kid1"
    assert v.payload["product"] == "algenta"
    assert v.payload["license_scope"] == "deployment"


def test_rotation_new_kid_also_verifies(keys) -> None:
    # kid2 shipped in the bundle ahead of a signer rotation.
    v = _verify(_token(keys["priv2"], kid="kid2"), keys)
    assert v.kid == "kid2"


# ── algorithm attacks ────────────────────────────────────────────────────────


def test_alg_none_rejected(keys) -> None:
    tok = jwt.encode(_claims(), key=None, algorithm="none", headers={"typ": lv.LICENSE_TYP, "kid": "kid1"})
    _, reason = lv.try_verify_license_token(tok, expected_product="algenta", trust_bundle=keys["bundle"])
    assert reason == "alg_not_allowed"


def test_hs256_rejected(keys) -> None:
    # The RS/HS-confusion defense: the verifier accepts RS256 only, so ANY HS256 token is
    # rejected at the alg gate before a key is ever selected. (PyJWT additionally refuses to
    # sign HS256 with a PEM key, so the classic PEM-as-secret forgery can't even be built via
    # encode — but the alg gate is the guarantee we rely on.)
    forged = jwt.encode(
        _claims(), key="attacker-chosen-secret", algorithm="HS256",
        headers={"typ": lv.LICENSE_TYP, "kid": "kid1"},
    )
    _, reason = lv.try_verify_license_token(forged, expected_product="algenta", trust_bundle=keys["bundle"])
    assert reason == "alg_not_allowed"


# ── header attacks ───────────────────────────────────────────────────────────


def test_wrong_typ_rejected(keys) -> None:
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], typ="JWT"), expected_product="algenta", trust_bundle=keys["bundle"]
    )
    assert reason == "wrong_typ"


def test_unknown_kid_rejected(keys) -> None:
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], kid="kid-unknown"), expected_product="algenta", trust_bundle=keys["bundle"]
    )
    assert reason == "kid_unknown"


def test_missing_kid_rejected(keys) -> None:
    tok = jwt.encode(_claims(), keys["priv1"], algorithm="RS256", headers={"typ": lv.LICENSE_TYP})
    _, reason = lv.try_verify_license_token(tok, expected_product="algenta", trust_bundle=keys["bundle"])
    assert reason == "kid_missing"


def test_token_supplied_key_url_rejected(keys) -> None:
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], headers={"jku": "https://evil.example/keys"}),
        expected_product="algenta", trust_bundle=keys["bundle"],
    )
    assert reason == "key_url_forbidden"


def test_unknown_crit_header_rejected(keys) -> None:
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], headers={"crit": ["exp"]}),
        expected_product="algenta", trust_bundle=keys["bundle"],
    )
    assert reason == "crit_unsupported"


# ── claim attacks ────────────────────────────────────────────────────────────


def test_wrong_issuer_rejected(keys) -> None:
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], iss="https://evil.example"),
        expected_product="algenta", trust_bundle=keys["bundle"],
    )
    assert reason == "bad_issuer"


def test_wrong_audience_rejected(keys) -> None:
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], aud="some-other-runtime"),
        expected_product="algenta", trust_bundle=keys["bundle"],
    )
    assert reason == "bad_audience"


def test_cross_product_replay_rejected(keys) -> None:
    # A Telys license must never activate Algenta.
    telys_token = _token(keys["priv1"], product="telys")
    _, reason = lv.try_verify_license_token(
        telys_token, expected_product="algenta", trust_bundle=keys["bundle"]
    )
    assert reason == "wrong_product"


def test_wrong_edition_rejected_when_expected(keys) -> None:
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], edition="workstation"),
        expected_product="algenta", expected_edition="server", trust_bundle=keys["bundle"],
    )
    assert reason == "wrong_edition"


def test_missing_required_claim_rejected(keys) -> None:
    claims = _claims()
    del claims["jti"]
    tok = jwt.encode(claims, keys["priv1"], algorithm="RS256", headers={"typ": lv.LICENSE_TYP, "kid": "kid1"})
    _, reason = lv.try_verify_license_token(tok, expected_product="algenta", trust_bundle=keys["bundle"])
    assert reason == "missing_claim"


def test_wrong_subject_rejected(keys) -> None:
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], sub="not-a-license"),
        expected_product="algenta", trust_bundle=keys["bundle"],
    )
    assert reason == "wrong_sub"


def test_bad_signature_rejected(keys) -> None:
    # Signed with an attacker key, but claims a kid whose real key is in the bundle.
    forged = _token(keys["priv_evil"], kid="kid1")
    _, reason = lv.try_verify_license_token(forged, expected_product="algenta", trust_bundle=keys["bundle"])
    assert reason == "bad_signature"


# ── size bounds ──────────────────────────────────────────────────────────────


def test_oversized_token_rejected(keys) -> None:
    big = _token(keys["priv1"], message="x" * (lv._MAX_TOKEN_BYTES))
    _, reason = lv.try_verify_license_token(big, expected_product="algenta", trust_bundle=keys["bundle"])
    assert reason == "token_size"


def test_oversized_claim_rejected(keys) -> None:
    # A claim within token bounds but over the per-claim bound.
    tok = _token(keys["priv1"], note="y" * (lv._MAX_STR_CLAIM_LEN + 1))
    _, reason = lv.try_verify_license_token(tok, expected_product="algenta", trust_bundle=keys["bundle"])
    assert reason == "claim_too_large"


# ── routing helper ───────────────────────────────────────────────────────────


def test_revoked_jti_rejected(keys) -> None:
    tok = _token(keys["priv1"], jti="lic-revoked-1")
    # not in the denylist → OK
    ok, reason = lv.try_verify_license_token(tok, expected_product="algenta", trust_bundle=keys["bundle"])
    assert ok is not None and reason == ""
    # in the denylist → rejected
    _, reason2 = lv.try_verify_license_token(
        tok, expected_product="algenta", trust_bundle=keys["bundle"],
        revoked_jtis={"lic-revoked-1"},
    )
    assert reason2 == "revoked"


def test_revocation_fails_open_when_no_denylist(keys) -> None:
    # Empty/None denylist never revokes (an unreachable revocation source must not break a valid license).
    v = lv.verify_license_token(
        _token(keys["priv1"], jti="whatever"), expected_product="algenta",
        trust_bundle=keys["bundle"], revoked_jtis=frozenset(),
    )
    assert v.payload["jti"] == "whatever"


def test_revoked_jtis_from_env(keys, monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_REVOKED_JTIS", "a, lic-env-revoked ,b")
    assert "lic-env-revoked" in lv.load_revoked_jtis()
    _, reason = lv.try_verify_license_token(
        _token(keys["priv1"], jti="lic-env-revoked"), expected_product="algenta",
        trust_bundle=keys["bundle"],
    )
    assert reason == "revoked"


def test_is_strict_profile_token(keys) -> None:
    assert lv.is_strict_profile_token(_token(keys["priv1"])) is True
    legacy = jwt.encode(_claims(), keys["priv1"], algorithm="RS256")  # no typ
    assert lv.is_strict_profile_token(legacy) is False
    assert lv.is_strict_profile_token("not-a-jwt") is False
