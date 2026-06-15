from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from apps.api_server.services import repository_intelligence_repository_source as rs
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)


def test_git_repository_relative_files_uses_combined_git_listing_without_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    command_calls: list[tuple[str, ...]] = []

    def _unexpected_is_git_repository(_root_path: Path) -> bool:
        raise AssertionError("_git_repository_relative_files should not preflight _is_git_repository")

    def _fake_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        assert cwd == tmp_path
        assert timeout == 120.0
        assert binary is False
        assert stdin is None
        command_calls.append(tuple(str(arg) for arg in args))
        return "src/main.py\nsrc/lib.py\nscratch.txt\n"

    monkeypatch.setattr(rs, "_is_git_repository", _unexpected_is_git_repository)
    monkeypatch.setattr(rs, "_git_command", _fake_git_command)

    assert rs._git_repository_relative_files(tmp_path) == [
        "scratch.txt",
        "src/lib.py",
        "src/main.py",
    ]
    assert command_calls == [
        ("git", "ls-files", "--cached", "--others", "--exclude-standard"),
    ]


def test_git_repository_relative_files_returns_none_when_git_listing_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def _unexpected_is_git_repository(_root_path: Path) -> bool:
        raise AssertionError("_git_repository_relative_files should not preflight _is_git_repository")

    def _failing_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        raise RepositoryIntelligenceError(
            code="git_command_failed",
            message="not a git repository",
            status_code=502,
            details={"command": list(args)},
        )

    monkeypatch.setattr(rs, "_is_git_repository", _unexpected_is_git_repository)
    monkeypatch.setattr(rs, "_git_command", _failing_git_command)

    assert rs._git_repository_relative_files(tmp_path) is None


def test_git_repository_relative_files_limits_git_listing_to_candidate_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    command_calls: list[tuple[str, ...]] = []

    def _fake_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        assert cwd == tmp_path
        assert timeout == 120.0
        assert binary is False
        assert stdin is None
        command_calls.append(tuple(str(arg) for arg in args))
        return "source/index.haml\nsource/layouts/default.haml\n"

    monkeypatch.setattr(rs, "_git_command", _fake_git_command)

    assert rs._git_repository_relative_files(
        tmp_path,
        candidate_paths=["source/layouts", "source"],
    ) == [
        "source/index.haml",
        "source/layouts/default.haml",
    ]
    assert command_calls == [
        (
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "source",
            "source/layouts",
        ),
    ]


def test_git_repository_relative_files_uses_tracked_only_listing_for_clean_clone(
    tmp_path: Path,
    monkeypatch,
) -> None:
    command_calls: list[tuple[str, ...]] = []

    def _fake_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        assert cwd == tmp_path
        assert timeout == 120.0
        assert binary is False
        assert stdin is None
        command_calls.append(tuple(str(arg) for arg in args))
        return "src/main.typ\nsrc/theme.typ\n"

    monkeypatch.setattr(rs, "_git_command", _fake_git_command)

    assert rs._git_repository_relative_files(
        tmp_path,
        assume_clean_git_clone=True,
    ) == [
        "src/main.typ",
        "src/theme.typ",
    ]
    assert command_calls == [
        ("git", "ls-files", "--cached"),
    ]


def test_git_tracked_content_hashes_limits_git_listing_to_candidate_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    command_calls: list[tuple[str, ...]] = []
    changed_path_calls: list[tuple[str, ...] | None] = []

    def _fake_git_changed_paths(
        _root_path: Path, *, candidate_paths=None
    ) -> list[str]:
        changed_path_calls.append(
            tuple(candidate_paths) if candidate_paths is not None else None
        )
        return []

    def _fake_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        assert cwd == tmp_path
        assert timeout in {60.0, 120.0}
        assert binary is False
        assert stdin is None
        command_calls.append(tuple(str(arg) for arg in args))
        if tuple(args[:3]) == ("git", "ls-files", "-s"):
            return (
                "100644 abcdef1234567890 0\tsrc/main.py\n"
                "100644 fedcba0987654321 0\tsrc/other.py\n"
            )
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(rs, "_git_changed_paths", _fake_git_changed_paths)
    monkeypatch.setattr(rs, "_git_command", _fake_git_command)

    assert rs._git_tracked_content_hashes(
        tmp_path,
        candidate_paths=["src/main.py"],
    ) == {"src/main.py": "abcdef1234567890"}
    assert changed_path_calls == [("src/main.py",)]
    assert command_calls == [
        ("git", "ls-files", "-s", "--", "src/main.py"),
    ]


