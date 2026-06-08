from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".styl"})
_IMPORT_RE = re.compile(
    r"""(?m)^\s*@(?P<kind>import|require)\s+(?P<body>(?:["'][^"']+["']|[^\n]+))\s*$"""
)
_QUOTED_TARGET_RE = re.compile(r"""['"](?P<target>[^'"]+)['"]""")
_VARIABLE_RE = re.compile(r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\??=\s*(?P<value>.+)$")
_CALL_LINE_RE = re.compile(r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\([^)\n]*\)\s*;?\s*$")
_OWNER_CALL_RE = re.compile(
    r"^\s*(?P<owner>[A-Za-z_][A-Za-z0-9_-]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\([^)\n]*\)\s*;?\s*$"
)
_DECLARATION_SKIP_PREFIXES = ("if ", "for ", "unless ", "return ", "@")
_RESERVED_CALL_NAMES = frozenset(
    {
        "alpha",
        "calc",
        "darken",
        "embedurl",
        "hsl",
        "hsla",
        "join",
        "length",
        "lighten",
        "list",
        "lookup",
        "match",
        "max",
        "min",
        "pathjoin",
        "pop",
        "push",
        "range",
        "red",
        "remove",
        "replace",
        "rgb",
        "rgba",
        "selector",
        "selectors",
        "shift",
        "slice",
        "split",
        "s",
        "unquote",
        "url",
        "warn",
    }
)


def strip_comments(text: str) -> str:
    characters = list(text)
    index = 0
    in_string: str | None = None
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if in_string is not None:
            if current == "\\":
                index += 2
                continue
            if current == in_string:
                in_string = None
            index += 1
            continue
        if current in {'"', "'"}:
            in_string = current
            index += 1
            continue
        if current == "/" and next_char == "/":
            while index < len(characters) and characters[index] != "\n":
                characters[index] = " "
                index += 1
            continue
        if current == "/" and next_char == "*":
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            while index + 1 < len(characters):
                if characters[index] == "*" and characters[index + 1] == "/":
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


def has_stylus_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_stylus_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_stylus_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    symbol_entries = iter_symbol_entries(text)
    return bool(_IMPORT_RE.search(stripped_text) or symbol_entries or iter_reference_entries(text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    stem = path.stem.lstrip("_")
    if path.parent in {PurePosixPath("."), PurePosixPath("")}:
        return stem
    return str(path.parent / stem)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number_from_index(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


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


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def iter_import_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").strip().lower()
        body = str(match.group("body") or "").strip()
        line_number = _line_number_from_index(stripped_text, match.start())
        targets = tuple(
            str(target_match.group("target") or "").strip()
            for target_match in _QUOTED_TARGET_RE.finditer(body)
            if str(target_match.group("target") or "").strip()
        )
        if not targets and body:
            targets = (body.split()[0].strip(),)
        for target in targets:
            item = (kind, target, line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for index, line in enumerate(lines):
        line_number = index + 1
        variable_match = _VARIABLE_RE.match(line)
        if variable_match is not None:
            symbol_name = str(variable_match.group("name") or "").strip()
            item = (symbol_name, "variable", line_number)
            if symbol_name and item not in seen:
                seen.add(item)
                entries.append(item)
            continue
        call_match = _CALL_LINE_RE.match(line)
        if call_match is None:
            continue
        symbol_name = str(call_match.group("name") or "").strip()
        if (
            not symbol_name
            or any(line.lstrip().startswith(prefix) for prefix in _DECLARATION_SKIP_PREFIXES)
            or symbol_name in _RESERVED_CALL_NAMES
        ):
            continue
        current_indent = _indent_width(line)
        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1
        if next_index >= len(lines):
            continue
        next_line = lines[next_index]
        if _indent_width(next_line) <= current_indent:
            continue
        item = (symbol_name, "mixin", line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_reference_entries(text: str) -> tuple[tuple[str, str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    declaration_lines = {line_number for _name, _kind, line_number in iter_symbol_entries(text)}
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    for index, line in enumerate(stripped_text.splitlines()):
        line_number = index + 1
        if line_number in declaration_lines:
            continue
        owner_match = _OWNER_CALL_RE.match(line)
        if owner_match is not None:
            owner = str(owner_match.group("owner") or "").strip() or None
            name = str(owner_match.group("name") or "").strip()
            if owner and name:
                item = ("mixin", owner, name, line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
            continue
        call_match = _CALL_LINE_RE.match(line)
        if call_match is None:
            continue
        name = str(call_match.group("name") or "").strip()
        if (
            not name
            or any(line.lstrip().startswith(prefix) for prefix in _DECLARATION_SKIP_PREFIXES)
            or name in _RESERVED_CALL_NAMES
        ):
            continue
        item = ("mixin", None, name, line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = symbol_name
            active_line = start_line
    return active_name
