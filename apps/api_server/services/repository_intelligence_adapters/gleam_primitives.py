from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".gleam"})
_IMPORT_RE = re.compile(
    r"^\s*import\s+"
    r"(?P<target>[a-z][a-z0-9_]*(?:/[a-z][a-z0-9_]*)*)"
    r"(?:\.\{(?P<imports>[^}]*)\})?"
    r"(?:\s+as\s+(?P<alias>[a-z][A-Za-z0-9_]*))?",
    re.MULTILINE,
)
_TYPE_RE = re.compile(
    r"^\s*(?:pub\s+)?(?:opaque\s+)?type\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_CONST_RE = re.compile(r"^\s*(?:pub\s+)?const\s+(?P<name>[a-z][A-Za-z0-9_]*)\b", re.MULTILINE)
_FN_RE = re.compile(
    r"^\s*(?:pub\s+)?(?:external\s+)?fn\s+(?P<name>[a-z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[a-z][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_]*)\b")
_VALUE_REFERENCE_RE = re.compile(r"(?<![./])\b(?P<name>[a-z][A-Za-z0-9_]*)\b")
_CALL_RE = re.compile(r"(?<![./])\b(?P<name>[a-z][A-Za-z0-9_]*)\b(?=\s*\()")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "as",
        "assert",
        "auto",
        "case",
        "const",
        "external",
        "fn",
        "if",
        "import",
        "let",
        "opaque",
        "panic",
        "pub",
        "todo",
        "type",
        "use",
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
    index = 0
    in_string = False
    while index < len(text):
        character = text[index]
        next_two = text[index : index + 2]
        if in_string:
            characters.append(character)
            if character == '"' and (index == 0 or text[index - 1] != "\\"):
                in_string = False
            index += 1
            continue
        if next_two == "//":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters)


def has_gleam_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_gleam_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if has_gleam_path_hints(path):
        return True
    effective_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    return bool(
        _IMPORT_RE.search(effective_stripped_text)
        or _TYPE_RE.search(effective_stripped_text)
        or _FN_RE.search(effective_stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for source_root in ("src", "test", "tests"):
        if source_root not in path.parts:
            continue
        root_index = path.parts.index(source_root)
        module_parts = list(path.parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        return "/".join(part for part in module_parts if part)
    return str(path.with_suffix("")).strip("/")


def parse_import_names(raw_value: str) -> tuple[str, ...]:
    names: list[str] = []
    for raw_name in str(raw_value or "").split(","):
        item = raw_name.strip()
        if not item or item in _RESERVED_SYMBOL_NAMES:
            continue
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", item):
            continue
        names.append(item)
    return tuple(dict.fromkeys(names))


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


@lru_cache(maxsize=1024)
def _iter_symbol_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in ((_TYPE_RE, "type"), (_CONST_RE, "constant"), (_FN_RE, "function")):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
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
                    symbol_kind,
                    _line_number(stripped_text, match.start()),
                )
            )
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    effective_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    return _iter_symbol_entries_from_stripped_text(effective_stripped_text)
