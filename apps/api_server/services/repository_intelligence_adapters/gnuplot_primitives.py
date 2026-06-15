from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

GNUPLOT_SOURCE_SUFFIXES = frozenset({".dem", ".gnuplot", ".gp", ".plt"})
GNUPLOT_CONFIDENT_SOURCE_SUFFIXES = frozenset({".gnuplot", ".gp", ".plt"})
_COMMENT_RE = re.compile(r"(?m)#.*$")
_COMMAND_RE = re.compile(
    r"(?mi)^\s*(?:set|unset|plot|splot|replot|load|call|fit|stats|pause|reset|print|show|bind|if|do)\b"
)
_LOAD_RE = re.compile(r"""(?mi)^\s*(?P<kind>load|call)\s+(?P<target>"[^"]+"|'[^']+')""")
_FUNCTION_RE = re.compile(r"(?mi)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*=")


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_gnuplot_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in GNUPLOT_SOURCE_SUFFIXES


def is_probable_gnuplot_source(*, path: Path | PurePosixPath, text: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix not in GNUPLOT_SOURCE_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _COMMAND_RE.search(stripped_text) is not None or _FUNCTION_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def clean_load_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if "://" in cleaned:
        return ""
    return cleaned


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_load_target(import_target)
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
        if PurePosixPath(normalized_candidate).suffix.lower() in GNUPLOT_SOURCE_SUFFIXES
        else tuple(f"{normalized_candidate}{suffix}" for suffix in sorted(GNUPLOT_SOURCE_SUFFIXES))
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for match in _LOAD_RE.finditer(strip_comments(text)):
        target = clean_load_target(match.group("target") or "")
        if not target:
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        entries.append((normalize_identifier(match.group("kind") or "load").lower(), target, line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_names: set[str] = set()
    for match in _FUNCTION_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in GNUPLOT_SOURCE_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
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
    line_count = _line_count(text)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "gnuplot"},
            ),
            symbol_name=module_name,
            symbol_kind="gnuplot",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"gnuplot {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": symbol_name, "kind": "function"},
                ),
                symbol_name=symbol_name,
                symbol_kind="function",
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_name}(...)",
            )
        )
    return tuple(symbols)
