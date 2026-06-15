from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

AIKEN_SOURCE_SUFFIXES = frozenset({".ak"})
AIKEN_CONFIG_BASENAMES = frozenset({"aiken.toml"})
_MODULE_ROOTS = ("lib", "validators", "src", "examples", "example")
_USE_RE = re.compile(
    r"^\s*use\s+(?P<target>[A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z][A-Za-z0-9_]*)*)"
    r"(?:\.\{(?P<imports>[\s\S]*?)\})?"
    r"(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?\s*$",
    re.MULTILINE,
)
_TYPE_RE = re.compile(
    r"^\s*(?:pub\s+)?type\s+(?P<name>[A-Z][A-Za-z0-9_]*)"
    r"(?:<[^>\n]+>)?\s*(?:\{|=)",
    re.MULTILINE,
)
_FUNCTION_RE = re.compile(
    r"^\s*(?:pub\s+)?fn\s+(?P<name>[a-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_CONST_RE = re.compile(
    r"^\s*(?:pub\s+)?const\s+(?P<name>[a-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_TEST_RE = re.compile(
    r"^\s*test\s+(?P<name>[a-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_VALIDATOR_RE = re.compile(
    r"^\s*(?:pub\s+)?validator(?:\s+(?P<name>[a-z_][A-Za-z0-9_]*))?\b",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_CALL_RE = re.compile(r"(?<![./#])\b(?P<name>[a-z_][A-Za-z0-9_]*)\b(?=\s*\()")
_MARKER_RE = re.compile(
    r"(?m)^\s*use\s+[A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z][A-Za-z0-9_]*)*"
    r"|^\s*(?:pub\s+)?type\s+[A-Z][A-Za-z0-9_]*"
    r"|^\s*(?:pub\s+)?fn\s+[a-z_][A-Za-z0-9_]*\s*\("
    r"|^\s*(?:pub\s+)?const\s+[a-z_][A-Za-z0-9_]*\b"
    r"|^\s*test\s+[a-z_][A-Za-z0-9_]*\s*\("
    r"|^\s*(?:pub\s+)?validator\b"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "and",
        "as",
        "benchmark",
        "else",
        "expect",
        "fail",
        "fn",
        "if",
        "is",
        "let",
        "opaque",
        "or",
        "pub",
        "test",
        "trace",
        "type",
        "use",
        "validator",
        "when",
    }
)


def _line_number(text: str, index: int) -> int:
    bounded_index = max(0, min(index, len(text)))
    return bisect_right(_line_start_offsets(text), bounded_index)


@lru_cache(maxsize=1024)
def _line_start_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    for offset, character in enumerate(text):
        if character == "\n":
            offsets.append(offset + 1)
    return tuple(offsets)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


@lru_cache(maxsize=1024)
def strip_comments(text: str) -> str:
    characters: list[str] = []
    index = 0
    in_string = False
    while index < len(text):
        next_two = text[index : index + 2]
        character = text[index]
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
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters).lstrip("\ufeff")


def has_aiken_path_hints(path: Path | PurePosixPath | str) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in AIKEN_SOURCE_SUFFIXES
        or normalized_path.name.lower() in AIKEN_CONFIG_BASENAMES
    )


def is_probable_aiken_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in AIKEN_SOURCE_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip() and _MARKER_RE.search(stripped_text))


def is_probable_aiken_config(*, path: Path | PurePosixPath | str, text: str) -> bool:
    if PurePosixPath(path).name.lower() not in AIKEN_CONFIG_BASENAMES:
        return False
    lowered = text.lower()
    return (
        'name = "' in lowered
        and 'version = "' in lowered
        and ("compiler = " in lowered or "[[dependencies]]" in lowered)
    )


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
    parts = list(normalized_path.parts)
    for module_root in _MODULE_ROOTS:
        if module_root not in parts:
            continue
        root_index = parts.index(module_root)
        relative_parts = parts[root_index + 1 :]
        if not relative_parts:
            continue
        relative_parts[-1] = PurePosixPath(relative_parts[-1]).stem.removesuffix(".test")
        return "/".join(part for part in relative_parts if part)
    return str(normalized_path.with_suffix("")).removesuffix(".test")


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


def parse_imported_names(raw_value: str) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    for raw_name in str(raw_value or "").replace("\n", " ").split(","):
        candidate = raw_name.strip()
        if not candidate or candidate in seen:
            continue
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", candidate):
            continue
        seen.add(candidate)
        names.append(candidate)
    return tuple(names)


def iter_use_entries(text: str) -> tuple[tuple[str, str | None, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, tuple[str, ...], int]] = []
    for match in _USE_RE.finditer(stripped_text):
        target = _normalize_repository_relative_path(str(match.group("target") or ""))
        if not target:
            continue
        alias = str(match.group("alias") or "").strip() or None
        imports = parse_imported_names(str(match.group("imports") or ""))
        entries.append((target, alias, imports, _line_number(stripped_text, match.start())))
    return tuple(entries)


@lru_cache(maxsize=1024)
def _iter_symbol_matches(stripped_text: str) -> tuple[tuple[str, str, int], ...]:
    matches: list[tuple[str, str, int]] = []
    for regex, symbol_kind in (
        (_TYPE_RE, "type"),
        (_FUNCTION_RE, "function"),
        (_CONST_RE, "constant"),
        (_TEST_RE, "test"),
        (_VALIDATOR_RE, "validator"),
    ):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip() or "validator"
            matches.append((symbol_name, symbol_kind, match.start()))
    return tuple(sorted(matches, key=lambda item: (item[2], item[0], item[1])))


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    matches = _iter_symbol_matches(stripped_text)
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


def resolve_import_target(
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_repository_relative_path(import_target)
    if not normalized_target:
        return None
    direct_candidates = (
        normalized_target,
        normalized_target.replace("/", "."),
        f"{normalized_target}.ak",
        f"lib/{normalized_target}.ak",
        f"validators/{normalized_target}.ak",
        _normalize_repository_relative_path(
            str(PurePosixPath(current_file).parent / f"{normalized_target}.ak")
        ),
    )
    for candidate in dict.fromkeys(direct_candidates):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved
    suffixes = tuple(
        candidate
        for candidate in dict.fromkeys(
            (
                f"{normalized_target}.ak",
                f"lib/{normalized_target}.ak",
                f"validators/{normalized_target}.ak",
                f"/{normalized_target}.ak",
            )
        )
        if candidate
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str | None, str, int]] = []
    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        entries.append(
            (
                str(match.group("alias") or "").strip() or None,
                str(match.group("name") or "").strip(),
                _line_number(stripped_text, match.start()),
            )
        )
    for match in _CALL_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name in _RESERVED_REFERENCE_NAMES:
            continue
        entries.append((None, name, _line_number(stripped_text, match.start())))
    return tuple(entries)
