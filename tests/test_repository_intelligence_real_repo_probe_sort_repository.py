"""Tests for repository_intelligence_real_repo_probe: sort_repository.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_sort_repository_languages_prefers_popularity_rank_before_name() -> None:
    assert sort_repository_languages(
        {"nim", "typescript", "python", "swift", "node", "dotnet", "groovy"}
    ) == [
        "typescript",
        "python",
        "node",
        "dotnet",
        "swift",
        "groovy",
        "nim",
    ]


