from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

CIRCOM_SUFFIXES = frozenset({".circom"})
_COMMON_MODULE_ROOTS = frozenset(
    {"benchmark", "benchmarks", "circuit", "circuits", "doc", "docs", "example", "examples", "lib", "src", "test", "tests"}
)
_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
_INCLUDE_RE = re.compile(r'(?mi)^\s*include\s+"(?P<target>[^"\n]+)"\s*;')
_TEMPLATE_RE = re.compile(r"(?mi)^\s*template\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_COMPONENT_DEF_RE = re.compile(
    r"(?mi)^\s*component\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?)\s*="
)
_COMPONENT_REF_RE = re.compile(
    r"(?mi)\bcomponent\s+[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?\s*=\s*(?P<target>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_PROBABLE_SOURCE_RE = re.compile(
    r"(?mi)^\s*(?:pragma\s+circom\b|include\s+\"|template\b|component\b|signal\s+(?:input|output)\b)"
)
_REFERENCE_SKIP_PREFIXES = ("include ", "pragma ", "template ", "signal ")
_RESERVED_REFERENCE_NAMES = frozenset(
    {"component", "for", "if", "include", "pragma", "signal", "template", "var"}
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


def has_circom_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in CIRCOM_SUFFIXES


def is_probable_circom_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_circom_path_hints(path) or not text or _looks_binaryish(text):
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
    if suffix in CIRCOM_SUFFIXES:
        without_suffix = normalize_repository_relative_path(
            str(PurePosixPath(normalized_base).with_suffix(""))
        )
        if without_suffix:
            candidates.extend((without_suffix, without_suffix.replace("/", ".")))
    else:
        candidates.extend((f"{normalized_base}.circom", normalized_base.replace("/", ".")))
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


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _TEMPLATE_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "template", stripped_text.count("\n", 0, match.start()) + 1))
    for match in _COMPONENT_DEF_RE.finditer(stripped_text):
        raw_name = normalize_identifier(match.group("name") or "")
        name = raw_name.split("[", 1)[0]
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "component", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(sorted(entries, key=lambda entry: (entry[2], entry[0], entry[1])))


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    declaration_lines = {line_number for _name, _kind, line_number in iter_symbol_entries(text)}
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        line = raw_line.strip()
        is_component_line = line.startswith("component ")
        if (
            not line
            or (line_number in declaration_lines and not is_component_line)
            or any(line.startswith(prefix) for prefix in _REFERENCE_SKIP_PREFIXES)
        ):
            continue
        for match in _COMPONENT_REF_RE.finditer(line):
            name = normalize_identifier(match.group("target") or "")
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
    if normalized_path.suffix.lower() not in CIRCOM_SUFFIXES:
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "circom"},
            ),
            symbol_name=module_name,
            symbol_kind="circom",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"circom {module_name}".strip(),
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
    return resolve_suffix_match(module_index=module_index, suffixes=(f"{candidate_base}.circom",))


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
    "CIRCOM_SUFFIXES",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "StableIdentifier",
    "candidate_module_keys",
    "collect_symbols",
    "has_circom_path_hints",
    "is_probable_circom_source",
    "iter_include_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "resolve_include",
    "source_symbol_name_for_line",
    "strip_comments",
]
