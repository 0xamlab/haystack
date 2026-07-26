#!/usr/bin/env python3
"""Production-wheel hardening: physically strip the HS256 dev secret from a packaged tree.

The runtime already refuses HS256 under RS256-only mode; this is defense-in-depth so the SHIPPED
artifact does not even contain the forgeable secret. Run against a staging copy of the package
before building the production wheel (or against an unpacked wheel):

    python3 scripts/strip_dev_stub.py --package-root build/wheel-staging

It (1) deletes ``apps/runtime/_dev_license_stub.py`` (the sole home of the dev secret), then
(2) greps the remaining tree for the secret literal and FAILS if any copy survives. With the stub
gone, ``apps.runtime.license`` sets ``_DEV_SECRET=None`` and the HS256 dev-stub path is unreachable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The literal we must guarantee is absent from a production artifact. Kept here (a build tool, never
# shipped) as the search needle.
_DEV_SECRET_NEEDLE = "algenta-dev-local-v1-not-for-production"
_STUB_RELATIVE = Path("apps/runtime/_dev_license_stub.py")


def strip_and_verify(package_root: Path) -> list[str]:
    """Delete the dev stub (source AND compiled bytecode) under ``package_root`` then return a list
    of files still containing the secret needle (empty = hardened). Never raises for a missing stub
    (idempotent).

    Scans ALL files as BYTES (not just ``*.py``) so a ``__pycache__/*.pyc`` or a compiled ``*.so``
    embedding the literal in its code constants is caught — grepping only ``*.py`` gave a false
    'secret absent' when the staged tree was byte-compiled."""
    stub = package_root / _STUB_RELATIVE
    if stub.exists():
        stub.unlink()
    # Remove any compiled artifacts of the stub (e.g. __pycache__/_dev_license_stub.cpython-*.pyc).
    for cache in package_root.rglob("__pycache__"):
        for pyc in cache.glob("_dev_license_stub.*"):
            try:
                pyc.unlink()
            except OSError:
                pass

    needle = _DEV_SECRET_NEEDLE.encode("utf-8")
    offenders: list[str] = []
    for path in package_root.rglob("*"):
        if not path.is_file() or path.name == "strip_dev_stub.py":
            continue  # this build tool legitimately holds the needle
        try:
            if needle in path.read_bytes():
                offenders.append(str(path.relative_to(package_root)))
        except OSError:
            continue
    return offenders


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip the dev license stub from a packaged tree.")
    parser.add_argument("--package-root", required=True, help="Root of the staged package / unpacked wheel.")
    args = parser.parse_args()

    root = Path(args.package_root).expanduser()
    if not root.is_dir():
        sys.stderr.write(f"package root not found: {root}\n")
        return 2

    offenders = strip_and_verify(root)
    if offenders:
        sys.stderr.write(
            "dev secret still present after strip (build is NOT hardened):\n  - "
            + "\n  - ".join(offenders)
            + "\n"
        )
        return 1
    sys.stdout.write("dev stub stripped; production tree contains no HS256 dev secret\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
