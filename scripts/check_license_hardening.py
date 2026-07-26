#!/usr/bin/env python3
"""Production license-hardening preflight / build guard.

Run before serving a production/licensed deployment to assert the verifier is hardened:
  * RS256-only mode is enforced (no forgeable HS256 path reachable), and
  * a verification key is configured (offline public key or trust bundle), and
  * (best-effort) the source-visible HS256 dev secret is not the ONLY thing standing between an
    attacker and a valid license — i.e. RS256-only is on so the dev secret is inert.

Exits 0 when hardened, non-zero with the reasons otherwise. Intended for the production entrypoint
and CI (the "build-time" half — the production wheel sets ALGENTA_LICENSE_RS256_ONLY=1 and, ideally,
strips the dev secret; this guard fails the deploy if RS256-only is not actually in force).
"""
from __future__ import annotations

import os
import sys


def hardening_violations() -> list[str]:
    from apps.runtime.license import (
        _offline_license_public_keys,
        _rs256_only_enforced,
    )

    violations: list[str] = []
    if not _rs256_only_enforced():
        violations.append(
            "RS256-only mode is OFF: set ALGENTA_LICENSE_RS256_ONLY=1 (or ALGENTA_REQUIRE_LOCAL_LICENSE=1) "
            "so the forgeable HS256 path is unreachable in production."
        )
    keys = _offline_license_public_keys()
    has_bundle = bool((os.environ.get("ALGENTA_LICENSE_TRUST_BUNDLE") or "").strip()) or bool(
        (os.environ.get("ALGENTA_LICENSE_TRUST_BUNDLE_FILE") or "").strip()
    )
    if not keys and not has_bundle:
        violations.append(
            "no verification key configured: set ALGENTA_LOCAL_LICENSE_PUBLIC_KEY(_FILE) or "
            "ALGENTA_LICENSE_TRUST_BUNDLE(_FILE) so RS256 licenses can be verified."
        )
    return violations


def main() -> int:
    violations = hardening_violations()
    if violations:
        sys.stderr.write("license hardening preflight FAILED:\n  - " + "\n  - ".join(violations) + "\n")
        return 1
    sys.stdout.write("license hardening OK: RS256-only enforced + verification key configured\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
