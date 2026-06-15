from __future__ import annotations

import bisect
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".scad"})
_IMPORT_RE = re.compile(
    r"^\s*(?P<kind>include|use)\s*(?:<(?P<angled>[^>]+)>|\"(?P<quoted>[^\"]+)\"|'(?P<single>[^']+)')\s*;?",
    re.IGNORECASE | re.MULTILINE,
)
_MODULE_DECL_RE = re.compile(
    r"^\s*module\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE | re.MULTILINE,
)
_FUNCTION_DECL_RE = re.compile(
    r"^\s*function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE | re.MULTILINE,
)
_CALL_RE = re.compile(r"(?<![$A-Za-z0-9_])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RESERVED_NAMES = frozenset(
    {
        "assert",
        "assign",
        "children",
        "circle",
        "color",
        "cylinder",
        "cube",
        "difference",
        "echo",
        "for",
        "function",
        "if",
        "include",
        "intersection",
        "let",
        "linear_extrude",
        "mirror",
        "module",
        "multmatrix",
        "offset",
        "polygon",
        "projection",
        "render",
        "resize",
        "rotate",
        "scale",
        "search",
        "sphere",
        "square",
        "surface",
        "translate",
        "union",
        "use",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def _normalize_import_target(value: str) -> str:
    normalized = str(value or "").strip().strip('"').strip("'")
    if not normalized:
        return ""
    return PurePosixPath(normalized.replace("\\", "/")).as_posix()


def _coerce_stripped_text(text: str, stripped_text: str | None = None) -> str:
    return strip_comments(text) if stripped_text is None else stripped_text


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


def _line_number(
    text: str,
    offset: int,
    *,
    line_starts: tuple[int, ...] | None = None,
) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    starts = _line_starts(text) if line_starts is None else line_starts
    return max(1, bisect.bisect_right(starts, bounded_offset))


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _strip_comments_preserving_lines(text: str) -> str:
    output: list[str] = []
    index = 0
    in_string: str | None = None
    escaped = False
    in_block_comment = False
    while index < len(text):
        character = text[index]
        next_two = text[index : index + 2]
        if in_block_comment:
            if next_two == "*/":
                in_block_comment = False
                index += 2
                continue
            output.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string is not None:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == in_string:
                in_string = None
            index += 1
            continue
        if next_two == "//":
            while index < len(text) and text[index] != "\n":
                output.append(" ")
                index += 1
            continue
        if next_two == "/*":
            in_block_comment = True
            output.extend([" ", " "])
            index += 2
            continue
        if character in {'"', "'"}:
            in_string = character
            output.append(character)
            index += 1
            continue
        output.append(character)
        index += 1
    return "".join(output)


@lru_cache(maxsize=512)
def strip_comments(text: str) -> str:
    if "//" not in text and "/*" not in text:
        return text
    return _strip_comments_preserving_lines(text)


def _is_keyword_boundary(character: str) -> bool:
    return not (character.isalnum() or character == "_")


def _line_starts_with_keyword(line: str, keyword: str) -> bool:
    stripped_line = line.lstrip()
    prefix = stripped_line[: len(keyword)]
    if prefix.lower() != keyword:
        return False
    if len(stripped_line) == len(keyword):
        return True
    return _is_keyword_boundary(stripped_line[len(keyword)])


@lru_cache(maxsize=512)
def _has_import_directive_prefix(stripped_text: str) -> bool:
    line_start = 0
    text_length = len(stripped_text)
    while line_start < text_length:
        line_end = stripped_text.find("\n", line_start)
        if line_end < 0:
            line_end = text_length
        line = stripped_text[line_start:line_end]
        if _line_starts_with_keyword(line, "use") or _line_starts_with_keyword(
            line,
            "include",
        ):
            return True
        if line_end >= text_length:
            break
        line_start = line_end + 1
    return False


def has_openscad_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_openscad_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if has_openscad_path_hints(path):
        return True
    stripped_text = _coerce_stripped_text(text, stripped_text)
    return bool(
        _IMPORT_RE.search(stripped_text)
        or _MODULE_DECL_RE.search(stripped_text)
        or _FUNCTION_DECL_RE.search(stripped_text)
    )


def has_import_directives(
    text: str,
    *,
    stripped_text: str | None = None,
) -> bool:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    return _has_import_directive_prefix(stripped_text)


def import_targets_for_text(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[str, ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    if not _has_import_directive_prefix(stripped_text):
        return ()
    targets: list[str] = []
    seen_targets: set[str] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        raw_target = (
            match.group("angled") or match.group("quoted") or match.group("single") or ""
        )
        normalized_target = _normalize_import_target(raw_target)
        if not normalized_target or normalized_target in seen_targets:
            continue
        seen_targets.add(normalized_target)
        targets.append(normalized_target)
    return tuple(targets)


def module_symbol_name(file_path: str) -> str:
    path = PurePosixPath(file_path)
    return _normalize_identifier(path.stem or path.name)


def _find_statement_end(
    text: str,
    start_offset: int,
    *,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[int, int]:
    line_start = text.rfind("\n", 0, start_offset) + 1
    brace_start = text.find("{", start_offset)
    semicolon_start = text.find(";", start_offset)
    if brace_start == -1 or (semicolon_start != -1 and semicolon_start < brace_start):
        if semicolon_start == -1:
            return (
                _line_number(text, start_offset, line_starts=line_starts),
                _line_count(text),
            )
        return (
            _line_number(text, start_offset, line_starts=line_starts),
            _line_number(text, semicolon_start, line_starts=line_starts),
        )
    brace_depth = 0
    in_string: str | None = None
    escaped = False
    for index in range(brace_start, len(text)):
        character = text[index]
        if in_string is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == in_string:
                in_string = None
            continue
        if character in {'"', "'"}:
            in_string = character
            continue
        if character == "{":
            brace_depth += 1
            continue
        if character == "}":
            brace_depth -= 1
            if brace_depth == 0:
                return (
                    _line_number(text, line_start, line_starts=line_starts),
                    _line_number(text, index, line_starts=line_starts),
                )
    return _line_number(text, line_start, line_starts=line_starts), _line_count(text)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_identifier(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def collect_symbol_entries(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    line_starts = _line_starts(stripped_text) if line_starts is None else line_starts
    file_symbol_name = module_symbol_name(file_path)
    entries: list[_CollectedSymbol] = []

    for match in _FUNCTION_DECL_RE.finditer(stripped_text):
        symbol_name = _normalize_identifier(match.group("name") or "")
        if not symbol_name:
            continue
        start_line = _line_number(
            stripped_text,
            match.start(),
            line_starts=line_starts,
        )
        symbol = _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {
                    "file_path": file_path,
                    "symbol_kind": "function",
                    "symbol_name": symbol_name,
                    "start_line": start_line,
                },
            ),
            symbol_name=symbol_name,
            symbol_kind="function",
            start_line=start_line,
            end_line=start_line,
            parent_symbol_id=None,
            signature=f"function {symbol_name}()",
        )
        entries.append(
            _CollectedSymbol(
                symbol=symbol,
                local_start_line=start_line,
                local_end_line=start_line,
                qualified_names=_ordered_names(symbol_name, f"{file_symbol_name}.{symbol_name}"),
            )
        )

    for match in _MODULE_DECL_RE.finditer(stripped_text):
        symbol_name = _normalize_identifier(match.group("name") or "")
        if not symbol_name:
            continue
        start_line, end_line = _find_statement_end(
            stripped_text,
            match.start(),
            line_starts=line_starts,
        )
        symbol = _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {
                    "file_path": file_path,
                    "symbol_kind": "module",
                    "symbol_name": symbol_name,
                    "start_line": start_line,
                },
            ),
            symbol_name=symbol_name,
            symbol_kind="module",
            start_line=start_line,
            end_line=end_line,
            parent_symbol_id=None,
            signature=f"module {symbol_name}()",
        )
        entries.append(
            _CollectedSymbol(
                symbol=symbol,
                local_start_line=start_line,
                local_end_line=end_line,
                qualified_names=_ordered_names(symbol_name, f"{file_symbol_name}.{symbol_name}"),
            )
        )

    return tuple(
        sorted(
            entries,
            key=lambda entry: (
                entry.local_start_line,
                entry.local_end_line,
                entry.symbol.symbol_kind,
                entry.symbol.symbol_name.lower(),
            ),
        )
    )
