from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

_KNOWN_SUFFIXES = frozenset({".robot", ".resource"})
_SECTION_RE = re.compile(r"^\s*\*{3}\s*(?P<name>[A-Za-z ]+?)\s*\*{3}\s*$", re.MULTILINE)
_SEPARATOR_RE = re.compile(r"(?:\s{2,}|\t+)")
_RESOURCE_SETTINGS = frozenset({"resource", "variables", "library"})
_KEYWORD_SETTINGS = frozenset(
    {
        "suite setup",
        "suite teardown",
        "test setup",
        "test teardown",
        "task setup",
        "task teardown",
        "setup",
        "teardown",
        "template",
        "test template",
        "[setup]",
        "[teardown]",
        "[template]",
    }
)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.lstrip()
        if stripped.startswith("#"):
            continue
        comment_index = raw_line.find("  #")
        lines.append(raw_line[:comment_index] if comment_index >= 0 else raw_line)
    return "\n".join(lines)


def has_robotframework_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_robotframework_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_robotframework_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and _SECTION_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    return str(path.with_suffix(""))


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number_from_index(text: str, offset: int) -> int:
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


def _split_cells(raw_line: str) -> tuple[str, ...]:
    stripped = raw_line.strip()
    if not stripped:
        return ()
    return tuple(cell.strip() for cell in _SEPARATOR_RE.split(stripped) if cell.strip())


def _normalize_section_name(raw_name: str) -> str:
    return " ".join(str(raw_name or "").strip().lower().split())


def iter_section_entries(text: str) -> tuple[tuple[str, int, int, tuple[str, ...]], ...]:
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines()
    entries: list[tuple[str, int, int, tuple[str, ...]]] = []
    current_section = ""
    current_start = 1
    current_lines: list[str] = []
    for line_number, raw_line in enumerate(lines, start=1):
        match = _SECTION_RE.match(raw_line)
        if match is not None:
            if current_section:
                entries.append((current_section, current_start, line_number - 1, tuple(current_lines)))
            current_section = _normalize_section_name(match.group("name"))
            current_start = line_number + 1
            current_lines = []
            continue
        if current_section:
            current_lines.append(raw_line)
    if current_section:
        entries.append((current_section, current_start, max(current_start, len(lines)), tuple(current_lines)))
    return tuple(entries)


def _iter_setting_cells(text: str) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    entries: list[tuple[str, tuple[str, ...], int]] = []
    for section_name, start_line, _end_line, section_lines in iter_section_entries(text):
        if section_name != "settings":
            continue
        for offset, raw_line in enumerate(section_lines):
            cells = _split_cells(raw_line)
            if len(cells) < 2:
                continue
            entries.append((cells[0].strip().lower(), cells, start_line + offset))
    return tuple(entries)


def iter_resource_imports(text: str) -> tuple[tuple[str, str, int], ...]:
    imports: list[tuple[str, str, int]] = []
    for setting_name, cells, line_number in _iter_setting_cells(text):
        if setting_name not in _RESOURCE_SETTINGS:
            continue
        imports.append((setting_name, cells[1], line_number))
    return tuple(imports)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for section_name, start_line, _end_line, section_lines in iter_section_entries(text):
        if section_name not in {"test cases", "tasks", "keywords"}:
            continue
        current_kind = "keyword" if section_name == "keywords" else "test"
        for offset, raw_line in enumerate(section_lines):
            if raw_line[:1].isspace():
                continue
            cells = _split_cells(raw_line)
            if not cells:
                continue
            item = (cells[0], current_kind, start_line + offset)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def iter_keyword_call_entries(text: str) -> tuple[tuple[str, int], ...]:
    calls: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for setting_name, cells, line_number in _iter_setting_cells(text):
        if setting_name in _KEYWORD_SETTINGS and len(cells) >= 2:
            item = (cells[1], line_number)
            if item not in seen:
                seen.add(item)
                calls.append(item)
    for section_name, start_line, _end_line, section_lines in iter_section_entries(text):
        if section_name not in {"test cases", "tasks", "keywords"}:
            continue
        for offset, raw_line in enumerate(section_lines):
            if not raw_line[:1].isspace():
                continue
            cells = _split_cells(raw_line)
            if not cells or cells[0] == "...":
                continue
            if cells[0].lower() in _KEYWORD_SETTINGS and len(cells) >= 2:
                item = (cells[1], start_line + offset)
            else:
                item = (cells[0], start_line + offset)
            if item not in seen:
                seen.add(item)
                calls.append(item)
    return tuple(calls)


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
