from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

WREN_SUFFIXES = frozenset({".wren"})
_IMPORT_RE = re.compile(
    r'^\s*import\s+"(?P<target>[^"]+)"(?:\s+for\s+(?P<symbols>\*|[A-Za-z_][A-Za-z0-9_, ]*))?',
    re.MULTILINE,
)
_CLASS_RE = re.compile(
    r"^\s*(?P<kind>foreign\s+class|class)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_VAR_RE = re.compile(r"^\s*var\s+(?P<name>[a-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
_METHOD_RE = re.compile(
    r"^(?:(?P<static>static)\s+)?(?:(?P<foreign>foreign)\s+)?"
    r"(?:(?P<construct>construct)\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*(?:\([^)]*\))?\s*(?:\{|$)"
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_UNQUALIFIED_REFERENCE_RE = re.compile(
    r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_MARKER_RE = re.compile(r"\b(?:import|class|foreign\s+class|var)\b")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "as",
        "break",
        "class",
        "construct",
        "continue",
        "else",
        "false",
        "for",
        "foreign",
        "if",
        "import",
        "in",
        "is",
        "null",
        "return",
        "static",
        "super",
        "this",
        "true",
        "var",
        "while",
    }
)


@dataclass(frozen=True)
class _SymbolEntry:
    name: str
    kind: str
    start_line: int
    end_line: int
    parent_name: str | None
    qualified_names: tuple[str, ...]


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


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


def strip_comments(text: str) -> str:
    characters: list[str] = []
    in_string = False
    escaped = False
    block_depth = 0
    index = 0
    while index < len(text):
        character = text[index]
        next_two = text[index : index + 2]
        if block_depth:
            if next_two == "/*":
                block_depth += 1
                characters.extend("  ")
                index += 2
                continue
            if next_two == "*/":
                block_depth -= 1
                characters.extend("  ")
                index += 2
                continue
            characters.append("\n" if character == "\n" else " ")
            index += 1
            continue
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
        if next_two == "//":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        if next_two == "/*":
            block_depth = 1
            characters.extend("  ")
            index += 2
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters)


def has_wren_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in WREN_SUFFIXES


def is_probable_wren_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_wren_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] in {"src", "test", "tests", "example", "examples"}:
        parts = parts[1:]
    if parts and parts[-1] in {"main", "module"}:
        parts = parts[:-1] or parts
    return "/".join(part for part in parts if part)


def parse_import_entries(text: str) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, tuple[str, ...], int]] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        if not target:
            continue
        raw_symbols = str(match.group("symbols") or "").strip()
        symbols: tuple[str, ...] = ()
        if raw_symbols and raw_symbols != "*":
            parsed_symbols = [
                part.strip()
                for part in raw_symbols.split(",")
                if part.strip() and part.strip() not in _RESERVED_SYMBOL_NAMES
            ]
            symbols = tuple(dict.fromkeys(parsed_symbols))
        item = (target, symbols, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def _find_matching_brace(text: str, start_index: int) -> int | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start_index, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character == "{":
            depth += 1
            continue
        if character == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _iter_class_methods(
    *,
    class_name: str,
    module_name: str,
    body_text: str,
    body_start_line: int,
) -> tuple[_SymbolEntry, ...]:
    entries: list[_SymbolEntry] = []
    lines = body_text.splitlines()
    index = 0
    while index < len(lines):
        stripped_line = lines[index].strip()
        match = _METHOD_RE.match(stripped_line)
        if match is None:
            index += 1
            continue
        method_name = str(match.group("name") or "").strip()
        if not method_name or method_name in _RESERVED_SYMBOL_NAMES:
            index += 1
            continue
        start_line = body_start_line + index
        line_delta = stripped_line.count("{") - stripped_line.count("}")
        end_line = start_line
        if line_delta > 0:
            depth = line_delta
            scan_index = index + 1
            while scan_index < len(lines):
                depth += lines[scan_index].count("{") - lines[scan_index].count("}")
                if depth <= 0:
                    end_line = body_start_line + scan_index
                    index = scan_index
                    break
                scan_index += 1
            else:
                end_line = body_start_line + len(lines) - 1
                index = len(lines) - 1
        kind = "constructor" if match.group("construct") else "method"
        entries.append(
            _SymbolEntry(
                name=method_name,
                kind=kind,
                start_line=start_line,
                end_line=end_line,
                parent_name=class_name,
                qualified_names=_ordered_names(
                    method_name,
                    f"{class_name}.{method_name}",
                    f"{module_name.replace('/', '.')}.{class_name}.{method_name}"
                    if module_name
                    else "",
                ),
            )
        )
        index += 1
    return tuple(entries)


def iter_symbol_entries(file_path: str, text: str) -> tuple[_SymbolEntry, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    entries: list[_SymbolEntry] = []
    class_spans: list[tuple[int, int]] = []
    for match in _CLASS_RE.finditer(stripped_text):
        class_name = str(match.group("name") or "").strip()
        if not class_name:
            continue
        start_line = _line_number(stripped_text, match.start())
        brace_start = stripped_text.find("{", match.end())
        brace_end = _find_matching_brace(stripped_text, brace_start) if brace_start >= 0 else None
        end_line = _line_number(stripped_text, brace_end) if brace_end is not None else start_line
        entries.append(
            _SymbolEntry(
                name=class_name,
                kind="class",
                start_line=start_line,
                end_line=end_line,
                parent_name=None,
                qualified_names=_ordered_names(
                    class_name,
                    f"{module_name.replace('/', '.')}.{class_name}" if module_name else "",
                ),
            )
        )
        if brace_start >= 0 and brace_end is not None:
            class_spans.append((match.start(), brace_end))
            body_text = stripped_text[brace_start + 1 : brace_end]
            body_start_line = _line_number(stripped_text, brace_start)
            entries.extend(
                _iter_class_methods(
                    class_name=class_name,
                    module_name=module_name,
                    body_text=body_text,
                    body_start_line=body_start_line,
                )
            )
    for match in _VAR_RE.finditer(stripped_text):
        if any(start < match.start() < end for start, end in class_spans):
            continue
        variable_name = str(match.group("name") or "").strip()
        if not variable_name or variable_name in _RESERVED_SYMBOL_NAMES:
            continue
        start_line = _line_number(stripped_text, match.start())
        entries.append(
            _SymbolEntry(
                name=variable_name,
                kind="variable",
                start_line=start_line,
                end_line=start_line,
                parent_name=None,
                qualified_names=_ordered_names(
                    variable_name,
                    f"{module_name.replace('/', '.')}.{variable_name}" if module_name else "",
                ),
            )
        )
    return tuple(sorted(entries, key=lambda item: (item.start_line, item.end_line, item.name)))
