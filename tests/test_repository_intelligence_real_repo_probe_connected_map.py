"""Tests for repository_intelligence_real_repo_probe: connected_map.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_connected_map_candidate_file_limit_scales_with_graph_budget() -> None:
    assert (
        _connected_map_candidate_file_limit(
            max_files=4_000,
            max_connected_files=192,
            concrete_seed_count=0,
        )
        == 800
    )
    assert (
        _connected_map_candidate_file_limit(
            max_files=1_200,
            max_connected_files=400,
            concrete_seed_count=0,
        )
        == 1200
    )
    assert (
        _connected_map_candidate_file_limit(
            max_files=256,
            max_connected_files=32,
            concrete_seed_count=0,
        )
        == 256
    )
    assert (
        _connected_map_candidate_file_limit(
            max_files=6_000,
            max_connected_files=256,
            concrete_seed_count=4,
        )
        == 384
    )
    assert (
        _connected_map_candidate_file_limit(
            max_files=6_000,
            max_connected_files=256,
            concrete_seed_count=12,
        )
        == 256
    )


