"""Tests for repository_intelligence_real_repo_probe: resolve_diagnostic.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_resolve_diagnostic_base_path_infers_cd_command(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    (repo_path / "services" / "execution-service").mkdir(parents=True)

    resolved = _resolve_diagnostic_base_path(
        repo_path,
        diagnostic_command="cd services/execution-service && pnpm exec tsc --noEmit",
        diagnostic_base_path=None,
    )

    assert resolved == (repo_path / "services" / "execution-service").resolve()


def test_resolve_diagnostic_project_path_infers_project_argument(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    (repo_path / "services" / "execution-service").mkdir(parents=True)
    (repo_path / "services" / "execution-service" / "tsconfig.test.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    resolved = _resolve_diagnostic_project_path(
        repo_path,
        diagnostic_command="pnpm exec tsc -p tsconfig.test.json --noEmit",
        diagnostic_base_path=repo_path / "services" / "execution-service",
    )

    assert resolved == "services/execution-service/tsconfig.test.json"


