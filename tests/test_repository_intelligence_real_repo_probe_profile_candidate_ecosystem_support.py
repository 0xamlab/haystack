from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from benchmarks import repository_intelligence_real_repo_probe_profile_candidate_ecosystem_support as support


def _normalize_repository_relative_path(path: str) -> str:
    normalized = path.replace(os.sep, "/").strip("/")
    return "" if normalized in {"", "."} else normalized


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    return "/test/" in f"/{lowered}/" or lowered.startswith("test/")


def test_supplement_candidate_file_paths_for_suffix_roots_is_deterministic_and_skips_symlinks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "repo"
    templates_path = repo_path / "templates"
    partials_path = templates_path / "partials"
    tests_path = templates_path / "test"
    shared_path = repo_path / "shared"
    partials_path.mkdir(parents=True)
    tests_path.mkdir(parents=True)
    shared_path.mkdir(parents=True)
    (templates_path / "seed.mustache").write_text("{{seed}}", encoding="utf-8")
    (templates_path / "a.mustache").write_text("{{a}}", encoding="utf-8")
    (partials_path / "b.mustache").write_text("{{b}}", encoding="utf-8")
    (tests_path / "ignored.mustache").write_text("{{ignored}}", encoding="utf-8")
    (shared_path / "linked.mustache").write_text("{{linked}}", encoding="utf-8")
    (templates_path / "linked.mustache").symlink_to(shared_path / "linked.mustache")

    monkeypatch.setattr(
        support,
        "repository_service",
        SimpleNamespace(
            _normalize_repository_relative_path=_normalize_repository_relative_path,
            _is_test_path=_is_test_path,
        ),
    )
    monkeypatch.setattr(support, "_is_non_operational_profile_path", lambda path: False)

    result = support._supplement_candidate_file_paths_for_suffix_roots(
        repo_path=repo_path,
        candidate_file_paths=["templates/seed.mustache"],
        suffixes={".mustache"},
        root_names=("templates",),
        max_extra_files=10,
    )

    assert result == [
        "templates/seed.mustache",
        "templates/a.mustache",
        "templates/partials/b.mustache",
    ]


def test_supplement_candidate_file_paths_for_surface_dir_parts_uses_matching_dirs_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "pkg" / "templates").mkdir(parents=True)
    (repo_path / "pkg" / "partials").mkdir(parents=True)
    (repo_path / "pkg" / "tests").mkdir(parents=True)
    (repo_path / "docs" / "templates").mkdir(parents=True)
    (repo_path / "pkg" / "templates" / "page.mustache").write_text("{{page}}", encoding="utf-8")
    (repo_path / "pkg" / "partials" / "card.mustache").write_text("{{card}}", encoding="utf-8")
    (repo_path / "pkg" / "tests" / "ignored.mustache").write_text("{{ignored}}", encoding="utf-8")
    (repo_path / "docs" / "templates" / "doc.mustache").write_text("{{doc}}", encoding="utf-8")
    (repo_path / "pkg" / "templates" / "notes.txt").write_text("notes", encoding="utf-8")

    monkeypatch.setattr(
        support,
        "repository_service",
        SimpleNamespace(
            _normalize_repository_relative_path=_normalize_repository_relative_path,
            _is_test_path=_is_test_path,
        ),
    )
    monkeypatch.setattr(support, "_is_non_operational_profile_path", lambda path: False)

    result = support._supplement_candidate_file_paths_for_surface_dir_parts(
        repo_path=repo_path,
        candidate_file_paths=["pkg/templates/page.mustache"],
        suffixes={".mustache"},
        directory_parts={"partials"},
        max_extra_files=10,
    )

    assert result == [
        "pkg/templates/page.mustache",
        "pkg/partials/card.mustache",
    ]
