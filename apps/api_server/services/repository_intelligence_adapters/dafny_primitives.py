from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

DAFNY_SUFFIXES = frozenset({".dfy"})
_COMMON_MODULE_ROOTS = frozenset(
    {"benchmark", "benchmarks", "doc", "docs", "example", "examples", "lib", "src", "test", "tests"}
)
_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
_INCLUDE_RE = re.compile(r'(?mi)^\s*include\s+"(?P<target>[^"\n]+)"')
_MODULE_RE = re.compile(
    r"(?mi)^\s*(?:abstract\s+)?module(?:\s+\{:[^}]+\})*\s+(?P<name>[A-Za-z_][A-Za-z0-9_.]*)"
)
_IMPORT_RE = re.compile(
    r"(?mi)^\s*import(?:\s+opened)?\s+(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\b"
)
_SYMBOL_RE = re.compile(
    r"(?mi)^\s*(?:ghost\s+|abstract\s+|static\s+|opaque\s+|twostate\s+|least\s+|greatest\s+|co\s+)*"
    r"(?P<kind>class|trait|datatype|codatatype|newtype|type|method|function|predicate|lemma|iterator|const)\s+"
    r"(?:\{:[^}]+\}\s+)*(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b"
)
_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_']*)\s*(?:\(|::)")
_PROBABLE_SOURCE_RE = re.compile(
    r"(?mi)^\s*(?:include\s+\"|(?:abstract\s+)?module\b|import\b|method\b|function\b|predicate\b|lemma\b|datatype\b|trait\b|class\b|newtype\b)"
)
_REFERENCE_SKIP_PREFIXES = (
    "include ",
    "import ",
    "module ",
    "abstract module ",
    "method ",
    "function ",
    "predicate ",
    "lemma ",
    "class ",
    "trait ",
    "datatype ",
    "codatatype ",
    "newtype ",
    "const ",
    "iterator ",
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "array",
        "assert",
        "assume",
        "bool",
        "break",
        "case",
        "class",
        "const",
        "continue",
        "datatype",
        "decreases",
        "else",
        "ensures",
        "exists",
        "false",
        "for",
        "forall",
        "function",
        "ghost",
        "if",
        "import",
        "in",
        "include",
        "invariant",
        "int",
        "is",
        "iterator",
        "lemma",
        "map",
        "match",
        "method",
        "modifies",
        "module",
        "multiset",
        "nat",
        "newtype",
        "object",
        "opaque",
        "opened",
        "predicate",
        "reads",
        "refines",
        "requires",
        "return",
        "returns",
        "seq",
        "set",
        "string",
        "then",
        "this",
        "trait",
        "true",
        "type",
        "var",
        "while",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t\f"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text).replace("\ufeff", "")


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_dafny_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in DAFNY_SUFFIXES


def is_probable_dafny_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_dafny_path_hints(path) or not text or _looks_binaryish(text):
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


def candidate_module_keys(
    base_path: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_base = normalize_repository_relative_path(base_path)
    if not normalized_base:
        return ()
    suffix = PurePosixPath(normalized_base).suffix.lower()
    candidates = [normalized_base]
    if suffix in DAFNY_SUFFIXES:
        without_suffix = normalize_repository_relative_path(
            str(PurePosixPath(normalized_base).with_suffix(""))
        )
        if without_suffix:
            candidates.extend((without_suffix, without_suffix.replace("/", ".")))
    else:
        candidates.extend((f"{normalized_base}.dfy", normalized_base.replace("/", ".")))
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def iter_include_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        target = normalize_identifier(match.group("target") or "")
        if not target:
            continue
        entry = (target, stripped_text.count("\n", 0, match.start()) + 1)
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    return tuple(entries)


def iter_import_entries(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, int]] = []
    seen_entries: set[tuple[str, str | None, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        target = normalize_identifier(match.group("target") or "")
        alias = normalize_identifier(match.group("alias") or "") or None
        if not target:
            continue
        entry = (target, alias, stripped_text.count("\n", 0, match.start()) + 1)
        if entry in seen_entries:
            continue
        seen_entries.add(entry)
        entries.append(entry)
    return tuple(entries)


def iter_module_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_names: set[str] = set()
    for match in _MODULE_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for module_name, line_number in iter_module_entries(stripped_text):
        seen_names.add(module_name)
        entries.append((module_name, "module", line_number))
    for match in _SYMBOL_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        kind = normalize_identifier(match.group("kind") or "").lower()
        if not name or not kind or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, kind, stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(sorted(entries, key=lambda entry: (entry[2], entry[0], entry[1])))


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    declaration_lines = {line_number for _name, _kind, line_number in iter_symbol_entries(text)}
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        line = raw_line.strip()
        if (
            not line
            or line_number in declaration_lines
            or any(line.startswith(prefix) for prefix in _REFERENCE_SKIP_PREFIXES)
        ):
            continue
        for match in _REFERENCE_RE.finditer(line):
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
    if normalized_path.suffix.lower() not in DAFNY_SUFFIXES:
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
    for module_name, _line in iter_module_entries(text):
        aliases.add(module_name)
    for symbol_name, _kind, _line in iter_symbol_entries(text):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    declared_modules = iter_module_entries(text)
    primary_module_name = declared_modules[0][0] if declared_modules else module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": primary_module_name, "kind": "dafny"},
            ),
            symbol_name=primary_module_name,
            symbol_kind="dafny",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"dafny {primary_module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    seen_names = {primary_module_name}
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        if symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
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


def resolve_include(
    include_target: str,
    current_file: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(include_target)
    if not normalized_target:
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_base = normalized_target
    if current_dir:
        candidate_base = normalize_repository_relative_path(
            str(PurePosixPath(current_dir) / normalized_target)
        ) or normalized_target
    for candidate_key in candidate_module_keys(
        candidate_base,
        normalize_repository_relative_path=normalize_repository_relative_path,
    ):
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=(f"{candidate_base}.dfy",))


def resolve_import_module(
    import_target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    slash_path = normalize_repository_relative_path(normalized_target.replace(".", "/"))
    if slash_path:
        for candidate_key in candidate_module_keys(
            slash_path,
            normalize_repository_relative_path=normalize_repository_relative_path,
        ):
            resolved = module_index.get(candidate_key)
            if resolved is not None:
                return resolved
        resolved = resolve_suffix_match(module_index=module_index, suffixes=(f"{slash_path}.dfy",))
        if resolved is not None:
            return resolved
    for prefix in ("src", "lib", "tests", "examples"):
        prefixed = normalize_repository_relative_path(f"{prefix}/{normalized_target.replace('.', '/')}")
        if not prefixed:
            continue
        resolved = resolve_suffix_match(module_index=module_index, suffixes=(f"{prefixed}.dfy",))
        if resolved is not None:
            return resolved
    return None


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    source_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        source_name = symbol_name
    return source_name


__all__ = [
    "DAFNY_SUFFIXES",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "StableIdentifier",
    "candidate_module_keys",
    "collect_symbols",
    "has_dafny_path_hints",
    "is_probable_dafny_source",
    "iter_import_entries",
    "iter_include_entries",
    "iter_module_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "resolve_import_module",
    "resolve_include",
    "source_symbol_name_for_line",
    "strip_comments",
]
