from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

BRIGHTSCRIPT_SOURCE_SUFFIXES = frozenset({".brs"})
BRIGHTSCRIPT_CONFIG_BASENAMES = frozenset({"manifest"})
_COMMENT_KEYWORD_RE = re.compile(
    r"(?im)\b(?:sub|function|library|createobject|createscene|end\s+sub|end\s+function)\b"
)
_CONFIG_SIGNAL_RE = re.compile(
    r"(?im)^\s*(?:title|major_version|minor_version|build_version|mm_icon_focus_hd|"
    r"splash_screen_hd|ui_resolutions|supports_input_launch|bs_libs_required)\s*="
)
_IMPORT_RE = re.compile(r'(?im)^\s*Library\s+"(?P<target>[^"]+)"')
_DECLARATION_RE = re.compile(
    r"(?im)^\s*(?:(?:public|private)\s+)?(?P<kind>sub|function|class|interface|enum)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_CALL_RE = re.compile(r"(?<![.\w])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_QUALIFIED_RE = re.compile(
    r"\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_PKG_PREFIX_RE = re.compile(r"^(?:pkg:/*|libpkg:/*)", re.IGNORECASE)
_RESERVED_CALL_NAMES = frozenset(
    {
        "and",
        "as",
        "box",
        "createobject",
        "createscene",
        "each",
        "else",
        "end",
        "false",
        "for",
        "function",
        "if",
        "invalid",
        "library",
        "not",
        "or",
        "print",
        "return",
        "step",
        "sub",
        "then",
        "true",
        "while",
    }
)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _line_count(text: str) -> int:
    return max(1, str(text or "").count("\n") + 1)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        chars: list[str] = []
        index = 0
        in_string = False
        while index < len(raw_line):
            character = raw_line[index]
            if character == '"':
                chars.append(character)
                if in_string and index + 1 < len(raw_line) and raw_line[index + 1] == '"':
                    chars.append('"')
                    index += 2
                    continue
                in_string = not in_string
                index += 1
                continue
            if character == "'" and not in_string:
                break
            chars.append(character)
            index += 1
        lines.append("".join(chars))
    return "\n".join(lines)


def _looks_binaryish(text: str) -> bool:
    sample = str(text or "")[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _normalize_path(value: str) -> str:
    raw_parts = PurePosixPath(str(value).replace("\\", "/")).parts
    normalized_parts: list[str] = []
    for part in raw_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def _normalize_import_target(target: str) -> str:
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return ""
    normalized_target = _PKG_PREFIX_RE.sub("", normalized_target)
    normalized_target = normalized_target.lstrip("/")
    return _normalize_path(normalized_target)


def has_brightscript_path_hints(path: Path | PurePosixPath | str) -> bool:
    pure_path = PurePosixPath(path)
    return (
        pure_path.suffix.lower() in BRIGHTSCRIPT_SOURCE_SUFFIXES
        or pure_path.name.lower() in BRIGHTSCRIPT_CONFIG_BASENAMES
    )


def is_probable_brightscript_config(*, path: Path | PurePosixPath, text: str) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.name.lower() not in BRIGHTSCRIPT_CONFIG_BASENAMES or not text or _looks_binaryish(
        text
    ):
        return False
    return bool(_CONFIG_SIGNAL_RE.search(text))


def is_probable_brightscript_source(*, path: Path | PurePosixPath, text: str) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.suffix.lower() not in BRIGHTSCRIPT_SOURCE_SUFFIXES or not text or _looks_binaryish(
        text
    ):
        return False
    stripped_text = strip_comments(text).strip()
    if not stripped_text:
        return False
    return bool(_COMMENT_KEYWORD_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(_normalize_path(file_path))
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = _normalize_path(file_path)
    pure_path = PurePosixPath(normalized_path)
    without_suffix = pure_path.with_suffix("")
    aliases = {
        normalized_path,
        str(without_suffix),
        pure_path.name,
        without_suffix.name,
        ".".join(without_suffix.parts),
    }
    return {alias for alias in aliases if alias}


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    entries: list[dict[str, object]] = []
    for match in _DECLARATION_RE.finditer(stripped_text):
        kind = str(match.group("kind") or "").strip().lower()
        name = str(match.group("name") or "").strip()
        if not kind or not name:
            continue
        line_number = _line_number(stripped_text, match.start())
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
    stripped_text = strip_comments(text)
    return tuple(
        (_normalize_import_target(str(match.group("target") or "")), _line_number(stripped_text, match.start()))
        for match in _IMPORT_RE.finditer(stripped_text)
        if _normalize_import_target(str(match.group("target") or ""))
    )


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for match in _QUALIFIED_RE.finditer(stripped_text):
        item = (
            str(match.group("owner") or "").strip() or None,
            str(match.group("name") or "").strip(),
            _line_number(stripped_text, match.start()),
        )
        if item[1] and item not in seen:
            seen.add(item)
            references.append(item)
    for match in _CALL_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name.lower() in _RESERVED_CALL_NAMES:
            continue
        item = (None, name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(references)


def resolve_import(
    file_path: str,
    target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(target)
    if not normalized_target:
        return None
    target_path = PurePosixPath(normalized_target)
    if not target_path.is_absolute() and "/" not in normalized_target:
        target_path = PurePosixPath(file_path).parent / target_path
        normalized_target = _normalize_path(str(target_path))
    normalized_target = normalize_repository_relative_path(normalized_target)
    direct_target = module_index.get(normalized_target)
    if direct_target:
        return direct_target
    candidates = [normalized_target]
    if PurePosixPath(normalized_target).suffix.lower() not in BRIGHTSCRIPT_SOURCE_SUFFIXES:
        candidates.extend(
            f"{normalized_target}{suffix}" for suffix in sorted(BRIGHTSCRIPT_SOURCE_SUFFIXES)
        )
    return resolve_suffix_match(module_index=module_index, suffixes=candidates)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = _normalize_path(file_path)
    aliases = path_aliases_for_file(normalized_path)
    absolute_path = root_path / normalized_path
    try:
        text = absolute_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return aliases
    pure_path = PurePosixPath(normalized_path)
    if pure_path.name.lower() in BRIGHTSCRIPT_CONFIG_BASENAMES:
        return aliases
    if not is_probable_brightscript_source(path=Path(normalized_path), text=text):
        return aliases
    for entry in iter_declared_symbol_entries(
        text=text,
        file_path=normalized_path,
        stable_identifier=lambda _kind, _payload: "",
    ):
        aliases.add(str(entry["symbol_name"]))
    return {alias for alias in aliases if alias}


def source_symbol_name_for_line(
    symbol_entries: Iterable[dict[str, object]],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for entry in symbol_entries:
        symbol_line = int(entry.get("start_line") or 0)
        if symbol_line <= line_number:
            current_name = str(entry.get("symbol_name") or "")
    return current_name or None
