from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

VCL_SUFFIXES = frozenset({".vcl"})
_COMMENT_LINE_RE = re.compile(r"//.*?$|#.*?$", re.MULTILINE)
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_SOURCE_MARKER_RE = re.compile(
    r"(?m)^\s*(?:vcl\s+\d+\.\d+\s*;|backend\s+[A-Za-z_][\w.-]*\s*\{|sub\s+[A-Za-z_][\w.-]*\s*\{|acl\s+[A-Za-z_][\w.-]*\s*\{|probe\s+[A-Za-z_][\w.-]*\s*\{|import\s+[A-Za-z_][\w.-]*\s*;)"
)
_SYMBOL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("backend", re.compile(r"(?m)^\s*backend\s+(?P<name>[A-Za-z_][\w.-]*)\s*\{")),
    ("sub", re.compile(r"(?m)^\s*sub\s+(?P<name>[A-Za-z_][\w.-]*)\s*\{")),
    ("acl", re.compile(r"(?m)^\s*acl\s+(?P<name>[A-Za-z_][\w.-]*)\s*\{")),
    ("probe", re.compile(r"(?m)^\s*probe\s+(?P<name>[A-Za-z_][\w.-]*)\s*\{")),
)
_INCLUDE_RE = re.compile(r'(?m)^\s*include\s+"(?P<target>[^"\r\n]+)"\s*;')
_CALL_RE = re.compile(r"(?m)\bcall\s+(?P<name>[A-Za-z_][\w.-]*)\s*;")
_BACKEND_REF_RE = re.compile(
    r"(?m)\b(?:req\.backend_hint|bereq\.backend)\s*=\s*(?P<name>[A-Za-z_][\w.-]*)\s*;"
)
_PROBE_REF_RE = re.compile(r"(?m)\.probe\s*=\s*(?P<name>[A-Za-z_][\w.-]*)\s*;")


def _preserve_line_count(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_comments(text: str) -> str:
    without_blocks = _COMMENT_BLOCK_RE.sub(_preserve_line_count, text)
    return _COMMENT_LINE_RE.sub("", without_blocks)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_vcl_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in VCL_SUFFIXES


def is_probable_vcl_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_vcl_path_hints(path) or not text:
        return False
    return bool(_SOURCE_MARKER_RE.search(strip_comments(text)))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    return normalized_path.with_suffix("").name


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[tuple[str, str]] = set()
    for symbol_kind, pattern in _SYMBOL_PATTERNS:
        for match in pattern.finditer(stripped_text):
            symbol_name = normalize_identifier(match.group("name") or "")
            key = (symbol_kind, symbol_name)
            if not symbol_name or key in seen_names:
                continue
            seen_names.add(key)
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(entries)


def iter_dependency_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            normalize_identifier(match.group("target") or ""),
            _line_number(stripped_text, match.start()),
        )
        for match in _INCLUDE_RE.finditer(stripped_text)
        if normalize_identifier(match.group("target") or "")
    )


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for pattern in (_CALL_RE, _BACKEND_REF_RE, _PROBE_REF_RE):
        for match in pattern.finditer(stripped_text):
            symbol_name = normalize_identifier(match.group("name") or "")
            if not symbol_name or symbol_name not in local_symbol_names:
                continue
            entry = (symbol_name, _line_number(stripped_text, match.start()))
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
    text: str | None = None,
) -> set[str]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in VCL_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        module_name_from_path(file_path),
    }
    if text:
        aliases.update(name for name, _kind, _line in iter_symbol_entries(text))
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[Any, ...]:
    from apps.api_server.services.repository_intelligence_contracts import _Symbol

    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "vcl"},
            ),
            symbol_name=module_name,
            symbol_kind="vcl",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"vcl {module_name}",
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
