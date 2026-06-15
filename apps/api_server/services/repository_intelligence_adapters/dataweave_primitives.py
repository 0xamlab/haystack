from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

DATAWEAVE_SUFFIXES = frozenset({".dwl"})
_COMMENT_RE = re.compile(r"(?m)//.*$")
_DIRECTIVE_RE = re.compile(r"(?mi)^\s*(?:%dw\b|output\b|import\b|var\b|fun\b|type\b)")
_IMPORT_RE = re.compile(
    r"(?mi)^\s*import\s+(?P<imports>.+?)\s+from\s+(?P<target>[A-Za-z0-9_:.\\/-]+)\s*$"
)
_FUNCTION_RE = re.compile(r"(?mi)^\s*fun\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_VARIABLE_RE = re.compile(r"(?mi)^\s*var\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=")


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


def has_dataweave_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in DATAWEAVE_SUFFIXES


def is_probable_dataweave_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in DATAWEAVE_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _DIRECTIVE_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def clean_import_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if "://" in cleaned:
        return ""
    return cleaned


def _import_target_candidates(current_file: str, import_target: str) -> tuple[PurePosixPath, ...]:
    normalized_target = clean_import_target(import_target).replace("::", "/")
    candidate_path = PurePosixPath(normalized_target)
    current_dir = PurePosixPath(current_file).parent
    candidates = [candidate_path]
    if not candidate_path.is_absolute():
        candidates.append(current_dir / candidate_path)
    deduped: list[PurePosixPath] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return tuple(deduped)


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_import_target(import_target)
    if not cleaned_target or cleaned_target.lower().startswith("dw::"):
        return None
    for candidate_path in _import_target_candidates(current_file, cleaned_target):
        normalized_candidate = normalize_repository_relative_path(candidate_path)
        if not normalized_candidate:
            continue
        direct_match = module_index.get(normalized_candidate)
        if direct_match is not None:
            return direct_match
        if "::" in cleaned_target:
            alias_match = module_index.get(cleaned_target)
            if alias_match is not None:
                return alias_match
        suffixes = (
            (normalized_candidate,)
            if PurePosixPath(normalized_candidate).suffix.lower() in DATAWEAVE_SUFFIXES
            else tuple(f"{normalized_candidate}{suffix}" for suffix in sorted(DATAWEAVE_SUFFIXES))
        )
        resolved_match = resolve_suffix_match(module_index=module_index, suffixes=suffixes)
        if resolved_match is not None:
            return resolved_match
    return None


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for match in _IMPORT_RE.finditer(strip_comments(text)):
        target = clean_import_target(match.group("target") or "")
        if not target:
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        entries.append(("imports", target, line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for pattern, kind in ((_FUNCTION_RE, "function"), (_VARIABLE_RE, "variable")):
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(match.group("name") or "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, kind, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in DATAWEAVE_SUFFIXES:
        return set()
    without_suffix = str(normalized_path.with_suffix(""))
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        without_suffix,
        without_suffix.replace("/", "."),
        without_suffix.replace("/", "::"),
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "dataweave"},
            ),
            symbol_name=module_name,
            symbol_kind="dataweave",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"dataweave {module_name}".strip(),
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
                signature=f"{symbol_kind} {symbol_name}".strip(),
            )
        )
    return tuple(symbols)
