from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

SMALI_SUFFIXES = frozenset({".smali"})
_COMMON_MODULE_ROOTS = frozenset({"smali", "smali_classes2", "smali_classes3", "src"})
_LINE_COMMENT_RE = re.compile(r"(?m)^\s*#.*$")
_CLASS_RE = re.compile(r"(?mi)^\s*\.class\b[^\n]*\sL(?P<descriptor>[A-Za-z0-9_/$-]+);")
_SUPER_RE = re.compile(r"(?mi)^\s*\.super\s+L(?P<descriptor>[A-Za-z0-9_/$-]+);")
_IMPLEMENTS_RE = re.compile(r"(?mi)^\s*\.implements\s+L(?P<descriptor>[A-Za-z0-9_/$-]+);")
_METHOD_RE = re.compile(
    r"(?mi)^\s*\.method\b[^\n]*?\s(?P<name><init>|<clinit>|[A-Za-z_$][A-Za-z0-9_$]*)\("
)
_REFERENCE_RE = re.compile(
    r"L(?P<descriptor>[A-Za-z0-9_/$-]+);->(?P<name><init>|<clinit>|[A-Za-z_$][A-Za-z0-9_$]*)\("
)
_PROBABLE_SOURCE_RE = re.compile(
    r"(?mi)^\s*\.(?:class|super|method|field|implements)\b|\binvoke-(?:virtual|static|direct|super|interface)\b"
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_smali_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in SMALI_SUFFIXES


def descriptor_to_path(descriptor: str) -> str:
    return f"{normalize_identifier(descriptor).lstrip('L').rstrip(';')}.smali"


def descriptor_to_class_name(descriptor: str) -> str:
    normalized = normalize_identifier(descriptor).lstrip("L").rstrip(";")
    return normalized.rsplit("/", 1)[-1].rsplit("$", 1)[-1]


def descriptor_to_dotted_name(descriptor: str) -> str:
    return normalize_identifier(descriptor).lstrip("L").rstrip(";").replace("/", ".")


def is_probable_smali_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_smali_path_hints(path) or not text or _looks_binaryish(text):
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


def resolve_descriptor(
    *,
    descriptor: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate = normalize_repository_relative_path(descriptor_to_path(descriptor))
    if not candidate:
        return None
    direct_match = module_index.get(candidate)
    if direct_match is not None:
        return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=(candidate,))


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for pattern, kind in ((_SUPER_RE, "extends"), (_IMPLEMENTS_RE, "implements")):
        for match in pattern.finditer(stripped_text):
            descriptor = normalize_identifier(match.group("descriptor") or "")
            if not descriptor:
                continue
            entry = (kind, descriptor, stripped_text.count("\n", 0, match.start()) + 1)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    class_match = _CLASS_RE.search(stripped_text)
    if class_match is not None:
        descriptor = normalize_identifier(class_match.group("descriptor") or "")
        if descriptor:
            entries.append(
                (
                    descriptor_to_class_name(descriptor),
                    "class",
                    stripped_text.count("\n", 0, class_match.start()) + 1,
                )
            )
    seen_names = {entry[0] for entry in entries}
    for match in _METHOD_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "method", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for match in _REFERENCE_RE.finditer(stripped_text):
        descriptor = normalize_identifier(match.group("descriptor") or "")
        name = normalize_identifier(match.group("name") or "")
        if not descriptor or not name:
            continue
        entry = (descriptor, name, stripped_text.count("\n", 0, match.start()) + 1)
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
    if normalized_path.suffix.lower() not in SMALI_SUFFIXES:
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
    class_match = _CLASS_RE.search(strip_comments(text))
    if class_match is not None:
        descriptor = normalize_identifier(class_match.group("descriptor") or "")
        if descriptor:
            aliases.add(descriptor_to_path(descriptor))
            aliases.add(descriptor_to_dotted_name(descriptor))
            aliases.add(descriptor_to_class_name(descriptor))
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
                {"file_path": file_path, "symbol_name": module_name, "kind": "smali"},
            ),
            symbol_name=module_name,
            symbol_kind="smali",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"smali {module_name}".strip(),
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
