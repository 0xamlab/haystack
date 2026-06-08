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

FACTOR_FILE_SUFFIXES = frozenset({".factor"})
FACTOR_CONFIG_BASENAMES = frozenset()
_IMPORT_PREFIXES = ("USING:", "QUALIFIED:", "FROM:", "EXCLUDE:")
_MARKER_PREFIXES = (
    "USING:",
    "QUALIFIED:",
    "FROM:",
    "EXCLUDE:",
    "IN:",
    ": ",
    ":: ",
    "M: ",
    "GENERIC:",
    "TUPLE:",
    "SYMBOL:",
    "PREDICATE:",
    "UNION:",
    "MIXIN:",
    "HOOK:",
    "CONSTANT:",
    "ERROR:",
)
IN_RE = re.compile(r"(?m)^\s*IN:\s+(?P<name>[A-Za-z0-9._-]+)\s*$")
QUALIFIED_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9._?!+*/<>=\\-])(?P<qualifier>[A-Za-z][A-Za-z0-9._-]*)\:(?P<name>[A-Za-z][A-Za-z0-9._?!+*/<>=-]*)(?![A-Za-z0-9._?!+*/<>=-])"
)
WORD_LITERAL_RE = re.compile(r"\\\s+(?P<name>[A-Za-z][A-Za-z0-9._?!+*/<>=-]*)")
WORD_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9._?!+*/<>=\\-])(?P<name>[A-Za-z][A-Za-z0-9._?!+*/<>=-]*)(?![A-Za-z0-9._?!+*/<>=-])"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "M",
        "USING",
        "QUALIFIED",
        "FROM",
        "EXCLUDE",
        "IN",
        "GENERIC",
        "TUPLE",
        "SYMBOL",
        "PREDICATE",
        "UNION",
        "MIXIN",
        "HOOK",
        "CONSTANT",
        "ERROR",
        "PRIVATE>",
        "<PRIVATE",
    }
)
_DECLARATION_PREFIX_KINDS = {
    "GENERIC:": "generic",
    "TUPLE:": "tuple",
    "SYMBOL:": "symbol",
    "PREDICATE:": "predicate",
    "UNION:": "union",
    "MIXIN:": "mixin",
    "HOOK:": "hook",
    "CONSTANT:": "constant",
    "ERROR:": "error",
}


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


@dataclass(frozen=True)
class _ImportStatement:
    target: str
    qualifier: str | None
    imported_names: tuple[str, ...]
    line_number: int


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
    stripped_lines: list[str] = []
    for raw_line in text.splitlines():
        comment_index = raw_line.find("!")
        stripped_lines.append(raw_line if comment_index < 0 else raw_line[:comment_index])
    return "\n".join(stripped_lines)


def has_factor_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return normalized_path.suffix.lower() in FACTOR_FILE_SUFFIXES


def is_probable_factor_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in FACTOR_FILE_SUFFIXES:
        return False
    for raw_line in strip_comments(text).splitlines():
        if raw_line.strip().startswith(_MARKER_PREFIXES):
            return True
    return False


def vocabulary_name_from_text(text: str, *, file_path: str) -> str:
    match = IN_RE.search(strip_comments(text))
    if match is not None:
        vocabulary_name = str(match.group("name") or "").strip()
        if vocabulary_name:
            return vocabulary_name
    return PurePosixPath(file_path).stem


def _normalize_symbol_token(value: str) -> str:
    return str(value or "").strip().rstrip(";")


def _looks_like_symbol_name(value: str) -> bool:
    normalized = _normalize_symbol_token(value)
    return normalized[:1].isalpha() and normalized not in RESERVED_SYMBOL_NAMES


