from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

OPENEDGE_SUFFIXES = frozenset({".cls", ".i", ".p", ".pf", ".w"})

_OPENEDGE_GENERAL_RE = re.compile(
    r"(?im)^\s*(?:"
    r"class\s+[A-Za-z_][\w.]*\s*:|"
    r"interface\s+[A-Za-z_][\w.]*\s*:|"
    r"method\b.*\(|"
    r"procedure\s+[A-Za-z_][\w-]*\b|"
    r"using\s+[A-Za-z_][\w.]*(?:\.\*)?\.|"
    r"define\s+(?:input|output|input-output|variable|buffer|temp-table)\b|"
    r"assign\b|"
    r"run\s+[A-Za-z_./\\-]+|"
    r"return\b|"
    r"create\s+[A-Za-z_][\w-]*\b|"
    r"display\b"
    r")"
)
_OPENEDGE_SPECIFIC_RE = re.compile(
    r"(?im)(?:"
    r"\bno-undo\b|"
    r"\broutine-level\s+on\s+error\b|"
    r"\bfor\s+each\b|"
    r"\bfind\s+first\b|"
    r"\bfile-info:[A-Za-z-]+\b|"
    r"\bundo,\s*throw\b|"
    r"\bend\s+(?:class|interface|method|procedure)\.|"
    r"\btemp-table\b|"
    r"\bvalid-object\s*\(|"
    r"\btype-of\s*\(|"
    r"\binput\s+parameter\b|"
    r"\boutput\s+parameter\b"
    r")"
)
_OPENEDGE_PARAM_FILE_RE = re.compile(
    r"(?im)^\s*-(?:basekey|cpinternal|cpstream|db|param|pf|p)\b"
)
_OPENEDGE_PREPROCESSOR_RE = re.compile(r"(?im)^\s*&(?:if|then|endif|scoped-define|global-define)\b")
_TEX_CLASS_RE = re.compile(r"(?im)^\\(?:NeedsTeXFormat|ProvidesClass)\b")
_VBA_CLASS_RE = re.compile(r"(?im)^\s*(?:VERSION\s+\d+\.\d+\s+CLASS|Attribute\s+VB_)")
_APEX_CLASS_RE = re.compile(
    r"(?im)^\s*(?:public|global|private|protected)\s+(?:with|without)\s+sharing\b|@isTest\b"
)

_CLASS_RE = re.compile(r"(?im)^\s*class\s+(?P<name>[A-Za-z_][\w.]*)\b")
_INTERFACE_RE = re.compile(r"(?im)^\s*interface\s+(?P<name>[A-Za-z_][\w.]*)\b")
_PROCEDURE_RE = re.compile(r"(?im)^\s*procedure\s+(?P<name>[A-Za-z_][\w-]*)\b")
_METHOD_RE = re.compile(r"(?im)^\s*method\b[^(]*\b(?P<name>[A-Za-z_][\w]*)\s*\(")
_TEMP_TABLE_RE = re.compile(r"(?im)^\s*define\s+temp-table\s+(?P<name>[A-Za-z_][\w-]*)\b")

_INCLUDE_RE = re.compile(r"\{(?!&)(?P<target>[A-Za-z0-9_./\\-]+(?:\.[A-Za-z0-9_]+)?)")
_RUN_RE = re.compile(r"(?im)^\s*run\s+(?P<target>[A-Za-z0-9_./\\-]+\.(?:cls|p|w))\b")
_USING_RE = re.compile(r"(?im)^\s*using\s+(?P<target>[A-Za-z_][\w.]*(?:\.\*)?)\s*\.")
_INHERITS_RE = re.compile(
    r"(?im)^\s*class\s+[A-Za-z_][\w.]*\s+inherits\s+(?P<target>[A-Za-z_][\w.]*)\b"
)
_IMPLEMENTS_RE = re.compile(
    r"(?im)\bimplements\s+(?P<targets>[A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*)\s*:"
)


