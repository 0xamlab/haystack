from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

J_SUFFIXES = frozenset({".ijs", ".ijt"})
_COMMON_MODULE_ROOTS = frozenset({"app", "demo", "extra", "guest", "page", "react", "src", "test"})
_LINE_COMMENT_RE = re.compile(r"(?m)^\s*NB\..*$")
_PROBABLE_SOURCE_RE = re.compile(
    r"(?m)^\s*(?:NB\.|[A-Za-z][A-Za-z0-9_]*\s*=:\s*|coclass\s+|cocurrent\s+|require\s+)"
)
_SYMBOL_RE = re.compile(r"(?m)^\s*(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*=:\s*")
_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*\b")


def strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_j_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in J_SUFFIXES


def is_probable_j_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_j_path_hints(path) or not text:
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _PROBABLE_SOURCE_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.stem


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    del text
    return ()


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _SYMBOL_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "definition", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        if _SYMBOL_RE.match(raw_line):
            continue
        for match in _TOKEN_RE.finditer(raw_line):
            name = normalize_identifier(match.group(0) or "")
            if not name or name not in local_symbol_names:
                continue
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
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in J_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for symbol_name, _kind, _line in iter_symbol_entries(text):
        aliases.add(symbol_name)
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "j"},
            ),
            symbol_name=module_name,
            symbol_kind="j",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"j {module_name}",
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
