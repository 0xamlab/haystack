from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

AMPL_SUFFIXES = frozenset({".ampl", ".mod", ".run", ".dat"})
_COMMON_MODULE_ROOTS = frozenset(
    {"data", "datasets", "example", "examples", "model", "models", "script", "scripts"}
)
_LINE_COMMENT_RE = re.compile(r"(?m)^\s*#.*$")
_DEPENDENCY_RE = re.compile(
    r"""(?mi)^\s*(?P<kind>commands|data|include|model)\s+(?:"(?P<quoted>[^"\n;]+)"|'(?P<squoted>[^'\n;]+)'|(?P<bare>[^;\s]+))\s*;"""
)
_DECLARATION_RE = re.compile(
    r"(?mi)^\s*(?P<kind>set|param|var|table|problem)\s+(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\b"
)
_OBJECTIVE_RE = re.compile(
    r"(?mi)^\s*(?P<kind>maximize|minimize)\s+(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s*:"
)
_CONSTRAINT_RE = re.compile(
    r"(?mi)^\s*(?:(?P<long>subject\s+to)|(?P<short>s\.t\.))\s+(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\s*:"
)
_REFERENCE_RE = re.compile(
    r"(?mi)^\s*(?:display|drop|fix|objective|problem|restore|show|unfix)\s+(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)\b"
)
_MODEL_SOURCE_RE = re.compile(
    r"(?mi)^\s*(?:set|param|var|table|problem)\s+[A-Za-z_][A-Za-z0-9_.-]*\b|^\s*(?:maximize|minimize)\s+[A-Za-z_][A-Za-z0-9_.-]*\s*:|^\s*(?:subject\s+to|s\.t\.)\s+[A-Za-z_][A-Za-z0-9_.-]*\s*:"
)
_RUN_SOURCE_RE = re.compile(
    r"(?mi)^\s*(?:commands|data|display|include|model|option|print|printf|reset|show|solve)\b"
)
_DATA_SOURCE_RE = re.compile(r"(?mi)^\s*data\s*;|^\s*(?:param|set)\s+[A-Za-z_][A-Za-z0-9_.-]*\b")


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t\f"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def has_ampl_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in AMPL_SUFFIXES


def is_probable_ampl_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_ampl_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".run":
        return _RUN_SOURCE_RE.search(stripped_text) is not None
    if suffix == ".dat":
        return _DATA_SOURCE_RE.search(stripped_text) is not None
    return _MODEL_SOURCE_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.stem


def clean_dependency_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if not cleaned or "://" in cleaned or "$" in cleaned or " " in cleaned:
        return ""
    return cleaned.replace("\\", "/")


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for match in _DEPENDENCY_RE.finditer(stripped_text):
        target = clean_dependency_target(
            match.group("quoted") or match.group("squoted") or match.group("bare") or ""
        )
        if not target:
            continue
        kind = normalize_identifier(match.group("kind") or "").lower()
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        entry = (kind, target, line_number)
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for pattern in (_DECLARATION_RE, _OBJECTIVE_RE, _CONSTRAINT_RE):
        for match in pattern.finditer(stripped_text):
            kind = normalize_identifier(match.group("kind") or match.group("long") or "constraint")
            name = normalize_identifier(match.group("name") or "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, kind.lower().replace(" ", "_"), stripped_text.count("\n", 0, match.start()) + 1))
    entries.sort(key=lambda entry: entry[2])
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for match in _REFERENCE_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name:
            continue
        entry = (name, stripped_text.count("\n", 0, match.start()) + 1)
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
    if normalized_path.suffix.lower() not in AMPL_SUFFIXES:
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "ampl"},
            ),
            symbol_name=module_name,
            symbol_kind="ampl",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"ampl {module_name}".strip(),
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


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line > line_number:
            break
        current_name = symbol_name
    return current_name
