from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

FOUR_D_SUFFIXES = frozenset({".4dm"})

_CLASS_EXTENDS_RE = re.compile(r"(?im)^\s*Class\s+extends\s+(?P<name>[_A-Za-z][A-Za-z0-9_]*)\b")
_CLASS_CONSTRUCTOR_RE = re.compile(r"(?im)^\s*Class\s+constructor\s*(?P<signature>\([^)]*\))?")
_PROPERTY_RE = re.compile(
    r"(?im)^\s*property\s+(?P<name>[_A-Za-z][A-Za-z0-9_]*)\s*:\s*(?P<signature>[^\n/]+)"
)
_FUNCTION_RE = re.compile(
    r"(?im)^\s*Function\s+(?:(?P<accessor>get|set)\s+)?(?P<name>[_A-Za-z][A-Za-z0-9_]*)"
    r"\s*(?P<signature>\([^)]*\)\s*(?::\s*[^\n/]+)?)?"
)
_CS_REFERENCE_RE = re.compile(r"(?<![\w.])cs\.(?P<name>[_A-Za-z][A-Za-z0-9_]*)\b")
_THIS_REFERENCE_RE = re.compile(r"(?<![\w.])This\.(?P<name>[_A-Za-z][A-Za-z0-9_]*)\b")
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:Class\s+extends|Class\s+constructor|Function\s+|property\s+|#DECLARE\b|var\s+\$)"
)


@lru_cache(maxsize=256)
def _line_start_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    for index, character in enumerate(text):
        if character == "\n":
            offsets.append(index + 1)
    return tuple(offsets)


def _line_number(text: str, index: int) -> int:
    bounded_index = max(0, min(index, len(text)))
    return bisect_right(_line_start_offsets(text), bounded_index)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def clear_strip_comments_cache() -> None:
    strip_comments.cache_clear()
    _line_start_offsets.cache_clear()
    _declared_symbol_rows.cache_clear()
    _dependency_entries_cached.cache_clear()
    _cs_reference_entries_cached.cache_clear()
    _this_reference_entries_cached.cache_clear()


def _strip_comments_uncached(text: str) -> str:
    characters: list[str] = []
    index = 0
    string_delimiter: str | None = None
    while index < len(text):
        next_two = text[index : index + 2]
        character = text[index]
        if string_delimiter is not None:
            characters.append(character)
            if character == string_delimiter and (index == 0 or text[index - 1] != "\\"):
                string_delimiter = None
            index += 1
            continue
        if next_two == "/*":
            characters.extend("  ")
            index += 2
            while index < len(text):
                block_two = text[index : index + 2]
                if block_two == "*/":
                    characters.extend("  ")
                    index += 2
                    break
                characters.append("\n" if text[index] == "\n" else " ")
                index += 1
            continue
        if next_two == "//":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character in {'"', "'"}:
            string_delimiter = character
        index += 1
    return "".join(characters).lstrip("\ufeff")


@lru_cache(maxsize=256)
def strip_comments(text: str) -> str:
    return _strip_comments_uncached(text)


def has_4d_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in FOUR_D_SUFFIXES


def is_probable_4d_source(
    *,
    path: Path | PurePosixPath | str,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if not has_4d_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not stripped_text.strip():
        return False
    return _MARKER_RE.search(stripped_text) is not None or "cs." in stripped_text


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


def _is_class_file(file_path: str) -> bool:
    parts = [part.lower() for part in PurePosixPath(file_path).parts]
    return "classes" in parts


def _is_method_file(file_path: str) -> bool:
    parts = [part.lower() for part in PurePosixPath(file_path).parts]
    return "methods" in parts or "databasemethods" in parts


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = PurePosixPath(file_path)
    without_suffix = str(normalized_path.with_suffix(""))
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        normalized_path.stem.lower(),
        without_suffix,
        without_suffix.replace("/", "."),
        module_name,
    }
    if _is_class_file(file_path):
        aliases.add(f"cs.{module_name}")
        aliases.add(f"cs.{module_name}.new")
    return {alias for alias in aliases if alias}


