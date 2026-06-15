from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

APL_SUFFIXES = frozenset({".apl", ".aplf", ".dyalog"})
_COMMON_MODULE_ROOTS = frozenset({"docs", "documentation", "samples", "tests", "tools"})
_LINE_COMMENT_RE = re.compile(r"(?m)^\s*⍝.*$")
_TRADFN_RE = re.compile(r"(?m)^\s*∇\s*(?:\([^)]*\)\s*←\s*)?(?P<name>[A-Za-z][A-Za-z0-9_]*)")
_HEADER_ASSIGN_RE = re.compile(r"(?m)^\s*\([^)]*\)\s*←\s*(?P<name>[A-Za-z][A-Za-z0-9_]*)")
_DFN_ASSIGN_RE = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*←\s*(?:\{|⎕NS\b|⎕SE\b)"
)
_REFERENCE_RE = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9_]*)")
_PROBABLE_SOURCE_RE = re.compile(
    r"(?m)←|∇|⎕|⋄|^\s*:(?:For|If|While|Repeat|Trap|Hold|Select|With)\b|^\s*⍝"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "And",
        "Else",
        "End",
        "For",
        "If",
        "In",
        "Or",
        "Repeat",
        "Return",
        "Select",
        "Trap",
        "While",
        "With",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t\f"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", text)


def has_apl_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in APL_SUFFIXES


def is_probable_apl_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_apl_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _PROBABLE_SOURCE_RE.search(text) is not None or _PROBABLE_SOURCE_RE.search(
        stripped_text
    ) is not None


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
    for pattern, kind in (
        (_TRADFN_RE, "tradfn"),
        (_HEADER_ASSIGN_RE, "header_assignment"),
        (_DFN_ASSIGN_RE, "dfn_assignment"),
    ):
        for match in pattern.finditer(stripped_text):
            name = str(match.group("name") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, kind, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(sorted(entries, key=lambda entry: (entry[2], entry[0])))


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        line = raw_line
        for pattern in (_TRADFN_RE, _HEADER_ASSIGN_RE, _DFN_ASSIGN_RE):
            match = pattern.match(line)
            if match is not None:
                line = line[match.end() :]
                break
        for match in _REFERENCE_RE.finditer(line):
            name = str(match.group("name") or "").strip()
            if not name or name in _RESERVED_REFERENCE_NAMES:
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
    if normalized_path.suffix.lower() not in APL_SUFFIXES:
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "apl"},
            ),
            symbol_name=module_name,
            symbol_kind="apl",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"apl {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "kind": symbol_kind,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}".strip(),
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        current_name = symbol_name
    return current_name
