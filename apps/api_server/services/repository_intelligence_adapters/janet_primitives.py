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

_KNOWN_SUFFIXES = frozenset({".janet"})
_IMPORT_RE = re.compile(
    r"^\s*\(\s*(?P<kind>import|use|require)\s+"
    r"(?P<target>(?:\"[^\"]+\"|[^\s)\]]+))"
    r"(?P<rest>[^)]*)\)",
    re.MULTILINE,
)
_ALIAS_RE = re.compile(r":as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_./-]*)")
_DEF_RE = re.compile(
    r"^\s*\(\s*(?P<kind>defn-?|defmacro-?|def-?|var-?)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_!?./:-]*)\b",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_./-]*)/(?P<name>[A-Za-z_][A-Za-z0-9_!?./:-]*)\b"
)
_UNQUALIFIED_REFERENCE_RE = re.compile(
    r"\(\s*(?P<name>[A-Za-z_][A-Za-z0-9_!?./:-]*)\b"
)
_MARKER_RE = re.compile(r"\(\s*(?:import|use|require|defn-?|defmacro-?|def-?|var-?)\b")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "break",
        "case",
        "def",
        "def-",
        "default",
        "defmacro",
        "defmacro-",
        "defn",
        "defn-",
        "do",
        "fn",
        "for",
        "if",
        "import",
        "loop",
        "quote",
        "quasiquote",
        "require",
        "set",
        "unquote",
        "use",
        "var",
        "var-",
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
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_string:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == "#":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters)


def has_janet_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_janet_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_janet_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] in {"src", "test", "tests", "tools", "bin"}:
        parts = parts[1:]
    if parts and parts[-1] == "init":
        parts = parts[:-1]
    return "/".join(part for part in parts if part)


def parse_import_statements(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, str, str | None, int]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        import_kind = str(match.group("kind") or "").strip()
        import_target = str(match.group("target") or "").strip().strip('"')
        if not import_kind or not import_target:
            continue
        import_alias: str | None = None
        rest = str(match.group("rest") or "")
        if import_alias is None:
            alias_match = _ALIAS_RE.search(rest)
            if alias_match is not None:
                import_alias = str(alias_match.group("alias") or "").strip() or None
        item = (
            import_kind,
            import_target,
            import_alias,
            _line_number(stripped_text, match.start()),
        )
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
        "def": "variable",
        "def-": "variable",
        "defn": "function",
        "defn-": "function",
        "defmacro": "macro",
        "defmacro-": "macro",
        "var": "variable",
        "var-": "variable",
    }
    for match in _DEF_RE.finditer(stripped_text):
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
