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

_KNOWN_SUFFIXES = frozenset({".elm"})
_MODULE_RE = re.compile(
    r"^\s*(?:port\s+)?module\s+(?P<name>[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)*)\s+exposing\b",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"^\s*import\s+"
    r"(?P<target>[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)*)"
    r"(?:\s+as\s+(?P<alias>[A-Z][A-Za-z0-9_]*))?"
    r"(?:\s+exposing\s*\((?P<exposing>[^)]*)\))?",
    re.MULTILINE,
)
_TYPE_ALIAS_RE = re.compile(
    r"^type\s+alias\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_TYPE_RE = re.compile(
    r"^type\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_FUNCTION_SIGNATURE_RE = re.compile(
    r"^(?P<name>[a-z_][A-Za-z0-9_']*)\s*:\s*",
    re.MULTILINE,
)
_FUNCTION_DEF_RE = re.compile(
    r"^(?P<name>[a-z_][A-Za-z0-9_']*)\b(?:\s+[^\n=]+)?\s*=",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_]*)\b")
_CALL_RE = re.compile(
    r"(?<![.'])\b(?P<name>[a-z_][A-Za-z0-9_']*)\b(?=\s*(?:\(|[A-Za-z_{\[]))"
)
_EXPOSING_ITEM_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\s*\((?P<body>.*?)\))?$")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "alias",
        "as",
        "case",
        "else",
        "exposing",
        "if",
        "import",
        "in",
        "let",
        "module",
        "of",
        "port",
        "then",
        "type",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    stripped_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line
        comment_index = line.find("--")
        if comment_index >= 0:
            line = line[:comment_index]
        stripped_lines.append(line.rstrip())
    return "\n".join(stripped_lines)


def is_probable_elm_source(*, path: Path | PurePosixPath, text: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in _KNOWN_SUFFIXES:
        return True
    stripped_text = strip_comments(text)
    return bool(_MODULE_RE.search(stripped_text) or _IMPORT_RE.search(stripped_text))


def has_elm_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for source_root in ("src", "tests", "examples", "example"):
        if source_root not in path.parts:
            continue
        root_index = path.parts.index(source_root)
        module_parts = list(path.parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        return ".".join(part for part in module_parts if part)
    stem = path.stem
    return stem


def parse_exposing_names(raw_value: str) -> tuple[str, ...]:
    body = str(raw_value or "").strip()
    if not body:
        return ()
    names: list[str] = []
    for raw_item in body.split(","):
        candidate = raw_item.strip()
        if not candidate or candidate in {"..", "(..)"}:
            continue
        match = _EXPOSING_ITEM_RE.match(candidate)
        if match is None:
            continue
        name = str(match.group("name") or "").strip()
        if not name or name in _RESERVED_SYMBOL_NAMES:
            continue
        names.append(name)
    return tuple(dict.fromkeys(names))


def exposing_all(raw_value: str) -> bool:
    return ".." in str(raw_value or "")


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in (
        (_TYPE_ALIAS_RE, "type_alias"),
        (_TYPE_RE, "type"),
        (_FUNCTION_SIGNATURE_RE, "function"),
        (_FUNCTION_DEF_RE, "function"),
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
