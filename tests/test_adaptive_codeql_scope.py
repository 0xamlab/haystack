"""Tests for scripts/adaptive_codeql_scope.py (adaptive/differential CodeQL scoping).

The scope decision is driven by the same Codna blast-radius graph engine scripts/test_impact.py
uses for CI test selection, with a deliberate bias: when in doubt scan MORE, never less. Every
assertion here pins one of those guarantees: empty diff -> skip, single-file diff -> closure
includes dependents, schedule/push -> full, scan-infrastructure or ambiguous input -> full,
non-extractable change (manifests/locks/docs) -> skip (never an empty-database differential).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "scripts" / "adaptive_codeql_scope.py"

STATIC_CONFIG = """name: Fixture source

paths-ignore:
  - benchmarks/**
  - tests/**
  - build/**
"""


def _load_tool():
    spec = importlib.util.spec_from_file_location("codeql_scope_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_fixture_repo(tmp_path: Path) -> Path:
    """A synthetic repo shaped like the real one: an import chain apps.core <- apps.service <-
    apps.api, a test importing the top, JS/TS sources, a workflow, and docs noise."""
    root = tmp_path / "repo"
    (root / ".github" / "codeql").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "apps").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "web").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    (root / ".github" / "codeql" / "codeql-config.yml").write_text(STATIC_CONFIG, encoding="utf-8")
    (root / ".github" / "workflows" / "ci.yml").write_text(
        "name: CI\non: push\njobs: {}\n", encoding="utf-8")
    (root / "apps" / "__init__.py").write_text("", encoding="utf-8")
    (root / "apps" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "apps" / "service.py").write_text("from apps.core import VALUE\n", encoding="utf-8")
    (root / "apps" / "api.py").write_text("from apps.service import VALUE\n", encoding="utf-8")
    (root / "tests" / "test_api.py").write_text(
        "from apps.api import VALUE\n\ndef test_value():\n    assert VALUE == 1\n",
        encoding="utf-8")
    (root / "web" / "app.ts").write_text("export const app = 1;\n", encoding="utf-8")
    (root / "web" / "util.js").write_text("module.exports = 1;\n", encoding="utf-8")
    (root / "docs" / "readme.md").write_text("docs\n", encoding="utf-8")
    return root


def _run_tool(args: list[str], *, env: dict[str, str] | None = None,
              cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_TOOL), *args],
        cwd=cwd or REPO_ROOT, capture_output=True, text=True,
        env={**os.environ, **(env or {})},
    )


def _decision(out: subprocess.CompletedProcess) -> dict:
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.splitlines()[0])


# ── decision contract ─────────────────────────────────────────────────────────────────────────────


def test_docs_only_diff_skips_every_language(tmp_path):
    root = _make_fixture_repo(tmp_path)
    for language in ("python", "javascript-typescript", "actions"):
        out = _run_tool(["--language", language, "--repo-root", str(root),
                         "--changed", "docs/readme.md"])
        data = _decision(out)
        assert data["decision"] == "skip", (language, data)
        assert data["scope_count"] == 0


def test_single_python_file_diff_scopes_to_blast_radius_closure(tmp_path):
    root = _make_fixture_repo(tmp_path)
    out = _run_tool(["--language", "python", "--repo-root", str(root),
                     "--changed", "apps/core.py", "--shared-core-fraction", "1.0"])
    data = _decision(out)
    assert data["decision"] == "differential", data
    scope = {ln.split(": ", 1)[1] for ln in out.stderr.splitlines() if ln.startswith("  scope: ")}
    # The closure: the changed leaf plus every transitive importer of it.
    assert scope == {"apps/core.py", "apps/service.py", "apps/api.py"}
    # paths-ignore'd trees never enter the scope even when they import the change.
    assert "tests/test_api.py" not in scope
    assert data["scope_count"] == 3
    assert data["config_path"].endswith(".yml")
    config_text = Path(data["config_path"]).read_text(encoding="utf-8")
    assert "paths:" in config_text
    assert '"apps/core.py"' in config_text
    # The static config's exclusions survive the merge.
    assert "paths-ignore:" in config_text
    assert '"tests/**"' in config_text


def test_middle_of_chain_diff_does_not_reach_upstream(tmp_path):
    root = _make_fixture_repo(tmp_path)
    out = _run_tool(["--language", "python", "--repo-root", str(root),
                     "--changed", "apps/service.py", "--shared-core-fraction", "1.0"])
    data = _decision(out)
    assert data["decision"] == "differential", data
    scope = {ln.split(": ", 1)[1] for ln in out.stderr.splitlines() if ln.startswith("  scope: ")}
    assert scope == {"apps/service.py", "apps/api.py"}


def test_javascript_leg_scopes_to_changed_sources_only(tmp_path):
    root = _make_fixture_repo(tmp_path)
    out = _run_tool(["--language", "javascript-typescript", "--repo-root", str(root),
                     "--changed", "web/app.ts", "apps/core.py"])
    data = _decision(out)
    assert data["decision"] == "differential", data
    scope = {ln.split(": ", 1)[1] for ln in out.stderr.splitlines() if ln.startswith("  scope: ")}
    assert scope == {"web/app.ts"}  # Python changes are invisible to the js-ts leg


def test_actions_leg_scopes_to_workflow_yaml_only(tmp_path):
    root = _make_fixture_repo(tmp_path)
    out = _run_tool(["--language", "actions", "--repo-root", str(root),
                     "--changed", ".github/workflows/ci.yml", "apps/core.py"])
    data = _decision(out)
    assert data["decision"] == "differential", data
    assert data["scope_count"] == 1


def test_schedule_event_is_always_full(tmp_path):
    root = _make_fixture_repo(tmp_path)
    out = _run_tool(["--language", "python", "--repo-root", str(root)],
                    env={"GITHUB_EVENT_NAME": "schedule"})
    data = _decision(out)
    assert data["decision"] == "full", data
    assert "schedule" in data["reason"]


def test_push_event_is_full_by_default_and_opt_in_diffs(tmp_path):
    root = _make_fixture_repo(tmp_path)
    # Default contract: push events never scope.
    out = _run_tool(["--language", "python", "--repo-root", str(root)],
                    env={"GITHUB_EVENT_NAME": "push"})
    assert _decision(out)["decision"] == "full"

    # Opt-in: a real two-commit repo + event payload scopes from event.before..event.after.
    def git(*args, cwd=root):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

    git("init", "-q", "-b", "main")
    git("add", "apps/core.py")
    git("commit", "-q", "-m", "base")
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                            capture_output=True, text=True).stdout.strip()
    (root / "apps" / "core.py").write_text("VALUE = 2\n", encoding="utf-8")
    git("add", "apps/core.py")
    git("commit", "-q", "-m", "change")
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                           capture_output=True, text=True).stdout.strip()
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"before": before, "after": after}), encoding="utf-8")
    out = _run_tool(["--language", "python", "--repo-root", str(root), "--allow-push-diff",
                     "--shared-core-fraction", "1.0"],
                    env={"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": str(event)})
    data = _decision(out)
    assert data["decision"] == "differential", data
    assert data["scope_count"] >= 1


def test_scan_infrastructure_changes_force_full(tmp_path):
    root = _make_fixture_repo(tmp_path)
    cases = [
        ("actions", ".github/codeql/codeql-config.yml"),
        ("python", "scripts/adaptive_codeql_scope.py"),
        ("javascript-typescript", "scripts/test_impact.py"),
        ("python", ".github/workflows/codeql.yml"),
    ]
    for language, changed in cases:
        root.joinpath(changed).parent.mkdir(parents=True, exist_ok=True)
        root.joinpath(changed).write_text("x\n", encoding="utf-8")
        out = _run_tool(["--language", language, "--repo-root", str(root), "--changed", changed])
        assert _decision(out)["decision"] == "full", (language, changed)


def test_manifest_only_diffs_skip_because_nothing_is_extractable(tmp_path):
    """Dependency manifests/lockfiles are not CodeQL extraction targets: a diff touching only
    them changes nothing the leg analyzes -> skip (never a differential with an empty database)."""
    root = _make_fixture_repo(tmp_path)
    cases = [
        ("python", "pyproject.toml"),
        ("python", "requirements-dev.txt"),
        ("javascript-typescript", "package.json"),
        ("javascript-typescript", "pnpm-lock.yaml"),
    ]
    for language, changed in cases:
        root.joinpath(changed).write_text("x\n", encoding="utf-8")
        out = _run_tool(["--language", language, "--repo-root", str(root), "--changed", changed])
        data = _decision(out)
        assert data["decision"] == "skip", (language, changed, data)
        assert data["scope_count"] == 0


def test_actions_leg_skips_nonextractable_github_yaml(tmp_path):
    root = _make_fixture_repo(tmp_path)
    (root / ".github" / "dependabot.yml").write_text("version: 2\n", encoding="utf-8")
    out = _run_tool(["--language", "actions", "--repo-root", str(root),
                     "--changed", ".github/dependabot.yml"])
    data = _decision(out)
    assert data["decision"] == "skip", data
    assert "extractable" in data["reason"]


def test_generated_config_paths_are_repo_relative(tmp_path):
    """CodeQL matches `paths:` against repository-relative URIs — every emitted scope entry must
    be a plain relative path (no leading '/', no './'), and must actually exist in the repo."""
    root = _make_fixture_repo(tmp_path)
    out = _run_tool(["--language", "python", "--repo-root", str(root),
                     "--changed", "apps/core.py", "--shared-core-fraction", "1.0"])
    data = _decision(out)
    assert data["decision"] == "differential", data
    import yaml
    generated = yaml.safe_load(Path(data["config_path"]).read_text(encoding="utf-8"))
    assert generated["paths"], "differential config must carry a non-empty paths list"
    for entry in generated["paths"]:
        assert not entry.startswith("/"), entry
        assert not entry.startswith("./"), entry
        assert not entry.startswith(".."), entry
        assert (root / entry).is_file(), entry


def test_deleted_files_are_not_seeds(tmp_path):
    root = _make_fixture_repo(tmp_path)
    out = _run_tool(["--language", "python", "--repo-root", str(root),
                     "--changed", "apps/gone.py"])
    assert _decision(out)["decision"] == "skip"


def test_oversized_closure_degrades_to_full(tmp_path):
    root = _make_fixture_repo(tmp_path)
    out = _run_tool(["--language", "python", "--repo-root", str(root),
                     "--changed", "apps/core.py", "--max-files", "1"])
    data = _decision(out)
    assert data["decision"] == "full", data
    assert "full scan is the honest scope" in data["reason"]


def test_pull_request_mode_diffs_against_merge_base(tmp_path):
    """Real mini repo pair (origin + clone): PR head vs merge-base(origin/main, HEAD)."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True)
    clone = tmp_path / "clone"

    def git(*args, cwd=clone):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

    git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
    (clone / ".github" / "codeql").mkdir(parents=True)
    (clone / ".github" / "codeql" / "codeql-config.yml").write_text(STATIC_CONFIG, encoding="utf-8")
    (clone / "apps").mkdir()
    (clone / "apps" / "__init__.py").write_text("", encoding="utf-8")
    (clone / "apps" / "base.py").write_text("BASE = 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    git("push", "-q", "origin", "main")
    git("checkout", "-q", "-b", "feature")
    (clone / "apps" / "new_module.py").write_text("from apps.base import BASE\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "feature change")

    tool = _load_tool()
    changed, reason = tool._changed_files_pull_request(clone, "main")
    assert changed == ["apps/new_module.py"], reason

    out = _run_tool(["--language", "python", "--repo-root", str(clone),
                     "--event-type", "pull_request", "--base-ref", "main",
                     "--shared-core-fraction", "1.0"])
    data = _decision(out)
    assert data["decision"] == "differential", data
    scope = {ln.split(": ", 1)[1] for ln in out.stderr.splitlines() if ln.startswith("  scope: ")}
    assert scope == {"apps/new_module.py"}


def test_github_output_contract(tmp_path):
    root = _make_fixture_repo(tmp_path)
    github_output = tmp_path / "gh_output.txt"
    out = _run_tool(["--language", "python", "--repo-root", str(root),
                     "--changed", "apps/core.py", "--shared-core-fraction", "1.0"],
                    env={"GITHUB_OUTPUT": str(github_output)})
    assert out.returncode == 0
    text = github_output.read_text(encoding="utf-8")
    assert "decision=differential" in text
    assert "config_path=" in text
    assert "scope_count=3" in text


# ── static config merge (YAML subset, stdlib only) ───────────────────────────────────────────────


def test_parse_static_config_round_trips_current_shape():
    tool = _load_tool()
    config = tool.parse_static_config(
        (REPO_ROOT / ".github" / "codeql" / "codeql-config.yml").read_text(encoding="utf-8"))
    assert config["name"] == "Algenta production source"
    assert config["paths-ignore"] == [
        "benchmarks/**", "tests/**", "build/**", "packages/python-sdk/build/**",
    ]


def test_parse_static_config_supports_one_level_maps_and_rejects_exotic_yaml():
    tool = _load_tool()
    config = tool.parse_static_config("name: X\npacks:\n  python: security-extended\n")
    assert config["packs"] == {"python": "security-extended"}
    with pytest.raises(ValueError):
        tool.parse_static_config("paths: [a, b]\n")
    with pytest.raises(ValueError):
        tool.parse_static_config("name: |\n  multiline\n")


def test_unknown_static_config_key_forces_full(tmp_path):
    root = _make_fixture_repo(tmp_path)
    (root / ".github" / "codeql" / "codeql-config.yml").write_text(
        "name: X\nfuture-key: 1\n", encoding="utf-8")
    out = _run_tool(["--language", "python", "--repo-root", str(root),
                     "--changed", "apps/core.py"])
    data = _decision(out)
    assert data["decision"] == "full", data
    assert "unsupported keys" in data["reason"]


def test_render_merged_config_keeps_static_exclusions_and_packs():
    tool = _load_tool()
    rendered = tool.render_merged_config(
        {"name": "Base", "paths-ignore": ["tests/**"], "packs": {"python": "security-extended"}},
        ["apps/core.py", "apps/service.py"], "python")
    assert "paths:" in rendered
    assert '  - "apps/core.py"' in rendered
    assert '  - "apps/service.py"' in rendered
    assert "paths-ignore:" in rendered
    assert '  - "tests/**"' in rendered
    assert "packs:" in rendered
    assert '  python: "security-extended"' in rendered


def test_blast_radius_engine_unavailable_forces_full(monkeypatch, tmp_path):
    tool = _load_tool()
    root = _make_fixture_repo(tmp_path)
    monkeypatch.setattr(tool, "_load_test_impact", lambda: None)
    decision, _, reason = tool.compute_scope(
        language="python", root=root, changed=["apps/core.py"],
        static_config_text=(root / ".github" / "codeql" / "codeql-config.yml").read_text(
            encoding="utf-8"),
        max_files=100, shared_core_fraction=0.4)
    assert decision == "full"
    assert "unavailable" in reason


# ── one real-repo smoke test (fast path only: global-broad, no graph build) ───────────────────────


def test_cli_real_repo_scan_infrastructure_change_is_full():
    out = _run_tool(["--language", "python",
                     "--changed", "scripts/adaptive_codeql_scope.py"])
    data = _decision(out)
    assert data["decision"] == "full", data
