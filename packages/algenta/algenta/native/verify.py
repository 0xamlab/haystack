"""Algenta offline verification: bundled-runtime manifest signature + artifact integrity + RS256 license.

The trust core of the on-device model. The bundled native runtime and the offline license verify themselves
LOCALLY, offline, against embedded Algenta public keys — no network, no OS-native signing. Mirrors
telys-sdk telys/verify.py.

Two trust anchors (NEVER share private keys — key separation):
  - RELEASE key  → signs the runtime manifest (artifact SHA-256s).       verify_manifest()
  - LICENSE key  → signs the RS256 ver:2 entitlement token.              verify_license()

Public keys resolve in order: env inline PEM → env *_FILE → embedded algenta/_keys/<name>.pem. Production
embeds the Algenta public keys; the env/file override stays for rotation / air-gapped operators.

CRITICAL: the manifest signature covers the EXACT manifest bytes shipped — verify those bytes as-read and
NEVER re-serialize before verifying. Requires ``cryptography`` (a core dep; imported lazily).
"""
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import math
import os

# Algenta rides the SHARED platform license signer (the decision-engine license-signer Worker + the OEM
# minter — one private key for all brands). Licenses are the engine's ver:2 entitlement tokens; verified
# OFFLINE against the platform RS256 license public key. iss/aud are env-overridable for self-hosted ops.
DEFAULT_LICENSE_ISSUER = "https://license.algenta.ai"
DEFAULT_LICENSE_AUDIENCES = ("algenta-runtime", "telys-runtime")
SUPPORTED_LICENSE_VER = 2
PRODUCT = "algenta"


class VerificationError(Exception):
    """Any signature / integrity / license-claim check failed. Fail closed — never proceed on this."""


def _expected_issuer() -> str:
    return os.environ.get("ALGENTA_LICENSE_ISSUER") or DEFAULT_LICENSE_ISSUER


def _expected_audiences() -> tuple[str, ...]:
    env = os.environ.get("ALGENTA_LICENSE_AUDIENCE")  # comma-separated override
    return tuple(a.strip() for a in env.split(",") if a.strip()) if env else DEFAULT_LICENSE_AUDIENCES


def _crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        return InvalidSignature, hashes, serialization, padding
    except ImportError as e:  # noqa: BLE001
        raise VerificationError(
            "offline verification needs the `cryptography` package — `pip install algenta` pulls it in."
        ) from e


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _load_public_key(env_inline: str, env_file: str, embedded_name: str):
    """Resolve a verification public key PEM (inline env > file env > embedded) and parse it. Fail if none."""
    _, _, serialization, _ = _crypto()
    pem = os.environ.get(env_inline)
    if not pem:
        path = os.environ.get(env_file)
        if not path:
            here = os.path.dirname(__file__)
            # embedded keys live one level up, in algenta/_keys/
            cand = os.path.join(os.path.dirname(here), "_keys", embedded_name)
            path = cand if os.path.exists(cand) else None
        if path:
            with open(path, "rb") as fh:
                pem = fh.read().decode("utf-8")
    if not pem:
        raise VerificationError(
            f"no Algenta verification key found. Set {env_inline} (inline PEM) or {env_file} (PEM path), "
            f"or ship the embedded key algenta/_keys/{embedded_name}. (Production embeds it; the env override "
            "is for key rotation / air-gapped operators.)"
        )
    try:
        key = serialization.load_pem_public_key(pem.encode("utf-8") if isinstance(pem, str) else pem)
    except Exception as e:  # noqa: BLE001
        raise VerificationError(f"invalid public key PEM ({embedded_name}): {e}") from e
    from cryptography.hazmat.primitives.asymmetric import rsa

    if not isinstance(key, rsa.RSAPublicKey):
        raise VerificationError(f"Algenta verification key must be RSA, got {type(key).__name__} ({embedded_name})")
    return key


def release_public_key():
    return _load_public_key("ALGENTA_RELEASE_PUBKEY", "ALGENTA_RELEASE_PUBKEY_FILE", "algenta_release_pub.pem")


def license_public_key():
    return _load_public_key("ALGENTA_LICENSE_PUBKEY", "ALGENTA_LICENSE_PUBKEY_FILE", "algenta_license_pub.pem")


def _rsa_verify(pubkey, signature: bytes, message: bytes) -> None:
    InvalidSignature, hashes, _, padding = _crypto()
    try:
        pubkey.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as e:
        raise VerificationError("signature does not verify against the Algenta public key") from e


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _consttime_eq(a: str, b: str) -> bool:
    return _hmac.compare_digest(a, b)