def resolve_target(
    current_file: str,
    target_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_repository_relative_path(target_name.replace("cs.", ""))
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    candidates = [
        target_name,
        normalized_target,
        f"cs.{normalized_target}",
        _normalize_repository_relative_path(str(current_dir / normalized_target)),
    ]
    if PurePosixPath(normalized_target).suffix.lower() not in FOUR_D_SUFFIXES:
        for suffix in FOUR_D_SUFFIXES:
            candidates.extend(
                (
                    f"{normalized_target}{suffix}",
                    _normalize_repository_relative_path(str(current_dir / f"{normalized_target}{suffix}")),
                )
            )
    for candidate in dict.fromkeys(candidate for candidate in candidates if candidate):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved
    suffixes = tuple(dict.fromkeys(candidate for candidate in candidates if candidate))
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


@lru_cache(maxsize=256)
def _declared_symbol_rows(
    stripped_text: str,
    file_path: str,
    line_count: int,
) -> tuple[tuple[str, str, int, int, str, int | None], ...]:
    rows: list[tuple[str, str, int, int, str, int | None]] = []
    if _is_class_file(file_path):
        class_name = module_name_from_path(file_path)
        rows.append((class_name, "class", 1, line_count, class_name, None))
    for match in _CLASS_CONSTRUCTOR_RE.finditer(stripped_text):
        start_line = _line_number(stripped_text, match.start())
        rows.append(
            (
                "constructor",
                "constructor",
                start_line,
                _line_number(stripped_text, match.end()),
                match.group("signature") or "Class constructor",
                start_line,
            )
        )
    for match in _PROPERTY_RE.finditer(stripped_text):
        start_line = _line_number(stripped_text, match.start())
        rows.append(
            (
                match.group("name"),
                "property",
                start_line,
                _line_number(stripped_text, match.end()),
                match.group("signature").strip(),
                start_line,
            )
        )
    for match in _FUNCTION_RE.finditer(stripped_text):
        accessor = (match.group("accessor") or "").lower()
        symbol_kind = "getter" if accessor == "get" else "setter" if accessor == "set" else "function"
        start_line = _line_number(stripped_text, match.start())
        rows.append(
            (
                match.group("name"),
                symbol_kind,
                start_line,
                _line_number(stripped_text, match.end()),
                (match.group("signature") or "").strip() or match.group("name"),
                start_line,
            )
        )
    return tuple(rows)


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[dict[str, object], ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    entries: list[dict[str, object]] = []
    line_count = _line_count(text)
    for symbol_name, symbol_kind, start_line, end_line, signature, line_number in _declared_symbol_rows(
        stripped_text,
        file_path,
        line_count,
    ):
        identifier_payload: dict[str, object] = {
            "file_path": file_path,
            "symbol_name": symbol_name,
        }
        if symbol_kind == "class":
            identifier_payload["symbol_kind"] = symbol_kind
        elif line_number is not None:
            identifier_payload["line"] = line_number
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    identifier_payload,
                ),
                "symbol_kind": symbol_kind,
                "symbol_name": symbol_name,
                "start_line": start_line,
                "end_line": end_line,
                "signature": signature,
            }
        )
    return tuple(entries)


@lru_cache(maxsize=256)
def _dependency_entries_cached(stripped_text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for match in _CLASS_EXTENDS_RE.finditer(stripped_text):
        entries.append(("extends", match.group("name"), _line_number(stripped_text, match.start())))
    for match in _CS_REFERENCE_RE.finditer(stripped_text):
        entries.append(("uses", match.group("name"), _line_number(stripped_text, match.start())))
    return tuple(entries)


def iter_dependency_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    return _dependency_entries_cached(stripped_text)


@lru_cache(maxsize=256)
def _cs_reference_entries_cached(stripped_text: str) -> tuple[tuple[str, int], ...]:
    return tuple(
        (match.group("name"), _line_number(stripped_text, match.start()))
        for match in _CS_REFERENCE_RE.finditer(stripped_text)
    )


def iter_cs_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    return _cs_reference_entries_cached(stripped_text)


@lru_cache(maxsize=256)
def _this_reference_entries_cached(stripped_text: str) -> tuple[tuple[str, int], ...]:
    return tuple(
        (match.group("name"), _line_number(stripped_text, match.start()))
        for match in _THIS_REFERENCE_RE.finditer(stripped_text)
    )


def iter_this_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    return _this_reference_entries_cached(stripped_text)
