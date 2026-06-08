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

FENNEL_SUFFIXES = frozenset({".fnl", ".fnlm"})
_IDENTIFIER_RE = r"[A-Za-z_][A-Za-z0-9_?!*+\-<>/=.:]*"
_IMPORT_TARGET_RE = r'(?:\"[^\"]+\"|:[A-Za-z_][A-Za-z0-9_.-]*|[A-Za-z_][A-Za-z0-9_.-]*)'
_MARKER_RE = re.compile(
    r"\(\s*(?:require|require-macros|import-macros|fn|lambda|λ|macro|local|global)\b"
)
_LOCAL_REQUIRE_RE = re.compile(
    rf"^\s*\(\s*(?P<scope>local|global)\s+(?P<binding>\{{[^)\n]*\}}|{_IDENTIFIER_RE})\s+"
    rf"\(\s*(?P<kind>require|require-macros)\s+(?P<target>{_IMPORT_TARGET_RE})",
    re.MULTILINE,
)
_IMPORT_MACROS_RE = re.compile(
    rf"^\s*\(\s*import-macros\s+(?P<binding>\{{[^)\n]*\}}|{_IDENTIFIER_RE})\s+"
    rf"(?P<target>{_IMPORT_TARGET_RE})",
    re.MULTILINE,
)
_PLAIN_REQUIRE_RE = re.compile(
    rf"\(\s*(?P<kind>require|require-macros)\s+(?P<target>{_IMPORT_TARGET_RE})"
)
_NAMED_DEFINITION_RE = re.compile(
    rf"^\s*\(\s*(?P<kind>fn|lambda|λ|macro|local|global)\s+(?P<name>{_IDENTIFIER_RE})\b",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    rf"\b(?P<alias>{_IDENTIFIER_RE})[.:](?P<name>{_IDENTIFIER_RE})"
)
_UNQUALIFIED_REFERENCE_RE = re.compile(rf"\(\s*(?P<name>{_IDENTIFIER_RE})\b")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "->",
        "->>",
        "-?>",
        "-?>>",
        ".",
        ":",
        "accumulate",
        "and",
        "assert",
        "case",
        "collect",
        "do",
        "doto",
        "each",
        "eval-compiler",
        "fn",
        "for",
        "global",
        "if",
        "import-macros",
        "lambda",
        "λ",
        "let",
        "local",
        "macro",
        "macrodebug",
        "match",
        "not",
        "or",
        "partial",
        "pick-args",
        "quote",
        "require",
        "require-macros",
        "set",
        "set-forcibly!",
        "tset",
        "values",
        "when",
        "while",
        "with-open",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


@dataclass(frozen=True)
class _SymbolEntry:
    name: str
    kind: str
    start_line: int


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
    for character in text:
        if in_string:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == ";":
            characters.append(" ")
            continue
        if character == "\n":
            characters.append(character)
            continue
        if character == '"':
            in_string = True
        characters.append(character)
    return "".join(characters)


def has_fennel_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in FENNEL_SUFFIXES


def is_probable_fennel_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_fennel_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    while parts and parts[0] in {"src", "fnl", "test", "tests", "spec"}:
        parts = parts[1:]
    if parts and parts[-1] == "init":
        parts = parts[:-1]
    return ".".join(part for part in parts if part)


def normalize_identifier(raw_name: str) -> str:
    normalized = str(raw_name or "").strip()
    while normalized.startswith(("'", "`", "~")):
        normalized = normalized[1:].strip()
    return normalized


def normalize_symbol_name(raw_name: str) -> str:
    return normalize_identifier(raw_name).lstrip(":")


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


