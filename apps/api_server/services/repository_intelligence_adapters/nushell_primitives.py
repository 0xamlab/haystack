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

_KNOWN_SUFFIXES = frozenset({".nu"})
_SOURCE_RE = re.compile(
    r"^\s*(?P<command>source(?:-env)?|overlay\s+use)\s+"
    r"(?P<target>(?:\"[^\"]+\"|'[^']+'|[^\s#;|]+))",
    re.MULTILINE | re.IGNORECASE,
)
_USE_RE = re.compile(
    r"^\s*(?:export\s+)?use\s+(?P<target>(?:\"[^\"]+\"|'[^']+'|[^\s#;|]+))",
    re.MULTILINE | re.IGNORECASE,
)
_DEF_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<kind>def(?:-env)?|extern|alias)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b",
    re.MULTILINE,
)
_MODULE_RE = re.compile(
    r"^\s*(?:export\s+)?module\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b",
    re.MULTILINE,
)
_COMMAND_REFERENCE_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b",
    re.MULTILINE,
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "alias",
        "break",
        "const",
        "continue",
        "def",
        "def-env",
        "do",
        "export",
        "extern",
        "for",
        "if",
        "let",
        "loop",
        "match",
        "module",
        "mut",
        "overlay",
        "return",
        "source",
        "source-env",
        "try",
        "use",
        "while",
    }
)
_BUILTIN_MODULE_NAMES = frozenset(
    {
        "std",
        "core",
        "math",
        "strings",
        "path",
        "url",
        "http",
        "stor",
        "platform",
        "random",
        "datetime",
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
    index = 0
    while index < len(text):
        character = text[index]
        if in_single:
            characters.append(character)
            if character == "'" and (index == 0 or text[index - 1] != "\\"):
                in_single = False
            index += 1
            continue
        if in_double:
            characters.append(character)
            if character == '"' and (index == 0 or text[index - 1] != "\\"):
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


def has_nushell_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_nushell_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if has_nushell_path_hints(path):
        return True
    stripped_text = strip_comments(text)
    return bool(
        _DEF_RE.search(stripped_text)
        or _USE_RE.search(stripped_text)
        or _SOURCE_RE.search(stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] in {"src", "scripts", "modules", "completions", "custom-completions"}:
        parts = parts[1:]
    if parts and parts[-1] == "mod":
        parts = parts[:-1]
    return "/".join(part for part in parts if part)


def parse_use_targets(raw_value: str) -> tuple[str, ...]:
    targets: list[str] = []
    for raw_target in str(raw_value or "").split(","):
        candidate = raw_target.strip().strip("\"'")
        if not candidate or candidate in _RESERVED_SYMBOL_NAMES:
            continue
        targets.append(candidate)
    return tuple(dict.fromkeys(targets))


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
    for regex, symbol_kind in ((_MODULE_RE, "module"), (_DEF_RE, "function")):
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
