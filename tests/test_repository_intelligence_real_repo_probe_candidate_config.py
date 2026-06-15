"""Tests for repository_intelligence_real_repo_probe: candidate_config.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_candidate_config_focus_paths_includes_nearby_tsconfig_files(tmp_path: Path) -> None:
    repo_path = _typescript_rootdir_repo(tmp_path)

    config_paths = _candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_base_path=repo_path / "services" / "app",
        diagnostic_project_path="services/app/tsconfig.test.json",
    )

    assert "services/app/tsconfig.test.json" in config_paths
    assert "services/app/tsconfig.json" in config_paths
    assert "packages/common/package.json" not in config_paths


def test_candidate_config_focus_paths_excludes_resolved_files_outside_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    app_path = repo_path / "services" / "app"
    app_path.mkdir(parents=True)
    external_path = tmp_path / "external"
    external_path.mkdir()
    (external_path / "package.json").write_text('{"name":"external"}', encoding="utf-8")
    (app_path / "package.json").symlink_to(external_path / "package.json")

    config_paths = _candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=["services/app"],
        diagnostic_base_path=app_path,
        diagnostic_project_path=None,
    )

    assert config_paths == []

