"""Tests for repository_intelligence_real_repo_probe: should_use.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_should_use_seeded_profile_candidate_scan_skips_scattered_small_root_sets() -> None:
    assert (
        _should_use_seeded_profile_candidate_scan(
            seed_paths=[],
            bridge_paths=[
                "play-functional/src/main/scala",
                "play-json-joda/src/main/scala",
                "play-json/js-native/src",
                "play-json/js/src",
                "play-json/jvm-native/src",
                "play-json/jvm/src/main/scala",
                "play-json/native/src/main/scala",
                "play-json/shared/src/main/scala",
            ],
        )
        is False
    )


def test_should_use_seeded_profile_candidate_scan_keeps_seeded_single_group_root_sets() -> None:
    assert (
        _should_use_seeded_profile_candidate_scan(
            seed_paths=[],
            bridge_paths=[
                "os/src",
                "os/src-2",
                "os/src-3",
                "os/src-jvm",
                "os/src-native",
                "os/watch/src",
                "os/zip/src",
            ],
        )
        is True
    )
    assert (
        _should_use_seeded_profile_candidate_scan(
            seed_paths=["pkgs/app/lib/app.dart"],
            bridge_paths=[
                "pkgs/app/lib",
                "pkgs/http/lib",
                "pkgs/http_profile/lib",
            ],
        )
        is True
    )


