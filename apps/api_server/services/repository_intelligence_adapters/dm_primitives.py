from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

DM_SOURCE_SUFFIXES = frozenset({".dm"})
DM_CONFIG_SUFFIXES = frozenset({".dme"})
DM_SUFFIXES = DM_SOURCE_SUFFIXES | DM_CONFIG_SUFFIXES
_INCLUDE_RE = re.compile(r'^\s*#include\s+[<"](?P<target>[^">\n]+)[>"]', re.MULTILINE)
_TYPE_RE = re.compile(
    r"^\s*(?P<path>/[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)+)\b(?!\s*\()",
    re.MULTILINE,
)
_EXPLICIT_PROC_RE = re.compile(
    r"^\s*(?:(?P<owner>/[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*)/)?"
    r"(?P<kind>proc|verb)/(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_BARE_PROC_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)\n]*\)\s*$",
    re.MULTILINE,
)
_CALL_RE = re.compile(r"(?<![./])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_TYPE_REFERENCE_RE = re.compile(
    r"(?<!\w)(?P<path>/[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)+)"
)
_DEFINE_RE = re.compile(r"^\s*#define\b", re.MULTILINE)
_VAR_RE = re.compile(r"\bvar/[A-Za-z_][A-Za-z0-9_]*\b")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "break",
        "continue",
        "del",
        "do",
        "else",
        "for",
        "goto",
        "if",
        "new",
        "proc",
        "return",
        "set",
        "spawn",
        "switch",
        "try",
        "var",
        "verb",
        "while",
    }
)


@dataclass(frozen=True)
class _SymbolEntry:
    name: str
    kind: str
    start_line: int
    qualified_names: tuple[str, ...]


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _ordered_names(*raw_names: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        candidate = str(raw_name or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return tuple(ordered)


def _coerce_stripped_text(text: str, stripped_text: str | None = None) -> str:
    return strip_comments(text) if stripped_text is None else stripped_text


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    if "/*" not in text and "//" not in text:
        return text
    characters: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    block_depth = 0
    index = 0
    while index < len(text):
        character = text[index]
        next_two = text[index : index + 2]
        if block_depth:
            if next_two == "/*":
                block_depth += 1
                characters.extend("  ")
                index += 2
                continue
            if next_two == "*/":
                block_depth -= 1
                characters.extend("  ")
                index += 2
                continue
            characters.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_single or in_double:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif in_single and character == "'":
                in_single = False
            elif in_double and character == '"':
                in_double = False
            index += 1
            continue
        if next_two == "/*":
            block_depth = 1
            characters.extend("  ")
            index += 2
            continue
        if next_two == "//":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == "'":
            in_single = True
        elif character == '"':
            in_double = True
        index += 1
    return "".join(characters)


def strip_comments(text: str) -> str:
    return _strip_comments_cached(text)


def has_dm_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return normalized_path.suffix.lower() in DM_SUFFIXES


def is_probable_dm_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_dm_path_hints(normalized_path):
        return False
    stripped_text = _coerce_stripped_text(text, stripped_text)
    if not stripped_text.strip():
        return False
    if normalized_path.suffix.lower() in DM_CONFIG_SUFFIXES:
        return bool(_INCLUDE_RE.search(stripped_text) or _DEFINE_RE.search(stripped_text))
    return bool(
        _INCLUDE_RE.search(stripped_text)
        or _TYPE_RE.search(stripped_text)
        or _EXPLICIT_PROC_RE.search(stripped_text)
        or _BARE_PROC_RE.search(stripped_text)
        or _VAR_RE.search(stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] in {"code", "interface", "maps"}:
        parts = parts[1:]
    if parts and parts[-1] in {"_setup", "main"}:
        parts = parts[:-1] or parts
    return "/".join(part for part in parts if part)


def parse_include_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        if not target:
            continue
        item = (target, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def candidate_include_paths(
    *,
    current_file: str,
    include_target: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_target = (
        str(include_target or "")
        .strip()
        .strip('"')
        .strip("'")
        .replace("\\", "/")
        .lstrip("/")
    )
    if not normalized_target:
        return ()
    target_path = PurePosixPath(normalized_target)
    current_directory = PurePosixPath(current_file).parent
    candidate_keys: list[str] = []
    if normalized_target.startswith(("./", "../")):
        candidate_keys.append(current_directory.joinpath(target_path).as_posix())
    else:
        candidate_keys.extend(
            (normalized_target, current_directory.joinpath(target_path).as_posix())
        )
    if target_path.suffix.lower() not in DM_SUFFIXES:
        candidate_keys.extend(f"{candidate}.dm" for candidate in tuple(candidate_keys))
        candidate_keys.extend(f"{candidate}.dme" for candidate in tuple(candidate_keys))
    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if normalized_candidate and normalized_candidate not in seen:
            seen.add(normalized_candidate)
            normalized_candidates.append(normalized_candidate)
    return tuple(normalized_candidates)


def resolve_include(
    *,
    current_file: str,
    include_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_candidates = candidate_include_paths(
        current_file=current_file,
        include_target=include_target,
        normalize_repository_relative_path=normalize_repository_relative_path,
    )
    for candidate_key in normalized_candidates:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=tuple(normalized_candidates))


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[_SymbolEntry, ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    entries: list[_SymbolEntry] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _TYPE_RE.finditer(stripped_text):
        path = str(match.group("path") or "").strip()
        if not path:
            continue
        item = ("type", path, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(
            _SymbolEntry(
                name=path,
                kind="type",
                start_line=item[2],
                qualified_names=_ordered_names(path, path.lstrip("/"), path.lstrip("/").replace("/", ".")),
            )
        )
    for match in _EXPLICIT_PROC_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        kind = str(match.group("kind") or "").strip() or "proc"
        owner = str(match.group("owner") or "").strip()
        if not name or name in _RESERVED_SYMBOL_NAMES:
            continue
        line_number = _line_number(stripped_text, match.start())
        item = (kind, name, line_number)
        if item in seen:
            continue
        seen.add(item)
        qualified_owner = owner.lstrip("/")
        entries.append(
            _SymbolEntry(
                name=name,
                kind=kind,
                start_line=line_number,
                qualified_names=_ordered_names(
                    name,
                    f"{owner}/{kind}/{name}" if owner else f"{kind}/{name}",
                    f"{qualified_owner.replace('/', '.')}.{name}" if qualified_owner else "",
                ),
            )
        )
    for match in _BARE_PROC_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name in _RESERVED_SYMBOL_NAMES:
            continue
        line_number = _line_number(stripped_text, match.start())
        item = ("proc", name, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(
            _SymbolEntry(
                name=name,
                kind="proc",
                start_line=line_number,
                qualified_names=(name,),
            )
        )
    return tuple(sorted(entries, key=lambda entry: (entry.start_line, entry.kind, entry.name)))


def iter_call_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _CALL_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name in _RESERVED_SYMBOL_NAMES:
            continue
        item = (name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_type_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _TYPE_REFERENCE_RE.finditer(stripped_text):
        path = str(match.group("path") or "").strip()
        if not path:
            continue
        item = (path, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: tuple[_SymbolEntry, ...], *, line_number: int
) -> str | None:
    current_name: str | None = None
    for entry in symbol_entries:
        if entry.start_line > line_number:
            break
        current_name = entry.name
    return current_name
