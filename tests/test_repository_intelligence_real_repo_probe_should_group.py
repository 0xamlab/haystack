"""Tests for repository_intelligence_real_repo_probe: should_group.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_should_group_focus_path_scan_prefers_large_diverse_root_sets() -> None:
    roots = [f"pkg_{index}/src" for index in range(24)]

    assert _should_group_focus_path_scan(roots) is True


def test_should_group_focus_path_scan_prefers_large_shared_parent_sets() -> None:
    roots = [f"pkgs/pkg_{index}/lib" for index in range(20)]

    assert _should_group_focus_path_scan(roots) is True


def test_should_group_focus_path_scan_skips_medium_multi_group_sets() -> None:
    roots = [
        "buildSrc/src/main/groovy",
        "doc/manual/src",
        "doc/site/src",
        "integration/geb-gradle/src/main/groovy",
        "integration/geb-testcontainers/src/main/groovy",
        "internal/test-support/src/main/groovy",
        "module/a/src/main/groovy",
        "module/b/src/main/groovy",
        "module/c/src/main/groovy",
        "module/d/src/main/groovy",
        "module/e/src/main/groovy",
        "module/f/src/main/groovy",
        "module/g/src/main/groovy",
        "module/h/src/main/groovy",
        "module/i/src/main/groovy",
        "module/j/src/main/groovy",
        "module/k/src/main/groovy",
        "module/l/src/main/groovy",
        "module/m/src/main/groovy",
        "module/n/src/main/groovy",
        "module/o/src/main/groovy",
        "module/p/src/main/groovy",
    ]

    assert _should_group_focus_path_scan(roots) is False


def test_should_group_focus_path_scan_prefers_medium_source_root_sets() -> None:
    roots = [
        "play-functional/src/main/scala",
        "play-json-joda/src/main/scala",
        "play-json/js-native/src",
        "play-json/js/src",
        "play-json/jvm-native/src",
        "play-json/jvm/src/main/scala",
        "play-json/native/src/main/scala",
        "play-json/shared/src/main/scala",
        "project",
    ]

    assert _should_group_focus_path_scan(roots) is False
    assert _should_group_focus_path_scan(roots[:-1]) is True