def test_git_tracked_content_hashes_returns_empty_for_empty_candidate_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def _unexpected_git_changed_paths(_root_path: Path) -> list[str]:
        raise AssertionError("empty candidate paths should bypass git change discovery")

    def _unexpected_git_command(*args, **kwargs):
        raise AssertionError("empty candidate paths should bypass git ls-files")

    monkeypatch.setattr(rs, "_git_changed_paths", _unexpected_git_changed_paths)
    monkeypatch.setattr(rs, "_git_command", _unexpected_git_command)

    assert rs._git_tracked_content_hashes(tmp_path, candidate_paths=[]) == {}


def test_git_tracked_content_hashes_skips_git_listing_for_clean_git_clone_hint_with_candidate_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def _unexpected_git_changed_paths(_root_path: Path, *, candidate_paths=None) -> list[str]:
        raise AssertionError("clean git clone hint should bypass git status")

    def _unexpected_git_command(*args, **kwargs):
        raise AssertionError("clean git clone hint with candidate paths should bypass git ls-files")

    monkeypatch.setattr(rs, "_git_changed_paths", _unexpected_git_changed_paths)
    monkeypatch.setattr(rs, "_git_command", _unexpected_git_command)

    assert rs._git_tracked_content_hashes(
        tmp_path,
        candidate_paths=["src/main.py"],
        assume_clean_git_clone=True,
    ) == {}


def test_resolved_repository_source_skips_git_status_for_clean_local_clone_hint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    connector = SimpleNamespace(
        id="connector-id",
        org_id="org-id",
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps(
            {
                "path": str(tmp_path),
                "assume_clean_git_clone": True,
            }
        ),
    )
    command_calls: list[tuple[str, ...]] = []

    def _unexpected_is_git_repository(_root_path: Path) -> bool:
        raise AssertionError("clean local clone hint should bypass git preflight")

    def _fake_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        assert cwd == tmp_path
        assert binary is False
        assert stdin is None
        command_calls.append(tuple(str(arg) for arg in args))
        if tuple(args) == ("git", "rev-parse", "HEAD"):
            return "deadbeef"
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(rs, "_is_git_repository", _unexpected_is_git_repository)
    monkeypatch.setattr(rs, "_git_command", _fake_git_command)

    with rs.resolved_repository_source(
        connector=connector,
        config=rs._parse_connector_config(connector),
        ref=None,
    ) as source:
        assert source.root_path == tmp_path
        assert source.resolved_revision == "deadbeef"
        assert source.is_git is True
        assert source.assume_clean_git_clone is True

    assert command_calls == [
        ("git", "rev-parse", "HEAD"),
    ]


def test_resolved_repository_source_uses_configured_clean_clone_resolved_revision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    connector = SimpleNamespace(
        id="connector-id",
        org_id="org-id",
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps(
            {
                "path": str(tmp_path),
                "assume_clean_git_clone": True,
                "resolved_revision": "a" * 40,
            }
        ),
    )

    def _unexpected_is_git_repository(_root_path: Path) -> bool:
        raise AssertionError("configured clean-clone revision should bypass git preflight")

    def _unexpected_git_command(*args, **kwargs):
        raise AssertionError("configured clean-clone revision should bypass git commands")

    monkeypatch.setattr(rs, "_is_git_repository", _unexpected_is_git_repository)
    monkeypatch.setattr(rs, "_git_command", _unexpected_git_command)

    with rs.resolved_repository_source(
        connector=connector,
        config=rs._parse_connector_config(connector),
        ref=None,
    ) as source:
        assert source.root_path == tmp_path
        assert source.resolved_revision == "a" * 40
        assert source.is_git is True
        assert source.assume_clean_git_clone is True


