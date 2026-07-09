#!/usr/bin/env python3
"""Build + code-sign + RS256-sign the Secure Enclave helper for shipping in the sidecar wheel.

Runs on a macOS CI runner (owner/release-time). Produces, in the output dir:
  * ``algenta-se-helper``  — the compiled Mach-O (optionally code-signed with hardened runtime)
  * ``manifest.json``      — canonical manifest ({format_version, platform, artifacts:[{name,sha256,size_bytes}]},
                             sorted keys, compact separators — the EXACT bytes the runtime verifier checks)
  * ``manifest.sig``       — RS256 (PKCS#1 v1.5, SHA-256) signature over manifest.json by the release key

so ``apps/runtime/hardware_key_store.SecureEnclaveKeyStore`` resolves + VERIFIES it at runtime instead of
JIT-compiling with swiftc. The clean-machine contract holds: a release ships this prebuilt binary, no
compiler at runtime.

Usage (release, from a macOS runner with swiftc):
    ALGENTA_SIGNING_KEY="$(cat release_priv.pem)" \
    ALGENTA_SE_CODESIGN_IDENTITY="Developer ID Application: …" \
    python scripts/build_se_helper.py \
        --out packages/algenta-runtime-native/algenta_runtime_native/se --platform macos-arm64

Local/dev (ad-hoc codesign, ephemeral test key):
    python scripts/build_se_helper.py --out /tmp/se --key /tmp/test_priv.pem
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# The helper source is a committed file (single source of truth with the dev-JIT path). Read it directly —
# do NOT import the runtime module (keeps this script dependency-light for CI: no structlog/app imports).
_SWIFT_SRC = Path(__file__).resolve().parent.parent / "apps" / "runtime" / "se_helper.swift"


def _load_swift_source() -> str:
    return _SWIFT_SRC.read_text(encoding="utf-8")


def _swiftc() -> str | None:
    found = shutil.which("swiftc")
    if found:
        return found
    for cand in ("/Library/Developer/CommandLineTools/usr/bin/swiftc", "/usr/bin/swiftc"):
        if Path(cand).exists():
            return cand
    return None


def _default_platform() -> str:
    if sys.platform != "darwin":
        return "unsupported"
    machine = os.uname().machine
    return "macos-arm64" if machine == "arm64" else "macos-x86_64"


def _compile(swiftc: str, out_binary: Path) -> None:
    src = out_binary.parent / "_se_helper.swift"
    src.write_text(_load_swift_source(), encoding="utf-8")
    try:
        res = subprocess.run(  # noqa: S603
            [swiftc, "-O", str(src), "-o", str(out_binary)], capture_output=True, text=True, timeout=300
        )
        if res.returncode != 0:
            raise SystemExit(f"swiftc failed:\n{res.stderr}")
    finally:
        src.unlink(missing_ok=True)


def _codesign(binary: Path, identity: str | None) -> None:
    # Hardened runtime + timestamp with a Developer ID for release; ad-hoc ('-') for local/dev.
    ident = identity or "-"
    args = ["codesign", "--force", "--options", "runtime", "--sign", ident, str(binary)]
    if identity:
        args.insert(1, "--timestamp")
    res = subprocess.run(args, capture_output=True, text=True)  # noqa: S603
    if res.returncode != 0:
        # ad-hoc signing failures are non-fatal for dev; a real identity failing IS fatal
        msg = f"codesign ({'identity' if identity else 'ad-hoc'}) failed: {res.stderr.strip()}"
        if identity:
            raise SystemExit(msg)
        print(f"warning: {msg}", file=sys.stderr)


def _sign_manifest(manifest_bytes: bytes, key_pem: str) -> bytes:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    key = serialization.load_pem_private_key(key_pem.encode(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise SystemExit("ALGENTA_SIGNING_KEY / --key must be an RSA private key (PKCS#8 PEM)")
    return key.sign(manifest_bytes, padding.PKCS1v15(), hashes.SHA256())


def main() -> int:
    ap = argparse.ArgumentParser(description="Build + sign the Secure Enclave helper for the sidecar wheel.")
    ap.add_argument("--out", required=True, help="Output dir (e.g. .../algenta_runtime_native/se).")
    ap.add_argument("--platform", default=None, help="Manifest platform tag (default: this host's macos-<arch>).")
    ap.add_argument("--key", default=None, help="RSA private key PEM path (else $ALGENTA_SIGNING_KEY inline).")
    args = ap.parse_args()

    if sys.platform != "darwin":
        raise SystemExit("the Secure Enclave helper can only be built on macOS")
    swiftc = _swiftc()
    if swiftc is None:
        raise SystemExit("swiftc not found — install the Xcode Command Line Tools")

    key_pem = None
    if args.key:
        key_pem = Path(args.key).read_text(encoding="utf-8")
    elif os.environ.get("ALGENTA_SIGNING_KEY"):
        key_pem = os.environ["ALGENTA_SIGNING_KEY"]
    if not key_pem:
        raise SystemExit("no signing key: pass --key or set ALGENTA_SIGNING_KEY (release refuses to ship unsigned)")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    binary = out / "algenta-se-helper"
    platform = args.platform or _default_platform()

    print(f"compiling {binary} …")
    _compile(swiftc, binary)
    _codesign(binary, os.environ.get("ALGENTA_SE_CODESIGN_IDENTITY"))

    data = binary.read_bytes()
    manifest = {
        "format_version": 1,
        "platform": platform,
        "artifacts": [
            {"name": "algenta-se-helper", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
        ],
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    (out / "manifest.json").write_bytes(manifest_bytes)
    (out / "manifest.sig").write_bytes(_sign_manifest(manifest_bytes, key_pem))

    print(json.dumps({
        "status": "ok",
        "binary": str(binary),
        "platform": platform,
        "sha256": manifest["artifacts"][0]["sha256"],
        "signed": True,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
