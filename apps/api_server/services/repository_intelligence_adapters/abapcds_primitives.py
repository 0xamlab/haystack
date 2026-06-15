from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

ABAPCDS_SUFFIXES = frozenset({".asddls"})

ABAPCDS_DECL_RE = re.compile(
    r"^\s*define\s+"
    r"(?:(?:root|custom|transient|abstract)\s+)*"
    r"(?:(?:view\s+entity)|(?:view)|(?:abstract\s+entity))\s+"
    r"(?P<name>(?:/[A-Za-z0-9_]+/)?[A-Za-z0-9_]+)\b",
    re.IGNORECASE | re.MULTILINE,
)
SELECT_FROM_RE = re.compile(
    r"\bas\s+select\s+from\s+(?P<target>(?:/[A-Za-z0-9_]+/)?[A-Za-z0-9_]+)\b",
    re.IGNORECASE,
)
PROJECTION_ON_RE = re.compile(
    r"\bas\s+projection\s+on\s+(?P<target>(?:/[A-Za-z0-9_]+/)?[A-Za-z0-9_]+)\b",
    re.IGNORECASE,
)
ASSOCIATION_TO_RE = re.compile(
    r"\bassociation\s+\[[^\]]+\]\s+to\s+(?P<target>(?:/[A-Za-z0-9_]+/)?[A-Za-z0-9_]+)\b",
    re.IGNORECASE,
)
_ABAPCDS_MARKER_RE = re.compile(
    r"(?is)\bdefine\s+"
    r"(?:(?:root|custom|transient|abstract)\s+)*"
    r"(?:(?:view\s+entity)|(?:view)|(?:abstract\s+entity))\s+"
    r"(?:/[A-Za-z0-9_]+/)?[A-Za-z0-9_]+\b"
)


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _line_count(text: str) -> int:
    return max(text.count("\n") + 1, 1)


def _normalize_entity_name(name: str) -> str:
    return str(name or "").strip()


def _entity_name_to_repository_stem(name: str) -> str:
    normalized_name = _normalize_entity_name(name)
    if not normalized_name:
        return ""
    return normalized_name.replace("/", "#").lower()


def _repository_stem_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    filename = normalized_path.name.lower()
    if filename.endswith(".ddls.asddls"):
        return filename[: -len(".ddls.asddls")]
    if filename.endswith(".asddls"):
        return filename[: -len(".asddls")]
    return normalized_path.stem.lower()


def has_abapcds_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in ABAPCDS_SUFFIXES


def is_probable_abapcds_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in ABAPCDS_SUFFIXES:
        return False
    stripped_text = text.strip()
    if not stripped_text:
        return False
    return bool(_ABAPCDS_MARKER_RE.search(stripped_text))


def iter_declared_type_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    entries: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for match in ABAPCDS_DECL_RE.finditer(text):
        symbol_name = _normalize_entity_name(match.group("name"))
        if not symbol_name or symbol_name.lower() in seen_names:
            continue
        seen_names.add(symbol_name.lower())
        start_line = _line_number(text, match.start())
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "symbol",
                    {
                        "file_path": file_path,
                        "kind": "entity",
                        "name": symbol_name,
                        "line": start_line,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": "entity",
                "start_line": start_line,
                "end_line": start_line,
                "signature": match.group(0).strip(),
            }
        )
    return tuple(
        sorted(entries, key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
    )


def iter_reference_targets(text: str) -> tuple[tuple[str, int, str], ...]:
    entries: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int, str]] = set()
    for dependency_type, regex in (
        ("selects_from", SELECT_FROM_RE),
        ("projects_on", PROJECTION_ON_RE),
        ("associates_to", ASSOCIATION_TO_RE),
    ):
        for match in regex.finditer(text):
            target_name = _normalize_entity_name(match.group("target"))
            if not target_name:
                continue
            entry = (target_name, _line_number(text, match.start()), dependency_type)
            if entry in seen:
                continue
            seen.add(entry)
            entries.append(entry)
    return tuple(entries)


def path_aliases_for_file(file_path: str) -> set[str]:
    aliases = {
        file_path,
        _repository_stem_from_path(file_path),
    }
    return {alias for alias in aliases if alias}


def resolve_target(
    target_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_entity_name(target_name)
    if not normalized_target:
        return None
    for candidate_key in (
        normalized_target,
        normalized_target.lower(),
        _entity_name_to_repository_stem(normalized_target),
    ):
        if candidate_key and candidate_key in module_index:
            return module_index[candidate_key]
    repository_stem = _entity_name_to_repository_stem(normalized_target)
    if not repository_stem:
        return None
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            repository_stem,
            f"{repository_stem}.ddls.asddls",
            f"/{repository_stem}.ddls.asddls",
            f"{repository_stem}.asddls",
            f"/{repository_stem}.asddls",
        ],
    )
