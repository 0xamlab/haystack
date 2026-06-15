from __future__ import annotations

import bisect
import re
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".scss"})
_IMPORT_RE = re.compile(r"@(?P<kind>use|forward|import)\s+(?P<body>[^;]+);")
_QUOTED_TARGET_RE = re.compile(r"""['"](?P<target>[^'"]+)['"]""")
_ALIAS_RE = re.compile(r"\bas\s+(?P<alias>\*|[A-Za-z_][A-Za-z0-9_-]*)\b")
_VARIABLE_RE = re.compile(r"(?m)^\s*\$(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*:")
_MIXIN_RE = re.compile(r"(?m)^\s*@mixin\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_FUNCTION_RE = re.compile(r"(?m)^\s*@function\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_PLACEHOLDER_RE = re.compile(r"(?m)^\s*%(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_INCLUDE_RE = re.compile(
    r"@include\s+(?:(?P<owner>[A-Za-z_][A-Za-z0-9_-]*)\.)?(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_QUALIFIED_FUNCTION_RE = re.compile(
    r"(?<![@$%.-])(?P<owner>[A-Za-z_][A-Za-z0-9_-]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\("
)
_FUNCTION_CALL_RE = re.compile(
    r"(?<![@$%.-])(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\("
)
_EXTEND_RE = re.compile(
    r"@extend\s+(?:(?P<owner>[A-Za-z_][A-Za-z0-9_-]*)\.)?%(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_VARIABLE_REF_RE = re.compile(r"(?<![#\w-])\$(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_DECLARATION_LINE_RE = re.compile(r"(?m)^\\s*[$%@]")
_RESERVED_CALL_NAMES = frozenset(
    {
        "and",
        "calc",
        "clamp",
        "color",
        "env",
        "hsl",
        "hsla",
        "if",
        "max",
        "min",
        "not",
        "or",
        "rgb",
        "rgba",
        "url",
        "var",
    }
)


def _coerce_stripped_text(text: str, stripped_text: str | None = None) -> str:
    return strip_comments(text) if stripped_text is None else stripped_text


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    if "//" not in text and "/*" not in text:
        return text
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


def strip_comments(text: str) -> str:
    return _strip_comments_cached(text)


def has_scss_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_scss_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_scss_path_hints(normalized_path):
        return False
    stripped_text = _coerce_stripped_text(text, stripped_text)
    if not stripped_text.strip():
        return False
    return bool(
        _IMPORT_RE.search(stripped_text)
        or _VARIABLE_RE.search(stripped_text)
        or _MIXIN_RE.search(stripped_text)
        or _FUNCTION_RE.search(stripped_text)
        or _PLACEHOLDER_RE.search(stripped_text)
        or "{" in stripped_text
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    stem = path.stem.lstrip("_")
    if path.parent in {PurePosixPath("."), PurePosixPath("")}:
        return stem
    return str(path.parent / stem)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _build_line_starts(text: str) -> tuple[int, ...]:
    starts = [0]
    search_start = 0
    while True:
        newline_index = text.find("\n", search_start)
        if newline_index < 0:
            break
        starts.append(newline_index + 1)
        search_start = newline_index + 1
    return tuple(starts)


@lru_cache(maxsize=256)
def _line_starts(text: str) -> tuple[int, ...]:
    return _build_line_starts(text)


def _line_number_from_index(
    text: str,
    offset: int,
    *,
    line_starts: tuple[int, ...] | None = None,
) -> int:
    if offset <= 0:
        return 1
    starts = _line_starts(text) if line_starts is None else line_starts
    return max(1, bisect.bisect_right(starts, offset))


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


def iter_import_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    line_starts = _line_starts(stripped_text) if line_starts is None else line_starts
    entries: list[tuple[str, str, str | None, int]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").strip().lower()
        body = str(match.group("body") or "")
        line_number = _line_number_from_index(
            stripped_text,
            match.start(),
            line_starts=line_starts,
        )
        alias_match = _ALIAS_RE.search(body) if kind in {"use", "forward"} else None
        alias = (
            str(alias_match.group("alias") or "").strip() or None
            if alias_match is not None
            else None
        )
        targets = tuple(
            str(target_match.group("target") or "").strip()
            for target_match in _QUOTED_TARGET_RE.finditer(body)
            if str(target_match.group("target") or "").strip()
        )
        for target in targets:
            item = (kind, target, alias, line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    line_starts = _line_starts(stripped_text) if line_starts is None else line_starts
    patterns = (
        (_VARIABLE_RE, "variable"),
        (_MIXIN_RE, "mixin"),
        (_FUNCTION_RE, "function"),
        (_PLACEHOLDER_RE, "placeholder"),
    )
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for pattern, symbol_kind in patterns:
        for match in pattern.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name:
                continue
            item = (
                symbol_name,
                symbol_kind,
                _line_number_from_index(
                    stripped_text,
                    match.start(),
                    line_starts=line_starts,
                ),
            )
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str | None, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    line_starts = _line_starts(stripped_text) if line_starts is None else line_starts
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (_INCLUDE_RE, "mixin"),
        (_QUALIFIED_FUNCTION_RE, "function"),
        (_EXTEND_RE, "placeholder"),
        (_VARIABLE_REF_RE, "variable"),
    )
    for pattern, reference_kind in patterns:
        for match in pattern.finditer(stripped_text):
            line_number = _line_number_from_index(
                stripped_text,
                match.start(),
                line_starts=line_starts,
            )
            line_start = stripped_text.rfind("\n", 0, match.start()) + 1
            line_end = stripped_text.find("\n", match.start())
            if line_end < 0:
                line_end = len(stripped_text)
            raw_line = stripped_text[line_start:line_end]
            if reference_kind in {"function", "variable"} and _DECLARATION_LINE_RE.match(raw_line):
                continue
            owner = str(match.groupdict().get("owner") or "").strip() or None
            name = str(match.group("name") or "").strip()
            if not name:
                continue
            item = (reference_kind, owner, name, line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    for match in _FUNCTION_CALL_RE.finditer(stripped_text):
        line_number = _line_number_from_index(
            stripped_text,
            match.start(),
            line_starts=line_starts,
        )
        line_start = stripped_text.rfind("\n", 0, match.start()) + 1
        line_end = stripped_text.find("\n", match.start())
        if line_end < 0:
            line_end = len(stripped_text)
        raw_line = stripped_text[line_start:line_end]
        if _DECLARATION_LINE_RE.match(raw_line):
            continue
        name = str(match.group("name") or "").strip()
        if not name or name in _RESERVED_CALL_NAMES:
            continue
        item = ("function", None, name, line_number)
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
