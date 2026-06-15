from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

ATS_SUFFIXES = frozenset({".dats", ".sats", ".hats"})
_MODULE_ROOTS = ("dats", "sats", "hats", "src", "lib", "recipe", "playground")
_INCLUDE_RE = re.compile(r'(?im)^\s*#include\s*"(?P<target>[^"]+)"')
_STALOAD_RE = re.compile(
    r'(?im)^\s*#?staload(?:\s+[A-Za-z_][A-Za-z0-9_]*\s*=)?\s*"(?P<target>[^"]+)"'
)
_TYPE_RE = re.compile(
    r"(?im)^\s*(?:typedef|datatype|abstype|abst@ype|datavtype|vtypedef)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_FUNCTION_RE = re.compile(
    r"(?im)^\s*(?:extern\s+)?fun(?:\{\})?\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_IMPLEMENT_RE = re.compile(
    r"(?im)^\s*implement(?:\s*\{[^}]*\})?\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_VALUE_RE = re.compile(r"(?im)^\s*val\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_CALL_RE = re.compile(r"(?<![$./])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?=\s*\()")
_MARKER_RE = re.compile(
    r"(?im)^\s*#include\b|^\s*#?staload\b|^\s*implement\b|^\s*(?:extern\s+)?fun\b|"
    r"^\s*(?:typedef|datatype|abstype|abst@ype|datavtype|vtypedef)\b"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "abstype",
        "abstype",
        "and",
        "case",
        "datatype",
        "else",
        "end",
        "extern",
        "fn",
        "fun",
        "if",
        "implement",
        "in",
        "lam",
        "let",
        "local",
        "overload",
        "staload",
        "then",
        "typedef",
        "val",
        "where",
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
    block_depth = 0
    in_string = False
    while index < len(text):
        next_two = text[index : index + 2]
        character = text[index]
        if block_depth > 0:
            if next_two == "(*":
                block_depth += 1
                characters.extend("  ")
                index += 2
                continue
            if next_two == "*)":
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
        if next_two == "(*":
            block_depth = 1
            characters.extend("  ")
            index += 2
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters).lstrip("\ufeff")


def has_ats_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in ATS_SUFFIXES


def is_probable_ats_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    if not has_ats_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_MARKER_RE.search(stripped_text))


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
    normalized_path = PurePosixPath(file_path)
    parts = [part for part in normalized_path.parts]
    lowered_parts = [part.lower() for part in parts]
    for module_root in _MODULE_ROOTS:
        if module_root not in lowered_parts:
            continue
        root_index = lowered_parts.index(module_root)
        relative_parts = parts[root_index + 1 :]
        if not relative_parts:
            continue
        relative_parts[-1] = PurePosixPath(relative_parts[-1]).stem
        return "/".join(part for part in relative_parts if part)
    return str(normalized_path.with_suffix(""))


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = PurePosixPath(file_path)
    module_name = module_name_from_path(file_path)
    without_suffix = str(normalized_path.with_suffix(""))
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        without_suffix,
        without_suffix.replace("/", "."),
        module_name,
        module_name.replace("/", "."),
        module_name.split("/")[-1] if module_name else "",
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
    if not normalized_target or normalized_target.startswith("$"):
        return None
    current_dir = PurePosixPath(current_file).parent
    candidates = [
        normalized_target,
        _normalize_repository_relative_path(str(current_dir / normalized_target)),
    ]
    if PurePosixPath(normalized_target).suffix.lower() not in ATS_SUFFIXES:
        for suffix in ATS_SUFFIXES:
            candidates.append(f"{normalized_target}{suffix}")
            candidates.append(_normalize_repository_relative_path(str(current_dir / f"{normalized_target}{suffix}")))
    for candidate in dict.fromkeys(candidates):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved
    suffixes = tuple(
        candidate
        for candidate in dict.fromkeys(
            [
                candidate
                for candidate in candidates
                if candidate
            ]
        )
        if candidate
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for regex, dependency_kind in ((_INCLUDE_RE, "includes"), (_STALOAD_RE, "staloads")):
        for match in regex.finditer(stripped_text):
            target_name = _normalize_repository_relative_path(str(match.group("target") or ""))
            if not target_name:
                continue
            entry = (dependency_kind, target_name, _line_number(stripped_text, match.start()))
            if entry in seen:
                continue
            seen.add(entry)
            entries.append(entry)
    return tuple(entries)


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    matches: list[tuple[str, str, int]] = []
    for regex, symbol_kind in (
        (_TYPE_RE, "type"),
        (_FUNCTION_RE, "function"),
        (_IMPLEMENT_RE, "implementation"),
        (_VALUE_RE, "value"),
    ):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name:
                continue
            matches.append((symbol_name, symbol_kind, match.start()))
    matches.sort(key=lambda item: (item[2], item[0], item[1]))
    entries: list[dict[str, object]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for index, (symbol_name, symbol_kind, start_offset) in enumerate(matches):
        start_line = _line_number(stripped_text, start_offset)
        dedupe_key = (symbol_name, symbol_kind, start_line)
        if dedupe_key in seen_entries:
            continue
        seen_entries.add(dedupe_key)
        next_line = (
            _line_number(stripped_text, matches[index + 1][2])
            if index + 1 < len(matches)
            else _line_count(stripped_text) + 1
        )
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "start_line": start_line,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": start_line,
                "end_line": max(start_line, next_line - 1),
                "signature": f"{symbol_kind} {symbol_name}",
            }
        )
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    for match in _CALL_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name in _RESERVED_REFERENCE_NAMES:
            continue
        entries.append((name, _line_number(stripped_text, match.start())))
    return tuple(entries)
