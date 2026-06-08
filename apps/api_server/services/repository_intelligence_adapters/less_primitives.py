from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".less"})
_IMPORT_RE = re.compile(r"@import(?:\s+\([^)]*\))?\s+(?P<body>[^;]+);")
_QUOTED_TARGET_RE = re.compile(r"""['"](?P<target>[^'"]+)['"]""")
_VARIABLE_RE = re.compile(r"(?m)^\s*@(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*:")
_MIXIN_RE = re.compile(r"(?m)^\s*[.#](?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\([^)]*\)\s*\{")
_QUALIFIED_MIXIN_RE = re.compile(
    r"(?m)^\s*(?P<owner>[.#][A-Za-z_][A-Za-z0-9_-]*)\s*[> ]+\s*[.#](?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\("
)
_MIXIN_CALL_RE = re.compile(r"(?m)^\s*[.#](?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\([^;{]*\)\s*;")
_VARIABLE_REF_RE = re.compile(r"(?<![@\\w-])@(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_DECLARATION_LINE_RE = re.compile(r"(?m)^\s*[@.#]")
_RESERVED_VARIABLE_NAMES = frozenset({"import", "media", "supports"})


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


def has_less_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_less_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_less_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(
        _IMPORT_RE.search(stripped_text)
        or _VARIABLE_RE.search(stripped_text)
        or _MIXIN_RE.search(stripped_text)
        or "{" in stripped_text
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    stem = path.stem
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


def iter_import_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        body = str(match.group("body") or "")
        line_number = _line_number_from_index(stripped_text, match.start())
        for target_match in _QUOTED_TARGET_RE.finditer(body):
            target = str(target_match.group("target") or "").strip()
            if not target:
                continue
            item = (target, line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    patterns = (
        (_VARIABLE_RE, "variable"),
        (_MIXIN_RE, "mixin"),
    )
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for pattern, symbol_kind in patterns:
        for match in pattern.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name:
                continue
            item = (symbol_name, symbol_kind, _line_number_from_index(stripped_text, match.start()))
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_reference_entries(text: str) -> tuple[tuple[str, str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (_QUALIFIED_MIXIN_RE, "mixin"),
        (_MIXIN_CALL_RE, "mixin"),
        (_VARIABLE_REF_RE, "variable"),
    )
    for pattern, reference_kind in patterns:
        for match in pattern.finditer(stripped_text):
            line_number = _line_number_from_index(stripped_text, match.start())
            line_start = stripped_text.rfind("\n", 0, match.start()) + 1
            line_end = stripped_text.find("\n", match.start())
            if line_end < 0:
                line_end = len(stripped_text)
            raw_line = stripped_text[line_start:line_end]
            if reference_kind == "variable" and _DECLARATION_LINE_RE.match(raw_line):
                continue
            owner = str(match.groupdict().get("owner") or "").strip().lstrip(".#") or None
            name = str(match.group("name") or "").strip()
            if not name or (reference_kind == "variable" and name in _RESERVED_VARIABLE_NAMES):
                continue
            item = (reference_kind, owner, name, line_number)
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
