from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

ALLOY_SUFFIXES = frozenset({".als"})
_MODULE_RE = re.compile(
    r"(?im)^\s*module\s+(?P<name>[A-Za-z_][A-Za-z0-9_./]*(?:/[A-Za-z_][A-Za-z0-9_./]*)*)"
)
_OPEN_RE = re.compile(
    r"(?im)^\s*open\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_./]*(?:/[A-Za-z_][A-Za-z0-9_./]*)*)"
    r"(?:\[[^\]]*\])?"
    r"(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?"
)
_DECL_RE = re.compile(
    r"(?im)^\s*(?:(?:abstract|one|lone|some|private)\s+)*(?P<sig_kind>sig|enum)\s+"
    r"(?P<sig_name>[A-Za-z_][A-Za-z0-9_]*)\b"
    r"|^\s*(?P<decl_kind>pred|fun|fact|assert)\s+"
    r"(?P<decl_name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_MARKER_RE = re.compile(
    r"(?im)^\s*module\s+[A-Za-z_][A-Za-z0-9_./]*(?:/[A-Za-z_][A-Za-z0-9_./]*)*|"
    r"^\s*open\s+[A-Za-z_][A-Za-z0-9_./]*(?:/[A-Za-z_][A-Za-z0-9_./]*)*|"
    r"^\s*(?:(?:abstract|one|lone|some|private)\s+)*(?:sig|enum)\s+[A-Za-z_][A-Za-z0-9_]*\b|"
    r"^\s*(?:pred|fun|fact|assert)\s+[A-Za-z_][A-Za-z0-9_]*\b|"
    r"^\s*(?:run|check)\b"
)
_IDENTIFIER_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "all",
        "and",
        "as",
        "assert",
        "check",
        "disj",
        "else",
        "enum",
        "exactly",
        "extends",
        "fact",
        "for",
        "fun",
        "iden",
        "iff",
        "implies",
        "in",
        "Int",
        "int",
        "let",
        "lone",
        "module",
        "no",
        "none",
        "not",
        "one",
        "open",
        "or",
        "pred",
        "private",
        "run",
        "set",
        "sig",
        "some",
        "sum",
        "this",
        "univ",
    }
)


def strip_comments(text: str) -> str:
    characters = list(text.lstrip("\ufeff"))
    index = 0
    in_string: str | None = None
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if in_string is not None:
            if current == "\\":
                index += 2
                continue
            if current == in_string:
                in_string = None
            index += 1
            continue
        if current in {'"', "'"}:
            in_string = current
            index += 1
            continue
        if current == "/" and next_char == "*":
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            while index + 1 < len(characters):
                if characters[index] == "*" and characters[index + 1] == "/":
                    characters[index] = " "
                    characters[index + 1] = " "
                    index += 2
                    break
                if characters[index] != "\n":
                    characters[index] = " "
                index += 1
            continue
        if current == "-" and next_char == "-":
            while index < len(characters) and characters[index] != "\n":
                characters[index] = " "
                index += 1
            continue
        index += 1
    return "".join(characters)


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


def has_alloy_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in ALLOY_SUFFIXES


def _normalize_repository_like_path(value: str) -> str:
    normalized_parts: list[str] = []
    for part in PurePosixPath(str(value or "").replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts and normalized_parts[-1] != "..":
                normalized_parts.pop()
            else:
                normalized_parts.append(part)
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def normalize_module_name(value: str) -> str:
    normalized = normalize_identifier(value).split("[", 1)[0].strip()
    return _normalize_repository_like_path(normalized.replace(".", "/"))


def module_declaration(text: str) -> tuple[str | None, int | None]:
    stripped_text = strip_comments(text)
    match = _MODULE_RE.search(stripped_text)
    if match is None:
        return None, None
    module_name = normalize_module_name(str(match.group("name") or ""))
    if not module_name:
        return None, None
    return module_name, _line_number(stripped_text, match.start())


def is_probable_alloy_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    if not has_alloy_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_MARKER_RE.search(stripped_text))


