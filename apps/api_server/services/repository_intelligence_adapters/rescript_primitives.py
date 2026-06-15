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

RESCRIPT_SUFFIXES = frozenset({".res", ".resi"})
RESCRIPT_CONFIG_BASENAMES = frozenset({"bsconfig.json", "rescript.json"})
_SOURCE_ROOTS = ("src", "lib", "test", "tests", "examples", "example", "scripts")
_MODULE_NAME_RE = r"[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*"
_OPEN_RE = re.compile(rf"^\s*open!?\s+(?P<target>{_MODULE_NAME_RE})\b", re.MULTILINE)
_MODULE_ALIAS_RE = re.compile(
    rf"^\s*module\s+(?P<name>[A-Z][A-Za-z0-9_']*)\s*=\s*(?P<target>{_MODULE_NAME_RE})\b",
    re.MULTILINE,
)
_MODULE_DECL_RE = re.compile(r"^\s*module\s+(?P<name>[A-Z][A-Za-z0-9_']*)\s*=", re.MULTILINE)
_TYPE_RE = re.compile(r"^\s*(?:rec\s+)?type\s+(?P<name>[a-z_][A-Za-z0-9_']*)\b", re.MULTILINE)
_LET_RE = re.compile(r"^\s*let\s+(?P<name>[a-z_][A-Za-z0-9_']*)\b", re.MULTILINE)
_EXTERNAL_RE = re.compile(r"^\s*external\s+(?P<name>[a-z_][A-Za-z0-9_']*)\b", re.MULTILINE)
_QUALIFIED_REFERENCE_RE = re.compile(
    rf"\b(?P<alias>{_MODULE_NAME_RE})\.(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b"
)
_TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_']*)\b")
_VALUE_REFERENCE_RE = re.compile(r"(?<![./'])\b(?P<name>[a-z_][A-Za-z0-9_']*)\b")
_CALL_RE = re.compile(
    r"(?<![./'])\b(?P<name>[a-z_][A-Za-z0-9_']*)\b(?=\s*(?:\(|=>|:\s*[A-Za-z_(]))"
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "as",
        "assert",
        "constraint",
        "else",
        "exception",
        "external",
        "for",
        "if",
        "in",
        "include",
        "lazy",
        "let",
        "module",
        "mutable",
        "of",
        "open",
        "private",
        "rec",
        "switch",
        "then",
        "to",
        "try",
        "type",
        "when",
        "while",
        "with",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    characters: list[str] = []
    index = 0
    block_depth = 0
    in_string = False
    text_length = len(text)
    while index < text_length:
        character = text[index]
        next_two = text[index : index + 2]
        if block_depth > 0:
            if next_two == "/*":
                block_depth += 1
                characters.extend("  ")
                index += 2
                continue
            if next_two == "*/":
                block_depth = max(0, block_depth - 1)
                characters.extend("  ")
                index += 2
                continue
            characters.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            characters.append(character)
            if character == '"' and (index == 0 or text[index - 1] != "\\"):
                in_string = False
            index += 1
            continue
        if next_two == "//":
            while index < text_length and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        if next_two == "/*":
            block_depth = 1
            characters.extend("  ")
            index += 2
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters)


def has_rescript_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in RESCRIPT_SUFFIXES
        or normalized_path.name.lower() in RESCRIPT_CONFIG_BASENAMES
    )


def is_probable_rescript_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    has_rescript_syntax = bool(
        _OPEN_RE.search(stripped_text)
        or _MODULE_ALIAS_RE.search(stripped_text)
        or _MODULE_DECL_RE.search(stripped_text)
        or _TYPE_RE.search(stripped_text)
        or _LET_RE.search(stripped_text)
        or _EXTERNAL_RE.search(stripped_text)
    )
    if normalized_path.suffix.lower() in RESCRIPT_SUFFIXES:
        return has_rescript_syntax
    return has_rescript_syntax


def is_probable_rescript_config(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).name.lower() not in RESCRIPT_CONFIG_BASENAMES:
        return False
    return any(marker in text for marker in ('"sources"', '"package-specs"', '"bs-dependencies"'))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for source_root in _SOURCE_ROOTS:
        if source_root not in path.parts:
            continue
        root_index = path.parts.index(source_root)
        module_parts = list(path.parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        return ".".join(part for part in module_parts if part)
    return path.stem


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


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in (
        (_MODULE_DECL_RE, "module"),
        (_TYPE_RE, "type"),
        (_LET_RE, "function"),
        (_EXTERNAL_RE, "function"),
    ):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name in seen_names
                or symbol_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))
