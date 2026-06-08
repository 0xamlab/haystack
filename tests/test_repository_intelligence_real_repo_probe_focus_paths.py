"""Tests for repository_intelligence_real_repo_probe: focus_paths.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_focus_paths_from_diagnostics_prefers_explicit_and_diagnostic_paths(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    repo_path.mkdir()
    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=(
            "services/execution-service/src/index.ts(12,5): error TS6059: "
            "File is not under 'rootDir'.\n"
        ),
    )

    focus_paths = _focus_paths_from_diagnostics(
        repo_path=repo_path,
        diagnostics=diagnostics,
        explicit_focus_paths=["services/execution-service"],
    )

    assert focus_paths == [
        "services/execution-service",
        "services/execution-service/src/index.ts",
        "services/execution-service/src",
    ]