def path_aliases_for_file(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    without_suffix = _normalize_repository_like_path(str(path.with_suffix("")))
    aliases = {
        _normalize_repository_like_path(file_path),
        without_suffix,
        without_suffix.replace("/", "."),
        path.stem,
    }
    return {alias for alias in aliases if alias}


def open_statements(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, str | None, int]] = []
    seen_statements: set[tuple[str, str | None, int]] = set()
    for match in _OPEN_RE.finditer(stripped_text):
        target_name = normalize_module_name(str(match.group("name") or ""))
        alias = normalize_identifier(str(match.group("alias") or "")) or None
        if not target_name:
            continue
        entry = (target_name, alias, _line_number(stripped_text, match.start()))
        if entry in seen_statements:
            continue
        seen_statements.add(entry)
        statements.append(entry)
    return tuple(statements)


def _symbol_name_and_kind(match: re.Match[str]) -> tuple[str, str]:
    sig_kind = str(match.group("sig_kind") or "").strip().lower()
    if sig_kind:
        symbol_name = normalize_identifier(str(match.group("sig_name") or ""))
        return symbol_name, {"sig": "signature", "enum": "enum"}[sig_kind]
    decl_kind = str(match.group("decl_kind") or "").strip().lower()
    symbol_name = normalize_identifier(str(match.group("decl_name") or ""))
    return symbol_name, {
        "pred": "predicate",
        "fun": "function",
        "fact": "fact",
        "assert": "assertion",
    }[decl_kind]


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    matches = list(_DECL_RE.finditer(stripped_text))
    entries: list[dict[str, object]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for index, match in enumerate(matches):
        symbol_name, symbol_kind = _symbol_name_and_kind(match)
        if not symbol_name:
            continue
        start_line = _line_number(stripped_text, match.start())
        dedupe_key = (symbol_name.lower(), symbol_kind, start_line)
        if dedupe_key in seen_entries:
            continue
        seen_entries.add(dedupe_key)
        next_line = (
            _line_number(stripped_text, matches[index + 1].start())
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
                "signature": match.group(0).strip(),
            }
        )
    return tuple(entries)


def iter_reference_targets(
    text: str,
    *,
    declared_symbol_entries: tuple[dict[str, object], ...],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    declared_names = {
        str(entry["symbol_name"]).lower()
        for entry in declared_symbol_entries
        if entry["symbol_name"]
    }
    declaration_start_lines = {
        (str(entry["symbol_name"]).lower(), int(entry["start_line"]))
        for entry in declared_symbol_entries
        if entry["symbol_name"]
    }
    targets: list[tuple[str, int]] = []
    seen_targets: set[tuple[str, int]] = set()
    for match in _IDENTIFIER_RE.finditer(stripped_text):
        target_name = normalize_identifier(str(match.group("name") or ""))
        if not target_name:
            continue
        lowered_name = target_name.lower()
        if lowered_name not in declared_names or lowered_name in _RESERVED_REFERENCE_NAMES:
            continue
        line_number = _line_number(stripped_text, match.start())
        if (lowered_name, line_number) in declaration_start_lines:
            continue
        entry = (target_name, line_number)
        if entry in seen_targets:
            continue
        seen_targets.add(entry)
        targets.append(entry)
    return tuple(targets)


def resolve_target(
    current_file: str,
    target_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_module_name(target_name)
    if not normalized_target:
        return None
    current_dir = _normalize_repository_like_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [
        normalized_target,
        f"{normalized_target}.als",
        normalized_target.replace("/", "."),
        PurePosixPath(normalized_target).name,
    ]
    if current_dir:
        candidate_keys.extend(
            {
                _normalize_repository_like_path(f"{current_dir}/{normalized_target}"),
                _normalize_repository_like_path(f"{current_dir}/{normalized_target}.als"),
            }
        )
    seen_candidates: set[str] = set()
    for candidate_key in candidate_keys:
        if not candidate_key or candidate_key in seen_candidates:
            continue
        seen_candidates.add(candidate_key)
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=(f"/{normalized_target}.als",))