def has_openedge_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in OPENEDGE_SUFFIXES


def _looks_binaryish(text: str) -> bool:
    return "\x00" in text


def is_probable_openedge_source(*, path: Path | PurePosixPath, text: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix not in OPENEDGE_SUFFIXES or not text or _looks_binaryish(text):
        return False
    if suffix == ".pf":
        return _OPENEDGE_PARAM_FILE_RE.search(text) is not None
    if suffix == ".cls":
        if _TEX_CLASS_RE.search(text) or _VBA_CLASS_RE.search(text) or _APEX_CLASS_RE.search(text):
            return False
    general_match = _OPENEDGE_GENERAL_RE.search(text) is not None
    specific_match = _OPENEDGE_SPECIFIC_RE.search(text) is not None
    if suffix == ".i":
        return specific_match or (
            _OPENEDGE_PREPROCESSOR_RE.search(text) is not None and general_match
        )
    return general_match and specific_match


def module_name_from_path(file_path: str) -> str:
    return PurePosixPath(file_path).stem


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[str, ...]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(str(file_path).replace("\\", "/"))
    suffix = normalized_path.suffix.lower()
    aliases: set[str] = {
        str(normalized_path),
        normalized_path.name,
        normalized_path.stem,
    }
    without_suffix = normalized_path.with_suffix("")
    aliases.add(str(without_suffix))
    if suffix in OPENEDGE_SUFFIXES:
        parts = without_suffix.parts
        for index in range(len(parts)):
            tail_parts = parts[index:]
            aliases.add("/".join(tail_parts))
            aliases.add(".".join(tail_parts))
    return tuple(sorted(alias for alias in aliases if alias))


def _symbol_name(match_name: str) -> str:
    return match_name.rsplit(".", 1)[-1]


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    project_name = module_name_from_path(file_path)
    project_symbol_id = stable_identifier(
        "sym",
        {"file_path": file_path, "kind": "module", "name": project_name},
    )
    symbols: list[_Symbol] = [
        _Symbol(
            symbol_id=project_symbol_id,
            symbol_name=project_name,
            symbol_kind="module",
            start_line=1,
            end_line=max(1, text.count("\n") + 1),
            parent_symbol_id=None,
            signature=None,
        )
    ]
    for regex, kind in (
        (_CLASS_RE, "class"),
        (_INTERFACE_RE, "interface"),
        (_PROCEDURE_RE, "procedure"),
        (_METHOD_RE, "method"),
        (_TEMP_TABLE_RE, "temp_table"),
    ):
        for match in regex.finditer(text):
            symbol_name = _symbol_name(match.group("name"))
            line_number = text.count("\n", 0, match.start()) + 1
            symbols.append(
                _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "kind": kind,
                            "name": symbol_name,
                            "line": line_number,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=kind,
                    start_line=line_number,
                    end_line=line_number,
                    parent_symbol_id=project_symbol_id,
                    signature=None,
                )
            )
    return tuple(symbols)


def clean_dependency_target(target: str) -> str:
    cleaned = str(target).strip().strip("\"'{} ").rstrip(".:")
    return cleaned.replace("\\", "/")


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for regex, dependency_type in (
        (_INCLUDE_RE, "include"),
        (_RUN_RE, "run"),
        (_USING_RE, "using"),
        (_INHERITS_RE, "inherits"),
    ):
        for match in regex.finditer(text):
            target = clean_dependency_target(match.group("target"))
            if not target:
                continue
            line_number = text.count("\n", 0, match.start()) + 1
            entries.append((dependency_type, target, line_number))
    for match in _IMPLEMENTS_RE.finditer(text):
        line_number = text.count("\n", 0, match.start()) + 1
        for target in match.group("targets").split(","):
            cleaned = clean_dependency_target(target)
            if cleaned:
                entries.append(("implements", cleaned, line_number))
    return tuple(entries)

