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

HY_SUFFIXES = frozenset({".hy"})
_MARKER_RE = re.compile(
    r"\(\s*(?:import|require|defn!?|\bdefn\+|defmacro!?|defclass|defreader|setv)\b",
    re.IGNORECASE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_.-]*)[./](?P<name>[A-Za-z_][A-Za-z0-9_?!*+\-<>/=.]*)"
)
_UNQUALIFIED_REFERENCE_RE = re.compile(
    r"\(\s*(?P<name>[A-Za-z_][A-Za-z0-9_?!*+\-<>/=.]*)\b"
)
_DEFINITION_HEAD_KINDS = {
    "defclass": "class",
    "defmacro": "macro",
    "defmacro!": "macro",
    "defn": "function",
    "defn!": "function",
    "defn+": "function",
    "defreader": "macro",
}
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "%",
        "*",
        "+",
        "+=",
        "->",
        "->>",
        ".",
        "/",
        "<",
        "<=",
        "=",
        ">",
        ">=",
        "and",
        "as->",
        "cond",
        "defclass",
        "defmacro",
        "defmacro!",
        "defmain",
        "defn",
        "defn!",
        "defn+",
        "defreader",
        "do",
        "eval-and-compile",
        "fn",
        "for",
        "if",
        "import",
        "is",
        "isinstance",
        "let",
        "not",
        "or",
        "quote",
        "quasiquote",
        "raise",
        "require",
        "setv",
        "unquote",
        "when",
        "with",
    }
)
_OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
_CLOSING_DELIMITERS = frozenset(_OPEN_TO_CLOSE.values())


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


def has_hy_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in HY_SUFFIXES


def is_probable_hy_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_hy_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


def normalize_identifier(raw_name: str) -> str:
    normalized = str(raw_name or "").strip()
    while normalized.startswith(("'", "`", "~")):
        normalized = normalized[1:].strip()
    return normalized


def normalize_symbol_name(raw_name: str) -> str:
    return normalize_identifier(raw_name)


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] in {"src", "test", "tests"}:
        parts = parts[1:]
    if parts and parts[-1] in {"__init__", "hy_init"}:
        parts = parts[:-1]
    return ".".join(part for part in parts if part)


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


