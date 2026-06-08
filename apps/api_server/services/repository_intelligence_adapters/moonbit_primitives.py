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

MOONBIT_SOURCE_SUFFIXES = frozenset({".mbt", ".mbti"})
MOONBIT_CONFIG_BASENAMES = frozenset({"moon.mod", "moon.pkg"})
_IDENTIFIER_RE = r"[A-Za-z_][A-Za-z0-9_]*"
_PACKAGE_ALIAS_RE = r"[A-Za-z0-9_./-]+"
_IMPORT_BLOCK_RE = re.compile(r"(?ms)^\s*import\s*\{(?P<body>.*?)\}\s*(?:for\s*\"[^\"]*\")?")
_IMPORT_ENTRY_RE = re.compile(
    rf"\"(?P<target>[^\"]+)\"(?:\s*@(?P<alias>{_PACKAGE_ALIAS_RE}))?"
)
_USING_BLOCK_RE = re.compile(
    rf"(?ms)^\s*(?:pub\s+)?using\s+@(?P<alias>{_PACKAGE_ALIAS_RE})\s*\{{(?P<body>.*?)\}}"
)
_EXPORT_ENTRY_RE = re.compile(rf"(?:type\s+)?(?P<name>{_IDENTIFIER_RE})")
_STRUCT_RE = re.compile(
    rf"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:all\s+)?struct\s+(?P<name>{_IDENTIFIER_RE})\b"
)
_ENUM_RE = re.compile(
    rf"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?enum\s+(?P<name>{_IDENTIFIER_RE})\b"
)
_TYPE_RE = re.compile(
    rf"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?type\s+(?P<name>{_IDENTIFIER_RE})\b"
)
_TRAIT_RE = re.compile(
    rf"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?trait\s+(?P<name>{_IDENTIFIER_RE})\b"
)
_METHOD_RE = re.compile(
    rf"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?fn\s+(?P<owner>{_IDENTIFIER_RE})::(?P<name>{_IDENTIFIER_RE})\s*(?:\[|\(|<)"
)
_FUNCTION_RE = re.compile(
    rf"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?fn\s+(?P<name>{_IDENTIFIER_RE})\s*(?:\[|\(|<)"
)
_TEST_RE = re.compile(r'(?m)^\s*test\s+\"(?P<name>[^\"]+)\"')
_QUALIFIED_REFERENCE_RE = re.compile(
    rf"@(?P<alias>{_PACKAGE_ALIAS_RE})\.(?P<name>{_IDENTIFIER_RE})(?:(?P<method>::{_IDENTIFIER_RE}))?"
)
_TYPE_METHOD_REFERENCE_RE = re.compile(
    rf"(?<![@])\b(?P<owner>{_IDENTIFIER_RE})::(?P<name>{_IDENTIFIER_RE})\s*(?=\()"
)
_UNQUALIFIED_CALL_RE = re.compile(rf"(?<![@./:])\b(?P<name>{_IDENTIFIER_RE})\s*(?=\()")
_CONFIG_MARKER_RE = re.compile(r"(?im)^\s*name\s*=|^\s*import\s*\{|^\s*options\s*\(")
_SOURCE_MARKER_RE = re.compile(
    r"(?im)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|type|trait|fn)\b|^\s*test\s+\"|^\s*(?:pub\s+)?using\s+@|^\s*(?:pub\s+)?impl\b"
)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?m)//.*$")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "else",
        "enum",
        "fn",
        "for",
        "if",
        "impl",
        "let",
        "match",
        "pub",
        "return",
        "struct",
        "test",
        "trait",
        "type",
        "using",
        "while",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _preserve_line_count_comment(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(_preserve_line_count_comment, text)
    return _LINE_COMMENT_RE.sub("", without_block_comments)


def normalize_identifier(raw_value: str) -> str:
    return str(raw_value or "").strip()


def _ordered_names(*raw_values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        candidate = normalize_identifier(raw_value)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return tuple(ordered)


def has_moonbit_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in MOONBIT_SOURCE_SUFFIXES
        or normalized_path.name.lower() in MOONBIT_CONFIG_BASENAMES
    )


def is_probable_moonbit_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in MOONBIT_SOURCE_SUFFIXES or not text:
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_SOURCE_MARKER_RE.search(stripped_text))


