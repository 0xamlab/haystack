"""License JWKS (P3b-B1) — publish the signer's PUBLIC key so the runtime verifies by kid.

Covers per-backend behavior (pem/cf_worker/dev_hmac), the n/e encoding's reconstructability,
the kid contract with LocalPemSigner (B2), the unauthenticated route, and the critical
security property: the JWKS must NEVER contain private key material.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api_server.services.license_jwk import get_active_license_jwks

_PRIVATE_JWK_FIELDS = {"d", "p", "q", "dp", "dq", "qi", "oth"}


def _keypair() -> tuple[str, str]:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub_pem = (
        priv.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv_pem, pub_pem


def _b64uint(s: str) -> int:
    return int.from_bytes(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)), "big")


def _settings(**kw) -> SimpleNamespace:
    base = {
        "license_signer_backend": None,
        "license_signing_private_key": None,
        "license_signing_private_key_file": None,
        "license_signer_kid": None,
        "license_signer_worker_public_key": None,
        "license_signer_worker_public_key_file": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


# ── per-backend ────────────────────────────────────────────────────────────────


def test_dev_hmac_backend_publishes_empty_keys() -> None:
    assert get_active_license_jwks(_settings(license_signer_backend="dev_hmac")) == {"keys": []}
    assert get_active_license_jwks(_settings(license_signer_backend=None)) == {"keys": []}


def test_pem_backend_publishes_public_jwk() -> None:
    priv_pem, _ = _keypair()
    jwks = get_active_license_jwks(
        _settings(
            license_signer_backend="pem",
            license_signing_private_key=priv_pem,
            license_signer_kid="lic-2026",
        )
    )
    assert len(jwks["keys"]) == 1
    jwk = jwks["keys"][0]
    assert jwk["kty"] == "RSA" and jwk["alg"] == "RS256" and jwk["use"] == "sig"
    assert jwk["kid"] == "lic-2026"
    # n/e reconstruct the actual public key
    pub = serialization.load_pem_private_key(priv_pem.encode(), password=None).public_key()
    assert _b64uint(jwk["n"]) == pub.public_numbers().n
    assert _b64uint(jwk["e"]) == pub.public_numbers().e


def test_cf_worker_backend_publishes_from_public_key() -> None:
    _, pub_pem = _keypair()
    jwks = get_active_license_jwks(
        _settings(
            license_signer_backend="cf_worker",
            license_signer_worker_public_key=pub_pem,
            license_signer_kid="wk-1",
        )
    )
    assert len(jwks["keys"]) == 1
    assert jwks["keys"][0]["kid"] == "wk-1"


def test_cf_worker_without_public_key_is_empty() -> None:
    assert get_active_license_jwks(_settings(license_signer_backend="cf_worker")) == {"keys": []}


def test_pem_backend_without_key_is_empty() -> None:
    assert get_active_license_jwks(_settings(license_signer_backend="pem")) == {"keys": []}


# ── SECURITY: never leak private material ──────────────────────────────────────


def test_jwks_never_contains_private_fields() -> None:
    priv_pem, _ = _keypair()
    jwks = get_active_license_jwks(
        _settings(
            license_signer_backend="pem",
            license_signing_private_key=priv_pem,
            license_signer_kid="lic",
        )
    )
    jwk = jwks["keys"][0]
    assert set(jwk) == {"kty", "use", "alg", "kid", "n", "e"}
    assert not (_PRIVATE_JWK_FIELDS & set(jwk))
    # and the private PEM markers never appear anywhere in the serialized doc
    import json

    blob = json.dumps(jwks)
    assert "PRIVATE" not in blob and "BEGIN" not in blob


# ── B2: kid contract with the signer ───────────────────────────────────────────


def test_jwks_kid_matches_local_pem_signer_token_header() -> None:
    from apps.api_server.services.license_signer import LocalPemSigner

    priv_pem, _ = _keypair()
    jwks = get_active_license_jwks(
        _settings(
            license_signer_backend="pem",
            license_signing_private_key=priv_pem,
            license_signer_kid="lic-2026",
        )
    )
    jwks_kid = jwks["keys"][0]["kid"]
    token = LocalPemSigner(priv_pem, kid="lic-2026").sign({"sub": "x"})
    assert jwt.get_unverified_header(token)["kid"] == jwks_kid  # consumer can select the key


# ── unauthenticated route ──────────────────────────────────────────────────────


def test_jwks_route_is_unauthenticated_and_returns_keys() -> None:
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from apps.api_server.routers import license as license_router

    app = FastAPI()
    app.include_router(license_router.router)
    client = TestClient(app)
    resp = client.get("/.well-known/jwks.json")  # no auth header
    assert resp.status_code == 200
    assert "keys" in resp.json()  # default config (dev_hmac) → empty keys list