def _tokenize_form(form_text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    index = 0
    while index < len(form_text):
        character = form_text[index]
        if character.isspace():
            index += 1
            continue
        if character in _OPEN_TO_CLOSE or character in _CLOSING_DELIMITERS:
            tokens.append(character)
            index += 1
            continue
        if character == '"':
            end_index = index + 1
            escaped = False
            while end_index < len(form_text):
                next_character = form_text[end_index]
                if escaped:
                    escaped = False
                elif next_character == "\\":
                    escaped = True
                elif next_character == '"':
                    end_index += 1
                    break
                end_index += 1
            tokens.append(form_text[index:end_index])
            index = end_index
            continue
        end_index = index
        while (
            end_index < len(form_text)
            and not form_text[end_index].isspace()
            and form_text[end_index] not in _OPEN_TO_CLOSE
            and form_text[end_index] not in _CLOSING_DELIMITERS
        ):
            end_index += 1
        tokens.append(form_text[index:end_index])
        index = end_index
    return tuple(tokens)


def _parse_form(form_text: str) -> Any:
    tokens = _tokenize_form(form_text)
    position = 0

    def _parse_expression() -> Any:
        nonlocal position
        if position >= len(tokens):
            return None
        lexeme = tokens[position]
        position += 1
        if lexeme in _OPEN_TO_CLOSE:
            expected_close = _OPEN_TO_CLOSE[lexeme]
            values: list[Any] = []
            while position < len(tokens) and tokens[position] != expected_close:
                value = _parse_expression()
                if value is not None:
                    values.append(value)
            if position < len(tokens) and tokens[position] == expected_close:
                position += 1
            return values
        if lexeme in _CLOSING_DELIMITERS:
            return None
        return lexeme

    return _parse_expression()


def _extract_top_level_forms(text: str) -> tuple[tuple[int, str], ...]:
    forms: list[tuple[int, str]] = []
    stripped_text = strip_comments(text)
    depth = 0
    start_index: int | None = None
    start_line = 1
    line_no = 1
    in_string = False
    escaped = False
    for index, character in enumerate(stripped_text):
        if character == "\n":
            line_no += 1
        if in_string:
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character in _OPEN_TO_CLOSE:
            if depth == 0 and character == "(":
                start_index = index
                start_line = line_no
            depth += 1
            continue
        if character not in _CLOSING_DELIMITERS or depth <= 0:
            continue
        depth -= 1
        if depth == 0 and start_index is not None:
            forms.append((start_line, stripped_text[start_index : index + 1].strip()))
            start_index = None
    return tuple(forms)


def _form_head(parsed_form: Any) -> str:
    if not isinstance(parsed_form, list) or not parsed_form:
        return ""
    head = parsed_form[0]
    if not isinstance(head, str):
        return ""
    return normalize_identifier(head)


def _iter_name_bindings(values: list[Any]) -> tuple[tuple[str, str | None], ...]:
    bindings: list[tuple[str, str | None]] = []
    pending_alias_index: int | None = None
    index = 0
    while index < len(values):
        value = values[index]
        if isinstance(value, list):
            index += 1
            continue
        atom = normalize_identifier(str(value))
        if not atom:
            index += 1
            continue
        if atom == ":as" and pending_alias_index is not None and index + 1 < len(values):
            alias = normalize_identifier(str(values[index + 1]))
            if alias:
                name, _previous = bindings[pending_alias_index]
                bindings[pending_alias_index] = (name, alias)
            index += 2
            pending_alias_index = None
            continue
        if atom.startswith(":"):
            pending_alias_index = None
            index += 1
            continue
        bindings.append((atom, None))
        pending_alias_index = len(bindings) - 1
        index += 1
    return tuple(bindings)


def parse_import_entries(text: str) -> tuple[tuple[str, str, str | None, tuple[tuple[str, str | None], ...], int], ...]:
    entries: list[tuple[str, str, str | None, tuple[tuple[str, str | None], ...], int]] = []
    for line_number, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        head = _form_head(parsed_form)
        if head not in {"import", "require"} or not isinstance(parsed_form, list):
            continue
        items = list(parsed_form[1:])
        index = 0
        while index < len(items):
            candidate = items[index]
            if isinstance(candidate, list):
                index += 1
                continue
            module_name = normalize_identifier(str(candidate))
            if not module_name or module_name.startswith(":"):
                index += 1
                continue
            module_alias: str | None = None
            imported_names: tuple[tuple[str, str | None], ...] = ()
            cursor = index + 1
            while cursor < len(items):
                follower = items[cursor]
                if isinstance(follower, list):
                    imported_names = _iter_name_bindings(follower)
                    cursor += 1
                    continue
                follower_atom = normalize_identifier(str(follower))
                if not follower_atom:
                    cursor += 1
                    continue
                if follower_atom == ":as" and cursor + 1 < len(items):
                    module_alias = normalize_identifier(str(items[cursor + 1])) or None
                    cursor += 2
                    continue
                if follower_atom in {"*", ":macros", ":readers"}:
                    if follower_atom == "*" and not imported_names:
                        imported_names = (("*", None),)
                    cursor += 1
                    continue
                if not follower_atom.startswith(":"):
                    break
                cursor += 1
            entries.append((head, module_name, module_alias, imported_names, line_number))
            index = cursor
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for line_number, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        head = _form_head(parsed_form)
        if head in _DEFINITION_HEAD_KINDS and isinstance(parsed_form, list) and len(parsed_form) >= 2:
            symbol_name = normalize_symbol_name(str(parsed_form[1]))
            if symbol_name and symbol_name not in _RESERVED_SYMBOL_NAMES:
                entry = (symbol_name, _DEFINITION_HEAD_KINDS[head], line_number)
                if entry not in seen_entries:
                    seen_entries.add(entry)
                    entries.append(entry)
            continue
        if head == "setv" and isinstance(parsed_form, list):
            values = parsed_form[1:]
            for index in range(0, len(values), 2):
                if index >= len(values):
                    break
                raw_name = values[index]
                if isinstance(raw_name, list):
                    continue
                symbol_name = normalize_symbol_name(str(raw_name))
                if not symbol_name or symbol_name.startswith(":") or symbol_name in _RESERVED_SYMBOL_NAMES:
                    continue
                entry = (symbol_name, "variable", line_number)
                if entry not in seen_entries:
                    seen_entries.add(entry)
                    entries.append(entry)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))