def is_probable_moonbit_config(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).name.lower() not in MOONBIT_CONFIG_BASENAMES or not text:
        return False
    return bool(_CONFIG_MARKER_RE.search(strip_comments(text)))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path).with_suffix("")
    stem = path.name
    if stem == "pkg.generated":
        return path.parent.name or stem
    return stem


def normalize_import_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target).strip('"').strip("'")
    if "@" in normalized_target:
        head, tail = normalized_target.rsplit("@", 1)
        if tail and "/" not in tail:
            normalized_target = head
    return normalized_target.rstrip("/")


def parse_import_entries(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, int]] = []
    seen: set[tuple[str, str | None, int]] = set()
    for block_match in _IMPORT_BLOCK_RE.finditer(stripped_text):
        body = str(block_match.group("body") or "")
        for entry_match in _IMPORT_ENTRY_RE.finditer(body):
            target = normalize_import_target(str(entry_match.group("target") or ""))
            alias = normalize_identifier(str(entry_match.group("alias") or "")) or None
            if not target:
                continue
            item = (
                target,
                alias,
                _line_number(stripped_text, block_match.start("body") + entry_match.start()),
            )
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def parse_using_entries(text: str) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, tuple[str, ...], int]] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for block_match in _USING_BLOCK_RE.finditer(stripped_text):
        alias = normalize_identifier(str(block_match.group("alias") or ""))
        if not alias:
            continue
        exported_names = tuple(
            dict.fromkeys(
                normalize_identifier(str(match.group("name") or ""))
                for match in _EXPORT_ENTRY_RE.finditer(str(block_match.group("body") or ""))
                if normalize_identifier(str(match.group("name") or ""))
            )
        )
        item = (
            alias,
            exported_names,
            _line_number(stripped_text, block_match.start()),
        )
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    for regex, symbol_kind in (
        (_STRUCT_RE, "struct"),
        (_ENUM_RE, "enum"),
        (_TYPE_RE, "type"),
        (_TRAIT_RE, "trait"),
    ):
        for match in regex.finditer(stripped_text):
            symbol_name = normalize_identifier(str(match.group("name") or ""))
            if not symbol_name or (symbol_name, symbol_kind) in seen:
                continue
            seen.add((symbol_name, symbol_kind))
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    for match in _METHOD_RE.finditer(stripped_text):
        owner = normalize_identifier(str(match.group("owner") or ""))
        method_name = normalize_identifier(str(match.group("name") or ""))
        if not owner or not method_name:
            continue
        symbol_name = f"{owner}::{method_name}"
        if (symbol_name, "function") in seen:
            continue
        seen.add((symbol_name, "function"))
        entries.append((symbol_name, "function", _line_number(stripped_text, match.start())))
    for match in _FUNCTION_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if (
            not symbol_name
            or symbol_name in _RESERVED_SYMBOL_NAMES
            or (symbol_name, "function") in seen
        ):
            continue
        seen.add((symbol_name, "function"))
        entries.append((symbol_name, "function", _line_number(stripped_text, match.start())))
    for match in _TEST_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name or (symbol_name, "test") in seen:
            continue
        seen.add((symbol_name, "test"))
        entries.append((symbol_name, "test", _line_number(stripped_text, match.start())))
    entries.sort(key=lambda entry: (entry[2], entry[1], entry[0]))
    return tuple(entries)


__all__ = [
    "MOONBIT_CONFIG_BASENAMES",
    "MOONBIT_SOURCE_SUFFIXES",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "StableIdentifier",
    "_CollectedSymbol",
    "_QUALIFIED_REFERENCE_RE",
    "_RESERVED_SYMBOL_NAMES",
    "_TYPE_METHOD_REFERENCE_RE",
    "_UNQUALIFIED_CALL_RE",
    "_line_count",
    "_line_number",
    "_ordered_names",
    "has_moonbit_path_hints",
    "is_probable_moonbit_config",
    "is_probable_moonbit_source",
    "iter_symbol_entries",
    "module_name_from_path",
    "normalize_identifier",
    "normalize_import_target",
    "parse_import_entries",
    "parse_using_entries",
    "strip_comments",
]
