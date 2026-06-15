from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

TEMPL_SUFFIXES = frozenset({".templ"})
_DECL_RE = re.compile(
    r"(?m)^\s*(?P<kind>templ|css|script)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_REF_RE = re.compile(r"@(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\.[A-Za-z_][A-Za-z0-9_]*)?\s*\(")
_SOURCE_MARKER_RE = re.compile(r"(?m)^\s*(?:templ|css|script)\s+[A-Za-z_][A-Za-z0-9_]*\s*\(")


def strip_comments(text: str) -> str:
    return text


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_templ_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in TEMPL_SUFFIXES


def is_probable_templ_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_templ_path_hints(path) or not text:
        return False
    return bool(_SOURCE_MARKER_RE.search(text))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    return normalized_path.with_suffix("").name


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    del text
    return ()


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _DECL_RE.finditer(text):
        name = normalize_identifier(match.group("name") or "")
        kind = normalize_identifier(match.group("kind") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, kind, text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for match in _REF_RE.finditer(text):
        raw_name = normalize_identifier(match.group("name") or "")
        if not raw_name or raw_name in {"templ"} or raw_name not in local_symbol_names:
            continue
        entry = (raw_name, text.count("\n", 0, match.start()) + 1)
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
    if normalized_path.suffix.lower() not in TEMPL_SUFFIXES:
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "templ"},
            ),
            symbol_name=module_name,
            symbol_kind="templ",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"templ {module_name}",
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
