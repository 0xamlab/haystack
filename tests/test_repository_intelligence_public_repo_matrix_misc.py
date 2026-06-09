"""Tests for test_repository_intelligence_public_repo_matrix: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-3/tests/test_repository_intelligence_public_repo_matrix.py during modularization.
"""
from __future__ import annotations

from tests._test_repository_intelligence_public_repo_matrix_helpers import *  # noqa: F401,F403


def test_ordered_public_repository_cases_respects_global_rank() -> None:
    cases = (
        public_repo_matrix.PublicRepositoryCase(
            language="zig",
            repository_url="https://github.com/zigtools/zls.git",
            expected_primary_ecosystem="zig",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="python",
            repository_url="https://github.com/pallets/click.git",
            expected_primary_ecosystem="python",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="dart",
            repository_url="https://github.com/dart-lang/http.git",
            expected_primary_ecosystem="dart",
        ),
    )

    ordered_cases = public_repo_matrix.ordered_public_repository_cases(cases=cases)

    assert [case.language for case in ordered_cases] == ["python", "dart", "zig"]


def test_run_public_repository_seed_plan_case_uses_operational_primary_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="dart",
        repository_url="https://github.com/dart-lang/http.git",
        expected_primary_ecosystem="dart",
    )
    repo_path = tmp_path / "dart-http"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix,
        "clone_public_repository_case",
        lambda *_args, **_kwargs: repo_path,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        lambda **_kwargs: {
            "candidate_file_paths": ["pkgs/http/lib/http.dart"],
            "entrypoint_files": ["pkgs/http/lib/http.dart"],
            "support_roots": ["pkgs/http/lib"],
            "config_paths": ["pkgs/http/pubspec.yaml"],
            "detected_ecosystems": ["java", "cpp", "dart", "groovy"],
            "operational_ecosystems": ["dart", "java", "cpp", "groovy"],
        },
    )

    result = public_repo_matrix.run_public_repository_seed_plan_case(
        case,
        checkout_root=tmp_path,
    )

    assert result["primary_detected_ecosystem"] == "java"
    assert result["primary_operational_ecosystem"] == "dart"
    assert result["primary_ecosystem"] == "dart"
    assert result["primary_match"] is True


def test_run_public_repository_matrix_reports_real_language_progress(tmp_path: Path) -> None:
    result = public_repo_matrix.run_public_repository_matrix(
        mode="seed_plan",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        limit=0,
        ranked_target_language_count=200,
    )

    assert result["case_count"] == 0
    assert result["support_progress"]["supported_real_language_count"] == 172
    assert result["support_progress"]["ranked_target_language_count"] == 200
    assert result["support_progress"]["progress_label"] == "172 / 200"
    assert result["support_progress"]["progress_fraction"] == pytest.approx(172 / 200)


