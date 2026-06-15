from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters.line_numbers import (
    line_number_for_offset,
    line_start_offsets,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_SUFFIXES = frozenset({".vim"})
_KNOWN_BASENAMES = frozenset({".vimrc", "_vimrc", "gvimrc", "vimrc"})
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:fu(?:nction)?!?|com(?:mand)?!?|aug(?:roup)?|autocmd|let|set|"
    r"call|execute|nnoremap|inoremap|vnoremap|xnoremap|cnoremap|tnoremap|"
    r"nmap|imap|vmap|xmap|omap|map|source|runtime!?|finish|if|for|while)\b"
)
_FUNCTION_RE = re.compile(
    r"(?im)^\s*fu(?:nction)?!?\s+"
    r"(?:(?P<prefix>[sgwbtlv]):)?"
    r"(?P<name>[A-Za-z0-9_#]+)"
    r"\s*\(",
)
_VALUE_RE = re.compile(
    r"(?im)^\s*let\s+"
    r"(?:(?P<prefix>[gwbtslv]):)?"
    r"(?P<name>[A-Za-z0-9_#]+)"
    r"\s*="
)
_SOURCE_RE = re.compile(
    r"(?im)^\s*(?:exe(?:cute)?\s+)?(?P<cmd>source|runtime!?)(?:\s+|!)(?P<target>[^\"'\n|]+)"
)
_CALL_RE = re.compile(
    r"(?<![A-Za-z0-9_#])(?P<name>(?:[sgwbtlv]:)?[A-Za-z0-9_#]+)\s*\(",
)
_AUTLOAD_CALL_RE = re.compile(r"(?<![A-Za-z0-9_#])(?P<name>[A-Za-z0-9_]+(?:#[A-Za-z0-9_]+)+)\s*\(")
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "append",
        "call",
        "cclose",
        "confirm",
        "copy",
        "deepcopy",
        "delete",
        "empty",
        "escape",
        "eval",
        "execute",
        "expand",
        "exists",
        "extend",
        "filter",
        "finish",
        "function",
        "get",
        "getline",
        "has",
        "index",
        "input",
        "join",
        "keys",
        "len",
        "map",
        "match",
        "printf",
        "range",
        "remove",
        "repeat",
        "resolve",
        "reverse",
        "search",
        "setline",
        "sort",
        "source",
        "split",
        "string",
        "substitute",
        "trim",
        "type",
        "values",
    }
)


def _strip_comments_uncached(text: str) -> str:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line
        escaped = False
        quote_open = False
        for index, character in enumerate(line):
            if character == "\\" and not escaped:
                escaped = True
                continue
            if character == '"' and not escaped:
                quote_open = not quote_open
                if not quote_open:
                    continue
            if character == '"' and not quote_open:
                line = line[:index]
                break
            escaped = False
        lines.append(line.rstrip())
    return "\n".join(lines)


@lru_cache(maxsize=512)
def strip_comments(text: str) -> str:
    return _strip_comments_uncached(text)


def has_vimscript_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in _KNOWN_SUFFIXES
        or normalized_path.name.lower() in _KNOWN_BASENAMES
    )


def is_probable_vimscript_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_vimscript_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_MARKER_RE.search(stripped_text))


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def _line_number(
    text: str,
    offset: int,
    *,
    starts: tuple[int, ...] | None = None,
) -> int:
    return line_number_for_offset(text, offset, starts=starts)


def _coerce_stripped_text(text: str, stripped_text: str | None = None) -> str:
    return strip_comments(text) if stripped_text is None else stripped_text


def module_name_from_path(path: str) -> str:
    normalized_path = PurePosixPath(path)
    if normalized_path.name.lower() in _KNOWN_BASENAMES:
        return normalized_path.name.lower().lstrip(".")
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if "autoload" in parts:
        autoload_index = parts.index("autoload")
        autoload_parts = parts[autoload_index + 1 :]
        if autoload_parts:
            return "#".join(autoload_parts)
    return ".".join(parts)


def autoload_target_for_name(function_name: str) -> str | None:
    normalized_name = normalize_identifier(function_name)
    if "#" not in normalized_name:
        return None
    name_parts = [part for part in normalized_name.split("#") if part]
    if len(name_parts) < 2:
        return None
    return f"autoload/{'/'.join(name_parts[:-1])}.vim"


def iter_source_statements(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _SOURCE_RE.finditer(stripped_text):
        target = normalize_identifier(str(match.group("target") or "").strip())
        if not target:
            continue
        target = target.split()[0].strip("'\"")
        if not target:
            continue
        line_number = _line_number(stripped_text, match.start("cmd"), starts=starts)
        key = (target, line_number)
        if key in seen:
            continue
        seen.add(key)
        statements.append(key)
    return tuple(statements)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _FUNCTION_RE.finditer(stripped_text):
        prefix = normalize_identifier(str(match.group("prefix") or ""))
        name = normalize_identifier(str(match.group("name") or ""))
        if prefix:
            name = f"{prefix}:{name}"
        if not name:
            continue
        line_number = _line_number(stripped_text, match.start("name"), starts=starts)
        item = (name, "function", line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    for match in _VALUE_RE.finditer(stripped_text):
        prefix = normalize_identifier(str(match.group("prefix") or ""))
        name = normalize_identifier(str(match.group("name") or ""))
        if prefix:
            name = f"{prefix}:{name}"
        if not name:
            continue
        line_number = _line_number(stripped_text, match.start("name"), starts=starts)
        item = (name, "value", line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_reference_names(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    references: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _CALL_RE.finditer(stripped_text):
        name = normalize_identifier(str(match.group("name") or ""))
        if not name:
            continue
        bare_name = name.split(":", 1)[-1]
        if bare_name.casefold() in _RESERVED_REFERENCE_NAMES:
            continue
        line_number = _line_number(stripped_text, match.start("name"), starts=starts)
        item = (name, line_number)
        if item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(references)
