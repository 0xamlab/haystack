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

_KNOWN_SUFFIXES = frozenset({".yar", ".yara"})
_IMPORT_RE = re.compile(r'^\s*import\s+"(?P<module>[^"\n]+)"', re.MULTILINE)
_INCLUDE_RE = re.compile(r'^\s*include\s+"(?P<path>[^"\n]+)"', re.MULTILINE)
_RULE_DECL_RE = re.compile(
    r"^\s*(?:(?:private|global)\s+)*(?:private|global)?\s*rule\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_CONDITION_RE = re.compile(r"\bcondition\s*:", re.IGNORECASE)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<module>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_IDENTIFIER_RE = re.compile(r"(?<![$#@!])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "all",
        "and",
        "any",
        "ascii",
        "at",
        "condition",
        "contains",
        "entrypoint",
        "false",
        "filesize",
        "for",
        "fullword",
        "global",
        "import",
        "in",
        "include",
        "nocase",
        "not",
        "of",
        "or",
        "private",
        "rule",
        "them",
        "true",
        "wide",
        "xor",
    }
)


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


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def strip_comments(text: str) -> str:
    characters = list(text)
    index = 0
    in_string: str | None = None
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if in_string is not None:
            if current == "\\":
                index += 2
                continue
            if current == in_string:
                in_string = None
            index += 1
            continue
        if current in {'"', "'"}:
            in_string = current
            index += 1
            continue
        if current == "/" and next_char == "/":
            while index < len(characters) and characters[index] != "\n":
                characters[index] = " "
                index += 1
            continue
        if current == "/" and next_char == "*":
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            while index + 1 < len(characters):
                if characters[index] == "*" and characters[index + 1] == "/":
                    characters[index] = " "
                    characters[index + 1] = " "
                    index += 2
                    break
                if characters[index] != "\n":
                    characters[index] = " "
                index += 1
            continue
        index += 1
    return "".join(characters)


def has_yara_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_yara_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_yara_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(
        _RULE_DECL_RE.search(stripped_text)
        or _INCLUDE_RE.search(stripped_text)
        or _IMPORT_RE.search(stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    return str(path.with_suffix("")) if path.suffix else path.name


def parse_import_modules(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            str(match.group("module") or "").strip(),
            _line_number(stripped_text, match.start()),
        )
        for match in _IMPORT_RE.finditer(stripped_text)
        if str(match.group("module") or "").strip()
    )


def parse_include_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            str(match.group("path") or "").strip(),
            _line_number(stripped_text, match.start()),
        )
        for match in _INCLUDE_RE.finditer(stripped_text)
        if str(match.group("path") or "").strip()
    )


def iter_rule_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    seen_names: set[str] = set()
    entries: list[tuple[str, int]] = []
    for match in _RULE_DECL_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        entries.append((symbol_name, _line_number(stripped_text, match.start())))
    return tuple(entries)


def condition_text(rule_text: str) -> str:
    stripped_text = strip_comments(rule_text)
    match = _CONDITION_RE.search(stripped_text)
    if match is None:
        return ""
    return stripped_text[match.end() :]