def test_resolved_repository_source_rejects_invalid_clean_clone_resolved_revision(
    tmp_path: Path,
) -> None:
    connector = SimpleNamespace(
        id="connector-id",
        org_id="org-id",
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps(
            {
                "path": str(tmp_path),
                "assume_clean_git_clone": True,
                "resolved_revision": "deadbeef",
            }
        ),
    )

    try:
        with rs.resolved_repository_source(
            connector=connector,
            config=rs._parse_connector_config(connector),
            ref=None,
        ):
            raise AssertionError("expected invalid_repository_config")
    except RepositoryIntelligenceError as exc:
        assert exc.code == "invalid_repository_config"


def test_git_changed_paths_uses_single_status_command_and_prefers_renamed_destination(
    tmp_path: Path,
    monkeypatch,
) -> None:
    command_calls: list[tuple[str, ...]] = []

    def _fake_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        assert cwd == tmp_path
        assert timeout == 60.0
        assert binary is True
        assert stdin is None
        command_calls.append(tuple(str(arg) for arg in args))
        return (
            b"M  src/main.py\0"
            b"?? scratch.txt\0"
            b"R  renamed/new_name.py\0renamed/old_name.py\0"
        )

    monkeypatch.setattr(rs, "_git_command", _fake_git_command)

    assert rs._git_changed_paths(tmp_path) == [
        "renamed/new_name.py",
        "scratch.txt",
        "src/main.py",
    ]
    assert command_calls == [
        ("git", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
    ]


def test_git_changed_paths_limits_status_to_candidate_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    command_calls: list[tuple[str, ...]] = []

    def _fake_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        assert cwd == tmp_path
        assert timeout == 60.0
        assert binary is True
        assert stdin is None
        command_calls.append(tuple(str(arg) for arg in args))
        return b"M  src/main.py\0"

    monkeypatch.setattr(rs, "_git_command", _fake_git_command)

    assert rs._git_changed_paths(
        tmp_path,
        candidate_paths=["src/main.py", "src/main.py", " "],
    ) == ["src/main.py"]
    assert command_calls == [
        (
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            "src/main.py",
        ),
    ]


def test_git_changed_paths_reuses_cached_full_repo_status_within_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    command_calls: list[tuple[str, ...]] = []

    def _fake_git_command(args, *, cwd=None, timeout=30.0, binary=False, stdin=None):
        assert cwd == tmp_path
        assert timeout == 60.0
        assert binary is True
        assert stdin is None
        command_calls.append(tuple(str(arg) for arg in args))
        if "--" in args:
            return b"M  src/main.py\0"
        return b"M  src/main.py\0?? scratch.txt\0"

    monkeypatch.setattr(rs, "_git_command", _fake_git_command)
    rs.clear_git_command_cache()

    rs.begin_git_command_cache_scope()
    try:
        assert rs._git_changed_paths(tmp_path) == [
            "scratch.txt",
            "src/main.py",
        ]
        assert rs._git_changed_paths(
            tmp_path,
            candidate_paths=["src/main.py"],
        ) == ["src/main.py"]
        assert command_calls == [
            ("git", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
        ]
    finally:
        rs.end_git_command_cache_scope()

    assert rs._git_changed_paths(
        tmp_path,
        candidate_paths=["src/main.py"],
    ) == ["src/main.py"]
    assert command_calls == [
        ("git", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
        (
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            "src/main.py",
        ),
    ]


def test_git_status_entries_accept_text_output_and_skip_rename_source_path() -> None:
    assert rs._git_status_entries(
        "M  src/main.py\0?? scratch.txt\0R  renamed/new_name.py\0renamed/old_name.py\0"
    ) == [
        ("M ", "src/main.py"),
        ("??", "scratch.txt"),
        ("R ", "renamed/new_name.py"),
    ]


def test_git_command_cache_scope_reuses_read_only_results_and_clears_after_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_calls: list[tuple[str, ...]] = []

    class _CompletedProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = b"true\n"
            self.stderr = b""

    def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        run_calls.append(tuple(str(arg) for arg in args))
        return _CompletedProcess()

    monkeypatch.setattr(rs.subprocess, "run", _fake_run)
    rs.clear_git_command_cache()

    rs.begin_git_command_cache_scope()
    try:
        assert rs._git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=tmp_path) == "true"
        assert rs._git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=tmp_path) == "true"
        assert run_calls == [
            ("git", "rev-parse", "--is-inside-work-tree"),
        ]
        assert rs.git_command_cache_size() == 1
    finally:
        rs.end_git_command_cache_scope()

    assert rs.git_command_cache_size() == 0
    assert rs._git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=tmp_path) == "true"
    assert run_calls == [
        ("git", "rev-parse", "--is-inside-work-tree"),
        ("git", "rev-parse", "--is-inside-work-tree"),
    ]


