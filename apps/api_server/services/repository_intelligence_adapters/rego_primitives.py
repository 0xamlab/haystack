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

_KNOWN_SUFFIXES = frozenset({".rego"})
_PACKAGE_RE = re.compile(
    r"^\s*package\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\b",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
    r"(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?\b",
    re.MULTILINE,
)
_DEFAULT_RULE_RE = re.compile(
    r"^\s*default\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_RULE_HEAD_RE = re.compile(
    r"^\s*(?!package\b|import\b|default\b|else\b|some\b|with\b|not\b|contains\b)"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\([^)\n]*\))?"
    r"(?:\[[^\]\n]+\])?"
    r"(?:\s+contains(?:\s+[A-Za-z_][A-Za-z0-9_]*)?)?"
    r"\s*(?::=|=|if\b|\{)",
    re.MULTILINE,
)
_DATA_REFERENCE_RE = re.compile(r"\b(?P<full>data(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\b")
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_IDENTIFIER_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "as",
        "contains",
        "data",
        "default",
        "else",
        "every",
        "false",
        "if",
        "import",
        "in",
        "not",
        "null",
        "package",
        "some",
        "true",
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
    stripped_lines: list[str] = []
    for raw_line in text.splitlines():
        quote: str | None = None
        escaped = False
        output_chars: list[str] = []
        for character in raw_line:
            if quote is None:
                if character == "#":
                    break
                if character in {'"', "'"}:
                    quote = character
                output_chars.append(character)
                continue
            output_chars.append(character)
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == quote:
                quote = None
        stripped_lines.append("".join(output_chars).rstrip())
    return "\n".join(stripped_lines)


def has_rego_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def package_name_from_text(text: str) -> str | None:
    match = _PACKAGE_RE.search(strip_comments(text))
    if match is None:
        return None
    package_name = str(match.group("name") or "").strip()
    return package_name or None


def is_probable_rego_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_rego_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(
        package_name_from_text(stripped_text)
        or _IMPORT_RE.search(stripped_text)
        or _DEFAULT_RULE_RE.search(stripped_text)
        or _RULE_HEAD_RE.search(stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.suffix:
        return str(path.with_suffix("")).replace("/", ".")
    return path.name


def parse_import_statements(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, str | None, int]] = []
    for match in _IMPORT_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        alias = str(match.group("alias") or "").strip() or None
        if not target:
            continue
        statements.append((target, alias, _line_number(stripped_text, match.start())))
    return tuple(statements)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in ((_DEFAULT_RULE_RE, "default"), (_RULE_HEAD_RE, "rule")):
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
