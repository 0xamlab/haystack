from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".v"})
COQ_CONFIG_BASENAMES = frozenset({"_coqproject", "_rocqproject"})
_MODULE_SEGMENT_RE = r"[A-Z][A-Za-z0-9_']*"
_IDENTIFIER_SEGMENT_RE = r"[A-Za-z_][A-Za-z0-9_']*"
_REQUIRE_RE = re.compile(
    rf"(?m)^\s*(?:From\s+(?P<prefix>{_MODULE_SEGMENT_RE}(?:\.{_MODULE_SEGMENT_RE})*)\s+)?"
    rf"Require\s+(?:(?P<qualifier>Import|Export)\s+)?"
    rf"(?P<modules>{_MODULE_SEGMENT_RE}(?:\.{_MODULE_SEGMENT_RE})*(?:\s+{_MODULE_SEGMENT_RE}(?:\.{_MODULE_SEGMENT_RE})*)*)\s*\."
)
_SYMBOL_RE = re.compile(
    rf"(?m)^\s*(?P<kind>Definition|Fixpoint|CoFixpoint|Lemma|Theorem|Corollary|Proposition|"
    rf"Fact|Example|Inductive|CoInductive|Record|Class|Instance|Ltac|Module\s+Type|Module)\s+"
    rf"(?P<name>{_IDENTIFIER_SEGMENT_RE})\b"
)
_QUALIFIED_REFERENCE_RE = re.compile(
    rf"\b(?P<module>{_MODULE_SEGMENT_RE}(?:\.{_MODULE_SEGMENT_RE})*)\.(?P<name>{_IDENTIFIER_SEGMENT_RE})\b"
)
_IDENTIFIER_RE = re.compile(rf"\b(?P<name>{_IDENTIFIER_SEGMENT_RE})\b")
_PROJECT_LOAD_PATH_RE = re.compile(
    rf"(?m)^\s*-(?P<flag>R|Q|I)\s+(?P<path>\S+)(?:\s+(?P<namespace>{_MODULE_SEGMENT_RE}(?:\.{_MODULE_SEGMENT_RE})*))?\s*$"
)
_PROJECT_SOURCE_FILE_RE = re.compile(r"(?m)^\s*(?P<path>[^-\s#][^#]*?\.v)\s*$")
_COMMENT_LINE_RE = re.compile(r"(?m)(?P<comment>\(\*|\*\))")
_PROBABLE_SOURCE_MARKERS = (
    "Require Import",
    "Require Export",
    "Qed.",
    "Defined.",
    "Lemma ",
    "Theorem ",
    "Proof.",
    "Inductive ",
    "Fixpoint ",
)
_PROJECT_MARKERS = ("-Q ", "-R ", "-I ", ".v")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "Abort",
        "Admitted",
        "Check",
        "CoFixpoint",
        "CoInductive",
        "Class",
        "Corollary",
        "Definition",
        "Defined",
        "End",
        "Example",
        "Fact",
        "Fixpoint",
        "From",
        "Hint",
        "Import",
        "Inductive",
        "Instance",
        "Lemma",
        "Ltac",
        "Module",
        "Notation",
        "Proof",
        "Proposition",
        "Qed",
        "Record",
        "Require",
        "Section",
        "Set",
        "Theorem",
        "Typeclasses",
        "Unset",
        "Variable",
        "Variables",
    }
    | {
        "apply",
        "assumption",
        "auto",
        "constructor",
        "destruct",
        "eauto",
        "exact",
        "induction",
        "intros",
        "left",
        "now",
        "pose",
        "refine",
        "repeat",
        "rewrite",
        "right",
        "simpl",
        "split",
        "subst",
        "symmetry",
        "trivial",
        "unfold",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def strip_comments(text: str) -> str:
    characters = list(text)
    depth = 0
    index = 0
    while index < len(characters):
        current = characters[index]
        next_character = characters[index + 1] if index + 1 < len(characters) else ""
        if current == "(" and next_character == "*":
            depth += 1
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            continue
        if depth > 0:
            if current == "*" and next_character == ")":
                depth = max(0, depth - 1)
                characters[index] = " "
                characters[index + 1] = " "
                index += 2
                continue
            if current != "\n":
                characters[index] = " "
            index += 1
            continue
        index += 1
    return "".join(characters)


def has_coq_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in _KNOWN_SUFFIXES
        or normalized_path.name.lower() in COQ_CONFIG_BASENAMES
    )


def is_probable_coq_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_coq_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if normalized_path.name.lower() in COQ_CONFIG_BASENAMES:
        return any(marker in stripped_text for marker in _PROJECT_MARKERS)
    return any(marker in stripped_text for marker in _PROBABLE_SOURCE_MARKERS) or bool(
        _REQUIRE_RE.search(stripped_text) or _SYMBOL_RE.search(stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    stem_parts = list(path.with_suffix("").parts)
    for root_name in ("theories", "src", "lib", "plugins", "examples", "test", "tests"):
        if root_name not in stem_parts:
            continue
        root_index = stem_parts.index(root_name)
        tail_parts = stem_parts[root_index + 1 :]
        if tail_parts:
            return ".".join(tail_parts)
    return path.stem


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _SYMBOL_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if (
            not symbol_name
            or symbol_name in seen_names
            or symbol_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        seen_names.add(symbol_name)
        symbol_kind = str(match.group("kind") or "").strip().lower().replace(" ", "_")
        entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def parse_require_modules(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    modules: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _REQUIRE_RE.finditer(stripped_text):
        prefix = str(match.group("prefix") or "").strip()
        line_number = _line_number(stripped_text, match.start())
        raw_modules = str(match.group("modules") or "").strip()
        for module_name in raw_modules.split():
            normalized_module = module_name.strip()
            if not normalized_module:
                continue
            qualified_module = (
                f"{prefix}.{normalized_module}"
                if prefix and "." not in normalized_module
                else normalized_module
            )
            entry = (qualified_module, line_number)
            if entry in seen:
                continue
            seen.add(entry)
            modules.append(entry)
    return tuple(modules)


def parse_project_roots(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    roots: list[str] = []
    seen: set[str] = set()
    for match in _PROJECT_LOAD_PATH_RE.finditer(stripped_text):
        candidate_root = str(match.group("path") or "").strip()
        if not candidate_root or candidate_root in seen:
            continue
        seen.add(candidate_root)
        roots.append(candidate_root)
    return tuple(roots)


def parse_project_sources(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    sources: list[str] = []
    seen: set[str] = set()
    for match in _PROJECT_SOURCE_FILE_RE.finditer(stripped_text):
        candidate_source = str(match.group("path") or "").strip()
        if not candidate_source or candidate_source in seen:
            continue
        seen.add(candidate_source)
        sources.append(candidate_source)
    return tuple(sources)