def test_git_command_cache_scope_reuses_results_between_relative_and_absolute_cwd(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_calls: list[tuple[str, ...]] = []

    class _CompletedProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = b"true\n"
            self.stderr = b""

    def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        run_calls.append(tuple(str(arg) for arg in args))
        return _CompletedProcess()

    monkeypatch.setattr(rs.subprocess, "run", _fake_run)
    monkeypatch.chdir(tmp_path.parent)
    relative_cwd = Path(tmp_path.name)
    absolute_cwd = tmp_path.resolve()
    rs.clear_git_command_cache()

    rs.begin_git_command_cache_scope()
    try:
        assert rs._git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=relative_cwd) == "true"
        assert rs._git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=absolute_cwd) == "true"
        assert run_calls == [
            ("git", "rev-parse", "--is-inside-work-tree"),
        ]
    finally:
        rs.end_git_command_cache_scope()


def test_git_command_cache_scope_reuses_results_between_relative_and_absolute_dash_c(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_calls: list[tuple[str, ...]] = []

    class _CompletedProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = b"tracked.txt\n"
            self.stderr = b""

    def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        run_calls.append(tuple(str(arg) for arg in args))
        return _CompletedProcess()

    monkeypatch.setattr(rs.subprocess, "run", _fake_run)
    monkeypatch.chdir(tmp_path.parent)
    relative_repo_path = Path(tmp_path.name)
    absolute_repo_path = tmp_path.resolve()
    rs.clear_git_command_cache()

    rs.begin_git_command_cache_scope()
    try:
        assert rs._git_command(
            ["git", "-C", str(relative_repo_path), "ls-files", "--cached", "--others", "--exclude-standard"]
        ) == "tracked.txt"
        assert rs._git_command(
            ["git", "-C", str(absolute_repo_path), "ls-files", "--cached", "--others", "--exclude-standard"]
        ) == "tracked.txt"
        assert run_calls == [
            ("git", "-C", str(relative_repo_path), "ls-files", "--cached", "--others", "--exclude-standard"),
        ]
    finally:
        rs.end_git_command_cache_scope()


def test_git_command_cache_scope_reuses_results_between_dash_c_and_cwd(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_calls: list[tuple[str, ...]] = []

    class _CompletedProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = b"deadbeef\n"
            self.stderr = b""

    def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        run_calls.append(tuple(str(arg) for arg in args))
        return _CompletedProcess()

    monkeypatch.setattr(rs.subprocess, "run", _fake_run)
    monkeypatch.chdir(tmp_path.parent)
    relative_repo_path = Path(tmp_path.name)
    absolute_repo_path = tmp_path.resolve()
    rs.clear_git_command_cache()

    rs.begin_git_command_cache_scope()
    try:
        assert rs._git_command(
            ["git", "-C", str(relative_repo_path), "rev-parse", "HEAD"]
        ) == "deadbeef"
        assert rs._git_command(
            ["git", "rev-parse", "HEAD"],
            cwd=absolute_repo_path,
        ) == "deadbeef"
        assert run_calls == [
            ("git", "-C", str(relative_repo_path), "rev-parse", "HEAD"),
        ]
    finally:
        rs.end_git_command_cache_scope()
