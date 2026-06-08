from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".mk"})
_MAKEFILE_BASENAMES = frozenset({"makefile", "gnumakefile"})
_SUPPORT_DIRECTORIES = frozenset({"build", "config", "make", "mk", "rules", "scripts", "tools"})
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:-?include|sinclude)\s+\S+|^[^\t\n#:=][^:=\n#]*:(?![=])|^[A-Za-z0-9_.-]+\s*(?::=|\?=|\+=|!=|=)"
)
_INCLUDE_RE = re.compile(r"(?im)^\s*(?:-?include|sinclude)\s+(?P<targets>[^#\n]+)")
_RULE_RE = re.compile(r"(?m)^(?P<targets>[^\t\n#:=][^:=\n#]*?)\s*:(?![=])(?P<deps>[^\n]*)$")
_MAKE_INVOKE_RE = re.compile(
    r"(?im)(?:\$\((?:MAKE|make)\)|\bmake\b)\s+(?P<target>[A-Za-z0-9_./+-]+)"
)
_SPECIAL_TARGETS = frozenset(
    {
        ".DEFAULT",
        ".DEFAULT_GOAL",
        ".DELETE_ON_ERROR",
        ".EXPORT_ALL_VARIABLES",
        ".IGNORE",
        ".INTERMEDIATE",
        ".LOW_RESOLUTION_TIME",
        ".NOTPARALLEL",
        ".ONESHELL",
        ".PHONY",
        ".POSIX",
        ".PRECIOUS",
        ".SECONDARY",
        ".SECONDEXPANSION",
        ".SILENT",
        ".SUFFIXES",
    }
)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.lstrip().startswith("#"):
            lines.append("")
            continue
        lines.append(raw_line)
    return "\n".join(lines)


def has_makefile_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in _KNOWN_SUFFIXES
        or normalized_path.name.lower() in _MAKEFILE_BASENAMES
    )


def is_probable_makefile_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_makefile_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and (
        bool(_MARKER_RE.search(stripped_text))
        or any(part.lower() in _SUPPORT_DIRECTORIES for part in normalized_path.parts[:-1])
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    return file_path if path.name.lower() in _MAKEFILE_BASENAMES else str(path.with_suffix(""))


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*raw_names: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        candidate = str(raw_name or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return tuple(ordered)


def normalize_include_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip('"').strip("'").replace("\\", "/")


def _split_tokens(raw_value: str) -> tuple[str, ...]:
    normalized = str(raw_value or "").replace("\\\n", " ").replace("|", " ")
    return tuple(token for token in normalized.split() if token)


def is_operational_target_name(name: str) -> bool:
    normalized_name = str(name or "").strip()
    return bool(normalized_name) and not (
        "$" in normalized_name
        or "%" in normalized_name
        or "=" in normalized_name
        or normalized_name.startswith(".")
        or normalized_name in _SPECIAL_TARGETS
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _RULE_RE.finditer(stripped_text):
        line_number = _line_number(stripped_text, match.start())
        for target_name in _split_tokens(match.group("targets") or ""):
            if not is_operational_target_name(target_name):
                continue
            item = (target_name, "target", line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0])))


def iter_include_targets(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    includes: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        line_number = _line_number(stripped_text, match.start())
        for target_name in _split_tokens(match.group("targets") or ""):
            normalized_target = normalize_include_target(target_name)
            if (
                not normalized_target
                or "$" in normalized_target
                or "*" in normalized_target
                or "?" in normalized_target
            ):
                continue
            item = (normalized_target, line_number)
            if item not in seen:
                seen.add(item)
                includes.append(item)
    return tuple(includes)


def iter_reference_names(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _RULE_RE.finditer(stripped_text):
        line_number = _line_number(stripped_text, match.start())
        for candidate in _split_tokens(match.group("deps") or ""):
            if not is_operational_target_name(candidate):
                continue
            item = (candidate, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
    for match in _MAKE_INVOKE_RE.finditer(stripped_text):
        target_name = str(match.group("target") or "").strip()
        if not is_operational_target_name(target_name):
            continue
        item = (target_name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(sorted(references, key=lambda item: (item[1], item[0])))
