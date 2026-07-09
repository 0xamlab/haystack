"""Self-contained verification of a bundled native artifact's signed manifest — RS256 over the EXACT shipped
bytes + per-file SHA-256. Used by the runtime to trust a prebuilt binary (e.g. the Secure Enclave helper)
before executing it, so a release ships no compiler / JIT and never runs an unverified/tampered binary.

Mirrors the manifest format of ``packages/algenta/algenta/native/verify.py`` (and what ``build-runtime.yml``
signs with ``ALGENTA_SIGNING_KEY``), so a manifest signed by the release key verifies identically here — but
this module keeps ``apps/runtime`` standalone (the engine must run on Fly/Linux where the algenta package is
not installed; the artifacts this verifies are only ever resolved on the platforms that ship them).

Release public key resolves, in order: ``ALGENTA_RELEASE_PUBKEY`` (inline PEM) → ``ALGENTA_RELEASE_PUBKEY_FILE``
(path) → ``<artifact_dir>/algenta_release_pub.pem`` (shipped next to the artifact) → the algenta package's
embedded key if importable. Fail-closed: no key, a bad signature, or a SHA-256 mismatch ⇒ NOT trusted.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os


class NativeVerificationError(Exception):
    """A manifest signature / artifact integrity / trust-anchor check failed. Fail closed."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_release_pubkey(artifact_dir: str | None):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pem: bytes | str | None = os.environ.get("ALGENTA_RELEASE_PUBKEY")
    if not pem:
        path = os.environ.get("ALGENTA_RELEASE_PUBKEY_FILE")
        if not path and artifact_dir:
            cand = os.path.join(artifact_dir, "algenta_release_pub.pem")
            path = cand if os.path.exists(cand) else None
        if path and os.path.exists(path):
            with open(path, "rb") as fh:
                pem = fh.read()
    if not pem:
        # last resort: the algenta package's embedded release key (present on a pip-installed host)
        try:
            from algenta.native.verify import release_public_key  # type: ignore[import-not-found]

            return release_public_key()
        except Exception as exc:  # noqa: BLE001
            raise NativeVerificationError(
                "no Algenta release public key found (set ALGENTA_RELEASE_PUBKEY / _FILE, ship "
                "algenta_release_pub.pem next to the artifact, or install the algenta package)"
            ) from exc
    try:
        key = serialization.load_pem_public_key(pem.encode() if isinstance(pem, str) else pem)
    except Exception as exc:  # noqa: BLE001
        raise NativeVerificationError(f"invalid release public key PEM: {exc}") from exc
    if not isinstance(key, rsa.RSAPublicKey):
        raise NativeVerificationError("release key must be RSA")
    return key


def verify_manifest(manifest_bytes: bytes, signature: bytes, pubkey) -> dict:
    """Verify the RS256 signature over the EXACT manifest bytes, THEN parse (never re-serialize first)."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        pubkey.verify(signature, manifest_bytes, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise NativeVerificationError("manifest signature does not verify against the release key") from exc
    try:
        manifest = json.loads(manifest_bytes)
    except Exception as exc:  # noqa: BLE001
        raise NativeVerificationError(f"manifest verified but is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), list) or not manifest["artifacts"]:
        raise NativeVerificationError("manifest missing a non-empty 'artifacts' list")
    return manifest


def verify_bundled_artifact(
    artifact_path: str, manifest_path: str, sig_path: str, *, expected_name: str
) -> dict:
    """Verify a bundled binary against its signed manifest: signature over the manifest bytes, then this
    artifact's SHA-256 matches its (now-trusted) manifest entry. Raises :class:`NativeVerificationError` on
    any failure. Returns the parsed manifest. Fail-closed — the caller must NOT execute an artifact that
    doesn't pass this."""
    for p in (artifact_path, manifest_path, sig_path):
        if not os.path.exists(p):
            raise NativeVerificationError(f"bundled artifact incomplete — missing {os.path.basename(p)}")
    with open(manifest_path, "rb") as fh:
        manifest_bytes = fh.read()
    with open(sig_path, "rb") as fh:
        signature = fh.read()
    pubkey = _load_release_pubkey(os.path.dirname(artifact_path))
    manifest = verify_manifest(manifest_bytes, signature, pubkey)
    entry = next((a for a in manifest["artifacts"] if a.get("name") == expected_name), None)
    if not entry or not isinstance(entry.get("sha256"), str) or len(entry["sha256"]) != 64:
        raise NativeVerificationError(f"artifact {expected_name!r} not listed in the signed manifest")
    actual = sha256_file(artifact_path)
    if not hmac.compare_digest(actual, entry["sha256"].lower()):
        raise NativeVerificationError(
            f"artifact integrity check FAILED for {expected_name}: "
            f"expected {entry['sha256'][:12]}…, got {actual[:12]}…"
        )
    return manifest
