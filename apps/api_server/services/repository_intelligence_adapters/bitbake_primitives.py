from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".bb", ".bbappend", ".bbclass"})
BITBAKE_CONFIG_BASENAMES = frozenset({"layer.conf", "bblayers.conf", "local.conf"})
_KNOWN_CONFIG_SUFFIXES = frozenset({".inc"})
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:include|require|inherit(?:_defer)?)\b|"
    r"^\s*(?:python\s+)?[A-Za-z_][A-Za-z0-9_:+.-]*\s*\(\)\s*\{|"
    r"^\s*[A-Za-z0-9_:+.${}-]+\s*(?:\?=|:=|\+=|=\.|=\+|\.=|=)"
)
_INCLUDE_RE = re.compile(
    r"(?im)^\s*(?P<kind>include|require)\s+(?P<target>[^#\n]+)"
)
_INHERIT_RE = re.compile(
    r"(?im)^\s*(?P<kind>inherit(?:_defer)?)\s+(?P<targets>[^#\n]+)"
)
_FUNCTION_RE = re.compile(
    r"(?im)^\s*(?:python\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_:+.-]*)\s*\(\)\s*\{"
)
_ASSIGNMENT_RE = re.compile(
    r"(?im)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_:+.-]*)\s*(?:\?=|:=|\+=|=\.|=\+|\.=|=)"
)
_VAR_REF_RE = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_:+.-]*)[^}]*\}")
_COMMENT_RE = re.compile(r"(^|[^\\\\])#.*$")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "addtask",
        "after",
        "before",
        "deltask",
        "export",
        "fakeroot",
        "include",
        "inherit",
        "inherit_defer",
        "python",
        "require",
    }
)
_NOISY_VARIABLES = frozenset(
    {
        "SUMMARY",
        "DESCRIPTION",
        "LICENSE",
        "LIC_FILES_CHKSUM",
        "SECTION",
        "DEPENDS",
        "RDEPENDS",
        "SRC_URI",
        "S",
        "B",
        "WORKDIR",
        "FILESEXTRAPATHS",
        "BBCLASSEXTEND",
        "PACKAGECONFIG",
        "IMAGE_INSTALL",
    }
)


def strip_comments(text: str) -> str:
    stripped_lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.lstrip().startswith("#"):
            stripped_lines.append("")
            continue
        stripped_lines.append(_COMMENT_RE.sub(r"\1", raw_line).rstrip())
    return "\n".join(stripped_lines)


def has_bitbake_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in _KNOWN_SUFFIXES
        or normalized_path.suffix.lower() in _KNOWN_CONFIG_SUFFIXES
        or normalized_path.name.lower() in BITBAKE_CONFIG_BASENAMES
    )


def is_probable_bitbake_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_bitbake_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.suffix.lower() == ".bbclass":
        return path.stem
    if path.suffix.lower() in {".bb", ".bbappend"}:
        stem = path.stem
        return stem.split("_", 1)[0] if "_" in stem else stem
    if path.suffix.lower() == ".inc":
        return path.stem
    return path.name


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
        normalized = str(raw_name or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def normalize_import_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip('"').strip("'").replace("\\", "/")


def _split_tokens(raw_value: str) -> tuple[str, ...]:
    normalized = str(raw_value or "").replace("\\\n", " ")
    return tuple(token for token in normalized.split() if token)


def is_referenceable_symbol_name(name: str) -> bool:
    normalized = str(name or "").strip()
    return bool(normalized) and normalized not in _RESERVED_SYMBOL_NAMES


def iter_include_targets(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    includes: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").strip().lower()
        line_number = _line_number(stripped_text, match.start())
        for target in _split_tokens(match.group("target") or ""):
            normalized_target = normalize_import_target(target)
            if (
                not normalized_target
                or "${" in normalized_target
                or "://" in normalized_target
                or "*" in normalized_target
                or "?" in normalized_target
            ):
                continue
            item = (kind, normalized_target, line_number)
            if item not in seen:
                seen.add(item)
                includes.append(item)
    return tuple(includes)


def iter_inherit_targets(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    inherits: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _INHERIT_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").strip().lower()
        line_number = _line_number(stripped_text, match.start())
        for target in _split_tokens(match.group("targets") or ""):
            normalized_target = normalize_import_target(target)
            if not normalized_target or "${" in normalized_target:
                continue
            item = (kind, normalized_target, line_number)
            if item not in seen:
                seen.add(item)
                inherits.append(item)
    return tuple(inherits)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _FUNCTION_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not is_referenceable_symbol_name(symbol_name):
            continue
        seen_names.add(symbol_name)
        entries.append((symbol_name, "task", _line_number(stripped_text, match.start())))
    for match in _ASSIGNMENT_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if (
            not is_referenceable_symbol_name(symbol_name)
            or symbol_name in seen_names
            or symbol_name in _NOISY_VARIABLES
        ):
            continue
        seen_names.add(symbol_name)
        entries.append((symbol_name, "variable", _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_reference_names(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _VAR_REF_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not is_referenceable_symbol_name(symbol_name):
            continue
        item = (symbol_name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(sorted(references, key=lambda item: (item[1], item[0])))
