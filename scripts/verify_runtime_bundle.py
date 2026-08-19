#!/usr/bin/env python3
"""Verify a signed Algenta managed-runtime bundle — the SQAI provisioner's reference.

Standalone (stdlib + `cryptography` only — no repo imports), so the SQAI
provisioner can mirror this file verbatim. Verification order fails closed at
every step, mirroring the Telys signed-bundle installer:

  1. read manifest.json + manifest.sig bytes FROM the archive (hard size caps
     BEFORE any allocation — the bundle is attacker-controlled until verified)
  2. verify the RS256 signature over those EXACT manifest bytes (never
     re-serialize / re-canonicalize before verifying)
  3. schema-check the manifest (format version, artifact entries, path safety:
     reject absolute paths, "..", empty segments)
  4. stream-hash every artifact member against the signed sha256 + size
     (regular files only — symlinks / devices / dirs-as-artifacts rejected)
  5. reject any archive member the signed manifest does not name (no smuggled
     payloads riding alongside verified files)

Usage:
    python3 scripts/verify_runtime_bundle.py <bundle.tar.gz> --public-key <pem>
    # or: ALGENTA_BUNDLE_PUBLIC_KEY (inline PEM) / ALGENTA_BUNDLE_PUBLIC_KEY_FILE

Prints OK + a summary and exits 0; any failure prints the reason and exits 1.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import tarfile
from pathlib import Path
from typing import Any

MANIFEST_NAME = "manifest.json"
MANIFEST_SIG_NAME = "manifest.sig"
BUNDLE_FORMAT_VERSION = 1

_ENV_PUBLIC_KEY = "ALGENTA_BUNDLE_PUBLIC_KEY"
_ENV_PUBLIC_KEY_FILE = "ALGENTA_BUNDLE_PUBLIC_KEY_FILE"

# Hard caps enforced BEFORE the signature is checked (anti-OOM: a tiny gzip
# member can declare a multi-GB size). Artifacts are additionally bounded by
# the SIGNED manifest size once the signature verifies.
MAX_MANIFEST_BYTES = 8 * 1024 * 1024      # 8 MB
MAX_SIG_BYTES = 64 * 1024                 # 64 KB
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB per-artifact ceiling


class BundleVerificationError(Exception):
    """Any signature / integrity / path-safety check failed. Fail closed."""


# ── Path safety ───────────────────────────────────────────────────────────────


def is_safe_relative_path(path: str) -> bool:
    """True only for a normalized, relative, traversal-free archive path."""
    if not path or path.startswith("/") or path.startswith("\\"):
        return False
    if "\\" in path or "\x00" in path:
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _require_safe_member(info: tarfile.TarInfo) -> None:
    if not is_safe_relative_path(info.name):
        raise BundleVerificationError(f"unsafe path in bundle member: {info.name!r}")
    if info.issym() or info.islnk():
        raise BundleVerificationError(f"link member rejected: {info.name!r}")
    if not (info.isfile() or info.isdir()):
        raise BundleVerificationError(f"non-regular member rejected: {info.name!r}")


# ── Capped member reads ───────────────────────────────────────────────────────


def _read_member_bytes(tar: tarfile.TarFile, name: str, max_bytes: int) -> bytes:
    try:
        info = tar.getmember(name)
    except KeyError:
        raise BundleVerificationError(f"bundle is missing member {name!r}") from None
    _require_safe_member(info)
    if not info.isfile():
        raise BundleVerificationError(f"bundle member {name!r} is not a regular file")
    if info.size > max_bytes:
        raise BundleVerificationError(
            f"bundle member {name!r} too large ({info.size} > {max_bytes} cap)"
        )
    handle = tar.extractfile(info)
    if handle is None:
        raise BundleVerificationError(f"could not read bundle member {name!r}")
    data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise BundleVerificationError(f"bundle member {name!r} exceeds {max_bytes}-byte cap")
    if len(data) != info.size:
        raise BundleVerificationError(
            f"bundle member {name!r} size mismatch (header {info.size}, read {len(data)})"
        )
    return data


# ── RS256 signature ───────────────────────────────────────────────────────────


def load_public_key_pem(inline_pem: str | None = None, key_file: str | None = None) -> str:
    """Resolve the verification public key: arg → env inline → env file."""
    if inline_pem and inline_pem.strip():
        return inline_pem.strip()
    if key_file:
        return Path(key_file).expanduser().read_text().strip()
    env_inline = (os.environ.get(_ENV_PUBLIC_KEY) or "").strip()
    if env_inline:
        return env_inline
    env_file = (os.environ.get(_ENV_PUBLIC_KEY_FILE) or "").strip()
    if env_file:
        return Path(env_file).expanduser().read_text().strip()
    raise BundleVerificationError(
        "no bundle verification key: pass --public-key or set "
        f"{_ENV_PUBLIC_KEY} (inline PEM) / {_ENV_PUBLIC_KEY_FILE} (path)"
    )


def verify_manifest_signature(manifest_bytes: bytes, signature: bytes, public_key_pem: str) -> None:
    """RS256 (RSASSA-PKCS1-v1_5 + SHA-256) over the exact shipped bytes."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    try:
        key = serialization.load_pem_public_key(public_key_pem.encode())
    except Exception as exc:  # noqa: BLE001
        raise BundleVerificationError(f"invalid public key PEM: {exc}") from exc
    if not isinstance(key, rsa.RSAPublicKey):
        raise BundleVerificationError(
            f"bundle verification key must be RSA, got {type(key).__name__}"
        )
    try:
        key.verify(signature, manifest_bytes, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise BundleVerificationError(
            "manifest signature does not verify against the bundle public key"
        ) from exc


# ── Manifest schema ───────────────────────────────────────────────────────────


def parse_verified_manifest(manifest_bytes: bytes) -> dict[str, Any]:
    """json.loads AFTER signature verification, then schema + path-safety checks."""
    try:
        manifest = json.loads(manifest_bytes)
    except Exception as exc:  # noqa: BLE001
        raise BundleVerificationError(f"manifest verified but is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise BundleVerificationError("manifest is not a JSON object")
    if manifest.get("bundle_format_version") != BUNDLE_FORMAT_VERSION:
        raise BundleVerificationError(
            f"unsupported bundle_format_version: {manifest.get('bundle_format_version')!r}"
        )
    for field in ("runtime_bundle_version", "platform", "created_at"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise BundleVerificationError(f"manifest missing string field {field!r}")
    if not isinstance(manifest.get("engine_stub"), bool):
        raise BundleVerificationError("manifest missing boolean field 'engine_stub'")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise BundleVerificationError("manifest missing a non-empty 'artifacts' list")
    seen: set[str] = set()
    for entry in artifacts:
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            and isinstance(entry.get("sha256"), str)
            and len(entry["sha256"]) == 64
            and isinstance(entry.get("size"), int)
            and not isinstance(entry.get("size"), bool)
            and entry["size"] >= 0
        ):
            raise BundleVerificationError(f"manifest artifact entry malformed: {entry!r}")
        path = entry["path"]
        if not is_safe_relative_path(path) or path in (MANIFEST_NAME, MANIFEST_SIG_NAME):
            raise BundleVerificationError(f"unsafe artifact path in manifest: {path!r}")
        if path in seen:
            raise BundleVerificationError(f"duplicate artifact path in manifest: {path!r}")
        seen.add(path)
    return manifest


# ── Full verification ─────────────────────────────────────────────────────────


def _stream_sha256(tar: tarfile.TarFile, info: tarfile.TarInfo, cap: int) -> tuple[str, int]:
    handle = tar.extractfile(info)
    if handle is None:
        raise BundleVerificationError(f"could not read artifact {info.name!r}")
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = handle.read(1 << 20)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise BundleVerificationError(f"artifact {info.name!r} exceeds {cap}-byte cap")
        digest.update(chunk)
    return digest.hexdigest(), total


def verify_bundle(bundle_path: str | Path, public_key_pem: str) -> dict[str, Any]:
    """Verify signature, per-artifact integrity, and path safety. Returns the manifest.

    Raises BundleVerificationError on ANY failure. Does not extract to disk.
    """
    bundle_path = Path(bundle_path)
    if not bundle_path.is_file():
        raise BundleVerificationError(f"bundle not found: {bundle_path}")

    with tarfile.open(bundle_path, "r:*") as tar:
        # 1 + 2: signature over the exact manifest bytes, before trusting anything.
        manifest_bytes = _read_member_bytes(tar, MANIFEST_NAME, MAX_MANIFEST_BYTES)
        signature = _read_member_bytes(tar, MANIFEST_SIG_NAME, MAX_SIG_BYTES)
        verify_manifest_signature(manifest_bytes, signature, public_key_pem)

        # 3: schema + path safety of the now-trusted manifest.
        manifest = parse_verified_manifest(manifest_bytes)
        by_path = {entry["path"]: entry for entry in manifest["artifacts"]}

        # 4 + 5: walk EVERY archive member — safety-check all, hash the listed,
        # reject unlisted regular files.
        verified: set[str] = set()
        for info in tar.getmembers():
            _require_safe_member(info)
            if info.isdir():
                continue
            if info.name in (MANIFEST_NAME, MANIFEST_SIG_NAME):
                continue
            entry = by_path.get(info.name)
            if entry is None:
                raise BundleVerificationError(
                    f"archive member not listed in signed manifest: {info.name!r}"
                )
            cap = min(int(entry["size"]), MAX_ARTIFACT_BYTES)
            actual_sha, actual_size = _stream_sha256(tar, info, cap)
            if actual_size != entry["size"]:
                raise BundleVerificationError(
                    f"artifact {info.name!r} size mismatch "
                    f"(manifest {entry['size']}, actual {actual_size})"
                )
            if not hmac.compare_digest(actual_sha, entry["sha256"].lower()):
                raise BundleVerificationError(
                    f"artifact integrity check FAILED for {info.name!r}: "
                    f"expected {entry['sha256'][:12]}…, got {actual_sha[:12]}…"
                )
            verified.add(info.name)

        missing = sorted(set(by_path) - verified)
        if missing:
            raise BundleVerificationError(
                f"manifest artifacts missing from archive: {', '.join(missing[:5])}"
            )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a signed Algenta runtime bundle.")
    parser.add_argument("bundle", help="path to algenta-runtime-<version>-<platform>.tar.gz")
    parser.add_argument("--public-key", type=Path, default=None,
                        help="PEM public key file (else env "
                             f"{_ENV_PUBLIC_KEY} / {_ENV_PUBLIC_KEY_FILE})")
    args = parser.parse_args()

    try:
        key_file = str(args.public_key) if args.public_key else None
        public_key_pem = load_public_key_pem(key_file=key_file)
        manifest = verify_bundle(args.bundle, public_key_pem)
    except BundleVerificationError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        "OK: "
        f"version={manifest['runtime_bundle_version']} "
        f"platform={manifest['platform']} "
        f"artifacts={len(manifest['artifacts'])} "
        f"engine_stub={manifest['engine_stub']} "
        f"created_at={manifest['created_at']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
