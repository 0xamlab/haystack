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

_KNOWN_SUFFIXES = frozenset({".purs"})
_MODULE_RE = re.compile(
    r"^\s*module\s+(?P<name>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\s+where\b",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"^\s*import\s+"
    r"(?P<qualified>qualified\s+)?"
    r"(?P<target>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)"
    r"(?:\s+as\s+(?P<alias>[A-Z][A-Za-z0-9_']*))?"
    r"(?:\s*\((?P<imports>[^)]*)\))?",
    re.MULTILINE,
)
_TYPE_ALIAS_RE = re.compile(r"^\s*type\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b", re.MULTILINE)
_DATA_RE = re.compile(
    r"^\s*(?:foreign\s+import\s+)?(?:data|newtype|class)\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
_VALUE_SIGNATURE_RE = re.compile(
    r"^\s*(?P<name>[a-z_][A-Za-z0-9_']*)\s*::\s*",
    re.MULTILINE,
)
_VALUE_DEF_RE = re.compile(
    r"^\s*(?P<name>[a-z_][A-Za-z0-9_']*)\b(?:\s+[^\n=]+)?\s*=",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\.(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b"
)
_TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_']*)\b")
_VALUE_REFERENCE_RE = re.compile(r"(?<![.'])\b(?P<name>[a-z_][A-Za-z0-9_']*)\b")
_CALL_RE = re.compile(
    r"(?<![.'])\b(?P<name>[a-z_][A-Za-z0-9_']*)\b(?=\s*(?:[$(]|\s+[A-Za-z_(\"']))"
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "ado",
        "as",
        "case",
        "class",
        "data",
        "derive",
        "do",
        "else",
        "false",
        "forall",
        "foreign",
        "hiding",
        "if",
        "import",
        "in",
        "infix",
        "infixl",
        "infixr",
        "instance",
        "let",
        "module",
        "newtype",
        "of",
        "then",
        "true",
        "type",
        "where",
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
    block_depth = 0
    in_string = False
    text_length = len(text)
    while index < text_length:
        character = text[index]
        next_two = text[index : index + 2]
        if block_depth > 0:
            if next_two == "{-":
                block_depth += 1
                characters.extend("  ")
                index += 2
                continue
            if next_two == "-}":
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
        if next_two == "--":
            while index < text_length and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        if next_two == "{-":
            block_depth = 1
            characters.extend("  ")
            index += 2
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters)


def has_purescript_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_purescript_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if has_purescript_path_hints(path):
        return True
    stripped_text = strip_comments(text)
    return bool(_MODULE_RE.search(stripped_text) or _IMPORT_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for source_root in ("src", "test", "tests", "examples", "example"):
        if source_root not in path.parts:
            continue
        root_index = path.parts.index(source_root)
        module_parts = list(path.parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        return ".".join(part for part in module_parts if part)
    return path.stem


def parse_import_names(raw_value: str) -> tuple[str, ...]:
    body = str(raw_value or "").strip()
    if not body:
        return ()
    names: list[str] = []
    current: list[str] = []
    depth = 0
    for character in body:
        if character == "," and depth == 0:
            candidate = "".join(current).strip()
            if candidate:
                names.append(candidate)
            current = []
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
        current.append(character)
    candidate = "".join(current).strip()
    if candidate:
        names.append(candidate)
    normalized_names: list[str] = []
    for raw_name in names:
        item = raw_name.strip()
        if not item or item in {"..", "(..)"}:
            continue
        if item.startswith("type "):
            item = item.removeprefix("type ").strip()
        if item.startswith("class "):
            item = item.removeprefix("class ").strip()
        item = item.split("(", 1)[0].strip()
        if not item or item in _RESERVED_SYMBOL_NAMES:
            continue
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_']*$", item):
            continue
        normalized_names.append(item)
    return tuple(dict.fromkeys(normalized_names))


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
        (_DATA_RE, "type"),
        (_TYPE_ALIAS_RE, "type_alias"),
        (_VALUE_SIGNATURE_RE, "function"),
        (_VALUE_DEF_RE, "function"),
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
