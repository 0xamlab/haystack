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

_KNOWN_SUFFIXES = frozenset({".bicep"})
_DECLARATION_RE = re.compile(
    r"(?m)^\s*(?P<kind>param|var|resource|module|output|type)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_MODULE_SOURCE_RE = re.compile(
    r"(?m)^\s*module\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s+['\"](?P<source>[^'\"\n]+)['\"]\s*="
)
_IDENTIFIER_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_QUALIFIED_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\.|::)")
_COMMENT_OR_STRING_RE = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/'
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "existing",
        "false",
        "for",
        "if",
        "import",
        "module",
        "null",
        "output",
        "param",
        "resource",
        "targetScope",
        "true",
        "type",
        "var",
    }
)
_PREFERRED_DIRECTORY_ENTRY_BASENAMES = frozenset({"main.bicep"})
_COMMENT_MASK_CACHE: dict[int, str] = {}


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
    if "//" not in text and "/*" not in text:
        return text

    def _mask_comment(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith(('"', "'")):
            return token
        newline_count = token.count("\n")
        if newline_count == 0:
            cached_mask = _COMMENT_MASK_CACHE.get(len(token))
            if cached_mask is None:
                cached_mask = " " * len(token)
                _COMMENT_MASK_CACHE[len(token)] = cached_mask
            return cached_mask
        return "".join("\n" if char == "\n" else " " for char in token)

    return _COMMENT_OR_STRING_RE.sub(_mask_comment, text)


def has_bicep_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_bicep_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if not has_bicep_path_hints(path):
        return False
    normalized_text = stripped_text if stripped_text is not None else strip_comments(text)
    stripped_text = normalized_text
    if not stripped_text.strip():
        return False
    return bool(
        _DECLARATION_RE.search(stripped_text)
        or re.search(r"(?m)^\s*targetScope\s*=", stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    without_suffix = str(path.with_suffix("")) if path.suffix else str(path)
    if (
        path.name.lower() in _PREFERRED_DIRECTORY_ENTRY_BASENAMES
        and str(path.parent) not in {"", "."}
    ):
        return str(path.parent).replace("/", ".")
    return without_suffix.replace("/", ".")


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    normalized_text = stripped_text if stripped_text is not None else strip_comments(text)
    stripped_text = normalized_text
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _DECLARATION_RE.finditer(stripped_text):
        symbol_kind = str(match.group("kind") or "").strip()
        symbol_name = str(match.group("name") or "").strip()
        if (
            not symbol_kind
            or not symbol_name
            or symbol_name in seen_names
            or symbol_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        seen_names.add(symbol_name)
        entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def parse_module_statements(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    normalized_text = stripped_text if stripped_text is not None else strip_comments(text)
    stripped_text = normalized_text
    statements: list[tuple[str, str, int]] = []
    for match in _MODULE_SOURCE_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        source_target = str(match.group("source") or "").strip()
        if not name or not source_target:
            continue
        statements.append((name, source_target, _line_number(stripped_text, match.start())))
    return tuple(statements)
