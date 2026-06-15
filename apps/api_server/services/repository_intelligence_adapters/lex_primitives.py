from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

LEX_SUFFIXES = frozenset({".l", ".lex"})
_COMMENT_RE = re.compile(r"(?s)/\*.*?\*/")
_MARKER_RE = re.compile(r"(?m)^\s*(?:%option|%x|%s|%%)\b")
_DEFINITION_RE = re.compile(r"(?m)^\s*(?P<name>[A-Z][A-Z0-9_]*)\s+.+$")
_REFERENCE_RE = re.compile(r"\{(?P<name>[A-Z][A-Z0-9_]*)\}")


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_lex_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in LEX_SUFFIXES


def _split_sections(text: str) -> tuple[str, str]:
    parts = strip_comments(text).split("%%", 2)
    if len(parts) < 2:
        return strip_comments(text), ""
    return parts[0], parts[1]


def is_probable_lex_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_lex_path_hints(path) or not text:
        return False
    definitions, rules = _split_sections(text)
    if "%%" not in strip_comments(text):
        return False
    return (
        _MARKER_RE.search(strip_comments(text)) is not None
        or _DEFINITION_RE.search(definitions) is not None
        or _REFERENCE_RE.search(rules) is not None
    )


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    return normalized_path.with_suffix("").name


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    del text
    return ()


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    definitions, _rules = _split_sections(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _DEFINITION_RE.finditer(definitions):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "definition", definitions.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
) -> tuple[tuple[str, int], ...]:
    _definitions, rules = _split_sections(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    rules_offset = strip_comments(text).find("%%")
    rules_base = 0 if rules_offset < 0 else rules_offset + 2
    for match in _REFERENCE_RE.finditer(rules):
        name = normalize_identifier(match.group("name") or "")
        if not name or name not in local_symbol_names:
            continue
        line_number = strip_comments(text).count("\n", 0, rules_base + match.start()) + 1
        entry = (name, line_number)
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
    if normalized_path.suffix.lower() not in LEX_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        module_name_from_path(file_path),
    }
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "lex"},
            ),
            symbol_name=module_name,
            symbol_kind="lex",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"lex {module_name}",
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
    for name, _kind, symbol_line in symbol_entries:
        if symbol_line == line_number:
            return name
    return None
