from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    plsql as repository_plsql,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

PLPGSQL_SUFFIXES = frozenset({".pgsql"})
_SQL_COMPATIBLE_SUFFIXES = frozenset({".sql"}) | PLPGSQL_SUFFIXES
_LANGUAGE_MARKER_RE = re.compile(r"(?i)\blanguage\s+plpgsql\b")
_DO_BLOCK_RE = re.compile(r"(?is)\bdo\s+\$\$.*?\$\$\s*language\s+plpgsql\b")
_DECLARE_RE = re.compile(r"(?im)^\s*declare\b")
_EXCEPTION_RE = re.compile(r"(?im)^\s*exception\b")
_PERFORM_RE = re.compile(r"(?im)^\s*perform\b")
_RETURN_QUERY_RE = re.compile(r"(?im)^\s*return\s+(?:next|query)\b")
_ELSIF_RE = re.compile(r"(?im)^\s*elsif\b")
_CREATE_TRIGGER_RE = re.compile(r"(?i)\bcreate\s+(?:or\s+replace\s+)?trigger\b")
_FUNCTION_BLOCK_RE = re.compile(
    r"(?is)\bcreate\s+(?:or\s+replace\s+)?"
    r"(?:function|procedure|trigger)\b.*?\bas\s+\$\$.*?\$\$\s*language\s+plpgsql\b"
)

strip_comments = repository_plsql.strip_comments
normalize_identifier = repository_plsql.normalize_identifier
symbol_name_parts = repository_plsql.symbol_name_parts


def has_plpgsql_path_hints(path: Path | PurePosixPath | str) -> bool:
    normalized_path = PurePosixPath(path)
    suffix = normalized_path.suffix.lower()
    if suffix in PLPGSQL_SUFFIXES:
        return True
    if suffix != ".sql":
        return False
    normalized_tokens = {
        re.sub(r"[^a-z0-9]+", "", token.lower())
        for token in normalized_path.parts
        if token not in {"", "."}
    }
    return bool(
        normalized_tokens
        & {"function", "functions", "procedure", "procedures", "trigger", "triggers", "plpgsql"}
    )


def is_probable_plpgsql_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    suffix = normalized_path.suffix.lower()
    if suffix not in _SQL_COMPATIBLE_SUFFIXES:
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    score = 0
    if _LANGUAGE_MARKER_RE.search(stripped_text):
        score += 4
    if _DO_BLOCK_RE.search(stripped_text):
        score += 3
    if _FUNCTION_BLOCK_RE.search(stripped_text):
        score += 3
    if _EXCEPTION_RE.search(stripped_text):
        score += 2
    if _DECLARE_RE.search(stripped_text):
        score += 1
    if _PERFORM_RE.search(stripped_text):
        score += 1
    if _RETURN_QUERY_RE.search(stripped_text):
        score += 1
    if _ELSIF_RE.search(stripped_text):
        score += 1
    if _CREATE_TRIGGER_RE.search(stripped_text):
        score += 1
    if suffix in PLPGSQL_SUFFIXES:
        return score >= 2
    return score >= 3


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _SQL_COMPATIBLE_SUFFIXES:
        return set()
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return set()
    if not is_probable_plpgsql_source(path=path, text=text):
        return set()
    aliases = {
        file_path.lower(),
        path.stem.lower(),
        str(path.with_suffix("")).lower(),
        str(path.with_suffix("")).replace("/", ".").lower(),
    }
    for symbol_entry in repository_plsql.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            str(alias).lower()
            for alias in symbol_entry["qualified_names"]
            if alias
        )
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def _candidate_suffixes(normalized_target: str, leaf_name: str) -> list[str]:
    namespace_path = normalized_target.replace(".", "/")
    suffixes: list[str] = []
    for suffix in (".pgsql", ".sql", ".pks", ".pkb", ".pls", ".prc", ".fnc", ".trg"):
        for base in (normalized_target, namespace_path, leaf_name):
            if base:
                suffixes.append(f"{base}{suffix}")
    return suffixes


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target, leaf_name = symbol_name_parts(import_target)
    if not normalized_target:
        return None
    for candidate in (normalized_target, leaf_name):
        if candidate and module_index.get(candidate) is not None:
            return module_index[candidate]
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=_candidate_suffixes(normalized_target, leaf_name),
    )


def resolve_target(
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    return resolve_import(
        reference_target,
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
    )
