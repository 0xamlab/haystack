from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    apacheconf as apacheconf_adapter,
    aspectj as aspectj_adapter,
    brightscript as brightscript_adapter,
    codeql as codeql_adapter,
    earthly as earthly_adapter,
    mako as mako_adapter,
    maven as maven_adapter,
    nginx as nginx_adapter,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _candidate_repository_roots,
    _language_for_path,
    _matches_repository_pattern,
    _matches_repository_scope,
    _normalize_repository_relative_path,
)
from apps.api_server.services.repository_intelligence_inventory import (
    _DEFAULT_EXCLUDED_PATH_PARTS,
)
from apps.api_server.services.repository_intelligence_repository_source import (
    _git_repository_relative_files,
)

from apps.api_server.services.repository_intelligence_text_file_registry import (
    TEXT_FILE_BASENAMES,
    TEXT_FILE_SUFFIXES,
)

_ALLOW_ALL_REPOSITORY_PATTERNS = frozenset({"*", "**", "**/*"})


def _path_is_indexable_repository_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_FILE_SUFFIXES:
        return True
    if path.name in TEXT_FILE_BASENAMES:
        return True
    if nginx_adapter.has_nginx_path_hints(path):
        return True
    if apacheconf_adapter.has_apacheconf_path_hints(path):
        return True
    if mako_adapter.has_mako_path_hints(path):
        return True
    if maven_adapter.has_maven_path_hints(path):
        return True
    if brightscript_adapter.has_brightscript_path_hints(path):
        return True
    if codeql_adapter.has_codeql_path_hints(path):
        return True
    if earthly_adapter.has_earthly_path_hints(path):
        return True
    if aspectj_adapter.has_aspectj_path_hints(path=path):
        return True
    if path.suffix.lower() == ".xml":
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return _language_for_path(path, text=text) in {"maven", "xpp"}
    if path.suffix:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return _language_for_path(path, text=text) in {"awk", "brightscript", "earthly"}


def _detected_repository_file_language(path: Path, *, repo_root: Path | None = None) -> str:
    if path.suffix.lower() not in {
        ".bas",
        ".cls",
        ".ctl",
        ".dfm",
        ".dpk",
        ".dpr",
        ".dproj",
        ".fmx",
        ".frm",
        ".h",
        ".hoon",
        ".inc",
        ".metal",
        ".metalh",
        ".bqn",
        ".q",
        ".r",
        ".r3",
        ".reb",
        ".rebol",
        ".ijs",
        ".ijt",
        ".m",
        ".mm",
        ".l",
        ".lex",
        ".mll",
        ".pas",
        ".pch",
        ".pl",
        ".sql",
        ".dbproj",
        ".sqlproj",
        ".prg",
        ".v",
        ".vhd",
        ".vhdl",
        ".vh",
        ".vbp",
        ".xq",
        ".xquery",
        ".xqy",
        ".xql",
        ".xqm",
        ".xsl",
        ".xslt",
        ".xml",
        ".y",
        ".yacc",
        ".mly",
        ".moon",
        ".templ",
        ".thrift",
        ".vcl",
        ".just",
        "",
    }:
        return _language_for_path(path, repo_root=repo_root)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = None
    return _language_for_path(path, text=text, repo_root=repo_root)


def _append_repository_file(
    *,
    root_path: Path,
    path: Path,
    files: list[Path],
    seen_paths: set[str],
    normalized_include_patterns: list[str] | tuple[str, ...],
    include_patterns_allow_all: bool,
    normalized_exclude_patterns: list[str] | tuple[str, ...],
    max_files: int,
    max_total_bytes: int | None,
    total_bytes: int,
) -> dict[str, int | bool]:
    if not path.is_file() or path.is_symlink():
        return {"total_bytes": total_bytes, "stop": False}
    if not _path_is_indexable_repository_file(path):
        return {"total_bytes": total_bytes, "stop": False}
    relative_path = _normalize_repository_relative_path(str(path.relative_to(root_path)))
    if not relative_path or relative_path in seen_paths:
        return {"total_bytes": total_bytes, "stop": False}
    parts = set(PurePosixPath(relative_path).parts)
    if parts & _DEFAULT_EXCLUDED_PATH_PARTS:
        return {"total_bytes": total_bytes, "stop": False}
    if not include_patterns_allow_all and normalized_include_patterns and not any(
        _matches_repository_pattern(relative_path, pattern)
        for pattern in normalized_include_patterns
    ):
        return {"total_bytes": total_bytes, "stop": False}
    if any(
        _matches_repository_pattern(relative_path, pattern)
        for pattern in normalized_exclude_patterns
    ):
        return {"total_bytes": total_bytes, "stop": False}
    try:
        file_size = path.stat().st_size
    except OSError:
        return {"total_bytes": total_bytes, "stop": False}
    if max_total_bytes is not None and files and total_bytes + file_size > max_total_bytes:
        return {"total_bytes": total_bytes, "stop": True}
    seen_paths.add(relative_path)
    files.append(path)
    total_bytes += file_size
    stop = len(files) >= max_files or (
        max_total_bytes is not None and total_bytes >= max_total_bytes
    )
    return {"total_bytes": total_bytes, "stop": stop}


