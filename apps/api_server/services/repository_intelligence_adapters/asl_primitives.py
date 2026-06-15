from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

ASL_SUFFIXES = frozenset({".asl", ".dsl"})
_ACPI_HINT_PARTS = frozenset({"acpi", "origin", "patched", "patches", "tables"})
_INCLUDE_RE = re.compile(r'(?im)^\s*#include\s*"(?P<target>[^"]+)"')
_DEFINITION_BLOCK_RE = re.compile(r"(?im)\bDefinitionBlock\s*\(")
_METHOD_RE = re.compile(
    r"(?im)^\s*Method\s*\(\s*(?P<name>\\?[A-Za-z_][A-Za-z0-9_\.]*)\s*,"
)
_DEVICE_RE = re.compile(r"(?im)^\s*Device\s*\(\s*(?P<name>\\?[A-Za-z_][A-Za-z0-9_\.]*)")
_NAME_RE = re.compile(r"(?im)^\s*Name\s*\(\s*(?P<name>\\?[A-Za-z_][A-Za-z0-9_\.]*)")
_OPERATION_REGION_RE = re.compile(
    r"(?im)^\s*OperationRegion\s*\(\s*(?P<name>\\?[A-Za-z_][A-Za-z0-9_\.]*)"
)
_EXTERNAL_RE = re.compile(
    r"(?im)^\s*External\s*\(\s*(?P<name>\\?[A-Za-z_][A-Za-z0-9_\.]*)\s*,"
)
_CALL_RE = re.compile(
    r"(?<![$/])(?P<qualified>\\?[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(?=\s*\()"
)
_MARKER_PATTERNS = (
    re.compile(r"(?im)^\s*External\s*\("),
    re.compile(r"(?im)^\s*Scope\s*\("),
    re.compile(r"(?im)^\s*Device\s*\("),
    re.compile(r"(?im)^\s*Method\s*\("),
    re.compile(r"(?im)^\s*Name\s*\("),
    re.compile(r"(?im)^\s*OperationRegion\s*\("),
    re.compile(r"(?im)^\s*Field\s*\("),
)
_DECLARATION_PATTERNS = (
    ("method", _METHOD_RE),
    ("device", _DEVICE_RE),
    ("name", _NAME_RE),
    ("region", _OPERATION_REGION_RE),
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "acquire",
        "and",
        "bankfield",
        "buffer",
        "condrefof",
        "createbitfield",
        "createbytefield",
        "createdwordfield",
        "createfield",
        "createqwordfield",
        "createwordfield",
        "definitionblock",
        "device",
        "else",
        "external",
        "field",
        "if",
        "index",
        "method",
        "name",
        "not",
        "operationregion",
        "or",
        "package",
        "processor",
        "release",
        "resourceconsumer",
        "resourcetemplate",
        "return",
        "scope",
        "serialized",
        "switch",
        "thermalzone",
        "while",
    }
)


def _line_number(text: str, index: int) -> int:
    bounded_index = max(0, min(index, len(text)))
    return text.count("\n", 0, bounded_index) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    characters: list[str] = []
    index = 0
    in_string = False
    block_depth = 0
    while index < len(text):
        next_two = text[index : index + 2]
        character = text[index]
        if block_depth > 0:
            if next_two == "/*":
                block_depth += 1
                characters.extend("  ")
                index += 2
                continue
            if next_two == "*/":
                block_depth = max(0, block_depth - 1)
                characters.extend("  ")
                index += 2
                continue
            characters.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            characters.append(character)
            if character == '"' and (index == 0 or text[index - 1] != "\\"):
                in_string = False
            index += 1
            continue
        if next_two == "//":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        if next_two == "/*":
            block_depth = 1
            characters.extend("  ")
            index += 2
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters).lstrip("\ufeff")


def _canonical_symbol_name(value: str) -> str:
    stripped_value = str(value or "").strip()
    return stripped_value[1:] if stripped_value.startswith("\\") else stripped_value


def _short_symbol_name(value: str) -> str:
    canonical_name = _canonical_symbol_name(value)
    return canonical_name.split(".")[-1] if canonical_name else ""


