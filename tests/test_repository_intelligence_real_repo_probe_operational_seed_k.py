"""Tests for repository_intelligence_real_repo_probe: operational_seed_k.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_without_diagnostics_balances_polyglot_manifest_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "polyglot-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{\n'
        '  "name": "polyglot-profile",\n'
        '  "scripts": { "dev": "vite" }\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "src" / "main.tsx").write_text("export const bootstrap = 1;\n", encoding="utf-8")
    (repo_path / "src" / "App.tsx").write_text("export const App = () => null;\n", encoding="utf-8")
    (repo_path / "lib" / "polyglot_profile_repo.rb").write_text(
        "module PolyglotProfileRepo\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "node" in seed_plan["detected_ecosystems"]
    assert "ruby" in seed_plan["detected_ecosystems"]
    assert "src/main.tsx" in seed_plan["entrypoint_files"]
    assert "lib/polyglot_profile_repo.rb" in seed_plan["entrypoint_files"]


