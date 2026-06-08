"""Tests for repository_intelligence_real_repo_probe: effective_focus.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_effective_focus_paths_for_snapshot_prefers_connected_files_over_broad_dirs() -> None:
    diagnostics = [
        RepositoryDiagnostic(
            path="services/execution-service/src/index.ts",
            line=12,
            severity="error",
            code="TS6059",
            message="File is not under rootDir.",
        )
    ]

    effective_focus_paths = _effective_focus_paths_for_snapshot(
        diagnostics=diagnostics,
        connected_files=[
            "services/execution-service/src/index.ts",
            "packages/common/src/execution.ts",
        ],
        fallback_focus_paths=[
            "services/execution-service",
            "services/execution-service/src/index.ts",
            "services/execution-service/src",
        ],
        config_focus_paths=[
            "services/execution-service/tsconfig.test.json",
            "package.json",
        ],
    )

    assert effective_focus_paths == [
        "services/execution-service/src/index.ts",
        "packages/common/src/execution.ts",
        "services/execution-service/tsconfig.test.json",
        "package.json",
    ]


def test_effective_focus_paths_for_snapshot_without_diagnostics_prefers_connected_files() -> None:
    effective_focus_paths = _effective_focus_paths_for_snapshot(
        diagnostics=[],
        connected_files=[
            "src/main.tsx",
            "src/App.tsx",
            "src/lib/utils.ts",
        ],
        fallback_focus_paths=["src"],
        config_focus_paths=["tsconfig.json", "package.json"],
    )

    assert effective_focus_paths == [
        "src/main.tsx",
        "src/App.tsx",
        "src/lib/utils.ts",
        "tsconfig.json",
        "package.json",
    ]