def _iter_repository_files_impl(
    root_path: Path,
    *,
    focus_paths: list[str] | tuple[str, ...],
    include_patterns: list[str] | tuple[str, ...],
    exclude_patterns: list[str] | tuple[str, ...],
    max_files: int,
    max_total_bytes: int | None,
    assume_clean_git_clone: bool = False,
) -> list[Path]:
    include_patterns_allow_all = bool(
        set(include_patterns) & _ALLOW_ALL_REPOSITORY_PATTERNS
    )
    concrete_focus_files: list[Path] = []
    if focus_paths:
        all_focus_paths_are_concrete_files = True
        for focus_path in focus_paths:
            candidate = (root_path / focus_path).resolve()
            if not (
                candidate.exists()
                and candidate.is_file()
                and (candidate == root_path or root_path in candidate.parents)
            ):
                all_focus_paths_are_concrete_files = False
                break
            concrete_focus_files.append(candidate)
        if all_focus_paths_are_concrete_files:
            files: list[Path] = []
            seen_paths: set[str] = set()
            total_bytes = 0
            for candidate in concrete_focus_files:
                result = _append_repository_file(
                    root_path=root_path,
                    path=candidate,
                    files=files,
                    seen_paths=seen_paths,
                    normalized_include_patterns=include_patterns,
                    include_patterns_allow_all=include_patterns_allow_all,
                    normalized_exclude_patterns=exclude_patterns,
                    max_files=max_files,
                    max_total_bytes=max_total_bytes,
                    total_bytes=total_bytes,
                )
                total_bytes = int(result["total_bytes"])
                if bool(result["stop"]):
                    break
            return files
    git_relative_files = _git_repository_relative_files(
        root_path,
        candidate_paths=focus_paths or None,
        assume_clean_git_clone=assume_clean_git_clone,
    )
    if git_relative_files is not None:
        files: list[Path] = []
        seen_paths: set[str] = set()
        total_bytes = 0
        for relative_path in git_relative_files:
            if focus_paths and not any(
                _matches_repository_scope(relative_path, focus_path) for focus_path in focus_paths
            ):
                continue
            result = _append_repository_file(
                root_path=root_path,
                path=root_path / relative_path,
                files=files,
                seen_paths=seen_paths,
                normalized_include_patterns=include_patterns,
                include_patterns_allow_all=include_patterns_allow_all,
                normalized_exclude_patterns=exclude_patterns,
                max_files=max_files,
                max_total_bytes=max_total_bytes,
                total_bytes=total_bytes,
            )
            total_bytes = int(result["total_bytes"])
            if bool(result["stop"]):
                break
        return files

    candidate_roots = _candidate_repository_roots(
        root_path=root_path,
        focus_paths=focus_paths,
    )
    files: list[Path] = []
    seen_paths: set[str] = set()
    total_bytes = 0
    for candidate_root in candidate_roots:
        if candidate_root.is_file():
            result = _append_repository_file(
                root_path=root_path,
                path=candidate_root,
                files=files,
                seen_paths=seen_paths,
                normalized_include_patterns=include_patterns,
                include_patterns_allow_all=include_patterns_allow_all,
                normalized_exclude_patterns=exclude_patterns,
                max_files=max_files,
                max_total_bytes=max_total_bytes,
                total_bytes=total_bytes,
            )
            total_bytes = int(result["total_bytes"])
            if bool(result["stop"]):
                break
            continue
        for current_root, dirnames, filenames in os.walk(candidate_root):
            dirnames[:] = [
                name for name in sorted(dirnames) if name not in _DEFAULT_EXCLUDED_PATH_PARTS
            ]
            for filename in sorted(filenames):
                result = _append_repository_file(
                    root_path=root_path,
                    path=Path(current_root) / filename,
                    files=files,
                    seen_paths=seen_paths,
                    normalized_include_patterns=include_patterns,
                    include_patterns_allow_all=include_patterns_allow_all,
                    normalized_exclude_patterns=exclude_patterns,
                    max_files=max_files,
                    max_total_bytes=max_total_bytes,
                    total_bytes=total_bytes,
                )
                total_bytes = int(result["total_bytes"])
                if bool(result["stop"]):
                    return files
    return files


