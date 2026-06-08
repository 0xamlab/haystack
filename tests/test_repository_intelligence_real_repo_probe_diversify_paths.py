"""Tests for repository_intelligence_real_repo_probe: diversify_paths.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_diversify_paths_by_support_root_preserves_ranked_root_order() -> None:
    assert probe_module._diversify_paths_by_support_root(
        paths=[
            "web/src/main.ts",
            "rust/src/main.rs",
            "py/src/acme/cli.py",
        ],
        support_roots={"web/src", "rust/src", "py/src"},
    ) == [
        "web/src/main.ts",
        "rust/src/main.rs",
        "py/src/acme/cli.py",
    ]