def parse_import_statements(text: str) -> tuple[_ImportStatement, ...]:
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()
    imports: list[_ImportStatement] = []
    seen: set[tuple[str, str | None, tuple[str, ...], int]] = set()
    line_index = 0
    while line_index < len(lines):
        stripped_line = lines[line_index].strip()
        prefix = next(
            (candidate for candidate in _IMPORT_PREFIXES if stripped_line.startswith(candidate)),
            None,
        )
        if prefix is None:
            line_index += 1
            continue
        start_line = line_index + 1
        parts = [stripped_line]
        while ";" not in parts[-1] and line_index + 1 < len(lines):
            line_index += 1
            parts.append(lines[line_index].strip())
        statement = " ".join(parts)
        body = statement[len(prefix) :]
        if ";" in body:
            body = body.split(";", 1)[0]
        body = body.strip()
        if prefix in {"USING:", "QUALIFIED:"}:
            for target in (_normalize_symbol_token(part) for part in body.split()):
                if not _looks_like_symbol_name(target):
                    continue
                item = (
                    target,
                    target if prefix == "QUALIFIED:" else None,
                    (),
                    start_line,
                )
                if item not in seen:
                    seen.add(item)
                    imports.append(
                        _ImportStatement(
                            target=target,
                            qualifier=item[1],
                            imported_names=(),
                            line_number=start_line,
                        )
                    )
        else:
            target_section, _, imported_section = body.partition("=>")
            target_parts = target_section.split()
            target = _normalize_symbol_token(target_parts[0] if target_parts else "")
            if _looks_like_symbol_name(target):
                imported_names = tuple(
                    _normalize_symbol_token(part)
                    for part in imported_section.split()
                    if _looks_like_symbol_name(part)
                )
                item = (
                    target,
                    None,
                    imported_names if prefix == "FROM:" else (),
                    start_line,
                )
                if item not in seen:
                    seen.add(item)
                    imports.append(
                        _ImportStatement(
                            target=target,
                            qualifier=None,
                            imported_names=item[2],
                            line_number=start_line,
                        )
                    )
        line_index += 1
    return tuple(imports)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    symbols: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        symbol_name = ""
        symbol_kind = ""
        if stripped_line.startswith(": "):
            parts = stripped_line.split()
            symbol_name = _normalize_symbol_token(parts[1] if len(parts) > 1 else "")
            symbol_kind = "word"
        elif stripped_line.startswith(":: "):
            parts = stripped_line.split()
            symbol_name = _normalize_symbol_token(parts[1] if len(parts) > 1 else "")
            symbol_kind = "word"
        elif stripped_line.startswith("M: "):
            parts = stripped_line.split()
            symbol_name = _normalize_symbol_token(parts[2] if len(parts) > 2 else "")
            symbol_kind = "method"
        else:
            for prefix, kind in _DECLARATION_PREFIX_KINDS.items():
                if stripped_line.startswith(prefix):
                    parts = stripped_line.split()
                    symbol_name = _normalize_symbol_token(parts[1] if len(parts) > 1 else "")
                    symbol_kind = kind
                    break
        if not _looks_like_symbol_name(symbol_name):
            continue
        item = (symbol_name, symbol_kind, line_number)
        if item not in seen:
            seen.add(item)
            symbols.append(item)
    return tuple(symbols)


def parse_reference_targets(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        for match in QUALIFIED_REFERENCE_RE.finditer(raw_line):
            qualifier = _normalize_symbol_token(match.group("qualifier"))
            name = _normalize_symbol_token(match.group("name"))
            if not _looks_like_symbol_name(qualifier) or not _looks_like_symbol_name(name):
                continue
            item = (qualifier, name, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
        for match in WORD_LITERAL_RE.finditer(raw_line):
            name = _normalize_symbol_token(match.group("name"))
            if not _looks_like_symbol_name(name):
                continue
            item = (None, name, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
        for match in WORD_TOKEN_RE.finditer(raw_line):
            name = _normalize_symbol_token(match.group("name"))
            if not _looks_like_symbol_name(name):
                continue
            item = (None, name, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
    return tuple(references)