def _compact_repository_focus_paths(
    root_path: Path,
    *,
    focus_paths: list[str] | tuple[str, ...],
    include_patterns: list[str] | tuple[str, ...],
    exclude_patterns: list[str] | tuple[str, ...],
    max_files: int,
    max_total_bytes: int | None,
    prefer_concrete_focus_paths: bool = False,
    assume_clean_git_clone: bool = False,
) -> tuple[str, ...]:
    normalized_focus_paths = tuple(
        dict.fromkeys(value for value in focus_paths if str(value).strip())
    )
    if len(normalized_focus_paths) <= 1:
        return normalized_focus_paths

    existing_candidates: dict[str, Path] = {}
    for focus_path in normalized_focus_paths:
        candidate = (root_path / focus_path).resolve()
        if candidate.exists() and (candidate == root_path or root_path in candidate.parents):
            existing_candidates[focus_path] = candidate

    if not existing_candidates:
        return normalized_focus_paths

    redundant_directories: set[str] = set()
    for focus_path in normalized_focus_paths:
        candidate = existing_candidates.get(focus_path)
        if candidate is None or not candidate.is_dir():
            continue
        descendant_focus_paths = [
            other_focus_path
            for other_focus_path in normalized_focus_paths
            if other_focus_path != focus_path
            and _matches_repository_scope(other_focus_path, focus_path)
        ]
        if not descendant_focus_paths:
            continue
        if prefer_concrete_focus_paths and any(
            (
                descendant_candidate := existing_candidates.get(descendant_focus_path)
            ) is not None
            and descendant_candidate.is_file()
            for descendant_focus_path in descendant_focus_paths
        ):
            redundant_directories.add(focus_path)
            continue
        matched_files = _iter_repository_files_impl(
            root_path,
            focus_paths=(focus_path,),
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            max_files=max_files,
            max_total_bytes=max_total_bytes,
            assume_clean_git_clone=assume_clean_git_clone,
        )
        if not matched_files:
            continue
        other_scopes = tuple(
            other_focus_path
            for other_focus_path in normalized_focus_paths
            if other_focus_path != focus_path
        )
        if all(
            any(
                _matches_repository_scope(
                    str(path.relative_to(root_path)).replace("\\", "/"),
                    other_scope,
                )
                for other_scope in other_scopes
            )
            for path in matched_files
        ):
            redundant_directories.add(focus_path)

    return tuple(
        focus_path
        for focus_path in normalized_focus_paths
        if focus_path not in redundant_directories
    )


def _iter_repository_files(
    root_path: Path,
    *,
    focus_paths: list[str] | tuple[str, ...],
    include_patterns: list[str] | tuple[str, ...],
    exclude_patterns: list[str] | tuple[str, ...],
    max_files: int,
    max_total_bytes: int | None,
    assume_clean_git_clone: bool = False,
) -> list[Path]:
    normalized_focus_paths = tuple(
        _normalize_repository_relative_path(value) for value in focus_paths if str(value).strip()
    )
    normalized_include_patterns = tuple(
        _normalize_repository_relative_path(value)
        for value in include_patterns
        if str(value).strip()
    )
    normalized_exclude_patterns = tuple(
        _normalize_repository_relative_path(value)
        for value in exclude_patterns
        if str(value).strip()
    )
    compacted_focus_paths = _compact_repository_focus_paths(
        root_path,
        focus_paths=normalized_focus_paths,
        include_patterns=normalized_include_patterns,
        exclude_patterns=normalized_exclude_patterns,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
        assume_clean_git_clone=assume_clean_git_clone,
    )
    return _iter_repository_files_impl(
        root_path,
        focus_paths=compacted_focus_paths,
        include_patterns=normalized_include_patterns,
        exclude_patterns=normalized_exclude_patterns,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
        assume_clean_git_clone=assume_clean_git_clone,
    )
