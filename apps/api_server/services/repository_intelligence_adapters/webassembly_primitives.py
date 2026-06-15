from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]

WEBASSEMBLY_SUFFIXES = frozenset({".wat", ".wast"})
_DECLARATION_RE = re.compile(
    r"(?im)\(\s*(?P<kind>func|global|memory|table|type)\s+(?P<name>\$[^\s\)]+)"
)
_IMPORT_RE = re.compile(
    r'(?im)\(\s*import\s+"(?P<module>[^"]+)"\s+"(?P<name>[^"]+)"'
)
_REFERENCE_RE = re.compile(
    r"(?im)(?:\(\s*)?(?:call|global\.get|global\.set|table\.get|table\.set|ref\.func)\s+(?P<name>\$[^\s\)]+)"
)
_FEATURE_RE = re.compile(
    r"(?im)\(\s*module\b|\(\s*func\b|\(\s*memory\b|\(\s*import\b|\(\s*export\b"
)


def strip_comments(text: str) -> str:
    return re.sub(r";;.*$", "", str(text or ""), flags=re.MULTILINE)


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


def _normalize_symbol_name(raw_name: str) -> str:
    normalized_name = str(raw_name or "").strip()
    return normalized_name[1:] if normalized_name.startswith("$") else normalized_name


def has_webassembly_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in WEBASSEMBLY_SUFFIXES


def is_probable_webassembly_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_webassembly_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text).strip()
    return bool(stripped_text and _FEATURE_RE.search(stripped_text))


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
    for match in _DECLARATION_RE.finditer(strip_comments(text)):
        symbol_name = _normalize_symbol_name(match.group("name") or "")
        if not symbol_name:
            continue
        line_number = _line_number(text, match.start())
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_kind": str(match.group("kind") or "").strip().lower(),
                        "symbol_name": symbol_name,
                        "line": line_number,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": str(match.group("kind") or "").strip().lower(),
                "start_line": line_number,
                "end_line": line_number,
                "signature": match.group(0).strip(),
            }
        )
    return tuple(entries)


def iter_import_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        (
            str(match.group("module") or "").strip(),
            str(match.group("name") or "").strip(),
            _line_number(text, match.start()),
        )
        for match in _IMPORT_RE.finditer(strip_comments(text))
        if str(match.group("module") or "").strip() and str(match.group("name") or "").strip()
    )


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    return tuple(
        (_normalize_symbol_name(match.group("name") or ""), _line_number(text, match.start()))
        for match in _REFERENCE_RE.finditer(strip_comments(text))
        if _normalize_symbol_name(match.group("name") or "")
    )