def _reference_target_names(value: str) -> tuple[str, ...]:
    canonical_name = _canonical_symbol_name(value)
    short_name = _short_symbol_name(canonical_name)
    return tuple(
        dict.fromkeys(
            target_name for target_name in (short_name, canonical_name) if target_name
        )
    )


def has_asl_path_hints(path: Path | PurePosixPath | str) -> bool:
    normalized_path = PurePosixPath(path)
    suffix = normalized_path.suffix.lower()
    if suffix == ".asl":
        return True
    if suffix != ".dsl":
        return False
    lowered_parts = {part.lower() for part in normalized_path.parts}
    if lowered_parts & _ACPI_HINT_PARTS:
        return True
    lowered_stem = normalized_path.stem.lower()
    return lowered_stem.startswith(("ssdt", "dsdt")) or "acpi" in lowered_stem


def is_probable_asl_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    if not has_asl_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip() or not _DEFINITION_BLOCK_RE.search(stripped_text):
        return False
    marker_count = sum(1 for pattern in _MARKER_PATTERNS if pattern.search(stripped_text))
    return marker_count >= 2


def _normalize_repository_relative_path(value: str) -> str:
    normalized_parts: list[str] = []
    for part in PurePosixPath(str(value or "").replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def module_name_from_path(file_path: str) -> str:
    return PurePosixPath(file_path).stem


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = PurePosixPath(file_path)
    without_suffix = str(normalized_path.with_suffix(""))
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        without_suffix,
        without_suffix.replace("/", "."),
        module_name,
    }
    return {alias for alias in aliases if alias}


def resolve_target(
    current_file: str,
    target_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_repository_relative_path(target_name)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    candidates = [
        normalized_target,
        _normalize_repository_relative_path(str(current_dir / normalized_target)),
    ]
    if PurePosixPath(normalized_target).suffix.lower() not in ASL_SUFFIXES:
        for suffix in ASL_SUFFIXES:
            candidates.append(f"{normalized_target}{suffix}")
            candidates.append(
                _normalize_repository_relative_path(str(current_dir / f"{normalized_target}{suffix}"))
            )
    for candidate in dict.fromkeys(candidate for candidate in candidates if candidate):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved
    suffixes = tuple(dict.fromkeys(candidate for candidate in candidates if candidate))
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        ("includes", match.group("target"), _line_number(stripped_text, match.start()))
        for match in _INCLUDE_RE.finditer(stripped_text)
    )


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    entries: list[dict[str, object]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    for symbol_kind, pattern in _DECLARATION_PATTERNS:
        for match in pattern.finditer(stripped_text):
            symbol_name = _short_symbol_name(match.group("name"))
            line_number = _line_number(stripped_text, match.start())
            if not symbol_name or (symbol_name, line_number) in seen_symbol_keys:
                continue
            seen_symbol_keys.add((symbol_name, line_number))
            entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_kind": symbol_kind,
                            "symbol_name": symbol_name,
                            "line": line_number,
                        },
                    ),
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "start_line": line_number,
                    "end_line": line_number,
                    "signature": match.group(0).strip(),
                }
            )
    entries.sort(key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
    return tuple(entries)


def iter_external_reference_entries(text: str) -> tuple[tuple[tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (_reference_target_names(match.group("name")), _line_number(stripped_text, match.start()))
        for match in _EXTERNAL_RE.finditer(stripped_text)
        if _reference_target_names(match.group("name"))
    )


def iter_reference_entries(text: str) -> tuple[tuple[tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[tuple[str, ...], int]] = []
    seen_entry_keys: set[tuple[tuple[str, ...], int]] = set()
    for match in _CALL_RE.finditer(stripped_text):
        target_names = _reference_target_names(match.group("qualified"))
        if not target_names or target_names[0].lower() in _RESERVED_REFERENCE_NAMES:
            continue
        entry = (target_names, _line_number(stripped_text, match.start()))
        if entry in seen_entry_keys:
            continue
        seen_entry_keys.add(entry)
        entries.append(entry)
    return tuple(entries)
