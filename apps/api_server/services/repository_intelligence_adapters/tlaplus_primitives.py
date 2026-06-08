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

_KNOWN_SUFFIXES = frozenset({".tla"})
_MODULE_HEADER_RE = re.compile(
    r"(?m)^\s*-{2,}\s*MODULE\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*-{2,}\s*$"
)
_EXTENDS_RE = re.compile(r"(?m)^\s*EXTENDS\s+(?P<modules>[A-Za-z0-9_, \t]+)$")
_INSTANCE_RE = re.compile(
    r"(?m)^\s*(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*==\s*)?"
    r"(?:(?:LOCAL|USE)\s+)?INSTANCE\s+(?P<module>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_DEFINITION_RE = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^=\n]*\))?\s*=="
)
_VARIABLES_RE = re.compile(r"(?m)^\s*VARIABLES?\s+(?P<names>[A-Za-z0-9_, \t]+)$")
_CONSTANTS_RE = re.compile(r"(?m)^\s*CONSTANTS?\s+(?P<names>[A-Za-z0-9_, \t]+)$")
_IDENTIFIER_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<module>[A-Za-z_][A-Za-z0-9_]*)!(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "ASSUME",
        "ASSUMPTION",
        "AXIOM",
        "CASE",
        "CHOOSE",
        "CONSTANT",
        "CONSTANTS",
        "DOMAIN",
        "ELSE",
        "ENABLED",
        "EXCEPT",
        "EXTENDS",
        "IF",
        "IN",
        "INSTANCE",
        "LAMBDA",
        "LET",
        "LOCAL",
        "MODULE",
        "OTHER",
        "SF_",
        "SUBSET",
        "THEN",
        "THEOREM",
        "UNCHANGED",
        "UNION",
        "USE",
        "VARIABLE",
        "VARIABLES",
        "WF_",
        "WITH",
    }
)
_PREFERRED_ENTRYPOINT_PREFIXES = ("MC", "AP")


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
    characters = list(text)
    index = 0
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if current == "\\" and next_char == "*":
            while index < len(characters) and characters[index] != "\n":
                characters[index] = " "
                index += 1
            continue
        if current == "(" and next_char == "*":
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            while index + 1 < len(characters):
                if characters[index] == "*" and characters[index + 1] == ")":
                    characters[index] = " "
                    characters[index + 1] = " "
                    index += 2
                    break
                if characters[index] != "\n":
                    characters[index] = " "
                index += 1
            continue
        index += 1
    return "".join(characters)


def has_tlaplus_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def module_name_from_path(file_path: str) -> str:
    return PurePosixPath(file_path).stem


def module_name_from_text(text: str, *, file_path: str) -> str:
    stripped_text = strip_comments(text)
    match = _MODULE_HEADER_RE.search(stripped_text)
    if match:
        module_name = str(match.group("name") or "").strip()
        if module_name:
            return module_name
    return module_name_from_path(file_path)


def is_probable_tlaplus_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_tlaplus_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(
        _MODULE_HEADER_RE.search(stripped_text)
        or _EXTENDS_RE.search(stripped_text)
        or _DEFINITION_RE.search(stripped_text)
    )


def _split_symbol_list(raw_value: str) -> tuple[str, ...]:
    symbols: list[str] = []
    seen: set[str] = set()
    for item in raw_value.split(","):
        symbol_name = str(item or "").strip()
        if (
            not symbol_name
            or symbol_name in seen
            or symbol_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        seen.add(symbol_name)
        symbols.append(symbol_name)
    return tuple(symbols)


def iter_symbol_entries(text: str, *, file_path: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    module_name = module_name_from_text(stripped_text, file_path=file_path)
    for regex, symbol_kind in ((_VARIABLES_RE, "variable"), (_CONSTANTS_RE, "constant")):
        for match in regex.finditer(stripped_text):
            for symbol_name in _split_symbol_list(str(match.group("names") or "").strip()):
                if symbol_name in seen_names:
                    continue
                seen_names.add(symbol_name)
                entries.append(
                    (symbol_name, symbol_kind, _line_number(stripped_text, match.start()))
                )
    for match in _DEFINITION_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if (
            not symbol_name
            or symbol_name in seen_names
            or symbol_name in _RESERVED_SYMBOL_NAMES
            or symbol_name == module_name
        ):
            continue
        seen_names.add(symbol_name)
        entries.append((symbol_name, "definition", _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def parse_extended_modules(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    modules: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _EXTENDS_RE.finditer(stripped_text):
        line_number = _line_number(stripped_text, match.start())
        for module_name in _split_symbol_list(str(match.group("modules") or "").strip()):
            item = (module_name, line_number)
            if item in seen:
                continue
            seen.add(item)
            modules.append(item)
    return tuple(modules)


def parse_instance_statements(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for match in _INSTANCE_RE.finditer(stripped_text):
        alias = str(match.group("alias") or "").strip() or None
        module_name = str(match.group("module") or "").strip()
        if not module_name:
            continue
        item = (alias, module_name, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        statements.append(item)
    return tuple(statements)