def _extract_destructured_bindings(binding_text: str) -> tuple[tuple[str, str], ...]:
    binding = str(binding_text or "").strip()
    if not (binding.startswith("{") and binding.endswith("}")):
        return ()
    tokens = (
        binding[1:-1]
        .replace("{", " ")
        .replace("}", " ")
        .replace("[", " ")
        .replace("]", " ")
        .split()
    )
    bindings: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    index = 0
    while index < len(tokens):
        piece = tokens[index]
        imported_name = ""
        alias_name = ""
        if piece == ":" and index + 1 < len(tokens):
            imported_name = normalize_symbol_name(tokens[index + 1])
            index += 2
        elif piece.startswith(":") and len(piece) > 1:
            imported_name = normalize_symbol_name(piece)
            index += 1
        else:
            index += 1
            continue
        if index < len(tokens):
            following_piece = tokens[index]
            if following_piece != ":" and not following_piece.startswith(":"):
                alias_name = normalize_symbol_name(following_piece)
                index += 1
        alias_name = alias_name or imported_name
        item = (imported_name, alias_name)
        if imported_name and alias_name and item not in seen:
            seen.add(item)
            bindings.append(item)
    return tuple(bindings)


def parse_import_entries(
    text: str,
) -> tuple[tuple[str, str, str | None, tuple[tuple[str, str], ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, str | None, tuple[tuple[str, str], ...], int]] = []
    seen: set[tuple[str, str, str | None, tuple[tuple[str, str], ...], int]] = set()
    captured_targets: set[tuple[int, str, str]] = set()
    for match in _LOCAL_REQUIRE_RE.finditer(stripped_text):
        binding_text = str(match.group("binding") or "").strip()
        import_kind = str(match.group("kind") or "").strip()
        import_target = str(match.group("target") or "").strip()
        named_bindings = _extract_destructured_bindings(binding_text)
        module_alias = (
            normalize_symbol_name(binding_text)
            if binding_text and not binding_text.startswith("{")
            else None
        )
        item = (
            import_kind,
            import_target,
            module_alias or None,
            named_bindings,
            _line_number(stripped_text, match.start()),
        )
        if item not in seen:
            seen.add(item)
            entries.append(item)
        captured_targets.add((match.start(), import_kind, import_target))
    for match in _IMPORT_MACROS_RE.finditer(stripped_text):
        binding_text = str(match.group("binding") or "").strip()
        import_target = str(match.group("target") or "").strip()
        named_bindings = _extract_destructured_bindings(binding_text)
        module_alias = (
            normalize_symbol_name(binding_text)
            if binding_text and not binding_text.startswith("{")
            else None
        )
        item = (
            "import-macros",
            import_target,
            module_alias or None,
            named_bindings,
            _line_number(stripped_text, match.start()),
        )
        if item not in seen:
            seen.add(item)
            entries.append(item)
        captured_targets.add((match.start(), "import-macros", import_target))
    for match in _PLAIN_REQUIRE_RE.finditer(stripped_text):
        import_kind = str(match.group("kind") or "").strip()
        import_target = str(match.group("target") or "").strip()
        if (match.start(), import_kind, import_target) in captured_targets:
            continue
        item = (
            import_kind,
            import_target,
            None,
            (),
            _line_number(stripped_text, match.start()),
        )
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[4], item[0], item[1], item[2] or "")))


def iter_symbol_entries(text: str) -> tuple[_SymbolEntry, ...]:
    stripped_text = strip_comments(text)
    kind_map = {
        "fn": "function",
        "lambda": "function",
        "λ": "function",
        "macro": "macro",
        "local": "variable",
        "global": "variable",
    }
    entries: list[_SymbolEntry] = []
    seen_names: set[str] = set()
    for match in _NAMED_DEFINITION_RE.finditer(stripped_text):
        raw_name = normalize_symbol_name(match.group("name"))
        raw_kind = str(match.group("kind") or "").strip()
        if (
            not raw_name
            or raw_name in seen_names
            or raw_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        seen_names.add(raw_name)
        entries.append(
            _SymbolEntry(
                name=raw_name,
                kind=kind_map.get(raw_kind, "symbol"),
                start_line=_line_number(stripped_text, match.start()),
            )
        )
    return tuple(sorted(entries, key=lambda entry: (entry.start_line, entry.name, entry.kind)))
