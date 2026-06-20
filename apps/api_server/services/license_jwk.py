"""License JWKS — publish the license signer's PUBLIC key so the runtime can verify
licenses (and the signed CRL) by ``kid`` instead of a hardcoded env key.

Per signer backend (see services/license_signer.py):
- ``pem``      → derive the RSA public key from the configured private key PEM, publish it.
- ``cf_worker``→ the app never holds the Worker's private key; publish the configured
                 Worker PUBLIC key PEM if provided, else nothing (the Worker may serve its
                 own JWKS in P4).
- ``dev_hmac`` (default) → HS256 has no asymmetric public key; JWKS is intentionally EMPTY.
  A consumer must treat "empty JWKS" as "no asymmetric verification available" (fall back
  to the shared-secret / offline-key path) — NOT as "trust an unsigned token".

The published JWK contains ONLY public fields (kty/use/alg/kid/n/e) — never private
material. Safe to serve unauthenticated.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import structlog
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

logger = structlog.get_logger(__name__)


def _b64url_uint(value: int) -> str:
    """Big-endian, minimal-length, unpadded base64url of a non-negative integer (RFC 7518)."""
    length = max(1, (value.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


def _rsa_public_jwk(public_key: RSAPublicKey, kid: str) -> dict[str, str]:
    numbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64url_uint(numbers.n),
        "e": _b64url_uint(numbers.e),
    }


def build_rsa_jwk_from_private_pem(private_pem: str, kid: str) -> dict[str, str] | None:
    """JWK (public half only) derived from an RSA PRIVATE key PEM. None if not RSA/invalid."""
    try:
        key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    except (ValueError, TypeError):
        logger.warning("license_jwk_private_pem_invalid")
        return None
    if not isinstance(key, RSAPrivateKey):
        logger.warning("license_jwk_private_key_not_rsa")
        return None
    return _rsa_public_jwk(key.public_key(), kid)


def build_rsa_jwk_from_public_pem(public_pem: str, kid: str) -> dict[str, str] | None:
    """JWK from an RSA PUBLIC key PEM (cf_worker publication). None if not RSA/invalid."""
    try:
        key = serialization.load_pem_public_key(public_pem.encode())
    except (ValueError, TypeError):
        logger.warning("license_jwk_public_pem_invalid")
        return None
    if not isinstance(key, RSAPublicKey):
        logger.warning("license_jwk_public_key_not_rsa")
        return None
    return _rsa_public_jwk(key, kid)


def _read_pem(inline: str | None, file_path: str | None) -> str:
    if inline:
        return inline
    if file_path:
        try:
            return Path(file_path).read_text()
        except OSError:
            logger.warning("license_jwk_pem_file_unreadable", path=file_path)
    return ""


def get_active_license_jwks(settings: Any = None) -> dict[str, list[dict[str, str]]]:
    """The JWKS document ({"keys": [...]}) for the configured license signer backend.

    Empty ``keys`` for dev_hmac (HS256) and for cf_worker without a published public key.
    """
    if settings is None:
        from apps.api_server.config import get_settings

        settings = get_settings()

    backend = (getattr(settings, "license_signer_backend", None) or "dev_hmac").strip()
    kid = (getattr(settings, "license_signer_kid", None) or "").strip()
    keys: list[dict[str, str]] = []

    if backend == "pem":
        pem = _read_pem(
            getattr(settings, "license_signing_private_key", None),
            getattr(settings, "license_signing_private_key_file", None),
        )
        if not kid:
            # The runtime selects the verification key by kid; a kid-less RS256 issuer makes
            # JWKS lookup fragile. Publish anyway (kid="") but flag it loudly.
            logger.warning("license_jwk_pem_backend_without_kid")
        jwk = build_rsa_jwk_from_private_pem(pem, kid) if pem else None
        if jwk:
            keys.append(jwk)
    elif backend == "cf_worker":
        pub_pem = _read_pem(
            getattr(settings, "license_signer_worker_public_key", None),
            getattr(settings, "license_signer_worker_public_key_file", None),
        )
        jwk = build_rsa_jwk_from_public_pem(pub_pem, kid) if pub_pem else None
        if jwk:
            keys.append(jwk)
    # dev_hmac / unknown → no asymmetric key → empty keys (verification is shared-secret).

    return {"keys": keys}
