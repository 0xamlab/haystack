from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

PLANTUML_SUFFIXES = frozenset({".puml", ".plantuml", ".iuml"})
_COMMON_MODULE_ROOTS = frozenset(
    {"architecture", "c4", "diagram", "diagrams", "docs", "plantuml", "puml", "uml", "viz"}
)
_COMMENT_RE = re.compile(r"(?m)^\s*'.*?$")
_DIRECTIVE_RE = re.compile(
    r"(?mi)^\s*(?:@start[a-z0-9_-]*|!include(?:_once|_many)?|!define(?:long)?|"
    r"!function|!procedure|!unquoted\s+(?:function|procedure)|!global|!if(?:n?def)?|"
    r"!endif|!theme|skinparam|sprite)\b"
)
_INCLUDE_RE = re.compile(r"(?mi)^\s*!include(?:_once|_many)?\s+(?P<target>.+?)\s*$")
_SYMBOL_RE = re.compile(
    r"(?mi)^\s*!(?:unquoted\s+)?(?P<kind>function|procedure|define(?:long)?)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_ALIASED_ELEMENT_RE = re.compile(
    r"(?mi)^\s*(?:abstract\s+class|actor|agent|annotation|artifact|boundary|card|circle|"
    r"class|cloud|collections?|component|control|database|entity|enum|file|folder|frame|"
    r"hexagon|interface|label|map|node|object|package|participant|person|queue|rectangle|"
    r"stack|state|storage|usecase)\b.*?\bas\s+(?P<alias>[A-Za-z_][A-Za-z0-9_.:-]*)\b"
)
_DECLARED_ELEMENT_RE = re.compile(
    r"(?mi)^\s*(?:class|interface|enum|object|state|participant|actor|component|database|"
    r"node|package|rectangle|usecase)\s+(?P<name>[A-Za-z_][A-Za-z0-9_.:-]*)\b"
)
_ARROW_RE = re.compile(
    r"(?P<source>[A-Za-z_][A-Za-z0-9_.:-]*)\s*"
    r"(?:[-.ox*#<|=]+(?:left|right|up|down)?[-.ox*#>|=]+)\s*"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_.:-]*)"
)
_MACRO_CALL_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "actor",
        "class",
        "component",
        "database",
        "else",
        "endif",
        "endwhile",
        "fork",
        "group",
        "if",
        "interface",
        "legend",
        "namespace",
        "newpage",
        "node",
        "note",
        "object",
        "opt",
        "package",
        "participant",
        "rectangle",
        "ref",
        "return",
        "skinparam",
        "state",
        "usecase",
        "while",
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
    return str(value or "").strip().strip('"').strip("'").strip()


def has_plantuml_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in PLANTUML_SUFFIXES


def is_probable_plantuml_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in PLANTUML_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _DIRECTIVE_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def clean_import_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return ""
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
    cleaned_target = clean_import_target(import_target)
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
        if PurePosixPath(normalized_candidate).suffix.lower() in PLANTUML_SUFFIXES
        else tuple(f"{normalized_candidate}{suffix}" for suffix in sorted(PLANTUML_SUFFIXES))
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for match in _INCLUDE_RE.finditer(strip_comments(text)):
        target = clean_import_target(match.group("target") or "")
        if not target:
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        entries.append(("includes", target, line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_names: set[str] = set()
    for match in _SYMBOL_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, stripped_text.count("\n", 0, match.start()) + 1))
    for pattern in (_ALIASED_ELEMENT_RE, _DECLARED_ELEMENT_RE):
        for match in pattern.finditer(stripped_text):
            group_values = match.groupdict()
            name = normalize_identifier(group_values.get("alias") or group_values.get("name") or "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_arrow_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen_edges: set[tuple[str, str, int]] = set()
    for line_number, raw_line in enumerate(strip_comments(text).splitlines(), start=1):
        for match in _ARROW_RE.finditer(raw_line):
            source_name = normalize_identifier(match.group("source") or "")
            target_name = normalize_identifier(match.group("target") or "")
            if (
                not source_name
                or not target_name
                or source_name.lower() in _RESERVED_REFERENCE_NAMES
                or target_name.lower() in _RESERVED_REFERENCE_NAMES
            ):
                continue
            edge_entry = (source_name, target_name, line_number)
            if edge_entry in seen_edges:
                continue
            seen_edges.add(edge_entry)
            entries.append(edge_entry)
    return tuple(entries)


def iter_macro_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if (
            not stripped_line
            or stripped_line.startswith("!")
            or stripped_line.startswith("@")
            or _ARROW_RE.search(raw_line)
        ):
            continue
        for match in _MACRO_CALL_RE.finditer(raw_line):
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
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in PLANTUML_SUFFIXES:
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "plantuml"},
            ),
            symbol_name=module_name,
            symbol_kind="plantuml",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"plantuml {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    symbol_kinds = {
        name: "macro" for name, _line_number in iter_symbol_entries(text) if name.isupper()
    }
    for symbol_name, line_number in iter_symbol_entries(text):
        symbol_kind = symbol_kinds.get(symbol_name, "symbol")
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
    symbol_entries: Iterable[tuple[str, int]],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, symbol_line in symbol_entries:
        if symbol_line <= line_number:
            current_name = symbol_name
    return current_name
