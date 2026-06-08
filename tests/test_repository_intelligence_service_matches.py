"""Tests for repository_intelligence_service: matches.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_matches_repository_pattern_treats_recursive_glob_as_optional_for_direct_children() -> None:
    assert repository_service._matches_repository_pattern("src/main.cpp", "src/**/*.cpp")
    assert repository_service._matches_repository_pattern("src/acme/main.cpp", "src/**/*.cpp")
    assert repository_service._matches_repository_pattern(
        "include/acme/core.hpp",
        "include/**/*.hpp",
    )


