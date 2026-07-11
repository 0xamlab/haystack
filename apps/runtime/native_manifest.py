"""Verify bundled native artifacts with a signed manifest.

The verifier checks RS256 over the exact manifest bytes and then checks every
listed artifact by SHA-256. Runtime callers use it before executing prebuilt
binaries, so release builds ship no compiler/JIT and never run tampered files.

The manifest format matches ``packages/algenta/algenta/native/verify.py`` and
``build-runtime.yml``. This module stays in ``apps/runtime`` because Fly/Linux
server code may not have the ``algenta`` package installed.

Release public keys resolve from ``ALGENTA_RELEASE_PUBKEY``, then
``ALGENTA_RELEASE_PUBKEY_FILE``, then ``algenta_release_pub.pem`` beside the
artifact, then the installed ``algenta`` package if importable.
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
    """Verify the manifest signature before parsing the JSON payload."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        pubkey.verify(signature, manifest_bytes, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise NativeVerificationError(
            "manifest signature does not verify against the release key"
        ) from exc
    try:
        manifest = json.loads(manifest_bytes)
    except Exception as exc:  # noqa: BLE001
        raise NativeVerificationError(f"manifest verified but is not valid JSON: {exc}") from exc
    if (
        not isinstance(manifest, dict)
        or not isinstance(manifest.get("artifacts"), list)
        or not manifest["artifacts"]
    ):
        raise NativeVerificationError("manifest missing a non-empty 'artifacts' list")
    return manifest


def verify_bundled_artifact(
    artifact_path: str, manifest_path: str, sig_path: str, *, expected_name: str
) -> dict:
    """Verify a bundled binary against its signed manifest.

    Signature verification happens first. Only then are artifact hashes trusted.
    Callers must not execute artifacts that fail this check.
    """
    for p in (artifact_path, manifest_path, sig_path):
        if not os.path.exists(p):
            raise NativeVerificationError(
                f"bundled artifact incomplete — missing {os.path.basename(p)}"
            )
    with open(manifest_path, "rb") as fh:
        manifest_bytes = fh.read()
    with open(sig_path, "rb") as fh:
        signature = fh.read()
    pubkey = _load_release_pubkey(os.path.dirname(artifact_path))
    manifest = verify_manifest(manifest_bytes, signature, pubkey)
    artifact_dir = os.path.dirname(artifact_path)
    seen_expected = False
    for entry in manifest["artifacts"]:
        name = entry.get("name")
        expected_sha = entry.get("sha256")
        if not isinstance(name, str) or not name or os.path.basename(name) != name:
            raise NativeVerificationError(f"manifest artifact name is unsafe: {name!r}")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise NativeVerificationError(f"artifact {name!r} has a malformed sha256")
        candidate = os.path.join(artifact_dir, name)
        if not os.path.exists(candidate):
            raise NativeVerificationError(f"signed runtime artifact is missing: {name}")
        actual = sha256_file(candidate)
        if not hmac.compare_digest(actual, expected_sha.lower()):
            raise NativeVerificationError(
                f"artifact integrity check FAILED for {name}: "
                f"expected {expected_sha[:12]}…, got {actual[:12]}…"
            )
        seen_expected = seen_expected or name == expected_name
    if not seen_expected:
        raise NativeVerificationError(
            f"artifact {expected_name!r} not listed in the signed manifest"
        )
    return manifest
