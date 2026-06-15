from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

XQUERY_SUFFIXES = frozenset({".xq", ".xquery", ".xqy", ".xql", ".xqm"})
_COMMENT_RE = re.compile(r"(?s)\(\:.*?\:\)")
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:xquery\s+version|module\s+namespace|declare\s+(?:%[A-Za-z0-9:._-]+\s+)*function|import\s+module\s+namespace)\b"
)
_IMPORT_RE = re.compile(
    r"""(?im)^\s*import\s+module\s+namespace\s+(?P<prefix>[A-Za-z_][A-Za-z0-9._-]*)\s*=\s*["'][^"']+["']\s+at\s+["'](?P<target>[^"']+)["']\s*;?"""
)
_FUNCTION_RE = re.compile(
    r"""(?im)^\s*declare\s+(?:%[A-Za-z0-9:._-]+\s+)*function\s+(?P<name>(?:[A-Za-z_][A-Za-z0-9._-]*:)?[A-Za-z_][A-Za-z0-9._-]*)\s*\("""
)
_CALL_RE = re.compile(
    r"""(?P<name>(?:[A-Za-z_][A-Za-z0-9._-]*:)?[A-Za-z_][A-Za-z0-9._-]*)\s*\("""
)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_xquery_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in XQUERY_SUFFIXES


def is_probable_xquery_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_xquery_path_hints(path) or not text:
        return False
    stripped_text = strip_comments(text)
    return _MARKER_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    return normalized_path.with_suffix("").name


def resolve_xquery_target(
    *,
    current_file: str,
    target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = normalize_identifier(target)
    if not cleaned_target or "://" in cleaned_target:
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
        if PurePosixPath(normalized_candidate).suffix.lower() in XQUERY_SUFFIXES
        else tuple(f"{normalized_candidate}{suffix}" for suffix in sorted(XQUERY_SUFFIXES))
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, str, int]] = []
    seen_entries: set[tuple[str, str, str, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        prefix = normalize_identifier(match.group("prefix") or "")
        target = normalize_identifier(match.group("target") or "")
        if not prefix or not target:
            continue
        entry = ("xquery_import", prefix, target, stripped_text.count("\n", 0, match.start()) + 1)
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _FUNCTION_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "function", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
    imported_prefixes: set[str],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        lowered = raw_line.lstrip().lower()
        if lowered.startswith("import module namespace"):
            continue
        candidate_line = raw_line
        if lowered.startswith("declare "):
            body_start = raw_line.find("{")
            if body_start < 0:
                continue
            candidate_line = raw_line[body_start + 1 :]
        for match in _CALL_RE.finditer(candidate_line):
            name = normalize_identifier(match.group("name") or "")
            if not name:
                continue
            prefix = name.split(":", 1)[0] if ":" in name else None
            if name not in local_symbol_names and (prefix is None or prefix not in imported_prefixes):
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
    if normalized_path.suffix.lower() not in XQUERY_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "xquery"},
            ),
            symbol_name=module_name,
            symbol_kind="xquery",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"xquery {module_name}",
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