def verify_manifest(manifest_bytes: bytes, signature: bytes, pubkey=None) -> dict:
    """Verify the manifest SIGNATURE over the EXACT shipped bytes, then parse + sanity-check it.

    Returns the parsed manifest {format_version, platform, artifacts:[{name,sha256,size_bytes}], ...}. We
    verify the raw bytes first and only THEN json.loads — never the other way around (no re-canonicalization)."""
    if pubkey is None:
        pubkey = release_public_key()
    _rsa_verify(pubkey, signature, manifest_bytes)
    try:
        manifest = json.loads(manifest_bytes)
    except Exception as e:  # noqa: BLE001
        raise VerificationError(f"manifest verified but is not valid JSON: {e}") from e
    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), list) or not manifest["artifacts"]:
        raise VerificationError("manifest missing a non-empty 'artifacts' list")
    for a in manifest["artifacts"]:
        if not (isinstance(a, dict) and isinstance(a.get("name"), str) and isinstance(a.get("sha256"), str)
                and len(a["sha256"]) == 64):
            raise VerificationError(f"manifest artifact entry malformed: {a!r}")
    return manifest


def verify_artifact(path: str, expected_sha256: str) -> None:
    """Confirm a file's SHA-256 matches the (already signature-verified) manifest entry."""
    actual = sha256_file(path)
    if not _consttime_eq(actual, expected_sha256.lower()):
        raise VerificationError(
            f"artifact integrity check FAILED for {os.path.basename(path)}: "
            f"expected {expected_sha256[:12]}…, got {actual[:12]}…"
        )


def verify_license(token: str, pubkey=None, *, now: int, issuer: str | None = None, audience=None,
                   product: str = PRODUCT) -> dict:
    """STRICT offline RS256 verification of the shared platform's ver:2 entitlement license. Returns claims.

    Enforced: alg==RS256 ONLY (no none/HS*/negotiation); reject a JWS `crit` header; signature verifies
    against the platform LICENSE key; iss matches the shared signer; aud includes an accepted audience;
    ver==2; a finite exp REQUIRED, checked against `now` (+ offline_grace_days); products.<product> present
    with a non-empty tier AND features list.
    """
    if issuer is None:
        issuer = _expected_issuer()
    accepted_aud = set(_expected_audiences()) if audience is None else (
        {audience} if isinstance(audience, str) else set(audience))
    if pubkey is None:
        pubkey = license_public_key()
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise VerificationError("license is not a compact JWS (expected header.payload.signature)")
    h_b64, p_b64, s_b64 = parts
    try:
        header = json.loads(_b64url_decode(h_b64))
    except Exception as e:  # noqa: BLE001
        raise VerificationError(f"license header is not valid base64url JSON: {e}") from e
    if header.get("alg") != "RS256":
        raise VerificationError(f"license alg must be RS256, got {header.get('alg')!r} (no none/HS*/negotiation)")
    if "crit" in header:
        raise VerificationError("license declares unsupported critical ('crit') header extensions — rejected")
    _rsa_verify(pubkey, _b64url_decode(s_b64), (h_b64 + "." + p_b64).encode("ascii"))
    try:
        claims = json.loads(_b64url_decode(p_b64))
    except Exception as e:  # noqa: BLE001
        raise VerificationError(f"license payload is not valid base64url JSON: {e}") from e
    if not isinstance(claims, dict):
        raise VerificationError("license payload is not a JSON object")
    if claims.get("iss") != issuer:
        raise VerificationError(f"license issuer {claims.get('iss')!r} != expected {issuer!r}")
    aud = claims.get("aud")
    aud_toks = {aud} if isinstance(aud, str) else (set(aud) if isinstance(aud, list) else set())
    if not (aud_toks & accepted_aud):
        raise VerificationError(f"license audience {aud!r} not in accepted {sorted(accepted_aud)}")
    ver = claims.get("ver")
    if isinstance(ver, bool) or not isinstance(ver, int) or ver != SUPPORTED_LICENSE_VER:
        raise VerificationError(f"license ver {ver!r} unsupported (this client supports v{SUPPORTED_LICENSE_VER})")
    exp = claims.get("exp", claims.get("expires_at"))
    if isinstance(exp, bool) or not isinstance(exp, (int, float)) or not math.isfinite(exp):
        raise VerificationError("license has no finite numeric expiry ('exp') — expiry is required")
    graceval = claims.get("offline_grace_days", claims.get("grace_days", 0))
    if isinstance(graceval, bool) or not isinstance(graceval, (int, float)) or not math.isfinite(graceval) or graceval < 0:
        raise VerificationError(f"license has an invalid offline_grace_days: {graceval!r}")
    if now > int(exp) + int(graceval) * 86400:
        raise VerificationError(f"license expired (exp={int(exp)}, grace_days={int(graceval)}, now={now})")
    products = claims.get("products")
    if not isinstance(products, dict) or product not in products:
        raise VerificationError(f"license does not grant product {product!r}")
    entry = products[product]
    if not isinstance(entry, dict) or not entry.get("tier"):
        raise VerificationError(f"license product {product!r} missing a tier")
    feats = entry.get("features")
    if not isinstance(feats, list) or not feats:
        raise VerificationError(f"license product {product!r} missing a non-empty features list")
    return claims
