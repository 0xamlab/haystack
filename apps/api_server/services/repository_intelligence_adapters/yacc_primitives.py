from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

YACC_SUFFIXES = frozenset({".y", ".yacc"})
_COMMENT_RE = re.compile(r"(?s)/\*.*?\*/")
_MARKER_RE = re.compile(r"(?m)^\s*(?:%token|%left|%right|%nonassoc|%type|%start|%%)\b")
_RULE_BLOCK_RE = re.compile(
    r"(?ms)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*:(?P<body>.*?)(?=^\s*[A-Za-z_][A-Za-z0-9_-]*\s*:|^\s*%%|\Z)"
)
_TOKEN_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_-]*\b")


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_yacc_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in YACC_SUFFIXES


def is_probable_yacc_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_yacc_path_hints(path) or not text:
        return False
    stripped_text = strip_comments(text)
    if "%%" not in stripped_text:
        return False
    return _MARKER_RE.search(stripped_text) is not None or _RULE_BLOCK_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    return normalized_path.with_suffix("").name


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    del text
    return ()


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _RULE_BLOCK_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "rule", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for match in _RULE_BLOCK_RE.finditer(stripped_text):
        body = match.group("body") or ""
        body_start = match.start("body")
        for token_match in _TOKEN_RE.finditer(body):
            name = normalize_identifier(token_match.group(0) or "")
            if not name or name not in local_symbol_names:
                continue
            line_number = stripped_text.count("\n", 0, body_start + token_match.start()) + 1
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
    if normalized_path.suffix.lower() not in YACC_SUFFIXES:
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "yacc"},
            ),
            symbol_name=module_name,
            symbol_kind="yacc",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"yacc {module_name}",
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
