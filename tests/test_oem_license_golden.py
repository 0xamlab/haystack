"""OEM license golden tests — the 100-year sub-brand licenses that must NOT break the current setup.

One shared strict verifier (scripts.issue_oem_license.verify_platform_license, mirroring telys/verify.py)
accepts EVERY brand's OEM license — that single shared trust anchor (one keypair, one iss/aud/kid) is what
lets codna/telys/algenta/… all verify offline. These pin: every brand's OEM license verifies for its own
product; wrong product / audience / issuer / key / expiry / alg-confusion are all rejected (fail closed);
the audit manifest shape; and no drift between the minter's platform constants and the engine's.

Launch blockers (per the go-live plan): existing codna/telys keep verifying after Algenta ships; a new 100y
OEM license verifies; wrong-product/audience/issuer/expired rejected.
"""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import scripts.issue_oem_license as oem

_ALL_PRODUCTS = sorted(oem.PRODUCT_DEFAULT_FEATURES)


def _keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return priv, pub


@pytest.fixture(scope="module")
def keypair() -> tuple[str, str]:
    return _keypair()


def _mint(priv: str, product: str, *, tier: str = "enterprise", features=None,
          exp_years: int = 100, grace_days: int = 3650, **kw):
    claims = oem.build_oem_claims(
        product=product,
        tier=tier,
        features=list(features) if features else list(oem.PRODUCT_DEFAULT_FEATURES[product]),
        customer=product,
        org_id=product,
        exp_years=exp_years,
        grace_days=grace_days,
        license_id=f"oem-{product}-test",
        **kw,
    )
    return oem.mint_oem_license(priv, claims), claims


# ── 1. every brand's OEM license verifies for its own product, ~100y, oem, uncapped ──────────────
@pytest.mark.parametrize("product", _ALL_PRODUCTS)
def test_oem_license_verifies_for_its_product(keypair, product):
    priv, pub = keypair
    token, _ = _mint(priv, product)
    claims = oem.verify_platform_license(token, pub, product=product)
    assert claims["deployment_class"] == "oem"
    assert claims["products"][product]["features"], "features must be non-empty"
    assert claims["exp"] - claims["iat"] > 99 * 365 * 86400, "must be ~100y"
    assert claims["named_seat_limit"] == 0 and claims["active_node_limit"] == 0, "OEM pool is uncapped"
    assert claims["commercial_use"] is True and claims["redistribution_allowed"] is True


# ── 2. ONE shared verifier accepts EVERY brand (key continuity / single trust anchor) ────────────
def test_one_verifier_accepts_every_brand(keypair):
    priv, pub = keypair
    for product in ("codna", "telys", "algenta"):
        token, _ = _mint(priv, product)
        oem.verify_platform_license(token, pub, product=product)  # must not raise


# ── 3-6. fail-closed rejections ─────────────────────────────────────────────────────────────────
def test_wrong_product_rejected(keypair):
    priv, pub = keypair
    token, _ = _mint(priv, "codna")
    with pytest.raises(oem.VerificationError):
        oem.verify_platform_license(token, pub, product="telys")


def test_wrong_audience_rejected(keypair):
    priv, pub = keypair
    token, _ = _mint(priv, "codna", audience="evil-runtime")
    with pytest.raises(oem.VerificationError):
        oem.verify_platform_license(token, pub, product="codna")


def test_wrong_issuer_rejected(keypair):
    priv, pub = keypair
    token, _ = _mint(priv, "codna", issuer="https://evil.example")
    with pytest.raises(oem.VerificationError):
        oem.verify_platform_license(token, pub, product="codna")


def test_expired_beyond_grace_rejected(keypair):
    priv, pub = keypair
    token, claims = _mint(priv, "codna", exp_years=0, grace_days=0)
    future = int(claims["exp"]) + 10  # a moment past exp, no grace
    with pytest.raises(oem.VerificationError):
        oem.verify_platform_license(token, pub, product="codna", now=future)


def test_within_grace_still_valid(keypair):
    # An expired-but-within-offline-grace license MUST still verify (the whole point of offline grace).
    priv, pub = keypair
    token, claims = _mint(priv, "codna", exp_years=0, grace_days=30)
    just_after_exp = int(claims["exp"]) + 5 * 86400  # 5 days past exp, within 30d grace
    oem.verify_platform_license(token, pub, product="codna", now=just_after_exp)  # must not raise


# ── 7. wrong signing key rejected (signature integrity) ─────────────────────────────────────────
def test_foreign_key_rejected(keypair):
    _, pub = keypair
    other_priv, _ = _keypair()  # a DIFFERENT keypair
    token, _ = _mint(other_priv, "codna")
    with pytest.raises(oem.VerificationError):
        oem.verify_platform_license(token, pub, product="codna")


# ── 8. algorithm-confusion (HS256 forged with the public key as secret) rejected ─────────────────
def test_alg_confusion_rejected(keypair):
    # The classic RS256→HS256 downgrade: HMAC-sign with the RSA PUBLIC key bytes as the secret. PyJWT
    # refuses to *encode* this (good), so we craft it by hand — exactly what an attacker would do — and
    # assert the verifier rejects it (it pins alg==RS256 + algorithms=["RS256"]).
    import base64
    import hashlib
    import hmac
    import json as _json

    _, pub = keypair
    claims = oem.build_oem_claims(
        product="codna", tier="enterprise", features=["fix"], customer="x", org_id="x",
        exp_years=100, grace_days=10, license_id="x",
    )

    def _b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    header = _b64(_json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(_json.dumps(claims).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = _b64(hmac.new(pub.encode(), signing_input, hashlib.sha256).digest())
    forged = f"{header}.{payload}.{sig}"
    with pytest.raises(oem.VerificationError):
        oem.verify_platform_license(forged, pub, product="codna")


# ── 9. audit manifest shape ──────────────────────────────────────────────────────────────────────
def test_audit_manifest_shape(keypair):
    priv, _ = keypair
    _, claims = _mint(priv, "telys", tier="team")
    m = oem.audit_manifest(claims, product="telys", kid=oem.PLATFORM_KID)
    assert m["product"] == "telys" and m["deployment_class"] == "oem"
    assert m["device_bound"] is False and m["kid"] == oem.PLATFORM_KID
    assert m["exp_years"] and m["exp_years"] > 99
    assert m["tier"] == "team" and m["features"]
    assert m["commercial_use"] is True


def test_device_bound_oem_license(keypair):
    priv, pub = keypair
    token, claims = _mint(priv, "codna", device_thumbprint="ed25519:abc123")
    oem.verify_platform_license(token, pub, product="codna")
    assert oem.audit_manifest(claims, product="codna", kid=oem.PLATFORM_KID)["device_bound"] is True


# ── 10. no drift between the minter's platform constants and the engine's ────────────────────────
def test_platform_constants_match_engine():
    from apps.api_server.services import device_service as ds

    assert oem.PLATFORM_ISSUER == ds._PLATFORM_LICENSE_ISSUER
    assert oem.PLATFORM_AUDIENCE == ds._PLATFORM_LICENSE_AUDIENCE
    assert oem.PLATFORM_KID == "algenta-license-2026"
    assert "algenta-runtime" in oem.ACCEPTED_AUDIENCES and "telys-runtime" in oem.ACCEPTED_AUDIENCES
