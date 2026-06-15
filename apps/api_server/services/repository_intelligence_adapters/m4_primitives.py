from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

M4_SUFFIXES = frozenset({".m4"})
_COMMON_MODULE_ROOTS = frozenset({"lib", "m4", "macros", "build-aux", "autoconf"})
_COMMENT_RE = re.compile(r"(?mi)^\s*dnl.*$")
_INCLUDE_PATTERNS = (
    re.compile(r"(?mi)\bm4_include\(\s*\[(?P<target>[^\]]+)\]\s*\)"),
    re.compile(r"(?mi)\binclude\(\s*`(?P<target>[^']+)'\s*\)"),
    re.compile(r'(?mi)\binclude\(\s*"(?P<target>[^"]+)"\s*\)'),
)
_SYMBOL_PATTERNS = (
    re.compile(r"(?mi)\bAC_DEFUN\(\s*\[(?P<name>[A-Z0-9_]+)\]"),
    re.compile(r"(?mi)\bm4_define\(\s*\[(?P<name>[A-Za-z0-9_]+)\]"),
    re.compile(r"(?mi)\bdefine\(\s*`(?P<name>[A-Za-z0-9_]+)'"),
)
_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<name>[A-Z][A-Z0-9_]{1,})(?=\s*(?:\(|[\],)]|$))"
)
_PROBABLE_SOURCE_RE = re.compile(r"(?mi)\b(?:AC_DEFUN|AC_INIT|m4_define|m4_include|dnl)\b")
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "AC_DEFUN",
        "AC_INIT",
        "AH_TEMPLATE",
        "AS_IF",
        "AS_VAR_IF",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip("`").strip()


def has_m4_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in M4_SUFFIXES


def is_probable_m4_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_m4_path_hints(path) or not text or _looks_binaryish(text):
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


def clean_include_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if not cleaned or "://" in cleaned:
        return ""
    return cleaned


def resolve_include(
    *,
    current_file: str,
    include_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_include_target(include_target)
    if not cleaned_target:
        return None
    candidate_path = PurePosixPath(cleaned_target)
    current_dir = PurePosixPath(current_file).parent
    normalized_candidate = normalize_repository_relative_path(
        candidate_path if candidate_path.is_absolute() else current_dir / candidate_path
    )
    raw_candidate = normalize_repository_relative_path(cleaned_target)
    for candidate in tuple(
        normalized
        for normalized in (normalized_candidate, raw_candidate)
        if normalized
    ):
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
        suffixes = (
            (candidate,)
            if PurePosixPath(candidate).suffix.lower() in M4_SUFFIXES
            else tuple(f"{candidate}{suffix}" for suffix in sorted(M4_SUFFIXES))
        )
        matched = resolve_suffix_match(module_index=module_index, suffixes=suffixes)
        if matched is not None:
            return matched
    return None


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for pattern in _INCLUDE_PATTERNS:
        for match in pattern.finditer(stripped_text):
            include_target = clean_include_target(match.group("target") or "")
            if not include_target:
                continue
            entry = ("includes", include_target, stripped_text.count("\n", 0, match.start()) + 1)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for pattern, kind in (
        (_SYMBOL_PATTERNS[0], "autoconf_macro"),
        (_SYMBOL_PATTERNS[1], "m4_macro"),
        (_SYMBOL_PATTERNS[2], "define_macro"),
    ):
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, kind, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        for match in _REFERENCE_RE.finditer(raw_line):
            name = normalize_identifier(match.group("name") or "")
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
    if normalized_path.suffix.lower() not in M4_SUFFIXES:
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "m4"},
            ),
            symbol_name=module_name,
            symbol_kind="m4",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"m4 {module_name}".strip(),
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
