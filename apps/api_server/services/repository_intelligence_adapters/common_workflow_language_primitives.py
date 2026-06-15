from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

COMMON_WORKFLOW_LANGUAGE_SUFFIXES = frozenset({".cwl"})
_COMMENT_RE = re.compile(r"(?m)#.*$")
_DIRECTIVE_RE = re.compile(r'(?mi)^\s*(?:cwlVersion|class|inputs|outputs|steps)\s*:\s*')
_RUN_RE = re.compile(r'(?mi)^\s*run\s*:\s*(?P<target>[^#\n]+?)\s*$')
_IMPORT_RE = re.compile(r'(?mi)^\s*\$(?:include|import)\s*:\s*(?P<target>[^#\n]+?)\s*$')
_CLASS_RE = re.compile(r'(?mi)^\s*class\s*:\s*(?P<name>Workflow|CommandLineTool|ExpressionTool|Operation)\s*$')


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_common_workflow_language_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in COMMON_WORKFLOW_LANGUAGE_SUFFIXES


def is_probable_common_workflow_language_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if (
        PurePosixPath(path).suffix.lower() not in COMMON_WORKFLOW_LANGUAGE_SUFFIXES
        or not text
        or _looks_binaryish(text)
    ):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _DIRECTIVE_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def clean_import_target(value: str) -> str:
    return normalize_identifier(value)


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_import_target(import_target)
    if not cleaned_target:
        return None
    candidate_path = PurePosixPath(cleaned_target)
    current_dir = PurePosixPath(current_file).parent
    normalized_candidate = normalize_repository_relative_path(
        candidate_path if candidate_path.is_absolute() else current_dir / candidate_path
    )
    if not normalized_candidate:
        return None
    direct_match = module_index.get(normalized_candidate)
    if direct_match is not None:
        return direct_match
    suffixes = (
        (normalized_candidate,)
        if PurePosixPath(normalized_candidate).suffix.lower() in COMMON_WORKFLOW_LANGUAGE_SUFFIXES
        else tuple(
            f"{normalized_candidate}{suffix}"
            for suffix in sorted(COMMON_WORKFLOW_LANGUAGE_SUFFIXES)
        )
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    stripped_text = strip_comments(text)
    for pattern, kind in ((_RUN_RE, "runs"), (_IMPORT_RE, "imports")):
        for match in pattern.finditer(stripped_text):
            target = clean_import_target(match.group("target") or "")
            if not target:
                continue
            line_number = stripped_text.count("\n", 0, match.start()) + 1
            entries.append((kind, target, line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    for match in _CLASS_RE.finditer(stripped_text):
        class_name = normalize_identifier(match.group("name") or "")
        if not class_name:
            continue
        entries.append((class_name, "class", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in COMMON_WORKFLOW_LANGUAGE_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = _line_count(text)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {
                    "file_path": file_path,
                    "symbol_name": module_name,
                    "kind": "common_workflow_language",
                },
            ),
            symbol_name=module_name,
            symbol_kind="common_workflow_language",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"common workflow language {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": symbol_name, "kind": symbol_kind},
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}".strip(),
            )
        )
    return tuple(symbols)
