"""Tests for repository_intelligence_service: iter.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_iter_repository_files_uses_git_listing_without_tree_walk(tmp_path: Path) -> None:
    repo_path = tmp_path / "git-listing-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def run() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    original_os_walk = repository_service.os.walk

    def _unexpected_os_walk(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("git-backed repository discovery should avoid os.walk")

    repository_service.os.walk = _unexpected_os_walk
    try:
        files = repository_service._iter_repository_files(
            repo_path,
            focus_paths=[],
            include_patterns=["src/*.py", "src/**/*.py"],
            exclude_patterns=[],
            max_files=128,
            max_total_bytes=None,
        )
    finally:
        repository_service.os.walk = original_os_walk

    assert [str(path.relative_to(repo_path)) for path in files] == ["src/service.py"]


