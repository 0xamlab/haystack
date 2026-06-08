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

_KNOWN_SUFFIXES = frozenset({".idr", ".lidr", ".ipkg"})
_MODULE_RE = re.compile(
    r"^\s*module\s+(?P<name>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\b",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"^\s*(?:(?:public|private|export)\s+)*import\s+"
    r"(?P<target>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\b",
    re.MULTILINE,
)
_DATA_RE = re.compile(r"^\s*data\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b", re.MULTILINE)
_RECORD_RE = re.compile(r"^\s*record\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b", re.MULTILINE)
_INTERFACE_RE = re.compile(
    r"^\s*interface\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b", re.MULTILINE
)
_FUNCTION_SIG_RE = re.compile(
    r"^\s*(?P<name>[a-z_][A-Za-z0-9_']*)\s*:",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\.(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b"
)
_TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_']*)\b")
_CALL_RE = re.compile(
    r"(?<![.'])\b(?P<name>[a-z_][A-Za-z0-9_']*)\b(?=\s*(?:\{|[A-Za-z_(]))"
)
_IPKG_ASSIGNMENT_RE = re.compile(
    r"^\s*(?P<key>[A-Za-z][A-Za-z0-9_-]*)\s*=\s*(?P<value>.+)$",
    re.MULTILINE,
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "case",
        "data",
        "do",
        "else",
        "export",
        "if",
        "implementation",
        "import",
        "in",
        "interface",
        "let",
        "module",
        "mutual",
        "namespace",
        "of",
        "parameters",
        "private",
        "public",
        "record",
        "then",
        "using",
        "where",
        "with",
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
    result: list[str] = []
    in_block_comment = 0
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if in_block_comment:
            if character == "{" and next_character == "-":
                in_block_comment += 1
                result.extend((" ", " "))
                index += 2
                continue
            if character == "-" and next_character == "}":
                in_block_comment = max(0, in_block_comment - 1)
                result.extend((" ", " "))
                index += 2
                continue
            result.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            result.append(character)
            index += 1
            continue
        if character == "-" and next_character == "-":
            while index < len(text) and text[index] != "\n":
                result.append(" ")
                index += 1
            continue
        if character == "{" and next_character == "-":
            in_block_comment = 1
            result.extend((" ", " "))
            index += 2
            continue
        result.append(character)
        index += 1
    return "".join(result)


def has_idris_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = str(PurePosixPath(path)).lower()
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES or normalized_path.endswith(
        ".lidr"
    )


def is_probable_idris_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_idris_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if PurePosixPath(path).suffix.lower() == ".ipkg":
        return bool(
            re.search(r"^\s*package\s+\S+", stripped_text, re.MULTILINE)
            or _IPKG_ASSIGNMENT_RE.search(stripped_text)
        )
    return bool(_MODULE_RE.search(stripped_text) or _IMPORT_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for source_root in ("src", "lib", "app", "test", "tests", "samples"):
        if source_root not in path.parts:
            continue
        root_index = path.parts.index(source_root)
        module_parts = list(path.parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        return ".".join(part for part in module_parts if part)
    return path.stem


def parse_import_statements(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    return tuple(
        dict.fromkeys(
            str(match.group("target") or "").strip()
            for match in _IMPORT_RE.finditer(stripped_text)
            if str(match.group("target") or "").strip()
        )
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in (
        (_DATA_RE, "data"),
        (_RECORD_RE, "record"),
        (_INTERFACE_RE, "interface"),
        (_FUNCTION_SIG_RE, "function"),
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
    return tuple(entries)
