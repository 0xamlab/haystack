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

_KNOWN_SUFFIXES = frozenset({".raku", ".rakumod", ".rakutest", ".pm6", ".p6"})
_PACKAGE_RE = re.compile(
    r"^\s*(?:unit\s+)?(?P<kind>module|class|role|grammar|package)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_:\-]*)\b",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"^\s*(?P<kind>use|need|require)\s+"
    r"(?P<target>(?:['\"][^'\"]+['\"]|[A-Za-z_][A-Za-z0-9_:\-.]*))"
    r"(?P<body>[^\n;]*);",
    re.MULTILINE,
)
_SYMBOL_RE = re.compile(
    r"^\s*(?:(?:proto|multi|only|our|my|state)\s+)*"
    r"(?P<kind>sub|method|token|rule|regex)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_:\-]*)\b",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_:]*)::(?P<name>[A-Za-z_][A-Za-z0-9_:\-]*)\b"
)
_UNQUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<name>[A-Za-z_][A-Za-z0-9_:\-]*)\s*(?:\(|\{)"
)
_MARKER_RE = re.compile(
    r"\b(?:use|need|require|unit\s+(?:module|class|role|grammar|package)|"
    r"module|class|role|grammar|package|sub|method|token|rule|regex)\b"
)
_IGNORED_IMPORT_TARGETS = frozenset(
    {
        "v6",
        "v6.c",
        "v6.d",
        "v6.e",
        "experimental",
        "lib",
        "nativecall",
        "test",
    }
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "BEGIN",
        "CATCH",
        "CHECK",
        "CONTROL",
        "END",
        "ENTER",
        "FIRST",
        "INIT",
        "KEEP",
        "LAST",
        "LEAVE",
        "NEXT",
        "POST",
        "PRE",
        "QUIT",
        "START",
        "TEMP",
        "UNDO",
        "class",
        "do",
        "else",
        "elsif",
        "for",
        "given",
        "grammar",
        "if",
        "method",
        "module",
        "need",
        "package",
        "race",
        "react",
        "regex",
        "require",
        "role",
        "rule",
        "sub",
        "token",
        "unless",
        "until",
        "use",
        "when",
        "while",
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


def strip_comments(text: str) -> str:
    characters: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_single or in_double:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif in_single and character == "'":
                in_single = False
            elif in_double and character == '"':
                in_double = False
            index += 1
            continue
        if character == "#":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == "'":
            in_single = True
        elif character == '"':
            in_double = True
        index += 1
    return "".join(characters)


def has_raku_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_raku_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_raku_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] in {"lib", "bin", "t", "xt", "test", "tests", "examples", "tools"}:
        parts = parts[1:]
    return "::".join(part for part in parts if part)


def parse_import_statements(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        import_kind = str(match.group("kind") or "").strip()
        import_target = str(match.group("target") or "").strip().strip("'").strip('"')
        if (
            not import_kind
            or not import_target
            or import_target.lower() in _IGNORED_IMPORT_TARGETS
        ):
            continue
        item = (import_kind, import_target, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            statements.append(item)
    return tuple(statements)


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
    symbol_kinds = {
        "class": "class",
        "grammar": "grammar",
        "method": "method",
        "module": "module",
        "package": "module",
        "regex": "regex",
        "role": "role",
        "rule": "rule",
        "sub": "function",
        "token": "token",
    }
    for match in _PACKAGE_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        raw_kind = str(match.group("kind") or "").strip()
        if (
            not symbol_name
            or symbol_name in seen_names
            or symbol_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        seen_names.add(symbol_name)
        entries.append(
            (
                symbol_name,
                symbol_kinds.get(raw_kind, "symbol"),
                _line_number(stripped_text, match.start()),
            )
        )
    for match in _SYMBOL_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        raw_kind = str(match.group("kind") or "").strip()
        if (
            not symbol_name
            or symbol_name in seen_names
            or symbol_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        seen_names.add(symbol_name)
        entries.append(
            (
                symbol_name,
                symbol_kinds.get(raw_kind, "symbol"),
                _line_number(stripped_text, match.start()),
            )
        )
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))
