from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path

import pytest

from apps.api_server.services import (
    repository_intelligence_decision_plan_workflow as decision_plan_workflow,
)
from apps.api_server.services import (
    repository_intelligence_patch_analysis as patch_analysis,
)
from apps.api_server.services import (
    repository_intelligence_repository_source as repository_source,
)
from apps.api_server.services import (
    repository_intelligence_verified_agentic as verified_agentic,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)


def test_patch_changed_files_tracks_only_touched_body_lines() -> None:
    patch_diff = """--- a/src/serena/util/exception.py
+++ b/src/serena/util/exception.py
@@ -37,7 +37,7 @@
             # This is a simplified check - could be improved
             return True
 
-    return True
+    return False
 
 
 def show_fatal_exception_safe(e: Exception) -> None:
"""

    assert patch_analysis._patch_changed_files(patch_diff) == {
        "src/serena/util/exception.py": [(40, 40)]
    }


def test_patch_changed_files_handles_additions_deletions_and_multi_hunk_ranges() -> None:
    added = """--- /dev/null
+++ b/src/new_file.py
@@ -0,0 +1,2 @@
+def created():
+    return 1
"""
    deleted = """--- a/src/old_file.py
+++ /dev/null
@@ -3,2 +0,0 @@
-old_value = 1
-old_value = 2
"""
    multi_hunk = """--- a/src/service.py
+++ b/src/service.py
@@ -2,1 +2,1 @@
-old = 1
+new = 1
@@ -10,0 +11,2 @@
+extra = 1
+extra = 2
"""

    assert patch_analysis._patch_changed_files(added) == {"src/new_file.py": [(1, 2)]}
    assert patch_analysis._patch_changed_files(deleted) == {"src/old_file.py": [(3, 4)]}
    assert patch_analysis._patch_changed_files(multi_hunk) == {"src/service.py": [(2, 2), (11, 12)]}


def test_patch_impact_summary_only_counts_the_changed_symbol_and_calibrates_risk() -> None:
    patch_diff = """--- a/src/serena/util/exception.py
+++ b/src/serena/util/exception.py
@@ -37,7 +37,7 @@
             # This is a simplified check - could be improved
             return True
 
-    return True
+    return False
 
 
 def show_fatal_exception_safe(e: Exception) -> None:
"""
    snapshot_manifest = {
        "snapshot_id": "snap-1",
        "files": [
            {
                "file_path": "src/serena/util/exception.py",
                "symbols": [
                    {
                        "symbol_name": "is_headless_environment",
                        "symbol_kind": "function",
                        "start_line": 37,
                        "end_line": 40,
                    },
                    {
                        "symbol_name": "show_fatal_exception_safe",
                        "symbol_kind": "function",
                        "start_line": 44,
                        "end_line": 45,
                    },
                ],
                "dependencies": [],
            }
        ],
    }

    impact = decision_plan_workflow._patch_impact_summary(
        snapshot_manifest,
        patch_diff,
        patch_changed_files=patch_analysis._patch_changed_files,
        top_level_service=patch_analysis._top_level_service,
        is_test_path=patch_analysis._is_test_path,
    )

    assert impact["impacted_symbols"] == ["is_headless_environment"]
    assert impact["rollback_complexity"] == "low"
    assert impact["api_break_candidates"] == 1
    assert impact["raw_risk_score"] == pytest.approx(0.21)

    calibrated = decision_plan_workflow._calibrate_patch_impact_risk(
        impact,
        triage_manifest={
            "signals": {
                "diagnostics": [
                    {
                        "path": "src/serena/util/exception.py",
                        "line": 40,
                        "severity": "error",
                        "message": "One-line behavior regression.",
                    }
                ]
            }
        },
        is_test_path=patch_analysis._is_test_path,
    )

    assert calibrated["raw_risk_score"] == pytest.approx(0.21)
    assert calibrated["risk_score"] == pytest.approx(0.13)
    assert calibrated["risk_adjustments"] == [
        {
            "kind": "verified_surgical_patch",
            "delta": pytest.approx(-0.08),
            "reason": (
                "Single-file, single-symbol source fix matches the diagnostic target with "
                "no dependency fanout or additional failing tests."
            ),
            "matched_file": "src/serena/util/exception.py",
        }
    ]


def test_validate_patch_against_snapshot_surfaces_baseline_identity(tmp_path: Path) -> None:
    patch_diff = """--- a/src/service.py
+++ b/src/service.py
@@ -1,1 +1,1 @@
-return 2
+return 1
"""

    @contextmanager
    def _materialized(_manifest: dict[str, object]):
        yield tmp_path

    def _git_command(args, *, timeout):  # type: ignore[no-untyped-def]
        if "apply" in args:
            raise RepositoryIntelligenceError(
                code="git_command_failed",
                message="error: patch does not apply",
                status_code=502,
                details={"command": list(args)},
            )
        return ""

    with pytest.raises(RepositoryIntelligenceError) as excinfo:
        patch_analysis._validate_patch_against_snapshot(
            snapshot_manifest={
                "snapshot_id": "snap-1",
                "resolved_revision": "deadbeef",
                "source_archive_path": "/tmp/snapshot-source.tar",
            },
            patch_diff=patch_diff,
            materialized_snapshot=_materialized,
            git_command=_git_command,
        )

    assert excinfo.value.code == "repository_patch_validation_failed"
    assert excinfo.value.status_code == 422
    assert excinfo.value.details["snapshot_id"] == "snap-1"
    assert excinfo.value.details["resolved_revision"] == "deadbeef"
    assert excinfo.value.details["patch_files"] == ["src/service.py"]
    assert excinfo.value.details["validation_command"][-2] == "--check"


def test_verified_agentic_diff_preserves_crlf_for_patch_validation(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline"
    work_root = tmp_path / "work"
    target_relative = Path("src/main/java/com/tencent/angel/AngelDeployMode.java")
    baseline_file = baseline_root / target_relative
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    original = (
        "__codna_benchmark__ = (\r\n"
        "/*\r\n"
        " * Tencent is pleased to support the open source community.\r\n"
        " */\r\n"
    )
    fixed = (
        "/*\r\n"
        " * Tencent is pleased to support the open source community.\r\n"
        " */\r\n"
    )
    baseline_file.write_bytes(original.encode("utf-8"))
    shutil.copytree(baseline_root, work_root)

    before = verified_agentic._capture_repository_tree_state(work_root)
    (work_root / target_relative).write_bytes(fixed.encode("utf-8"))
    after = verified_agentic._capture_repository_tree_state(work_root)
    patch_diff = verified_agentic._unified_diff_from_tree_states(before, after)

    @contextmanager
    def _materialized(_manifest: dict[str, object]):
        yield baseline_root

    patch_analysis._validate_patch_against_snapshot(
        snapshot_manifest={
            "snapshot_id": "snap-crlf",
            "resolved_revision": "ca2525e",
            "source_archive_path": "/tmp/source.tar",
        },
        patch_diff=patch_diff,
        materialized_snapshot=_materialized,
        git_command=repository_source._git_command,
    )

    assert "-__codna_benchmark__ = (" in patch_diff
