#!/usr/bin/env python3
"""Release-blocking guard for the vendored forked-Cline agent-core.

Enforces the Apache-2.0 / telemetry red lines from the Algenta Repositories plan
(see agent-core/CLINE_FORK.md):

  1. Never depend on the npm ``@cline/core`` / ``@cline/sdk`` packages. Their
     published npm manifests omit a license field (=> "Proprietary"); we vendor
     from the Apache-2.0 GitHub source instead. So no lockfile may reference them.
  2. No ``cline.bot`` host strings or PostHog keys in shipped agent-core files
     (docs may mention them; shipped code/config may not).
  3. Every vendored Cline source file carries an Apache-2.0 license header.

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
# Vendored Cline source will live under one of these once the adapter is wired.
_VENDOR_DIRS = ("agent-core/vendor", "agent-core/cline")
_CODE_SUFFIXES = {".ts", ".mts", ".cts", ".js", ".mjs", ".cjs", ".tsx", ".jsx"}


def _iter_files(base: Path, suffixes: set[str] | None = None):
    if not base.exists():
        return
    for path in sorted(base.rglob("*")):
        if not path.is_file() or "node_modules" in path.parts:
            continue
        if suffixes is not None and path.suffix not in suffixes:
            continue
        yield path


def scan_lockfiles_for_npm_cline(root: Path) -> list[str]:
    """Fail if any lockfile references the npm @cline/core | @cline/sdk packages."""
    violations: list[str] = []
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.name not in _LOCKFILE_NAMES
            or "node_modules" in path.parts
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _NPM_CLINE_RE.search(text):
            violations.append(
                f"{path.relative_to(root)}: references npm @cline/core|@cline/sdk — "
                "vendor from the Apache-2.0 source instead (npm manifests are unlicensed)."
            )
    return violations


def scan_for_telemetry_endpoints(root: Path) -> list[str]:
    """Fail if shipped agent-core code/config carries cline.bot or a PostHog key."""
    violations: list[str] = []
    for path in _iter_files(root / _AGENT_CORE_DIR):
        if path.suffix == ".md":  # docs may legitimately reference cline.bot
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = _TELEMETRY_RE.search(text)
        if match:
            violations.append(
                f"{path.relative_to(root)}: contains telemetry endpoint/key "
                f"'{match.group(0)}' — strip cline.bot endpoints / PostHog keys."
            )
    return violations


def scan_vendored_apache_headers(root: Path) -> list[str]:
    """Fail if a vendored Cline source file lacks an Apache-2.0 header."""
    violations: list[str] = []
    for vendor in _VENDOR_DIRS:
        for path in _iter_files(root / vendor, suffixes=_CODE_SUFFIXES):
            try:
                head = path.read_text(encoding="utf-8", errors="ignore")[:2000]
            except OSError:
                continue
            if not any(marker in head for marker in _APACHE_MARKERS):
                violations.append(
                    f"{path.relative_to(root)}: vendored Cline file missing an "
                    "Apache-2.0 license header."
                )
    return violations


def run_guards(root: Path) -> list[str]:
    return [
        *scan_lockfiles_for_npm_cline(root),
        *scan_for_telemetry_endpoints(root),
        *scan_vendored_apache_headers(root),
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
        "cline-fork guard OK: no npm @cline deps, no telemetry endpoints in shipped "
        "agent-core, vendored headers clean."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
