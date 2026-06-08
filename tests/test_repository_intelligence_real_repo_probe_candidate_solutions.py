"""Tests for repository_intelligence_real_repo_probe: candidate_solutions.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_candidate_solutions_specialize_typescript_rootdir_drift() -> None:
    repo_path = Path("/tmp/repo")
    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=(
            "services/execution-service/src/index.ts(12,5): error TS6059: "
            "File is not under 'rootDir'.\n"
            "packages/common/src/execution.ts(4,1): error TS6059: "
            "File is not under 'rootDir'.\n"
        ),
    )

    solutions = _candidate_solutions(diagnostics)

    assert len(solutions) == 1
    assert solutions[0]["problem_class"] == "typescript_rootdir_drift"
    assert solutions[0]["diagnostic_count"] == 2
    assert "project references" in " ".join(solutions[0]["candidate_actions"]).lower()


