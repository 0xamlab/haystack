from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".dhall"})
_LOCAL_IMPORT_RE = re.compile(
    r"(?P<path>(?:\./|\.\./)(?:[A-Za-z0-9_.+-]+/)*[A-Za-z0-9_.+-]+(?:\.dhall)?)"
)
_LET_IMPORT_RE = re.compile(
    r"(?m)^\s*let\s+(?P<alias>[A-Za-z_][A-Za-z0-9_-]*)\s*=\s*"
    r"(?P<path>(?:\./|\.\./)[^ \t\r\n,;]+)"
)
_LET_SYMBOL_RE = re.compile(r"(?m)^\s*let\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_FIELD_SYMBOL_RE = re.compile(
    r"(?m)(?:^|[{,]\s*|\n\s*)(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*(?::[^\n=]+)?="
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_-]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_MARKER_RE = re.compile(r"\b(?:let|in|merge|toMap)\b|(?:\./|\.\./)[A-Za-z0-9_.+-]+")
_RESERVED_SYMBOL_NAMES = frozenset({"let", "in", "if", "then", "else", "merge", "toMap"})
_PACKAGE_STYLE_BASENAMES = frozenset({"package.dhall", "default.dhall", "defaults.dhall"})


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


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


def strip_comments(text: str) -> str:
    characters: list[str] = []
    in_string = False
    escape = False
    block_depth = 0
    index = 0
    while index < len(text):
        chunk = text[index : index + 2]
        character = text[index]
        if block_depth > 0:
            if chunk == "{-":
                block_depth += 1
                characters.extend((" ", " "))
                index += 2
                continue
            if chunk == "-}":
                block_depth -= 1
                characters.extend((" ", " "))
                index += 2
                continue
            characters.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            characters.append(character)
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if chunk == "{-":
            block_depth = 1
            characters.extend((" ", " "))
            index += 2
            continue
        if chunk == "--":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters)


def has_dhall_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_dhall_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_dhall_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    has_markers = _MARKER_RE.search(stripped_text) is not None
    is_package_style_entry = PurePosixPath(path).name.lower() in _PACKAGE_STYLE_BASENAMES
    return bool(stripped_text.strip()) and bool(
        has_markers or is_package_style_entry
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.name.lower() in _PACKAGE_STYLE_BASENAMES and str(path.parent) not in {"", "."}:
        return str(path.parent)
    return str(path.with_suffix("")) if path.suffix else str(path)


def parse_import_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _LOCAL_IMPORT_RE.finditer(stripped_text):
        import_path = str(match.group("path") or "").strip()
        if not import_path:
            continue
        item = (import_path, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            statements.append(item)
    return tuple(statements)


def parse_bound_import_statements(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _LET_IMPORT_RE.finditer(stripped_text):
        alias = str(match.group("alias") or "").strip()
        import_path = str(match.group("path") or "").strip()
        if not alias or not import_path:
            continue
        item = (alias, import_path, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            statements.append(item)
    return tuple(statements)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _LET_SYMBOL_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in seen_names or symbol_name in _RESERVED_SYMBOL_NAMES:
            continue
        seen_names.add(symbol_name)
        entries.append(("binding", symbol_name, _line_number(stripped_text, match.start())))
    for match in _FIELD_SYMBOL_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in seen_names or symbol_name in _RESERVED_SYMBOL_NAMES:
            continue
        seen_names.add(symbol_name)
        entries.append(("field", symbol_name, _line_number(stripped_text, match.start("name"))))
    sorted_entries = sorted(entries, key=lambda item: (item[2], item[1], item[0]))
    return tuple(
        (name, kind, line_number)
        for kind, name, line_number in sorted_entries
    )
