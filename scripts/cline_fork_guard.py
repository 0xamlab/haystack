#!/usr/bin/env python3
"""Release-blocking guard for the vendored forked-Cline agent-core.

Enforces the Apache-2.0 / telemetry red lines from the Algenta Repositories plan:

  1. OUR product must not DEPEND on the npm ``@cline/core`` / ``@cline/sdk``
     packages (their published npm manifests omit a license => "Proprietary"); we
     vendor from the Apache-2.0 GitHub source instead. So no lockfile OUTSIDE the
     vendored tree may reference them. The vendored upstream's own lockfile is
     third-party source, not our dependency graph, and is exempt.
  2. OUR agent-core code/config must not carry ``cline.bot`` hosts or PostHog keys.
     The vendored upstream source (``agent-core/vendor/**``) is third-party and
     exempt from this scan — its operated endpoints are neutralized at the
     build/runtime layer (telemetry is a no-op in our headless local config; the
     build-time strip is tracked separately). Docs (``*.md``) are exempt.
  3. Each vendored upstream tree (``agent-core/vendor/<name>/`` containing a
     ``package.json``) must retain its Apache-2.0 ``LICENSE`` and a ``NOTICE`` —
     the actual Apache-2.0 redistribution obligation, NOT per-file headers.

Run: ``python3 scripts/cline_fork_guard.py`` — exits non-zero on any violation.
Importable: ``from scripts.cline_fork_guard import run_guards``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_LOCKFILE_NAMES = {
    "bun.lock",
    "bun.lockb",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}
_NPM_CLINE_RE = re.compile(r"@cline/(core|sdk)\b")
_TELEMETRY_RE = re.compile(r"cline\.bot|phc_[A-Za-z0-9]{20,}")
_APACHE_MARKERS = ("Apache License", "SPDX-License-Identifier: Apache-2.0")

_AGENT_CORE_DIR = "agent-core"


def _is_under_vendor(rel_parts: tuple[str, ...]) -> bool:
    """True if a repo-relative path is inside an ``agent-core/vendor/`` tree."""
    for i in range(len(rel_parts) - 1):
        if rel_parts[i] == "agent-core" and rel_parts[i + 1] == "vendor":
            return True
    return False


def scan_lockfiles_for_npm_cline(root: Path) -> list[str]:
    """Fail if a lockfile OUTSIDE the vendored tree references npm @cline/core|@cline/sdk."""
    violations: list[str] = []
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.name not in _LOCKFILE_NAMES
            or "node_modules" in path.parts
        ):
            continue
        rel = path.relative_to(root)
        if _is_under_vendor(rel.parts):
            continue  # vendored upstream's own lockfile — third-party, not our deps
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _NPM_CLINE_RE.search(text):
            violations.append(
                f"{rel}: our lockfile references npm @cline/core|@cline/sdk — vendor "
                "from the Apache-2.0 source instead (npm manifests are unlicensed)."
            )
    return violations


def scan_for_telemetry_endpoints(root: Path) -> list[str]:
    """Fail if OUR agent-core code/config (not the vendored upstream) carries a
    cline.bot host or PostHog key."""
    base = root / _AGENT_CORE_DIR
    violations: list[str] = []
    if not base.exists():
        return violations
    for path in sorted(base.rglob("*")):
        if not path.is_file() or "node_modules" in path.parts or path.suffix == ".md":
            continue
        rel = path.relative_to(root)
        if _is_under_vendor(rel.parts):
            continue  # third-party vendored source — endpoints neutralized at build/runtime
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = _TELEMETRY_RE.search(text)
        if match:
            violations.append(
                f"{rel}: contains telemetry endpoint/key '{match.group(0)}' in our "
                "agent-core code — strip cline.bot endpoints / PostHog keys."
            )
    return violations


def scan_vendored_attribution(root: Path) -> list[str]:
    """Each vendored upstream tree (agent-core/vendor/<name>/ with a package.json)
    must retain an Apache-2.0 LICENSE and a NOTICE (the Apache redistribution duty)."""
    violations: list[str] = []
    vendor_root = root / _AGENT_CORE_DIR / "vendor"
    if not vendor_root.exists():
        return violations
    for child in sorted(vendor_root.iterdir()):
        if not child.is_dir() or not (child / "package.json").exists():
            continue
        rel = child.relative_to(root)
        license_path = child / "LICENSE"
        if not license_path.exists() or not any(
            marker in license_path.read_text(encoding="utf-8", errors="ignore")
            for marker in _APACHE_MARKERS
        ):
            violations.append(f"{rel}: vendored tree missing an Apache-2.0 LICENSE.")
        if not (child / "NOTICE").exists():
            violations.append(
                f"{rel}: vendored tree missing a NOTICE (Apache-2.0 attribution)."
            )
    return violations


def run_guards(root: Path) -> list[str]:
    return [
        *scan_lockfiles_for_npm_cline(root),
        *scan_for_telemetry_endpoints(root),
        *scan_vendored_attribution(root),
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations = run_guards(root)
    if violations:
        print("cline-fork guard FAILED:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1
    print(
        "cline-fork guard OK: no npm @cline deps in our lockfiles, no telemetry "
        "endpoints in our agent-core code, vendored trees carry LICENSE + NOTICE."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
