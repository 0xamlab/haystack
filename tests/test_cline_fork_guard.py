"""Tests for the release-blocking forked-Cline license/telemetry guard.

`test_current_repo_has_no_violations` is the CI-enforced gate: it fails the build if
OUR product depends on the npm @cline/* packages, leaks a cline.bot endpoint into our
agent-core code, or a vendored upstream tree is missing its Apache-2.0 LICENSE/NOTICE.
The vendored upstream source (agent-core/vendor/**) is third-party and exempt from the
npm/telemetry scans.
"""

from __future__ import annotations

from pathlib import Path

from scripts.cline_fork_guard import (
    run_guards,
    scan_for_telemetry_endpoints,
    scan_lockfiles_for_npm_cline,
    scan_vendored_attribution,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_current_repo_has_no_violations():
    assert run_guards(_REPO_ROOT) == []


def test_detects_npm_cline_in_our_lockfile_but_not_vendored(tmp_path):
    # Our own lockfile referencing npm @cline -> violation.
    (tmp_path / "bun.lock").write_text(
        '"@cline/core@0.0.44": { "resolved": "..." }\n', encoding="utf-8"
    )
    assert scan_lockfiles_for_npm_cline(tmp_path)

    # The SAME reference inside a vendored tree is exempt (third-party upstream).
    vendored_lock = tmp_path / "agent-core" / "vendor" / "cline"
    vendored_lock.mkdir(parents=True)
    (vendored_lock / "bun.lock").write_text(
        '"@cline/core@0.0.44": { "resolved": "..." }\n', encoding="utf-8"
    )
    # Remove the top-level offending lock; only the vendored one remains -> clean.
    (tmp_path / "bun.lock").unlink()
    assert scan_lockfiles_for_npm_cline(tmp_path) == []


def test_detects_telemetry_in_our_code_but_not_vendored(tmp_path):
    agent_core = tmp_path / "agent-core"
    agent_core.mkdir()
    (agent_core / "leak.mjs").write_text('fetch("https://data.cline.bot/e");\n', encoding="utf-8")
    assert scan_for_telemetry_endpoints(tmp_path)

    # Docs and vendored upstream source are exempt.
    (agent_core / "leak.mjs").unlink()
    (agent_core / "NOTES.md").write_text("based on cline.bot\n", encoding="utf-8")
    vendored = agent_core / "vendor" / "cline" / "sdk"
    vendored.mkdir(parents=True)
    (vendored / "env.ts").write_text('const H = "https://data.cline.bot";\n', encoding="utf-8")
    assert scan_for_telemetry_endpoints(tmp_path) == []


def test_detects_posthog_key_in_our_code(tmp_path):
    agent_core = tmp_path / "agent-core"
    agent_core.mkdir()
    (agent_core / "telemetry.mjs").write_text(
        'const KEY = "phc_abcdefghijklmnopqrstuvwxyz0123";\n', encoding="utf-8"
    )
    assert scan_for_telemetry_endpoints(tmp_path)


def test_vendored_tree_requires_license_and_notice(tmp_path):
    tree = tmp_path / "agent-core" / "vendor" / "cline"
    tree.mkdir(parents=True)
    (tree / "package.json").write_text('{"name":"@cline/packages"}\n', encoding="utf-8")
    # Missing LICENSE + NOTICE -> violations.
    assert len(scan_vendored_attribution(tmp_path)) == 2

    (tree / "LICENSE").write_text("                Apache License\n           Version 2.0\n", encoding="utf-8")
    (tree / "NOTICE").write_text("Based on Cline, Apache-2.0.\n", encoding="utf-8")
    assert scan_vendored_attribution(tmp_path) == []
