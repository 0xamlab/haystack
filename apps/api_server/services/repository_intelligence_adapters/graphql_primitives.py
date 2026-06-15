from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

GRAPHQL_SUFFIXES = frozenset({".graphql", ".graphqls", ".gql"})
_DEFINITION_RE = re.compile(
    r"(?im)^\s*(?:extend\s+)?"
    r"(?P<kind>schema|scalar|type|interface|union|enum|input|directive|fragment|query|mutation|subscription)"
    r"(?:\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*))?"
)
_IMPORT_RE = re.compile(
    r"""(?im)^\s*#\s*import\s+["'](?P<target>[^"']+)["']"""
)
_TYPE_REFERENCE_RE = re.compile(r":\s*\[?(?P<name>[A-Za-z_][A-Za-z0-9_]*)!?")
_IMPLEMENTS_RE = re.compile(r"(?im)\bimplements\s+(?P<names>[A-Za-z_][A-Za-z0-9_!\s&]+)")
_SCHEMA_ROOT_RE = re.compile(
    r"(?im)\b(?P<kind>query|mutation|subscription)\s*:\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_FRAGMENT_SPREAD_RE = re.compile(r"\.\.\.(?!on\b)(?P<name>[A-Za-z_][A-Za-z0-9_]*)")


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for line in str(text or "").splitlines():
        if re.match(r"^\s*#\s*import\b", line):
            lines.append(line)
            continue
        if "#" not in line:
            lines.append(line)
            continue
        quote: str | None = None
        escaped = False
        buffer: list[str] = []
        for character in line:
            if escaped:
                buffer.append(character)
                escaped = False
                continue
            if character == "\\" and quote is not None:
                buffer.append(character)
                escaped = True
                continue
            if character in {'"', "'"}:
                if quote == character:
                    quote = None
                elif quote is None:
                    quote = character
                buffer.append(character)
                continue
            if character == "#" and quote is None:
                break
            buffer.append(character)
        lines.append("".join(buffer))
    return "\n".join(lines)


def _looks_binaryish(text: str) -> bool:
    sample = str(text or "")[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _line_count(text: str) -> int:
    return max(1, str(text or "").count("\n") + 1)


def has_graphql_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in GRAPHQL_SUFFIXES


def is_probable_graphql_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_graphql_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text).strip()
    if not stripped_text:
        return False
    return bool(
        _DEFINITION_RE.search(stripped_text)
        or _IMPORT_RE.search(stripped_text)
        or _SCHEMA_ROOT_RE.search(stripped_text)
        or _FRAGMENT_SPREAD_RE.search(stripped_text)
        or stripped_text.startswith("{")
    )


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = PurePosixPath(str(file_path).replace("\\", "/"))
    without_suffix = normalized_path.with_suffix("")
    aliases = {
        str(normalized_path).replace("\\", "/"),
        without_suffix.name,
        ".".join(without_suffix.parts),
        "/".join(without_suffix.parts),
    }
    return {alias for alias in aliases if alias}


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    entries: list[dict[str, object]] = []
    for match in _DEFINITION_RE.finditer(strip_comments(text)):
        kind = str(match.group("kind") or "").strip().lower()
        name = str(match.group("name") or "").strip()
        if not name:
            continue
        line_number = _line_number(text, match.start())
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_kind": kind,
                        "symbol_name": name,
                        "line": line_number,
                    },
                ),
                "symbol_name": name,
                "symbol_kind": kind,
                "start_line": line_number,
                "end_line": line_number,
                "signature": match.group(0).strip(),
            }
        )
    return tuple(entries)


def iter_import_entries(text: str) -> tuple[tuple[str, int], ...]:
    return tuple(
        (str(match.group("target") or "").strip(), _line_number(text, match.start()))
        for match in _IMPORT_RE.finditer(strip_comments(text))
        if str(match.group("target") or "").strip()
    )


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    references: list[tuple[str, int]] = []
    for match in _TYPE_REFERENCE_RE.finditer(strip_comments(text)):
        references.append((str(match.group("name")), _line_number(text, match.start())))
    for match in _SCHEMA_ROOT_RE.finditer(strip_comments(text)):
        references.append((str(match.group("name")), _line_number(text, match.start())))
    for match in _FRAGMENT_SPREAD_RE.finditer(strip_comments(text)):
        references.append((str(match.group("name")), _line_number(text, match.start())))
    for match in _IMPLEMENTS_RE.finditer(strip_comments(text)):
        raw_names = str(match.group("names") or "")
        for name in re.split(r"\s*&\s*|\s+", raw_names):
            normalized_name = name.replace("!", "").strip()
            if normalized_name:
                references.append((normalized_name, _line_number(text, match.start())))
    return tuple(references)


def resolve_import(
    file_path: str,
    target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_repository_relative_path(str(target or "").strip())
    if not normalized_target or "://" in normalized_target:
        return None
    current_parent = PurePosixPath(file_path).parent
    target_path = PurePosixPath(normalized_target)
    if not target_path.is_absolute():
        target_path = current_parent / target_path
    normalized_path = normalize_repository_relative_path(str(target_path))
    suffix = PurePosixPath(normalized_path).suffix.lower()
    candidates = [normalized_path]
    if suffix not in GRAPHQL_SUFFIXES:
        candidates.extend(f"{normalized_path}{candidate_suffix}" for candidate_suffix in sorted(GRAPHQL_SUFFIXES))
    return resolve_suffix_match(module_index=module_index, suffixes=candidates)
