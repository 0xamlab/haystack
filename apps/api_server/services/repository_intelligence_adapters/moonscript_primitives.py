from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

MOONSCRIPT_SUFFIXES = frozenset({".moon"})
_CLASS_RE = re.compile(
    r"(?m)^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+(?P<extends>[A-Za-z_][A-Za-z0-9_$.]*))?"
)
_FUNCTION_RE = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:[:=])\s*(?:\([^)\n]*\)\s*)?(?P<arrow>->|=>)(?=\s|$)"
)
_IMPORT_FROM_REQUIRE_RE = re.compile(
    r"(?m)^\s*import\s+.+?\s+from\s+require\s+['\"](?P<target>[^'\"]+)['\"]"
)
_REQUIRE_ASSIGN_RE = re.compile(
    r"(?m)^\s*(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*require\s+['\"](?P<target>[^'\"]+)['\"]"
)
_REQUIRE_SIDE_EFFECT_RE = re.compile(r"(?m)^\s*require\s+['\"](?P<target>[^'\"]+)['\"]")


def strip_comments(text: str) -> str:
    lines: list[str] = []
    in_block_comment = False
    for raw_line in text.splitlines():
        line = raw_line
        if in_block_comment:
            end_index = line.find("]]")
            if end_index == -1:
                lines.append("")
                continue
            line = line[end_index + 2 :]
            in_block_comment = False
        start_index = line.find("--[[")
        if start_index != -1:
            end_index = line.find("]]", start_index + 4)
            if end_index == -1:
                in_block_comment = True
                line = line[:start_index]
            else:
                line = line[:start_index] + line[end_index + 2 :]
        comment_index = line.find("--")
        if comment_index != -1:
            line = line[:comment_index]
        lines.append(line)
    return "\n".join(lines)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_moonscript_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in MOONSCRIPT_SUFFIXES


def is_probable_moonscript_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_moonscript_path_hints(path) or not text:
        return False
    stripped_text = strip_comments(text)
    return any(
        marker in stripped_text
        for marker in ("->", "=>", "class ", "import ", "require ", "local *")
    )


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    return normalized_path.with_suffix("").name


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for pattern in (_IMPORT_FROM_REQUIRE_RE, _REQUIRE_ASSIGN_RE, _REQUIRE_SIDE_EFFECT_RE):
        for match in pattern.finditer(stripped_text):
            target = normalize_identifier(match.group("target") or "")
            if not target:
                continue
            entry = (target, "imports", stripped_text.count("\n", 0, match.start()) + 1)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _CLASS_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "class", stripped_text.count("\n", 0, match.start()) + 1))
    for match in _FUNCTION_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "function", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for match in _CLASS_RE.finditer(stripped_text):
        target_name = normalize_identifier(match.group("extends") or "")
        if not target_name or target_name not in local_symbol_names:
            continue
        entry = (target_name, stripped_text.count("\n", 0, match.start()) + 1)
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in MOONSCRIPT_SUFFIXES:
        return set()
    aliases = {
        file_path,
        file_path.lower(),
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        module_name_from_path(file_path),
    }
    aliases.update(alias.lower() for alias in tuple(aliases))
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "moonscript"},
            ),
            symbol_name=module_name,
            symbol_kind="moonscript",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"moonscript {module_name}",
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": symbol_name, "kind": symbol_kind},
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    best_name: str | None = None
    best_line = -1
    for name, _kind, symbol_line in symbol_entries:
        if symbol_line <= line_number and symbol_line >= best_line:
            best_name = name
            best_line = symbol_line
    return best_name
