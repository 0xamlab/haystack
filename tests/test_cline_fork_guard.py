"""Tests for the release-blocking forked-Cline license/telemetry guard.

`test_current_repo_has_no_violations` is the CI-enforced gate: it fails the build if
anyone vendors the npm @cline/* packages, leaks a cline.bot endpoint into shipped
agent-core code, or adds a vendored Cline file without an Apache-2.0 header.
"""

from __future__ import annotations

from pathlib import Path

from scripts.cline_fork_guard import (
    run_guards,
    scan_for_telemetry_endpoints,
    scan_lockfiles_for_npm_cline,
    scan_vendored_apache_headers,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_current_repo_has_no_violations():
    assert run_guards(_REPO_ROOT) == []


def test_detects_npm_cline_in_lockfile(tmp_path):
    (tmp_path / "bun.lock").write_text(
        '"@cline/core@0.0.44": { "resolved": "..." }\n', encoding="utf-8"
    )
    assert scan_lockfiles_for_npm_cline(tmp_path)

    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
    assert scan_lockfiles_for_npm_cline(clean) == []


def test_detects_telemetry_in_shipped_code(tmp_path):
    agent_core = tmp_path / "agent-core"
    agent_core.mkdir()
    (agent_core / "leak.mjs").write_text(
        'fetch("https://data.cline.bot/e");\n', encoding="utf-8"
    )
    assert scan_for_telemetry_endpoints(tmp_path)

    # Docs may legitimately reference cline.bot — not a violation.
    (agent_core / "leak.mjs").unlink()
    (agent_core / "CLINE_FORK.md").write_text(
        "based on cline.bot, with PostHog phc_abcdefghijklmnopqrstuvwxyz\n",
        encoding="utf-8",
    )
    assert scan_for_telemetry_endpoints(tmp_path) == []


def test_detects_posthog_key_in_shipped_code(tmp_path):
    agent_core = tmp_path / "agent-core"
    agent_core.mkdir()
    (agent_core / "telemetry.mjs").write_text(
        'const KEY = "phc_abcdefghijklmnopqrstuvwxyz0123";\n', encoding="utf-8"
    )
    assert scan_for_telemetry_endpoints(tmp_path)


def test_detects_missing_apache_header_in_vendored(tmp_path):
    vendor = tmp_path / "agent-core" / "vendor"
    vendor.mkdir(parents=True)
    no_header = vendor / "no_header.ts"
    no_header.write_text("export const x = 1;\n", encoding="utf-8")
    assert scan_vendored_apache_headers(tmp_path)

    no_header.write_text(
        "// SPDX-License-Identifier: Apache-2.0\nexport const x = 1;\n", encoding="utf-8"
    )
    assert scan_vendored_apache_headers(tmp_path) == []
