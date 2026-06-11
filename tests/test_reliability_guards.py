"""Tests for the modular reliability guards (Wave A0).

Verifies: the guards auto-discover; the committed baseline keeps the *repo itself*
free of NEW violations (this is the regression gate, in pytest form); and each guard
actually detects a freshly-planted violation in an isolated tree."""

from __future__ import annotations

from pathlib import Path

from scripts.reliability_guards import GUARDS, run_guards

EXPECTED_GUARDS = {"raw_egress", "boundary_imports", "sync_sidecar", "github_workflows"}


def test_guards_auto_discovered():
    assert EXPECTED_GUARDS <= set(GUARDS), f"missing guards: {EXPECTED_GUARDS - set(GUARDS)}"
    # every guard is a complete spec
    for g in GUARDS.values():
        assert g.name and g.description and callable(g.scan)


def test_repo_has_no_new_violations():
    """The actual CI gate: with the committed baseline, the repo has zero NEW violations."""
    result = run_guards()
    offenders = {name: r["new"] for name, r in result.items() if r["new"]}
    assert not offenders, f"new reliability-guard violations: {offenders}"


def _write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_raw_egress_detects_new(tmp_path: Path):
    _write(tmp_path, "apps/x.py", "import httpx\n\ndef f():\n    return httpx.get('http://x')\n")
    # an allowed wrapper is exempt
    _write(tmp_path, "apps/api_server/services/egress_guard.py", "import httpx\nhttpx.get('http://ok')\n")
    found = {v.path for v in GUARDS["raw_egress"].scan(tmp_path)}
    assert "apps/x.py" in found
    assert "apps/api_server/services/egress_guard.py" not in found


def test_boundary_imports_detects_new(tmp_path: Path):
    _write(tmp_path, "scripts/x.py", "from apps.api_server.services import repository_intelligence_core\n")
    _write(tmp_path, "scripts/ok.py", "from decision_engine import AsyncAlgentaClient\n")
    found = {v.path for v in GUARDS["boundary_imports"].scan(tmp_path)}
    assert "scripts/x.py" in found
    assert "scripts/ok.py" not in found


def test_sync_sidecar_detects_new(tmp_path: Path):
    _write(tmp_path, "apps/api_server/routers/repositories.py", "def h():\n    r = run_agent(spec)\n    return r\n")
    found = {v.path for v in GUARDS["sync_sidecar"].scan(tmp_path)}
    assert "apps/api_server/routers/repositories.py" in found


def test_github_workflows_flags_dangerous_only(tmp_path: Path):
    danger = (
        "on:\n  pull_request_target:\n"
        "permissions:\n  contents: write\n"
        "jobs:\n  x:\n    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "        with:\n          ref: ${{ github.event.pull_request.head.sha }}\n"
    )
    safe = (
        "on:\n  pull_request:\n"
        "permissions:\n  contents: read\n"
        "jobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n"
    )
    _write(tmp_path, ".github/workflows/danger.yml", danger)
    _write(tmp_path, ".github/workflows/safe.yml", safe)
    found = {v.path for v in GUARDS["github_workflows"].scan(tmp_path)}
    assert ".github/workflows/danger.yml" in found
    assert ".github/workflows/safe.yml" not in found
    # github_workflows is never baselined — any hit is fatal
    assert GUARDS["github_workflows"].baselined is False
