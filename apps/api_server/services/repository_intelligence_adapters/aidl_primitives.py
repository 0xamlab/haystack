from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    jvm as repository_jvm,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

AIDL_SUFFIXES = frozenset({".aidl"})

PACKAGE_RE = repository_jvm.PACKAGE_RE
IMPORT_RE = repository_jvm.IMPORT_RE
TYPE_REFERENCE_RE = repository_jvm.TYPE_REFERENCE_RE

AIDL_DECL_RE = re.compile(
    r"^\s*(?:@[A-Za-z_][A-Za-z0-9_\.]*\s+)*(?:oneway\s+)?"
    r"(?P<kind>interface|parcelable|union|enum)\s+"
    r"(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_AIDL_MARKER_RE = re.compile(
    r"(?m)^\s*(?:"
    r"package\s+[A-Za-z_][A-Za-z0-9_\.]*\s*;|"
    r"import\s+[A-Za-z_][A-Za-z0-9_\.]*\s*;|"
    r"(?:@[A-Za-z_][A-Za-z0-9_\.]*\s+)*(?:oneway\s+)?"
    r"(?:interface|parcelable|union|enum)\s+[A-Z][A-Za-z0-9_]*\b"
    r")"
)


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _line_count(text: str) -> int:
    return max(text.count("\n") + 1, 1)


def has_aidl_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in AIDL_SUFFIXES


def is_probable_aidl_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in AIDL_SUFFIXES:
        return False
    stripped_text = text.strip()
    if not stripped_text:
        return False
    return bool(_AIDL_MARKER_RE.search(stripped_text))


def iter_declared_type_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    entries: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for match in AIDL_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        symbol_kind = str(match.group("kind") or "").strip().lower()
        if not symbol_name or not symbol_kind or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        start_line = _line_number(text, match.start())
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "symbol",
                    {
                        "file_path": file_path,
                        "kind": symbol_kind,
                        "name": symbol_name,
                        "line": start_line,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": start_line,
                "end_line": start_line,
                "signature": match.group(0).strip(),
            }
        )
    return tuple(
        sorted(entries, key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
    )


def path_aliases_for_file(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = {
        file_path,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    return {alias for alias in aliases if alias and alias != "."}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    normalized_path = normalized_target.replace(".", "/")
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_path,
            f"{normalized_path}.aidl",
            f"{normalized_path}.java",
            f"{normalized_path}.kt",
            f"{normalized_path}.kts",
        ],
    )
