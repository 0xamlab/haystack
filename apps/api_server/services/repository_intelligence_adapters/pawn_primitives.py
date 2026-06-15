from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

PAWN_SOURCE_SUFFIXES = frozenset({".pwn"})
PAWN_INCLUDE_SUFFIXES = frozenset({".inc"})
PAWN_SUFFIXES = PAWN_SOURCE_SUFFIXES | PAWN_INCLUDE_SUFFIXES
_COMMON_MODULE_ROOTS = frozenset({"filterscripts", "gamemodes", "include", "pawn"})
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?m)//.*$")
_INCLUDE_RE = re.compile(r'(?mi)^\s*#include\s*[<"](?P<target>[^>"]+)[>"]')
_ENUM_RE = re.compile(r"(?mi)^\s*enum\s+(?P<name>[A-Za-z_@][A-Za-z0-9_@]*)")
_FUNCTION_RE = re.compile(
    r"(?mi)^\s*(?:(?:stock|public|native|forward|static)\s+)*(?:(?:[A-Za-z_][A-Za-z0-9_]*):)?(?P<name>[A-Za-z_@][A-Za-z0-9_@]*)\s*\([^;]*\)"
)
_REFERENCE_RE = re.compile(r"(?P<name>[A-Za-z_@][A-Za-z0-9_@]*)\s*\(")
_PROBABLE_SOURCE_RE = re.compile(
    r"(?mi)^\s*#include\b|^\s*(?:stock|public|native|forward|enum)\b|^\s*(?:new|const)\b|^\s*[A-Za-z_][A-Za-z0-9_]*\s*:"
)
_DECLARATION_PREFIX_RE = re.compile(
    r"(?mi)^\s*(?:stock|public|native|forward|static|enum|if|for|while|switch|return|sizeof)\b"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "for",
        "if",
        "main",
        "return",
        "sizeof",
        "switch",
        "while",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _preserve_line_count_comment(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_comments(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(_preserve_line_count_comment, text)
    return _LINE_COMMENT_RE.sub("", without_block_comments)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_pawn_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in PAWN_SUFFIXES


def is_probable_pawn_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_pawn_path_hints(path) or not text or _looks_binaryish(text):
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


def clean_include_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if "://" in cleaned:
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
    if not normalized_candidate:
        return None
    direct_match = module_index.get(normalized_candidate)
    if direct_match is not None:
        return direct_match
    suffixes = (
        (normalized_candidate,)
        if PurePosixPath(normalized_candidate).suffix.lower() in PAWN_SUFFIXES
        else tuple(f"{normalized_candidate}{suffix}" for suffix in sorted(PAWN_SUFFIXES))
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    for match in _INCLUDE_RE.finditer(stripped_text):
        include_target = clean_include_target(match.group("target") or "")
        if not include_target:
            continue
        entries.append(("includes", include_target, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for pattern, kind in ((_ENUM_RE, "enum"), (_FUNCTION_RE, "function")):
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in seen_names or name.lower() in _RESERVED_REFERENCE_NAMES:
                continue
            seen_names.add(name)
            entries.append((name, kind, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line or _DECLARATION_PREFIX_RE.match(stripped_line):
            continue
        for match in _REFERENCE_RE.finditer(raw_line):
            name = normalize_identifier(match.group("name") or "")
            if not name or name.lower() in _RESERVED_REFERENCE_NAMES:
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
    if normalized_path.suffix.lower() not in PAWN_SUFFIXES:
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "pawn"},
            ),
            symbol_name=module_name,
            symbol_kind="pawn",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"pawn {module_name}".strip(),
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
